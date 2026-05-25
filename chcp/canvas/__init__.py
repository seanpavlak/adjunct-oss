"""Playwright-based Canvas browser automation."""

__all__ = ["CanvasService"]


def __getattr__(name: str):
    if name == "CanvasService":
        from chcp.canvas.service import CanvasService

        return CanvasService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
