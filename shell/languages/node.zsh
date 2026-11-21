# =====================================================================
# LANGUAGE MODULE: NODE / BUN
# =====================================================================

if ! command -v node >/dev/null 2>&1 && ! command -v bun >/dev/null 2>&1; then
    return 0
fi

if [[ -d "$HOME/.bun/bin" ]]; then
    export BUN_INSTALL="$HOME/.bun"
    export PATH="$BUN_INSTALL/bin:$PATH"
fi

if [[ -d "$HOME/.npm-global/bin" ]]; then
    export PATH="$HOME/.npm-global/bin:$PATH"
fi
