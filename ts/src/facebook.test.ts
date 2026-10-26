import assert from "node:assert/strict";
import test from "node:test";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { FacebookTool } from "./facebook.js";

test("FacebookTool schedules text and photo posts", async () => {
  const requests: Array<{ url: string; body: BodyInit | null | undefined }> = [];
  const fetchImpl: typeof fetch = async (input, init) => {
    const url = String(input);
    requests.push({ url, body: init?.body });
    return new Response(JSON.stringify({ id: url.endsWith("/photos") ? "photo-1" : "post-1" }), {
      headers: { "Content-Type": "application/json" },
    });
  };
  const tool = await FacebookTool.create({
    config: {
      facebook: {
        graph_api_base: "https://graph.example",
        graph_api_version: "v1",
        page_id: "page-1",
        access_token: "token",
      },
    },
    fetchImpl,
  });

  await tool.createPost("hello", { scheduledPublishTime: 1_800_000_000 });
  assert.equal(requests[0].url, "https://graph.example/v1/page-1/feed");
  assert.equal(
    new URLSearchParams(requests[0].body as URLSearchParams).get("scheduled_publish_time"),
    "1800000000",
  );

  const directory = await mkdtemp(path.join(os.tmpdir(), "facebook-test-"));
  try {
    const image = path.join(directory, "image.png");
    await writeFile(image, "image");
    await tool.createPhotoPost(image, "caption", { scheduledPublishTime: 1_800_000_000 });
    assert.equal(requests[1].url, "https://graph.example/v1/page-1/photos");
    assert.equal(requests[2].url, "https://graph.example/v1/page-1/feed");
    assert.equal(
      new URLSearchParams(requests[2].body as URLSearchParams).get("attached_media[0]"),
      '{"media_fbid":"photo-1"}',
    );
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
