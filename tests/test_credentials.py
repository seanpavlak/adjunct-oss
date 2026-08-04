"""
Unit tests for 1Password credential resolution
"""

import json
from unittest.mock import patch

import pytest

from chcp.core.credentials import (
    CanvasCredentials,
    CredentialError,
    _field_values,
    resolve_canvas_credentials,
)


class TestFieldValues:
    def test_list_of_fields(self):
        payload = json.dumps(
            [
                {"label": "username", "value": "user@example.com"},
                {"label": "password", "value": "secret"},
            ]
        )
        assert _field_values(payload) == {
            "username": "user@example.com",
            "password": "secret",
        }

    def test_single_field_object(self):
        payload = json.dumps({"label": "username", "value": "user@example.com"})
        assert _field_values(payload) == {"username": "user@example.com"}


class TestResolveCanvasCredentials:
    def test_missing_op_item_raises(self, monkeypatch):
        monkeypatch.delenv("CANVAS_OP_ITEM", raising=False)
        monkeypatch.delenv("OP_ITEM", raising=False)

        with pytest.raises(CredentialError, match="CANVAS_OP_ITEM"):
            resolve_canvas_credentials()

    def test_from_1password(self, monkeypatch):
        monkeypatch.setenv("CANVAS_OP_ITEM", "CHCP Canvas")
        monkeypatch.delenv("CANVAS_OP_VAULT", raising=False)
        monkeypatch.delenv("OP_VAULT", raising=False)

        item_json = json.dumps(
            {
                "fields": [
                    {
                        "id": "username",
                        "purpose": "USERNAME",
                        "label": "username",
                        "value": "op-user@example.com",
                    },
                    {
                        "id": "password",
                        "purpose": "PASSWORD",
                        "label": "password",
                        "value": "op-secret",
                    },
                ]
            }
        )

        def fake_run_op(args):
            if "--otp" in args:
                return "123456"
            if "--format" in args:
                return item_json
            raise AssertionError(f"Unexpected op args: {args}")

        with (
            patch("chcp.core.credentials._op_available", return_value=True),
            patch("chcp.core.credentials._run_op", side_effect=fake_run_op),
        ):
            creds = resolve_canvas_credentials()
            assert creds.username == "op-user@example.com"
            assert creds.password == "op-secret"
            assert creds.source == "1password"
            assert creds.has_otp_provider
            assert creds.get_otp() == "123456"

    def test_from_1password_email_field(self, monkeypatch):
        monkeypatch.setenv("CANVAS_OP_ITEM", "CHCP Canvas")
        item_json = json.dumps(
            {
                "fields": [
                    {"label": "email", "value": "email-user@example.com"},
                    {"label": "password", "value": "op-secret"},
                ]
            }
        )

        with (
            patch("chcp.core.credentials._op_available", return_value=True),
            patch("chcp.core.credentials._run_op", return_value=item_json),
        ):
            creds = resolve_canvas_credentials()
            assert creds.username == "email-user@example.com"

    def test_from_1password_direct_field_fallback(self, monkeypatch):
        """When JSON omits concealed values, fetch username/password via --fields."""
        monkeypatch.setenv("CANVAS_OP_ITEM", "CHCP Canvas")
        item_json = json.dumps(
            {
                "fields": [
                    {"label": "username", "purpose": "USERNAME", "type": "STRING"},
                    {"label": "password", "purpose": "PASSWORD", "type": "CONCEALED"},
                ]
            }
        )

        def fake_run_op(args):
            if "--format" in args:
                return item_json
            if "--fields" in args:
                field = args[args.index("--fields") + 1]
                if field in ("username", "label=username"):
                    return "direct-user@example.com"
                if field in ("password", "label=password"):
                    return "direct-secret"
            raise AssertionError(f"Unexpected op args: {args}")

        with (
            patch("chcp.core.credentials._op_available", return_value=True),
            patch("chcp.core.credentials._run_op", side_effect=fake_run_op),
        ):
            creds = resolve_canvas_credentials()
            assert creds.username == "direct-user@example.com"
            assert creds.password == "direct-secret"


class TestCanvasCredentials:
    def test_otp_provider(self):
        creds = CanvasCredentials(
            username="a",
            password="b",
            _otp_provider=lambda: "999111",
        )
        assert creds.get_otp() == "999111"
