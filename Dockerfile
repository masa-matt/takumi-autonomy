# Takumi Autonomy Bot — Dockerfile
#
# ビルド: docker build -t takumi-bot .
# 実行:   docker-compose up -d

FROM python:3.12-slim

WORKDIR /app

# 依存パッケージを先にコピー（レイヤーキャッシュ活用）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ソースをコピー
COPY apps/     apps/
COPY packages/ packages/

# runtime/ は volume mount するためここでは作るだけ
RUN mkdir -p runtime/workspaces/jobs \
             runtime/reports \
             runtime/approvals \
             runtime/memory/entries \
             runtime/memory/skills \
             runtime/logs/claude_code

# Bot 起動
CMD ["python", "apps/discord-bot/gateway.py"]
