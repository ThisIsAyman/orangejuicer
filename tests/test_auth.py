"""Tests for orangejuicer.auth"""

import os
from unittest.mock import MagicMock, patch

import pytest

from orangejuicer.auth import OTFAuth


def test_auth_reads_env_vars(monkeypatch):
    monkeypatch.setenv("OTF_EMAIL", "test@example.com")
    monkeypatch.setenv("OTF_PASSWORD", "secret")
    auth = OTFAuth()
    assert auth.email == "test@example.com"
    assert auth.password == "secret"


def test_auth_constructor_args_take_precedence(monkeypatch):
    monkeypatch.setenv("OTF_EMAIL", "env@example.com")
    monkeypatch.setenv("OTF_PASSWORD", "envpass")
    auth = OTFAuth(email="arg@example.com", password="argpass")
    assert auth.email == "arg@example.com"
    assert auth.password == "argpass"


def test_get_client_uses_credentials():
    mock_otf_user = MagicMock()
    mock_otf_instance = MagicMock()
    mock_otf_cls = MagicMock(return_value=mock_otf_instance)
    mock_user_cls = MagicMock(return_value=mock_otf_user)

    auth = OTFAuth(email="u@example.com", password="pw")

    with patch.dict("sys.modules", {"otf_api": MagicMock(Otf=mock_otf_cls, OtfUser=mock_user_cls)}):
        result = auth.get_client()

    mock_user_cls.assert_called_once_with("u@example.com", "pw")
    mock_otf_cls.assert_called_once_with(user=mock_otf_user)
    assert result is mock_otf_instance


def test_get_client_raises_import_error():
    auth = OTFAuth(email="u@example.com", password="pw")
    with patch.dict("sys.modules", {"otf_api": None}):
        with pytest.raises(ImportError, match="otf-api"):
            auth.get_client()
