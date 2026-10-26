import assert from "node:assert/strict";
import test from "node:test";

import { callApi } from "./ai.js";

test("callApi uses per-service URL and JSON content type", async () => {
  let requestedUrl = "";
  let contentType = "";
  const fetchImpl: typeof fetch = async (input, init) => {
    requestedUrl = String(input);
    contentType = new Headers(init?.headers).get("Content-Type") ?? "";
    return new Response(JSON.stringify({ ok: true }), {
      headers: { "Content-Type": "application/json" },
    });
  };

  const result = await callApi("/chat", {
    service: "chat",
    payload: { message: "hello" },
    config: {
      ai: {
        chat: { base_url: "https://chat.example/v2" },
        image: { base_url: "https://image.example/v1" },
      },
    },
    fetchImpl,
  });

  assert.deepEqual(result, { ok: true });
  assert.equal(requestedUrl, "https://chat.example/v2/chat");
  assert.equal(contentType, "application/json");
});
