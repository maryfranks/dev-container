# =====================================================================
# TOOL MODULE: FZF
# =====================================================================

if ! command -v fzf >/dev/null 2>&1; then
    return 0
fi

export FZF_DEFAULT_OPTS="--height 40% --layout=reverse --border"

if fzf --zsh >/dev/null 2>&1; then
    source <(fzf --zsh)
fi
