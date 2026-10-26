import { setTimeout as delay } from "node:timers/promises";

import { type ConfigInput, sectionConfig } from "./config.js";

export type JsonObject = Record<string, any>;
export type ApiResponseType = "json" | "bytes" | "text";

export type CallApiOptions = {
  service?: string;
  method?: string;
  payload?: unknown;
  headers?: Record<string, string>;
  params?: Record<string, string | number | boolean>;
  responseType?: ApiResponseType;
  config?: ConfigInput;
  fetchImpl?: typeof fetch;
};

export async function callApi(
  endpoint: string,
  options: CallApiOptions = {},
): Promise<any> {
  const service = options.service ?? "chat";
  const root = await sectionConfig(options.config, "ai");
  const serviceSettings = root[service] ?? {};
  if (
    serviceSettings === null ||
    Array.isArray(serviceSettings) ||
    typeof serviceSettings !== "object"
  ) {
    throw new TypeError(`ai.${service} config must be an object`);
  }
  const settings = { ...root, ...serviceSettings };
  const url = resolveEndpoint(
    endpoint,
    String(settings.base_url ?? ""),
    options.params,
  );
  const headers = new Headers(options.headers);
  const apiKey =
    String(settings.api_key ?? "").trim() ||
    (settings.api_key_env
      ? process.env[String(settings.api_key_env)]?.trim() ?? ""
      : "");
  const keyHeader = String(settings.api_key_header ?? "Authorization");
  if (apiKey && !headers.has(keyHeader)) {
    const scheme = String(settings.auth_scheme ?? "Bearer").trim();
    headers.set(keyHeader, `${scheme} ${apiKey}`.trim());
  }
  headers.set(
    "Accept",
    headers.get("Accept") ?? String(settings.accept ?? "application/json"),
  );

  const payload = options.payload;
  const isJson =
    payload !== undefined &&
    payload !== null &&
    (Array.isArray(payload) || typeof payload === "object");
  if (isJson && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await (options.fetchImpl ?? fetch)(url, {
    method: String(options.method ?? "POST").toUpperCase(),
    headers,
    body:
      payload === undefined || payload === null
        ? undefined
        : isJson
          ? JSON.stringify(payload)
          : (payload as BodyInit),
    signal: AbortSignal.timeout(Number(settings.timeout_seconds ?? 120) * 1000),
  });
  if (!response.ok) {
    const detail = (await response.text()).slice(0, 1000);
    throw new Error(`AI API request failed (HTTP ${response.status}): ${detail}`);
  }
  const responseType = options.responseType ?? "json";
  if (responseType === "bytes") return Buffer.from(await response.arrayBuffer());
  if (responseType === "text") return response.text();
  return response.json();
}

export type GenerateOptions = {
  endpoint?: string;
  model?: string;
  options?: JsonObject;
  config?: ConfigInput;
  fetchImpl?: typeof fetch;
};

export async function textToImage(
  prompt: string,
  options: GenerateOptions = {},
): Promise<Buffer> {
  if (!prompt.trim()) throw new TypeError("prompt is required");
  const settings = await sectionConfig(options.config, "ai");
  const image = serviceSettings(settings, "image");
  const endpoint = options.endpoint ?? image.endpoint;
  const model = options.model ?? image.model;
  if (!endpoint || !model) {
    throw new TypeError("Provide image endpoint and model in arguments or config");
  }
  const payload: JsonObject = {
    ...(image.request_options ?? {}),
    ...(options.options ?? {}),
    [String(image.model_field ?? "model")]: model,
    [String(image.prompt_field ?? "prompt")]: prompt,
  };
  const result = await callApi(String(endpoint), {
    service: "image",
    method: String(image.method ?? "POST"),
    payload,
    config: options.config,
    fetchImpl: options.fetchImpl,
  });
  const item = Array.isArray(result?.[image.data_field ?? "data"])
    ? result[image.data_field ?? "data"][0]
    : result;
  const encoded = item?.[image.base64_response_field ?? "b64_json"];
  if (encoded) {
    const data = String(encoded).replace(/^data:[^,]*,/, "");
    return Buffer.from(data, "base64");
  }
  const imageUrl = item?.[image.url_response_field ?? "url"];
  if (!imageUrl) throw new Error("Image API response has no base64 data or URL");
  const downloaded = await (options.fetchImpl ?? fetch)(String(imageUrl), {
    signal: AbortSignal.timeout(Number(image.timeout_seconds ?? 120) * 1000),
  });
  if (!downloaded.ok) {
    throw new Error(`Image download failed (HTTP ${downloaded.status})`);
  }
  return Buffer.from(await downloaded.arrayBuffer());
}

export async function textToAudio(
  text: string,
  options: GenerateOptions = {},
): Promise<Buffer> {
  if (!text.trim()) throw new TypeError("text is required");
  const root = await sectionConfig(options.config, "ai");
  const audio = serviceSettings(root, "audio");
  const endpoint = options.endpoint ?? audio.endpoint;
  const model = options.model ?? audio.model;
  if (!endpoint || !model) {
    throw new TypeError("Provide audio endpoint and model in arguments or config");
  }
  const payload: JsonObject = {
    ...(audio.request_options ?? {}),
    ...(options.options ?? {}),
    [String(audio.model_field ?? "model")]: model,
    [String(audio.text_field ?? "input")]: text,
  };
  const result = await callApi(String(endpoint), {
    service: "audio",
    method: String(audio.method ?? "POST"),
    payload,
    responseType: String(audio.response_type ?? "bytes") as ApiResponseType,
    config: options.config,
    fetchImpl: options.fetchImpl,
  });
  if (Buffer.isBuffer(result)) return result;
  const encoded =
    result?.[audio.base64_response_field ?? "audio"] ??
    result?.[audio.alternate_base64_response_field ?? "b64_json"];
  if (!encoded) throw new Error("Audio API response does not contain audio bytes");
  return Buffer.from(String(encoded).replace(/^data:[^,]*,/, ""), "base64");
}

export async function textToVideo(
  prompt: string,
  options: GenerateOptions = {},
): Promise<JsonObject> {
  if (!prompt.trim()) throw new TypeError("prompt is required");
  const root = await sectionConfig(options.config, "ai");
  const video = serviceSettings(root, "video");
  const endpoint = options.endpoint ?? video.endpoint;
  const statusEndpoint = video.status_endpoint;
  if (!endpoint || !statusEndpoint) {
    throw new TypeError("Configure ai.video.endpoint and status_endpoint");
  }
  const payload: JsonObject = {
    ...(video.request_options ?? {}),
    ...(options.options ?? {}),
    [String(video.prompt_field ?? "prompt")]: prompt,
  };
  const model = options.model ?? video.model;
  if (model) payload[String(video.model_field ?? "model")] = model;

  const created = await callApi(String(endpoint), {
    service: "video",
    method: String(video.method ?? "POST"),
    payload,
    config: options.config,
    fetchImpl: options.fetchImpl,
  });
  if (!created || typeof created !== "object") {
    throw new TypeError("Video create API must return a JSON object");
  }
  const taskId = created[String(video.task_id_field ?? "id")];
  if (!taskId) return created;

  const taskField = String(video.task_id_field ?? "id");
  const statusField = String(video.status_field ?? "status");
  const success = new Set<string>(
    video.success_values ?? ["succeeded", "completed"],
  );
  const failures = new Set<string>(video.failure_values ?? ["failed", "error"]);
  const deadline =
    Date.now() + Number(video.poll_timeout_seconds ?? 900) * 1000;
  while (true) {
    const statusUrl = String(statusEndpoint)
      .replaceAll(`{${taskField}}`, encodeURIComponent(String(taskId)))
      .replaceAll("{task_id}", encodeURIComponent(String(taskId)));
    const result = await callApi(statusUrl, {
      service: "video",
      method: String(video.status_method ?? "GET"),
      config: options.config,
      fetchImpl: options.fetchImpl,
    });
    const status = String(result?.[statusField] ?? "");
    if (success.has(status)) return result;
    if (failures.has(status)) {
      throw new Error(`Video generation failed: ${JSON.stringify(result)}`);
    }
    if (Date.now() >= deadline) {
      throw new Error(`Video task ${String(taskId)} exceeded polling timeout`);
    }
    await delay(Number(video.poll_interval_seconds ?? 5) * 1000);
  }
}

function resolveEndpoint(
  endpoint: string,
  baseUrl: string,
  params?: Record<string, string | number | boolean>,
): string {
  let url: URL;
  try {
    url = new URL(endpoint);
  } catch {
    if (!baseUrl) throw new TypeError("Configure service base_url for relative endpoint");
    url = new URL(endpoint.replace(/^\/+/, ""), `${baseUrl.replace(/\/+$/, "")}/`);
  }
  for (const [key, value] of Object.entries(params ?? {})) {
    url.searchParams.set(key, String(value));
  }
  return url.toString();
}

function serviceSettings(root: JsonObject, service: string): JsonObject {
  const value = root[service] ?? {};
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new TypeError(`ai.${service} config must be an object`);
  }
  return value;
}
