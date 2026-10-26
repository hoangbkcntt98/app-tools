"""YouTube Data API video upload tool."""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Mapping

from .config import section_config
from .google_auth import build_google_service

YOUTUBE_UPLOAD_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def upload_video(
    video_path: str | Path,
    *,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    category_id: str | None = None,
    privacy_status: str | None = None,
    made_for_kids: bool | None = None,
    contains_synthetic_media: bool | None = None,
    publish_at: str | None = None,
    config: Mapping[str, Any] | str | Path | None = None,
    service: Any = None,
) -> dict[str, Any]:
    """Upload a video with metadata supplied by call or YouTube config."""
    path = Path(video_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(path)
    if not title.strip():
        raise ValueError("title is required")
    settings = section_config(config, "youtube")
    privacy = privacy_status or settings.get("privacy_status")
    category = category_id or settings.get("category_id")
    if not privacy:
        raise ValueError("Provide privacy_status or youtube.privacy_status in config")
    if not category:
        raise ValueError("Provide category_id or youtube.category_id in config")
    if privacy not in {"private", "unlisted", "public"}:
        raise ValueError("privacy_status must be private, unlisted, or public")
    kids_setting = made_for_kids
    if kids_setting is None:
        kids_setting = settings.get("made_for_kids")
    synthetic_setting = contains_synthetic_media
    if synthetic_setting is None:
        synthetic_setting = settings.get("contains_synthetic_media")
    for key, value in (
        ("made_for_kids", kids_setting),
        ("contains_synthetic_media", synthetic_setting),
    ):
        if value is not None and not isinstance(value, bool):
            raise ValueError(f"youtube.{key} must be a boolean")
    if service is None:
        try:
            from googleapiclient.http import MediaFileUpload
        except ImportError as exc:
            raise RuntimeError("Google API client package is required for YouTube uploads") from exc
        service = build_google_service(
            "youtube",
            "v3",
            config,
            scopes=list(settings.get("scopes") or YOUTUBE_UPLOAD_SCOPES),
            overrides={
                key: value
                for key, value in {
                    "auth_type": settings.get("auth_type", "oauth"),
                    "oauth_client_file": settings.get("oauth_client_file"),
                    "token_file": settings.get("token_file"),
                    "service_account_file": settings.get("service_account_file"),
                    "api_name": settings.get("api_name", "youtube"),
                    "api_version": settings.get("api_version", "v3"),
                }.items()
                if value is not None
            },
        )
    else:
        try:
            from googleapiclient.http import MediaFileUpload
        except ImportError as exc:
            raise RuntimeError("Google API client package is required for YouTube uploads") from exc

    status: dict[str, Any] = {"privacyStatus": privacy}
    if kids_setting is not None:
        status["selfDeclaredMadeForKids"] = kids_setting
    if synthetic_setting is not None:
        status["containsSyntheticMedia"] = synthetic_setting
    if publish_at:
        status["publishAt"] = publish_at
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": list(tags if tags is not None else settings.get("tags", [])),
            "categoryId": str(category),
        },
        "status": status,
    }
    media = MediaFileUpload(
        str(path),
        mimetype=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        resumable=bool(settings.get("resumable_upload", True)),
        chunksize=int(settings.get("chunk_size_bytes", -1)),
    )
    return service.videos().insert(
        part=str(settings.get("upload_parts", "snippet,status")),
        body=body,
        media_body=media,
    ).execute()
