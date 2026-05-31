#!/bin/bash

set -e

echo "Running initialization script..."

# pyproject.tomlの存在確認
if [ -f "pyproject.toml" ]; then
    echo "Found pyproject.toml, running uv sync..."
    
    # Pythonのインストール (uvが自動的に適切なバージョンをインストール)
    if ! uv python list | grep -q "installed"; then
        echo "Installing Python via uv..."
        uv python install
    fi
    
    # プロジェクトの依存関係をインストール
    uv sync
    
    echo "Python environment setup complete!"
else
    echo "No pyproject.toml found. Skipping uv sync."
fi

# package.jsonの存在確認
if [ -f "package.json" ]; then
    echo "Found package.json, running pnpm install..."
    pnpm install
    echo "Node.js dependencies installed!"
else
    echo "No package.json found. Skipping pnpm install."
fi

echo "Initialization complete!"