# =====================================================================
# TOOL MODULE: UV
# =====================================================================

if ! command -v uv >/dev/null 2>&1; then
    return 0
fi

export PATH="$HOME/.local/bin:$PATH"

if uv generate-shell-completion zsh >/dev/null 2>&1; then
    eval "$(uv generate-shell-completion zsh)"
fi
