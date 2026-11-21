# =====================================================================
# LANGUAGE MODULE: PYTHON
# =====================================================================

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
    return 0
fi

export PATH="$HOME/.local/bin:$PATH"
export PIP_DISABLE_PIP_VERSION_CHECK=1

if command -v python3 >/dev/null 2>&1; then
    alias py='python3'
fi
