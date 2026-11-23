# Modular Dev Container Setup

I built this repository because I needed a cloud development container capable of running multi-agent coding workloads off a resource-constrained MacBook Air. My personal setup already lived in a private dotfiles repository, so I sanitized the core engine out of that repo and turned it into a standalone, public dev-container template built on Debian `bookworm-slim` with Python 3.11+ (for standard-library `tomllib`).

It ships with sensible defaults out of the box—arbitrary user-named profiles, guarded modular shell loaders, an optional follow-up setup script, and an external-source workflow for dotfiles and agent Command-Line Interface (CLI) configurations driven by a single gitignored `config.toml`. It targets any runtime that supports the Dev Containers CLI, primarily GitHub Codespaces and `prized.dev`.

## Repository Overview

* `Dockerfile` and `.devcontainer/devcontainer.json`: Base image definition (non-root user, `zsh`, `git`, `gh`, `node`, `python3`, `uv`, `starship`, `fzf`, and Antigravity CLI `agy`) and container runtime configuration pointing to a prebuilt registry image.
* `bootstrap.sh` and `scripts/`: Runtime entrypoint, `config.toml` parser (`scripts/read-config.py`), file-level symlink resolver (`scripts/symlinks.sh`), and directory-level agent configurator (`scripts/agents.sh`).
* `shell/` and `profiles/`: Baseline `zsh`, `git`, `starship`, `vim`, and `tmux` layers, plus guarded language and tool modules (`shell/languages/`, `shell/tools/`).
* `agent-configs/`: Starter `agy` settings (`antigravity-cli/`) protected by a whitelisted `.gitignore`.
* `ansible/`: Playbook and example inventory for building images and launching containers on `prized.dev` or other Dev Containers CLI hosts.

## Quick Start

Getting a container running takes a few steps—mostly copying the template config, choosing a profile strategy, and pointing `.devcontainer/devcontainer.json` at a published image:

1. Copy `config.example.toml` to `config.toml` and define `[profiles.<name>]` entries (plus `[core].default_profile` if automatic selection is desired).
2. Leave `[sources]` and `[agents]` external fields blank to use the built-in defaults, or point them at external dotfiles and agent repositories.
3. Build and push the container image to a registry, then update `"image"` (and `"remoteUser"` if `[core].username` differs from `dev`) in `.devcontainer/devcontainer.json`.
4. Launch in GitHub Codespaces or run `ansible/playbook.yaml` against a `prized.dev` host. On container creation, `postCreateCommand` runs `./bootstrap.sh --if-configured`.
5. Run `make check` inside the repo to verify shell syntax, Python compilation, and smoke tests.

For full setup instructions, profile resolution rules, and `prized.dev` / Codespaces details, see [docs/getting-started.md](docs/getting-started.md).

## Architecture

I kept the build-time image and runtime configuration strictly separated so the same prebuilt container image works across different machines, profiles, and external repositories without baking personal state into image layers.

* **Build-time vs. runtime:** `Dockerfile` installs immutable system tools and creates the user; `bootstrap.sh` runs at container creation to clone external repos, write runtime exports to `~/.config/devcontainer/runtime.zsh`, and wire symlinks.
* **Two symlink models:** Shell and editor configs (`zshrc`, `gitconfig`, `starship.toml`, `vimrc`, `tmux.conf`) link as individual files for layered composition, whereas `~/.agents` and agent CLI directories (such as `~/.gemini/antigravity-cli`) link as whole directories because coding agents write and atomically replace files at runtime. When `[agents.agy].config` is blank, `~/.gemini/config` is created as a real directory with `skills`, `roles`, and `AGENTS.md` symlinked into it from `~/.agents`.
* **External-first precedence:** `scripts/symlinks.sh` checks external dotfiles (`profiles/<name>/` -> `profiles/default/` -> `shell/`) before falling back to this repository's built-in layers. When `config_repo` or `config_dir` is set for an agent, `scripts/agents.sh` skips `agent-configs/` entirely.
* **No built-in secret store:** Credentials stay out of the repo and image; GitHub Codespaces handles GitHub auth natively, and `prized.dev` hosts rely on Secure Shell (SSH) agent forwarding (`SSH_AUTH_SOCK`).

For the full technical specification, symlink precedence rules, and the `agent-configs/` `.gitignore` whitelist, see [docs/architecture.md](docs/architecture.md).

## Roadmap

* **Explicit agent presets:** Out-of-the-box config blocks and defaults for additional coding agents beyond `agy` (such as Claude and Codex), building on the `extra_config_dir_1` and `extra_config_dir_2` slots.
* **Secrets management:** First-class patterns for injecting secrets in standalone environments (such as 1Password CLI `op` with a gitignored env workflow).
* **Bare Virtual Machine (VM) provisioning:** Extending `ansible/playbook.yaml` to install Docker and the Dev Containers CLI from scratch on unprovisioned hosts.
