# Handoff

## Session Goal
Discord UX の改善（自然チャット・スレッド・SOUL.md 人格）と CP ドキュメントの整備。

## Current Checkpoint
CP-LV2-03 Repo / File 取り込み — **部分完了、repo clone 連携が残り**

## 完了済み CP
| CP | 内容 | 通過日 |
|---|---|---|
| CP-00 | 仕様固定 | 2026-04-18 |
| CP-01 | Job Sandbox 基盤 | 2026-04-18 |
| CP-02 | Discord 受付・Job 状態 | 2026-04-18 |
| CP-04 | Hermes Recall / Save | 2026-04-18 |

## Done（このセッション）

### Discord UX 全面改善
- `DISCORD_TASK_CHANNELS` 環境変数で指定したチャンネルでは `/task` 不要
- 普通のメッセージ → スレッドを作成して返答
- スレッド内の続きのメッセージにも応答（`on_message` でスレッド親チャンネルを判定）
- 雑談（`_is_task()` = False）→ Claude Code 直接呼び出し、SOUL 人格で一言返す
- 作業依頼 → スレッド内でジョブ実行、自然な口調で報告

### SOUL.md 人格
- `docs/SOUL.md` 新規作成（Takumi Shin の人格定義）
- `Dockerfile` に `COPY docs/ docs/` を追加（コンテナに含める）
- `job_runner.py` の `_build_workspace_prompt()` 先頭に SOUL.md を注入
- `_run_chat_reply()` でも SOUL.md を使った即時返答

### result.md フォーマット改善
- 「要約・受信メッセージ・応答・備考」形式を廃止
- プロンプトに「Markdown ヘッダー禁止・自然な話し言葉で書け」を追加

### outbox スラグ化
- `copy_to_outbox(ws, dirname)` — 引数を job_id → dirname に変更
- outbox ディレクトリ名: `job-20260418-xxx/` → `0418-タスク名/`
- `result.md` のみの場合は outbox に出力しない（作業ログ扱い）

### その他
- `.env.example` に `DISCORD_TASK_CHANNELS` 等の新環境変数を追加
- `outbox/` を git 管理から除外

## Not Done
- CP-03 repo clone の Discord 連携（プロンプト追加 or パイプライン制御）
- `docs/runbooks/repo-and-file-ingress.md`
- `docs/runbooks/hermes-bridge.md`
- CP-05〜09

## Files Changed
- `Dockerfile` — `COPY docs/ docs/` 追加
- `docs/SOUL.md` — 新規
- `docs/checkpoints.md` — CP-00/01/02/04 通過マーク、CP-03 部分完了を明記
- `docs/current-milestone.md` — 現在地更新
- `docs/handoff.md` — 本ファイル
- `.env.example` — 新環境変数追加
- `takumi/discord/gateway.py` — タスクチャンネル・スレッド・雑談分岐・outbox スラグ
- `takumi/discord/job_runner.py` — SOUL.md 注入・result.md 指示改善
- `takumi/sandbox/ingress.py` — `copy_to_outbox(dirname)` に変更

## Suggested Next Step
1. CP-03 完了: `_build_workspace_prompt()` に「URL があれば repos/ にクローンして作業」追加
2. `docs/runbooks/repo-and-file-ingress.md` 作成
3. CP-03 通過確認: Discord で GitHub URL を含むタスクを投げてクローン→調査が動くか確認
4. CP-05 へ進む

## Memory Candidates
- `DISCORD_TASK_CHANNELS` を設定しないと自然チャットが動かない
- SOUL.md はビルド時にイメージに焼き込む（volume ではない）→ 変更時は再ビルド必要
- `_is_task()` のパターンに含まれない日本語動詞は雑談と判定される（調整可能）
- スレッド内の会話は会話履歴を持たない（毎回 SOUL.md のみ）
