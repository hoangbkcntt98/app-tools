"""Google API credential and service construction helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .config import section_config


def _credential_path(settings: Mapping[str, Any], key: str) -> Path:
    value = settings.get(key)
    if not value:
        raise ValueError(f"Google config requires {key!r}")
    path = Path(str(value)).expanduser()
    if not path.is_absolute() and settings.get("_config_path"):
        path = Path(str(settings["_config_path"])).parent / path
    return path.resolve()


def create_credentials(
    config: Mapping[str, Any] | str | Path | None,
    *,
    scopes: list[str],
    overrides: Mapping[str, Any] | None = None,
):
    """Create configured OAuth or service-account Google credentials."""
    settings = section_config(config, "google", overrides)
    auth_type = str(settings.get("auth_type", "oauth")).strip().lower()
    try:
        if auth_type == "service_account":
            from google.oauth2.service_account import Credentials

            path = _credential_path(settings, "service_account_file")
            return Credentials.from_service_account_file(str(path), scopes=scopes)
        if auth_type != "oauth":
            raise ValueError("google.auth_type must be 'oauth' or 'service_account'")

        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            "Google API dependencies missing; install Google API client packages."
        ) from exc

    token_path = _credential_path(settings, "token_file")
    client_path = _credential_path(settings, "oauth_client_file")
    credentials = (
        Credentials.from_authorized_user_file(str(token_path), scopes)
        if token_path.is_file()
        else None
    )
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_path), scopes)
        credentials = flow.run_local_server(
            port=int(settings.get("oauth_port", 0)),
            timeout_seconds=int(settings.get("oauth_timeout_seconds", 300)),
        )
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def build_google_service(
    api_name: str,
    api_version: str,
    config: Mapping[str, Any] | str | Path | None,
    *,
    scopes: list[str],
    overrides: Mapping[str, Any] | None = None,
):
    """Build a Google API client using provided API identity and config."""
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Google API dependencies missing; install Google API client packages."
        ) from exc
    settings = section_config(config, "google", overrides)
    credentials = create_credentials(config, scopes=scopes, overrides=overrides)
    return build(
        str(settings.get("api_name", api_name)),
        str(settings.get("api_version", api_version)),
        credentials=credentials,
        cache_discovery=False,
    )
