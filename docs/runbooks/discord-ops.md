# Discord Ops Runbook — V2 Discord Bot の操作手順

## 概要

Takumi Local Autonomy V2 の Discord Bot（`takumi/discord/gateway.py`）は、
V1 VPS Bot（`apps/discord-bot/`）とは独立したローカル稼働の Bot です。

V2 Bot の特徴:
- Job 状態を 5 段階で管理し、Discord 上で中間報告を行う
- 危険操作（push / delete / secret 等）は BLOCKED 状態に遷移し、承認ボタンを表示する
- すべての job が `takumi/jobs/<job-id>/` に workspace を持つ

---

## Job 状態

```
queued  →  running  →  done
   ↓          ↓
blocked    failed
   ↓
running → done / failed
```

| 状態    | 意味                         | Discord 表示 |
|---------|------------------------------|--------------|
| queued  | タスク受付、実行待ち          | 📥 Queued…  |
| running | 実行中                       | 🔄           |
| blocked | 承認待ち（承認ボタン表示）    | 🔒           |
| done    | 正常完了（緑 Embed）          | ✅           |
| failed  | 失敗（赤 Embed）              | ❌           |

---

## コマンド

| 方法              | 書き方                          | 動作 |
|-------------------|---------------------------------|------|
| メンション（推奨）| `@Takumi <タスク内容>`          | タスク投入 |
| プレフィックス    | `!task <タスク内容>`            | タスク投入 |
| 状態確認          | `!status job-20260415-xxxxxxxx` | job 状態を Embed で返す |
| 死活確認          | `!ping`                         | Pong + latency |

---

## 起動方法

```bash
# ローカルで直接起動
cd /path/to/takumi-autonomy
DISCORD_TOKEN=xxx python -m takumi.discord.gateway

# または
python takumi/discord/gateway.py
```

### 環境変数

| 変数              | 必須 | 説明 |
|-------------------|------|------|
| `DISCORD_TOKEN`   | ✅   | Discord Bot トークン |
| `ANTHROPIC_API_KEY` | —  | 未設定ならスタブモード（開発・検証用） |

---

## 承認フロー（BLOCKED 状態）

危険キーワード（delete / push / token / secret / production 等）を含むタスクは  
自動的に BLOCKED 状態に遷移し、Discord に承認ボタンを表示します。

```
ユーザー: @Takumi push to production
Bot:      🔒 job-xxx — BLOCKED
          Block reason: This task requires approval before execution.
          [✅ 承認して実行]  [❌ 却下]
```

- **承認**: RUNNING → 実行 → DONE/FAILED
- **却下**: FAILED（error: Rejected by user.）
- **5分タイムアウト**: 自動的に却下扱い

---

## DENY（実行禁止）

`rm -rf`、`curl|bash`、`/etc/shadow` 等の即時危険パターンは  
BLOCKED にも遷移せず、直接 FAILED になります。

```
ユーザー: @Takumi rm -rf /tmp
Bot:      ❌ job-xxx — FAILED
          Error: Denied: task matched a forbidden pattern
```

---

## 危険度分類ルール

`takumi/discord/job_runner.py` の `_classify()` が判定します。

| 分類               | 例 | 動作 |
|--------------------|----|------|
| `deny`             | `rm -rf`, `curl\|bash` | 即 FAILED |
| `approval_required`| `delete`, `push`, `token`, `production` | BLOCKED → 承認待ち |
| `auto_allow`       | その他 | RUNNING → 実行 |

---

## V1 との違い

| 項目 | V1（`apps/discord-bot/`）| V2（`takumi/discord/`）|
|------|--------------------------|------------------------|
| 稼働場所 | VPS（常駐） | ローカル PC |
| Job 状態 | PENDING/RUNNING/DONE/FAILED | queued/running/blocked/done/failed |
| 中間報告 | なし（完了後に一括） | 状態変化ごとにメッセージ編集 |
| 承認フロー | CLI プロンプト or auto-approve | Discord ボタン |
| Workspace | `runtime/workspaces/jobs/` | `takumi/jobs/` |

---

## トラブルシューティング

### Bot が起動しない
```
RuntimeError: DISCORD_TOKEN 環境変数が設定されていません
```
→ `.env` の `DISCORD_TOKEN` を確認してください。

### Message Content Intent エラー
```
discord.errors.PrivilegedIntentsRequired
```
→ Discord Developer Portal → Bot → **Message Content Intent を ON** にしてください。

### スタブモードになる
```
[STUB] タスクを受け付けました: ...
```
→ `ANTHROPIC_API_KEY` が未設定です。API を使う場合は `.env` に設定してください。
