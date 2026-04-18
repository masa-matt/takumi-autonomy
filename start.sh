#!/bin/bash
# Takumi V2 起動スクリプト
# docker compose up + Claude Code 認証同期（macOS Keychain）を一括実行する
set -euo pipefail

cd "$(dirname "$0")"

echo "[start] Docker イメージをビルド中…"
docker compose build

echo "[start] Docker コンテナを起動中…"
docker compose up -d

echo "[start] Claude Code 認証を確認中…"
python3 scripts/sync_claude_auth.py

echo "[start] 起動完了。"
