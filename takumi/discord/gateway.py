#!/usr/bin/env python3
"""takumi.discord.gateway — Takumi Local Autonomy V2 Discord Bot

タスクチャンネル（DISCORD_TASK_CHANNELS）での普通のメッセージ、
または @Takumi メンション / /task コマンドでタスクを受け付ける。

環境変数:
  DISCORD_TOKEN              必須
  DISCORD_TASK_CHANNELS      カンマ区切りのチャンネルID（自然言語チャット用）
  DISCORD_GUILD_ID           スラッシュコマンドの即時反映用（推奨）
  ANTHROPIC_API_KEY          任意（TAKUMI_EXECUTOR=api 時に必要）
  TAKUMI_EXECUTOR            api（デフォルト）/ claude-code
"""

import asyncio
import logging
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

import discord
from discord import app_commands
from discord.ext import commands

from takumi.core.job_state import Job, JobStatus
from takumi.discord.job_runner import run_job, resume_job
from takumi.sandbox.ingress import (
    list_inbox, copy_from_inbox, copy_to_outbox, INBOX_DIR, OUTBOX_DIR
)
from takumi.sandbox.workspace import get_workspace

# ── ロギング ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("takumi-v2")

# ── Bot 設定 ──────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("!"),
    intents=intents,
)

_thread_pool = ThreadPoolExecutor(max_workers=4)

# BLOCKED ジョブを Discord メッセージと紐づけておく辞書
_pending_approvals: dict[str, asyncio.Future] = {}

# 自然言語でタスクを受け付けるチャンネル（DISCORD_TASK_CHANNELS=id1,id2）
_TASK_CHANNEL_IDS: set[int] = set(
    int(cid.strip())
    for cid in os.environ.get("DISCORD_TASK_CHANNELS", "").split(",")
    if cid.strip().isdigit()
)


def _task_slug(task: str, job_id: str) -> str:
    """タスク文字列から人間可読なスラグを生成する（outbox dir / スレッド名用）。"""
    mmdd = job_id[8:12]  # job-20260418-xxx → "0418"
    slug = re.sub(r'[^\w\u3040-\u30ff\u4e00-\u9fff]+', '-', task, flags=re.UNICODE)
    slug = slug.strip('-')[:25]
    return f"{mmdd}-{slug}" if slug else mmdd


# ── 雑談 vs タスクの判定 ──────────────────────────────────────────────────────

_TASK_PATTERNS = re.compile(
    r'作って|作成|つくって|生成|実装|修正|変更|調べ|確認|分析|まとめ|書いて|'
    r'テスト|レビュー|クローン|clone|デバッグ|直して|調査|出力|作る|'
    r'create|make|build|fix|check|analyze|review|write|generate|run|execute',
    re.IGNORECASE,
)


def _is_task(text: str) -> bool:
    """メッセージが作業依頼かどうかをヒューリスティックで判定する。"""
    return bool(_TASK_PATTERNS.search(text))


def _run_chat_reply(text: str) -> str:
    """SOUL.md の人格で雑談に短く返す（ジョブなし・サンドボックスなし）。"""
    from takumi.discord.job_runner import _load_soul
    soul = _load_soul()
    prompt = (
        f"{soul}\n\n"
        "---\n\n"
        "以下のメッセージに、Takumi として自然に短く返してください。\n"
        "Markdown のヘッダーや箇条書きは使わないこと。一言〜二文で返すこと。\n\n"
        f"メッセージ: {text}"
    )
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--dangerously-skip-permissions"],
            capture_output=True, text=True, timeout=30,
        )
        reply = result.stdout.strip()
        # --output-format json なしなので plain text が返る
        if result.returncode == 0 and reply:
            return reply
    except Exception:
        pass
    return "ちょっと調子悪い、後で試して"


# ── ステータス表示 ─────────────────────────────────────────────────────────────

_STATUS_ICON = {
    JobStatus.QUEUED:   "📥",
    JobStatus.RUNNING:  "⚙️",
    JobStatus.BLOCKED:  "🔒",
    JobStatus.DONE:     "✅",
    JobStatus.FAILED:   "❌",
}

_STATUS_COLOR = {
    JobStatus.QUEUED:   discord.Color.light_grey(),
    JobStatus.RUNNING:  discord.Color.blue(),
    JobStatus.BLOCKED:  discord.Color.orange(),
    JobStatus.DONE:     discord.Color.green(),
    JobStatus.FAILED:   discord.Color.red(),
}

_STATUS_TEXT = {
    JobStatus.QUEUED:   "受け取った、少し待って",
    JobStatus.RUNNING:  "作業中...",
    JobStatus.BLOCKED:  "確認が必要",
    JobStatus.DONE:     None,   # result_summary を使う
    JobStatus.FAILED:   None,   # error を使う
}


def _build_embed(job: Job, slug: str | None = None) -> discord.Embed:
    """Embed モード（/task コマンド等）用。"""
    icon  = _STATUS_ICON.get(job.status, "❓")
    color = _STATUS_COLOR.get(job.status, discord.Color.light_grey())
    title = slug or job.job_id

    embed = discord.Embed(
        title=f"{icon} {title}",
        description=job.task[:120],
        color=color,
    )

    if job.block_reason:
        embed.add_field(name="確認事項", value=job.block_reason[:300], inline=False)

    if job.result_summary:
        embed.add_field(name="結果", value=job.result_summary[:1000], inline=False)

    if job.error:
        embed.add_field(name="エラー", value=job.error[:500], inline=False)

    if job.started_at and job.completed_at:
        embed.add_field(name="開始", value=job.started_at[:19].replace("T", " "), inline=True)
        embed.add_field(name="完了", value=job.completed_at[:19].replace("T", " "), inline=True)

    embed.set_footer(text=job.job_id)
    return embed


def _build_chat_text(job: Job) -> str:
    """チャットモード（タスクチャンネル）用のプレーンテキスト。"""
    if job.status == JobStatus.DONE:
        text = job.result_summary or "完了"
        return text
    if job.status == JobStatus.FAILED:
        return f"失敗した。\n> {job.error[:400]}" if job.error else "失敗した。"
    if job.status == JobStatus.BLOCKED:
        return f"確認が必要。\n> {job.block_reason[:300]}" if job.block_reason else "確認が必要。"
    return _STATUS_TEXT.get(job.status, "...")


# ── 承認ボタン View ────────────────────────────────────────────────────────────

class ApprovalView(discord.ui.View):
    def __init__(self, job_id: str, future: asyncio.Future):
        super().__init__(timeout=300)
        self.job_id = job_id
        self.future = future

    @discord.ui.button(label="✅ 承認して実行", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.future.done():
            self.future.get_event_loop().call_soon_threadsafe(self.future.set_result, True)
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="❌ 却下", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.future.done():
            self.future.get_event_loop().call_soon_threadsafe(self.future.set_result, False)
        self.stop()
        await interaction.response.defer()

    async def on_timeout(self):
        if not self.future.done():
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(self.future.set_result, False)


# ── コアタスク処理 ─────────────────────────────────────────────────────────────

async def _run_job(
    status_msg: discord.Message,
    description: str,
    chat_mode: bool = False,
) -> None:
    """タスクを実行して Discord メッセージを更新する（共通処理）。

    chat_mode=True のとき、Embed ではなくプレーンテキストで更新する。
    """
    loop = asyncio.get_event_loop()
    slug_holder: list[str] = []  # job 確定後に slug を格納

    def on_status(job: Job) -> None:
        if not slug_holder:
            slug_holder.append(_task_slug(job.task, job.job_id))
        slug = slug_holder[0]

        if chat_mode:
            text = _build_chat_text(job)
            if job.status == JobStatus.BLOCKED:
                future = loop.create_future()
                _pending_approvals[job.job_id] = future
                view = ApprovalView(job.job_id, future)
                asyncio.run_coroutine_threadsafe(
                    status_msg.edit(content=text, view=view),
                    loop,
                ).result(timeout=10)
            else:
                asyncio.run_coroutine_threadsafe(
                    status_msg.edit(content=text, view=None),
                    loop,
                ).result(timeout=10)
        else:
            embed = _build_embed(job, slug)
            if job.status == JobStatus.BLOCKED:
                future = loop.create_future()
                _pending_approvals[job.job_id] = future
                view = ApprovalView(job.job_id, future)
                asyncio.run_coroutine_threadsafe(
                    status_msg.edit(content=None, embed=embed, view=view),
                    loop,
                ).result(timeout=10)
            else:
                asyncio.run_coroutine_threadsafe(
                    status_msg.edit(content=None, embed=embed, view=None),
                    loop,
                ).result(timeout=10)

    inbox_files = [f.name for f in list_inbox()]

    job: Job = await loop.run_in_executor(
        _thread_pool,
        lambda: run_job(description, on_status=on_status, inbox_files=inbox_files or None),
    )

    if job.status == JobStatus.BLOCKED:
        future = _pending_approvals.get(job.job_id)
        if future:
            try:
                approved = await asyncio.wait_for(asyncio.shield(future), timeout=300)
            except asyncio.TimeoutError:
                approved = False
            finally:
                _pending_approvals.pop(job.job_id, None)

            job = await loop.run_in_executor(
                _thread_pool,
                lambda: resume_job(job, approved=approved, on_status=on_status),
            )

    # 成果物（result.md 以外）があれば自動で outbox に取り出す
    if job.status == JobStatus.DONE:
        ws = get_workspace(job.job_id)
        if ws and ws.output.exists():
            deliverables = [
                f for f in ws.output.iterdir()
                if f.is_file() and f.name != "result.md"
            ]
            if deliverables:
                slug = slug_holder[0] if slug_holder else job.job_id
                copy_to_outbox(ws, slug)
                (OUTBOX_DIR / slug / "result.md").unlink(missing_ok=True)
                log.info("Job %s: %d deliverable(s) → outbox/%s", job.job_id, len(deliverables), slug)

    log.info("Job %s finished: status=%s", job.job_id, job.status.value)


async def _process_thread_message(message: discord.Message, description: str) -> None:
    """タスクチャンネルのスレッド内での会話を継続する。"""
    if not _is_task(description):
        reply = await loop_run(_run_chat_reply, description)
        await message.reply(reply)
        return
    status_msg = await message.reply("受け取った、少し待って")
    await _run_job(status_msg, description, chat_mode=True)


async def _process_task_mention(message: discord.Message, description: str) -> None:
    """@メンション経由のタスク処理。雑談は即返答、作業依頼はジョブ実行。"""
    if not _is_task(description):
        reply = await loop_run(_run_chat_reply, description)
        await message.reply(reply)
        return
    status_msg = await message.reply("受け取った、少し待って")
    await _run_job(status_msg, description, chat_mode=True)


async def _process_task_channel(message: discord.Message, description: str) -> None:
    """タスクチャンネルでの自然言語メッセージ処理。

    常にスレッドを作り、その中で雑談/タスクを処理する。
    """
    slug = re.sub(r'[^\w\u3040-\u30ff\u4e00-\u9fff]+', '-', description, flags=re.UNICODE)
    thread_name = slug.strip('-')[:80] or "chat"
    thread = await message.create_thread(name=thread_name, auto_archive_duration=60)

    if not _is_task(description):
        # 雑談: スレッド内で SOUL 人格として返す
        reply = await loop_run(_run_chat_reply, description)
        await thread.send(reply)
        return

    # 作業依頼: スレッド内でジョブ実行
    status_msg = await thread.send("受け取った、少し待って")
    await _run_job(status_msg, description, chat_mode=True)


async def loop_run(fn, *args):
    """同期関数をスレッドプールで実行する。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_thread_pool, lambda: fn(*args))


async def _process_task_interaction(interaction: discord.Interaction, description: str) -> None:
    """スラッシュコマンド経由のタスク処理。"""
    await interaction.response.defer()
    status_msg = await interaction.followup.send("受け取った、少し待って", wait=True)
    await _run_job(status_msg, description, chat_mode=False)


# ── inbox / outbox 一覧 ────────────────────────────────────────────────────────

def _handle_files_list() -> str:
    inbox = list_inbox()
    inbox_text = (
        "\n".join(f"  • `{f.name}`" for f in inbox)
        if inbox else "  （空）"
    )

    outbox_files: list[str] = []
    if OUTBOX_DIR.exists():
        for job_dir in sorted(OUTBOX_DIR.iterdir(), reverse=True):
            if job_dir.is_dir():
                for f in sorted(job_dir.iterdir()):
                    if f.is_file():
                        outbox_files.append(f"`{job_dir.name}/{f.name}`")
    outbox_text = "\n".join(f"  • {f}" for f in outbox_files) if outbox_files else "  （空）"

    return (
        f"📥 **inbox** ({len(inbox)} files)\n{inbox_text}\n\n"
        f"📤 **outbox**\n{outbox_text}\n\n"
        f"inbox のファイルは次のタスク実行時に自動で渡されます。\n"
        f"成果物ファイルはタスク完了時に自動で outbox に取り出されます。"
    )


# ── Claude Code 認証フロー ──────────────────────────────────────────────────────

async def _ensure_claude_auth() -> None:
    if os.environ.get("TAKUMI_EXECUTOR", "").lower() != "claude-code":
        return

    log.info("Claude Code executor: 認証状態を確認中…")
    result = subprocess.run(
        ["claude", "auth", "status", "--json"],
        capture_output=True, text=True,
    )
    if '"loggedIn": true' in result.stdout:
        log.info("Claude Code: 認証済み")
        return

    log.warning("Claude Code: 未認証または期限切れ。ホストで同期スクリプトを実行してください。")

    channel_id = os.environ.get("DISCORD_AUTH_CHANNEL_ID")
    channel = bot.get_channel(int(channel_id)) if channel_id else None
    if channel is None:
        guild_id = os.environ.get("DISCORD_GUILD_ID")
        if guild_id:
            guild = bot.get_guild(int(guild_id))
            if guild:
                channel = next(
                    (ch for ch in guild.text_channels
                     if ch.permissions_for(guild.me).send_messages),
                    None,
                )
    if channel is None:
        try:
            app_info = await bot.application_info()
            if app_info.owner:
                channel = await app_info.owner.create_dm()
        except Exception:
            pass

    msg = (
        "🔐 **Claude Code の認証が必要です**\n\n"
        "ホスト（Mac）のターミナルで以下を実行してください:\n"
        "```\npython3 scripts/sync_claude_auth.py\n```"
    )
    if channel:
        await channel.send(msg)
        log.info("Discord に認証手順を送信しました。")
    else:
        log.warning("Discord チャンネルが見つかりません:\n%s", msg)


# ── イベント ──────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    guild_id = os.environ.get("DISCORD_GUILD_ID")
    if guild_id:
        guild = discord.Object(id=int(guild_id))
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        log.info("Slash commands synced to guild %s (instant).", guild_id)
    else:
        await bot.tree.sync()
        log.info("Slash commands synced globally (may take up to 1 hour).")

    if _TASK_CHANNEL_IDS:
        log.info("Task channels: %s", _TASK_CHANNEL_IDS)
    else:
        log.info("DISCORD_TASK_CHANNELS not set — using @mention / /task only.")

    log.info("Takumi V2 Bot ready: %s (id=%s)", bot.user, bot.user.id)
    await _ensure_claude_auth()


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # スレッド内のメッセージ
    if isinstance(message.channel, discord.Thread):
        parent_id = message.channel.parent_id
        if _TASK_CHANNEL_IDS and parent_id in _TASK_CHANNEL_IDS:
            description = message.content.strip()
            if description:
                await _process_thread_message(message, description)
            return
        await bot.process_commands(message)
        return

    # タスクチャンネル: 普通のメッセージをタスクとして受け付ける
    if _TASK_CHANNEL_IDS and message.channel.id in _TASK_CHANNEL_IDS:
        ctx = await bot.get_context(message)
        if ctx.valid:
            await bot.process_commands(message)
            return
        description = message.content.strip()
        if description:
            await _process_task_channel(message, description)
        return

    # @メンション
    if bot.user in message.mentions:
        content = message.content
        for mention in (f"<@{bot.user.id}>", f"<@!{bot.user.id}>"):
            content = content.replace(mention, "")
        description = content.strip()
        if not description:
            await message.reply("何かやることある？")
            return
        ctx = await bot.get_context(message)
        if ctx.valid:
            await bot.process_commands(message)
            return
        await _process_task_mention(message, description)
        return

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("タスクの内容を書いて")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        log.error("Command error: %s", error)
        await ctx.send(f"エラー: {error}")


# ── スラッシュコマンド ─────────────────────────────────────────────────────────

@bot.tree.command(name="task", description="タスクを投入して結果を返す")
@app_commands.describe(description="実行したいタスクの内容")
async def slash_task(interaction: discord.Interaction, description: str):
    await _process_task_interaction(interaction, description)


@bot.tree.command(name="status", description="job の現在状態を確認する")
@app_commands.describe(job_id="確認する job の ID（例: job-20260418-xxxxxxxx）")
async def slash_status(interaction: discord.Interaction, job_id: str):
    job = Job.load(job_id)
    if job is None:
        await interaction.response.send_message(f"job が見つからない: `{job_id}`", ephemeral=True)
        return
    await interaction.response.send_message(embed=_build_embed(job))


@bot.tree.command(name="ping", description="死活確認")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"生きてる。latency={bot.latency * 1000:.0f}ms"
    )


@bot.tree.command(name="files", description="inbox / outbox の一覧を表示")
async def slash_files(interaction: discord.Interaction):
    await interaction.response.send_message(_handle_files_list())


# ── エントリポイント ───────────────────────────────────────────────────────────

def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN 環境変数が設定されていません")
    log.info("Starting Takumi Local Autonomy V2 Bot…")
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
