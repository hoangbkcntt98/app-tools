import { google } from "googleapis";

import { type ConfigInput, resolveConfigPath, sectionConfig } from "./config.js";

export async function googleService(
  api: "sheets" | "drive" | "youtube",
  version: string,
  config?: ConfigInput,
  scopes?: string[],
): Promise<any> {
  const settings = await sectionConfig(config, "google");
  const serviceSettings = await sectionConfig(config, api);
  const merged = { ...settings, ...serviceSettings };
  const selectedScopes = scopes ?? merged.scopes ?? settings.scopes ?? [];
  let auth: any;
  const authType = String(merged.auth_type ?? settings.auth_type ?? "oauth");
  if (authType === "service_account") {
    const keyFile = merged.service_account_file ?? settings.service_account_file;
    if (!keyFile) throw new TypeError("google.service_account_file is required");
    auth = new google.auth.GoogleAuth({
      keyFile: resolveConfigPath(settings, String(keyFile)),
      scopes: selectedScopes,
    });
  } else if (authType === "oauth") {
    const env = (key: string) =>
      process.env[String(merged[key] ?? settings[key] ?? "")] ?? "";
    const clientId =
      merged.oauth_client_id ?? env("oauth_client_id_env");
    const clientSecret =
      merged.oauth_client_secret ?? env("oauth_client_secret_env");
    const refreshToken =
      merged.oauth_refresh_token ?? env("oauth_refresh_token_env");
    if (!clientId || !clientSecret || !refreshToken) {
      throw new TypeError(
        "Configure Google OAuth client ID, client secret, and refresh token",
      );
    }
    const oauth = new google.auth.OAuth2(clientId, clientSecret);
    oauth.setCredentials({ refresh_token: refreshToken });
    auth = oauth;
  } else {
    throw new TypeError("google.auth_type must be oauth or service_account");
  }
  const apiName = String(merged.api_name ?? settings[`${api}_api_name`] ?? api);
  const apiVersion = String(
    merged.api_version ?? settings[`${api}_api_version`] ?? version,
  );
  const factory = (google as any)[apiName];
  if (typeof factory !== "function") {
    throw new TypeError(`Unsupported Google API name: ${apiName}`);
  }
  return factory({ version: apiVersion, auth });
}
