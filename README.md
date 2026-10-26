# Common tools

Reusable, config-driven tools for Facebook, Google, YouTube, AI HTTP APIs, and
logging.

## Setup

Implementations live in `python/` and `ts/`. Run commands from repository
root. Copy matching `config.example.json` to ignored `config.json`; set
provider URLs, IDs, scopes, models, paths, and credentials. Set secrets as
direct config values such as `ai.chat.api_key` and
`facebook.access_token`. These config files are ignored by Git. Explicit
function arguments override matching config values.

Install integrations:

```bash
python -m pip install -r common/tools/python/requirements.txt
```

Google OAuth credential and token paths resolve relative to the selected config
file. Service account auth works where Google API supports it; grant account
access to target Sheets and Drive files. Python imports use
`common.tools.python.*`; set `COMMON_TOOLS_CONFIG` or pass `config=...`.

Run Python tools directly with `common/tools/python/cli.py`. Command examples
for each integration live in `common/tools/tools.test.txt`.

```bash
python common/tools/python/cli.py --help
python common/tools/python/cli.py --config common/tools/python/config.json \
  sheets-read --spreadsheet-id SPREADSHEET_ID --range 'Sheet1!A1:C5'
```

## Facebook

`FacebookTool` reads settings from `facebook` in config. Put Page access token
in `access_token`; set Page ID, Graph API base URL, and version in config or
pass Page ID to an operation.

```python
from common.tools.python.facebook import FacebookTool

facebook = FacebookTool("common/tools/python/config.json")

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
wrappers accept `config=` and the same operation arguments. `scheduled_publish_time`
is Unix seconds (UTC); scheduling sends the Page post/photo/video unpublished
for Facebook to publish at that time. CLI also accepts ISO-8601 with explicit timezone:

```bash
python common/tools/python/cli.py --config common/tools/python/config.json facebook-post \
  --message "Scheduled post" --publish-at 2026-10-27T09:00:00Z
python common/tools/python/cli.py --config common/tools/python/config.json facebook-post \
  --message "Scheduled photo" --image output/image.jpg --publish-at 2026-10-27T09:00:00Z
python common/tools/python/cli.py --config common/tools/python/config.json facebook-upload-video \
  --video output/video.mp4 --description "Scheduled video" --publish-at 2026-10-27T09:00:00Z
```

## Databases

Python and TypeScript database tools create PostgreSQL or MySQL connection pools
and provide parameterized `select`, `insert`, `update`, and `delete` operations.
Set `database.driver` to `postgresql` or `mysql` in config. Both implementations
validate and quote table/column identifiers; update and delete require non-empty
conditions to avoid accidental full-table changes.

```python
from common.tools.python.database import create_database_pool

db = create_database_pool("common/tools/python/config.json")
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

Functions use Google credentials configured in `google`. IDs, ranges, paths, and
cell contents are function arguments.

```python
from common.tools.python.google import (
    download_drive_file,
    read_spreadsheet,
    upload_drive_file,
    write_spreadsheet,
)

config = "common/tools/python/config.json"

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

## Anki notes

These commands use AnkiConnect (Anki open and AnkiConnect available). Set
`anki.api_url` in config or pass `--api-url`. Listing supports Anki search
queries and optional limit. Sync runs AnkiConnect `sync` with configurable
timeout; AnkiWeb credentials must already be configured in Anki. Create/update
fields use JSON objects; deletion is permanent and takes explicit note IDs.

```bash
python common/tools/python/cli.py anki-sync --timeout 300
python common/tools/python/cli.py anki-notes-list --query 'deck:Default' --limit 50
python common/tools/python/cli.py anki-note-add --deck 'Default' --note-type 'Basic' --fields '{"Front":"Question","Back":"Answer"}' --tags '["manual"]'
python common/tools/python/cli.py anki-note-update --note-id 1234567890 --fields '{"Back":"Updated answer"}'
python common/tools/python/cli.py anki-note-delete --note-id 1234567890
```

## Local video tools

`video-concat` joins video clips in the order supplied. Stream-copy is default; use
`--reencode` when source formats differ. Requires `ffmpeg` on PATH.
TypeScript exports equivalent `concatenateVideos(...)` and `htmlToVideo(...)`
functions from `./src/video.js`.

```bash
python common/tools/python/cli.py video-concat \\
  --input clip-1.mp4 --input clip-2.mp4 --output output/combined.mp4
python common/tools/python/cli.py video-concat \\
  --input clip-1.mp4 --input clip-2.mp4 --output output/combined.mp4 --reencode
```

`html-to-video` captures a local HTML page as MP4 using headless Chromium and
ffmpeg. Install Python dependency plus browser with `python -m pip install -r
common/tools/python/requirements.txt && python -m playwright install chromium`. Page
animation runs while screenshots are captured; defaults are 5 seconds, 30 fps,
and portrait 1080x1920.
For TypeScript, install the browser with `npx playwright install chromium`.

```bash
python common/tools/python/cli.py html-to-video \\
  --html page.html --output output/page.mp4 --duration 8 --fps 30 --width 1080 --height 1920
```

## YouTube

Uploads use YouTube Data API OAuth credentials under `youtube` config. Set
OAuth client file, token file, upload scope, category ID, and privacy status.
Provide video file and title per call.

```python
from common.tools.python.youtube import upload_video

result = upload_video(
    "output/video.mp4",
    title="Video title",
    description="Video description",
    tags=["tag-one", "tag-two"],
    category_id="22",
    privacy_status="private",
    config="common/tools/python/config.json",
)
video_id = result["id"]
```

`category_id` and `privacy_status` can come from config instead of arguments.
`publish_at` supports scheduled publish time where YouTube API permits it.
Upload options such as chunk size and returned API parts are configurable.

## AI APIs

Each `ai.chat`, `ai.image`, `ai.video`, and `ai.audio` section can use its own
`base_url`, `api_key`, `api_key_header`, `auth_scheme`, and `timeout_seconds`.
Root-level AI settings remain fallbacks. Relative endpoints
join against that service's base URL; absolute endpoint URLs override it.

```python
from pathlib import Path
from common.tools.python.ai import call_api, text_to_audio, text_to_image, text_to_video

config = "common/tools/python/config.json"

# Generic request. `service` selects auth, timeout, and base URL section.
chat_response = call_api(
    "/chat/completions",
    service="chat",
    payload={"model": "CHAT_MODEL", "messages": [{"role": "user", "content": "Hi"}]},
    config=config,
)

# Image/audio functions return bytes; save them wherever caller chooses.
image_bytes = text_to_image("A prompt", config=config)
Path("output/image.png").write_bytes(image_bytes)
audio_bytes = text_to_audio("Text to speak", config=config)
Path("output/audio.mp3").write_bytes(audio_bytes)

# Video creation polls configured status endpoint until complete or timeout.
video_result = text_to_video("A video prompt", config=config)
```

Image/audio/video model, endpoint, request fields, response fields, polling
states, and intervals are configurable. Pass `endpoint`, `model`, and
`options={...}` to override image/audio/video settings per call. `call_api`
accepts `method`, `payload`, `headers`, `params`, and `response_type` (`json`,
`bytes`, or `text`). For video, configure both `video.endpoint` and
`video.status_endpoint` with `{task_id}` placeholder when polling is needed.

## Logging

`get_logger` returns a standard Python logger with configured level, file,
console, format, and propagation. `log` writes one message using same settings.

```python
from common.tools.python.logger import get_logger, log

logger = get_logger("my_tool", "common/tools/python/config.json")
logger.info("Started")
logger.error("Failed")

log("Completed", name="my_tool", level="INFO", config="common/tools/python/config.json")
```

Set `logger.file` to `null` to disable file output, or use `console` to enable
console output. Relative log paths resolve from config file directory.

## TypeScript

TypeScript tools mirror Python tools: Facebook Page posts/photos/videos/comments;
Google Sheets read/write and Drive upload/download; PostgreSQL/MySQL CRUD pools;
YouTube upload; AI API, image, audio, video; local video processing; and logging.
Run from repository root:

```bash
cd common/tools/ts
npm install
npm run typecheck
```

Copy `common/tools/ts/config.example.json` to `common/tools/ts/config.json`.
Set `COMMON_TOOLS_TS_CONFIG` to select another config file. Set AI credentials
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

Functions accept `config` object or path; API and upload methods accept service
objects/fetch implementations for tests. `FacebookTool.create()` returns
instance with `getComments`, `createComment`, and `uploadVideo` methods.

## Permissions

Facebook comment reads and publishing need token permissions for target Page.
Google Sheets/Drive operations need configured OAuth scopes or service-account
access. YouTube uploads need OAuth credentials with upload scope. AI providers
may use different request/response schemas; configure endpoint paths and field
names to match each provider.
