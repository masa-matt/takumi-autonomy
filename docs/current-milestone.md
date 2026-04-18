# Current Milestone

## 現在の phase
Phase 1: ローカル sandbox 足場

## 完了済み checkpoint
- CP-00 仕様固定 — ✅ 通過
- CP-01 Job Sandbox 基盤 — ✅ 通過
- CP-02 Discord 受付とジョブ状態管理 — ✅ PoC 通過（2026-04-18）
- CP-04 Hermes Recall / Save 統合 — ✅ PoC 通過（2026-04-18）

## 現在の checkpoint
CP-LV2-03 Repo / File 取り込み — **部分完了、repo clone 連携が残り**

## 達成状況
- [x] ローカルファイルを inbox 経由で sandbox に渡せる
- [x] outbox で成果物を受け取れる（result.md 除外・スラグ名）
- [x] `clone_repo()` / `clone_local_repo()` の実装（`takumi/sandbox/ingress.py`）
- [ ] Discord からタスク内の URL を検出して自動クローン
- [ ] repo / file 取り込みルールの文書化

## 残タスク（CP-03 通過まで）
1. プロンプトに「URL があれば repos/ にクローンして作業」を追加（Claude Code 任せ方式）
2. `docs/runbooks/repo-and-file-ingress.md` 作成

## その後
- CP-05: 単一 repo 調査・修正・検証
- CP-06: 複数 repo 比較
- CP-07: PR 本文案・Review
- CP-08: 承認境界・停止条件・handoff 運用
- CP-09: V2 運用試験

## 今回まだ作り込まないもの
- 本番 repo への push / PR 自動実行
- IAM が必要なログ調査
- Hermes skill 承認フロー（approve/reject コマンド）
