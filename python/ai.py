"""Configurable HTTP-based AI API tools for image, video, audio, and JSON calls."""
from __future__ import annotations

import base64
import binascii
import os
import time
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin, urlsplit

import requests

from .config import section_config


def _endpoint(
    settings: Mapping[str, Any],
    endpoint: str | None,
    base_url: str | None = None,
) -> str:
    selected = str(endpoint or "").strip()
    configured_base = str(base_url or settings.get("base_url", "")).strip()
    if not selected:
        raise ValueError("API endpoint is required")
    if selected.startswith(("http://", "https://")):
        return selected
    if not configured_base:
        raise ValueError("Configure service base_url for relative API endpoints")
    return urljoin(configured_base.rstrip("/") + "/", selected.lstrip("/"))


def _headers(
    settings: Mapping[str, Any],
    headers: Mapping[str, str] | None,
) -> dict[str, str]:
    result = {str(key): str(value) for key, value in (headers or {}).items()}
    api_key = str(settings.get("api_key", "")).strip()
    env_name = str(settings.get("api_key_env", "")).strip()
    if not api_key and env_name:
        api_key = os.environ.get(env_name, "").strip()
    key_header = str(settings.get("api_key_header", "Authorization"))
    if api_key and not any(key.lower() == key_header.lower() for key in result):
        scheme = str(settings.get("auth_scheme", "Bearer")).strip()
        result[key_header] = f"{scheme} {api_key}".strip()
    return result


def call_api(
    endpoint: str,
    *,
    service: str = "chat",
    base_url: str | None = None,
    method: str = "POST",
    payload: Any = None,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, Any] | None = None,
    response_type: str = "json",
    config: Mapping[str, Any] | str | Path | None = None,
    session: Any = None,
) -> Any:
    """Call configured AI/provider endpoint; return JSON, bytes, or text."""
    result_type = response_type.lower()
    if result_type not in {"json", "bytes", "text"}:
        raise ValueError("response_type must be 'json', 'bytes', or 'text'")
    root_settings = section_config(config, "ai")
    selected_settings = root_settings.get(service, {})
    if not isinstance(selected_settings, Mapping):
        raise ValueError(f"ai.{service} config must be an object")
    settings = {
        key: value
        for key, value in root_settings.items()
        if not isinstance(value, Mapping)
    }
    settings.update(selected_settings)
    configured_base = base_url or settings.get("base_url")
    request_headers = _headers(settings, headers)
    request_headers.setdefault("Accept", str(settings.get("accept", "application/json")))
    if payload is not None and isinstance(payload, (dict, list)):
        request_headers.setdefault("Content-Type", "application/json")
    client = session or requests
    response = client.request(
        method=str(method).upper(),
        url=_endpoint(
            settings, endpoint, str(configured_base) if configured_base else None
        ),
        json=payload if isinstance(payload, (dict, list)) else None,
        data=payload if payload is not None and not isinstance(payload, (dict, list)) else None,
        headers=request_headers,
        params=dict(params or {}),
        timeout=float(settings.get("timeout_seconds", 120)),
    )
    response.raise_for_status()
    if result_type == "json":
        return response.json()
    if result_type == "bytes":
        return response.content
    return response.text


def _image_bytes(
    response: Any,
    timeout: float,
    *,
    data_field: str,
    base64_field: str,
    url_field: str,
) -> bytes:
    data = response.get(data_field) if isinstance(response, dict) else None
    item = data[0] if isinstance(data, list) and data else response
    if isinstance(item, dict):
        encoded = item.get(base64_field)
        if encoded:
            encoded = str(encoded)
            if encoded.startswith("data:") and "," in encoded:
                encoded = encoded.split(",", 1)[1]
            return base64.b64decode(encoded, validate=True)
        image_url = item.get(url_field)
        if image_url:
            download = requests.get(str(image_url), timeout=timeout)
            download.raise_for_status()
            return download.content
    raise RuntimeError("Image API response must contain base64 data or an image URL")


def text_to_image(
    prompt: str,
    *,
    endpoint: str | None = None,
    model: str | None = None,
    options: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | str | Path | None = None,
) -> bytes:
    """Generate image bytes from text using configured image API."""
    if not prompt.strip():
        raise ValueError("prompt is required")
    settings = section_config(config, "ai")
    image_settings = settings.get("image", {})
    if not isinstance(image_settings, Mapping):
        raise ValueError("ai.image config must be an object")
    api_endpoint = endpoint or image_settings.get("endpoint")
    selected_model = model or image_settings.get("model")
    if not api_endpoint or not selected_model:
        raise ValueError("Provide image endpoint and model in arguments or ai.image config")
    payload = dict(image_settings.get("request_options", {}))
    payload.update(dict(options or {}))
    payload[str(image_settings.get("model_field", "model"))] = selected_model
    payload[str(image_settings.get("prompt_field", "prompt"))] = prompt
    response = call_api(
        str(api_endpoint),
        service="image",
        method=str(image_settings.get("method", "POST")),
        payload=payload,
        config=config,
    )
    return _image_bytes(
        response,
        float(settings.get("timeout_seconds", 120)),
        data_field=str(image_settings.get("data_field", "data")),
        base64_field=str(image_settings.get("base64_response_field", "b64_json")),
        url_field=str(image_settings.get("url_response_field", "url")),
    )


def text_to_audio(
    text: str,
    *,
    endpoint: str | None = None,
    model: str | None = None,
    options: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | str | Path | None = None,
) -> bytes:
    """Generate audio bytes from text using configured speech API."""
    if not text.strip():
        raise ValueError("text is required")
    settings = section_config(config, "ai")
    audio_settings = settings.get("audio", {})
    if not isinstance(audio_settings, Mapping):
        raise ValueError("ai.audio config must be an object")
    api_endpoint = endpoint or audio_settings.get("endpoint")
    selected_model = model or audio_settings.get("model")
    if not api_endpoint or not selected_model:
        raise ValueError("Provide audio endpoint and model in arguments or ai.audio config")
    payload = dict(audio_settings.get("request_options", {}))
    payload.update(dict(options or {}))
    payload[str(audio_settings.get("model_field", "model"))] = selected_model
    payload[str(audio_settings.get("text_field", "input"))] = text
    audio = call_api(
        str(api_endpoint),
        service="audio",
        method=str(audio_settings.get("method", "POST")),
        payload=payload,
        response_type=str(audio_settings.get("response_type", "bytes")),
        config=config,
    )
    if isinstance(audio, dict):
        encoded = audio.get(str(audio_settings.get("base64_response_field", "audio")))
        if encoded is None:
            encoded = audio.get(str(audio_settings.get("alternate_base64_response_field", "b64_json")))
        if not encoded:
            raise RuntimeError("Audio API response did not contain audio bytes")
        encoded = str(encoded)
        if encoded.startswith("data:") and "," in encoded:
            encoded = encoded.split(",", 1)[1]
        audio = base64.b64decode(encoded, validate=True)
    if not audio:
        raise RuntimeError("Audio API returned empty response")
    return bytes(audio)


def text_to_video(
    prompt: str,
    *,
    endpoint: str | None = None,
    model: str | None = None,
    options: Mapping[str, Any] | None = None,
    output: str | Path | None = None,
    config: Mapping[str, Any] | str | Path | None = None,
) -> dict[str, Any]:
    """Create and poll a video task using configurable provider response fields."""
    if not prompt.strip():
        raise ValueError("prompt is required")
    settings = section_config(config, "ai")
    video_settings = settings.get("video", {})
    if not isinstance(video_settings, Mapping):
        raise ValueError("ai.video config must be an object")
    create_endpoint = endpoint or video_settings.get("endpoint")
    selected_model = model or video_settings.get("model")
    status_endpoint = video_settings.get("status_endpoint")
    if not create_endpoint or not status_endpoint:
        raise ValueError("Configure ai.video.endpoint and ai.video.status_endpoint")
    payload = dict(video_settings.get("request_options", {}))
    payload.update(dict(options or {}))
    payload[str(video_settings.get("prompt_field", "prompt"))] = prompt
    if selected_model:
        payload[str(video_settings.get("model_field", "model"))] = selected_model
    result = call_api(
        str(create_endpoint),
        service="video",
        method=str(video_settings.get("method", "POST")),
        payload=payload,
        config=config,
    )
    if not isinstance(result, dict):
        raise RuntimeError("Video create API must return a JSON object")
    task_id_field = str(video_settings.get("task_id_field", "id"))
    task_id = result.get(task_id_field)
    if not task_id:
        if output is not None:
            _save_video(result, Path(output), video_settings, config)
        return result

    status_field = str(video_settings.get("status_field", "status"))
    success_values = set(video_settings.get("success_values", ["succeeded", "completed"]))
    failure_values = set(video_settings.get("failure_values", ["failed", "error"]))
    interval = float(video_settings.get("poll_interval_seconds", 5))
    timeout = float(video_settings.get("poll_timeout_seconds", 900))
    deadline = time.monotonic() + timeout
    while True:
        url = str(status_endpoint).format(task_id=task_id)
        result = call_api(
            url,
            service="video",
            method=str(video_settings.get("status_method", "GET")),
            config=config,
        )
        if not isinstance(result, dict):
            raise RuntimeError("Video status API must return a JSON object")
        status = result.get(status_field)
        if status in success_values:
            if output is not None:
                _save_video(result, Path(output), video_settings, config)
            return result
        if status in failure_values:
            raise RuntimeError(f"Video generation failed: {result}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Video task {task_id} exceeded polling timeout")
        time.sleep(interval)

def _save_video(
    response: Mapping[str, Any],
    output: Path,
    settings: Mapping[str, Any],
    config: Mapping[str, Any] | str | Path | None,
) -> None:
    """Save video bytes or a downloadable URL from a provider response."""
    data_field = str(settings.get("data_field", "data"))
    item: Any = response.get(data_field, response)
    if isinstance(item, list) and item:
        item = item[0]
    if not isinstance(item, Mapping):
        item = response

    encoded = item.get(str(settings.get("base64_response_field", "video")))
    video_bytes: bytes | None = None
    video_url = None
    if encoded:
        encoded = str(encoded)
        if encoded.startswith("data:") and "," in encoded:
            encoded = encoded.split(",", 1)[1]
        try:
            video_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            if _looks_like_video_url(encoded):
                video_url = encoded
            else:
                raise RuntimeError(
                    "Video API base64 field is not valid base64; configure "
                    "ai.video.url_response_field if this field contains a URL"
                ) from None
    if video_bytes is None:
        video_url = video_url or item.get(str(settings.get("url_response_field", "url")))
        if not video_url:
            raise RuntimeError(
                "Video API response must contain base64 data or a video URL to save with --output"
            )
        base_url = str(settings.get("base_url", "")).strip()
        download_url = str(video_url)
        if not download_url.startswith(("http://", "https://")):
            if not base_url:
                raise RuntimeError(
                    "Configure ai.video.base_url to download a relative video URL"
                )
            download_url = urljoin(base_url.rstrip("/") + "/", download_url)
        video_bytes = call_api(
            download_url,
            service="video",
            method="GET",
            response_type="bytes",
            config=config,
        )
    if not video_bytes:
        raise RuntimeError("Video API returned empty video data")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(video_bytes)

def _looks_like_video_url(value: str) -> bool:
    """Recognize URL-shaped values returned in a provider's video field."""
    parsed = urlsplit(value)
    return (
        parsed.scheme in {"http", "https"}
        or value.startswith(("/", "./", "../"))
        or ("/" in value and not any(character.isspace() for character in value))
        or Path(parsed.path).suffix.lower() in {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
    )
