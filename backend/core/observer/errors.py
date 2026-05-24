"""
Runtime error classification pipeline.

Captures terminal output, classifies errors, and produces structured diagnostics.
Does NOT implement self-healing — only structured observation.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ErrorCategory(str, Enum):
    MISSING_DEPENDENCY = "missing_dependency"
    MODULE_RESOLUTION = "module_resolution"
    SYNTAX_ERROR = "syntax_error"
    PORT_CONFLICT = "port_conflict"
    TYPE_ERROR = "type_error"
    BUILD_FAILURE = "build_failure"
    RUNTIME_EXCEPTION = "runtime_exception"
    MIGRATION_FAILURE = "migration_failure"
    PERMISSION_DENIED = "permission_denied"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class Diagnostic:
    category: ErrorCategory
    message: str
    source: str
    line: Optional[int] = None
    file: Optional[str] = None
    code: Optional[str] = None
    suggestion: Optional[str] = None
    raw_lines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "message": self.message,
            "source": self.source,
            "line": self.line,
            "file": self.file,
            "code": self.code,
            "suggestion": self.suggestion,
        }


_MODULE_RESOLVE_RE = re.compile(
    r"(?:Cannot find module|Module not found|Module parse failed|Failed to resolve)"
)
_DEPENDENCY_RE = re.compile(
    r"(?:Cannot find package|Module not found|npm ERR!.*not found|ERR_PNPM.*not found)"
)
_SYNTAX_RE = re.compile(
    r"(?:SyntaxError|Unexpected token|Parsing error|ParseError)"
)
_PORT_RE = re.compile(
    r"(?:EADDRINUSE|address already in use|port.*already in use)"
)
_TYPE_TS_RE = re.compile(
    r"(?:Type [\'\"]?[\w<>\[\],|& ]+[\'\"]? is not assignable|Property [\'\"]?\w+[\'\"]? does not exist)"
)
_PHP_ERROR_RE = re.compile(
    r"(?:Fatal error|Parse error|syntax error, unexpected|PHP Fatal error)"
)
_MIGRATION_RE = re.compile(
    r"(?:Migration failed|prisma migrate|migrate.*error|Can't write migration)"
)
_PERMISSION_RE = re.compile(
    r"(?:EACCES|permission denied|EPERM)"
)


def classify_error_line(line: str) -> Optional[ErrorCategory]:
    if _MODULE_RESOLVE_RE.search(line):
        return ErrorCategory.MODULE_RESOLUTION
    if _DEPENDENCY_RE.search(line):
        return ErrorCategory.MISSING_DEPENDENCY
    if _SYNTAX_RE.search(line):
        return ErrorCategory.SYNTAX_ERROR
    if _PORT_RE.search(line):
        return ErrorCategory.PORT_CONFLICT
    if _TYPE_TS_RE.search(line):
        return ErrorCategory.TYPE_ERROR
    if _PHP_ERROR_RE.search(line):
        return ErrorCategory.SYNTAX_ERROR
    if _MIGRATION_RE.search(line):
        return ErrorCategory.MIGRATION_FAILURE
    if _PERMISSION_RE.search(line):
        return ErrorCategory.PERMISSION_DENIED
    return None


def analyze_build_output(stdout: str, stderr: str) -> list[Diagnostic]:
    all_lines = (stderr + "\n" + stdout).splitlines()
    diagnostics: list[Diagnostic] = []
    seen_messages: set[str] = set()

    for i, line in enumerate(all_lines):
        cat = classify_error_line(line)
        if cat is None:
            continue

        if line.strip() in seen_messages:
            continue
        seen_messages.add(line.strip())

        diag = Diagnostic(
            category=cat,
            message=line.strip(),
            source="build",
            line=i + 1,
            raw_lines=[line],
        )

        diag.suggestion = _suggest_fix(cat, line)
        diagnostics.append(diag)

    if not diagnostics and stderr.strip():
        diagnostics.append(
            Diagnostic(
                category=ErrorCategory.UNKNOWN,
                message=stderr.strip()[:200],
                source="build",
                raw_lines=all_lines,
            )
        )

    return diagnostics


def analyze_dev_output(line: str) -> Optional[Diagnostic]:
    cat = classify_error_line(line)
    if cat is None:
        return None
    return Diagnostic(
        category=cat,
        message=line.strip()[:200],
        source="dev-server",
        suggestion=_suggest_fix(cat, line),
        raw_lines=[line],
    )


def _suggest_fix(cat: ErrorCategory, line: str) -> str:
    suggestions = {
        ErrorCategory.MISSING_DEPENDENCY: "Run the package manager install command for the missing package",
        ErrorCategory.MODULE_RESOLUTION: "Check the import path and ensure the module is installed",
        ErrorCategory.SYNTAX_ERROR: "Check for syntax issues near the reported line number",
        ErrorCategory.PORT_CONFLICT: "Kill the existing process on that port or use a different port",
        ErrorCategory.TYPE_ERROR: "Fix the type mismatch in the reported file",
        ErrorCategory.BUILD_FAILURE: "Review build configuration and dependency versions",
        ErrorCategory.RUNTIME_EXCEPTION: "Check the stack trace and fix the runtime error",
        ErrorCategory.MIGRATION_FAILURE: "Review migration files and database state",
        ErrorCategory.PERMISSION_DENIED: "Check file permissions and run with appropriate access",
        ErrorCategory.NETWORK_ERROR: "Check network connectivity and proxy settings",
        ErrorCategory.UNKNOWN: "Review the raw error output for clues",
    }
    return suggestions.get(cat, "Unknown error — review the output manually")
