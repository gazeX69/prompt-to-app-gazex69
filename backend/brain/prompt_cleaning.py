import re


_PLANNING_SECTION_PATTERNS = [
    r"^\s*daftar\s+tugas\s*:",
    r"^\s*task\s+list\s*:",
    r"^\s*rencana\s+implementasi\s*:",
    r"^\s*implementation\s+plan\s*:",
    r"^\s*mvp\s+yang\s+direkomendasikan\s*:",
    r"^\s*recommended\s+mvp\s*:",
    r"^\s*pertanyaan\s*:",
    r"^\s*questions?\s*:",
    r"^\s*use\s+this\s+confirmed\s+mvp\s+scope\s*:",
]


def clean_user_intent_prompt(prompt: str | None) -> str:
    text = (prompt or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    kept: list[str] = []
    for line in lines:
        if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in _PLANNING_SECTION_PATTERNS):
            break
        kept.append(line)
    return "\n".join(kept).strip()
