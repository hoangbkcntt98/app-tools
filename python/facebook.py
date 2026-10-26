"""Configuration-driven Facebook Page publishing and comment tools."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

import requests

from .config import section_config


class FacebookTool:
    def __init__(
        self,
        config: Mapping[str, Any] | str | Path | None = None,
        *,
        settings: Mapping[str, Any] | None = None,
        session: Any = None,
    ) -> None:
        self.settings = dict(settings or section_config(config, "facebook"))
        self.session = session or requests.Session()
        self.timeout = float(self.settings.get("timeout_seconds", 120))
        self.base_url = str(self.settings.get("graph_api_base", "")).rstrip("/")
        self.version = str(self.settings.get("graph_api_version", "")).strip("/")
        self.page_id = str(self.settings.get("page_id", "")).strip()
        self.access_token = self._get_token()
        if not self.base_url or not self.version:
            raise ValueError("facebook.graph_api_base and graph_api_version are required")

    def _get_token(self) -> str:
        token = str(self.settings.get("access_token", "")).strip()
        env_name = str(self.settings.get("access_token_env", "")).strip()
        if not token and env_name:
            token = os.environ.get(env_name, "").strip()
        if not token:
            raise ValueError(
                "Provide facebook.access_token or facebook.access_token_env."
            )
        return token

    def _request(self, method: str, object_path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}/{self.version}/{object_path.lstrip('/')}"
        params = dict(kwargs.pop("params", {}) or {})
        params["access_token"] = self.access_token
        response = self.session.request(
            method,
            url,
            params=params,
            timeout=self.timeout,
            **kwargs,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if not response.ok or (isinstance(payload, dict) and payload.get("error")):
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise RuntimeError(
                f"Facebook API request failed (HTTP {response.status_code}): "
                f"{message or 'invalid API response'}"
            )
        if not isinstance(payload, dict):
            raise RuntimeError("Facebook API returned a non-object response")
        return payload

    def upload_video(
        self,
        video_path: str | Path,
        *,
        page_id: str | None = None,
        description: str = "",
        title: str | None = None,
        scheduled_publish_time: int | None = None,
        extra_fields: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Upload local video or Google Drive URL to selected Page.

        Drive URLs are downloaded into a temporary file and removed only after
        Facebook confirms successful upload. Failed uploads preserve the file
        path for retry/debugging.
        """
        source_value = str(video_path)
        drive_file_id = _google_drive_file_id(source_value)
        temporary_path: Path | None = None
        if drive_file_id:
            from .google import download_drive_file

            suffix = Path(urlparse(source_value).path).suffix or ".mp4"
            temp_file = tempfile.NamedTemporaryFile(
                prefix="facebook-drive-video-", suffix=suffix, delete=False
            )
            temp_file.close()
            temporary_path = Path(temp_file.name)
            try:
                download_drive_file(drive_file_id, temporary_path)
            except Exception:
                temporary_path.unlink(missing_ok=True)
                raise
            path = temporary_path
        else:
            path = Path(video_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(path)
        target_page = str(page_id or self.page_id).strip()
        if not target_page:
            raise ValueError("page_id is required")
        data = {"description": description}
        if title is not None:
            data["title"] = title
        if scheduled_publish_time is not None:
            data.update(
                published="false",
                scheduled_publish_time=int(scheduled_publish_time),
            )
        data.update(dict(extra_fields or {}))
        try:
            with path.open("rb") as video_file:
                result = self._request(
                    "POST",
                    f"{target_page}/videos",
                    data=data,
                    files={"source": (path.name, video_file)},
                )
        except Exception as exc:
            if temporary_path:
                exc.add_note(f"Temporary Drive download preserved at: {temporary_path}")
            raise
        if temporary_path:
            temporary_path.unlink(missing_ok=True)
        return result

    def create_post(
        self,
        message: str,
        *,
        page_id: str | None = None,
        scheduled_publish_time: int | None = None,
        published: bool = True,
        image_url: str | None = None,
    ) -> dict[str, Any]:
        """Create a Page text/link post now or schedule it with Unix time."""
        if not message.strip():
            raise ValueError("message must be non-empty")
        target_page = str(page_id or self.page_id).strip()
        if not target_page:
            raise ValueError("page_id is required")
        data: dict[str, Any] = {"message": message}
        if image_url:
            data["link"] = image_url
        if scheduled_publish_time is not None:
            data.update(published="false", scheduled_publish_time=int(scheduled_publish_time))
        elif not published:
            data["published"] = "false"
        return self._request("POST", f"{target_page}/feed", data=data)

    def create_photo_post(
        self,
        image_path: str | Path,
        message: str,
        *,
        page_id: str | None = None,
        scheduled_publish_time: int | None = None,
    ) -> dict[str, Any]:
        """Publish or schedule a Page photo post."""
        path = Path(image_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(path)
        target_page = str(page_id or self.page_id).strip()
        if not target_page:
            raise ValueError("page_id is required")
        if not message.strip():
            raise ValueError("message must be non-empty")
        if scheduled_publish_time is None:
            with path.open("rb") as source:
                return self._request(
                    "POST", f"{target_page}/photos", data={"caption": message},
                    files={"source": (path.name, source)},
                )

        # Upload image unpublished, then create scheduled feed post referencing it.
        with path.open("rb") as source:
            uploaded = self._request(
                "POST", f"{target_page}/photos", data={"published": "false"},
                files={"source": (path.name, source)},
            )
        photo_id = uploaded.get("id")
        if not photo_id:
            raise RuntimeError("Facebook photo upload response omitted id")
        return self._request(
            "POST", f"{target_page}/feed",
            data={
                "message": message,
                "attached_media[0]": json.dumps({"media_fbid": photo_id}),
                "published": "false",
                "scheduled_publish_time": str(int(scheduled_publish_time)),
            },
        )

    def get_comments(
        self,
        object_id: str,
        *,
        fields: str | None = None,
        limit: int | None = None,
        page_all: bool = False,
    ) -> list[dict[str, Any]]:
        """Read comments on a Page post/video, optionally following pagination."""
        if not object_id:
            raise ValueError("object_id is required")
        settings = self.settings
        selected_fields = fields or settings.get(
            "comment_fields", "id,message,from,created_time"
        )
        params: dict[str, Any] = {"fields": selected_fields}
        selected_limit = limit if limit is not None else settings.get("comment_limit")
        if selected_limit is not None:
            params["limit"] = int(selected_limit)
        comments: list[dict[str, Any]] = []
        path = f"{object_id}/comments"
        while path:
            payload = self._request("GET", path, params=params)
            data = payload.get("data", [])
            if not isinstance(data, list):
                raise RuntimeError("Facebook comments response has invalid data")
            comments.extend(item for item in data if isinstance(item, dict))
            if not page_all:
                break
            path = str(payload.get("paging", {}).get("next", ""))
            if path.startswith(("http://", "https://")):
                parsed_next = urlparse(path)
                parsed_base = urlparse(self.base_url)
                if parsed_next.netloc != parsed_base.netloc:
                    raise RuntimeError("Facebook pagination URL uses unexpected host")
                path = parsed_next.path.lstrip("/")
                version_prefix = f"{self.version}/"
                if path.startswith(version_prefix):
                    path = path[len(version_prefix) :]
                params = {
                    key: values[-1]
                    for key, values in parse_qs(parsed_next.query).items()
                    if values
                }
            else:
                params = {}
        return comments

    def create_comment(self, object_id: str, message: str) -> dict[str, Any]:
        """Create a comment on a Page post or video."""
        if not object_id or not message.strip():
            raise ValueError("object_id and non-empty message are required")
        return self._request(
            "POST",
            f"{object_id}/comments",
            data={"message": message},
        )


def upload_video(
    video_path: str | Path,
    *,
    config: Mapping[str, Any] | str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return FacebookTool(config).upload_video(video_path, **kwargs)


def _google_drive_file_id(value: str) -> str | None:
    """Extract a Drive file ID from /file/d/ID or open?id=ID URLs."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return None
    host = (parsed.hostname or "").lower()
    if host not in {"drive.google.com", "www.drive.google.com", "docs.google.com"}:
        return None
    match = re.search(r"/file/d/([A-Za-z0-9_-]+)", parsed.path)
    file_id = match.group(1) if match else parse_qs(parsed.query).get("id", [None])[0]
    if not file_id or not re.fullmatch(r"[A-Za-z0-9_-]+", file_id):
        raise ValueError("Google Drive URL must contain a valid file ID")
    return file_id


def get_comments(
    object_id: str,
    *,
    config: Mapping[str, Any] | str | Path | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    return FacebookTool(config).get_comments(object_id, **kwargs)
