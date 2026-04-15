# Takumi Local Autonomy V2 Bot — Dockerfile
#
# ビルド: docker compose up -d --build
# 実行:   docker compose up -d

FROM python:3.12-slim

WORKDIR /app

# Node.js 20 + Claude Code CLI をインストール
# TAKUMI_EXECUTOR=claude-code 使用時に必要
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Python 依存パッケージ（レイヤーキャッシュ活用のため先にコピー）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# V2 ソースをコピー
COPY takumi/ takumi/
COPY packages/ packages/

# job workspaces と inbox ディレクトリを作成（volume mount のマウントポイント）
RUN mkdir -p takumi/jobs inbox

# V2 Bot 起動
CMD ["python", "-m", "takumi.discord.gateway"]
