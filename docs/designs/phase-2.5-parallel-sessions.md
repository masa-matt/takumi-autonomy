# Phase 2.5: Parallel Sessions

## Goal

複数の Discord スレッド（セッション）で同時に作業を走らせられるようにする。
同じ Takumi が複数の作業を並行して進める「マルチタスク」体験を実現する。

**解決する無駄**:
- 現状は同期実行のみ。1ジョブ走っていると次の Discord メッセージが詰まる
- 別スレッドの作業は独立しているのに、直列実行で待たされる
- CPU / ネットワークのアイドル時間が無駄

---

## Acceptance Criteria

- [ ] 別スレッドのタスクが同時に走る（N 並列、N は設定可能）
- [ ] 同一スレッド内のタスクは直列（workspace 競合を防ぐ）
- [ ] Hermes の同時書き込みで data race が起きない（file lock）
- [ ] Worker が異常終了してもジョブを retry できる（最大 M 回）
- [ ] Queue の状態が可視化される（`!status` コマンドで確認可能）
- [ ] V2 の単一セッション動作は継続動作する（opt-in でなく自動で並列化）
- [ ] 並列度の上限をリソースに応じて設定できる

---

## アーキテクチャ

```
Discord Gateway (async)
  ↓ put (non-blocking)
Job Queue (asyncio.Queue, in-process)
  ↓ get
Worker Pool (N workers, asyncio task)
  ↓ per job:
    ├─ session lock acquire (session_id)
    ├─ spawn Claude Code subprocess
    ├─ Hermes write (with file lock)
    └─ session lock release
```

**なぜ in-process asyncio Queue？**:
- V2 は単一コンテナ単一プロセス。Redis を入れる理由がない
- asyncio で十分な並列性が得られる（Claude Code は subprocess なので GIL の影響を受けない）
- 将来 multi-process / multi-host に拡張する必要が出たら Redis 化

---

## Data Model

### `takumi/core/job_queue.py`（新設）

```python
from dataclasses import dataclass, field
from enum import Enum
import asyncio

class JobPriority(str, Enum):
    HIGH = "high"      # user が直接投げたタスク
    NORMAL = "normal"  # 通常
    LOW = "low"        # バッチ処理・蒸留等

@dataclass
class QueuedJob:
    job_id: str
    session_id: str | None
    task: str
    priority: JobPriority
    enqueued_at: str
    attempts: int = 0
    max_attempts: int = 2
    on_status: callable | None = None
```

### Session Lock

```python
# In-memory lock (per-process)
_session_locks: dict[str, asyncio.Lock] = {}

def get_session_lock(session_id: str) -> asyncio.Lock:
    if session_id not in _session_locks:
        _session_locks[session_id] = asyncio.Lock()
    return _session_locks[session_id]
```

**複数プロセス化した場合**: file lock（`filelock` パッケージ）に切り替え。2.5 では in-memory で OK。

---

## File Changes

### 新設

| File | 内容 |
|---|---|
| `takumi/core/job_queue.py` | JobQueue / QueuedJob / priority scheduler |
| `takumi/core/worker.py` | Worker ループ本体 |
| `takumi/core/file_lock.py` | Hermes 書き込み用の file lock wrapper |
| `takumi/discord/status_command.py` | `!status` コマンドハンドラ |

### 修正

| File | 変更内容 |
|---|---|
| `takumi/discord/gateway.py` | ジョブを直接 `run_job` せず `job_queue.enqueue` する。non-blocking |
| `takumi/discord/job_runner.py` | `run_job` が worker から呼ばれる前提にする（session lock acquire は外側） |
| `takumi/hermes/memory.py` | 書き込みに `with file_lock(...):` を被せる |
| `takumi/hermes/skill.py` | 同上 |
| `takumi/hermes/repo_cache.py` | 同上 |
| `takumi/core/session_store.py` | 同上（session 状態の更新） |
| `Dockerfile` / `docker-compose.yml` | 特に変更なし（全て in-process） |

### 環境変数

| 変数 | 役割 | デフォルト |
|---|---|---|
| `TAKUMI_WORKER_COUNT` | 並列 worker 数 | 3 |
| `TAKUMI_MAX_ATTEMPTS` | ジョブ retry 上限 | 2 |
| `TAKUMI_QUEUE_MAXSIZE` | Queue のバッファサイズ | 50 |

---

## Worker 実装

```python
# takumi/core/worker.py
import asyncio
import logging
from takumi.core.job_queue import JobQueue, QueuedJob
from takumi.core.session_store import get_session_lock
from takumi.discord.job_runner import run_job

log = logging.getLogger("takumi-v2")

async def worker_loop(worker_id: int, queue: JobQueue):
    while True:
        qjob = await queue.get()
        try:
            await _run_with_lock(worker_id, qjob)
        except Exception as exc:
            log.exception("worker=%d job=%s failed: %s", worker_id, qjob.job_id, exc)
            await _handle_failure(queue, qjob, exc)
        finally:
            queue.task_done()

async def _run_with_lock(worker_id: int, qjob: QueuedJob):
    session_key = qjob.session_id or f"adhoc-{qjob.job_id}"
    lock = get_session_lock(session_key)
    async with lock:
        log.info("worker=%d starting job=%s session=%s", worker_id, qjob.job_id, session_key)
        # run_job は同期なので executor で回す
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, run_job, qjob.task, qjob.on_status, None, qjob.session_id)

async def _handle_failure(queue, qjob, exc):
    qjob.attempts += 1
    if qjob.attempts < qjob.max_attempts:
        log.warning("retrying job=%s (attempt %d/%d)", qjob.job_id, qjob.attempts, qjob.max_attempts)
        await queue.put(qjob)
    else:
        log.error("job=%s exhausted attempts, giving up", qjob.job_id)
        # Discord に失敗通知する callback を qjob.on_status 経由で呼ぶ
```

---

## Gateway の変更

```python
# 既存: gateway._run_job で直接 run_job(task, on_status) を呼んでいた

# 新しい: queue に投入するだけ
from takumi.core.job_queue import get_queue, QueuedJob

async def _enqueue_task(status_msg, description, session_id=None):
    queue = get_queue()
    qjob = QueuedJob(
        job_id=_generate_job_id(),
        session_id=session_id,
        task=description,
        priority=JobPriority.HIGH,
        enqueued_at=now_iso(),
        on_status=_make_status_callback(status_msg),
    )
    await queue.put(qjob)
    await status_msg.edit(content=f"受け取った（queue に入れた・位置: {queue.qsize()}）")
```

**重要**: `_run_job` の sync→async 変換は worker 側で `run_in_executor` を使って行う。gateway は即座に return するので Discord の UI がブロックしない。

---

## `!status` コマンド

Queue と worker の状態を表示する:

```
📊 Takumi Queue Status

Workers: 3 active (2 idle, 1 running)
Queue: 5 pending (high=2, normal=3, low=0)
Active sessions: 7

Running:
- worker-1: session=sess-xxx task="repo の調査..."

Pending (next 5):
1. session=sess-yyy priority=high task="..."
2. session=sess-zzz priority=normal task="..."
...
```

---

## Hermes の file lock

`takumi/core/file_lock.py`:

```python
import fcntl
from contextlib import contextmanager
from pathlib import Path

@contextmanager
def file_lock(path: Path, timeout: float = 10.0):
    """書き込み用の排他ロック。atomic write には tmp+rename を使う。"""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as f:
        # non-blocking + timeout
        import time
        start = time.time()
        while True:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() - start > timeout:
                    raise TimeoutError(f"file lock timeout: {path}")
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

Hermes の書き込みを全て wrap:

```python
def write_memory(job, output, danger_level="auto_allow"):
    ...
    path = _ENTRIES_DIR / f"{entry_id}.json"
    with file_lock(path):
        _atomic_write_json(path, entry.to_dict())
```

`_atomic_write_json` は tmp file + rename:

```python
def _atomic_write_json(path: Path, data: dict):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.rename(path)
```

**Index ファイル（`runtime/sessions/_index.json`）**も同じ方式で守る。

---

## Race Condition 対策

| シナリオ | 対策 |
|---|---|
| 同一 session に連続メッセージ | session_lock で直列化（同じ lock を取り合う） |
| 異なる session が同時に Hermes に書く | file_lock + atomic write |
| session_index.json の同時更新 | file_lock でラップ |
| skill approval と job 実行が同時 | skill ファイルごとに file_lock |
| repo cache の同時 update | cache ファイルごとに file_lock |
| Queue への同時 put | asyncio.Queue は thread-safe（というか async-safe） |

---

## Flow

### 並列実行の時系列

```
T+0s  User A: スレッド A にメッセージ → queue に QJob1 投入
T+0s  User B: スレッド B にメッセージ → queue に QJob2 投入
T+0s  Worker-1 が QJob1 を取得 → session_A lock acquire
T+0s  Worker-2 が QJob2 を取得 → session_B lock acquire
T+0s  両方の Claude Code subprocess が並行実行
...
T+5s  User A: スレッド A に2回目メッセージ → queue に QJob3 投入
T+5s  Worker-3 が QJob3 を取得 → session_A lock を待つ（QJob1 が保持中）
T+30s QJob1 完了 → session_A lock release
T+30s QJob3 が session_A lock 取得 → 実行開始
```

同一 session 内の直列性が保たれる。

---

## Edge Cases

| ケース | 対処 |
|---|---|
| Queue がフル（maxsize 到達） | `!status` で警告・新規受付を一時拒否（status_msg でユーザーに通知） |
| Worker が例外でクラッシュ | `worker_loop` のトップレベル try で catch → worker を再起動 |
| Claude Code subprocess が hang | timeout=300 既存 → 継続。worker はその間ブロック（許容） |
| File lock が他プロセスに奪われたまま帰らない | timeout 付き lock + error ログ。稀なのでアラートで対応 |
| asyncio イベントループ停止 | サービス全体が死ぬので外部 healthcheck（docker restart policy） |
| ジョブが retry 上限に達した | 最終 failure 扱い・Discord に通知・audit log |
| 順序保証が必要なケース | 同一 session lock で自動的に投入順序が保たれる |

---

## 性能の目安

- Claude Code subprocess ≈ 数秒〜数分（API レスポンス時間）
- File lock の待ち時間: 数 ms
- Queue / Worker のオーバーヘッド: 無視できる
- CPU より Claude API のレート制限の方が先に効く

**推奨 worker 数**: 3〜5。Claude Code の同時 session は契約プランによる。
Max plan なら 5〜10 同時は問題ない想定だが、実測して調整。

---

## Testing Plan

### 単体テスト

- `JobQueue` の FIFO + priority 動作
- `file_lock` の排他・timeout
- `_atomic_write_json` の途中失敗時に元ファイルが壊れない
- `worker_loop` の retry 動作

### 統合テスト（手動）

1. 3つの別スレッドに同時にタスクを投げる → 3つが並行実行される
2. 同じスレッドに2つ連続投げる → 2つ目は1つ目の完了を待つ
3. `!status` で queue 状態が見える
4. Worker を kill（SIGKILL）→ 別 worker が retry
5. 負荷試験: 20タスクを一気に投入、maxsize で溢れることを確認

### 並列書き込みテスト

- 10 タスクを同時実行し、`runtime/memory/entries/` に全部保存されること（欠損なし）
- `_index.json` が破損しないこと

---

## Non-goals

- Multi-process / Multi-host（Redis + 複数コンテナ）
- Job persistence（プロセス再起動で queue が失われる）
- 動的 worker スケーリング
- ジョブ優先度の自動調整
- Cross-session coordination（「別タスクの完了を待ってから実行」等）

これらは V3 本番設計で扱う。

---

## Dependencies

- `filelock` パッケージ（`pip install filelock`）— fcntl 直接でも可だが wrapper が便利
- Phase 2.1〜2.4 完了推奨（それぞれが Hermes 書き込みを増やすため、file lock の効果が大きくなる）

docs 更新:
- `docs/runbooks/parallel-ops.md` 新設（運用監視・トラブルシュート）
- `docs/operating-rules.md` に並列制約を追記
- `docs/metrics.md` に queue / worker メトリクスを追加
