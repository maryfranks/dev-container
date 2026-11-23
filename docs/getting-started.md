# Getting Started

This guide covers configuring `config.toml`, building and publishing the container image, launching in GitHub Codespaces or `prized.dev`, and verifying the installation.

## Prerequisites

* Docker (required to build and push the container image).
* A Dev Containers Command-Line Interface (CLI) runtime: GitHub Codespaces, a `prized.dev` box, or a Linux host with Docker and `@devcontainers/cli` installed.
* Ansible on the controller machine (required only when deploying to remote hosts via `ansible/playbook.yaml`).

## 1. Create and Configure `config.toml`

Copy the template before building or launching:

```bash
cp config.example.toml config.toml
```

`config.toml` is listed in `.gitignore` and `.dockerignore` so personal settings never enter Git history or container image layers.

### Configure `[core]` and Profiles

Edit `[core]` and `[profiles.<name>]` in `config.toml`:

* `[core].username`: Container username (default `"dev"`, must match `^[a-z_][a-z0-9_-]*$`). If changed from `"dev"`, update `"remoteUser"` in `.devcontainer/devcontainer.json` to match.
* `[profiles.<name>]`: Define arbitrary profile names (such as `[profiles.default]`, `[profiles.personal]`, or `[profiles.work]`) with `git_name` and `git_email`.
* `[core].default_profile`: Set to a defined profile name for automatic selection at container creation, or leave as `""` to require `--profile <name>` or `PROFILE=<name>` at runtime.

Profile resolution follows a strict order with no silent fallback:

1. `--profile <name>` passed to `./bootstrap.sh`
2. `PROFILE` environment variable
3. `[core].default_profile` in `config.toml`

If `config.toml` is missing (without `--if-configured`) or no profile resolves, `./bootstrap.sh` exits immediately with an error.

### Configure Sources, Modules, and Agents

* `[sources]`: Leave `dotfiles_repo`, `dotfiles_dir`, and `post_setup_script` blank to use built-in defaults (`shell/`, `profiles/default/`). Set `dotfiles_repo` (or a local `dotfiles_dir`) to bring external dotfiles, and set `post_setup_script` to run a follow-up script after core bootstrap completes.
* `[modules]`: List language and tool loaders under `languages` and `tools` (matching `^[A-Za-z0-9_-]+$`, sourced from `shell/languages/<name>.zsh` and `shell/tools/<name>.zsh`).
* `[agents]`: Set `repo` or `dir` to symlink `target_dir` (default `~/.agents`) to an external shared agent bundle, or leave both blank to initialize a minimal local `~/.agents` directory.
* `[agents.<name>]`: Configure agent CLI slots (such as `[agents.agy]`). Leave `config_repo` and `config_dir` blank to use `agent-configs/`, or set one to point at an external repository/directory. Up to two additional directories (`extra_config_dir_1`, `extra_config_dir_2`) can be mapped alongside `settings` and `config`.
* `[env]`: Define optional non-secret environment variables exported into `~/.config/devcontainer/runtime.zsh`.

## 2. Build and Push the Prebuilt Registry Image

`.devcontainer/devcontainer.json` pulls a prebuilt registry image directly (no `"build"` block is used). Build and push the image from the repository root:

```bash
docker build --build-arg USERNAME=dev -t <dockerhub-user>/devcontainer:latest .
docker push <dockerhub-user>/devcontainer:latest
```

Pass the same `USERNAME` value configured in `[core].username`. Update `"image"` (and `"remoteUser"` if `USERNAME` is not `dev`) in `.devcontainer/devcontainer.json`:

```json
{
  "image": "<dockerhub-user>/devcontainer:latest",
  "remoteUser": "dev"
}
```

## 3. Launch the Dev Container

### Option A: GitHub Codespaces

1. Open the repository in GitHub Codespaces.
2. Grant access to additional repositories if needed by configuring `customizations.codespaces.repositories` in `.devcontainer/devcontainer.json`.
3. Choose one dotfiles mechanism only: do not enable both GitHub Codespaces account-level dotfiles (`Settings -> Codespaces -> Dotfiles`) and `[sources].dotfiles_repo` in `config.toml` at the same time. Both target `$HOME/.zshrc` and `$HOME/.gitconfig`, which causes backup collisions.

### Option B: `prized.dev` or Dev Containers CLI Host (Ansible)

1. Copy the example inventory and configure target hosts:
   ```bash
   cp ansible/inventory/hosts.example.yaml ansible/inventory/hosts.yaml
   ```
   Ensure Secure Shell (SSH) agent forwarding is enabled (`ansible_ssh_common_args: "-o ForwardAgent=yes"`).
2. Update `repo_url` and `image_name` in `ansible/playbook.yaml` (or pass them via `-e`).
3. Optional: Build (and optionally push) the image via Ansible using `[core].username` from `config.toml`:
   ```bash
   ansible-playbook -i ansible/inventory/hosts.yaml ansible/playbook.yaml --tags build -e push_image=true
   ```
4. Sync the repository, copy `config.toml`, and launch the container on target hosts:
   ```bash
   ansible-playbook -i ansible/inventory/hosts.yaml ansible/playbook.yaml
   ```

## 4. Bootstrap Behavior (`--if-configured`) and Re-Applying Changes

`.devcontainer/devcontainer.json` sets `"postCreateCommand": "./bootstrap.sh --if-configured"` with `"waitFor": "postCreateCommand"`:

* When `config.toml` exists, `./bootstrap.sh --if-configured` runs the full bootstrap before attaching.
* When `config.toml` is missing (such as a fresh GitHub Codespaces clone), `--if-configured` prints a setup notice and exits `0` so container creation succeeds. Create `config.toml` and run `./bootstrap.sh` manually inside the container afterward.
* Direct runs (`./bootstrap.sh` without `--if-configured`) fail with exit status `1` if `config.toml` is missing or no profile resolves.
* Because `postCreateCommand` runs only at container creation, re-run `./bootstrap.sh` (or `./bootstrap.sh --profile <name>`) inside the container after editing `config.toml` or updating external repositories.

## 5. Verify the Setup

Run the repository check suite:

```bash
make check
```

`make check` executes:

* `make lint`: Syntax checks via `bash -n`, `zsh -n`, and `python3 -B -m py_compile`.
* `make test`: End-to-end smoke tests via `python3 -B tests/smoke_test.py`.
