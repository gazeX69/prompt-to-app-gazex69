import asyncio
import logging
import re

from backend.brain.prompt_cleaning import clean_user_intent_prompt
from backend.core.dependency_resolution import (
    apply_native_dependency_repair,
    has_unresolved_feature_dependency,
    has_unresolved_framework_dependency,
    resolve_dependency_health,
)
from backend.runtime_contract import RuntimeErrorCode
from backend.sockets.manager import emit_agent_state, emit_runtime_error, emit_terminal_line
from backend.templates.react_vite_contract import (
    PROTECTED_CONTRACT_FILES,
    restore_canonical_react_vite_contract,
    validate_react_vite_contract,
)

logger = logging.getLogger(__name__)

def _extract_served_run_marker(html_text: str) -> str | None:
    patterns = [
        r'<meta\s+name=["\']ai-run-id["\']\s+content=["\']([^"\']+)["\']',
        r'data-run-id=["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text)
        if match:
            return match.group(1)
    return None


PLACEHOLDER_TEXT_PATTERNS = [
    "hello world",
    "hello vite",
    "vite + react",
    "edit src/app",
    "click on the vite",
    "placeholder",
    "coming soon",
    "generated app",
    "welcome to your app",
]


def _normalize_visible_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


INTENT_ALLOWED_PLACEHOLDER_TERMS = {
    "hello world": ["hello world", "hello", "halo world"],
    "welcome": ["welcome", "selamat datang"],
    "welcome to your app": ["welcome", "selamat datang"],
    "coming soon": ["coming soon", "segera hadir"],
}


def _is_intended_placeholder_text(pattern: str, prompt: str) -> bool:
    terms = INTENT_ALLOWED_PLACEHOLDER_TERMS.get(pattern, [])
    return any(term in prompt for term in terms)


def _placeholder_patterns_not_matching_intent(visible_text: str, prompt: str) -> list[str]:
    return [
        pattern
        for pattern in PLACEHOLDER_TEXT_PATTERNS
        if pattern in visible_text and not _is_intended_placeholder_text(pattern, prompt)
    ]


def _visible_text_matches_simple_intent(visible_text: str, prompt: str) -> bool:
    simple_intents = [
        (["hello world", "hello", "halo world"], ["hello world", "hello"]),
        (["welcome", "selamat datang"], ["welcome", "selamat datang"]),
        (["coming soon", "segera hadir"], ["coming soon", "segera hadir"]),
    ]
    return any(
        any(term in prompt for term in prompt_terms)
        and any(term in visible_text for term in visible_terms)
        for prompt_terms, visible_terms in simple_intents
    )


def _prompt_is_visual_change_intent(prompt: str) -> bool:
    visual_terms = [
        "background",
        "bacground",
        "bg",
        "warna",
        "color",
        "colour",
        "kuning",
        "yellow",
        "style",
        "styling",
        "tema",
        "theme",
        "ganti",
        "ubah",
        "change",
    ]
    return any(term in prompt for term in visual_terms)


def _intent_requirements(prompt_text: str) -> tuple[str, list[str], list[str], int]:
    try:
        from backend.brain.plan_signature import build_plan_signature

        signature = build_plan_signature(prompt_text)
        app_type = signature.app_type
    except Exception:
        app_type = "app"

    if app_type == "marketplace":
        return (
            app_type,
            ["product", "produk", "catalog", "katalog", "cart", "keranjang", "checkout", "admin"],
            ["product", "produk", "cart", "keranjang", "checkout"],
            5,
        )
    if app_type == "inventory":
        return (
            app_type,
            ["item", "barang", "stock", "stok", "quantity", "sku", "low stock", "stok rendah"],
            ["item", "barang", "stock", "stok"],
            4,
        )
    if app_type == "dashboard":
        return (
            app_type,
            ["dashboard", "metric", "analytics", "report", "chart", "summary"],
            ["dashboard", "metric", "summary"],
            2,
        )
    if app_type == "crud_app":
        return (
            app_type,
            ["crud", "record", "item", "create", "add", "edit", "update", "delete"],
            ["create", "add", "delete", "edit", "update"],
            2,
        )
    if app_type in {"recruitment", "finance", "booking", "pos", "cms", "lms", "saas", "social media"}:
        return (
            app_type,
            [app_type.replace("_", " "), "dashboard", "admin", "list", "form", "status"],
            ["dashboard", "admin", "list", "form"],
            3,
        )
    return app_type, [], [], 0


def _validate_preview_usability(
    *,
    prompt_text: str,
    body_text: str,
    root_text: str,
    root_child_count: int,
    interactive_count: int,
) -> tuple[bool, str | None]:
    visible_text = _normalize_visible_text(root_text or body_text)
    clean_prompt = clean_user_intent_prompt(prompt_text)
    prompt = _normalize_visible_text(clean_prompt)

    if root_child_count < 1:
        return False, "Application usability validation failed: React root has no mounted children."

    matched_intended_placeholders = [
        pattern
        for pattern in PLACEHOLDER_TEXT_PATTERNS
        if pattern in visible_text and _is_intended_placeholder_text(pattern, prompt)
    ]

    if len(visible_text) < 8 and not matched_intended_placeholders and not _visible_text_matches_simple_intent(visible_text, prompt):
        return False, "Application usability validation failed: rendered application has no meaningful visible content."

    if _placeholder_patterns_not_matching_intent(visible_text, prompt) and not _prompt_is_visual_change_intent(prompt):
        return False, "Application usability validation failed: rendered output appears to be a placeholder page."

    app_type, expected_terms, required_any_terms, min_interactive = _intent_requirements(clean_prompt)
    if expected_terms:
        matched_terms = [term for term in expected_terms if term in visible_text]
        if len(matched_terms) < 2:
            return False, f"Application usability validation failed: {app_type} prompt did not render enough domain-specific UI."
        if required_any_terms and not any(term in visible_text for term in required_any_terms):
            return False, f"Application usability validation failed: {app_type} prompt is missing required core flow terminology."
        if interactive_count < min_interactive:
            return False, f"Application usability validation failed: {app_type} UI does not expose enough visible controls."

    if "counter" in prompt:
        if "counter" not in visible_text and "count" not in visible_text:
            return False, "Application usability validation failed: counter prompt did not render counter/count UI."
        if interactive_count < 1:
            return False, "Application usability validation failed: counter UI has no visible control."

    if any(token in prompt for token in ["todo", "to-do", "task"]):
        if not any(token in visible_text for token in ["todo", "to-do", "task", "list"]):
            return False, "Application usability validation failed: todo prompt did not render todo/task/list UI."
        if interactive_count < 2:
            return False, "Application usability validation failed: todo UI does not expose enough visible controls."

    if any(token in prompt for token in ["crud", "create read update delete"]):
        if not any(token in visible_text for token in ["crud", "record", "item", "mvp"]):
            return False, "Application usability validation failed: CRUD prompt did not render record/item UI."
        if not any(token in visible_text for token in ["create", "add", "delete", "edit", "update"]):
            return False, "Application usability validation failed: CRUD UI does not expose create/update/delete affordances."
        if interactive_count < 2:
            return False, "Application usability validation failed: CRUD UI does not expose enough visible controls."

    return True, None


async def verify_rendered_dom_truth(preview_url: str, run_id: str, project_id: str, prompt_text: str, ecosystem: str) -> dict:
    clean_prompt_text = clean_user_intent_prompt(prompt_text)
    logger.info("[Validation] clean_prompt=%r", clean_prompt_text)
    if ecosystem != "react-vite":
        # Static HTML / PHP already validated raw HTML marker in HTTP step, 
        # but Playwright is optional to prove browser render
        pass

    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            await emit_terminal_line(f"[EventLoop] verification_start for {run_id}", "info", project_id)
            import time
            start_time = time.time()
            
            browser = await p.chromium.launch(headless=True)
            await emit_terminal_line(f"[Playwright] browser launched", "info", project_id)
            page = await browser.new_page()
            console_errors: list[str] = []
            page_errors: list[str] = []

            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))
            # ===========================
            try:
                response = await page.goto(
                    preview_url,
                    wait_until="domcontentloaded",
                    timeout=15000
                )

                await emit_terminal_line(
                    "[DEBUG] GOTO_OK",
                    "info",
                    project_id
                )

                if response is None or response.status >= 400:
                    raise RuntimeError(
                        f"Preview HTTP status invalid: {response.status if response else 'no response'}"
                    )

                await page.wait_for_load_state(
                    "networkidle",
                    timeout=15000
                )

                await emit_terminal_line(
                    "[DEBUG] NETWORKIDLE_OK",
                    "info",
                    project_id
                )

                await emit_terminal_line(
                    "[Playwright] page opened",
                    "info",
                    project_id
                )

                # ========================
                await emit_terminal_line(f"[P7.6] playwright validation started", "info", project_id)
                await emit_terminal_line(f"[Playwright] DOM verification started", "info", project_id)
                await page.wait_for_selector('#root', state='attached', timeout=5000)
            except Exception as e:
                await browser.close()
                if ecosystem != "react-vite":
                    return {
                        "success": True, 
                        "html_verified": True,
                        "source_verified": True,
                        "dom_verified": False,
                        "error": None
                    }
                return {
                    "success": False,
                    "html_verified": True,
                    "source_verified": True,
                    "dom_verified": False,
                    "error": f"Preview DOM verification failed before mount checks: {e}"
                }
            
            rendered_run_id = await page.evaluate("() => document.getElementById('runtime-truth')?.getAttribute('data-run-id')")
            
            # Real DOM Content Verification
            body_inner_text = await page.evaluate("() => document.body.innerText")
            body_inner_html = await page.evaluate("() => document.body.innerHTML")
            root_inner_text = await page.evaluate("() => document.getElementById('root')?.innerText || ''")
            root_child_count = await page.evaluate("() => document.getElementById('root')?.childElementCount || 0")
            interactive_count = await page.evaluate("""() => Array.from(
                document.querySelectorAll('button,input,textarea,select,a[href],[role="button"],[contenteditable="true"]')
            ).filter((element) => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
            }).length""")
            
            from backend.sandbox.executor import _safe_project_path
            run_dir = _safe_project_path(project_id, run_id)
            run_dir.mkdir(parents=True, exist_ok=True)
            
            screenshot_path = run_dir / "screenshot.png"
            dom_path = run_dir / "rendered_dom.html"
            
            await page.screenshot(path=str(screenshot_path))
            await emit_terminal_line(f"[Playwright] screenshot captured", "info", project_id)
            
            with open(dom_path, "w", encoding="utf-8") as f:
                f.write(body_inner_html)
                
            await browser.close()
            
            duration_ms = int((time.time() - start_time) * 1000)
            await emit_terminal_line(f"[EventLoop] verification_end (duration: {duration_ms}ms)", "info", project_id)
            await emit_terminal_line(f"[EventLoop] verification_duration_ms: {duration_ms}", "info", project_id)
            
            if not body_inner_text.strip() or len(body_inner_text.strip()) < 2:
                # Page is visually blank
                return {
                    "success": False,
                    "html_verified": True,
                    "source_verified": True,
                    "dom_verified": False,
                    "error": "Rendered preview is blank despite HTTP 200"
                }

            if not root_inner_text.strip() or root_child_count < 1:
                return {
                    "success": False,
                    "html_verified": True,
                    "source_verified": True,
                    "dom_verified": False,
                    "error": "React root exists but no rendered content was mounted inside #root"
                }

            if console_errors or page_errors:
                fatal = "; ".join((console_errors + page_errors)[:5])
                return {
                    "success": False,
                    "html_verified": True,
                    "source_verified": True,
                    "dom_verified": False,
                    "error": f"Fatal browser errors during preview: {fatal}"
                }

            usable, usability_error = _validate_preview_usability(
                prompt_text=clean_prompt_text,
                body_text=body_inner_text,
                root_text=root_inner_text,
                root_child_count=int(root_child_count or 0),
                interactive_count=int(interactive_count or 0),
            )
            if not usable:
                return {
                    "success": False,
                    "html_verified": True,
                    "source_verified": True,
                    "dom_verified": bool(rendered_run_id),
                    "usable": False,
                    "error": usability_error,
                }
            
            if rendered_run_id and rendered_run_id != run_id:
                return {
                    "success": False,
                    "html_verified": True,
                    "source_verified": True,
                    "dom_verified": False,
                    "error": f"DOM run_id mismatch. Expected {run_id}, got {rendered_run_id}"
                }
            
            return {
                "success": True,
                "html_verified": True,
                "source_verified": True,
                "dom_verified": bool(rendered_run_id),
                "usable": True,
                "error": None if rendered_run_id else "Runtime process is reachable, but DOM ownership marker is missing."
            }
            
    except ImportError:
        return {
            "success": ecosystem != "react-vite",
            "html_verified": True,
            "source_verified": True,
            "dom_verified": False,
            "error": "Playwright is not installed. DOM verification unavailable."
        }
    except Exception as e:
        if "Executable doesn't exist" in str(e) or "NotImplementedError" in str(e):
            return {
                "success": ecosystem != "react-vite",
                "html_verified": True,
                "source_verified": True,
                "dom_verified": False,
                "error": "Playwright is not installed. DOM verification unavailable."
            }
        return {
            "success": False,
            "html_verified": True,
            "source_verified": True,
            "dom_verified": False,
            "error": f"Playwright execution failed: {e}"
        }


async def _validate_dependency_resolution_environment(project_id: str, run_id: str, phase: str) -> tuple[bool, str | None]:
    report = await asyncio.to_thread(resolve_dependency_health, project_id, run_id)
    missing = report.get("missing_dependencies") or []
    if not missing and not (report.get("invalid_dependencies") or []):
        await emit_terminal_line(f"[DependencyValidator] Dependency health valid ({phase})", "info", project_id)
        return True, None

    if has_unresolved_framework_dependency(report):
        missing_names = ", ".join(sorted({str(item.get("package")) for item in missing if item.get("classification") == "framework"}))
        err = f"Framework dependency contract failure: {missing_names}"
        await emit_terminal_line(f"[DependencyValidator] {err}", "stderr", project_id)
        return False, err

    if has_unresolved_feature_dependency(report):
        missing_names = ", ".join(sorted({str(item.get("package")) for item in missing if item.get("classification") == "feature"}))
        await emit_terminal_line(f"[DependencyValidator] Feature dependency missing ({phase}): {missing_names}", "warning", project_id)
        repair_summary = "; ".join(
            f"{item.get('dependency')}:{item.get('strategy')}"
            for item in report.get("repair_strategy") or []
        )
        if repair_summary:
            await emit_terminal_line(f"[DependencyRepair] Proposed repair: {repair_summary}", "info", project_id)
        repaired = await asyncio.to_thread(apply_native_dependency_repair, project_id, run_id, report=report)
        if not has_unresolved_feature_dependency(repaired) and not (repaired.get("invalid_dependencies") or []):
            await emit_terminal_line("[DependencyRepair] Native dependency repair resolved feature imports", "info", project_id)
            return True, None
        unresolved = ", ".join(sorted({str(item.get("package")) for item in repaired.get("missing_dependencies") or []}))
        err = f"Dependency Resolution Failure: missing feature dependencies require package.json or source repair: {unresolved}"
        await emit_runtime_error(
            RuntimeErrorCode.E_DEPENDENCY_MISSING,
            err,
            project_id=project_id,
            run_id=run_id,
            source="dependency_resolution",
        )
        await emit_terminal_line(f"[DependencyValidator] {err}", "stderr", project_id)
        return False, err

    invalid_names = ", ".join(sorted({str(item.get("package")) for item in report.get("invalid_dependencies") or []}))
    err = f"Dependency Resolution Failure: invalid dependencies require review: {invalid_names}"
    await emit_runtime_error(
        RuntimeErrorCode.E_DEPENDENCY_MISSING,
        err,
        project_id=project_id,
        run_id=run_id,
        source="dependency_resolution",
    )
    await emit_terminal_line(f"[DependencyValidator] {err}", "stderr", project_id)
    return False, err


async def _validate_react_vite_environment(project_id: str, run_id: str, phase: str) -> tuple[bool, str | None]:
    await emit_agent_state("validating", project_id)
    report = await asyncio.to_thread(validate_react_vite_contract, project_id, run_id)
    if report.passed:
        await emit_terminal_line(f"[Contract] React/Vite environment valid ({phase})", "info", project_id)
        return await _validate_dependency_resolution_environment(project_id, run_id, phase)

    await emit_terminal_line(f"[Contract] React/Vite environment invalid ({phase}): {report.summary()}", "stderr", project_id)
    restored = await asyncio.to_thread(restore_canonical_react_vite_contract, project_id, run_id)
    await emit_terminal_line(f"[ContractRepair] Restored canonical files: {', '.join(restored)}", "info", project_id)

    repaired = await asyncio.to_thread(validate_react_vite_contract, project_id, run_id)
    if repaired.passed:
        await emit_terminal_line(f"[Contract] React/Vite environment valid after deterministic repair ({phase})", "info", project_id)
        return await _validate_dependency_resolution_environment(project_id, run_id, phase)

    return False, repaired.summary()


def _first_error_code(summary: str | None, fallback: RuntimeErrorCode = RuntimeErrorCode.E_CONTRACT_INVALID) -> str:
    if not summary:
        return fallback.value
    first = summary.split(";", 1)[0].split(":", 1)[0].strip()
    return first if first.startswith("E_") else fallback.value


async def _filter_react_vite_generated_files(files: list, project_id: str) -> list:
    allowed_files = []
    for f in files:
        normalized_path = f.path.replace("\\", "/")
        if normalized_path in PROTECTED_CONTRACT_FILES:
            await emit_terminal_line(f"[Contract] Skipping generated ecosystem contract overwrite: {normalized_path}", "warning", project_id)
            continue
        allowed_files.append(f)
    return allowed_files

