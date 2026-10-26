"""Command-line entry point for Python integrations."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PYTHON_PACKAGE_DIR = str(Path(__file__).resolve().parent)
if PYTHON_PACKAGE_DIR in sys.path:
    # Prevent python/google.py from shadowing Google's installed namespace.
    sys.path.remove(PYTHON_PACKAGE_DIR)
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def _json_value(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"invalid JSON: {exc}") from exc


def _add_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        help="Path to config JSON; defaults to COMMON_TOOLS_CONFIG or config.json",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run common tools from command line",
        epilog="Run from repository root. Use --config before subcommand.",
    )
    _add_config(parser)
    commands = parser.add_subparsers(dest="command", required=True)

    command = commands.add_parser("log", help="Write one log message")
    command.add_argument("--message", required=True)
    command.add_argument("--name", default="tools.cli")
    command.add_argument("--level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="INFO")

    command = commands.add_parser("ai-call", help="Call configured AI HTTP API")
    command.add_argument("--service", default="chat", choices=["chat", "image", "video", "audio"])
    command.add_argument("--endpoint", required=True)
    command.add_argument("--method", default="POST")
    command.add_argument("--payload", type=_json_value)
    command.add_argument("--headers", type=_json_value, default={})
    command.add_argument("--params", type=_json_value, default={})
    command.add_argument("--response-type", choices=["json", "bytes", "text"], default="json")
    command.add_argument("--output", help="Write bytes response to this file")

    for service in ("image", "audio", "video"):
        command = commands.add_parser(f"ai-{service}", help=f"Generate {service}")
        command.add_argument("--prompt" if service != "audio" else "--text", required=True)
        command.add_argument("--model")
        command.add_argument("--options", type=_json_value, default={})
        command.add_argument("--output", help="Save generated media to this path")

    command = commands.add_parser("facebook-comments", help="Read Facebook comments")
    command.add_argument("--object-id", required=True)
    command.add_argument("--fields")
    command.add_argument("--limit", type=int)
    command.add_argument("--all-pages", action="store_true")

    command = commands.add_parser("facebook-comment", help="Publish Facebook comment")
    command.add_argument("--object-id", required=True)
    command.add_argument("--message", required=True)

    command = commands.add_parser("facebook-upload-video", help="Upload video to Facebook Page")
    command.add_argument("--video", required=True)
    command.add_argument("--page-id")
    command.add_argument("--description", default="")
    command.add_argument("--title")
    command.add_argument("--publish-at", help="Future ISO-8601 time with timezone")

    command = commands.add_parser("facebook-post", help="Publish or schedule Facebook Page post")
    command.add_argument("--message", required=True)
    command.add_argument("--page-id")
    command.add_argument("--image")
    command.add_argument("--publish-at", help="Future ISO-8601 time with timezone")

    command = commands.add_parser("sheets-read", help="Read spreadsheet ranges")
    command.add_argument("--spreadsheet-id", required=True)
    command.add_argument("--range", dest="ranges", action="append", help="Repeat for multiple ranges")

    command = commands.add_parser("sheets-write", help="Write JSON rows to spreadsheet")
    command.add_argument("--spreadsheet-id", required=True)
    command.add_argument("--range", required=True)
    command.add_argument("--values", required=True, type=_json_value, help='JSON 2D array, e.g. \'[["A","B"]]\'')
    command.add_argument("--value-input-option")

    command = commands.add_parser("drive-upload", help="Upload local file to Drive")
    command.add_argument("--file", required=True)
    command.add_argument("--folder-id", required=True)
    command.add_argument("--remote-name")
    command.add_argument("--mime-type")

    command = commands.add_parser("drive-download", help="Download Drive file")
    command.add_argument("--file-id", required=True)
    command.add_argument("--output", required=True)
    command.add_argument(
        "--mime-type",
        help="Export MIME type for Google Docs, Sheets, or Slides files",
    )

    command = commands.add_parser("anki-sync", help="Sync Anki collection with AnkiWeb")
    command.add_argument("--api-url")
    command.add_argument("--timeout", type=int, default=300)

    command = commands.add_parser("anki-notes-list", help="List Anki notes")
    command.add_argument("--query", default="", help="Anki search query; empty lists all notes")
    command.add_argument("--limit", type=int, help="Maximum note count")
    command.add_argument("--api-url")

    command = commands.add_parser("anki-note-add", help="Create Anki note through AnkiConnect")
    command.add_argument("--deck", required=True)
    command.add_argument("--note-type", required=True)
    command.add_argument("--fields", required=True, type=_json_value, help="JSON object mapping field names to values")
    command.add_argument("--tags", type=_json_value, default=[])
    command.add_argument("--api-url")

    command = commands.add_parser("anki-note-update", help="Update Anki note fields")
    command.add_argument("--note-id", required=True, type=int)
    command.add_argument("--fields", required=True, type=_json_value, help="JSON object mapping field names to values")
    command.add_argument("--api-url")

    command = commands.add_parser("anki-note-delete", help="Delete Anki notes permanently")
    command.add_argument("--note-id", required=True, dest="note_ids", action="append", type=int, help="Repeat for multiple note IDs")
    command.add_argument("--api-url")

    command = commands.add_parser("video-concat", help="Join video clips with ffmpeg")
    command.add_argument("--input", dest="videos", action="append", required=True, help="Input video; repeat in desired order")
    command.add_argument("--output", required=True)
    command.add_argument("--reencode", action="store_true", help="Re-encode clips with differing formats")
    command.add_argument("--ffmpeg-bin")

    command = commands.add_parser("html-to-video", help="Capture HTML page as an MP4 video")
    command.add_argument("--html", required=True)
    command.add_argument("--output", required=True)
    command.add_argument("--duration", type=float, default=5)
    command.add_argument("--fps", type=int, default=30)
    command.add_argument("--width", type=int, default=1080)
    command.add_argument("--height", type=int, default=1920)
    command.add_argument("--start", type=float, default=0, help="Wait this many seconds after page load before capture")
    command.add_argument("--ffmpeg-bin")
    command.add_argument("--chromium-bin")

    command = commands.add_parser("youtube-upload", help="Upload video to YouTube")
    command.add_argument("--video", required=True)
    command.add_argument("--title", required=True)
    command.add_argument("--description", default="")
    command.add_argument("--tags", type=_json_value)
    command.add_argument("--category-id")
    command.add_argument("--privacy-status")
    command.add_argument("--publish-at")
    return parser


def _print(value: Any) -> None:
    if isinstance(value, bytes):
        print(f"{len(value)} bytes")
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    args = _build_parser().parse_args()
    config = args.config

    if args.command == "log":
        from python.logger import log

        log(args.message, name=args.name, level=args.level, config=config)
        return

    if args.command == "ai-call":
        from python.ai import call_api

        result = call_api(
            args.endpoint,
            service=args.service,
            method=args.method,
            payload=args.payload,
            headers=args.headers,
            params=args.params,
            response_type=args.response_type,
            config=config,
        )
        if isinstance(result, bytes) and args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(result)
            print(output)
        else:
            _print(result)
        return

    if args.command.startswith("ai-"):
        from python.ai import text_to_audio, text_to_image, text_to_video

        if args.command == "ai-image":
            result = text_to_image(args.prompt, model=args.model, options=args.options, config=config)
        elif args.command == "ai-audio":
            result = text_to_audio(args.text, model=args.model, options=args.options, config=config)
        else:
            result = text_to_video(
                args.prompt,
                model=args.model,
                options=args.options,
                output=args.output,
                config=config,
            )
        if isinstance(result, bytes):
            if not args.output:
                raise SystemExit("--output is required for AI image/audio bytes")
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(result)
            print(output)
        elif args.command == "ai-video" and args.output:
            print(Path(args.output))
        else:
            _print(result)
        return

    if args.command.startswith("facebook-"):
        from python.facebook import FacebookTool

        tool = FacebookTool(config)
        if args.command == "facebook-comments":
            result = tool.get_comments(
                args.object_id, fields=args.fields, limit=args.limit, page_all=args.all_pages
            )
        elif args.command == "facebook-post":
            from datetime import datetime, timezone
            scheduled = None
            if args.publish_at:
                try:
                    value = datetime.fromisoformat(args.publish_at.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise SystemExit(f"invalid --publish-at: {exc}") from exc
                if value.tzinfo is None:
                    raise SystemExit("--publish-at requires ISO-8601 timezone")
                scheduled = int(value.astimezone(timezone.utc).timestamp())
                if scheduled <= int(datetime.now(timezone.utc).timestamp()):
                    raise SystemExit("--publish-at must be a future time")
            if args.image:
                result = tool.create_photo_post(args.image, args.message, page_id=args.page_id, scheduled_publish_time=scheduled)
            else:
                result = tool.create_post(args.message, page_id=args.page_id, scheduled_publish_time=scheduled)
        elif args.command == "facebook-comment":
            result = tool.create_comment(args.object_id, args.message)
        else:
            from datetime import datetime, timezone
            scheduled = None
            if args.publish_at:
                try:
                    value = datetime.fromisoformat(args.publish_at.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise SystemExit(f"invalid --publish-at: {exc}") from exc
                if value.tzinfo is None:
                    raise SystemExit("--publish-at requires ISO-8601 timezone")
                scheduled = int(value.astimezone(timezone.utc).timestamp())
                if scheduled <= int(datetime.now(timezone.utc).timestamp()):
                    raise SystemExit("--publish-at must be a future time")
            result = tool.upload_video(
                args.video, page_id=args.page_id, description=args.description, title=args.title,
                scheduled_publish_time=scheduled,
            )
        _print(result)
        return

    if args.command.startswith("sheets-") or args.command.startswith("drive-"):
        from python.google import (
            download_drive_file,
            read_spreadsheet,
            upload_drive_file,
            write_spreadsheet,
        )

        if args.command == "sheets-read":
            result = read_spreadsheet(args.spreadsheet_id, ranges=args.ranges, config=config)
        elif args.command == "sheets-write":
            if not isinstance(args.values, list) or any(not isinstance(row, list) for row in args.values):
                raise SystemExit("--values must be a JSON 2D array")
            result = write_spreadsheet(
                args.spreadsheet_id,
                args.range,
                args.values,
                value_input_option=args.value_input_option,
                config=config,
            )
        elif args.command == "drive-upload":
            result = upload_drive_file(
                args.file,
                args.folder_id,
                remote_name=args.remote_name,
                mime_type=args.mime_type,
                config=config,
            )
        else:
            result = download_drive_file(
                args.file_id,
                args.output,
                mime_type=args.mime_type,
                config=config,
            )
        _print(result)
        return

    if args.command.startswith("anki-note-"):
        from anki_image_generator.services.anki_connector import AnkiConnector

        anki_settings = {}
        if config:
            from python.config import section_config
            anki_settings = section_config(config, "anki")
        connector = AnkiConnector(api_url=args.api_url or anki_settings.get("api_url", "http://127.0.0.1:8765"))
        if args.command == "anki-sync":
            result = connector.sync(timeout=args.timeout)
        elif args.command == "anki-notes-list":
            result = connector.list_notes(query=args.query, limit=args.limit)
        elif args.command == "anki-note-add":
            if not isinstance(args.fields, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in args.fields.items()):
                raise SystemExit("--fields must be a JSON object of string values")
            if not isinstance(args.tags, list) or not all(isinstance(tag, str) for tag in args.tags):
                raise SystemExit("--tags must be a JSON array of strings")
            result = connector.add_note(args.deck, args.note_type, args.fields, args.tags)
        elif args.command == "anki-note-update":
            if not isinstance(args.fields, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in args.fields.items()):
                raise SystemExit("--fields must be a JSON object of string values")
            result = connector.update_note_fields(args.note_id, args.fields)
        else:
            result = connector.delete_notes(args.note_ids)
        _print(result)
        return

    if args.command == "video-concat":
        from python.video import concatenate_videos

        print(concatenate_videos(args.videos, args.output, ffmpeg_bin=args.ffmpeg_bin, reencode=args.reencode))
        return

    if args.command == "html-to-video":
        from python.video import html_to_video

        print(html_to_video(
            args.html, args.output, duration=args.duration, fps=args.fps,
            width=args.width, height=args.height, start=args.start,
            ffmpeg_bin=args.ffmpeg_bin, chromium_bin=args.chromium_bin,
        ))
        return

    if args.command == "youtube-upload":
        from python.youtube import upload_video

        result = upload_video(
            args.video,
            title=args.title,
            description=args.description,
            tags=args.tags,
            category_id=args.category_id,
            privacy_status=args.privacy_status,
            publish_at=args.publish_at,
            config=config,
        )
        _print(result)


if __name__ == "__main__":
    main()
