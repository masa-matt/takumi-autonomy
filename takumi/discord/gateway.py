#!/usr/bin/env python3
"""takumi.discord.gateway — Takumi Local Autonomy V2 Discord Bot

V2 の改善点（V1 との違い）:
  - Job 状態を 5 状態で管理（queued / running / blocked / done / failed）
  - 中間報告（状態変化ごとにメッセージを編集）
  - BLOCKED 時に承認ボタンを表示し、ユーザーが判断する

コマンド:
  @Takumi <タスク>   タスクを投入（推奨）
  !task <タスク>     プレフィックスでも可
  !status <job-id>  job の現在状態を確認
  !ping              死活確認

環境変数:
  DISCORD_TOKEN     必須
  ANTHROPIC_API_KEY 任意（未設定ならスタブモード）
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import discord
from discord.ext import commands

from takumi.core.job_state import Job, JobStatus
from takumi.discord.job_runner import run_job, resume_job
from takumi.sandbox.ingress import list_inbox, copy_from_inbox, INBOX_DIR

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

# チャンネルごとの pending inbox files
# {channel_id: [filename, ...]}  — 次の !task / @Takumi で input/ にコピーされる
_pending_inbox_files: dict[int, list[str]] = {}


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

async def _process_task(message: discord.Message, description: str) -> None:
    """Discord メッセージからタスクを受け取り、job を作成・実行して報告する。"""
    loop = asyncio.get_event_loop()

    # 即時 queued メッセージを送信
    status_msg = await message.reply(f"📥 **Queued…**\n> {description[:120]}")
    current_embed: discord.Embed | None = None
    approval_view: ApprovalView | None = None

    # 状態変化コールバック（同期スレッドから呼ばれる）
    def on_status(job: Job) -> None:
        nonlocal current_embed, approval_view
        current_embed = _build_embed(job)

        if job.status == JobStatus.BLOCKED:
            future = loop.create_future()
            _pending_approvals[job.job_id] = future
            view = ApprovalView(job.job_id, future)
            approval_view = view
            # スレッドから安全に Discord メッセージを編集
            asyncio.run_coroutine_threadsafe(
                status_msg.edit(content=None, embed=current_embed, view=view),
                loop,
            ).result(timeout=10)
        else:
            asyncio.run_coroutine_threadsafe(
                status_msg.edit(content=None, embed=current_embed, view=None),
                loop,
            ).result(timeout=10)

    # 1. run_job を thread pool で実行（BLOCKED なら途中で返る）
    channel_id = message.channel.id
    pending_files = _pending_inbox_files.pop(channel_id, [])

    job: Job = await loop.run_in_executor(
        _thread_pool,
        lambda: run_job(description, on_status=on_status, inbox_files=pending_files or None),
    )

    # 2. BLOCKED の場合: ボタン応答を待って resume
    if job.status == JobStatus.BLOCKED:
        future = _pending_approvals.get(job.job_id)
        if future:
            try:
                approved = await asyncio.wait_for(
                    asyncio.shield(future), timeout=300
                )
            except asyncio.TimeoutError:
                approved = False
            finally:
                _pending_approvals.pop(job.job_id, None)

            # resume を thread pool で実行
            job = await loop.run_in_executor(
                _thread_pool,
                lambda: resume_job(job, approved=approved, on_status=on_status),
            )

    log.info("Job %s finished: status=%s", job.job_id, job.status.value)


# ── イベント / コマンド ────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    log.info("Takumi V2 Bot ready: %s (id=%s)", bot.user, bot.user.id)


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
        await ctx.send("⚠️ タスクの内容が必要です。例: `!task この repo を調べて`")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        log.error("Command error: %s", error)
        await ctx.send(f"⚠️ エラー: {error}")


@bot.command(name="task", help="タスクを投入して結果を返す")
async def cmd_task(ctx, *, description: str):
    await _process_task(ctx.message, description)


@bot.command(name="status", help="job の現在状態を確認する")
async def cmd_status(ctx, job_id: str):
    from takumi.core.job_state import Job
    job = Job.load(job_id)
    if job is None:
        await ctx.send(f"❓ job が見つかりません: `{job_id}`")
        return
    await ctx.send(embed=_build_embed(job))


@bot.command(name="ping", help="死活確認")
async def cmd_ping(ctx):
    await ctx.send(f"🏓 Pong! latency={bot.latency * 1000:.0f}ms  (Takumi V2)")


@bot.command(name="files", help="inbox ファイル一覧 / 次のタスクに添付")
async def cmd_files(ctx, filename: str | None = None):
    """inbox のファイルを確認・予約する。

    !files          — inbox の一覧を表示
    !files data.csv — data.csv を次の @Takumi タスクの input/ にコピー予約
    """
    if filename is None:
        # 一覧表示
        files = list_inbox()
        if not files:
            await ctx.send(
                f"📭 inbox は空です。\n"
                f"`{INBOX_DIR}` にファイルを置いてください。"
            )
        else:
            names = "\n".join(f"  • `{f.name}`" for f in files)
            await ctx.send(f"📂 **inbox** ({len(files)} files)\n{names}")
        return

    # ファイルを予約（次の !task / @Takumi で input/ にコピーされる）
    # パストラバーサルチェックは copy_from_inbox 内で行う
    if "/" in filename or "\\" in filename or ".." in filename:
        await ctx.send(f"⚠️ 無効なファイル名: `{filename}`")
        return

    src = INBOX_DIR / filename
    if not src.exists():
        await ctx.send(f"❓ inbox に `{filename}` が見つかりません。")
        return

    channel_id = ctx.channel.id
    if channel_id not in _pending_inbox_files:
        _pending_inbox_files[channel_id] = []
    if filename not in _pending_inbox_files[channel_id]:
        _pending_inbox_files[channel_id].append(filename)

    queued = _pending_inbox_files[channel_id]
    names = ", ".join(f"`{f}`" for f in queued)
    await ctx.send(
        f"📎 `{filename}` を予約しました。\n"
        f"予約中: {names}\n"
        f"次の `@Takumi <タスク>` で input/ にコピーされます。"
    )


# ── エントリポイント ───────────────────────────────────────────────────────────

def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN 環境変数が設定されていません")
    log.info("Starting Takumi Local Autonomy V2 Bot…")
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
