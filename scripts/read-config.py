#!/usr/bin/env python3
"""Parse config.toml, resolve the active profile strictly, and emit shell vars."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import sys
import tomllib
from pathlib import Path
from typing import Any

ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
AGENT_FIELDS = (
    ("config_repo", "CONFIG_REPO"),
    ("config_dir", "CONFIG_DIR"),
    ("settings", "SETTINGS"),
    ("config", "CONFIG"),
    ("extra_config_dir_1", "EXTRA_1"),
    ("extra_config_dir_2", "EXTRA_2"),
    ("target_settings_dir", "TARGET_SETTINGS"),
    ("target_config_dir", "TARGET_CONFIG"),
    ("target_extra_dir_1", "TARGET_EXTRA_1"),
    ("target_extra_dir_2", "TARGET_EXTRA_2"),
)


def fail(message: str) -> None:
    """Print an error message to stderr and exit with status 1."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def load_toml(config_path: Path) -> dict[str, Any]:
    """Verify config.toml exists and parse it with standard-library tomllib."""
    if not config_path.is_file():
        fail(
            f"Configuration file not found: {config_path}\n"
            "Run: cp config.example.toml config.toml\n"
            "Then configure [core].default_profile or [profiles.<name>] before bootstrapping."
        )
    try:
        with config_path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        fail(f"Invalid TOML in {config_path}: {exc}")
    if not isinstance(data, dict):
        fail(f"Expected top-level TOML table in {config_path}.")
    return data


def get_table(parent: dict[str, Any], key: str, context: str) -> dict[str, Any]:
    """Return a TOML sub-table, failing cleanly if its type is invalid."""
    value = parent.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        fail(f"Expected [{context}] to be a TOML table.")
    return value


def get_str(table: dict[str, Any], key: str, default: str = "") -> str:
    """Read a scalar string value from a TOML table with whitespace trimmed."""
    value = table.get(key, default)
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        fail(f"Expected scalar string for '{key}', got {type(value).__name__}.")
    return str(value).strip()


def get_str_list(table: dict[str, Any], key: str, context: str) -> list[str]:
    """Read a list of non-empty strings from a TOML table."""
    value = table.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        fail(f"Expected array for [{context}].{key}.")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            fail(f"Expected string items in [{context}].{key}, got {type(item).__name__}.")
        if item.strip():
            items.append(item.strip())
    return items


def resolve_dotted_key(data: dict[str, Any], dotted_key: str) -> str:
    """Resolve a dotted key for --get queries without requiring profile selection."""
    if dotted_key == "core.username":
        return get_str(get_table(data, "core", "core"), "username", "dev") or "dev"
    current: Any = data
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            fail(f"Configuration key '{dotted_key}' not found.")
        current = current[part]
    if isinstance(current, bool):
        return "true" if current else "false"
    if isinstance(current, (dict, list)):
        fail(f"Configuration key '{dotted_key}' is not a scalar value.")
    return str(current).strip()


def resolve_profile(data: dict[str, Any], cli_profile: str | None) -> tuple[str, dict[str, Any]]:
    """Resolve active profile: --profile -> PROFILE env -> [core].default_profile."""
    core = get_table(data, "core", "core")
    profiles = get_table(data, "profiles", "profiles")
    defined = [k for k, v in profiles.items() if isinstance(v, dict)]
    available = ", ".join(defined) if defined else "(none defined)"

    candidate = (
        (cli_profile or "").strip()
        or os.environ.get("PROFILE", "").strip()
        or get_str(core, "default_profile", "")
    )
    if not candidate:
        fail(
            "No active profile resolved.\n"
            "Specify a profile using one of:\n"
            "  1. ./bootstrap.sh --profile <name>\n"
            "  2. PROFILE=<name> ./bootstrap.sh\n"
            '  3. [core].default_profile = "<name>" in config.toml\n'
            f"Defined profiles in config.toml: {available}"
        )
    profile_data = profiles.get(candidate)
    if not isinstance(profile_data, dict):
        fail(f"Profile '{candidate}' is not defined under [profiles.{candidate}].\nDefined profiles in config.toml: {available}")
    return candidate, profile_data


def shell_array(name: str, values: list[str]) -> str:
    """Format a bash array assignment with shlex quoting."""
    return f"{name}=({' '.join(shlex.quote(v) for v in values)})"


def emit_shell(repo_dir: Path, config_path: Path, data: dict[str, Any], cli_profile: str | None) -> None:
    """Validate config sections and print bash-safe variable assignments."""
    profile_name, profile_data = resolve_profile(data, cli_profile)
    core = get_table(data, "core", "core")
    sources = get_table(data, "sources", "sources")
    modules = get_table(data, "modules", "modules")
    agents_root = get_table(data, "agents", "agents")
    env_table = get_table(data, "env", "env")

    env_keys: list[str] = []
    env_vals: list[str] = []
    for key, val in env_table.items():
        if not ENV_KEY_RE.match(key):
            fail(f"Invalid environment variable name in [env]: '{key}'.")
        if isinstance(val, (dict, list)):
            fail(f"Expected scalar value for [env].{key}.")
        env_keys.append(key)
        env_vals.append("" if val is None else str(val))

    lines = [
        f"CFG_REPO_DIR={shlex.quote(str(repo_dir))}",
        f"CFG_CONFIG_PATH={shlex.quote(str(config_path))}",
        f"CFG_PROFILE={shlex.quote(profile_name)}",
        f"CFG_USERNAME={shlex.quote(get_str(core, 'username', 'dev') or 'dev')}",
        f"CFG_GIT_NAME={shlex.quote(get_str(profile_data, 'git_name', ''))}",
        f"CFG_GIT_EMAIL={shlex.quote(get_str(profile_data, 'git_email', ''))}",
        f"CFG_DOTFILES_REPO={shlex.quote(get_str(sources, 'dotfiles_repo', ''))}",
        f"CFG_DOTFILES_DIR={shlex.quote(get_str(sources, 'dotfiles_dir', ''))}",
        f"CFG_POST_SETUP_SCRIPT={shlex.quote(get_str(sources, 'post_setup_script', ''))}",
        shell_array("CFG_MODULES_LANGUAGES", get_str_list(modules, "languages", "modules")),
        shell_array("CFG_MODULES_TOOLS", get_str_list(modules, "tools", "modules")),
        f"CFG_AGENTS_REPO={shlex.quote(get_str(agents_root, 'repo', ''))}",
        f"CFG_AGENTS_DIR={shlex.quote(get_str(agents_root, 'dir', ''))}",
        f"CFG_AGENTS_TARGET_DIR={shlex.quote(get_str(agents_root, 'target_dir', '~/.agents') or '~/.agents')}",
        shell_array("CFG_ENV_KEYS", env_keys),
        shell_array("CFG_ENV_VALS", env_vals),
    ]

    agent_tables = [(k, v) for k, v in agents_root.items() if isinstance(v, dict)]
    lines.append(f"CFG_AGENT_COUNT={len(agent_tables)}")
    for idx, (name, tbl) in enumerate(agent_tables):
        enabled = tbl.get("enabled", True)
        if not isinstance(enabled, bool):
            fail(f"Expected boolean for [agents.{name}].enabled.")
        prefix = f"CFG_AGENT_{idx}"
        lines.append(f"{prefix}_NAME={shlex.quote(name)}")
        lines.append(f"{prefix}_ENABLED={shlex.quote('true' if enabled else 'false')}")
        for toml_key, suffix in AGENT_FIELDS:
            lines.append(f"{prefix}_{suffix}={shlex.quote(get_str(tbl, toml_key, ''))}")

    print("\n".join(lines))


def main() -> None:
    repo_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Read and validate devcontainer config.toml.")
    parser.add_argument("--config", default=str(repo_dir / "config.toml"), help="Path to config.toml.")
    parser.add_argument("--profile", default=None, help="Active profile override.")
    parser.add_argument("--get", dest="get_key", default=None, help="Print a single dotted key.")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    data = load_toml(config_path)
    if args.get_key is not None:
        print(resolve_dotted_key(data, args.get_key))
    else:
        emit_shell(repo_dir, config_path, data, args.profile)


if __name__ == "__main__":
    main()
