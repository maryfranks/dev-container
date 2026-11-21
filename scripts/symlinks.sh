#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
CONFIG_PATH="$REPO_DIR/config.toml"
CLI_PROFILE=""
CLI_DOTFILES_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config=*) CONFIG_PATH="${1#*=}"; shift ;;
        --config) [[ $# -ge 2 ]] || { echo "Error: --config requires a value." >&2; exit 1; }; CONFIG_PATH="$2"; shift 2 ;;
        --profile=*) CLI_PROFILE="${1#*=}"; shift ;;
        --profile) [[ $# -ge 2 ]] || { echo "Error: --profile requires a value." >&2; exit 1; }; CLI_PROFILE="$2"; shift 2 ;;
        --dotfiles-dir=*) CLI_DOTFILES_DIR="${1#*=}"; shift ;;
        --dotfiles-dir) [[ $# -ge 2 ]] || { echo "Error: --dotfiles-dir requires a value." >&2; exit 1; }; CLI_DOTFILES_DIR="$2"; shift 2 ;;
        -h|--help) echo "Usage: scripts/symlinks.sh [--config <path>] [--profile <name>] [--dotfiles-dir <path>]"; exit 0 ;;
        *) echo "Error: Unknown argument: $1" >&2; exit 1 ;;
    esac
done

READ_ARGS=(--config "$CONFIG_PATH")
[[ -n "$CLI_PROFILE" ]] && READ_ARGS+=(--profile "$CLI_PROFILE")
config_eval="$(python3 -B "$REPO_DIR/scripts/read-config.py" "${READ_ARGS[@]}")"
eval "$config_eval"

expand_path() {
    case "$1" in
        "~") printf '%s\n' "$HOME" ;;
        "~/"*) printf '%s\n' "$HOME/${1:2}" ;;
        *) printf '%s\n' "$1" ;;
    esac
}

make_backup_path() {
    local stamp candidate counter=1
    stamp="$(date +%Y%m%d%H%M%S)"
    candidate="${1}.bak.${stamp}"
    while [[ -e "$candidate" || -L "$candidate" ]]; do
        candidate="${1}.bak.${stamp}.${counter}"
        counter=$((counter + 1))
    done
    printf '%s\n' "$candidate"
}

EXTERNAL_DOTFILES_DIR=""
if [[ -n "$CLI_DOTFILES_DIR" ]]; then
    EXTERNAL_DOTFILES_DIR="$(expand_path "$CLI_DOTFILES_DIR")"
elif [[ -n "$CFG_DOTFILES_DIR" ]]; then
    EXTERNAL_DOTFILES_DIR="$(expand_path "$CFG_DOTFILES_DIR")"
elif [[ -n "$CFG_DOTFILES_REPO" ]]; then
    EXTERNAL_DOTFILES_DIR="$HOME/.local/share/devcontainer/dotfiles"
fi

# Precedence: external profiles/<name> -> local profiles/<name> -> profiles/default -> shell/
resolve_file() {
    local filename="$1"
    local candidates=()
    [[ -n "$EXTERNAL_DOTFILES_DIR" ]] && candidates+=("$EXTERNAL_DOTFILES_DIR/profiles/$CFG_PROFILE/$filename")
    candidates+=(
        "$REPO_DIR/profiles/$CFG_PROFILE/$filename"
        "$REPO_DIR/profiles/default/$filename"
        "$REPO_DIR/shell/$filename"
    )
    local path
    for path in "${candidates[@]}"; do
        if [[ -f "$path" ]]; then
            printf '%s\n' "$path"
            return 0
        fi
    done
    echo "Error: Could not resolve configuration file '$filename' for profile '$CFG_PROFILE'." >&2
    return 1
}

safe_link_file() {
    local resolved_src dst backup_path
    resolved_src="$(readlink -f "$1")"
    dst="$2"
    mkdir -p "$(dirname "$dst")"

    if [[ -L "$dst" && -e "$dst" && "$(readlink -f "$dst")" == "$resolved_src" ]]; then
        echo "[ok]     $dst -> $resolved_src"
        return 0
    fi
    if [[ -e "$dst" || -L "$dst" ]]; then
        backup_path="$(make_backup_path "$dst")"
        mv "$dst" "$backup_path"
        echo "[backup] $dst -> $backup_path"
    fi
    ln -s "$resolved_src" "$dst"
    echo "[link]   $dst -> $resolved_src"
}

link_profile_file() {
    local src
    src="$(resolve_file "$1")"
    safe_link_file "$src" "$2"
}

link_profile_file "zshrc" "$HOME/.zshrc"
link_profile_file "gitconfig" "$HOME/.gitconfig"
link_profile_file "starship.toml" "$HOME/.config/starship.toml"
link_profile_file "vimrc" "$HOME/.vimrc"
link_profile_file "tmux.conf" "$HOME/.tmux.conf"
