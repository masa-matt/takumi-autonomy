# Handoff

## Session Goal
Hermes Recall / Save を V2 に統合し、CP-04 の実装を完了する。

## Current Checkpoint
CP-LV2-04 Hermes Recall / Save 統合 — **実装完了、Discord テスト待ち**

## Context Read
- `.claude/CLAUDE.md`
- `docs/checkpoints.md`
- `docs/current-milestone.md`
- `docs/handoff.md`（前回）

## Done

### CP-00/01/02 完了マーク
- `docs/checkpoints.md`: CP-00/01/02 の通過条件をすべて `[x]` に更新（通過日 2026-04-18）

### takumi/hermes/ 作成（新規）
- `takumi/hermes/__init__.py`: `search_sessions`, `write_memory`, `create_skill_draft`, `search_skills` をエクスポート
- `takumi/hermes/models.py`: MemoryEntry / SearchHit / SearchResult / SaveResult / Skill / SkillResult（外部依存なし）
- `takumi/hermes/memory.py`: V1 `memory_api.py` + `session_search_api.py` を V2 Job 型に適合させて移植
  - ストレージ: `runtime/memory/entries/*.json`（`HERMES_ENTRIES_DIR` env で上書き可）
  - センシティブパターンガード（token / password / secret 等）
  - キーワード Jaccard スコアで上位 3 件を返す
- `takumi/hermes/skill.py`: V1 `skill_api.py` を V2 Job 型に適合させて移植
  - ストレージ: `runtime/memory/skills/*.json`（`HERMES_SKILLS_DIR` env で上書き可）
  - DRAFT → APPROVED の承認フロー（まだ Discord コマンド未接続）

### job_runner.py に Recall / Save を統合
- `_build_recall_context(task)`: `search_sessions` + `search_skills` を呼び、プロンプトに注入するテキストを生成
- `_build_workspace_prompt()`: Recall セクションを追加（ヒット 0 件の場合は省略）
- `_save(job, output, danger_level)`: job 完了後に `write_memory` + `create_skill_draft` を呼ぶ
  - `run_job`: auto_allow パスで `_save(job, output, danger)` を呼ぶ
  - `resume_job`: 承認後実行パスで `_save(job, output, "approval_required")` を呼ぶ
  - 例外は WARNING でログに落とすだけ（Hermes 失敗で job 失敗にしない）

### docker-compose.yml
- `./runtime:/app/runtime` volume を追加（コンテナ再起動後もメモリが保持される）

## Not Done
- Discord で `/task 前やったこと覚えてる？` を実際にテストして CP-04 通過確認
- skill approve/reject の Discord コマンド
- `docs/runbooks/hermes-bridge.md`（CP-04 成果物）
- Repo clone・取り込みフロー（CP-03）
- CP-05: 単一 repo 調査・修正・検証

## Files Changed
- `docs/checkpoints.md` — CP-00/01/02 を通過済みに更新
- `docs/current-milestone.md` — CP-04 に更新
- `takumi/hermes/__init__.py` — 新規
- `takumi/hermes/models.py` — 新規
- `takumi/hermes/memory.py` — 新規
- `takumi/hermes/skill.py` — 新規
- `takumi/discord/job_runner.py` — Recall 注入、Save 呼び出し、_build_recall_context 追加
- `docker-compose.yml` — runtime volume 追加

## Validation（次回起動で確認すること）
1. `docker compose up -d --build` → コンテナ起動
2. `/task 元気？` → job done、`runtime/memory/entries/mem-*.json` が生成される
3. `/task 前やったこと覚えてる？` → プロンプトに Recall セクションが含まれる（コンテナログで確認）
4. `ls runtime/memory/entries/` → エントリが増えている

## Risks / Concerns
- `runtime/` をホスト側マウントにしたため、コンテナ内の `takumi` ユーザー（UID 1000）が書き込めるか要確認
  → `chown -R 1000:1000 runtime/` を必要に応じてホストで実行

## Suggested Next Step
1. `./start.sh` でコンテナを再起動してビルドを反映
2. Discord で `/task 元気？` → エントリ生成を確認
3. Discord で `/task 前やったこと覚えてる？` → Recall が効くか確認 → CP-04 通過
4. `docs/runbooks/hermes-bridge.md` を作成して CP-04 成果物を整える

## Memory Candidates
- `takumi/hermes/` のストレージパスは env var で差し替え可能（`HERMES_ENTRIES_DIR` / `HERMES_SKILLS_DIR`）
- Recall は job_runner の `_build_workspace_prompt()` でプロンプトに注入される
- Save は `_save()` が `run_job` / `resume_job` 完了時に呼ばれる（例外は WARNING のみ）
- `runtime/` をコンテナにマウントするため、ホスト側のパーミッション確認が必要な場合がある
