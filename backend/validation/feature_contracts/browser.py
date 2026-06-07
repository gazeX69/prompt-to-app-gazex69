from dataclasses import dataclass
from typing import Protocol
from typing import Any

from .actions import BrowserAction, BrowserActionResult


@dataclass
class FeatureBrowserSession:
    preview_url: str
    page: Any | None = None


class BrowserDriver(Protocol):
    async def open(self, preview_url: str) -> FeatureBrowserSession:
        ...

    async def close(self, session: FeatureBrowserSession) -> None:
        ...

    async def run_action(self, session: FeatureBrowserSession, action: BrowserAction) -> BrowserActionResult:
        ...


class PlaywrightBrowserDriver:
    """Playwright adapter boundary for future feature contracts.

    P10-F4 intentionally does not implement click/fill/type behavior. Contracts
    produce BrowserAction objects, and future phases can execute them through
    this adapter without coupling contracts directly to Playwright APIs.
    """

    async def open(self, preview_url: str) -> FeatureBrowserSession:
        return FeatureBrowserSession(preview_url=preview_url)

    async def close(self, session: FeatureBrowserSession) -> None:
        return None

    async def run_action(self, session: FeatureBrowserSession, action: BrowserAction) -> BrowserActionResult:
        return BrowserActionResult(
            action=action,
            success=False,
            message="Browser action execution is not implemented in P10-F4.",
            detail={"preview_url": session.preview_url},
        )


FeatureBrowserAdapter = PlaywrightBrowserDriver
