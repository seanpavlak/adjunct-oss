"""Run one Chromium process per course so class data cannot cross.

Each worker is a fresh Python process with its own Playwright browser.
The process environment seals the course key. A worker that is asked to
run a different course refuses before it opens a page or calls a model.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Optional, Sequence

from chcp.core.course_utils import active_course_keys, load_courses_config
from chcp.paths import REPO_ROOT

# Keep window launches from stacking on the same tick. MFA is not per window.
LAUNCH_STAGGER_SECONDS = 1.0


class PrefixWriter:
    """Prefix each line written by a course worker."""

    def __init__(self, stream, prefix: str):
        self._stream = stream
        self._prefix = prefix
        self._pending = ""
        self._chcp_prefixed = True

    def write(self, data: str) -> int:
        if not data:
            return 0
        text = self._pending + data
        self._pending = ""
        if not text.endswith("\n"):
            parts = text.split("\n")
            self._pending = parts.pop()
            lines = parts
        else:
            lines = text.split("\n")[:-1]
        rendered = "".join(f"{self._prefix}{line}\n" for line in lines)
        if rendered:
            self._stream.write(rendered)
        return len(data)

    def flush(self) -> None:
        if self._pending:
            self._stream.write(f"{self._prefix}{self._pending}")
            self._pending = ""
        self._stream.flush()

    def isatty(self) -> bool:
        return False

    def __getattr__(self, name: str):
        return getattr(self._stream, name)


def install_parallel_log_prefix() -> None:
    """Tag this process's stdout with its sealed course key."""
    if os.environ.get("CHCP_PARALLEL") != "1":
        return
    key = os.environ.get("CHCP_COURSE_KEY") or "?"
    if getattr(sys.stdout, "_chcp_prefixed", False):
        return
    prefix = f"[{key}] "
    sys.stdout = PrefixWriter(sys.stdout, prefix)
    sys.stderr = PrefixWriter(sys.stderr, prefix)


def course_keys(config: Optional[dict] = None) -> list[str]:
    loaded = config if config is not None else load_courses_config()
    courses = loaded.get("courses") or {}
    if not courses:
        raise ValueError("No courses found in courses.json")
    keys = active_course_keys(loaded)
    if not keys:
        raise ValueError("No active courses found in courses.json")
    return keys


def build_worker_commands(
    action: str,
    course_keys_to_run: Sequence[str],
    *,
    week: Optional[int] = None,
    provider: Optional[str] = None,
    extra_args: Optional[Sequence[str]] = None,
    storage_state_path: Optional[str] = None,
    python: Optional[str] = None,
    main_py: Optional[str] = None,
) -> list[tuple[list[str], dict]]:
    """One command and sealed environment per course. Nothing is shared."""
    executable = python or sys.executable
    entry = main_py or str(REPO_ROOT / "main.py")
    workers: list[tuple[list[str], dict]] = []
    for slot, key in enumerate(course_keys_to_run):
        cmd = [
            executable,
            entry,
            action,
            "--course",
            key,
            "--window-slot",
            str(slot),
        ]
        if week is not None:
            cmd.extend(["--week", str(week)])
        if provider:
            cmd.extend(["--provider", provider])
        if extra_args:
            cmd.extend(extra_args)
        env = os.environ.copy()
        env["CHCP_PARALLEL"] = "1"
        env["CHCP_COURSE_KEY"] = key
        env["CHCP_WINDOW_SLOT"] = str(slot)
        if storage_state_path:
            env["CHCP_STORAGE_STATE"] = storage_state_path
        workers.append((cmd, env))
    return workers


def _terminate(procs: Sequence[subprocess.Popen]) -> None:
    for proc in procs:
        if proc.poll() is None:
            proc.terminate()
    deadline = time.time() + 5
    for proc in procs:
        if proc.poll() is not None:
            continue
        remaining = max(0.1, deadline - time.time())
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            proc.kill()


def run_courses_in_parallel(
    action: str,
    *,
    week: Optional[int] = None,
    provider: Optional[str] = None,
    extra_args: Optional[Sequence[str]] = None,
    storage_state_path: Optional[str] = None,
) -> None:
    """Start every course in its own process and wait until each window closes."""
    keys = course_keys()
    workers = build_worker_commands(
        action,
        keys,
        week=week,
        provider=provider,
        extra_args=extra_args,
        storage_state_path=storage_state_path,
    )
    print(
        f"Starting {len(workers)} separate Chromium windows ({', '.join(keys)}). "
        "Each process loads only that course. Close a window to stop that course. "
        "Ctrl+C stops all of them."
    )
    procs: list[subprocess.Popen] = []
    try:
        for (cmd, env), key in zip(workers, keys):
            print(f"Launching course {key}")
            procs.append(
                subprocess.Popen(
                    cmd,
                    env=env,
                    cwd=str(REPO_ROOT),
                )
            )
            time.sleep(LAUNCH_STAGGER_SECONDS)
        pending = {key: proc for key, proc in zip(keys, procs)}
        while pending:
            for key, proc in list(pending.items()):
                code = proc.poll()
                if code is None:
                    continue
                print(f"[{key}] finished (exit {code})")
                del pending[key]
            if pending:
                time.sleep(0.4)
    except KeyboardInterrupt:
        print("\nStopping every course window...")
        _terminate(procs)
        raise
    finally:
        _terminate(procs)
