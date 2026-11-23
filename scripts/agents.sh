#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
CONFIG_PATH="$REPO_DIR/config.toml"
CLI_PROFILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config=*) CONFIG_PATH="${1#*=}"; shift ;;
        --config) [[ $# -ge 2 ]] || { echo "Error: --config requires a value." >&2; exit 1; }; CONFIG_PATH="$2"; shift 2 ;;
        --profile=*) CLI_PROFILE="${1#*=}"; shift ;;
        --profile) [[ $# -ge 2 ]] || { echo "Error: --profile requires a value." >&2; exit 1; }; CLI_PROFILE="$2"; shift 2 ;;
        -h|--help) echo "Usage: scripts/agents.sh [--config <path>] [--profile <name>]"; exit 0 ;;
        *) echo "Error: Unknown argument: $1" >&2; exit 1 ;;
    esac
done

READ_ARGS=(--config "$CONFIG_PATH")
[[ -n "$CLI_PROFILE" ]] && READ_ARGS+=(--profile "$CLI_PROFILE")
config_eval="$(python3 -B "$REPO_DIR/scripts/read-config.py" "${READ_ARGS[@]}")"
eval "$config_eval"

source "$SCRIPT_DIR/lib.sh"

safe_link_dir() {
    local src_dir="$1" dst_dir="$2" resolved_src backup_path
    if [[ ! -d "$src_dir" ]]; then
        echo "Error: Agent source directory does not exist: $src_dir" >&2
        exit 1
    fi
    resolved_src="$(cd "$src_dir" && pwd -P)"
    mkdir -p "$(dirname "$dst_dir")"

    if [[ -L "$dst_dir" && -d "$dst_dir" && "$(cd "$dst_dir" && pwd -P)" == "$resolved_src" ]]; then
        echo "[ok]     $dst_dir -> $resolved_src"
        return 0
    fi
    if [[ -e "$dst_dir" || -L "$dst_dir" ]]; then
        backup_path="$(make_backup_path "$dst_dir")"
        mv "$dst_dir" "$backup_path"
        echo "[backup] $dst_dir -> $backup_path"
    fi
    ln -s "$resolved_src" "$dst_dir"
    echo "[link]   $dst_dir -> $resolved_src"
}

setup_shared_agents_bundle() {
    local target_dir src_dir backup_path
    target_dir="$(expand_path "${CFG_AGENTS_TARGET_DIR:-~/.agents}")"

    if [[ -n "$CFG_AGENTS_REPO" || -n "$CFG_AGENTS_DIR" ]]; then
        src_dir="${CFG_AGENTS_DIR:+$(expand_path "$CFG_AGENTS_DIR")}"
        src_dir="${src_dir:-$HOME/.local/share/devcontainer/agents}"
        [[ -n "$CFG_AGENTS_REPO" ]] && sync_git_repo "$CFG_AGENTS_REPO" "$src_dir"
        safe_link_dir "$src_dir" "$target_dir"
        return 0
    fi

    if [[ -L "$target_dir" || ( -e "$target_dir" && ! -d "$target_dir" ) ]]; then
        backup_path="$(make_backup_path "$target_dir")"
        mv "$target_dir" "$backup_path"
        echo "[backup] $target_dir -> $backup_path"
    fi

    mkdir -p "$target_dir/skills"
    if [[ ! -e "$target_dir/AGENTS.md" ]]; then
        printf '%s\n' \
            "# Shared Agent Instructions" "" \
            "Shared, agent-agnostic guidelines, skills, roles, and rules live in \`~/.agents/\`." \
            "Agent CLI configurations can include this file via \`@~/.agents/AGENTS.md\`." \
            >"$target_dir/AGENTS.md"
        echo "[init]   Created starter $target_dir/AGENTS.md"
    else
        echo "[ok]     $target_dir already initialized"
    fi
}

assert_not_builtin_agent_configs() {
    local agent_name="$1" src_path="$2" builtin_dir="$REPO_DIR/agent-configs"
    [[ -d "$builtin_dir" && -d "$src_path" ]] || return 0
    local canonical_builtin canonical_src
    canonical_builtin="$(cd "$builtin_dir" && pwd -P)"
    canonical_src="$(cd "$src_path" && pwd -P)"
    if [[ "$canonical_src" == "$canonical_builtin" || "$canonical_src" == "$canonical_builtin/"* ]]; then
        echo "Error: [agents.${agent_name}] uses external config_repo/config_dir and must not point into $canonical_builtin." >&2
        exit 1
    fi
}

link_agent_slot() {
    local agent_name="$1" slot_label="$2" raw_src="$3" raw_dst="$4" source_base="$5" is_external="$6"
    [[ -z "$raw_src" && -z "$raw_dst" ]] && return 0
    if [[ -z "$raw_src" || -z "$raw_dst" ]]; then
        echo "Error: [agents.${agent_name}] ${slot_label} requires both source and target paths to be set." >&2
        exit 1
    fi
    local src_path dst_path
    if [[ "$raw_src" == /* || "$raw_src" == "~" || "$raw_src" == "~/"* ]]; then
        src_path="$(expand_path "$raw_src")"
    else
        src_path="${source_base%/}/$raw_src"
    fi
    dst_path="$(expand_path "$raw_dst")"
    [[ "$is_external" == "true" ]] && assert_not_builtin_agent_configs "$agent_name" "$src_path"
    safe_link_dir "$src_path" "$dst_path"
}

setup_agent_clis() {
    local i prefix v_name v_enabled v_repo v_dir name enabled config_repo config_dir is_external source_base
    local slot src_key dst_key label v_src v_dst
    for ((i = 0; i < CFG_AGENT_COUNT; i++)); do
        prefix="CFG_AGENT_${i}"
        v_name="${prefix}_NAME"; v_enabled="${prefix}_ENABLED"
        v_repo="${prefix}_CONFIG_REPO"; v_dir="${prefix}_CONFIG_DIR"
        name="${!v_name}"; enabled="${!v_enabled}"
        config_repo="${!v_repo}"; config_dir="${!v_dir}"

        if [[ "$enabled" != "true" ]]; then
            echo "[skip]   Agent '$name' is disabled"
            continue
        fi

        is_external="false"; source_base="$REPO_DIR"
        if [[ -n "$config_repo" || -n "$config_dir" ]]; then
            is_external="true"
            source_base="${config_dir:+$(expand_path "$config_dir")}"
            source_base="${source_base:-$HOME/.local/share/devcontainer/agent-configs-${name}}"
            [[ -n "$config_repo" ]] && sync_git_repo "$config_repo" "$source_base"
            [[ -d "$source_base" ]] || { echo "Error: External config directory for [agents.${name}] does not exist: $source_base" >&2; exit 1; }
            echo "[byo]    Agent '$name' using external source $source_base (skipping agent-configs/)"
        fi

        for slot in "SETTINGS:TARGET_SETTINGS:settings" "CONFIG:TARGET_CONFIG:config" "EXTRA_1:TARGET_EXTRA_1:extra_config_dir_1" "EXTRA_2:TARGET_EXTRA_2:extra_config_dir_2"; do
            IFS=: read -r src_key dst_key label <<<"$slot"
            v_src="${prefix}_${src_key}"; v_dst="${prefix}_${dst_key}"
            link_agent_slot "$name" "$label" "${!v_src}" "${!v_dst}" "$source_base" "$is_external"
        done
    done
}

setup_shared_agents_bundle
setup_agent_clis
