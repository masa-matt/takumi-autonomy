"""Hermes Bridge — session_search

File-based implementation for PoC.
Searches past memory entries in runtime/memory/entries/ by keyword overlap.
"""

import json
import re
from pathlib import Path

from schemas.memory_entry import SearchHit, SearchResult

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_ENTRIES_DIR = _PROJECT_ROOT / "runtime" / "memory" / "entries"

# Common stop-words to ignore when scoring
_STOP_WORDS = {"", "the", "a", "an", "to", "in", "of", "for", "and", "or", "is", "it"}


def search_sessions(query: str, top_k: int = 3) -> SearchResult:
    """Search past memory entries by keyword matching.

    Scores each entry by Jaccard-like overlap between query tokens and
    the entry's task + output_summary text.

    Returns top_k highest-scoring hits (score > 0 only).
    """
    _ENTRIES_DIR.mkdir(parents=True, exist_ok=True)

    entry_files = sorted(_ENTRIES_DIR.glob("*.json"))
    total_searched = len(entry_files)

    if not entry_files or not query.strip():
        return SearchResult(query=query, hits=[], total_searched=total_searched)

    query_tokens = _tokenize(query)
    if not query_tokens:
        return SearchResult(query=query, hits=[], total_searched=total_searched)

    hits: list[SearchHit] = []
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
        hits.append(
            SearchHit(
                entry_id=entry["entry_id"],
                job_id=entry["job_id"],
                task=entry["task"],
                output_summary=entry.get("output_summary"),
                saved_at=entry["saved_at"],
                score=score,
            )
        )

    hits.sort(key=lambda h: h.score, reverse=True)
    return SearchResult(query=query, hits=hits[:top_k], total_searched=total_searched)


def _tokenize(text: str) -> set[str]:
    return set(re.split(r"\W+", text.lower())) - _STOP_WORDS
