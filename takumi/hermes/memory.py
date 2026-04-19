"""takumi.hermes.memory — write_memory / search_sessions

File-based PoC. Entries stored in runtime/memory/entries/ as JSON.
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from takumi.hermes.models import MemoryEntry, SaveResult, SearchHit, SearchResult

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_ENTRIES_DIR = Path(
    os.environ.get("HERMES_ENTRIES_DIR", str(_PROJECT_ROOT / "runtime" / "memory" / "entries"))
)

_SENSITIVE_PATTERNS = [
    r"\btoken\b",
    r"\bpassword\b",
    r"\bsecret\b",
    r"\bapi.?key\b",
    r"\bcredential",
    r"\bprivate.?key\b",
    r"\bssh.?key\b",
]

_STOP_WORDS = {"", "the", "a", "an", "to", "in", "of", "for", "and", "or", "is", "it",
               "が", "を", "は", "に", "の", "で", "と", "も", "から", "まで", "する", "した", "ある", "いる"}


# ── Save ──────────────────────────────────────────────────────────────────────

def write_memory(job, output: Optional[str], danger_level: str = "auto_allow") -> SaveResult:
    """Job の実行結果をメモリエントリとして保存する。

    Args:
        job:          完了した Job オブジェクト（job.job_id, job.task, job.status）
        output:       _execute() が返した生の出力文字列（None 可）
        danger_level: _classify() が返す danger レベル文字列
    """
    _ENTRIES_DIR.mkdir(parents=True, exist_ok=True)

    if output is None:
        return SaveResult(saved=False, skip_reason="no execution result")

    for pattern in _SENSITIVE_PATTERNS:
        if re.search(pattern, output, re.IGNORECASE):
            return SaveResult(saved=False, skip_reason=f"output matches sensitive pattern: {pattern!r}")

    entry_id = f"mem-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    entry = MemoryEntry(
        entry_id=entry_id,
        job_id=job.job_id,
        task=job.task,
        status=job.status.value,
        output_summary=output[:500],
        danger_level=danger_level,
        tags=[job.status.value, danger_level],
    )

    path = _ENTRIES_DIR / f"{entry_id}.json"
    path.write_text(json.dumps(entry.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return SaveResult(saved=True, entry_id=entry_id)


def write_chat_memory(user_text: str, reply: str) -> SaveResult:
    """雑談（ジョブを伴わない会話）も記憶として保存する。

    Job を持たない代わりに job_id は `chat-YYYYMMDD-xxxxxxxx`、tags に "chat" を入れる。
    output_summary は「user: ... / takumi: ...」形式で両方残す。
    """
    _ENTRIES_DIR.mkdir(parents=True, exist_ok=True)

    if not reply:
        return SaveResult(saved=False, skip_reason="empty reply")

    combined = f"user: {user_text}\ntakumi: {reply}"
    for pattern in _SENSITIVE_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            return SaveResult(saved=False, skip_reason=f"chat matches sensitive pattern: {pattern!r}")

    today = datetime.now(timezone.utc).strftime('%Y%m%d')
    suffix = uuid.uuid4().hex[:8]
    entry_id = f"mem-{today}-{suffix}"
    chat_job_id = f"chat-{today}-{suffix}"

    entry = MemoryEntry(
        entry_id=entry_id,
        job_id=chat_job_id,
        task=user_text[:200],
        status="chat",
        output_summary=combined[:500],
        danger_level="auto_allow",
        tags=["chat"],
    )

    path = _ENTRIES_DIR / f"{entry_id}.json"
    path.write_text(json.dumps(entry.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return SaveResult(saved=True, entry_id=entry_id)


# ── Search ────────────────────────────────────────────────────────────────────

def search_sessions(query: str, top_k: int = 3, recent_always: int = 3) -> SearchResult:
    """過去メモリエントリをキーワードマッチで検索する。

    キーワードマッチに加えて、直近 recent_always 件を常に含める。
    日本語のように単語分割が難しい言語でもコンテキストが途切れないようにする。
    """
    _ENTRIES_DIR.mkdir(parents=True, exist_ok=True)

    # 新しい順にソート（ファイル名に日付が含まれる）
    entry_files = sorted(_ENTRIES_DIR.glob("*.json"), reverse=True)
    total_searched = len(entry_files)

    if not entry_files:
        return SearchResult(query=query, hits=[], total_searched=total_searched)

    # 直近エントリを日付降順で取得
    recent_entries: list[dict] = []
    for path in entry_files:
        if len(recent_entries) >= recent_always:
            break
        try:
            recent_entries.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue

    # キーワードマッチ
    keyword_hits: list[SearchHit] = []
    query_tokens = _tokenize(query)
    if query_tokens:
        for path in entry_files:
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            text = f"{entry.get('task', '')} {entry.get('output_summary') or ''}"
            text_tokens = _tokenize(text)
            overlap = len(query_tokens & text_tokens)
            if overlap == 0:
                continue
            score = round(overlap / len(query_tokens), 3)
            keyword_hits.append(SearchHit(
                entry_id=entry["entry_id"],
                job_id=entry["job_id"],
                task=entry["task"],
                output_summary=entry.get("output_summary"),
                saved_at=entry["saved_at"],
                score=score,
            ))
        keyword_hits.sort(key=lambda h: h.score, reverse=True)

    # 直近エントリを SearchHit に変換（スコア 0 = recent）
    seen_ids: set[str] = {h.entry_id for h in keyword_hits[:top_k]}
    recent_hits: list[SearchHit] = []
    for entry in recent_entries:
        if entry["entry_id"] in seen_ids:
            continue
        recent_hits.append(SearchHit(
            entry_id=entry["entry_id"],
            job_id=entry["job_id"],
            task=entry["task"],
            output_summary=entry.get("output_summary"),
            saved_at=entry["saved_at"],
            score=0.0,
        ))

    combined = keyword_hits[:top_k] + recent_hits
    return SearchResult(query=query, hits=combined, total_searched=total_searched)


def _tokenize(text: str) -> set[str]:
    return set(re.split(r"\W+", text.lower())) - _STOP_WORDS
