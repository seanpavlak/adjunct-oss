"""One Canvas login shared by every ALL course window.

Canvas burns an MFA code on the first successful submit. The other windows
must reuse that browser session instead of asking for a second code.
The saved file is cookies for this login only. It does not contain a course's
discussion posts, prompts, or grades.
"""

from __future__ import annotations

import os
import tempfile
from typing import Callable, Optional

from chcp.settings import canvas_config


def url_needs_canvas_login(url: str) -> bool:
    """True when the browser is still on a Canvas login or MFA page."""
    return "/login" in (url or "")


def establish_canvas_session(
    email: str,
    password: str,
    otp_provider: Optional[Callable[[], Optional[str]]] = None,
) -> str:
    """Log in once and return a path to the Playwright storage state."""
    from chcp.canvas.service import CanvasService

    fd, path = tempfile.mkstemp(prefix="chcp-canvas-session-", suffix=".json")
    os.close(fd)
    os.chmod(path, 0o600)
    try:
        with CanvasService(headless=False) as canvas:
            canvas.login(email, password, otp_provider=otp_provider)
            canvas.page.goto(canvas_config.BASE_URL, wait_until="domcontentloaded")
            if not canvas.has_authenticated_session():
                raise RuntimeError(
                    "Canvas login did not finish, so no course windows were opened."
                )
            canvas.context.storage_state(path=path)
    except Exception:
        discard_session_file(path)
        raise
    print("Canvas login succeeded. Course windows will reuse this session.")
    return path


def discard_session_file(path: Optional[str]) -> None:
    """Remove a saved Canvas session. Missing files are ignored."""
    if not path:
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
