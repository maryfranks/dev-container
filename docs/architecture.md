# Architecture Specification

## Build-Time vs. Runtime Separation

The repository separates immutable container image construction from per-user runtime configuration.

### Build-Time (`Dockerfile` and `.dockerignore`)

* Base image: `debian:bookworm-slim` with `ARG USERNAME=dev` and `ARG FZF_VERSION=0.75.0`.
* System packages installed via `apt-get`: `ca-certificates`, `curl`, `git`, `gpg`, `make`, `openssh-client`, `python3`, `python3-venv`, `sudo`, `tmux`, `unzip`, `vim`, `zsh`.
* Toolchains installed globally: `uv` (`/usr/local/bin`), Node.js Long-Term Support (LTS), GitHub Command-Line Interface (CLI) `gh`, Starship (`/usr/local/bin`), and `fzf` (`/usr/local/bin`).
* User setup: Creates non-root `$USERNAME` with `/bin/zsh` and passwordless `sudo`, then installs Antigravity CLI (`agy`) into `$HOME/.local/bin`.
* Build context exclusions (`.dockerignore`): Excludes `.git`, `config.toml`, `*.local.toml`, `.env`, `.env.*` (except `!.env.example`), `agent-configs/local/`, `agent-configs/*/*.local.json`, `profiles/*/gitconfig.local`, `profiles/*/zshrc.local`, `docs/`, `README.md`, `plan.md`, `ansible/`, and `tests/`.

### Prebuilt Registry Image Rationale

* `.devcontainer/devcontainer.json` specifies `"image"` directly without a `"build"` block.
* Prebuilding and pushing the image to a container registry avoids rebuilding Operating System (OS) packages and toolchains on every container creation across GitHub Codespaces and `prized.dev` hosts.
* Decoupling image builds from `.devcontainer/devcontainer.json` keeps personal settings (`config.toml`) and external repositories out of image layers.

### Runtime (`bootstrap.sh` and `scripts/`)

* Entrypoint: `.devcontainer/devcontainer.json` invokes `./bootstrap.sh --if-configured` via `postCreateCommand` with `"waitFor": "postCreateCommand"`.
* `--if-configured` guard: When `config.toml` does not exist and `--if-configured` is set, `bootstrap.sh` prints a notice and exits `0`. Otherwise, `scripts/read-config.py` parses `config.toml` with Python standard-library `tomllib`.
* Validation (`scripts/read-config.py`): Validates `[core].username` against `^[a-z_][a-z0-9_-]*$`, `[modules]` entries against `^[A-Za-z0-9_-]+$`, and `[env]` keys against `^[A-Za-z_][A-Za-z0-9_]*$`. Resolves the active profile strictly in order: `--profile`, `PROFILE` environment variable, `[core].default_profile`.
* Runtime state generation: `bootstrap.sh` writes `DEVCONTAINER_REPO_DIR`, `DEVCONTAINER_PROFILE`, `DEVCONTAINER_DOTFILES_DIR`, `DEVCONTAINER_MODULES_LANGUAGES`, `DEVCONTAINER_MODULES_TOOLS`, and non-empty `[env]` exports to `$HOME/.config/devcontainer/runtime.zsh` outside the repository so `git status` remains clean.
* Git identity: When `git_name` or `git_email` is set on the active profile, `bootstrap.sh` writes `user.name` and `user.email` to `$HOME/.gitconfig.local`.
* Post-setup hook: If `[sources].post_setup_script` is set, `bootstrap.sh` executes it after `scripts/symlinks.sh` and `scripts/agents.sh` complete, resolving relative paths against external dotfiles first, then the repository root.

## Symlink Model: Individual Files vs. Whole Directories

### Individual-File Symlinks (`scripts/symlinks.sh`)

`scripts/symlinks.sh` links five shell, git, prompt, and editor files individually:

* `zshrc` -> `$HOME/.zshrc`
* `gitconfig` -> `$HOME/.gitconfig`
* `starship.toml` -> `$HOME/.config/starship.toml`
* `vimrc` -> `$HOME/.vimrc`
* `tmux.conf` -> `$HOME/.tmux.conf`

Individual-file symlinks enable layered composition. `$HOME/.zshrc` points to the resolved `profiles/<name>/zshrc`, which sources `$HOME/.config/devcontainer/runtime.zsh`, `shell/zshrc`, profile-specific overrides, and `$HOME/.zshrc.local`. `shell/zshrc` loads `[modules].languages` and `[modules].tools` only when `_devcontainer_module_available` confirms the binary exists via `command -v`.

### Whole-Directory Symlinks (`scripts/agents.sh`)

`scripts/agents.sh` links `[agents].target_dir` (default `~/.agents`) and enabled `[agents.<name>]` directories as whole directories rather than individual files.

Coding agents write logs, caches, and databases and perform atomic file replacements inside configuration directories at runtime. Individual-file symlinks break on atomic renames and leave orphaned files behind; directory symlinks route all runtime reads and writes directly to the target directory.

### Backup Safety (`scripts/lib.sh`)

Before creating a file or directory symlink, `scripts/symlinks.sh` and `scripts/agents.sh` check whether the destination already resolves to the expected source. If an existing file, directory, or non-matching symlink occupies the destination, `make_backup_path` moves it to `<target>.bak.<YYYYMMDDHHMMSS>` (appending `.<counter>` on collision) before linking.

## External-First Two-Layer Lookup Precedence

### Dotfiles Resolution (`scripts/symlinks.sh`)

When `[sources].dotfiles_repo` or `[sources].dotfiles_dir` is set, `bootstrap.sh` clones or fast-forward pulls `dotfiles_repo` into `$HOME/.local/share/devcontainer/dotfiles` (or uses `dotfiles_dir` directly).

For each of `{zshrc, gitconfig, starship.toml, vimrc, tmux.conf}`, `resolve_file` selects the first existing file in order:

1. `<external_dotfiles>/profiles/<active_profile>/<file>`
2. `<external_dotfiles>/profiles/default/<file>`
3. `<external_dotfiles>/shell/<file>`
4. `<repo>/profiles/<active_profile>/<file>`
5. `<repo>/profiles/default/<file>`
6. `<repo>/shell/<file>`

Shell module loaders in `shell/zshrc` (`_devcontainer_load_modules`) follow the same external-first rule, checking `${DEVCONTAINER_DOTFILES_DIR}/shell/<kind>/<mod>.zsh` before `${DEVCONTAINER_REPO_DIR}/shell/<kind>/<mod>.zsh`.

### Shared Agent Bundle (`[agents]`)

* External mode (`[agents].repo` or `[agents].dir` set): `scripts/agents.sh` clones/pulls `repo` into `$HOME/.local/share/devcontainer/agents` (unless `dir` overrides the path) and symlinks `target_dir` (default `~/.agents`) as a whole directory to that source.
* Built-in initialization (`repo` and `dir` blank): `scripts/agents.sh` creates `$target_dir/skills` and `$target_dir/roles`, and writes a starter `$target_dir/AGENTS.md` if missing.
* When `[agents.agy].config` is blank and `target_config_dir` (`~/.gemini/config`) is set, `scripts/agents.sh` ensures `target_config_dir` is a real directory (backing up any pre-existing symlink or non-directory) and symlinks `skills`, `roles`, and `AGENTS.md` from `$CFG_AGENTS_TARGET_DIR` (`~/.agents`) into it.

### Agent CLI Configurations (`[agents.<name>]`)

Each `[agents.<name>]` table with `enabled = true` maps up to four directory slots: `settings` -> `target_settings_dir`, `config` -> `target_config_dir`, `extra_config_dir_1` -> `target_extra_dir_1`, and `extra_config_dir_2` -> `target_extra_dir_2`.

* Built-in mode (`config_repo` and `config_dir` blank): Relative slot paths resolve against the repository root (defaulting `settings` to `agent-configs/antigravity-cli` for `agy`, with `config = ""` linking `skills`, `roles`, and `AGENTS.md` from `~/.agents` into `~/.gemini/config`).
* External mode (`config_repo` or `config_dir` set): `scripts/agents.sh` clones/pulls `config_repo` into `$HOME/.local/share/devcontainer/agent-configs-<name>` (unless `config_dir` is set), skips `agent-configs/` completely, and resolves relative slot paths against the external directory. `assert_not_builtin_agent_configs` rejects any path resolving inside `agent-configs/`.

## `agent-configs/` Multi-Step `.gitignore` Whitelist

In built-in mode, runtime writes from `agy` land inside `agent-configs/antigravity-cli/`. To keep `git status` clean while tracking starter files, `agent-configs/.gitignore` applies a four-step whitelist:

```gitignore
*
!.gitignore
!antigravity-cli/
antigravity-cli/*
!antigravity-cli/settings.json
```

1. `*` ignores all entries by default.
2. `!.gitignore` and `!antigravity-cli/` un-ignore `.gitignore` and the target subdirectory so Git descends into it.
3. `antigravity-cli/*` ignores all wildcard contents generated at runtime inside the subdirectory.
4. Explicit negations (`!antigravity-cli/settings.json`) whitelist only the tracked starter file.

## Runtime and Secrets Boundaries

* No built-in secret store: The repository does not store, manage, or inject secrets.
* Local and gitignored files: `config.toml`, `*.local.toml`, `.env`, `.env.*` (except `.env.example`), `agent-configs/*/*.local.json`, `profiles/*/gitconfig.local`, `profiles/*/zshrc.local`, and `ansible/inventory/hosts.yaml` are excluded by `.gitignore` and `.dockerignore`.
* GitHub Codespaces: Handles GitHub authentication and Codespaces secrets natively; `.devcontainer/devcontainer.json` supports `customizations.codespaces.repositories` for multi-repository access.
* `prized.dev` and Dev Containers CLI hosts: `.devcontainer/devcontainer.json` bind-mounts `${localEnv:SSH_AUTH_SOCK:/dev/null}` to `/ssh-agent` and sets `SSH_AUTH_SOCK=/ssh-agent` so Git operations over Secure Shell (SSH) use the forwarded host agent without storing private keys in the container. `ansible/inventory/hosts.example.yaml` enables `ansible_ssh_common_args: "-o ForwardAgent=yes"` for multi-host provisioning.
