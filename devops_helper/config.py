"""Config loading: .devops-helper.yaml + env var overrides."""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ServerConfig:
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class Config:
    gemini_api_key: str
    gemini_model: str
    mcp_servers: dict[str, ServerConfig]
    destructive_patterns: list[str]


def _expand_env(value: str) -> str:
    """Expand ${VAR} references from environment."""
    import re

    def replace(m: re.Match) -> str:
        return os.environ.get(m.group(1), m.group(0))

    return re.sub(r"\$\{([^}]+)\}", replace, value)


def _expand_server_env(raw_env: dict[str, str]) -> dict[str, str]:
    return {k: _expand_env(v) for k, v in raw_env.items()}


def _find_config_file() -> Path | None:
    for candidate in [Path(".devops-helper.yaml"), Path.home() / ".devops-helper.yaml"]:
        if candidate.exists():
            return candidate
    return None


def load_config() -> Config:
    raw: dict[str, Any] = {}
    config_file = _find_config_file()
    if config_file:
        with config_file.open() as f:
            raw = yaml.safe_load(f) or {}

    gemini_api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    gemini_model = os.environ.get("GEMINI_MODEL") or raw.get("gemini_model", "gemini-2.5-flash")

    servers: dict[str, ServerConfig] = {}
    for name, cfg in (raw.get("mcp_servers") or {}).items():
        servers[name] = ServerConfig(
            command=cfg["command"],
            args=cfg.get("args", []),
            env=_expand_server_env(cfg.get("env", {})),
        )

    default_patterns = [
        "delete_*", "stop_*", "terminate_*", "scale_*", "restart_*",
        "sync_*", "trigger_*", "create_*", "update_*", "apply_*", "destroy_*",
        "*_delete", "*_stop", "*_terminate", "*_scale", "*_restart",
        "*_sync", "*_trigger", "*_create", "*_update", "*_apply", "*_destroy",
    ]
    patterns: list[str] = raw.get("destructive_patterns", default_patterns)

    return Config(
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        mcp_servers=servers,
        destructive_patterns=patterns,
    )


def is_destructive(tool_name: str, patterns: list[str]) -> bool:
    lower = tool_name.lower()
    return any(fnmatch.fnmatch(lower, p.lower()) for p in patterns)
