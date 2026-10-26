"""Google Sheets and Drive tools with caller-supplied IDs and paths."""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Mapping, Sequence

from .config import section_config
from .google_auth import build_google_service

SHEETS_READ_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SHEETS_WRITE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DRIVE_READ_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
DRIVE_WRITE_SCOPES = ["https://www.googleapis.com/auth/drive"]


def _google_service(
    config: Mapping[str, Any] | str | Path | None,
    *,
    api_name: str,
    api_version: str,
    scopes: list[str],
    service_key: str,
):
    settings = section_config(config, "google")
    configured_scopes = settings.get(f"{service_key}_scopes", settings.get("scopes"))
    selected_scopes = list(configured_scopes) if configured_scopes else scopes
    return build_google_service(
        api_name,
        api_version,
        config,
        scopes=selected_scopes,
        overrides={
            "api_name": settings.get(f"{service_key}_api_name", api_name),
            "api_version": settings.get(f"{service_key}_api_version", api_version),
        },
    )


def read_spreadsheet(
    spreadsheet_id: str,
    *,
    ranges: Sequence[str] | None = None,
    value_render_option: str | None = None,
    config: Mapping[str, Any] | str | Path | None = None,
    service: Any = None,
) -> dict[str, Any]:
    """Read spreadsheet metadata and requested ranges, or every tab."""
    if not spreadsheet_id:
        raise ValueError("spreadsheet_id is required")
    settings = section_config(config, "google")
    service = service or _google_service(
        config,
        api_name="sheets",
        api_version="v4",
        scopes=SHEETS_READ_SCOPES,
        service_key="sheets",
    )
    metadata = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields=str(
            settings.get(
                "sheets_metadata_fields",
                "properties(title),sheets(properties(title))",
            )
        ),
    ).execute()
    requested_ranges = list(ranges or [])
    if not requested_ranges:
        requested_ranges = [
            "'" + tab["properties"]["title"].replace("'", "''") + "'"
            for tab in metadata.get("sheets", [])
        ]
    values = []
    render_option = (
        str(value_render_option or "").strip()
        or str(settings.get("value_render_option") or "").strip()
        or "FORMATTED_VALUE"
    )
    for range_name in requested_ranges:
        response = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueRenderOption=render_option,
            )
            .execute()
        )
        values.append({"range": response.get("range", range_name), "values": response.get("values", [])})
    return {
        "spreadsheet_id": spreadsheet_id,
        "title": metadata.get("properties", {}).get("title", spreadsheet_id),
        "ranges": values,
    }


def write_spreadsheet(
    spreadsheet_id: str,
    range_name: str,
    values: Sequence[Sequence[Any]],
    *,
    value_input_option: str | None = None,
    config: Mapping[str, Any] | str | Path | None = None,
    service: Any = None,
) -> dict[str, Any]:
    """Write caller-provided cell values to a Google Sheets range."""
    if not spreadsheet_id or not range_name:
        raise ValueError("spreadsheet_id and range_name are required")
    settings = section_config(config, "google")
    input_option = (
        str(value_input_option or "").strip()
        or str(settings.get("value_input_option") or "").strip()
        or "USER_ENTERED"
    )
    service = service or _google_service(
        config,
        api_name="sheets",
        api_version="v4",
        scopes=SHEETS_WRITE_SCOPES,
        service_key="sheets",
    )
    return (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption=input_option,
            body={"values": [list(row) for row in values]},
        )
        .execute()
    )


def upload_drive_file(
    local_path: str | Path,
    folder_id: str,
    *,
    remote_name: str | None = None,
    mime_type: str | None = None,
    config: Mapping[str, Any] | str | Path | None = None,
    service: Any = None,
) -> dict[str, Any]:
    """Upload one local file to a caller-selected Drive folder."""
    path = Path(local_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(path)
    if not folder_id:
        raise ValueError("folder_id is required")
    settings = section_config(config, "google")
    service = service or _google_service(
        config,
        api_name="drive",
        api_version="v3",
        scopes=DRIVE_WRITE_SCOPES,
        service_key="drive",
    )
    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        raise RuntimeError("Google API client package is required for Drive uploads") from exc
    media = MediaFileUpload(
        str(path),
        mimetype=mime_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        resumable=bool(settings.get("resumable_upload", True)),
    )
    return (
        service.files()
        .create(
            body={"name": remote_name or path.name, "parents": [folder_id]},
            media_body=media,
            supportsAllDrives=bool(settings.get("supports_all_drives", True)),
            fields=str(settings.get("drive_file_fields", "id,name,mimeType,webViewLink")),
        )
        .execute()
    )


def download_drive_file(
    file_id: str,
    destination: str | Path,
    *,
    mime_type: str | None = None,
    config: Mapping[str, Any] | str | Path | None = None,
    service: Any = None,
) -> Path:
    """Download a Drive file or export a Google Docs Editor file."""
    if not file_id:
        raise ValueError("file_id is required")
    settings = section_config(config, "google")
    output = Path(destination).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    service = service or _google_service(
        config,
        api_name="drive",
        api_version="v3",
        scopes=DRIVE_READ_SCOPES,
        service_key="drive",
    )
    try:
        from googleapiclient.http import MediaIoBaseDownload
    except ImportError as exc:
        raise RuntimeError("Google API client package is required for Drive downloads") from exc
    import io

    supports_all_drives = bool(settings.get("supports_all_drives", True))
    file_info = (
        service.files()
        .get(
            fileId=file_id,
            supportsAllDrives=supports_all_drives,
            fields="mimeType",
        )
        .execute()
    )
    file_mime_type = str(file_info.get("mimeType", ""))
    if file_mime_type.startswith("application/vnd.google-apps."):
        default_exports = {
            "application/vnd.google-apps.document":
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.google-apps.spreadsheet":
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.google-apps.presentation":
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.google-apps.drawing": "application/pdf",
        }
        export_type = mime_type or default_exports.get(file_mime_type)
        if not export_type:
            raise ValueError(
                f"Google Drive file type {file_mime_type!r} needs an explicit export MIME type"
            )
        request = service.files().export(fileId=file_id, mimeType=export_type)
    else:
        request = service.files().get_media(
            fileId=file_id,
            supportsAllDrives=supports_all_drives,
        )
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    output.write_bytes(buffer.getvalue())
    return output
