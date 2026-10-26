import { createReadStream, createWriteStream } from "node:fs";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { pipeline } from "node:stream/promises";

import { type ConfigInput, resolveConfigPath, sectionConfig } from "./config.js";
import { googleService } from "./google_auth.js";

export async function readSpreadsheet(
  spreadsheetId: string,
  options: {
    ranges?: string[];
    valueRenderOption?: string;
    config?: ConfigInput;
    service?: any;
  } = {},
): Promise<Record<string, any>> {
  if (!spreadsheetId) throw new TypeError("spreadsheetId is required");
  const settings = await sectionConfig(options.config, "google");
  const sheets =
    options.service ??
    (await googleService(
      "sheets",
      String(settings.sheets_api_version ?? "v4"),
      options.config,
      settings.sheets_scopes,
    ));
  const metadata = await sheets.spreadsheets.get({
    spreadsheetId,
    fields: settings.sheets_metadata_fields ??
      "properties(title),sheets(properties(title))",
  });
  const ranges: string[] = options.ranges?.length
    ? options.ranges
    : (metadata.data.sheets ?? []).map(
        (sheet: any) => `'${String(sheet.properties.title).replaceAll("'", "''")}'`,
      );
  const values = [];
  for (const range of ranges) {
    const response = await sheets.spreadsheets.values.get({
      spreadsheetId,
      range,
      valueRenderOption:
        options.valueRenderOption ?? settings.value_render_option ?? "FORMATTED_VALUE",
    });
    values.push({
      range: response.data.range ?? range,
      values: response.data.values ?? [],
    });
  }
  return {
    spreadsheet_id: spreadsheetId,
    title: metadata.data.properties?.title ?? spreadsheetId,
    ranges: values,
  };
}

export async function writeSpreadsheet(
  spreadsheetId: string,
  range: string,
  values: unknown[][],
  options: {
    valueInputOption?: string;
    config?: ConfigInput;
    service?: any;
  } = {},
): Promise<Record<string, any>> {
  if (!spreadsheetId || !range) {
    throw new TypeError("spreadsheetId and range are required");
  }
  const settings = await sectionConfig(options.config, "google");
  const sheets =
    options.service ??
    (await googleService("sheets", "v4", options.config, settings.sheets_scopes));
  const response = await sheets.spreadsheets.values.update({
    spreadsheetId,
    range,
    valueInputOption:
      options.valueInputOption ?? settings.value_input_option ?? "USER_ENTERED",
    requestBody: { values },
  });
  return response.data;
}

export async function uploadDriveFile(
  localPath: string,
  folderId: string,
  options: {
    remoteName?: string;
    mimeType?: string;
    config?: ConfigInput;
    service?: any;
  } = {},
): Promise<Record<string, any>> {
  if (!folderId) throw new TypeError("folderId is required");
  const settings = await sectionConfig(options.config, "google");
  const drive =
    options.service ??
    (await googleService("drive", "v3", options.config, settings.drive_scopes));
  const file = resolveConfigPath(settings, localPath);
  const response = await drive.files.create({
    requestBody: { name: options.remoteName ?? path.basename(file), parents: [folderId] },
    media: {
      mimeType: options.mimeType ?? "application/octet-stream",
      body: createReadStream(file),
    },
    supportsAllDrives: settings.supports_all_drives ?? true,
    fields: settings.drive_file_fields ?? "id,name,mimeType,webViewLink",
  });
  return response.data;
}

export async function downloadDriveFile(
  fileId: string,
  destination: string,
  options: { config?: ConfigInput; service?: any } = {},
): Promise<string> {
  if (!fileId) throw new TypeError("fileId is required");
  const settings = await sectionConfig(options.config, "google");
  const drive =
    options.service ??
    (await googleService("drive", "v3", options.config, settings.drive_scopes));
  const output = resolveConfigPath(settings, destination);
  await mkdir(path.dirname(output), { recursive: true });
  const response = await drive.files.get(
    {
      fileId,
      alt: "media",
      supportsAllDrives: settings.supports_all_drives ?? true,
    },
    { responseType: "stream" },
  );
  await pipeline(response.data, createWriteStream(output));
  return output;
}
