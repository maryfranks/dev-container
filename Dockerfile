FROM debian:bookworm-slim

ARG USERNAME=dev
ARG FZF_VERSION=0.75.0

ENV HOME=/home/$USERNAME
ENV SHELL=/bin/zsh
ENV PATH="/home/$USERNAME/.local/bin:/usr/local/bin:${PATH}"

# System essentials, core runtimes, shell utilities, and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    gpg \
    make \
    openssh-client \
    python3 \
    python3-venv \
    sudo \
    tmux \
    unzip \
    vim \
    wget \
    zsh \
    && rm -rf /var/lib/apt/lists/*

# Install uv globally into /usr/local/bin
ENV UV_INSTALL_DIR="/usr/local/bin"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Node.js LTS
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI (gh)
RUN mkdir -p -m 755 /etc/apt/keyrings \
    && out=$(mktemp) && wget -nv -O "$out" https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    && cat "$out" | tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
    && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && mkdir -p -m 755 /etc/apt/sources.list.d \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/* "$out"

# Install Starship prompt globally into /usr/local/bin
RUN curl -fsSL https://starship.rs/install.sh | sh -s -- --yes --bin-dir /usr/local/bin

# Install fzf binary (supports fzf --zsh)
RUN ARCH=$(dpkg --print-architecture) \
    && curl -fsSL "https://github.com/junegunn/fzf/releases/download/v${FZF_VERSION}/fzf-${FZF_VERSION}-linux_${ARCH}.tar.gz" \
    | tar -xz -C /usr/local/bin fzf

# Create non-root user with zsh and passwordless sudo
RUN useradd -m -s /bin/zsh "$USERNAME" \
    && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$USERNAME" \
    && chmod 0440 "/etc/sudoers.d/$USERNAME"

USER $USERNAME
WORKDIR $HOME

# Install Antigravity CLI (agy) into user local bin
RUN mkdir -p "$HOME/.local/bin" \
    && curl -fsSL https://antigravity.google/cli/install.sh | bash

CMD ["zsh"]
