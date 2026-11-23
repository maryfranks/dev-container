# Modular Dev Container Setup

I built this because I wanted to learn to work with coding agents but my aging MacBook Air didn't have enough resources. I started in a GitHub codespace for my first project repo and quickly realized that reconfiguring the agents for every project was a huge pain. I built out the container in a private dotfiles repo where it had easy access to all of my config. After testing it in a few codespace environments and a port over to prized.dev, I pulled the core setup out into a standalone, public dev-container template built on Debian `bookworm-slim` with Python 3.11+ (for standard-library `tomllib`).

Everything is controlled from a single gitignored `config.toml`. It comes with working defaults right away, allows custom profiles, toggles shell tools that only load when they are actually installed, and can run a follow-up setup script or pull in dotfiles and agent Command-Line Interface (CLI) configs from other repos. It works anywhere the Dev Containers CLI runs and the symlinks sync all config changes back to the repo without requiring any container rebuilds. It currently installs the tools that I use (Python, Node, Google Antigravity) but the modular structure is easily configurable for any setup.

## Repository Overview

* `Dockerfile` and `.devcontainer/devcontainer.json`: Base image (non-root user, `zsh`, `git`, `gh`, `node`, `python3`, `uv`, `starship`, `fzf`, and Antigravity CLI `agy`) and container config pointing to a prebuilt image.
* `bootstrap.sh` and `scripts/`: Startup script, `config.toml` parser (`scripts/read-config.py`), dotfile symlinker (`scripts/symlinks.sh`), and agent directory symlinker (`scripts/agents.sh`).
* `shell/` and `profiles/`: Baseline `zsh`, `git`, `starship`, `vim`, and `tmux` configs, plus optional language and tool modules (`shell/languages/`, `shell/tools/`).
* `agent-configs/`: Starter `agy` settings (`antigravity-cli/`) with a `.gitignore` that only tracks the starter files.
* `ansible/`: Playbook and example inventory for building images and launching containers on `prized.dev` or other Dev Containers CLI hosts.

## Quick Start

The container setup is just a few steps:

1. Copy `config.example.toml` to `config.toml` and add `[profiles.<name>]` entries (plus `[core].default_profile` to select one automatically).
2. Leave the external fields in `[sources]` and `[agents]` blank to use the built-in defaults, or point them at external dotfiles and agent repositories.
3. Build and push the container image to a registry, then update `"image"` (and `"remoteUser"` if `[core].username` is not `dev`) in `.devcontainer/devcontainer.json`.
4. Launch in GitHub Codespaces or run `ansible/playbook.yaml` against a `prized.dev` host. When the container is created, `postCreateCommand` runs `./bootstrap.sh --if-configured`.
5. Run `make check` inside the repo to check shell syntax, Python compilation, and smoke tests.

For full setup instructions, profile fallback order, and `prized.dev` / Codespaces notes, see [docs/getting-started.md](docs/getting-started.md).

## Architecture

I kept the build-time image and runtime config separate so the same prebuilt image works across different machines, profiles, and external repositories without baking personal settings into the image. It also allows config changes without a full container or Virtual Machine (VM) rebuild.

* Build-time vs. runtime: `Dockerfile` installs system tools and creates the user; `bootstrap.sh` runs at container creation to clone external repos, write runtime exports to `~/.config/devcontainer/runtime.zsh`, and set up symlinks.
* Two symlink models: Shell and editor configs (`zshrc`, `gitconfig`, `starship.toml`, `vimrc`, `tmux.conf`) link as individual files so layers can override each other. By contrast, `~/.agents` and agent CLI directories (like `~/.gemini/antigravity-cli`) link as whole directories because coding agents rewrite files on the fly (which breaks individual file symlinks). When `[agents.agy].config` is blank, `~/.gemini/config` is created as a real directory with `skills`, `roles`, and `AGENTS.md` symlinked into it from `~/.agents`.
* External configs come first: `scripts/symlinks.sh` checks external dotfiles (`profiles/<name>/` -> `profiles/default/` -> `shell/`) before falling back to this repo's built-in files. When `config_repo` or `config_dir` is set for an agent, `scripts/agents.sh` skips `agent-configs/` completely.
* No built-in secret store: Credentials stay out of the repo and image; GitHub Codespaces handles GitHub auth natively, and `prized.dev` hosts rely on Secure Shell (SSH) agent forwarding (`SSH_AUTH_SOCK`).

For the full technical spec, symlink precedence rules, and the `agent-configs/` `.gitignore` setup, see [docs/architecture.md](docs/architecture.md).

## Roadmap

The goal is a fully portable dev container setup that runs anywhere with any combination of dev tooling.

* Explicit agent presets: Built-in config blocks and defaults for more coding agents beyond `agy` (like Claude and Codex), using the `extra_config_dir_1` and `extra_config_dir_2` slots.
* Secrets management: A clean way to pass secrets into standalone containers (like 1Password CLI `op` with a gitignored env file). Currently all secret management is handled by the platform providers: GitHub and prized.dev.
* Bare VM provisioning: Extending `ansible/playbook.yaml` to install Docker and the Dev Containers CLI from scratch on fresh hosts.
* A better way to manage tool configs.

## A note on AI usage in this project

I used an agent to extract and sanitize the configs for this repo. It's a simplified version of the way I organize my environment and once it was standalone, I had to make some changes for it to work. I also incorporated some learnings from the fresh container in prized.dev. I generated the first draft of the documentation with agents, but even though I asked it twice to use less jargon and a more approachable tone, the "plainspoken voice" (which is how agent described it) was terrible. It writes a great, very technically precise architecture document, but the README I still mostly writes by hand.
