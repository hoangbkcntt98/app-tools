from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from python.ai import call_api, text_to_audio, text_to_image, text_to_video
from python.database import DatabasePool
from python.facebook import FacebookTool
from python.google import read_spreadsheet, write_spreadsheet
from python.logger import get_logger, log
from python.config import DEFAULT_CONFIG_PATH


class TestDatabasePool(unittest.TestCase):
    def test_mysql_crud_quotes_identifiers_and_binds_values(self):
        cursor = MagicMock()
        cursor.description = None
        cursor.rowcount = 1
        cursor.lastrowid = 42
        connection = MagicMock()
        connection.cursor.return_value = cursor
        pool = MagicMock()
        pool.get_connection.return_value = connection
        database = DatabasePool(pool, "mysql")

        result = database.update("people", {"name": "O'Reilly"}, where={"id": 3})
        self.assertEqual(result, {"rowcount": 1, "lastrowid": 42})
        self.assertEqual(
            cursor.execute.call_args.args,
            ("UPDATE `people` SET `name` = %s WHERE `id` = %s", ("O'Reilly", 3)),
        )
        with self.assertRaisesRegex(ValueError, "where must not be empty"):
            database.delete("people", where={})
        with self.assertRaisesRegex(ValueError, "invalid SQL identifier"):
            database.select("people; DROP TABLE people")


class TestToolConfigAndLogger(unittest.TestCase):
    def test_default_config_is_repository_root_config(self):
        self.assertEqual(DEFAULT_CONFIG_PATH, Path(__file__).resolve().parents[1] / "config.json")

    def test_loads_json_and_resolves_log_file_relative_to_config(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config_path.write_text(
                json.dumps({"logger": {"file": "logs/tool.log", "console": False}}),
                encoding="utf-8",
            )
            logger = get_logger("python.test.config", config_path)
            logger.info("configured")
            self.assertIn("configured", (Path(directory) / "logs/tool.log").read_text())

    def test_log_accepts_custom_level_and_message(self):
        with tempfile.TemporaryDirectory() as directory:
            config = {
                "logger": {
                    "file": str(Path(directory) / "tool.log"),
                    "console": False,
                }
            }
            log("warning message", level="WARNING", config=config)
            self.assertIn("WARNING tools: warning message", (Path(directory) / "tool.log").read_text())


class TestGoogleTools(unittest.TestCase):
    def test_reads_requested_ranges_and_sheet_title(self):
        service = MagicMock()
        service.spreadsheets.return_value.get.return_value.execute.return_value = {
            "properties": {"title": "Test"},
            "sheets": [{"properties": {"title": "Tab"}}],
        }
        service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
            "range": "Tab!A1",
            "values": [["hello"]],
        }
        result = read_spreadsheet("sheet-id", ranges=["Tab!A1"], service=service)
        self.assertEqual(result["title"], "Test")
        self.assertEqual(result["ranges"], [{"range": "Tab!A1", "values": [["hello"]]}])

    def test_writes_provided_values(self):
        service = MagicMock()
        service.spreadsheets.return_value.values.return_value.update.return_value.execute.return_value = {
            "updatedCells": 2
        }
        result = write_spreadsheet(
            "sheet-id", "Tab!A1", [["A", "B"]], service=service
        )
        self.assertEqual(result["updatedCells"], 2)
        call = service.spreadsheets.return_value.values.return_value.update.call_args
        self.assertEqual(call.kwargs["body"]["values"], [["A", "B"]])


class TestFacebookTool(unittest.TestCase):
    def test_comment_read_uses_configured_page_token_and_graph_version(self):
        session = MagicMock()
        response = MagicMock()
        response.ok = True
        response.json.return_value = {"data": [{"id": "comment-1", "message": "Hi"}]}
        session.request.return_value = response
        tool = FacebookTool(
            settings={
                "graph_api_base": "https://graph.example",
                "graph_api_version": "v1",
                "page_id": "page",
                "access_token": "token",
            },
            session=session,
        )
        self.assertEqual(tool.get_comments("post"), [{"id": "comment-1", "message": "Hi"}])
        args, kwargs = session.request.call_args
        self.assertEqual(args[:2], ("GET", "https://graph.example/v1/post/comments"))
        self.assertEqual(kwargs["params"]["access_token"], "token")

    def test_create_post_schedules_using_unix_timestamp(self):
        session = MagicMock()
        response = MagicMock(ok=True)
        response.json.return_value = {"id": "post-1"}
        session.request.return_value = response
        tool = FacebookTool(settings={
            "graph_api_base": "https://graph.example", "graph_api_version": "v1",
            "page_id": "page", "access_token": "token",
        }, session=session)
        result = tool.create_post("hello", scheduled_publish_time=1_800_000_000)
        self.assertEqual(result, {"id": "post-1"})
        args, kwargs = session.request.call_args
        self.assertEqual(args[:2], ("POST", "https://graph.example/v1/page/feed"))
        self.assertEqual(kwargs["data"], {
            "message": "hello", "published": "false", "scheduled_publish_time": 1_800_000_000,
        })

    def test_create_photo_post_schedules_photo(self):
        session = MagicMock()
        photo_response = MagicMock(ok=True)
        photo_response.json.return_value = {"id": "photo-1"}
        post_response = MagicMock(ok=True)
        post_response.json.return_value = {"id": "post-1"}
        session.request.side_effect = [photo_response, post_response]
        tool = FacebookTool(settings={
            "graph_api_base": "https://graph.example", "graph_api_version": "v1",
            "page_id": "page", "access_token": "token",
        }, session=session)
        with tempfile.NamedTemporaryFile() as image:
            image.write(b"image")
            image.flush()
            tool.create_photo_post(image.name, "caption", scheduled_publish_time=1_800_000_000)
        self.assertEqual(session.request.call_count, 2)
        photo_args, photo_kwargs = session.request.call_args_list[0]
        self.assertEqual(photo_args[:2], ("POST", "https://graph.example/v1/page/photos"))
        self.assertEqual(photo_kwargs["data"], {"published": "false"})
        post_args, post_kwargs = session.request.call_args_list[1]
        self.assertEqual(post_args[:2], ("POST", "https://graph.example/v1/page/feed"))
        self.assertEqual(post_kwargs["data"], {
            "message": "caption", "attached_media[0]": '{"media_fbid": "photo-1"}',
            "published": "false", "scheduled_publish_time": "1800000000",
        })

    def test_upload_video_schedules_using_unix_timestamp(self):
        session = MagicMock()
        response = MagicMock(ok=True)
        response.json.return_value = {"id": "video-1"}
        session.request.return_value = response
        tool = FacebookTool(settings={
            "graph_api_base": "https://graph.example", "graph_api_version": "v1",
            "page_id": "page", "access_token": "token",
        }, session=session)
        with tempfile.NamedTemporaryFile() as video:
            video.write(b"video")
            video.flush()
            result = tool.upload_video(
                video.name, description="caption", scheduled_publish_time=1_800_000_000
            )
        self.assertEqual(result, {"id": "video-1"})
        args, kwargs = session.request.call_args
        self.assertEqual(args[:2], ("POST", "https://graph.example/v1/page/videos"))
        self.assertEqual(kwargs["data"], {
            "description": "caption",
            "published": "false",
            "scheduled_publish_time": 1_800_000_000,
        })

    @patch("python.google.download_drive_file")
    def test_upload_video_from_drive_url_downloads_then_removes_temp_file(self, download):
        session = MagicMock()
        response = MagicMock(ok=True)
        response.json.return_value = {"id": "video-1"}
        session.request.return_value = response

        def write_download(_file_id, destination, **_kwargs):
            Path(destination).write_bytes(b"video-bytes")
            return Path(destination)

        download.side_effect = write_download
        tool = FacebookTool(
            settings={
                "graph_api_base": "https://graph.example",
                "graph_api_version": "v1",
                "page_id": "page",
                "access_token": "token",
            },
            session=session,
        )
        result = tool.upload_video(
            "https://drive.google.com/file/d/drive-file_1/view?usp=drivesdk",
            description="Caption",
        )
        self.assertEqual(result, {"id": "video-1"})
        download.assert_called_once()
        self.assertEqual(download.call_args.args[0], "drive-file_1")
        uploaded = session.request.call_args.kwargs["files"]["source"]
        self.assertEqual(uploaded[0], Path(download.call_args.args[1]).name)
        self.assertEqual(uploaded[1].closed, True)
        self.assertFalse(Path(download.call_args.args[1]).exists())

    @patch("python.google.download_drive_file")
    def test_upload_video_from_drive_url_preserves_temp_file_on_facebook_failure(self, download):
        session = MagicMock()
        response = MagicMock(ok=False, status_code=400)
        response.json.return_value = {"error": {"message": "upload failed"}}
        session.request.return_value = response

        def write_download(_file_id, destination, **_kwargs):
            Path(destination).write_bytes(b"video-bytes")
            return Path(destination)

        download.side_effect = write_download
        tool = FacebookTool(
            settings={
                "graph_api_base": "https://graph.example",
                "graph_api_version": "v1",
                "page_id": "page",
                "access_token": "token",
            },
            session=session,
        )
        with self.assertRaisesRegex(RuntimeError, "upload failed") as raised:
            tool.upload_video("https://drive.google.com/open?id=drive-file_2")
        preserved_path = Path(raised.exception.__notes__[0].split(": ", 1)[1])
        self.assertTrue(preserved_path.is_file())
        preserved_path.unlink()

    def test_comment_read_follows_pagination(self):
        session = MagicMock()
        first = MagicMock(ok=True)
        first.json.return_value = {
            "data": [{"id": "1"}],
            "paging": {"next": "https://graph.example/v1/post/comments?after=x"},
        }
        second = MagicMock(ok=True)
        second.json.return_value = {"data": [{"id": "2"}]}
        session.request.side_effect = [first, second]
        tool = FacebookTool(
            settings={
                "graph_api_base": "https://graph.example",
                "graph_api_version": "v1",
                "access_token": "token",
            },
            session=session,
        )
        self.assertEqual(
            [item["id"] for item in tool.get_comments("post", page_all=True)],
            ["1", "2"],
        )
        self.assertEqual(
            session.request.call_args_list[1].args[1],
            "https://graph.example/v1/post/comments",
        )
        self.assertEqual(session.request.call_args_list[1].kwargs["params"]["after"], "x")


class TestAITools(unittest.TestCase):
    @patch("python.ai.requests.request")
    def test_call_api_returns_json_and_uses_config_values(self, request):
        response = MagicMock()
        response.json.return_value = {"answer": 42}
        request.return_value = response
        result = call_api(
            "/answer",
            config={
                "ai": {
                    "base_url": "https://api.example/v1",
                    "api_key": "secret",
                }
            },
        )
        self.assertEqual(result, {"answer": 42})
        self.assertEqual(request.call_args.kwargs["url"], "https://api.example/v1/answer")
        self.assertEqual(
            request.call_args.kwargs["headers"]["Authorization"], "Bearer secret"
        )

    @patch("python.ai.requests.request")
    def test_call_api_uses_chat_specific_base_url(self, request):
        response = MagicMock()
        response.json.return_value = {"choices": []}
        request.return_value = response
        call_api(
            "/chat/completions",
            config={
                "ai": {
                    "chat": {"base_url": "https://chat.example/v2"},
                    "image": {"base_url": "https://image.example/v1"},
                }
            },
        )
        self.assertEqual(
            request.call_args.kwargs["url"],
            "https://chat.example/v2/chat/completions",
        )

    @patch("python.ai.requests.request")
    def test_call_api_uses_service_specific_auth_and_timeout(self, request):
        response = MagicMock()
        response.json.return_value = {"data": []}
        request.return_value = response
        call_api(
            "/generate",
            service="image",
            config={
                "ai": {
                    "api_key_env": "SHARED_KEY",
                    "timeout_seconds": 300,
                    "image": {
                        "base_url": "https://image.example/v1",
                        "api_key": "image-secret",
                        "api_key_header": "X-Image-Key",
                        "auth_scheme": "",
                        "timeout_seconds": 45,
                    },
                }
            },
        )
        self.assertEqual(
            request.call_args.kwargs["headers"]["X-Image-Key"], "image-secret"
        )
        self.assertEqual(request.call_args.kwargs["timeout"], 45)
        self.assertNotIn("Authorization", request.call_args.kwargs["headers"])

    @patch("python.ai.call_api", return_value={"data": [{"b64_json": "aW1hZ2U="}]})
    def test_text_to_image_uses_configured_model_and_payload(self, call):
        result = text_to_image(
            "draw",
            config={
                "ai": {
                    "base_url": "https://api.example/v1",
                    "image": {
                        "base_url": "https://image.example/v3",
                        "endpoint": "/image",
                        "model": "model-a",
                    },
                }
            },
        )
        self.assertEqual(result, b"image")
        payload = call.call_args.kwargs["payload"]
        self.assertEqual(payload, {"model": "model-a", "prompt": "draw"})
        self.assertEqual(call.call_args.kwargs["service"], "image")

    @patch("python.ai.call_api", return_value=b"audio")
    def test_text_to_audio_returns_provider_bytes(self, call):
        result = text_to_audio(
            "speak",
            config={
                "ai": {
                    "audio": {
                        "endpoint": "/audio",
                        "model": "voice-model",
                        "response_type": "bytes",
                    }
                }
            },
        )
        self.assertEqual(result, b"audio")

    @patch("python.ai.time.sleep")
    @patch("python.ai.call_api")
    def test_text_to_video_uses_configured_status_fields(self, call, _sleep):
        call.side_effect = [
            {"task": "job-1"},
            {"state": "running"},
            {"state": "done"},
        ]
        result = text_to_video(
            "animate",
            config={
                "ai": {
                    "video": {
                        "endpoint": "/create",
                        "status_endpoint": "/jobs/{task_id}",
                        "task_id_field": "task",
                        "status_field": "state",
                        "success_values": ["done"],
                        "poll_interval_seconds": 0,
                    }
                }
            },
        )
        self.assertEqual(result, {"state": "done"})
        self.assertEqual(call.call_args_list[1].args[0], "/jobs/job-1")


    @patch("python.ai.time.sleep")
    @patch("python.ai.call_api")
    def test_text_to_video_resolves_relative_output_url(self, call, _sleep):
        call.side_effect = [
            {"id": "job-1"},
            {"status": "completed", "video": "/v1/media/job-1.mp4"},
            b"video",
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "video.mp4"
            result = text_to_video(
                "animate",
                output=output,
                config={
                    "ai": {
                        "video": {
                            "base_url": "http://example.test/v1",
                            "endpoint": "/create",
                            "status_endpoint": "/jobs/{task_id}",
                            "poll_interval_seconds": 0,
                        }
                    }
                },
            )
            self.assertEqual(result["status"], "completed")
            self.assertEqual(output.read_bytes(), b"video")
            self.assertEqual(
                call.call_args_list[2].args[0],
                "http://example.test/v1/media/job-1.mp4",
            )
            self.assertEqual(call.call_args_list[2].kwargs["response_type"], "bytes")

if __name__ == "__main__":
    unittest.main()
