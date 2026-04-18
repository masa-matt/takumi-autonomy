# Current Milestone

## 現在の phase
Phase 1: ローカル sandbox 足場

## 現在の checkpoint
CP-LV2-02 Discord 受付とジョブ状態管理 — **PoC 通過（2026-04-18）**

## この checkpoint の目的
Discord から依頼してジョブとして扱える状態にする。

## 達成状況
- [x] Discord から自然言語で依頼を受け取れる
- [x] job id を採番できる
- [x] job 状態を queued / running / blocked / done / failed で管理できる
- [x] 中間報告を返せる
- [x] 承認待ちメッセージを送れる
- [ ] `docs/runbooks/discord-ops.md`（未作成 — 次セッションで整備）

## 今回まだ作り込まないもの
- Hermes Recall / Save 統合
- 本番 repo への push / PR 自動実行
- IAM が必要なログ調査

## 次の checkpoint
CP-LV2-03 Repo / File 取り込み
