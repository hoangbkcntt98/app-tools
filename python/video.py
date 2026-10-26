"""Local ffmpeg utilities for joining clips and turning HTML into video."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence


def _ffmpeg(binary: str | None = None) -> str:
    executable = binary or shutil.which("ffmpeg")
    if not executable:
        raise RuntimeError("ffmpeg not found; install ffmpeg or pass ffmpeg_bin")
    return executable


def concatenate_videos(
    videos: Sequence[str | Path],
    output: str | Path,
    *,
    ffmpeg_bin: str | None = None,
    reencode: bool = False,
    video_codec: str = "libx264",
    audio_codec: str = "aac",
) -> Path:
    """Concatenate video files in order. Re-encode clips with differing formats."""
    inputs = [Path(item).expanduser().resolve() for item in videos]
    destination = Path(output).expanduser()
    if not inputs:
        raise ValueError("at least one input video is required")
    for item in inputs:
        if not item.is_file():
            raise FileNotFoundError(item)
    destination.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = _ffmpeg(ffmpeg_bin)
    with tempfile.TemporaryDirectory(prefix="ffmpeg-concat-") as temp_dir:
        listing = Path(temp_dir) / "inputs.txt"
        # ffconcat quote escaping; paths are absolute and single quotes escaped.
        listing.write_text("".join(f"file '{str(p).replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n" for p in inputs), encoding="utf-8")
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing)]
        command += ["-c:v", video_codec, "-c:a", audio_codec] if reencode else ["-c", "copy"]
        command.append(str(destination))
        subprocess.run(command, check=True)
    return destination


def html_to_video(
    html: str | Path,
    output: str | Path,
    *,
    duration: float = 5,
    fps: int = 30,
    width: int = 1080,
    height: int = 1920,
    start: float = 0,
    ffmpeg_bin: str | None = None,
    chromium_bin: str | None = None,
) -> Path:
    """Record rendered HTML as a video using Chromium screenshots and ffmpeg."""
    import importlib.util
    if importlib.util.find_spec("playwright") is None:
        raise RuntimeError("HTML video needs Playwright: pip install playwright && playwright install chromium")
    from playwright.sync_api import sync_playwright

    if duration <= 0 or fps <= 0 or width <= 0 or height <= 0 or start < 0:
        raise ValueError("duration, fps, width, height must be positive; start must be non-negative")
    source = Path(html).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    destination = Path(output).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = _ffmpeg(ffmpeg_bin)
    with tempfile.TemporaryDirectory(prefix="html-video-") as temp_dir:
        frames = Path(temp_dir) / "frame-%06d.png"
        count = int(duration * fps)
        with sync_playwright() as playwright:
            launch_options = {"headless": True}
            if chromium_bin:
                launch_options["executable_path"] = chromium_bin
            browser = playwright.chromium.launch(**launch_options)
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
            page.goto(source.as_uri(), wait_until="networkidle")
            page.wait_for_timeout(int(start * 1000))
            for frame in range(count):
                page.screenshot(path=str(Path(temp_dir) / f"frame-{frame:06d}.png"))
                if frame + 1 < count:
                    page.wait_for_timeout(max(1, round(1000 / fps)))
            browser.close()
        subprocess.run([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(fps),
            "-i", str(frames), "-frames:v", str(count), "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(destination),
        ], check=True)
    return destination
