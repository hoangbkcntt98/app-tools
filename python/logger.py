"""Configurable standard-library logger for shared tools."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping

from .config import section_config


def get_logger(
    name: str,
    config: Mapping[str, Any] | str | Path | None = None,
    *,
    settings: Mapping[str, Any] | None = None,
) -> logging.Logger:
    """Get a logger with optional configured file and console handlers."""
    options = dict(settings or section_config(config, "logger"))
    logger = logging.getLogger(name)
    level = str(options.get("level", "INFO")).upper()
    resolved_level = logging.getLevelName(level)
    if not isinstance(resolved_level, int):
        raise ValueError(f"Invalid logger level: {level}")
    logger.setLevel(resolved_level)
    logger.propagate = bool(options.get("propagate", False))
    formatter = logging.Formatter(
        str(options.get("format", "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    )

    if options.get("console", False) and not any(
        getattr(handler, "_common_tools_console", False)
        for handler in logger.handlers
    ):
        handler = logging.StreamHandler()
        handler._common_tools_console = True
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    log_file = options.get("file")
    if log_file:
        path = Path(str(log_file)).expanduser()
        config_path = options.get("_config_path")
        if not path.is_absolute() and config_path:
            path = Path(str(config_path)).parent / path
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = path.resolve()
        if not any(
            getattr(handler, "_common_tools_file", None) == str(normalized)
            for handler in logger.handlers
        ):
            handler = logging.FileHandler(normalized, encoding="utf-8")
            handler._common_tools_file = str(normalized)
            handler.setFormatter(formatter)
            logger.addHandler(handler)
    return logger


def log(
    message: str,
    *,
    name: str = "tools",
    level: str = "INFO",
    config: Mapping[str, Any] | str | Path | None = None,
) -> None:
    """Write one message using logger settings from config."""
    logger = get_logger(name, config)
    method = getattr(logger, str(level).lower(), None)
    if not callable(method) or str(level).upper() not in logging._nameToLevel:
        raise ValueError(f"Invalid logger level: {level}")
    method(message)
