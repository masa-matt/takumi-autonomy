#!/usr/bin/env python3
"""gateway.py — Takumi Autonomy Discord Bot

使い方:
  @Takumi <タスクの内容>   メンションでタスクを投入（推奨）
  !task <内容>             プレフィックスでも可
  !metrics                 MOR / PRR / PCR を表示
  !ping                    死活確認

環境変数 (`.env` で設定):
  DISCORD_TOKEN       必須。Bot トークン
  TAKUMI_EXECUTOR     任意。agent-sdk (デフォルト) / claude-code
"""

import asyncio
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
intents.message_content = True  # Privileged Intent: Developer Portal で要有効化

# メンション (@bot ...) でも ! プレフィックスでも反応する
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("!"),
    intents=intents,
)

_EXECUTOR_NAME = os.environ.get("TAKUMI_EXECUTOR", "agent-sdk")
_runner = None
_thread_pool = ThreadPoolExecutor(max_workers=4)


def get_runner():
    global _runner
    if _runner is None:
        _runner = make_runner(_EXECUTOR_NAME)
    return _runner


# ── 共通タスク実行ロジック ─────────────────────────────────────────────────────
async def _run_task(channel, description: str, reply_to=None):
    """description を JobRunner に投げて結果を channel に送る。

    reply_to: discord.Message — 返信先。None なら通常送信。
    """
    log.info("Task received: %r", description[:80])

    # 「処理中」メッセージを先に送る
    processing_text = f"⏳ **Processing…**\n> {description[:120]}"
    if reply_to:
        processing_msg = await reply_to.reply(processing_text)
    else:
        processing_msg = await channel.send(processing_text)

    loop = asyncio.get_event_loop()
    try:
        job, report_path = await loop.run_in_executor(
            _thread_pool,
            lambda: get_runner().run(description),
        )
        embed = build_embed(report_path)
        log.info("Task done: job=%s status=%s", job.job_id, job.status.value)
    except Exception as exc:
        log.exception("JobRunner error for task: %s", description)
        embed = build_error_embed(description, str(exc))

    await processing_msg.edit(content=None, embed=embed)


# ── イベント ──────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    log.info("Bot ready: %s (id=%s)", bot.user, bot.user.id)
    log.info("Executor: %s", _EXECUTOR_NAME)


@bot.event
async def on_message(message: discord.Message):
    """メンション (@bot <内容>) をタスクとして処理する。

    !コマンドは process_commands に委譲する。
    """
    # 自分自身や他の Bot は無視
    if message.author.bot:
        return

    # Bot がメンションされているか確認
    if bot.user in message.mentions:
        # メンション部分を除去してタスク本文を取り出す
        content = message.content
        for mention in (f"<@{bot.user.id}>", f"<@!{bot.user.id}>"):
            content = content.replace(mention, "")
        description = content.strip()

        if not description:
            await message.reply(
                "タスクの内容を書いてください。\n例: `@Takumi ワークスペースのファイル一覧を教えて`"
            )
            return

        # !task などのプレフィックスコマンドと重複処理しないようにスキップ
        ctx = await bot.get_context(message)
        if ctx.valid:
            # 既知のコマンドとして解釈できる場合は process_commands に任せる
            await bot.process_commands(message)
            return

        await _run_task(message.channel, description, reply_to=message)
        return

    # メンションなし → 通常のコマンド処理
    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ タスクの内容を書いてください。\n例: `!task ワークスペースのファイル一覧を教えて`")
    elif isinstance(error, commands.CommandNotFound):
        pass  # 他 bot のコマンドは無視
    else:
        log.error("Command error: %s", error)
        await ctx.send(f"⚠️ エラーが発生しました: {error}")


# ── コマンド ──────────────────────────────────────────────────────────────────
@bot.command(name="task", help="タスクを投入して結果を返す")
async def cmd_task(ctx, *, description: str):
    """!task <description>"""
    await _run_task(ctx.channel, description, reply_to=ctx.message)


@bot.command(name="metrics", help="MOR / PRR / PCR を表示")
async def cmd_metrics(ctx):
    """!metrics"""
    try:
        m = metrics_summary()
        lines = [
            "**Takumi Metrics**",
            "```",
            f"Total jobs    : {m.get('total_jobs', 0)}",
            f"MOR (memory)  : {m.get('MOR', 0):.1%}",
            f"PRR (recall)  : {m.get('PRR', 0):.1%}",
            f"PCR (skill)   : {m.get('PCR', 0):.1%}",
            "```",
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
