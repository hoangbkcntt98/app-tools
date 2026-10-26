import assert from "node:assert/strict";
import test from "node:test";

import { concatenateVideos, htmlToVideo } from "./video.js";

test("local video helpers validate inputs before running external tools", async () => {
  await assert.rejects(concatenateVideos([], "output.mp4"), /at least one input video/);
  await assert.rejects(
    htmlToVideo("page.html", "output.mp4", { duration: 0 }),
    /duration, fps, width, height must be positive/,
  );
});
