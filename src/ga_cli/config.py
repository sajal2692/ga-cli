from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import click

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "ga-cli" / "config.toml"


@dataclass
class Config:
    path: Path
    default_property: str | None = None
    credentials: str | None = None
    aliases: dict[str, str] = field(default_factory=dict)


def config_path(flag_value: str | None) -> Path:
    if flag_value:
        return Path(flag_value).expanduser()
    env = os.environ.get("GA_CONFIG")
    if env:
        return Path(env).expanduser()
    return DEFAULT_CONFIG_PATH


def load(flag_value: str | None) -> Config:
    path = config_path(flag_value)
    if not path.is_file():
        return Config(path=path)
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise click.UsageError(f"Invalid config file {path}: {exc}") from exc
    aliases = data.get("properties", {})
    if not isinstance(aliases, dict):
        raise click.UsageError(f"Invalid [properties] section in {path}: expected a table.")
    return Config(
        path=path,
        default_property=data.get("default_property"),
        credentials=data.get("credentials"),
        aliases={str(k): str(v) for k, v in aliases.items()},
    )


def for_ctx(ctx: click.Context) -> Config:
    obj = ctx.obj
    if "_config" not in obj:
        obj["_config"] = load(obj.get("config_flag"))
    cfg: Config = obj["_config"]
    return cfg
