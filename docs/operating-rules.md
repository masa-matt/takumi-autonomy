# Operating Rules — Takumi Local Autonomy V2

このドキュメントは Takumi の運用ルールをコード実装と対応させて明文化したもの。
CLAUDE.md の Non-negotiable rules をより具体的・実装参照可能な形で記述する。

---

## 1. タスク受付と分類

### 受付チャンネル
- `DISCORD_TASK_CHANNELS` 環境変数で指定されたチャンネルのみタスク受付
- `@mention` でも受け付ける（チャンネル外でも有効）
- 全メッセージはスレッドを作成してから返答

### タスク vs 雑談の分類
- `_is_task()` ヒューリスティック（日本語・英語の作業動詞パターン）で判定
- 雑談 → SOUL 人格で即時返答（job pipeline を通さない）
- タスク → job pipeline → Claude Code 実行

---

## 2. 実行前の危険度チェック

実装: `job_runner._classify(task)` → "deny" / "approval_required" / "auto_allow"

| 判定 | アクション |
|---|---|
| `deny` | 即座に FAILED（実行しない） |
| `approval_required` | BLOCKED（Discord で人間確認） |
| `auto_allow` | RUNNING → Claude Code 実行 |

詳細パターン一覧: `docs/runbooks/approval-and-stop-conditions.md`

---

## 3. sandbox の境界

- 1ジョブ = 1sandbox（`takumi/jobs/<job_id>/`）
- Claude Code は `--add-dir <workspace>` で sandbox 内のみに制限
- ホストへの書き戻し・元 repo への push は行わない
- 成果物は `output/` → `outbox/<slug>/` にのみ出力

---

## 4. Claude Code への制御

プロンプト（`_build_workspace_prompt`）で明示する stop 条件:

| 操作 | 指示 |
|---|---|
| 元 repo への push / PR 作成 | 実行しない → output/result.md に報告して止まる |
| 複数 repo 一括変更 | 実行しない → what-to-change を報告して止まる |
| PR 草案 | output/pr-draft.md に保存して止まる |
| sandbox 外への書き込み | --add-dir で物理的に制限 |

---

## 5. handoff の義務

- 各ジョブで `output/handoff.md` を残す（Claude Code への指示）
- 大きなセッション終了時は `docs/handoff.md` を更新する（人間または Takumi）
- `output/changes.diff` に変更差分を保存する（変更があれば）

---

## 6. Hermes（記憶）

- ジョブ完了後に `write_memory()` → `runtime/memory/entries/` に保存
- 次回ジョブ開始時に `search_sessions()` で過去記録を検索（recent_always=3）
- skill 候補は `create_skill_draft()` で `runtime/memory/skills/` に保存

---

## 7. 承認フロー（BLOCKED 時）

```
BLOCKED になった場合:
  1. Discord に "確認が必要" メッセージ（🔒 絵文字・オレンジ Embed）
  2. ✅ リアクション → resume_job(approved=True) → RUNNING
  3. ❌ リアクション → resume_job(approved=False) → FAILED
```

実装: `gateway.py` の BLOCKED ハンドリング、`job_runner.resume_job()`

---

## 8. スコープ外（実装しない）

- 本番 repo への push / PR 自動実行
- IAM が必要なログ調査
- Hermes skill 承認フロー（approve/reject コマンド）
- 複数ユーザー・複数エージェントの並行運用
