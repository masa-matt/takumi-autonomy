"""report_formatter.py

JobRunner の report JSON を Discord Embed に変換する。

Discord Embed の制限:
  - title        : 256 chars
  - description  : 4096 chars
  - field value  : 1024 chars
  - total embed  : 6000 chars
"""

import json
from pathlib import Path

import discord


# ステータスごとの色と絵文字
_STATUS_META = {
    "done":    (discord.Color.green(),  "✅"),
    "failed":  (discord.Color.red(),    "❌"),
    "pending": (discord.Color.yellow(), "⏳"),
    "running": (discord.Color.blue(),   "🔄"),
}


def _trunc(text: str, limit: int) -> str:
    """limit 文字を超えたら末尾を … にする。"""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def build_embed(report_path: str) -> discord.Embed:
    """report JSON ファイルを読んで Embed を返す。"""
    with open(report_path, encoding="utf-8") as f:
        r = json.load(f)

    status = r.get("status", "unknown")
    color, icon = _STATUS_META.get(status, (discord.Color.grayed(), "❓"))

    job_id   = r.get("job_id", "?")
    task_txt = _trunc(r.get("task", ""), 100)
    title    = _trunc(f"{icon} {job_id}", 256)

    embed = discord.Embed(
        title=title,
        description=f"**Task:** {task_txt}",
        color=color,
    )

    # ── 実行結果 ──────────────────────────────────────────────────────────────
    result = r.get("result") or {}
    if isinstance(result, dict):
        output = result.get("output") or result.get("error") or ""
    else:
        output = str(result)

    if output:
        embed.add_field(
            name="Output",
            value=_trunc(output, 1024),
            inline=False,
        )

    stop_reason = r.get("stop_reason")
    if stop_reason:
        embed.add_field(
            name="Stop reason",
            value=_trunc(stop_reason, 512),
            inline=False,
        )

    # ── Recall ────────────────────────────────────────────────────────────────
    recall = r.get("recall", {})
    hits   = recall.get("hits_count", 0)
    skills = len(recall.get("skill_hits", []))
    top    = recall.get("top_hit_task") or "—"
    embed.add_field(
        name="Recall",
        value=f"memory={hits}  skills={skills}\n`{_trunc(top, 80)}`",
        inline=True,
    )

    # ── Memory Save ───────────────────────────────────────────────────────────
    save  = r.get("save", {})
    saved = "✅ saved" if save.get("saved") else f"— {save.get('skip_reason','')}"
    embed.add_field(name="Memory", value=saved, inline=True)

    # ── Executor mode ─────────────────────────────────────────────────────────
    mode = "—"
    if isinstance(result, dict) and result.get("metadata"):
        mode = result["metadata"].get("mode", "—")
    embed.add_field(name="Mode", value=mode, inline=True)

    embed.set_footer(text=job_id)
    return embed


def build_error_embed(task: str, error: str) -> discord.Embed:
    """JobRunner 呼び出し自体が例外で落ちた場合の Embed。"""
    embed = discord.Embed(
        title="❌ Internal error",
        description=f"**Task:** {_trunc(task, 100)}",
        color=discord.Color.red(),
    )
    embed.add_field(name="Error", value=_trunc(error, 1024), inline=False)
    return embed
