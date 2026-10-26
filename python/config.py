"""Configuration loading and section merging for shared tools."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

TOOLS_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = TOOLS_DIR.parent / "config.json"


def load_config(
    config: Mapping[str, Any] | str | Path | None = None,
    *,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load tool config from a mapping or JSON path."""
    if isinstance(config, Mapping):
        return dict(config)
    path = config_path or (config if isinstance(config, (str, Path)) else None)
    if path is None:
        path = os.environ.get("COMMON_TOOLS_CONFIG")
        if path is None:
            if not DEFAULT_CONFIG_PATH.is_file():
                return {}
            path = DEFAULT_CONFIG_PATH
    config_file = Path(path).expanduser()
    try:
        result = json.loads(config_file.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load tool config {config_file}: {exc}") from exc
    if not isinstance(result, dict):
        raise ValueError(f"Tool config must contain a JSON object: {config_file}")
    result["_config_path"] = str(config_file.resolve())
    return result


def section_config(
    config: Mapping[str, Any] | str | Path | None,
    section: str,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return section settings merged with explicit per-call overrides."""
    root = load_config(config)
    settings = root.get(section, {})
    if not isinstance(settings, Mapping):
        raise ValueError(f"Config section {section!r} must be an object")
    merged = dict(settings)
    if overrides:
        merged.update(overrides)
    merged["_config_path"] = root.get("_config_path")
    return merged
