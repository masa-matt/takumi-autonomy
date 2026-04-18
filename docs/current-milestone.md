# Current Milestone

## 現在の phase
Phase 1 完了 → 実運用フェーズへ移行

## 完了済み checkpoint（全 CP 通過）
- CP-00 仕様固定 — ✅ 通過
- CP-01 Job Sandbox 基盤 — ✅ 通過
- CP-02 Discord 受付とジョブ状態管理 — ✅ PoC 通過（2026-04-18）
- CP-03 Repo / File 取り込み — ✅ PoC 通過（2026-04-18）
- CP-04 Hermes Recall / Save 統合 — ✅ PoC 通過（2026-04-18）
- CP-05 単一 repo 調査・修正・検証 — ✅ PoC 通過（2026-04-18）
- CP-06 複数 repo 比較と影響範囲整理 — ✅ PoC 通過（2026-04-18）
- CP-07 PR 本文案と PR Review — ✅ PoC 通過（2026-04-18）
- CP-08 承認境界・停止条件・handoff 運用 — ✅ PoC 通過（2026-04-18）
- CP-09 V2 運用試験 — ✅ PoC 通過（2026-04-18）

## 現在の状態
Phase 1 全チェックポイント通過。実運用継続 + V3 設計フェーズへ。

## 次の方向性: V3 設計
**Goal**: 単一 Takumi アイデンティティ + 共有 Hermes ブレイン + スレッド単位のセッション継続
詳細: [docs/v3-vision.md](./v3-vision.md)

最初の一歩（Phase 2.1）: スレッド = セッション化してワークスペースを再利用する
（現状の UX 問題「スレッド内で前の repo を忘れる」を直接解決）

## 残タスク（V2 スコープ）
- Hermes skill 承認フロー（approve/reject コマンド）
- CP-09 実運用での継続タスク処理（業務タスク3件以上）

## 今回作り込まないもの
- 本番 repo への push / PR 自動実行
- IAM が必要なログ調査
- 複数ユーザー・複数エージェントの並行運用
