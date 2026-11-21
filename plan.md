# Dev Container & BYO Configuration Architecture Plan

## Goals & Scope
- **Portable Public Dev Container Base:** Build a standalone, public dev-container repository (not a GitHub template repository) serving as a modular base for shell and tool environments on Debian `bookworm-slim`.
- **"Bring Your Own" (BYO) Workflow:** Support overriding defaults via external repositories or local directories for user dotfiles, shared agent content (`~/.agents`), and agent CLI configurations—without baking personal state or secrets into container images.
- **Flexible User-Named Profiles:** Support arbitrary user-named profiles (`[profiles.<name>]`) rather than hardcoding `personal` or `work`, while supporting a single default profile when multi-profile switching is unnecessary.
- **Follow-Up Setup Hook:** Support an optional follow-up setup script provided by the user's dotfiles that runs after core bootstrap completes.
- **Portable Runtimes & Clear Boundaries:** Target GitHub Codespaces and `prized.dev` (or any host running the Dev Containers CLI). Secret management/injection and bare/naked VM provisioning are explicitly out of scope for now (future roadmap).

---

## Build vs. Runtime Architecture

### Image Build & Registry Workflow (`Dockerfile`, `.dockerignore` & `devcontainer.json`)
- **Base OS & Python Prerequisite:** Built on Debian `bookworm-slim` with `python3` (3.11+ via `apt`) installed so `scripts/read-config.py` can rely on standard-library `tomllib` without third-party dependencies.
- **Root `Dockerfile` & `.dockerignore` Alignment:** `Dockerfile` and `.dockerignore` both live at the repository root. Users build the image from the repository root (`docker build --build-arg USERNAME=<name> -t <dockerhub-user>/<image>:<tag> .`) and push it to their own Docker Hub (or compatible container registry).
- **Prebuilt Registry Image in `devcontainer.json`:** `.devcontainer/devcontainer.json` pulls the user's published image via `"image": "<dockerhub-user>/<image>:<tag>"` rather than compiling the `Dockerfile` inside the devcontainer runtime (`"build"` is **not** used in `devcontainer.json`).
- **Build Arguments:** `Dockerfile` accepts `USERNAME` (defaulting to `dev`) at `docker build` time (or via Ansible when automating image builds/hosts) to create the non-root container user cleanly. Do **not** accept or bake `PROFILE` at image build time.
- **Build Context Hygiene (`.dockerignore`):** Exclude `config.toml`, `*.local.*`, `.env*`, `.git`, documentation, and caches so personal settings or secrets never enter image layers when building from the repository root.

### Runtime & Bootstrap (`bootstrap.sh` & `scripts/read-config.py`)
- **Lifecycle Trigger (`postCreateCommand`):** `bootstrap.sh` runs at container creation/initialization via `postCreateCommand` in `.devcontainer/devcontainer.json` (with `"waitFor": "postCreateCommand"` when setup must complete before attaching), rather than re-running full repo cloning and symlinking on every container restart.
- **Manual Re-Runs After Edits:** Because `postCreateCommand` only runs on container creation, users re-apply changes after editing `config.toml`, updating modules, or pulling external repos by running `./bootstrap.sh` (or `./bootstrap.sh --profile <name>`) manually inside the container.
- **Strict `config.toml` & Profile Resolution Precedence (No Silent Fallback):**
  0. **Prerequisite (`config.toml`):** `scripts/read-config.py` requires `config.toml` to exist before launching. If `config.toml` is missing, fail immediately with a clear terminal error instructing the user to run `cp config.example.toml config.toml`.
  1. `--profile <name>` CLI flag passed to `bootstrap.sh`
  2. `PROFILE` environment variable
  3. `[core].default_profile` in `config.toml`
  4. If none is set, fail immediately with an explicit error message and usage guidance. (`config.example.toml` leaves `default_profile = ""` so template fallback never silently selects a profile.)
- **Follow-Up Dotfiles Setup Script:** Once base cloning, symlinking, and agent setup complete, if `[sources].post_setup_script` is configured, execute that script from the user's dotfiles (or specified path) as the final bootstrap step.

---

## Symlinking Model & Configuration Layering

### File Symlinks vs. Whole-Directory Symlinks
- **Individual File Symlinks (`zshrc`, `gitconfig`, `starship.toml`, `vimrc`, `tmux.conf`):** Linked individually as files so layered configurations can compose cleanly across shared defaults (`shell/vimrc`, `shell/tmux.conf`, `shell/zshrc`), modular scripts, and profile-specific overrides.
- **Whole-Directory Symlinks (`~/.agents` and agent CLI config directories):** Linked as **entire directories** rather than individual files inside them. Coding agents frequently write, update, or atomically replace files inside their configuration directories at runtime—individual file symlinks break on atomic replacements and leave detached files behind.
- **Path Expansion & Existing Target Safety:** Paths beginning with `~/` expand to `$HOME/`. If a target path already exists and is not already a symlink pointing to the desired source, `symlinks.sh` / `agents.sh` backs it up with a `.bak.<timestamp>` suffix before creating the symlink.
- **Runtime Writes Trade-Off:** Because whole-directory symlinks point directly into a target directory, runtime writes by an agent appear inside that directory's working tree. Keeping runtime state out of tracked Git files (via `.gitignore` whitelisting or gitignored local overrides) preserves clean Git status.

### Profiles & External Dotfiles Resolution
- **Profile Schema (`[profiles.<name>]`):** Profiles are user-named tables in `config.toml` (e.g., `[profiles.default]`, `[profiles.personal]`, `[profiles.work]`, `[profiles.client_a]`) holding profile metadata such as `git_name` and `git_email`. Users who only need a single context can define one profile and set `[core].default_profile`.
- **File Lookup Precedence:** When `[sources].dotfiles_dir` or `[sources].dotfiles_repo` is configured, file symlinks check the external dotfiles directory first for `profiles/<name>/<file>`, falling back to local/built-in `profiles/<name>/<file>`, then `profiles/default/<file>`, and finally shared defaults (`shell/vimrc`, `shell/tmux.conf`) when absent.
- **Shell Startup & Modular Loaders:** `$HOME/.zshrc` links to the resolved `profiles/<name>/zshrc`, which sources `shell/zshrc` (loading only modules listed in `[modules].languages` and `[modules].tools`, each guarded with `command -v` checks so missing binaries never cause startup errors) before applying profile-specific aliases, exports, and overrides.

### Shared Agent Bundle & Built-In vs. BYO Agent Configs
- **Agent-Agnostic Shared Content (`~/.agents`):** Managed under `[agents]` (`AGENTS.md`, `skills/`, `roles/`, `rules/`, `templates/`), symlinked as a whole directory into `target_dir` (default `~/.agents`) from either built-in files or an external repo/path. Agent configurations can reference shared instructions agnostically (e.g., `@~/.agents/AGENTS.md`).
- **Built-In Agent Config Directory (`agent-configs/`):** Houses the repository's out-of-the-box default directories (`antigravity-cli/` and `antigravity-config/`):
  - Used only when `config_repo` and `config_dir` are left blank in `[agents.<name>]`.
  - `agent-configs/.gitignore` handles tracking and ignoring automatically for the built-in starter files (while an external repo's own `.gitignore` governs BYO directories).
- **Opinionated `agy` Default + Multi-Step `.gitignore` Whitelist:**
  - Out of the box, the repository provides starter directories and settings for `agy` (`antigravity-cli/` and `antigravity-config/`, plus support for up to two additional sync directories `extra_config_dir_1` and `extra_config_dir_2`).
  - Because Git does not descend into an ignored parent directory to apply file-level `!` un-ignores, `agent-configs/.gitignore` must explicitly un-ignore the subdirectories, ignore their wildcard contents, and then whitelist specific tracked files:
    ```gitignore
    *
    !.gitignore
    !README.md
    !antigravity-cli/
    !antigravity-config/
    antigravity-cli/*
    antigravity-config/*
    !antigravity-cli/settings.json
    !antigravity-config/skills.json
    !antigravity-config/AGENTS.md
    ```
  - Other agent CLIs (such as Claude or Codex) can map their directories now, with dedicated out-of-the-box presets on the roadmap.
- **External Repo Mounting Rule:** `agents.sh` must **never** modify, replace, or symlink into `agent-configs/` when a user supplies an external `config_repo` or `config_dir`. Instead, `agents.sh` skips `agent-configs/` completely and symlinks the target CLI paths (such as `~/.gemini/antigravity-cli`) directly to the external directory (resolving `settings`, `config`, and `extra_config_dir_*` relative to that external repo/directory), keeping this repository's `git status` clean.

---

## Target Environments, Secrets Boundaries & Roadmap

- **GitHub Codespaces:**
  - Uses GitHub's native authentication and account-level dotfiles preferences (`Settings -> Codespaces -> Dotfiles`).
  - **Dotfiles Collision Rule ("Pick One"):** `README.md` must explicitly warn users not to enable both GitHub Codespaces account-level dotfiles and `[sources].dotfiles_repo` in `config.toml` simultaneously, as both will attempt to symlink `$HOME/.zshrc` and `$HOME/.gitconfig` (causing `.bak.<timestamp>` backups or overwriting one another).
  - Supports multi-repository access in a single codespace via `customizations.codespaces.repositories` in `.devcontainer/devcontainer.json`.
  - Docs: [Managing repository access for your codespaces](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-repository-access-for-your-codespaces) and [Personalizing GitHub Codespaces for your account](https://docs.github.com/en/codespaces/setting-your-user-preferences/personalizing-github-codespaces-for-your-account).
- **`prized.dev` & Dev Containers CLI Hosts:**
  - Works on `prized.dev` boxes and any host with the Dev Containers CLI installed.
  - Multi-host Ansible inventory (`ansible/inventory/hosts.yaml`) supports SSH agent forwarding (`ansible_ssh_common_args: "-o ForwardAgent=yes"`), paired with `SSH_AUTH_SOCK` mount/passthrough in `devcontainer.json` so Git over SSH works without storing private keys inside the container.
  - Docs: [Prized Documentation](https://prized.dev/docs), [Boxes vs. Codespaces / Dev Containers](https://prized.dev/docs/boxes-vs-codespaces-coder-devpod), and [Remote-SSH & Box Setup](https://prized.dev/docs/cursor-remote-ssh).
- **Secrets Exclusion & Roadmap:**
  - This repository **does not** store, manage, or inject secrets.
  - **Roadmap:**
    1. Explicit out-of-the-box config presets for additional coding agents beyond `agy` (e.g., Claude, Codex).
    2. First-class secret-injection patterns (such as 1Password CLI `op`) for runtimes without automatic credential passthrough.
    3. Bare/unprovisioned VM setup in Ansible (installing Docker and the Dev Containers CLI from scratch).

---

## Repository Structure & `export/` Sanitization Rules

### Planned Public Structure
```text
.
├── README.md                      # Usage instructions for built-in agy & BYO agent directories
├── Dockerfile                     # Debian bookworm-slim + python3 (3.11+) + USERNAME (built & pushed to user's Docker Hub)
├── .dockerignore                  # Excludes config.toml, local overrides, secrets, caches (lives at root with Dockerfile)
├── .gitignore                     # Excludes config.toml, *.local.*, .env*
├── .devcontainer/
│   └── devcontainer.json          # image="<dockerhub-user>/<image>:<tag>", postCreateCommand, waitFor, SSH_AUTH_SOCK, Codespaces customizations
├── config.example.toml            # Fully commented config template (default_profile = "")
├── bootstrap.sh                   # Entrypoint: resolves profile, clones/links sources, runs follow-up hook
├── README.md                      # Setup guide, Docker Hub build/push workflow, profiles, symlinks, runtimes, secrets, roadmap
├── ansible/
│   ├── inventory/
│   │   └── hosts.example.yaml     # Multi-host inventory example with ForwardAgent=yes
│   └── playbook.yaml              # Provisioning/sync playbook for Dev Containers CLI hosts
├── scripts/
│   ├── read-config.py             # Stdlib tomllib parser, config.toml existence check & strict profile resolver
│   ├── symlinks.sh                # File symlinking with external dotfiles fallback & .bak backups
│   └── agents.sh                  # Whole-directory symlinking for ~/.agents & built-in vs. BYO agent CLI dirs
├── shell/
│   ├── zshrc                      # Common platform loader + guarded [modules] sourcing
│   ├── tmux.conf                  # Shared default tmux configuration
│   ├── vimrc                      # Shared default vim configuration
│   ├── languages/                 # Modular language loaders (guarded by command -v)
│   └── tools/                     # Modular tool loaders (guarded by command -v)
├── profiles/
│   └── default/
│       ├── zshrc                  # Root $HOME/.zshrc sourcing shell/zshrc + profile overrides
│       ├── gitconfig              # Starter git config
│       └── starship.toml          # Starter prompt config
└── agent-configs/                 # Built-in default agent CLI configurations (untouched when BYO repo is used)
    ├── .gitignore                 # Multi-step default-ignore (*) + subdir un-ignore + file whitelist for agy
    ├── antigravity-cli/
    │   └── settings.json          # Starter agy CLI settings
    └── antigravity-config/
        ├── AGENTS.md              # Starter agent instructions (e.g., @~/.agents/AGENTS.md)
        └── skills.json            # Starter skills manifest
```

### Strict Sanitization & Boundary Rules for Generating `export/`
1. **No Personal or Private Files:** Exclude private directories and personal samples (such as `private/writing-samples.md`, personal SSH keys, tokens, or real internal hostnames).
2. **Placeholder Identities & Endpoints:** Replace real usernames, emails, GitHub handles, and box hostnames with neutral placeholders (`dev`, `you@example.com`, `<owner>/*`, `example-box`).
3. **Config Separation:** Generate `config.example.toml` with full comments and `default_profile = ""`, and ensure no active `config.toml` or `.local` override file is emitted into `export/`.
4. **Whitelist Integrity:** Ensure `agent-configs/.gitignore` only whitelists generic, public starter files (`settings.json`, `skills.json`, `AGENTS.md`) and contains zero references to private folders.
