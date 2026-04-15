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
import pathlib
import re
import shutil
from concurrent.futures import ThreadPoolExecutor

import discord
from discord import app_commands
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
# {channel_id: [filename, ...]}  — 次のタスクで input/ にコピーされる
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

    pending_files = _pending_inbox_files.pop(channel_id, [])

    job: Job = await loop.run_in_executor(
        _thread_pool,
        lambda: run_job(description, on_status=on_status, inbox_files=pending_files or None),
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
    """inbox 一覧テキストを返す。"""
    files = list_inbox()
    if not files:
        return f"📭 inbox は空です。\n`{INBOX_DIR}` にファイルを置いてください。"
    names = "\n".join(f"  • `{f.name}`" for f in files)
    return f"📂 **inbox** ({len(files)} files)\n{names}"


def _handle_files_reserve(channel_id: int, filename: str) -> str:
    """filename を予約してメッセージを返す。エラー時はエラーメッセージを返す。"""
    if "/" in filename or "\\" in filename or ".." in filename:
        return f"⚠️ 無効なファイル名: `{filename}`"
    src = INBOX_DIR / filename
    if not src.exists():
        return f"❓ inbox に `{filename}` が見つかりません。"
    if channel_id not in _pending_inbox_files:
        _pending_inbox_files[channel_id] = []
    if filename not in _pending_inbox_files[channel_id]:
        _pending_inbox_files[channel_id].append(filename)
    queued = _pending_inbox_files[channel_id]
    names = ", ".join(f"`{f}`" for f in queued)
    return (
        f"📎 `{filename}` を予約しました。\n"
        f"予約中: {names}\n"
        f"次の `/task` または `@Takumi <タスク>` で input/ にコピーされます。"
    )


# ── Claude Code 認証フロー ──────────────────────────────────────────────────────

async def _find_auth_channel() -> discord.abc.Messageable | None:
    """認証メッセージを送るチャンネルを決める。

    優先順位:
    1. DISCORD_AUTH_CHANNEL_ID 環境変数
    2. DISCORD_GUILD_ID のサーバー内の最初の書き込み可能テキストチャンネル
    3. ボットオーナーへの DM
    """
    channel_id = os.environ.get("DISCORD_AUTH_CHANNEL_ID")
    if channel_id:
        ch = bot.get_channel(int(channel_id))
        if ch:
            return ch

    guild_id = os.environ.get("DISCORD_GUILD_ID")
    if guild_id:
        guild = bot.get_guild(int(guild_id))
        if guild:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    return ch

    app_info = await bot.application_info()
    if app_info.owner:
        return await app_info.owner.create_dm()

    return None


async def _wait_for_auth_code_file(timeout_sec: int = 300) -> str | None:
    """inbox/.auth_code が作成されるまでポーリングして内容を返す。

    ファイルを読んだら即削除する（コードを Discord チャットに流さないため）。
    デフォルトは5分待機。
    """
    auth_file = INBOX_DIR / ".auth_code"
    for _ in range(timeout_sec // 10):
        await asyncio.sleep(10)
        if auth_file.exists():
            try:
                code = auth_file.read_text(encoding="utf-8").strip()
                if not code:
                    continue  # 空ファイルはスキップ（ユーザーがまだ書いていない）
                auth_file.unlink()
                log.info("auth_code ファイルを読み込みました（削除済み）")
                return code
            except Exception as exc:
                log.warning("auth_code ファイル読み込みエラー: %s", exc)
    return None


def _restore_claude_config_if_needed() -> None:
    """/root/.claude.json が欠けていればバックアップから復元する。

    Docker volume は /root/.claude/（ディレクトリ）を永続化しているが、
    /root/.claude.json（ファイル）は volume 外のためコンテナ再起動で消える。
    /root/.claude/backups/ に残っている最新バックアップで補完する。
    """
    config = pathlib.Path("/root/.claude.json")
    if config.exists():
        return

    backup_dir = pathlib.Path("/root/.claude/backups")
    if not backup_dir.exists():
        return

    backups = sorted(backup_dir.glob(".claude.json.backup.*"))
    if not backups:
        log.info("claude config なし、バックアップも見つからず")
        return

    latest = backups[-1]
    try:
        shutil.copy2(latest, config)
        log.info("claude config をバックアップから復元しました: %s → %s", latest, config)
    except Exception as exc:
        log.warning("claude config 復元失敗: %s", exc)


def _pexpect_launch_auth() -> tuple[str | None, object | None]:
    """pexpect で claude auth login を PTY 越しに起動し、URL を取得して返す。

    Returns:
        (url, child) — URL が取れた場合は child プロセスを保持して返す
        ("already", None) — 認証済みの場合
        (None, None) — URL が取れなかった場合（認証済みとみなす）
    """
    import pexpect  # type: ignore

    env = {**os.environ, "DISPLAY": ""}
    child = pexpect.spawn("claude auth login", env=env, timeout=10, encoding="utf-8")

    try:
        i = child.expect([r"https://\S+", r"already", pexpect.EOF, pexpect.TIMEOUT])
    except Exception as exc:
        log.warning("pexpect expect 失敗: %s", exc)
        try:
            child.close(force=True)
        except Exception:
            pass
        return None, None

    if i == 1:
        # "already logged in" — 認証済み
        try:
            child.close(force=True)
        except Exception:
            pass
        return "already", None

    if i in (2, 3):
        # EOF or TIMEOUT — URL が取れなかった（認証済み or 接続不可）
        try:
            child.close(force=True)
        except Exception:
            pass
        return None, None

    # i == 0 — URL 行にマッチした
    matched_text = (child.before or "") + (child.after or "")
    m = re.search(r"https://\S+", matched_text)
    url = m.group(0) if m else None
    return url, child


def _pexpect_send_code(child: object, code: str) -> bool:
    """pexpect child にコードを送信してトークン交換を待つ。

    Returns: True = 成功 / False = 失敗
    """
    import pexpect  # type: ignore

    try:
        child.sendline(code)
        # 完了 or EOF まで最大60秒待つ
        child.expect([pexpect.EOF, pexpect.TIMEOUT], timeout=60)
    except Exception as exc:
        log.warning("pexpect コード送信/待機エラー: %s", exc)
    finally:
        try:
            child.close(force=True)
        except Exception:
            pass
    return True


async def _ensure_claude_auth() -> None:
    """claude-code executor の認証を確認し、未認証なら Discord + ローカルファイル経由で認証を要求する。

    フロー:
    1. pexpect（PTY）で claude auth login を起動し URL を取得
    2. Discord に URL と手順を送信
    3. ユーザーがブラウザで認証 → Authentication Code を inbox/.auth_code に書く
    4. Bot がファイルを検知 → pexpect 経由で claude auth login にコードを送信
    5. トークン交換完了 → claude --print で動作確認
    """
    if os.environ.get("TAKUMI_EXECUTOR", "").lower() != "claude-code":
        return

    # コンテナ再起動で /root/.claude.json が消えている場合にバックアップから復元
    _restore_claude_config_if_needed()

    log.info("Claude Code executor: 認証状態を確認中…")

    loop = asyncio.get_event_loop()

    # pexpect は同期 API — ThreadPoolExecutor で実行
    url, child = await loop.run_in_executor(_thread_pool, _pexpect_launch_auth)

    if url == "already":
        log.info("Claude Code: 認証済み")
        return

    if not url:
        log.info("Claude Code: 認証済みとみなして続行")
        return

    # 未認証 → Discord に手順を送信
    log.info("Claude Code: 未認証。Discord に認証手順を送信します。")
    channel = await _find_auth_channel()

    inbox_path = INBOX_DIR / ".auth_code"
    host_inbox = "./inbox/.auth_code"

    # 空ファイルを作成しておく（ユーザーが開いて貼り付けるだけでいいように）
    try:
        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        if not inbox_path.exists():
            inbox_path.touch()
            log.info("空の auth_code ファイルを作成しました: %s", inbox_path)
    except Exception as exc:
        log.warning("auth_code ファイルの作成に失敗: %s", exc)

    if channel:
        await channel.send(
            "🔐 **Claude Code の認証が必要です**\n\n"
            "**Step 1.** 以下のURLをブラウザで開いてログインしてください:\n"
            f"<{url}>\n\n"
            "**Step 2.** 認証後に表示される `Authentication Code` を以下のファイルに貼り付けて保存してください:\n"
            f"`{host_inbox}`\n\n"
            "（ファイルはすでに作成済みです。開いて貼り付けるだけでOKです）"
        )
        log.info("Discord に認証手順を送信しました。ファイル待機中: %s", inbox_path)
    else:
        log.warning("チャンネルが見つかりません。認証URL: %s", url)
        log.warning("認証後のコードを %s に書き込んでください。", inbox_path)

    # ファイルからコードを待つ（最大5分）
    code = await _wait_for_auth_code_file(timeout_sec=300)

    if not code:
        if child:
            await loop.run_in_executor(_thread_pool, lambda: child.close(force=True))
        log.warning("Claude Code: 認証コードが届かずタイムアウト")
        if channel:
            await channel.send(
                "⚠️ 認証がタイムアウトしました（5分）。\n"
                "`docker compose restart` して再試行してください。"
            )
        return

    # コードを受け取った → Discord に通知して pexpect 経由で送信
    if channel:
        await channel.send("🔄 Authentication Code を受け取りました。認証中です（最大60秒）...")
    log.info("認証コードを受け取りました。pexpect 経由で送信します。")

    await loop.run_in_executor(_thread_pool, lambda: _pexpect_send_code(child, code))

    # 動作確認
    log.info("Claude Code の動作を確認中…")
    try:
        test_proc = await asyncio.create_subprocess_exec(
            "claude", "--print", "respond with just: ok",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, _ = await asyncio.wait_for(test_proc.communicate(), timeout=60)
        if test_proc.returncode == 0:
            log.info("Claude Code: 認証OK")
            if channel:
                await channel.send("✅ Claude Code の認証が完了しました！タスクを受け付けられます。")
        else:
            log.warning("Claude Code: 動作確認NG (returncode=%d)", test_proc.returncode)
            if channel:
                await channel.send(
                    "⚠️ 認証が正常に完了しなかった可能性があります。\n"
                    "`docker compose restart` して再試行してください。"
                )
    except asyncio.TimeoutError:
        log.warning("Claude Code: 動作確認タイムアウト")
        if channel:
            await channel.send(
                "⏳ 認証状態の確認がタイムアウトしました。\n"
                "少し待ってから `/task こんにちは` を試してみてください。"
            )


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


@bot.tree.command(name="files", description="inbox ファイル一覧 / 次のタスクにファイルを添付")
@app_commands.describe(filename="添付するファイル名（省略すると一覧表示）")
async def slash_files(interaction: discord.Interaction, filename: str | None = None):
    channel_id = interaction.channel_id or 0
    if filename is None:
        await interaction.response.send_message(_handle_files_list())
    else:
        msg = _handle_files_reserve(channel_id, filename)
        await interaction.response.send_message(msg)


# ── エントリポイント ───────────────────────────────────────────────────────────

def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN 環境変数が設定されていません")
    log.info("Starting Takumi Local Autonomy V2 Bot…")
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
