# Retrospective: Phase 1 完了（2026-04-18）

## 何をやったか

1日のセッションで CP-00〜09 全チェックポイントの PoC 通過を達成。
Discord → Claude Code → Hermes のフルスタック統合を実装した。

---

## 良かったこと

- **Recall の設計**: `recent_always` パラメータで日本語の tokenization 問題を回避できた
- **SOUL.md の効果**: 人格注入により Claude Code の返答トーンが大きく改善された
- **executor_adapter の抽象化**: claude-code / api / stub の切り替えが env var だけで可能
- **プロンプト設計の進化**: repo 調査・比較・PR 支援・stop 条件を段階的に追加できた
- **checkpoint discipline**: PoC 通過の証拠を毎回記録したことで進捗が明確だった

---

## 改善できること

- **hermes-bridge.md 未作成**: CP-04 の成果物が1つ残っている。次セッションで対応
- **CP-09 の実運用検証**: インフラは完成したが、実際の業務タスク3件の処理が必要
- **スレッド内の会話履歴**: 現在は毎回ゼロから始まる。会話コンテキストの保持が課題
- **_is_task() のカバレッジ**: 日本語動詞パターンが漏れるケースあり。継続的に調整が必要

---

## 技術的な発見

- Docker コンテナで `claude auth login` はブラウザ OAuth が必要 → `docker exec -it` で手動実行
- `--output-format json` の結果は `{"result": "..."}` 形式で返る
- `subprocess.run` で claude を呼ぶ場合、PTY が必要な対話は `pexpect` が必要だった
- git の outbox を `git rm --cached` で管理外に戻す手順が必要だった

---

## 次フェーズへの提案

1. **実運用フェーズ（CP-09 継続）**: 業務タスクを Discord 経由で継続的に投げる
2. **hermes-bridge.md 作成**: CP-04 の唯一の未完成成果物
3. **skill 承認フロー**: 蓄積された skill draft を human がレビュー・承認する仕組み
4. **会話履歴**: スレッド内の発言を context として引き継ぐ仕組み（Hermes に保存）
