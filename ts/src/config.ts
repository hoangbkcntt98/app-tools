import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

export type ToolConfig = Record<string, any>;
export type ConfigInput = ToolConfig | string;

const moduleDir = path.dirname(fileURLToPath(import.meta.url));
export const defaultConfigPath = path.resolve(moduleDir, "../../config.json");

export async function loadConfig(input?: ConfigInput): Promise<ToolConfig> {
  if (input && typeof input === "object") return { ...input };
  const filePath =
    input ??
    process.env.COMMON_TOOLS_TS_CONFIG ??
    (await fileExists(defaultConfigPath) ? defaultConfigPath : undefined);
  if (!filePath) return {};
  try {
    const parsed: unknown = JSON.parse(await readFile(filePath, "utf8"));
    if (parsed === null || Array.isArray(parsed) || typeof parsed !== "object") {
      throw new TypeError(`Tool config must contain a JSON object: ${filePath}`);
    }
    return { ...(parsed as ToolConfig), _configPath: path.resolve(filePath) };
  } catch (error) {
    throw new Error(`Could not load tool config ${filePath}`, { cause: error });
  }
}

export async function sectionConfig(
  input: ConfigInput | undefined,
  section: string,
): Promise<ToolConfig> {
  const root = await loadConfig(input);
  const value = root[section] ?? {};
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new TypeError(`Config section ${section} must be an object`);
  }
  return { ...value, _configPath: root._configPath };
}

export function resolveConfigPath(
  config: ToolConfig,
  inputPath: string,
): string {
  const expanded = inputPath.startsWith("~/")
    ? path.join(process.env.HOME ?? "", inputPath.slice(2))
    : inputPath;
  if (path.isAbsolute(expanded)) return expanded;
  const parent = config._configPath
    ? path.dirname(config._configPath)
    : process.cwd();
  return path.resolve(parent, expanded);
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    await readFile(filePath);
    return true;
  } catch {
    return false;
  }
}
