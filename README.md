# Modular Dev Container Setup

A standalone, public dev-container repository built on Debian `bookworm-slim` (with Python 3.11+ for standard-library `tomllib`) designed to run anywhere a runtime provides the Dev Containers CLI—primarily **GitHub Codespaces** and **`prized.dev`**.

It includes sensible out-of-the-box defaults, arbitrary user-named profiles (or a single default profile), modular shell loaders, an optional follow-up dotfiles setup script, and a "Bring Your Own" (BYO) workflow for dotfiles and agent configurations via a gitignored `config.toml`.

## Quick Start

> **Important Prerequisite:** Create `config.toml` and configure a profile before running `./bootstrap.sh` directly. Direct runs of `./bootstrap.sh` exit immediately with an error if `config.toml` is missing or no profile is resolved. When `--if-configured` is passed (used by `postCreateCommand` in `.devcontainer/devcontainer.json`), a missing `config.toml` prints a setup notice and exits `0` instead of failing container creation.

1. **Copy the example config before launching:**
   ```bash
   cp config.example.toml config.toml
   ```
   `config.toml` is gitignored (and excluded by `.dockerignore`) so personal settings and local overrides never enter Git or container image layers.

2. **Choose your profile strategy in `config.toml`:**
   * Define any profile names you want under `[profiles.<name>]` (such as `default`, `personal`, `work`, `client_a`, etc.).
   * Set `[core].default_profile = "<name>"` if you want a profile selected automatically at container creation (for example, `default_profile = "default"`).
   * Or leave `[core].default_profile = ""` if you intend to supply the `PROFILE` environment variable at container launch (or pass `--profile <name>` manually).

3. **Configure sources, modules, username, and follow-up scripts in `config.toml`:**
   * Leave external repo/path fields blank to use this repo's built-in defaults (`shell/`, `profiles/default/`, `agent-configs/`).
   * Or configure `[sources]`, `[agents]`, and `[agents.<name>]` to bring your own dotfiles, agent repositories, and optional post-bootstrap setup script.
   * **Customizing the container username:** `[core].username` (default `"dev"`, must match `^[a-z_][a-z0-9_-]*$`) is passed as `--build-arg USERNAME=<name>` during image builds (`docker build` or `ansible/playbook.yaml --tags build`). Update `"remoteUser"` in `.devcontainer/devcontainer.json` to match whenever building with a `USERNAME` other than `dev`.

4. **Build and publish the container image (Docker Hub):**
   ```bash
   docker build --build-arg USERNAME=dev -t <your-dockerhub-user>/devcontainer:latest .
   docker push <your-dockerhub-user>/devcontainer:latest
   ```
   Update `"image": "<your-dockerhub-user>/devcontainer:latest"` (and `"remoteUser"` if `USERNAME` differs from `dev`) in `.devcontainer/devcontainer.json`. `.devcontainer/devcontainer.json` pulls the prebuilt registry image directly (no `"build"` block is used).

5. **Launch in your devcontainer runtime:**
   * Open the repository in **GitHub Codespaces** or run with the Dev Containers CLI on a **`prized.dev`** box (or another host with the Dev Containers CLI installed).
   * `postCreateCommand` runs `./bootstrap.sh --if-configured` automatically on container creation (with `"waitFor": "postCreateCommand"` so setup finishes before attaching). When `config.toml` exists, full bootstrap runs; when `config.toml` is missing (such as a fresh GitHub Codespaces clone), it prints a setup notice and exits `0`.
   * **Re-applying changes later:** Because `postCreateCommand` runs only when a container is created, re-run `./bootstrap.sh` (or `./bootstrap.sh --profile <name>`) manually inside the container whenever you edit `config.toml` or update external repos.

## Profiles: Why Use Them & How They Work

Profiles are not locked to hardcoded names—define whatever profile names match how you work.

### Why Use Multiple Profiles vs. a Single Default
* **Separate Git identities & contexts:** Keep distinct `git_name` and `git_email` values across work, personal projects, open-source contributions, or client engagements.
* **Tailored shell & prompt behavior:** Layer profile-specific `zshrc` overrides, `starship.toml` prompts, or tool/language modules per workflow.
* **Simple single-profile mode:** If you don't need context switching, define `[profiles.default]` and set `[core].default_profile = "default"`.

### Profile Resolution Order (Strict, No Silent Fallback)
1. `--profile <name>` flag passed to `bootstrap.sh`
2. `PROFILE` environment variable
3. `[core].default_profile` in `config.toml`
4. If `config.toml` is missing (without `--if-configured`) or no profile is set, `bootstrap.sh` exits immediately with an explicit error prompting to create `config.toml` and specify a profile.

## How Configs Layer, Symlink & Compose

### 1. Individual File Symlinks vs. Whole-Directory Symlinks
* **Individual file symlinks (`zshrc`, `gitconfig`, `starship.toml`, `vimrc`, `tmux.conf`):**
  Linked as individual files so layered configurations compose cleanly. `$HOME/.zshrc` links to the resolved `profiles/<name>/zshrc`, which sources `shell/zshrc` (loading only enabled `[modules].languages` and `[modules].tools`—each validated against `^[A-Za-z0-9_-]+$` and guarded with `command -v` checks so missing binaries never cause startup errors) before applying profile overrides.
* **Whole-directory symlinks (`~/.agents` and agent CLI config directories):**
  Linked as **entire directories** rather than individual files inside them. Coding agents frequently write, update, or atomically replace files inside their configuration directories at runtime—individual file symlinks break on atomic replacements and leave detached files behind.
* **Backup safety:** If a target path already exists and is not already pointing to the expected source, `symlinks.sh` / `agents.sh` backs it up with a `.bak.<timestamp>` suffix before linking.

### 2. Layering & Resolution Precedence
1. **External dotfiles (`[sources].dotfiles_repo` / `dotfiles_dir`):** Checked first across `profiles/<name>/`, then `profiles/default/`, and finally `shell/` for `{zshrc,gitconfig,starship.toml,vimrc,tmux.conf}`.
2. **Built-in profile & shell defaults:** Falls back to local/built-in `profiles/<name>/`, then `profiles/default/`, and finally shared defaults (`shell/vimrc`, `shell/tmux.conf`).
3. **Shared agent bundle (`[agents]`):** Syncs agent-agnostic content (`AGENTS.md`, `skills/`, `roles/`, `rules/`, `templates/`) to `target_dir` (default `~/.agents`) as a whole-directory symlink when `repo` or `dir` is set. When both `repo` and `dir` are left blank, `agents.sh` initializes `~/.agents` with a minimal starter `AGENTS.md` and `skills/` directory if missing. Agent configs can reference shared instructions agnostically (for example, `@~/.agents/AGENTS.md`).
4. **Agent CLI configurations (`agent-configs/` vs. BYO external repos):**
   * **Built-in defaults (`agent-configs/`):** Houses starter directories (`agent-configs/antigravity-cli/` and `agent-configs/antigravity-config/` for `agy`) used when `config_repo` and `config_dir` are left blank. Uses a multi-step `.gitignore` (default-ignore `*`, explicitly un-ignore target subdirectories, ignore their wildcard contents, and whitelist tracked files) so runtime writes by an agent do not dirty your Git working tree.
   * **BYO external agent configs:** When you supply `config_repo` or `config_dir`, `agents.sh` skips `agent-configs/` completely and symlinks your target CLI paths (such as `~/.gemini/antigravity-cli`) directly to your external repository/directory—keeping this repository's `git status` completely clean.
   * **Relative path rule:** When `config_repo` or `config_dir` is set, `settings`, `config`, `extra_config_dir_1`, and `extra_config_dir_2` are resolved relative to that external repo/directory; when left blank, they are resolved relative to this repository root.
   * **Extra sync directories:** Supports a primary `config` directory plus up to **two extra sync directories** (`extra_config_dir_1` and `extra_config_dir_2`) so tools like Claude or Codex can map their directories now even before dedicated presets are added.
5. **Follow-up dotfiles setup script (`[sources].post_setup_script`):** Runs *after* core cloning, symlinking, and agent setup complete for any personal post-bootstrap tasks.
6. **Local overrides:** Gitignored files (`config.toml`, `*.local.*`, `.env*`) keep machine-specific tweaks out of version control.

## Runtime Environments & Secrets

This repository targets environments with the **Dev Containers CLI** and **does not store, manage, or inject secrets itself**.

### GitHub Codespaces
* **GitHub auth & secrets:** Codespaces handles GitHub authentication and configured Codespaces secrets natively.
* **Dotfiles collision warning ("Pick One"):** Do **not** enable both GitHub Codespaces account-level dotfiles (`Settings -> Codespaces -> Dotfiles`) and `[sources].dotfiles_repo` in `config.toml` at the same time—both will attempt to symlink `$HOME/.zshrc` and `$HOME/.gitconfig`, causing `.bak.<timestamp>` backups or overwriting one another. Pick one mechanism and leave the other unset.
* **Multi-repo access:** Use `customizations.codespaces.repositories` in `.devcontainer/devcontainer.json` (for example, `"<owner>/*": { "permissions": "write-all" }`) to grant access to additional repositories in a single codespace. See [Managing repository access for your codespaces](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-repository-access-for-your-codespaces) and [Personalizing GitHub Codespaces for your account](https://docs.github.com/en/codespaces/setting-your-user-preferences/personalizing-github-codespaces-for-your-account).

### `prized.dev` & Dev Containers CLI Hosts
* **`prized.dev`:** Runs a hosted Linux box with the Dev Containers CLI workflow and SSH agent forwarding. See the [Prized Documentation](https://prized.dev/docs), [Boxes vs. Codespaces / Dev Containers](https://prized.dev/docs/boxes-vs-codespaces-coder-devpod), and [Remote-SSH & Box Setup](https://prized.dev/docs/cursor-remote-ssh).
* **Ansible (`ansible/`):** `ansible/inventory/hosts.example.yaml` supports targeting **multiple hosts** with SSH agent forwarding (`ansible_ssh_common_args: "-o ForwardAgent=yes"`), paired with `ansible/playbook.yaml`. The default play syncs the repository, copies `config.toml`, and runs `devcontainer up` using the prebuilt image; running with `--tags build` reads `[core].username` from `config.toml` and builds the image with `--build-arg USERNAME=...`.
* **SSH agent forwarding into the container:** Mounting `SSH_AUTH_SOCK` into the container in `devcontainer.json` enables Git operations over SSH without storing private keys or tokens inside the image or container.

### What This Repo Does Not Handle (Secrets)
* There is **no built-in secret store or secret-injection mechanism** in this repository.
* Rely on Codespaces secrets/auth, `prized.dev` / SSH agent forwarding, or external tooling for credentials.

## Roadmap

* **Explicit Agent Presets:** Out-of-the-box config blocks and defaults for additional coding agents beyond `agy` (such as Claude and Codex), building on the current `agent-configs/` + two extra sync directory setup.
* **Secrets Management:** First-class patterns/integrations for bringing secrets into containers outside built-in platform auth (such as 1Password CLI `op` with a gitignored env/secrets workflow).
* **Bare / Unprovisioned VM Setup:** Extending Ansible to install Docker and the Dev Containers CLI from scratch on bare VMs that do not already have them.
