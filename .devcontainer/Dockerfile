FROM debian:bookworm-slim

# 必要な基本パッケージのインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    sudo \
    zsh \
    && rm -rf /var/lib/apt/lists/*

# vscodeユーザーの作成とroot権限付与
RUN groupadd -g 1000 vscode && \
    useradd -m -s /bin/zsh -u 1000 -g vscode vscode && \
    echo "vscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    mkdir -p /home/vscode/.vscode-server && \
    chown -R vscode:vscode /home/vscode

# uvのインストール (vscodeユーザーとして)
USER vscode
WORKDIR /home/vscode
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/home/vscode/.local/bin:$PATH"

# Voltaのインストール
ENV VOLTA_HOME="/home/vscode/.volta"
ENV PATH="$VOLTA_HOME/bin:$PATH"
RUN curl https://get.volta.sh | bash

# Voltaを使用してNode.js LTSのインストール
RUN volta install node@latest

# oh-my-zshのインストール
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended

# claude codeのインストール
RUN curl -fsSL https://claude.ai/install.sh | bash

# ワークスペースディレクトリの設定
WORKDIR /workspace

# デフォルトシェルをzshに設定
ENV SHELL=/bin/zsh