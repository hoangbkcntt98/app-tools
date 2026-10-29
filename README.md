# Common tools

Reusable, config-driven tools for Facebook, Google, YouTube, AI HTTP APIs, and
logging.

## Setup

Implementations live in `python/` and `ts/`. Both use one `config.json` in
`jobs/app-tools/`. Copy `config.example.json` to ignored `config.json`; set
provider URLs, IDs, scopes, models, paths, and credentials. Set secrets as
direct config values such as `ai.chat.api_key` and
`facebook.access_token`. These config files are ignored by Git. Explicit
function arguments override matching config values.

Set root `response_as_json` to `true` to wrap Python CLI results as
`{"status":"ok","response":...}`. Failures return
`{"status":"error","response":null,"error":"..."}` and exit with nonzero status.
Set it to `false` to keep existing CLI output.

Before running, install and configure both required services:

- [AnkiConnect](https://github.com/hoangbkcntt98/anki-connect-server)
- [Muse2API](https://github.com/hoangbkcntt98/muse2api)

Install integrations:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r python/requirements.txt
```

Google OAuth credential and token paths resolve relative to the selected config
file. Service account auth works where Google API supports it; grant account
access to target Sheets and Drive files. Python imports use
`python.*`; set `COMMON_TOOLS_CONFIG` or pass `config=...`.

Run Python tools directly with `python/cli.py`. Command examples
for each integration live in `tools.test.txt`.

```bash
python python/cli.py --help
python python/cli.py --config config.json \
  sheets-read --spreadsheet-id SPREADSHEET_ID --range 'Sheet1!A1:C5'
```

## Facebook

### Prerequisites

Install Python dependencies. Configure Facebook Graph API version, Page ID,
and Page access token in `facebook`; token needs permissions for target Page.

### Input parameters

Operations take post/video object ID and message for comments; message, optional
image, or local video path for publishing. Video upload also accepts title,
description, Page ID, and optional future `--publish-at` timestamp.

### Usage

#### Python import

`FacebookTool` reads settings from `facebook` in config. Per-call arguments
override matching config values.

```python
from python.facebook import FacebookTool

facebook = FacebookTool("config.json")

# Read one page of comments, or follow all API pages with page_all=True.
comments = facebook.get_comments(
    "POST_OR_VIDEO_ID",
    fields="id,message,from,created_time",
    limit=100,
    page_all=True,
)

# Publish comment to a post or video.
comment = facebook.create_comment("POST_OR_VIDEO_ID", "Comment text")

# Schedule text/link, photo, or video Page post with Unix timestamp in UTC.
post = facebook.create_post("Scheduled message", scheduled_publish_time=1_800_000_000)
photo_post = facebook.create_photo_post(
    "output/image.jpg", "Scheduled photo", scheduled_publish_time=1_800_000_000,
)

# Upload local video to configured Page now or schedule it.
upload = facebook.upload_video(
    "output/video.mp4",
    description="Video description",
    title="Optional title",
    scheduled_publish_time=1_800_000_000,
)
```

`page_id`, `description`, `title`, `fields`, `limit`, and extra upload fields
can be passed per call. Module-level `get_comments(...)` and `upload_video(...)`
wrappers accept `config=` and the same operation arguments.

#### Command line

`scheduled_publish_time` in Python is Unix seconds (UTC). CLI `--publish-at`
requires a future ISO-8601 time with timezone. Scheduling asks Facebook to
publish the Page post/photo/video at that time.

```bash
python python/cli.py --config config.json facebook-post \
  --message "Scheduled post" --publish-at 2026-10-27T09:00:00Z
python python/cli.py --config config.json facebook-post \
  --message "Scheduled photo" --image output/image.jpg --publish-at 2026-10-27T09:00:00Z
python python/cli.py --config config.json facebook-upload-video \
  --video output/video.mp4 --description "Scheduled video" --publish-at 2026-10-27T09:00:00Z
python python/cli.py --config config.json facebook-comments \
  --object-id POST_OR_VIDEO_ID --limit 50 --all-pages
python python/cli.py --config config.json facebook-comment \
  --object-id POST_OR_VIDEO_ID --message "Comment text"
```

## Databases

### Prerequisites

Configure `database.driver` as `postgresql` or `mysql`, plus connection settings.
Install `psycopg[binary,pool]` for PostgreSQL or `mysql-connector-python` for
MySQL. TypeScript requires `pg` or `mysql2`.

### Input parameters

Pass table/column names, values, filters, and optional select limit to database
methods. Update/delete require non-empty `where` conditions.

### Usage

#### Python import

Python and TypeScript database tools create PostgreSQL or MySQL connection pools
and provide parameterized `select`, `insert`, `update`, and `delete` operations.
Set `database.driver` to `postgresql` or `mysql` in config. Both implementations
validate and quote table/column identifiers; update and delete require non-empty
conditions to avoid accidental full-table changes.

No database CLI command is currently provided.

```python
from python.database import create_database_pool

db = create_database_pool("config.json")
try:
    db.insert("users", {"name": "Ada"})
    rows = db.select("users", where={"active": True}, limit=50)
    db.update("users", {"active": False}, where={"id": 42})
    db.delete("users", where={"id": 42})
finally:
    db.close()
```

Python dependencies: `psycopg[binary,pool]` for PostgreSQL and
`mysql-connector-python` for MySQL. TypeScript dependencies: `pg` and `mysql2`.
Set database credentials through config or environment-specific config files.

## Google Sheets and Drive

### Prerequisites

Configure Google API credentials under `google`. OAuth needs `client.json` and
creates `token.json`; service-account auth needs a service-account JSON file
such as `account_service.json`. Enable Sheets/Drive APIs. Share target Sheets
and Drive files/folders with service account email when using service-account
auth. Configure `sheets_scopes` and `drive_scopes`.

### Input parameters

Sheets operations take spreadsheet ID, A1 ranges, values, and optional input
mode. Drive upload takes local file and folder ID; download takes file ID or
sharing URL, output path, and optional export MIME type.

### Usage

#### Python import

Functions use credentials configured in `google`. IDs, ranges, paths, and cell
contents are function arguments.

```python
from python.google import (
    download_drive_file,
    read_spreadsheet,
    upload_drive_file,
    write_spreadsheet,
)

config = "config.json"

# Read every tab, or request specific ranges with ranges=["Tab!A1:C20"].
sheet = read_spreadsheet("SPREADSHEET_ID", config=config)
first_tab = read_spreadsheet(
    "SPREADSHEET_ID",
    ranges=["Sheet1!A1:C20"],
    config=config,
)

# Write caller-provided rows; range and input mode are configurable.
result = write_spreadsheet(
    "SPREADSHEET_ID",
    "Sheet1!A1:B2",
    [["Name", "Value"], ["one", 1]],
    value_input_option="USER_ENTERED",
    config=config,
)

# Upload local file into a Drive folder; download Drive file by ID.
metadata = upload_drive_file("output/report.csv", "DRIVE_FOLDER_ID", config=config)
local_path = download_drive_file(
    "DRIVE_FILE_ID", "downloads/report.csv", config=config
)
```

`read_spreadsheet` returns spreadsheet ID, title, and requested ranges with cell
values. `write_spreadsheet` returns Google API update metadata.
`upload_drive_file` returns Drive file metadata. `download_drive_file` returns
the destination `Path`. Drive uploads/downloads support shared drives according
to `google.supports_all_drives`.

#### Command line

```bash
python python/cli.py --config config.json sheets-read \
  --spreadsheet-id SPREADSHEET_ID --range 'Sheet1!A1:C5'
python python/cli.py --config config.json sheets-write \
  --spreadsheet-id SPREADSHEET_ID --range 'Sheet1!A1:B2' \
  --values '[["Name","Value"],["one",1]]'
python python/cli.py --config config.json drive-upload \
  --file output/report.csv --folder-id DRIVE_FOLDER_ID
python python/cli.py --config config.json drive-download \
  --url 'https://drive.google.com/file/d/FILE_ID/view' \
  --output downloads/file.bin
```

For Google Docs, Sheets, or Slides files, `drive-download` exports to a default
office format. Pass `--mime-type` to choose another supported export format.

## Anki notes

### Prerequisites

Install and run Anki with AnkiConnect available. Set `anki.api_url` in config
or pass `--api-url`. Configure AnkiWeb credentials in Anki before sync.

### Input parameters

Listing takes an Anki search query and optional limit. Add takes deck, note
type, JSON fields, and optional JSON tags. Update takes note ID and JSON fields.
Delete takes one or more note IDs and is permanent. Sync accepts timeout.

### Usage

#### Command line

```bash
#start anki connect server
./anki_connect_server.sh start

python python/cli.py anki-sync --timeout 300
python python/cli.py anki-notes-list --query 'deck:Default' --limit 50
python python/cli.py anki-note-add --deck 'Default' --note-type 'Basic' --fields '{"Front":"Question","Back":"Answer"}' --tags '["manual"]'
python python/cli.py anki-note-update --note-id 1234567890 --fields '{"Back":"Updated answer"}'
python python/cli.py anki-note-delete --note-id 1234567890
```

There is no standalone Python notes API exposed; use AnkiConnect command-line
tools above.

## Local video tools

### Prerequisites

Install `ffmpeg` and ensure it is on PATH. `html-to-video` also needs Playwright
and Chromium (`python -m pip install -r python/requirements.txt` and
`python -m playwright install chromium`).

### Input parameters

`video-concat` takes ordered input clips, output path, and optional `--reencode`.
`html-to-video` takes HTML path, output path, duration, FPS, dimensions, and
optional start delay.

### Usage

#### Command line

`video-concat` joins video clips in the order supplied. Stream-copy is default; use
`--reencode` when source formats differ. Requires `ffmpeg` on PATH.

```bash
python python/cli.py video-concat \
  --input clip-1.mp4 --input clip-2.mp4 --output output/combined.mp4
python python/cli.py video-concat \
  --input clip-1.mp4 --input clip-2.mp4 --output output/combined.mp4 --reencode
```

`html-to-video` captures a local HTML page as MP4 using headless Chromium and
ffmpeg. Page animation runs while screenshots are captured; defaults are 5
seconds, 30 fps, and portrait 1080x1920.

```bash
python python/cli.py html-to-video \
  --html page.html --output output/page.mp4 --duration 8 --fps 30 --width 1080 --height 1920
```

#### Python import

```python
from python.video import concatenate_videos, html_to_video

concatenate_videos(["clip-1.mp4", "clip-2.mp4"], "output/combined.mp4")
html_to_video("page.html", "output/page.mp4", duration=8, fps=30)
```

TypeScript exports equivalent `concatenateVideos(...)` and `htmlToVideo(...)`
functions from `./src/video.js`; install its browser with
`npx playwright install chromium`.

## YouTube

### Prerequisites

Configure YouTube Data API OAuth credentials under `youtube`: OAuth client,
token, upload scope, category ID, and privacy status. Install Google API client
packages.

### Input parameters

Upload takes local video path and title. Description, tags, category ID,
privacy status, and optional publish time can be passed per call or configured
where supported.

### Usage

#### Python import

Uploads use YouTube Data API OAuth credentials under `youtube` config. Set
OAuth client file, token file, upload scope, category ID, and privacy status.
Provide video file and title per call.

```python
from python.youtube import upload_video

result = upload_video(
    "output/video.mp4",
    title="Video title",
    description="Video description",
    tags=["tag-one", "tag-two"],
category_id="22",
privacy_status="private",
made_for_kids=False,
contains_synthetic_media=False,
    config="config.json",
)
video_id = result["id"]
```

`category_id`, `privacy_status`, `made_for_kids`, and
`contains_synthetic_media` can come from config instead of arguments.
`made_for_kids` and `contains_synthetic_media` accept `true` or `false`; leave
them unset to omit those declarations. Choose values that accurately describe
video and intended audience. `publish_at` supports scheduled publish time where
YouTube API permits it. Upload options such as chunk size and returned API
parts are configurable.

#### Command line

```bash
python python/cli.py --config config.json youtube-upload \
  --video output/video.mp4 --title "Video title" \
  --privacy-status private --made-for-kids no \
  --contains-synthetic-media no --publish-at 2026-10-27T09:00:00Z
```

## AI APIs

### Prerequisites

Configure each provider under `ai.chat`, `ai.image`, `ai.audio`, or `ai.video`
with its base URL, API key/auth settings, and endpoint fields. Muse2API is
required for Muse image/video generation.

### Input parameters

Generation commands take a prompt (`--text` for audio), optional model, JSON
options, and optional output path. Generic `ai-call` takes service, endpoint,
HTTP method, JSON payload/headers/params, response type, and optional output.

### Usage

#### Python import

Each `ai.chat`, `ai.image`, `ai.video`, and `ai.audio` section can use its own
`base_url`, `api_key`, `api_key_header`, `auth_scheme`, and `timeout_seconds`.
Root-level AI settings remain fallbacks. Relative endpoints
join against that service's base URL; absolute endpoint URLs override it.

```python
from pathlib import Path
from python.ai import call_api, text_to_audio, text_to_image, text_to_video

config = "config.json"

# Generic request. `service` selects auth, timeout, and base URL section.
chat_response = call_api(
    "/chat/completions",
    service="chat",
    payload={"model": "CHAT_MODEL", "messages": [{"role": "user", "content": "Hi"}]},
    config=config,
)

  # Passing output saves bytes before optional server-side media cleanup.
  image_bytes = text_to_image("A prompt", output="output/image.png", config=config)
audio_bytes = text_to_audio("Text to speak", config=config)
Path("output/audio.mp3").write_bytes(audio_bytes)

  # Video creation polls, saves output, then cleans returned server-side media.
  video_result = text_to_video(
      "A video prompt", output="output/video.mp4", config=config
  )
```

When an output path is supplied, returned video media names are deleted from
the provider after successful download. Image cleanup runs only for model
`muse-image`. Both use the matching service `api_key` and derive
`/admin/media/delete` from its `base_url`; set `ai.media_delete_endpoint` or a
service-level `media_delete_endpoint` to override that path.

Image/audio/video model, endpoint, request fields, response fields, polling
states, and intervals are configurable. Pass `endpoint`, `model`, and
`options={...}` to override image/audio/video settings per call. `call_api`
accepts `method`, `payload`, `headers`, `params`, and `response_type` (`json`,
`bytes`, or `text`). For video, configure both `video.endpoint` and
`video.status_endpoint` with `{task_id}` placeholder when polling is needed.
Configure `ai.video.url_response_field` or
`ai.video.base64_response_field` when provider uses different response fields.
CLI `ai-video --output output/video.mp4` saves returned video URL or base64 data.

#### Command line

```bash
python python/cli.py --config config.json ai-call \
  --service chat --endpoint /chat/completions \
  --payload '{"model":"MODEL","messages":[{"role":"user","content":"Hi"}]}'
python python/cli.py --config config.json ai-image \
  --prompt "A Shiba Inu in a space helmet" --output output/image.png
python python/cli.py --config config.json ai-audio \
  --text "Hello there" --output output/audio.mp3
python python/cli.py --config config.json ai-video \
  --prompt "Sunrise over ocean" --output output/video.mp4
```

## Logging

### Prerequisites

Configure optional logger level, file path, console output, format, and
propagation under `logger`.

### Input parameters

Pass a message and optional logger name and level. `log` supports
`DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`.

### Usage

#### Python import

`get_logger` returns a standard Python logger with configured level, file,
console, format, and propagation. `log` writes one message using same settings.

```python
from python.logger import get_logger, log

logger = get_logger("my_tool", "config.json")
logger.info("Started")
logger.error("Failed")

log("Completed", name="my_tool", level="INFO", config="config.json")
```

Set `logger.file` to `null` to disable file output, or use `console` to enable
console output. Relative log paths resolve from config file directory.

#### Command line

```bash
python python/cli.py --config config.json log \
  --name tools.cli --level INFO --message "Task completed"
```

## TypeScript

### Prerequisites and usage

TypeScript tools mirror Python tools: Facebook Page posts/photos/videos/comments;
Google Sheets read/write and Drive upload/download; PostgreSQL/MySQL CRUD pools;
YouTube upload; AI API, image, audio, video; local video processing; and logging.
Install dependencies, then run from repository root:

```bash
cd ts
npm install
npm run typecheck
```

TypeScript also reads root `config.json` by default. Set
`COMMON_TOOLS_TS_CONFIG` to select another config file. Set AI credentials
in per-service `api_key` fields. Google OAuth credentials use direct config
fields `oauth_client_id`, `oauth_client_secret`, and `oauth_refresh_token`;
service-account auth uses `service_account_file`.

```typescript
import { FacebookTool } from "./src/facebook.js";
import {
  downloadDriveFile,
  readSpreadsheet,
  uploadDriveFile,
  writeSpreadsheet,
} from "./src/google.js";
import { callApi, textToAudio, textToImage, textToVideo } from "./src/ai.js";
import { log } from "./src/logger.js";
import { uploadVideo } from "./src/youtube.js";
import { createDatabasePool } from "./src/database.js";
import { concatenateVideos, htmlToVideo } from "./src/video.js";

const config = "config.json";
const facebook = await FacebookTool.create({ config });
const comments = await facebook.getComments("POST_OR_VIDEO_ID", { pageAll: true });
const fbUpload = await facebook.uploadVideo("output/video.mp4", {
  description: "Video description",
});
const scheduledPost = await facebook.createPost("Scheduled text", {
  scheduledPublishTime: 1_800_000_000,
});

const sheet = await readSpreadsheet("SPREADSHEET_ID", {
  ranges: ["Sheet1!A1:C20"],
  config,
});
await writeSpreadsheet("SPREADSHEET_ID", "Sheet1!A1:B2", [["Name", "Value"]], { config });
const driveFile = await uploadDriveFile("output/report.csv", "DRIVE_FOLDER_ID", { config });
await downloadDriveFile("DRIVE_FILE_ID", "downloads/file.bin", { config });

const database = await createDatabasePool({ config });
try {
  await database.insert("users", { name: "Ada" });
  const users = await database.select("users", { where: { active: true }, limit: 50 });
  await database.update("users", { active: false }, { id: 42 });
  await database.delete("users", { id: 42 });
} finally {
  await database.close();
}

const ytUpload = await uploadVideo("output/video.mp4", {
  title: "Video title",
  config,
});

const response = await callApi("/chat/completions", {
  service: "chat",
  payload: { model: "MODEL", messages: [{ role: "user", content: "Hi" }] },
  config,
});
const image = await textToImage("Image prompt", { config });
const audio = await textToAudio("Text to speak", { config });
const video = await textToVideo("Video prompt", { config });
const combined = await concatenateVideos(
  ["output/part-1.mp4", "output/part-2.mp4"],
  "output/combined.mp4",
);
const htmlVideo = await htmlToVideo("output/page.html", "output/page.mp4", {
  duration: 8,
});
await log(`Generated ${image.length} image bytes; comments: ${comments.length}`, { config });
```

### Input parameters

Pass operation-specific IDs, paths, prompts, ranges, values, or SQL data shown
in the example calls. Optional settings use an options object; `config` accepts
a path or loaded configuration object.

Functions accept `config` object or path; API and upload methods accept service
objects/fetch implementations for tests. `FacebookTool.create()` returns
instance with `getComments`, `createComment`, and `uploadVideo` methods.

## Permissions

Facebook comment reads and publishing need token permissions for target Page.
Google Sheets/Drive operations need configured OAuth scopes or service-account
access. YouTube uploads need OAuth credentials with upload scope. AI providers
may use different request/response schemas; configure endpoint paths and field
names to match each provider.
