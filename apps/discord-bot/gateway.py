#!/usr/bin/env python3
"""gateway.py — Takumi Autonomy Discord Bot

コマンド一覧:
  !task <内容>    タスクを投入して結果を返す
  !metrics        MOR / PRR / PCR を表示
  !ping           死活確認

環境変数 (`.env` で設定):
  DISCORD_TOKEN       必須。Bot トークン
  TAKUMI_EXECUTOR     任意。agent-sdk (デフォルト) / claude-code
"""

import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import discord
from discord.ext import commands

from report_formatter import build_embed, build_error_embed
from runner_bridge import make_runner, metrics_summary

# ── ロギング ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("takumi-bot")

# ── Bot 設定 ──────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True          # メッセージ本文を読む

bot = commands.Bot(command_prefix="!", intents=intents)

# JobRunner はプロセス単位でシングルトン（スレッドセーフな使い方のみ）
_EXECUTOR_NAME = os.environ.get("TAKUMI_EXECUTOR", "agent-sdk")
_runner = None
_thread_pool = ThreadPoolExecutor(max_workers=4)


def get_runner():
    global _runner
    if _runner is None:
        _runner = make_runner(_EXECUTOR_NAME)
    return _runner


# ── イベント ──────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    log.info("Bot ready: %s (id=%s)", bot.user, bot.user.id)
    log.info("Executor: %s", _EXECUTOR_NAME)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ 引数が足りません。`!task <タスクの内容>` のように使ってください。")
    elif isinstance(error, commands.CommandNotFound):
        pass  # 他 bot のコマンドを無視
    else:
        log.error("Command error: %s", error)
        await ctx.send(f"⚠️ エラーが発生しました: {error}")


# ── コマンド ──────────────────────────────────────────────────────────────────
@bot.command(name="task", help="タスクを投入して結果を返す")
async def cmd_task(ctx, *, description: str):
    """!task <description> — JobRunner にタスクを投入する。"""
    # 即座に「処理中」メッセージを送る
    processing_msg = await ctx.send(
        f"⏳ **Processing…**\n> {description[:120]}"
    )

    loop = asyncio.get_event_loop()
    try:
        # JobRunner は同期処理なので ThreadPoolExecutor 経由で実行
        job, report_path = await loop.run_in_executor(
            _thread_pool,
            lambda: get_runner().run(description),
        )
        embed = build_embed(report_path)

    except Exception as exc:
        log.exception("JobRunner error for task: %s", description)
        embed = build_error_embed(description, str(exc))

    await processing_msg.edit(content=None, embed=embed)


@bot.command(name="metrics", help="MOR / PRR / PCR を表示")
async def cmd_metrics(ctx):
    """!metrics — 累積メトリクスを表示する。"""
    try:
        m = metrics_summary()
        lines = [
            "**Takumi Metrics**",
            f"```",
            f"Total jobs    : {m.get('total_jobs', 0)}",
            f"MOR (memory)  : {m.get('MOR', 0):.1%}",
            f"PRR (recall)  : {m.get('PRR', 0):.1%}",
            f"PCR (skill)   : {m.get('PCR', 0):.1%}",
            f"```",
        ]
        await ctx.send("\n".join(lines))
    except Exception as exc:
        log.exception("metrics error")
        await ctx.send(f"⚠️ メトリクス取得エラー: {exc}")


@bot.command(name="ping", help="死活確認")
async def cmd_ping(ctx):
    await ctx.send(f"🏓 Pong! latency={bot.latency * 1000:.0f}ms")


# ── エントリポイント ───────────────────────────────────────────────────────────
def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN 環境変数が設定されていません")
    log.info("Starting Takumi Autonomy Bot…")
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
