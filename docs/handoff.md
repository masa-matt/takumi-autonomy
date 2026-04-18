# Handoff

## Session Goal
Claude Code executor を Docker コンテナ内で OAuth 認証し、Discord からタスクを実行できる状態にする（CP-02 PoC 完了）

## Current Checkpoint
CP-LV2-02 Discord 受付とジョブ状態管理 — **PoC 通過**

## Context Read
- `.claude/CLAUDE.md`
- `docs/checkpoints.md`
- `docs/current-milestone.md`

## Done

### 認証基盤（新規）
- `scripts/sync_claude_auth.py`: macOS Keychain → コンテナへの OAuth 認証情報同期スクリプト
  - 有効期限チェック → 期限内はスキップ
  - 期限切れ → リフレッシュトークンで自動更新（`https://platform.claude.com/v1/oauth/token`）
  - リフレッシュ失敗 → Keychain アクセス（パスワードダイアログ）でフォールバック
- `start.sh`: `docker compose build && up && sync_claude_auth.py` を一括実行

### Dockerfile / docker-compose
- 非 root ユーザー `takumi` (UID 1000) を追加（`--dangerously-skip-permissions` が root 禁止のため）
- `claude_auth` volume のマウント先を `/root/.claude` → `/home/takumi/.claude` に変更
- `./outbox:/app/outbox` volume を追加

### Discord → Claude Code パイプライン修正
- `claude --print <prompt>` → `claude -p <prompt>` に修正（`--print` は入力待機しない）
- `--dangerously-skip-permissions` を追加（非 root 環境で有効）
- inbox auto-include: タスク実行時に inbox の全ファイルを自動で `input/` へ（明示予約廃止）
- outbox auto-copy: job 完了時に `output/` を `outbox/<job_id>/` へ自動コピー
- `/files` コマンド: 予約機能廃止 → inbox / outbox の両方を一覧表示

### 判明した制約（重要）
- `claude auth login` はコンテナ（Linux）で stdin を待機せずに即 exit 0 する設計
  → ブラウザコールバックはローカル HTTP サーバー前提（Linux 非 GUI 環境では機能しない）
  → 対応策: Keychain からの直接コピー + リフレッシュトークンによる自動更新

## Not Done
- `docs/runbooks/discord-ops.md`（CP-02 成果物）
- BLOCKED 状態の承認フローの実 PoC（実装済み、未テスト）
- Hermes Recall / Save 統合（CP-04）
- Repo clone・取り込みフロー（CP-03）

## Files Changed
- `Dockerfile` — 非 root ユーザー追加
- `docker-compose.yml` — outbox volume、claude_auth マウント先変更
- `takumi/discord/gateway.py` — inbox auto-include、outbox auto-copy、/files 簡素化、auth フロー更新
- `takumi/discord/job_runner.py` — `claude -p <prompt>` 修正、`--dangerously-skip-permissions` 追加
- `takumi/sandbox/ingress.py` — `OUTBOX_DIR`、`copy_all_inbox()`、`copy_to_outbox()` 追加
- `scripts/sync_claude_auth.py` — 新規: Keychain 同期 + トークンリフレッシュ
- `start.sh` — 新規: 起動ワンライナー

## Validation
- `docker exec takumi-bot claude auth status` → `loggedIn: true` ✅
- `/task 元気？` → done、result.md が Discord に返る ✅
- `/task hello.py を output/ に作成して` → done、`takumi/jobs/<id>/output/hello.py` 生成 ✅
- `/files` → `/task 添付ファイルを読んで要約して` → inbox の PDF が自動で input/ に渡る ✅
- トークン期限切れ時の自動リフレッシュ ✅

## Risks / Concerns
- OAuth トークンのリフレッシュエンドポイント・Client ID はバイナリから逆引き（公式未文書）
  → Claude Code のバージョンアップで変わる可能性あり
- `--dangerously-skip-permissions` は sandbox 境界（`--add-dir`）に依存して安全性を担保している
  → `--add-dir` の指定が正しくないと sandbox 外への書き込みが可能になる

## Approval Needed
- 次 checkpoint 以降の本格実装前に Hermes 連携設計の確認

## Memory Candidates
- `claude auth login` は Linux コンテナで stdin を待機しない（設計上の制約）
- リフレッシュエンドポイント: `https://platform.claude.com/v1/oauth/token`、Client ID: `9d1c250a-e61b-44d9-88ed-5944d1962f5e`
- `--dangerously-skip-permissions` は root では使用不可（Claude Code のセキュリティ制約）

## Skill Candidates
- `sync_claude_auth`: macOS Keychain → Docker コンテナへの Claude Code OAuth 同期

## Suggested Next Step
1. `docs/runbooks/discord-ops.md` を作成して CP-02 成果物を整える
2. BLOCKED フロー（承認待ち → approve/reject）を実際に Discord でテスト
3. CP-03: inbox からのファイル取り込み + repo clone フローの実装・検証
