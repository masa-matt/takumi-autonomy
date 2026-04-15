# Takumi Local Autonomy V2 — アーキテクチャ設計書

**対象バージョン:** V2  
**最終更新:** 2026-04-15  
**ステータス:** Phase 1 実装中（CP-LV2-03 完了）

---

## 1. 設計思想

### 基本方針

| 原則 | 内容 |
|---|---|
| **1ジョブ1Sandbox** | 作業は必ず `takumi/jobs/<job-id>/` に閉じる |
| **Host is not workspace** | ローカルPC本体を直接作業場にしない |
| **Copy-in / Copy-out** | ファイルは sandbox にコピーして受け取り、成果物は output で返す |
| **承認境界の明示** | 危険操作は必ず止まってユーザーに判断を委ねる |
| **Executor は差し替え可能** | Anthropic API / Claude Code CLI / Stub を同一インターフェースで扱う |

### 「作業を sandbox に閉じる」はできるか？

**Yes。Claude Code CLI では以下のフラグで実現する:**

```bash
claude \
  --print \
  --cwd takumi/jobs/<job-id>/ \      # 作業ディレクトリを workspace に設定
  --add-dir takumi/jobs/<job-id>/ \  # ファイルアクセスを workspace 内に限定
  "<workspace context + task>"
```

| フラグ | 効果 | 制約レベル |
|---|---|---|
| `--cwd` | 作業ディレクトリを workspace に固定 | ソフト（設計的） |
| `--add-dir` | ファイル R/W を workspace 内に限定 | ソフト（設計的） |
| Docker per-job | workspace だけをマウントしたコンテナで実行 | ハード（OS レベル） |

**V2 Phase 1 の方針:** `--cwd` + `--add-dir` + プロンプト制約で十分。  
完全分離が必要になった場合は Docker per-job へ移行する（CP-LV2-09 以降で検討）。

---

## 2. コンポーネント構成

```
Discord (入口)
    ↓  /task <内容> または @Takumi <内容>
┌─────────────────────────────────────┐
│  gateway.py                         │
│  - スラッシュコマンド受付           │
│  - Job 状態を Discord に中間報告     │
│  - BLOCKED 時に承認ボタンを表示     │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  job_runner.py                      │
│  - 危険度判定（deny/approval/allow）│
│  - run_job() / resume_job()         │
│  - executor への委譲                │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  executor (_execute)                │
│  - stub   : [STUB] 応答             │
│  - api    : Anthropic API           │
│  - claude-code : Claude Code CLI    │
│      --cwd workspace/               │
│      --add-dir workspace/           │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  sandbox workspace                  │
│  takumi/jobs/<job-id>/              │
│    input/   ← 取り込んだファイル    │
│    repos/   ← clone した repo       │
│    output/  ← 成果物・diff          │
│    logs/    ← 実行ログ              │
│    state/   ← job 状態 JSON         │
└─────────────────────────────────────┘
               ↓
Discord (報告)  /  egress (成果物回収)
```

---

## 3. Job 状態機械

```
queued → running → done
  ↓         ↓
blocked   failed
  ↓
running → done / failed
```

| 状態 | 意味 | Discord 表示 |
|---|---|---|
| queued | 受付、実行待ち | 📥 |
| running | 実行中 | 🔄 |
| blocked | 危険操作につき承認待ち | 🔒 |
| done | 正常完了 | ✅ |
| failed | 失敗 | ❌ |

状態は `takumi/jobs/<job-id>/state/job.json` に永続化される。

---

## 4. Executor 設計

### 選択方法

`TAKUMI_EXECUTOR` 環境変数で切り替える。

| `TAKUMI_EXECUTOR` | 動作 | 必要な設定 |
|---|---|---|
| 未設定（`ANTHROPIC_API_KEY` あり） | api モード | `ANTHROPIC_API_KEY` |
| 未設定（`ANTHROPIC_API_KEY` なし） | stub モード | なし |
| `api` | Anthropic API | `ANTHROPIC_API_KEY` |
| `claude-code` | Claude Code CLI | `claude` コマンド + ログイン済み |

### claude-code モードの詳細

```python
# takumi/discord/job_runner.py

def _execute_claude_code(job: Job) -> str:
    workspace = get_workspace(job.job_id)
    prompt = _build_workspace_prompt(job.task, workspace)

    subprocess.run([
        "claude", "--print", "--output-format", "json",
        "--cwd",     str(workspace.path),
        "--add-dir", str(workspace.path),
        prompt,
    ], timeout=300)
```

`_build_workspace_prompt()` が Claude Code に渡すプロンプト:

```
作業ディレクトリ: /path/to/takumi/jobs/<job-id>/
構造:
  input/  : 入力ファイル（読み取り専用）
  repos/  : clone した repo
  output/ : 成果物の書き出し先
  logs/   : 実行ログ

制約:
- ワークスペース外には書き込まないこと
- 成果物は output/ に保存すること
- 完了したら output/result.md に要約を書くこと

タスク: <job.task>
```

### 危険度判定

`_classify(task)` が判定し、状態遷移を制御する。

| 分類 | 例 | 動作 |
|---|---|---|
| `deny` | `rm -rf`, `curl\|bash`, `/etc/shadow` | 即 FAILED |
| `approval_required` | `delete`, `push`, `token`, `production` | BLOCKED → 承認待ち |
| `auto_allow` | その他 | RUNNING → 実行 |

---

## 5. ファイル共有（inbox）

```
ホスト（Mac）: inbox/data.csv を置く
    ↓ Docker volume mount (read-only)
コンテナ: /app/inbox/data.csv
    ↓ /files data.csv コマンド
sandbox: takumi/jobs/<job-id>/input/data.csv
    ↓ executor が参照
output/result.md に結果
```

コマンド:
- `/files` — inbox の一覧表示
- `/files <filename>` — 次のタスクに添付予約
- `/task <内容>` — 予約済みファイルを input/ にコピーしてタスク実行

---

## 6. Docker 構成

### Dockerfile（V2）

```dockerfile
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY takumi/ takumi/
COPY packages/ packages/

RUN mkdir -p takumi/jobs inbox

CMD ["python", "-m", "takumi.discord.gateway"]
```

### docker-compose.yml

```yaml
services:
  takumi-bot:
    build: .
    env_file: .env
    volumes:
      - ./takumi/jobs:/app/takumi/jobs    # job workspaces（永続化）
      - ./inbox:/app/inbox:ro             # inbox（read-only）
      - ~/.claude:/root/.claude:ro        # Claude Code 認証情報（claude-code mode 時）
    restart: unless-stopped
```

### ローカル直接起動（Docker なし）

```bash
# claude auth login 済みの Mac 上で直接起動
TAKUMI_EXECUTOR=claude-code \
DISCORD_TOKEN=your-token \
python -m takumi.discord.gateway
```

`~/.claude` の認証情報を直接使うため、Docker 不要で最もシンプル。

---

## 7. ディレクトリ構造

```
takumi-autonomy/
├── takumi/                     ← V2 実装
│   ├── core/
│   │   └── job_state.py        — Job 状態機械
│   ├── discord/
│   │   ├── gateway.py          — Discord Bot（スラッシュコマンド + 承認UI）
│   │   └── job_runner.py       — ジョブ実行パイプライン + executor
│   └── sandbox/
│       ├── workspace.py        — workspace ライフサイクル
│       ├── ingress.py          — ファイル / repo 取り込み
│       └── egress.py           — 成果物回収
├── takumi/jobs/                ← 実行時 job workspaces（git 管理外）
│   └── job-YYYYMMDD-xxxxxxxx/
│       ├── input/
│       ├── repos/
│       ├── output/
│       ├── logs/
│       └── state/job.json
├── inbox/                      ← ユーザーがファイルを置く場所
├── docs/
│   ├── design/
│   │   └── v2-architecture.md  ← このファイル
│   ├── checkpoints.md
│   └── runbooks/
├── apps/                       ← V1（VPS 稼働中、変更しない）
├── Dockerfile                  ← V2 用に修正済み
├── docker-compose.yml
└── README.md
```

---

## 8. チェックポイントロードマップ

| CP | 内容 | 状態 |
|---|---|---|
| CP-LV2-00 | V2 仕様固定 | ✅ 完了 |
| CP-LV2-01 | Sandbox workspace 基盤 | ✅ 完了 |
| CP-LV2-02 | Discord 受付 + 5状態 + 承認ボタン + スラッシュコマンド | ✅ 完了 |
| CP-LV2-03 | inbox volume mount + File ingress | ✅ 完了 |
| **Fix** | Dockerfile V2 化 + claude-code executor sandbox 対応 | ✅ 完了 |
| CP-LV2-04 | Hermes Recall / Save 統合 | 未着手 |
| CP-LV2-05 | 単一 repo 調査・修正・検証 | 未着手 |
| CP-LV2-06 | 複数 repo 比較と影響範囲整理 | 未着手 |
| CP-LV2-07 | PR 本文案 / PR Review | 未着手 |
| CP-LV2-08 | 承認境界・停止条件・handoff 運用 | 未着手 |
| CP-LV2-09 | Trial run | 未着手 |

---

## 9. 環境変数リファレンス

| 変数 | 必須 | 説明 |
|---|---|---|
| `DISCORD_TOKEN` | ✅ | Discord Bot トークン |
| `TAKUMI_EXECUTOR` | — | `api` / `claude-code` / 未設定（→ stub or api） |
| `ANTHROPIC_API_KEY` | `api` モード時 | Anthropic API キー |
| `INBOX_DIR` | — | inbox パス（デフォルト: `/app/inbox`）。ローカル実行時は `./inbox` を設定 |

---

## 10. 承認境界

以下の操作は実行前に必ず止まる（BLOCKED 状態）:

- `delete` を含む操作
- `push` / `deploy`
- `token` / `secret` / `password` を扱う操作
- `production` 環境への操作
- `drop table` 等の DDL

以下は即時 FAILED（実行しない）:

- `rm -rf` 系
- `curl | bash` / `wget | bash`
- `/etc/shadow` へのアクセス
- fork bomb パターン
