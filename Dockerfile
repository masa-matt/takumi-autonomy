# Takumi Local Autonomy V2 Bot — Dockerfile
#
# ビルド: docker build -t takumi-bot .
# 実行:   docker compose up -d

FROM python:3.12-slim

WORKDIR /app

# 依存パッケージを先にコピー（レイヤーキャッシュ活用）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# V2 ソースをコピー
COPY takumi/ takumi/
COPY packages/ packages/

# job workspaces と inbox ディレクトリを作成（volume mount のマウントポイント）
RUN mkdir -p takumi/jobs inbox

# V2 Bot 起動
CMD ["python", "-m", "takumi.discord.gateway"]
