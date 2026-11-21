# Built-In Agent Command-Line Interface (CLI) Configurations (`agent-configs/`)

Starter configurations for `agy` (`antigravity-cli/` and `antigravity-config/`).

## Built-In Defaults vs. Bring Your Own (BYO) External Configs

- Built-in mode (`config_repo` and `config_dir` blank in `config.toml`): `scripts/agents.sh` symlinks target CLI directories (such as `~/.gemini/antigravity-cli` and `~/.gemini/config`) directly to `agent-configs/antigravity-cli` and `agent-configs/antigravity-config`.
- External BYO mode (`config_repo` or `config_dir` set in `config.toml`): `scripts/agents.sh` skips `agent-configs/` completely and symlinks target CLI paths directly to the external repository or directory, keeping this repository's `git status` clean.

## Whole-Directory Symlinks

Coding agents routinely write logs, caches, databases, and atomic file updates inside configuration directories at runtime. Individual file symlinks break on atomic renames and leave orphaned files behind, so `scripts/agents.sh` symlinks each target directory as a whole directory.

## Multi-Step `.gitignore` Whitelist

In built-in mode, runtime writes land inside `agent-configs/antigravity-cli/` and `agent-configs/antigravity-config/`. To keep `git status` clean, `agent-configs/.gitignore` ignores everything (`*`), un-ignores the tracked subdirectories so Git descends into them, ignores wildcard contents inside each subdirectory, and whitelists only the starter files (`settings.json`, `skills.json`, `AGENTS.md`).

## Shared Agent Bundle (`~/.agents`)

Cross-agent instructions and skills live in `~/.agents` (configured under `[agents]` in `config.toml`):
- When `[agents].repo` or `[agents].dir` is set, `scripts/agents.sh` symlinks `~/.agents` as a whole directory to the external shared bundle.
- When both are blank, `scripts/agents.sh` initializes `~/.agents` locally with a starter `AGENTS.md` and `skills/` directory if missing.
- `antigravity-config/AGENTS.md` references `@~/.agents/AGENTS.md`, and `antigravity-config/skills.json` points to `~/.agents/skills`.
