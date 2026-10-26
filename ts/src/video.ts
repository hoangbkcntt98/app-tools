import { spawnSync } from "node:child_process";
import { access, mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

export async function concatenateVideos(
  videos: string[],
  output: string,
  options: {
    ffmpegBin?: string;
    reencode?: boolean;
    videoCodec?: string;
    audioCodec?: string;
  } = {},
): Promise<string> {
  if (!videos.length) throw new TypeError("at least one input video is required");
  const inputs = videos.map((file) => path.resolve(file));
  for (const input of inputs) {
    await access(input);
  }
  const destination = path.resolve(output);
  await mkdir(path.dirname(destination), { recursive: true });
  const temp = await mkdtemp(path.join(os.tmpdir(), "ffmpeg-concat-"));
  try {
    const listing = path.join(temp, "inputs.txt");
    const escaped = inputs.map((input) =>
      `file '${input.replaceAll("'", "'\\''")}'\n`
    ).join("");
    await writeFile(listing, escaped, "utf8");
    const args = [
      "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
      "-i", listing,
      ...(options.reencode
        ? ["-c:v", options.videoCodec ?? "libx264", "-c:a", options.audioCodec ?? "aac"]
        : ["-c", "copy"]),
      destination,
    ];
    run(options.ffmpegBin ?? "ffmpeg", args);
    return destination;
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
}

export async function htmlToVideo(
  html: string,
  output: string,
  options: {
    duration?: number;
    fps?: number;
    width?: number;
    height?: number;
    start?: number;
    ffmpegBin?: string;
    chromiumBin?: string;
  } = {},
): Promise<string> {
  const duration = options.duration ?? 5;
  const fps = options.fps ?? 30;
  const width = options.width ?? 1080;
  const height = options.height ?? 1920;
  const start = options.start ?? 0;
  if (duration <= 0 || fps <= 0 || width <= 0 || height <= 0 || start < 0) {
    throw new TypeError("duration, fps, width, height must be positive; start must be non-negative");
  }
  const source = path.resolve(html);
  const destination = path.resolve(output);
  await access(source);
  await mkdir(path.dirname(destination), { recursive: true });
  const temp = await mkdtemp(path.join(os.tmpdir(), "html-video-"));
  const count = Math.floor(duration * fps);
  try {
    let chromium: typeof import("playwright").chromium;
    try {
      ({ chromium } = await import("playwright"));
    } catch (error) {
      throw new Error("HTML video needs Playwright: install playwright and Chromium", { cause: error });
    }
    const browser = await chromium.launch({
      headless: true,
      ...(options.chromiumBin ? { executablePath: options.chromiumBin } : {}),
    });
    try {
      const page = await browser.newPage({
        viewport: { width, height },
        deviceScaleFactor: 1,
      });
      await page.goto(pathToFileURL(source).href, { waitUntil: "networkidle" });
      if (start) await page.waitForTimeout(start * 1000);
      for (let frame = 0; frame < count; frame += 1) {
        const filename = path.join(temp, `frame-${String(frame).padStart(6, "0")}.png`);
        await page.screenshot({ path: filename });
        if (frame + 1 < count) await page.waitForTimeout(Math.max(1, Math.round(1000 / fps)));
      }
    } finally {
      await browser.close();
    }
    run(options.ffmpegBin ?? "ffmpeg", [
      "-hide_banner", "-loglevel", "error", "-y", "-framerate", String(fps),
      "-i", path.join(temp, "frame-%06d.png"), "-frames:v", String(count),
      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
      destination,
    ]);
    return destination;
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
}

function run(binary: string, args: string[]): void {
  const result = spawnSync(binary, args, { encoding: "utf8" });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${binary} failed (${result.status}): ${result.stderr.trim()}`);
  }
}
