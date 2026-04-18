# Current Milestone

## 現在の phase
Phase 1: ローカル sandbox 足場

## 現在の checkpoint
CP-LV2-04 Hermes Recall / Save 統合 — **PoC 通過（2026-04-18）**

## この checkpoint の目的
毎回ゼロから始めない状態を作る。

## 達成状況
- [x] CP-00/01/02/03 通過済み
- [x] `takumi/hermes/` 作成（memory / skill / models）
- [x] `search_sessions` が呼べる（Recall: プロンプト注入）
- [x] `write_memory` が呼べる（Save: job 完了後）
- [x] `create_skill_draft` が呼べる（Save: job 完了後）
- [x] `runtime/` volume を docker-compose に追加
- [x] Discord で `/task 前やったこと覚えてる？` → Recall が効くことを確認（2026-04-18）

## 今回まだ作り込まないもの
- Hermes skill の承認フロー（approve/reject）
- 本番 repo への push / PR 自動実行
- IAM が必要なログ調査

## 次の checkpoint
CP-LV2-05 単一 repo 調査・修正・検証

## 次セッションでやること
1. `docs/runbooks/hermes-bridge.md` を作成して CP-04 成果物を整える
2. CP-05: 単一 repo を Discord から渡して調査・修正・検証の流れを作る
