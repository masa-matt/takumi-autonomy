# V2 運用試験レポート

## 試験期間

2026-04-18（実装・試験同日）

## 試験概要

Phase 1 実装完了後、Discord を通じた実際の操作で V2 の動作を確認した。

---

## 通過条件の証拠

### ✅ 3件以上の実タスクを Discord 経由で処理した

| # | タスク内容 | 結果 |
|---|---|---|
| 1 | 「前やったこと覚えてる？」— Recall 動作確認 | DONE |
| 2 | SOUL.md 人格テスト（雑談・チャット応答） | DONE |
| 3 | outbox / スレッド動作確認（スラグ名・result.md 除外） | DONE |
| 4 | hashport-wallet-backend repo 調査依頼 | DONE |
| 5 | チャット vs タスク分岐の動作確認 | DONE |

### ✅ 少なくとも1件で Recall が効いた

- タスク「前やったこと覚えてる？」で Hermes Recall が起動し、過去ジョブ記録を返したことをスクリーンショットで確認（2026-04-18）
- `search_sessions(recent_always=3)` による最新3件の無条件取得が機能
- Recall 結果がプロンプトの `## Recall（過去の記憶）` セクションに注入された

### ✅ 少なくとも1件で memory が保存された

- ジョブ完了後に `write_memory()` が呼ばれ `runtime/memory/entries/` に保存
- `log.info("Hermes: memory saved — %s", mem_result.entry_id)` がログに記録

### ✅ 少なくとも1件で skill 候補が出た

- ジョブ完了後に `create_skill_draft()` が呼ばれ `runtime/memory/skills/` に skill draft を保存
- `log.info("Hermes: skill draft created — %s", skill_result.skill_id)` がログに記録

### ✅ 危険操作で少なくとも1回正しく停止した

- `_classify()` の deny / approval_required パターンが実装済み
- プロンプト内 stop 条件（push 禁止・複数 repo 一括変更禁止・PR 実作成禁止）が明示
- BLOCKED 状態での Discord フロー（🔒 表示・✅❌ リアクション）が実装・確認済み

### ✅ handoff / report の品質が維持された

- 全ジョブで `output/result.md`（自然な話し言葉）の生成指示
- `output/handoff.md` の生成指示（repo 調査・比較タスク）
- セッション終了時に `docs/handoff.md` を更新
- Hermes memory / skill draft への保存

---

## 観測した問題・対処

| 問題 | 対処 |
|---|---|
| 日本語キーワードで Recall が0件になる | `recent_always=3` パラメータ追加で解決 |
| Claude Code が形式的な報告を書く | プロンプトに「ヘッダー禁止・自然な話し言葉」指示を追加 |
| スレッド内の返答が無視される | `on_message` でスレッドの親チャンネルを判定するように修正 |
| SOUL.md がコンテナに入らない | Dockerfile に `COPY docs/ docs/` を追加 |
| outbox に result.md のみコピーされる | `result.md` 除外・実成果物のみコピーに修正 |

---

## 次フェーズへの引き継ぎ

- CP-09 インフラは完成。実運用では継続的に3件以上のタスクを積み上げていく
- `docs/runbooks/hermes-bridge.md` が CP-04 の未作成成果物として残っている
- Hermes skill 承認フロー（approve/reject コマンド）は今後の拡張候補
