# Runbook: Hermes Recall / Save 統合（CP-04）

## 概要

Hermes はファイルベースの記憶システム。ジョブ実行結果を蓄積し、次回以降のジョブに過去の文脈を渡す。

**ループ**: ジョブ開始時に Recall → プロンプトに注入 → 実行 → 完了後に Save

---

## ディレクトリ構造

```
runtime/
  memory/
    entries/   ← ジョブ記録（mem-YYYYMMDD-XXXXXXXX.json）
    skills/    ← スキル草案（skill-YYYYMMDD-XXXXXXXX.json）
```

`runtime/` は `docker-compose.yml` で volume mount 済み。コンテナ再起動しても消えない。

環境変数で変更可能:
- `HERMES_ENTRIES_DIR` — entries ディレクトリのパス
- `HERMES_SKILLS_DIR` — skills ディレクトリのパス

---

## Recall（検索）

### `search_sessions(query, top_k=3, recent_always=3)`

ジョブ開始時に `job_runner._build_recall_context()` が呼ぶ。

**動作**:
1. キーワードマッチ: query を単語分割し、過去エントリの task + output_summary と Jaccard 類似度を計算
2. 直近 N 件を無条件で追加（`recent_always`）— 日本語のように単語分割が難しい場合でも文脈が途切れない
3. 両者を合わせて返す（重複除去）

**返す情報**:
```
[スコア:0.5] 2026-04-18 / repo の調査をして
  → repos/myapp を調べた。pytest が...
[直近] 2026-04-18 / こんにちは
  → こんにちは！何か手伝えることはある？
```

### `search_skills(query, top_k=3)`

`status == "approved"` のスキルのみ返す。草案（draft）は検索対象外。

---

## Save（保存）

### `write_memory(job, output, danger_level)`

ジョブ完了後に `job_runner._save()` が呼ぶ。

**保存しない条件**:
- `output` が None（実行失敗）
- output に機密パターンが含まれる（token / password / secret / api key 等）

**保存先**: `runtime/memory/entries/mem-YYYYMMDD-XXXXXXXX.json`

```json
{
  "entry_id": "mem-20260418-a1b2c3d4",
  "job_id": "job-20260418-xxxxxxxx",
  "task": "repos/myapp のテストを調べて",
  "status": "done",
  "output_summary": "pytest を走らせたら...",
  "danger_level": "auto_allow",
  "tags": ["done", "auto_allow"],
  "saved_at": "2026-04-18T12:34:56+00:00"
}
```

### `create_skill_draft(job, output)`

ジョブが `DONE` の場合のみ、スキル草案を作成。

**保存先**: `runtime/memory/skills/skill-YYYYMMDD-XXXXXXXX.json`

```json
{
  "skill_id": "skill-20260418-a1b2c3d4",
  "name": "repos_myapp_テストを調べて",
  "status": "draft",
  "trigger_keywords": ["repos", "myapp", "テスト", "調べ"],
  "procedure_summary": "pytest を走らせたら...",
  "source_job_id": "job-20260418-xxxxxxxx"
}
```

草案は `status: "draft"` のまま蓄積される。`search_skills` では返さない。
承認（`status: "approved"` に変更）は人間が手動で行う（将来的に approve コマンドで対応予定）。

---

## ジョブパイプライン内の位置

```
run_job(task)
  ↓
_build_recall_context(task)        ← search_sessions + search_skills
  ↓
_build_workspace_prompt(...)       ← Recall をプロンプトに注入
  ↓
executor_adapter.execute(job, ws)  ← Claude Code 実行
  ↓
_save(job, output, danger)         ← write_memory + create_skill_draft
```

---

## ログで確認する方法

```bash
# Hermes の保存・スキップをリアルタイムで確認
docker compose logs -f takumi | grep "Hermes"

# 出力例
# INFO  Hermes: memory saved — mem-20260418-a1b2c3d4
# DEBUG Hermes: memory skip — output matches sensitive pattern: '\\btoken\\b'
# INFO  Hermes: skill draft created — skill-20260418-b2c3d4e5
```

```bash
# 保存されたエントリを直接確認
ls runtime/memory/entries/
cat runtime/memory/entries/mem-20260418-a1b2c3d4.json

# スキル草案を確認
ls runtime/memory/skills/
cat runtime/memory/skills/skill-20260418-b2c3d4e5.json
```

---

## スキルの承認手順（手動）

```bash
# draft → approved に変更（jq が使える場合）
jq '.status = "approved"' runtime/memory/skills/skill-YYYYMMDD-XXXXXXXX.json \
  > /tmp/skill.json && mv /tmp/skill.json runtime/memory/skills/skill-YYYYMMDD-XXXXXXXX.json

# 次回 search_skills() でヒットするようになる
```

将来: Discord の `!approve skill-xxx` コマンドで対応予定。

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| Recall が0件 | entries/ が空 / タスクが初回 | 正常。実行を重ねると蓄積される |
| Recall にスコアなし（[直近]のみ） | キーワードが一致しない（日本語等） | `recent_always=3` で直近は常に取得されるので許容 |
| memory が保存されない | output に機密パターンが含まれる | ログの `memory skip` を確認してパターンを確認 |
| skill が検索に出ない | status が draft のまま | 手動で approved に変更するか、将来の承認コマンドを待つ |
| runtime/memory/ が消える | volume mount がない | `docker-compose.yml` の volumes 設定を確認 |
