import logging
from uuid import uuid4
from backend.brain.schemas import CaseMemory, FailureMemory, PlanSignature
from backend.brain.memory_store import load_cases, load_failures, _write_array, MEMORY_FILES
from backend.services.ai_service import complete

logger = logging.getLogger(__name__)


def build_case_context(
    *,
    prompt: str,
    signature: PlanSignature,
    matched_cases: list | None = None,
    dss_recommendations: list[dict] | None = None,
    confidence: float | None = None,
) -> str:
    """
    Convert CBR + DSS results into a generation contract.
    This is intentionally phrased as confidence-based evidence, not truth.
    """
    lines = [
        "=== CBR + DSS DECISION CONTEXT ===",
        "Epistemic rule: treat every conclusion as a confidence estimate, never as absolute truth.",
        f"User request: {prompt.strip()}",
        (
            "Plan signature: "
            f"domain={signature.domain}, app_type={signature.app_type}, "
            f"complexity={signature.complexity}, intent={signature.intent}"
        ),
        f"Feature keywords: {', '.join(signature.feature_keywords) or 'none'}",
        f"Required capabilities: {', '.join(signature.required_capabilities) or 'none'}",
    ]
    if confidence is not None:
        lines.append(f"Decision confidence: {confidence:.2f}")

    strong_matches = [
        case
        for case in (matched_cases or [])
        if getattr(case, "score", 0.0) >= 0.5
        or (getattr(case, "domain", None) == signature.domain and getattr(case, "app_type", None) == signature.app_type)
    ]
    if strong_matches:
        lines.append("Retrieved local cases to reuse/adapt:")
        for case in strong_matches[:3]:
            lines.append(
                "- "
                f"{case.id} ({case.title}) score={case.score}; "
                f"solution={case.solution or case.summary or 'not recorded'}; "
                f"lessons={case.lessons_learned or 'not recorded'}"
            )
    else:
        lines.append("Retrieved local cases: no sufficiently strong case; create a new solution and retain learning after success.")

    if dss_recommendations:
        lines.append("DSS/SPK recommended defaults for unresolved decisions:")
        for rec in dss_recommendations:
            options = rec.get("options") or []
            best = max(options, key=lambda item: item.get("score", 0.0), default=None)
            if best:
                lines.append(
                    "- "
                    f"{rec.get('key')}: {best.get('text')} "
                    f"(confidence={best.get('score')}, risk={rec.get('risk')})"
                )

    lines.extend(
        [
            "Generation contract:",
            "- Reuse matching local case patterns when confidence is adequate; adapt them to the new request.",
            "- If memory is weak, generate a fresh implementation and keep it previewable.",
            "- Do not collapse broad app requests into hello world, static text, or placeholder pages.",
            "- For medium/large apps, deliver a working MVP slice with real UI flows, seeded data, state, and persistence where recommended.",
            "=== END CBR + DSS DECISION CONTEXT ===",
        ]
    )
    return "\n".join(lines)

def retain_case(prompt: str, signature: PlanSignature, detail: dict = None) -> CaseMemory:
    """
    Learns from a successful generation by saving it as a new case in memory.
    Uses LLM to summarize the prompt into a structured case representation.
    """
    title = f"{signature.app_type.replace('_', ' ').title()} App"
    summary = f"App generated for: {prompt}"
    constraints = "None specified"
    solution = "Generated components codebase"
    lessons = "None recorded"

    try:
        # Ask LLM to generate title, summary, constraints, solution, and lessons
        sys_prompt = "You are a software engineering memory recorder. Summarize user requests and solutions."
        user_prompt = (
            f"Based on this project prompt: '{prompt}', please analyze and provide:\n"
            f"1. TITLE: A title of the application (2-4 words, e.g., 'Task Board MVP')\n"
            f"2. SUMMARY: A short summary of what was generated (1 sentence)\n"
            f"3. CONSTRAINTS: Any constraints found or simulated (1 sentence, e.g., 'React frontend only, uses local storage')\n"
            f"4. SOLUTION: Overview of technical solution (1 sentence, e.g., 'Built responsive dashboard with Monaco layout and custom states')\n"
            f"5. LESSONS: Practical advice or lessons learned (1 sentence, e.g., 'Separate logic into custom hook for state consistency')\n"
            f"Format response exactly using the labels TITLE:, SUMMARY:, CONSTRAINTS:, SOLUTION:, and LESSONS:."
        )

        response = complete(
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            max_tokens=300,
            temperature=0.3
        )

        # Parse output
        for line in response.split("\n"):
            line_strip = line.strip()
            if line_strip.upper().startswith("TITLE:"):
                title = line_strip[len("TITLE:"):].strip()
            elif line_strip.upper().startswith("SUMMARY:"):
                summary = line_strip[len("SUMMARY:"):].strip()
            elif line_strip.upper().startswith("CONSTRAINTS:"):
                constraints = line_strip[len("CONSTRAINTS:"):].strip()
            elif line_strip.upper().startswith("SOLUTION:"):
                solution = line_strip[len("SOLUTION:"):].strip()
            elif line_strip.upper().startswith("LESSONS:"):
                lessons = line_strip[len("LESSONS:"):].strip()

    except Exception as e:
        logger.exception("Failed to call LLM for case summary generation, falling back to defaults: %s", e)

    new_case = CaseMemory(
        id=f"case_{uuid4().hex[:8]}",
        title=title,
        domain=signature.domain,
        app_type=signature.app_type,
        feature_keywords=signature.feature_keywords,
        required_capabilities=signature.required_capabilities,
        summary=summary,
        original_prompt=prompt,
        context="React + Vite (TypeScript), FastAPI (Python), Node.js Sandbox",
        constraints=constraints,
        solution=solution,
        lessons_learned=lessons
    )

    
    try:
        cases = load_cases()
        cases.append(new_case.dict())
        _write_array(MEMORY_FILES["cases"], cases)
        logger.info(f"Retained new case in memory: {new_case.id} ({new_case.title})")
    except Exception as e:
        logger.exception("Failed to write new case to memory: %s", e)
        
    return new_case


def retain_failure(prompt: str, signature: PlanSignature, error_message: str) -> FailureMemory:
    """
    Learns from a failed generation by saving it as a failure record in memory.
    The avoided capabilities will penalize similar future generations to avoid failures.
    """
    new_failure = FailureMemory(
        id=f"fail_{uuid4().hex[:8]}",
        domain=signature.domain,
        app_type=signature.app_type,
        failure_type="generation_error",
        avoided_capabilities=signature.required_capabilities,
        summary=error_message[:200] if error_message else "Unknown generation error"
    )
    
    try:
        failures = load_failures()
        failures.append(new_failure.dict())
        _write_array(MEMORY_FILES["failures"], failures)
        logger.info(f"Retained new failure in memory: {new_failure.id} (domain={new_failure.domain})")
    except Exception as e:
        logger.exception("Failed to write new failure to memory: %s", e)
        
    return new_failure
