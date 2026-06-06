"""
Manual pause control for long-running CLI actions.

Ctrl+X requests a pause; processing stops at the next safe checkpoint and
waits for Enter before continuing. Close the browser or press Ctrl+C to exit.
"""

import sys
import threading
import time
from contextlib import contextmanager
from typing import Optional


class PauseController:
    """Thread-safe pause controller with optional Ctrl+X keyboard listener."""

    def __init__(self) -> None:
        self._pause_requested = threading.Event()
        self._stop_listener = threading.Event()
        self._stdin_reserved = threading.Event()
        self._listener_thread: Optional[threading.Thread] = None
        self._enabled = False

    def enable(self) -> None:
        """Start listening for Ctrl+X."""
        if self._enabled:
            return
        self._enabled = True
        self._stop_listener.clear()
        self._listener_thread = threading.Thread(
            target=self._listen_for_pause_key,
            daemon=True,
            name="pause-listener",
        )
        self._listener_thread.start()
        print("Press Ctrl+X to pause (Enter to resume), close browser or Ctrl+C to stop")

    def disable(self) -> None:
        """Stop the keyboard listener."""
        if not self._enabled:
            return
        self._enabled = False
        self._stop_listener.set()
        if self._listener_thread:
            self._listener_thread.join(timeout=1)
            self._listener_thread = None
        self._pause_requested.clear()
        self._stdin_reserved.clear()

    def request_pause(self) -> None:
        if not self._pause_requested.is_set():
            self._pause_requested.set()
            print("\nPause requested — finishing current step...")

    def is_pause_requested(self) -> bool:
        return self._pause_requested.is_set()

    def wait_if_paused(self) -> None:
        """Block until the user resumes if a pause was requested."""
        if not self._pause_requested.is_set():
            return
        with self.reserve_stdin():
            print("\nPaused — press Enter to resume (Ctrl+X to pause again)")
            try:
                input()
            except EOFError:
                pass
        self._pause_requested.clear()

    @contextmanager
    def reserve_stdin(self):
        """Prevent the listener from reading stdin while the main thread uses input()."""
        self._stdin_reserved.set()
        try:
            yield
        finally:
            self._stdin_reserved.clear()

    def _listen_for_pause_key(self) -> None:
        if sys.platform == "win32":
            self._listen_windows()
        else:
            self._listen_unix()

    def _listen_unix(self) -> None:
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        try:
            old_settings = termios.tcgetattr(fd)
        except termios.error:
            return

        try:
            while not self._stop_listener.is_set():
                if self._stdin_reserved.is_set():
                    if self._stop_listener.wait(0.1):
                        break
                    continue

                try:
                    tty.setcbreak(fd)
                    ready, _, _ = select.select([sys.stdin], [], [], 0.2)
                    if ready:
                        ch = sys.stdin.read(1)
                        if ch == "\x18":  # Ctrl+X
                            self.request_pause()
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            pass
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except termios.error:
                pass

    def _listen_windows(self) -> None:
        import msvcrt

        while not self._stop_listener.is_set():
            if self._stdin_reserved.is_set():
                if self._stop_listener.wait(0.1):
                    break
                continue
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch == b"\x18":
                    self.request_pause()
            time.sleep(0.1)


_controller: Optional[PauseController] = None


def get_pause_controller() -> PauseController:
    """Return the shared pause controller for the current process."""
    global _controller
    if _controller is None:
        _controller = PauseController()
    return _controller
