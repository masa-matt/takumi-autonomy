# Current Milestone

## 現在の phase
Phase 1: ローカル sandbox 足場

## 完了済み checkpoint
- CP-00 仕様固定 — ✅ 通過
- CP-01 Job Sandbox 基盤 — ✅ 通過
- CP-02 Discord 受付とジョブ状態管理 — ✅ PoC 通過（2026-04-18）
- CP-03 Repo / File 取り込み — ✅ PoC 通過（2026-04-18）
- CP-04 Hermes Recall / Save 統合 — ✅ PoC 通過（2026-04-18）
- CP-05 単一 repo 調査・修正・検証 — ✅ PoC 通過（2026-04-18）
- CP-06 複数 repo 比較と影響範囲整理 — ✅ PoC 通過（2026-04-18）

## 現在の checkpoint
CP-LV2-07 PR 本文案と PR Review — **PoC 通過（2026-04-18）**

## 達成状況
- [x] プロンプトに PR 支援手順（タイトル案・本文案・review コメント草案・stop 条件）を追加
- [x] `docs/runbooks/pr-workflow.md` 作成
- [x] `docs/templates/pr-body.md` 作成
- [x] `docs/templates/pr-review.md` 作成

## 次の checkpoint
CP-LV2-08 承認境界・停止条件・handoff 運用

## その後
- CP-09: V2 運用試験

## 今回まだ作り込まないもの
- 本番 repo への push / PR 自動実行
- IAM が必要なログ調査
- Hermes skill 承認フロー（approve/reject コマンド）
