"""
Resolve Canvas credentials from 1Password CLI.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional


class CredentialError(RuntimeError):
    """Raised when Canvas credentials cannot be resolved."""


@dataclass
class CanvasCredentials:
    """Canvas login credentials with lazy OTP from 1Password."""

    username: str
    password: str
    source: str = "1password"
    _otp_provider: Optional[Callable[[], str]] = None

    def get_otp(self) -> Optional[str]:
        """Return a fresh OTP when an OTP provider is configured."""
        if self._otp_provider is None:
            return None
        return self._otp_provider()

    @property
    def has_otp_provider(self) -> bool:
        return self._otp_provider is not None


def _op_available() -> bool:
    return shutil.which("op") is not None


def _run_op(args: list[str]) -> str:
    """Run ``op`` and return stdout, raising CredentialError on failure."""
    try:
        result = subprocess.run(
            ["op", *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise CredentialError(
            "1Password CLI (`op`) not found. Install it from "
            "https://developer.1password.com/docs/cli/get-started/"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise CredentialError("1Password CLI timed out waiting for authentication") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise CredentialError(
            "1Password CLI failed"
            + (f": {detail}" if detail else ". Sign in with `op signin` or enable app integration.")
        )
    return result.stdout.strip()


def _field_values(fields_json: str) -> dict[str, str]:
    """Parse ``op item get --fields ... --format json`` into label -> value."""
    data = json.loads(fields_json)
    values: dict[str, str] = {}

    if isinstance(data, dict):
        # Single field or label-keyed object
        if "value" in data and "label" in data:
            values[str(data["label"]).lower()] = str(data["value"])
        else:
            for key, value in data.items():
                if isinstance(value, dict) and "value" in value:
                    values[str(key).lower()] = str(value["value"])
                elif isinstance(value, str):
                    values[str(key).lower()] = value
        return values

    if isinstance(data, list):
        for field in data:
            if not isinstance(field, dict):
                continue
            label = str(field.get("label") or field.get("id") or "").lower()
            if label and "value" in field and field["value"] is not None:
                values[label] = str(field["value"])
        return values

    raise CredentialError("Unexpected 1Password field JSON format")


def _op_item_ref() -> tuple[Optional[str], Optional[str]]:
    item = (
        os.getenv("CANVAS_OP_ITEM")
        or os.getenv("OP_ITEM")
        or ""
    ).strip() or None
    vault = (
        os.getenv("CANVAS_OP_VAULT")
        or os.getenv("OP_VAULT")
        or ""
    ).strip() or None
    return item, vault


def _otp_from_1password(item: str, vault: Optional[str] = None) -> str:
    args = ["item", "get", item, "--otp"]
    if vault:
        args.extend(["--vault", vault])
    otp = _run_op(args)
    if not otp:
        raise CredentialError(
            f"1Password item '{item}' has no one-time password. "
            "Add a TOTP field to the Login item."
        )
    return otp.strip()


def _extract_login_fields(item_data: dict) -> tuple[str, str]:
    """Pull username/password from an ``op item get --format json`` payload."""
    by_label: dict[str, str] = {}
    by_purpose: dict[str, str] = {}

    for field in item_data.get("fields") or []:
        if not isinstance(field, dict):
            continue
        value = field.get("value")
        if value is None or value == "":
            continue
        value = str(value)
        label = str(field.get("label") or field.get("id") or "").lower().strip()
        purpose = str(field.get("purpose") or "").upper().strip()
        if label:
            by_label[label] = value
        if purpose:
            by_purpose[purpose] = value

    username = (
        by_purpose.get("USERNAME")
        or by_label.get("username")
        or by_label.get("email")
        or by_label.get("email address")
        or ""
    ).strip()
    password = by_purpose.get("PASSWORD") or by_label.get("password") or ""
    return username, password


def _op_field_value(item: str, field: str, vault: Optional[str] = None) -> str:
    """Read a single field value via ``op item get --fields`` (forces reveal)."""
    # Prefer label=... form documented by `op item get --help`
    field_ref = field if "=" in field else f"label={field}"
    args = ["item", "get", item, "--fields", field_ref, "--reveal"]
    if vault:
        args.extend(["--vault", vault])
    try:
        return _run_op(args).strip()
    except CredentialError:
        return ""


def _credentials_from_1password(item: str, vault: Optional[str] = None) -> CanvasCredentials:
    if not _op_available():
        raise CredentialError(
            "CANVAS_OP_ITEM is set but 1Password CLI (`op`) is not installed or not on PATH"
        )

    args = ["item", "get", item, "--format", "json", "--reveal"]
    if vault:
        args.extend(["--vault", vault])

    try:
        item_data = json.loads(_run_op(args))
    except json.JSONDecodeError as exc:
        raise CredentialError(f"Could not parse 1Password item '{item}' as JSON") from exc

    username, password = _extract_login_fields(item_data)

    # Full-item JSON sometimes omits concealed values; fetch fields directly.
    if not username:
        username = (
            _op_field_value(item, "username", vault)
            or _op_field_value(item, "email", vault)
        )
    if not password:
        password = _op_field_value(item, "password", vault)

    if not username or not password:
        labels = []
        for field in item_data.get("fields") or []:
            if isinstance(field, dict):
                label = field.get("label") or field.get("id") or "?"
                purpose = field.get("purpose") or ""
                labels.append(f"{label}" + (f"/{purpose}" if purpose else ""))
        detail = f" Found fields: {', '.join(labels)}." if labels else ""
        raise CredentialError(
            f"Could not resolve username/password from 1Password item '{item}'.{detail} "
            "Ensure the Login has username and password fields (use `op item get … --reveal`)."
        )

    return CanvasCredentials(
        username=username,
        password=password,
        source="1password",
        _otp_provider=lambda: _otp_from_1password(item, vault),
    )


def resolve_canvas_credentials() -> CanvasCredentials:
    """
    Resolve Canvas credentials from 1Password.

    Requires ``CANVAS_OP_ITEM`` (or ``OP_ITEM``), optional ``CANVAS_OP_VAULT``.
    OTP is fetched lazily via ``get_otp()`` at MFA time.
    """
    item, vault = _op_item_ref()
    if not item:
        raise CredentialError(
            "Canvas credentials not configured. Set CANVAS_OP_ITEM to your "
            "1Password Login item UUID or name (must include username, password, and OTP)."
        )
    return _credentials_from_1password(item, vault)
