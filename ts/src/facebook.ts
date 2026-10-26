import { type ConfigInput, sectionConfig } from "./config.js";

export type FacebookOptions = {
  config?: ConfigInput;
  fetchImpl?: typeof fetch;
};

export class FacebookTool {
  private constructor(
    private readonly settings: Record<string, any>,
    private readonly token: string,
    private readonly fetchImpl: typeof fetch,
  ) {}

  static async create(options: FacebookOptions = {}): Promise<FacebookTool> {
    const settings = await sectionConfig(options.config, "facebook");
    const token =
      String(settings.access_token ?? "").trim() ||
      process.env[String(settings.access_token_env ?? "")]?.trim() ||
      "";
    if (!token) {
      throw new TypeError("Provide facebook.access_token or access_token_env");
    }
    if (!settings.graph_api_base || !settings.graph_api_version) {
      throw new TypeError("facebook.graph_api_base and graph_api_version are required");
    }
    return new FacebookTool(settings, token, options.fetchImpl ?? fetch);
  }

  async uploadVideo(
    videoPath: string,
    options: {
      pageId?: string;
      description?: string;
      title?: string;
      scheduledPublishTime?: number;
      extraFields?: Record<string, string>;
    } = {},
  ): Promise<Record<string, any>> {
    const pageId = options.pageId ?? this.settings.page_id;
    if (!pageId) throw new TypeError("pageId is required");
    const file = await fileBlob(videoPath);
    const body = new FormData();
    body.set("access_token", this.token);
    body.set("description", options.description ?? "");
    if (options.title !== undefined) body.set("title", options.title);
    if (options.scheduledPublishTime !== undefined) {
      body.set("published", "false");
      body.set("scheduled_publish_time", String(options.scheduledPublishTime));
    }
    for (const [key, value] of Object.entries(options.extraFields ?? {})) {
      body.set(key, value);
    }
    body.set("source", file);
    return this.request(`${pageId}/videos`, { method: "POST", body });
  }

  async createPost(
    message: string,
    options: {
      pageId?: string;
      scheduledPublishTime?: number;
      published?: boolean;
      imageUrl?: string;
    } = {},
  ): Promise<Record<string, any>> {
    if (!message.trim()) throw new TypeError("message must be non-empty");
    const pageId = options.pageId ?? this.settings.page_id;
    if (!pageId) throw new TypeError("pageId is required");
    const body = new URLSearchParams({ access_token: this.token, message });
    if (options.imageUrl) body.set("link", options.imageUrl);
    if (options.scheduledPublishTime !== undefined) {
      body.set("published", "false");
      body.set("scheduled_publish_time", String(options.scheduledPublishTime));
    } else if (options.published === false) {
      body.set("published", "false");
    }
    return this.request(`${pageId}/feed`, { method: "POST", body });
  }

  async createPhotoPost(
    imagePath: string,
    message: string,
    options: { pageId?: string; scheduledPublishTime?: number } = {},
  ): Promise<Record<string, any>> {
    if (!message.trim()) throw new TypeError("message must be non-empty");
    const pageId = options.pageId ?? this.settings.page_id;
    if (!pageId) throw new TypeError("pageId is required");
    const file = await fileBlob(imagePath);
    if (options.scheduledPublishTime === undefined) {
      const body = new FormData();
      body.set("access_token", this.token);
      body.set("caption", message);
      body.set("source", file);
      return this.request(`${pageId}/photos`, { method: "POST", body });
    }

    const upload = new FormData();
    upload.set("access_token", this.token);
    upload.set("published", "false");
    upload.set("source", file);
    const uploaded = await this.request(`${pageId}/photos`, {
      method: "POST",
      body: upload,
    });
    if (!uploaded.id) throw new Error("Facebook photo upload response omitted id");
    const post = new URLSearchParams({
      access_token: this.token,
      message,
      "attached_media[0]": JSON.stringify({ media_fbid: uploaded.id }),
      published: "false",
      scheduled_publish_time: String(options.scheduledPublishTime),
    });
    return this.request(`${pageId}/feed`, { method: "POST", body: post });
  }

  async getComments(
    objectId: string,
    options: {
      fields?: string;
      limit?: number;
      pageAll?: boolean;
    } = {},
  ): Promise<Record<string, any>[]> {
    if (!objectId) throw new TypeError("objectId is required");
    const params = new URLSearchParams({
      fields: options.fields ??
        this.settings.comment_fields ??
        "id,message,from,created_time",
      access_token: this.token,
    });
    const limit = options.limit ?? this.settings.comment_limit;
    if (limit !== undefined) params.set("limit", String(limit));
    const comments: Record<string, any>[] = [];
    let url = this.url(`${objectId}/comments`);
    url.search = params.toString();
    do {
      const response = await this.fetchImpl(url, {
        signal: AbortSignal.timeout(Number(this.settings.timeout_seconds ?? 120) * 1000),
      });
      const data = await this.json(response);
      if (!Array.isArray(data.data)) throw new Error("Facebook comments response has invalid data");
      comments.push(...data.data.filter((item: unknown) => item && typeof item === "object"));
      const next = options.pageAll ? data.paging?.next : undefined;
      if (!next) break;
      const nextUrl = new URL(next);
      if (nextUrl.host !== this.url("").host) {
        throw new Error("Facebook pagination URL uses unexpected host");
      }
      url = nextUrl;
    } while (true);
    return comments;
  }

  async createComment(objectId: string, message: string): Promise<Record<string, any>> {
    if (!objectId || !message.trim()) {
      throw new TypeError("objectId and non-empty message are required");
    }
    const body = new URLSearchParams({ access_token: this.token, message });
    return this.request(`${objectId}/comments`, { method: "POST", body });
  }

  private url(objectPath: string): URL {
    return new URL(
      `${String(this.settings.graph_api_version).replace(/^\/+|\/+$/g, "")}/${objectPath.replace(/^\/+/, "")}`,
      `${String(this.settings.graph_api_base).replace(/\/+$/, "")}/`,
    );
  }

  private async request(
    objectPath: string,
    init: RequestInit,
  ): Promise<Record<string, any>> {
    const url = this.url(objectPath);
    const response = await this.fetchImpl(url, {
      ...init,
      signal: AbortSignal.timeout(Number(this.settings.timeout_seconds ?? 120) * 1000),
    });
    return this.json(response);
  }

  private async json(response: Response): Promise<Record<string, any>> {
    let payload: any = {};
    try {
      payload = await response.json();
    } catch {
      // Keep malformed provider responses in the same error path.
    }
    if (!response.ok || payload.error) {
      throw new Error(
        `Facebook API request failed (HTTP ${response.status}): ${payload.error?.message ?? "invalid API response"}`,
      );
    }
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new Error("Facebook API returned a non-object response");
    }
    return payload;
  }
}

// Node's File API accepts file bytes without introducing a third-party dependency.
async function fileBlob(filePath: string): Promise<Blob> {
  const { readFile } = await import("node:fs/promises");
  const { basename } = await import("node:path");
  const bytes = await readFile(filePath);
  return new File([bytes], basename(filePath));
}
