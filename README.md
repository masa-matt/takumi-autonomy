# Takumi Local Autonomy V2

Discord から自然言語で依頼できる、ローカル向けの安全な半自律作業代行基盤。

## 概要

V2 では、ローカル PC 本体を直接作業場にするのではなく、ジョブごとに隔離された sandbox workspace を作業場にすることを原則とします。

```
Discord (依頼) → Takumi Core (ジョブ化) → sandbox (作業) → Discord (報告)
```

## アーキテクチャ

```
takumi/
  core/      — Job 状態機械（queued/running/blocked/done/failed）
  discord/   — Discord Bot + ジョブ実行パイプライン
  sandbox/   — workspace 作成・ingress・egress
  jobs/      — 実行時 job workspaces（runtime、git 管理外）

inbox/       — ホスト側ファイル置き場（Docker volume mount 経由で Bot に渡す）
apps/        — V1 VPS Bot（稼働中、変更しない）
```

### Job 状態遷移

```
queued → running → done
  ↓         ↓
blocked   failed
  ↓
running → done / failed
```

| 状態    | 意味                       |
|---------|----------------------------|
| queued  | 受付、実行待ち             |
| running | 実行中                     |
| blocked | 危険操作につき承認待ち     |
| done    | 正常完了                   |
| failed  | 失敗                       |

## 必要なもの

- Python 3.11+
- `pip install discord.py anthropic`
- Discord Bot Token（[Discord Developer Portal](https://discord.com/developers/applications) で取得）
  - Message Content Intent を ON にすること
  - OAuth2 スコープ: `bot` + `applications.commands`
- Executor（どちらか）:
  - **Anthropic API**: `ANTHROPIC_API_KEY` を設定
  - **Claude Code（定額プラン）**: `claude` CLI インストール + `claude auth login`

## セットアップ

```bash
git clone https://github.com/<your-org>/takumi-autonomy.git
cd takumi-autonomy
pip install -r requirements.txt

cp .env.example .env
# .env に DISCORD_TOKEN と executor の設定を記入
```

### .env の設定

```env
DISCORD_TOKEN=your-discord-bot-token

# --- executor の選択（どちらか）---

# Anthropic API（従量課金）
ANTHROPIC_API_KEY=sk-ant-...
TAKUMI_EXECUTOR=api

# Claude Code CLI（定額プラン）
TAKUMI_EXECUTOR=claude-code
# ANTHROPIC_API_KEY は不要
```

### Claude Code（定額プラン）で動かす場合

Max / Pro プランのアカウントがあれば、API キーなしで動かせます。

```bash
# 1. Claude Code CLI をインストール
npm install -g @anthropic-ai/claude-code
# または Homebrew: brew install claude-code

# 2. ログイン（ブラウザが開く）
claude auth login

# 3. .env に設定
TAKUMI_EXECUTOR=claude-code

# 4. 起動
python -m takumi.discord.gateway
```

## 起動方法

### ローカル直接起動

```bash
# .env を読み込んで起動
export $(grep -v '^#' .env | xargs)
python -m takumi.discord.gateway
```

### Docker で起動

```bash
docker compose up -d
docker compose logs -f
```

## Discord コマンド

| コマンド | 動作 |
|---|---|
| `/task <内容>` | タスクを投入（推奨） |
| `@Takumi <内容>` | メンションでもタスク投入可 |
| `/status <job-id>` | job の現在状態を確認 |
| `/files` | inbox のファイル一覧を表示 |
| `/files <filename>` | 次のタスクにファイルを添付 |
| `/ping` | 死活確認 |

### 承認フロー

危険キーワード（`delete` / `push` / `token` / `production` 等）を含むタスクは、承認ボタンが表示されます。

```
/task push to production
→ 🔒 BLOCKED — [✅ 承認して実行] [❌ 却下]
```

### ファイルの渡し方

```bash
# 1. Mac でファイルを inbox/ に置く
cp ~/data.csv ~/development/takumi-autonomy/inbox/data.csv

# 2. Discord で
/files data.csv         # "data.csv を予約しました"
/task data.csv を分析して  # → input/data.csv を参照して実行
```

Docker 起動時は `./inbox:/app/inbox:ro` でマウントされます。  
ローカル直接起動時は `INBOX_DIR=./inbox` を環境変数に追加してください。

## ディレクトリ構造（実行時）

```
takumi/jobs/<job-id>/
  input/   — 取り込んだファイル（inbox からのコピー等）
  repos/   — clone した repo
  output/  — 生成物・diff
  logs/    — 実行ログ
  state/   — job 状態 JSON
```

## 開発

```bash
# 構文チェック
python -m py_compile takumi/discord/gateway.py takumi/discord/job_runner.py

# スタブモードで動作確認（API キー不要）
# ANTHROPIC_API_KEY を設定しない状態で起動すると [STUB] で応答する
DISCORD_TOKEN=your-token python -m takumi.discord.gateway
```

## V1 との違い

| 項目 | V1 (`apps/discord-bot/`) | V2 (`takumi/discord/`) |
|---|---|---|
| 稼働場所 | VPS（常駐） | ローカル PC |
| Job 状態 | PENDING/RUNNING/DONE/FAILED | queued/running/blocked/done/failed |
| 中間報告 | 完了後に一括 | 状態変化ごとにメッセージ編集 |
| 承認フロー | CLI プロンプト | Discord ボタン |
| コマンド | `!` プレフィックス | `/` スラッシュコマンド |
| ファイル共有 | なし | inbox volume mount |
| Workspace | `runtime/workspaces/jobs/` | `takumi/jobs/` |
