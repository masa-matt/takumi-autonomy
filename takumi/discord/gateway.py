#!/usr/bin/env python3
"""takumi.discord.gateway — Takumi Local Autonomy V2 Discord Bot

コマンド:
  /task <description>   タスクを投入（スラッシュコマンド、推奨）
  /status <job_id>      job の現在状態を確認
  /ping                 死活確認
  /files [filename]     inbox 一覧 / 次のタスクにファイルを添付
  @Takumi <タスク>      メンションでもタスク投入可

環境変数:
  DISCORD_TOKEN     必須
  ANTHROPIC_API_KEY 任意（TAKUMI_EXECUTOR=api 時に必要）
  TAKUMI_EXECUTOR   api（デフォルト）/ claude-code
"""

import asyncio
import logging
import os
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
from takumi.sandbox.workspace import get_workspace, Workspace, JOBS_DIR

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
# {job_id: asyncio.Future}  — Future が resolve されると承認/却下が伝わる
_pending_approvals: dict[str, asyncio.Future] = {}


# ── Embed ヘルパー ─────────────────────────────────────────────────────────────

_STATUS_ICON = {
    JobStatus.QUEUED:   "📥",
    JobStatus.RUNNING:  "🔄",
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


def _build_embed(job: Job) -> discord.Embed:
    icon  = _STATUS_ICON.get(job.status, "❓")
    color = _STATUS_COLOR.get(job.status, discord.Color.light_grey())

    embed = discord.Embed(
        title=f"{icon} {job.job_id}",
        description=f"**Task:** {job.task[:120]}",
        color=color,
    )
    embed.add_field(name="Status", value=job.status.value, inline=True)

    if job.block_reason:
        embed.add_field(name="Block reason", value=job.block_reason[:300], inline=False)

    if job.result_summary:
        embed.add_field(name="Result", value=job.result_summary[:1000], inline=False)

    if job.error:
        embed.add_field(name="Error", value=job.error[:500], inline=False)

    if job.started_at and job.completed_at:
        embed.add_field(name="Started",   value=job.started_at[:19].replace("T", " "), inline=True)
        embed.add_field(name="Completed", value=job.completed_at[:19].replace("T", " "), inline=True)

    embed.set_footer(text=job.job_id)
    return embed


# ── 承認ボタン View ────────────────────────────────────────────────────────────

class ApprovalView(discord.ui.View):
    """BLOCKED ジョブへの承認 / 却下ボタン。"""

    def __init__(self, job_id: str, future: asyncio.Future):
        super().__init__(timeout=300)  # 5 分で自動タイムアウト
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
    channel_id: int,
    description: str,
) -> None:
    """タスクを実行して Discord メッセージを更新する（共通処理）。

    メッセージ送信後の処理をまとめたヘルパー。
    _process_task（mention）と _process_task_interaction（slash）の両方から呼ばれる。
    """
    loop = asyncio.get_event_loop()

    def on_status(job: Job) -> None:
        embed = _build_embed(job)
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

    # inbox の全ファイルを自動で渡す（明示的予約不要）
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

    log.info("Job %s finished: status=%s", job.job_id, job.status.value)


async def _process_task(message: discord.Message, description: str) -> None:
    """メンション経由のタスク処理。"""
    status_msg = await message.reply(f"📥 **Queued…**\n> {description[:120]}")
    await _run_job(status_msg, message.channel.id, description)


async def _process_task_interaction(interaction: discord.Interaction, description: str) -> None:
    """スラッシュコマンド経由のタスク処理。"""
    await interaction.response.defer()
    status_msg = await interaction.followup.send(
        f"📥 **Queued…**\n> {description[:120]}", wait=True
    )
    channel_id = interaction.channel_id or 0
    await _run_job(status_msg, channel_id, description)


# ── inbox ヘルパー（共通）─────────────────────────────────────────────────────

def _handle_files_list() -> str:
    """inbox / outbox の一覧テキストを返す。"""
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
        f"inbox のファイルは次の `/task` 実行時に自動で渡されます。\n"
        f"成果物を取り出すには `/fetch <job_id>` を使ってください。"
    )


def _handle_fetch(job_id: str) -> str:
    """job の output/ を outbox に取り出す。result.md は除外。"""
    ws = get_workspace(job_id)
    if ws is None:
        # job_id が job- で始まらない場合など部分一致で探す
        if JOBS_DIR.exists():
            matches = [d for d in JOBS_DIR.iterdir() if d.is_dir() and job_id in d.name]
            if len(matches) == 1:
                ws = Workspace(matches[0])
            elif len(matches) > 1:
                names = ", ".join(d.name for d in matches[:5])
                return f"❓ 複数の job が見つかりました: {names}\nフルの job_id を指定してください。"
        if ws is None:
            return f"❓ job が見つかりません: `{job_id}`"

    if not ws.output.exists():
        return f"📭 `{job_id}` の output/ は空です。"

    # result.md（作業サマリー）は除外して成果物のみコピー
    deliverables = [
        f for f in ws.output.iterdir()
        if f.is_file() and f.name != "result.md"
    ]

    if not deliverables:
        return f"📭 `{job_id}` に成果物ファイルがありません（result.md のみ）。"

    copied = copy_to_outbox(ws, job_id)
    # result.md を outbox から除去
    outbox_job_dir = OUTBOX_DIR / job_id
    result_md = outbox_job_dir / "result.md"
    if result_md.exists():
        result_md.unlink()

    names = "\n".join(f"  • `{f.name}`" for f in deliverables)
    return f"📤 **{job_id}** の成果物を outbox に取り出しました:\n{names}"


# ── Claude Code 認証フロー ──────────────────────────────────────────────────────


async def _ensure_claude_auth() -> None:
    """Claude Code executor の認証状態を確認し、未認証・期限切れなら Discord に通知する。

    認証情報はホスト側の scripts/sync_claude_auth.py（または start.sh）が
    macOS Keychain から取得してコンテナへコピーする。
    コンテナ側は認証状態を確認するのみ。
    """
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
        "```\npython3 scripts/sync_claude_auth.py\n```\n"
        "macOS のキーチェーンアクセスダイアログが表示されます。\n"
        "パスワードを入力すると認証情報がコンテナへ自動コピーされます。\n\n"
        "次回からは `./start.sh` で起動すると自動的に同期されます。"
    )
    if channel:
        await channel.send(msg)
        log.info("Discord に認証手順を送信しました。")
    else:
        log.warning("Discord チャンネルが見つかりません:\n%s", msg)


# ── イベント ──────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    # スラッシュコマンド sync
    guild_id = os.environ.get("DISCORD_GUILD_ID")
    if guild_id:
        guild = discord.Object(id=int(guild_id))
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        log.info("Slash commands synced to guild %s (instant).", guild_id)
    else:
        await bot.tree.sync()
        log.info("Slash commands synced globally (may take up to 1 hour).")

    log.info("Takumi V2 Bot ready: %s (id=%s)", bot.user, bot.user.id)

    # Claude Code 認証確認（claude-code モード時のみ）
    await _ensure_claude_auth()


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if bot.user in message.mentions:
        content = message.content
        for mention in (f"<@{bot.user.id}>", f"<@!{bot.user.id}>"):
            content = content.replace(mention, "")
        description = content.strip()

        if not description:
            await message.reply(
                "タスクの内容を書いてください。\n例: `@Takumi この repo の failing test を調べて`"
            )
            return

        ctx = await bot.get_context(message)
        if ctx.valid:
            await bot.process_commands(message)
            return

        await _process_task(message, description)
        return

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ タスクの内容が必要です。例: `/task description:この repo を調べて`")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        log.error("Command error: %s", error)
        await ctx.send(f"⚠️ エラー: {error}")


# ── スラッシュコマンド ─────────────────────────────────────────────────────────

@bot.tree.command(name="task", description="タスクを投入して結果を返す")
@app_commands.describe(description="実行したいタスクの内容")
async def slash_task(interaction: discord.Interaction, description: str):
    await _process_task_interaction(interaction, description)


@bot.tree.command(name="status", description="job の現在状態を確認する")
@app_commands.describe(job_id="確認する job の ID（例: job-20260415-xxxxxxxx）")
async def slash_status(interaction: discord.Interaction, job_id: str):
    job = Job.load(job_id)
    if job is None:
        await interaction.response.send_message(
            f"❓ job が見つかりません: `{job_id}`", ephemeral=True
        )
        return
    await interaction.response.send_message(embed=_build_embed(job))


@bot.tree.command(name="ping", description="死活確認")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"🏓 Pong! latency={bot.latency * 1000:.0f}ms  (Takumi V2)"
    )


@bot.tree.command(name="files", description="inbox / outbox の一覧を表示")
async def slash_files(interaction: discord.Interaction):
    await interaction.response.send_message(_handle_files_list())


@bot.tree.command(name="fetch", description="job の成果物を outbox に取り出す")
@app_commands.describe(job_id="取り出す job の ID（例: job-20260418-xxxxxxxx）")
async def slash_fetch(interaction: discord.Interaction, job_id: str):
    await interaction.response.send_message(_handle_fetch(job_id))


# ── エントリポイント ───────────────────────────────────────────────────────────

def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN 環境変数が設定されていません")
    log.info("Starting Takumi Local Autonomy V2 Bot…")
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
