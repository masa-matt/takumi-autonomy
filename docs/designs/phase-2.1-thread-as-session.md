# Phase 2.1: Thread = Session

## Goal

Discord スレッド内で連続するメッセージを「同じ作業の続き」として扱う。
同一スレッドでは workspace（特に `repos/`）を再利用し、前のメッセージで clone した repo がそのまま使える状態にする。

**解決する UX 問題**:
- スレッド1回目で `https://github.com/org/repo` を見てもらう
- スレッド2回目で「その続きで Bitcoin ブランチ見て」と言うと、今は repos/ が空で「どの repo か分からない」と返される
- 2.1 後は、前回 clone した repo がそのまま使える

---

## Acceptance Criteria

- [ ] スレッド初回メッセージで作成した workspace が、同スレッド2回目以降のメッセージでも使われる
- [ ] `runtime/sessions/<session_id>.json` が作成・更新される
- [ ] `thread_id → session_id` のマッピングが永続化されている（コンテナ再起動後も同スレッドは継続）
- [ ] セッション内の過去メッセージ（最大 N 件）がプロンプトに注入される
- [ ] Thread archive イベントでセッションが `archived` 状態になる
- [ ] 7日間アクセスのないセッションは自動で archived にする
- [ ] 既存の V2 の機能（単発タスク・雑談・outbox 出力）はそのまま動く

---

## Data Model

### `takumi/core/session.py`（新設）

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

class SessionStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"

@dataclass
class Session:
    session_id: str              # "sess-20260418-xxxxxxxx"
    thread_id: str               # Discord thread ID (str for stability)
    channel_id: str              # parent channel ID
    workspace_path: str          # e.g. "takumi/jobs/job-20260418-xxx"
    status: SessionStatus = SessionStatus.ACTIVE
    job_ids: list[str] = field(default_factory=list)
    message_history: list[dict] = field(default_factory=list)
                                 # [{"role": "user"|"takumi", "text": "...", "ts": "..."}]
    created_at: str = ""
    last_active_at: str = ""

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "Session": ...
```

### `takumi/core/session_store.py`（新設）

File-based persistence。並列アクセスは 2.5 で対応するため、2.1 ではシンプルな read-modify-write で OK。

```python
def create_session(thread_id: str, channel_id: str, workspace_path: str) -> Session: ...
def get_session_by_thread(thread_id: str) -> Session | None: ...
def get_session(session_id: str) -> Session | None: ...
def update_session(session: Session) -> None: ...
def archive_session(session_id: str) -> None: ...
def list_active_sessions() -> list[Session]: ...
def archive_stale_sessions(max_idle_days: int = 7) -> int: ...
```

**保存先**: `runtime/sessions/<session_id>.json`
**Index**: `runtime/sessions/_index.json` に `{thread_id: session_id}` マップを保持
  - 理由: thread_id → session_id の高速 lookup。session ファイルを全スキャンしたくない

---

## File Changes

### 新設

| File | 内容 |
|---|---|
| `takumi/core/session.py` | Session モデル・SessionStatus enum |
| `takumi/core/session_store.py` | ファイルベース永続化 CRUD |
| `takumi/core/session_store_test.py` | 単体テスト |

### 修正

| File | 変更内容 |
|---|---|
| `takumi/discord/gateway.py` | `_process_task_channel` で session 作成、`_process_thread_message` で session lookup し既存 workspace を再利用 |
| `takumi/discord/job_runner.py` | `run_job(task, session_id=None)` に拡張。session_id があれば workspace 新規作成せず既存を使う。`_build_workspace_prompt` に session メッセージ履歴を注入 |
| `takumi/sandbox/workspace.py` | `get_or_create_workspace(job_id, reuse_path=None)` を追加。reuse_path があればそれを使う |

### 設定・環境変数

| 変数 | 役割 | デフォルト |
|---|---|---|
| `TAKUMI_SESSION_MAX_IDLE_DAYS` | 何日アクセスなしで archive するか | 7 |
| `TAKUMI_SESSION_HISTORY_LIMIT` | プロンプトに注入する過去メッセージの最大数 | 10 |

---

## Flow

### 初回メッセージ（新スレッド）

```
User: Discord task channel にメッセージ投稿
  ↓
gateway.on_message
  ↓
_process_task_channel(message, description)
  ↓ create thread
thread = await message.create_thread(...)
  ↓
session = session_store.create_session(thread.id, channel.id, workspace_path=None)
  ↓
_is_task(description)
  ├─ False → _run_chat_reply（session に履歴のみ追加）
  └─ True  → job = run_job(description, session_id=session.session_id)
              ↓ run_job 内で新 workspace 作成
              ↓ session.workspace_path を更新
              ↓ session.job_ids.append(job_id)
              ↓ session_store.update_session(session)
```

### 2回目以降のメッセージ（既存スレッド）

```
User: 既存スレッドにメッセージ投稿
  ↓
gateway.on_message
  ↓ isinstance(message.channel, discord.Thread)
_process_thread_message(message, description)
  ↓
session = session_store.get_session_by_thread(str(message.channel.id))
  ├─ None → （エラーパス）新規セッションとして扱うか、無視する
  └─ Found → session.last_active_at 更新
              ↓
_is_task(description)
  ├─ False → _run_chat_reply（session.message_history に追加）
  └─ True  → run_job(description, session_id=session.session_id)
              ↓ run_job は session.workspace_path の既存 workspace を再利用
              ↓ プロンプトに session.message_history（最大 N 件）を注入
              ↓ session.job_ids.append(new_job_id)
```

### Thread archive 検知

Discord API の `on_thread_update` イベントで `thread.archived == True` になった時:

```python
@bot.event
async def on_thread_update(before, after):
    if not before.archived and after.archived:
        session_store.archive_session_by_thread(str(after.id))
```

### 定期 archive（起動時 + 定期タスク）

起動時と毎日1回（asyncio.create_task で loop）:

```python
session_store.archive_stale_sessions(max_idle_days=TAKUMI_SESSION_MAX_IDLE_DAYS)
```

---

## Workspace 再利用の具体

現状 `takumi/sandbox/workspace.py` は `get_workspace(job_id)` だが、2.1 では:

```python
# 既存
def get_workspace(job_id: str) -> Workspace | None: ...

# 新設
def get_or_create_workspace(job_id: str, reuse_path: Path | None = None) -> Workspace:
    """reuse_path があればその workspace を新 job_id にも紐付ける。
    物理的なディレクトリは同じ。state/job.json 等は新 job_id 分を追加。"""
```

設計上の選択肢:
- **A: 物理ディレクトリ共有** — 同じ `takumi/jobs/<session_initial_job_id>/` を使い続ける
  - 利点: repos/ がそのまま使える
  - 欠点: job_id とディレクトリが 1:1 でなくなる（state/job.json が複数になるか、上書きされるか）
- **B: シンボリックリンク** — 新 job ディレクトリを作り、repos/ だけ初回 job の repos/ への symlink
  - 利点: 各 job 独立
  - 欠点: symlink 管理が複雑

**2.1 では A を採用**。物理ディレクトリは初回 job のものを使い、新 job は同じディレクトリ内で動く。state/ には `jobs/` サブディレクトリを作り、job_id ごとに状態を分ける。

```
takumi/jobs/<session_initial_job_id>/
  input/        ← 共有
  repos/        ← 共有（rebuild 不要！）
  output/       ← job ごとに上書きされる or 最新が残る
  logs/         ← 共有
  state/
    jobs/
      job-xxx.json  ← 初回 job
      job-yyy.json  ← 2回目 job
```

注意: output/ は毎回上書きになる。**各 job の output は outbox 側で保持される**ので実運用上問題なし。

---

## プロンプトへの注入

`_build_workspace_prompt()` に session 履歴セクションを追加:

```
{soul_section}

## セッション履歴（このスレッドでの過去のやり取り）
- [user 19:20] ちょっと仕事頼んでいい？ このリポジトリ https://github.com/...
- [takumi 19:20] もちろん、いいっすよ。clone しときますね。
- [user 19:25] Bitcoin ブランチ見て。

## Recall（過去の記憶）
...

作業ディレクトリ: {workspace.path}
...
```

履歴は最新 `TAKUMI_SESSION_HISTORY_LIMIT` 件（デフォルト10件）まで。古いものは切る。

---

## Edge Cases

| ケース | 対処 |
|---|---|
| コンテナ再起動後、thread に投稿された | `session_store.get_session_by_thread` で index から復元 |
| Thread が削除された（discord 側） | 次回投稿時に session 再作成。古い session は stale として archive |
| workspace ディレクトリがユーザーに手動削除された | get_or_create_workspace が新規作成にフォールバック、session.workspace_path を更新 |
| session ファイルが破損している | log warning・session を新規作成・index を修復 |
| 同一スレッドに猛連打でメッセージ（race） | 2.1 では単純 read-modify-write（上書きリスクあり）。2.5 で file lock 対応 |
| session が active 多すぎてディスク圧迫 | `archive_stale_sessions` の idle 日数を短くする（環境変数で調整） |
| `_is_task` が False の雑談も session 履歴に残すべきか | Yes。文脈の一部として扱う。ただし job は走らない |

---

## Testing Plan

### 単体テスト (`takumi/core/session_store_test.py`)

- create → get_by_thread → update → archive の往復
- index の整合性（session 作成・削除で index も更新される）
- archive_stale_sessions が idle を超えたものだけ archive する
- 破損した session ファイルを skip して動く

### 統合テスト（手動）

1. Discord の task channel に `https://github.com/example/repo を clone して` と投稿
2. スレッドが作られる、repo が clone される
3. スレッド内で `README 見せて` と投稿 → 前回 clone した repo の README が読める
4. コンテナを再起動
5. 同じスレッドに `package.json の依存見せて` → 引き続き同じ repo が使える（session 復元確認）
6. 8日間放置（または idle を1時間に設定）→ archive される

### ログで確認

```
INFO session: created sess-20260418-xxxxxxxx (thread=1234567890, workspace=takumi/jobs/job-xxx)
INFO session: reusing sess-20260418-xxxxxxxx (thread=1234567890)
INFO session: archived sess-20260418-xxxxxxxx (reason=idle 7d)
```

---

## Non-goals（2.1 では扱わない）

- 並列セッション対応（2.5 で対応）
- repo structure の cache（2.2 で対応）
- skill の自動注入（2.3 で対応）
- 会話履歴の要約・蒸留（2.4 で対応）
- セッション間での情報共有（「別スレッドでやった件なんだけど」への対応は別設計）
- Hermes entries との関係整理（2.1 では独立。entries は従来通り job 単位で保存）

---

## Dependencies

実装に必要な外部:
- なし（既存の discord.py・file I/O のみ）

docs 更新:
- `docs/runbooks/session-management.md` を新設（ユーザー向け操作説明）
- `docs/operating-rules.md` に session ライフサイクルを追記
