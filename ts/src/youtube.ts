import { createReadStream } from "node:fs";
import path from "node:path";

import { type ConfigInput, resolveConfigPath, sectionConfig } from "./config.js";
import { googleService } from "./google_auth.js";

export async function uploadVideo(
  videoPath: string,
  options: {
    title: string;
    description?: string;
    tags?: string[];
    categoryId?: string;
    privacyStatus?: string;
    publishAt?: string;
    config?: ConfigInput;
    service?: any;
  },
): Promise<Record<string, any>> {
  if (!options.title?.trim()) throw new TypeError("title is required");
  const settings = await sectionConfig(options.config, "youtube");
  const categoryId = options.categoryId ?? settings.category_id;
  const privacyStatus = options.privacyStatus ?? settings.privacy_status;
  if (!categoryId || !privacyStatus) {
    throw new TypeError("Configure youtube.category_id and privacy_status");
  }
  const file = resolveConfigPath(settings, videoPath);
  const youtube =
    options.service ??
    (await googleService(
      "youtube",
      String(settings.api_version ?? "v3"),
      options.config,
      settings.scopes ?? ["https://www.googleapis.com/auth/youtube.upload"],
    ));
  const status: Record<string, string> = { privacyStatus };
  if (options.publishAt) status.publishAt = options.publishAt;
  const response = await youtube.videos.insert({
    part: settings.upload_parts ?? "snippet,status",
    requestBody: {
      snippet: {
        title: options.title,
        description: options.description ?? "",
        tags: options.tags ?? settings.tags ?? [],
        categoryId: String(categoryId),
      },
      status,
    },
    media: {
      mimeType: "application/octet-stream",
      body: createReadStream(file),
    },
    notifySubscribers: settings.notify_subscribers,
  });
  return response.data;
}
