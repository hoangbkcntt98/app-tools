import { appendFile, mkdir } from "node:fs/promises";
import path from "node:path";

import { type ConfigInput, resolveConfigPath, sectionConfig } from "./config.js";

export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
export type Logger = {
  debug(message: string): Promise<void>;
  info(message: string): Promise<void>;
  warning(message: string): Promise<void>;
  error(message: string): Promise<void>;
  critical(message: string): Promise<void>;
};

const levelPriority: Record<LogLevel, number> = {
  DEBUG: 10,
  INFO: 20,
  WARNING: 30,
  ERROR: 40,
  CRITICAL: 50,
};

export async function getLogger(
  name: string,
  input?: ConfigInput,
): Promise<Logger> {
  const settings = await sectionConfig(input, "logger");
  const minimum = normalizeLevel(settings.level ?? "INFO");
  const logPath =
    typeof settings.file === "string" && settings.file.trim()
      ? resolveConfigPath(settings, settings.file)
      : undefined;
  const format = String(
    settings.format ?? "%(asctime)s %(levelname)s %(name)s: %(message)s",
  );

  async function write(level: LogLevel, message: string): Promise<void> {
    if (levelPriority[level] < levelPriority[minimum]) return;
    const timestamp = new Date().toISOString();
    const line = format
      .replaceAll("%(asctime)s", timestamp)
      .replaceAll("%(levelname)s", level)
      .replaceAll("%(name)s", name)
      .replaceAll("%(message)s", message);
    if (settings.console) {
      if (level === "WARNING") console.warn(line);
      else if (level === "ERROR" || level === "CRITICAL") console.error(line);
      else if (level === "DEBUG") console.debug(line);
      else console.info(line);
    }
    if (logPath) {
      await mkdir(path.dirname(logPath), { recursive: true });
      await appendFile(logPath, `${line}\n`, "utf8");
    }
  }

  return {
    debug: (message) => write("DEBUG", message),
    info: (message) => write("INFO", message),
    warning: (message) => write("WARNING", message),
    error: (message) => write("ERROR", message),
    critical: (message) => write("CRITICAL", message),
  };
}

export async function log(
  message: string,
  options: {
    name?: string;
    level?: LogLevel;
    config?: ConfigInput;
  } = {},
): Promise<void> {
  const logger = await getLogger(options.name ?? "tools", options.config);
  const level = options.level ?? "INFO";
  await logger[level.toLowerCase() as keyof Logger](message);
}

function normalizeLevel(value: unknown): LogLevel {
  const level = String(value).toUpperCase();
  if (!(level in levelPriority)) {
    throw new TypeError(`Invalid logger level: ${String(value)}`);
  }
  return level as LogLevel;
}
