#!/usr/bin/env bash
# Shared shell helpers sourced by bootstrap.sh, scripts/symlinks.sh, and scripts/agents.sh.

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

sync_git_repo() {
    local repo_url="$1" dest_dir="$2"
    if [[ -d "$dest_dir/.git" ]]; then
        if git -C "$dest_dir" pull --ff-only >/dev/null 2>&1; then
            echo "[git]    Updated $dest_dir"
        else
            echo "[warn]   Could not fast-forward pull $dest_dir; continuing with existing checkout." >&2
        fi
        return 0
    fi
    if [[ -e "$dest_dir" || -L "$dest_dir" ]]; then
        if [[ -d "$dest_dir" && -z "$(ls -A "$dest_dir")" ]]; then
            rmdir "$dest_dir"
        else
            echo "Error: Destination '$dest_dir' already exists and is not a git repository for '$repo_url'." >&2
            exit 1
        fi
    fi
    mkdir -p "$(dirname "$dest_dir")"
    git clone "$repo_url" "$dest_dir"
    echo "[git]    Cloned $repo_url -> $dest_dir"
}
