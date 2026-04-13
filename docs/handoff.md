# Handoff Note

Session: 2026-04-14

---

## Session Goal

CP-00 の正式完了と、CP-01 (Minimum Vertical Slice) の実装・検証。

---

## Done

### CP-00 正式完了
- `docs/architecture-baseline.md` 新規作成（アーキテクチャ決定スナップショット）
- `docs/claude-code-operating-rules.md` 新規作成（Recall/Save/Safety/Workspace/Reporting/Handoff ルール）
- `docs/current-milestone.md` 新規作成（現在地の明示）
- `git init` + initial commit + `cp-00-spec-frozen` タグ付け

### CP-01 実装・検証完了
- `packages/schemas/task.py` — Task / Job / JobStatus dataclasses
- `packages/schemas/execution_result.py` — ExecutionResult dataclass
- `packages/utils/ids.py` — generate_job_id (job-YYYYMMDD-XXXXXXXX 形式)
- `apps/executor-gateway/base.py` — Executor 抽象インターフェース
- `apps/executor-gateway/workspace_manager.py` — 1 job = 1 workspace 作成 + report 保存
- `apps/executor-gateway/agent_sdk_executor.py` — Anthropic API Executor (stub mode 付き)
- `apps/takumi-core/orchestration/job_runner.py` — Job ライフサイクル管理
- `scripts/run_local.py` — Discord なしで動く CLI ハーネス
- `runtime/workspaces/jobs/` / `runtime/reports/` — 実行時ディレクトリ
- `.gitignore` — runtime 成果物を除外

### CP-01 通過条件確認
- [x] task を投入できる (`--task "..."`)
- [x] job id が発行される (`job-20260413-126cb556` など)
- [x] 1 job 1 workspace が作成される (`runtime/workspaces/jobs/{job_id}/`)
- [x] executor が 1 回実行される (stub mode で動作確認済み)
- [x] report が保存される (`runtime/reports/{job_id}.json` + workspace 内 `result.json`)
- [x] 失敗時も記録が残る (import エラー時も report 保存を確認)

---

## Not Done

- Anthropic API 実接続テスト (ANTHROPIC_API_KEY が設定されれば動く実装済み)
- Discord bot / gateway (CP-01 は CLI ハーネスで代替)
- Hermes 連携 (CP-03)
- 承認エンジン (CP-02)
- MOR/PRR/PCR 計測 (CP-02〜03)

---

## Files Changed

### 新規作成
```
docs/architecture-baseline.md
docs/claude-code-operating-rules.md
docs/current-milestone.md
packages/schemas/__init__.py
packages/schemas/task.py
packages/schemas/execution_result.py
packages/utils/__init__.py
packages/utils/ids.py
apps/executor-gateway/base.py
apps/executor-gateway/workspace_manager.py
apps/executor-gateway/agent_sdk_executor.py
apps/takumi-core/orchestration/job_runner.py
scripts/run_local.py
runtime/workspaces/jobs/.gitkeep
runtime/reports/.gitkeep
runtime/logs/.gitkeep
.gitignore
```

---

## Tests / Verification

```bash
python scripts/run_local.py --task "list files in workspace"
```

出力:
- status=done
- runtime/workspaces/jobs/job-YYYYMMDD-XXXXXXXX/ が作成される
- runtime/workspaces/jobs/job-YYYYMMDD-XXXXXXXX/artifacts/, logs/, result.json が存在
- runtime/reports/job-YYYYMMDD-XXXXXXXX.json が存在

---

## Risks / Concerns

- Python sys.path を run_local.py で手動設定している（PoC 許容範囲、後で pyproject.toml で整理）
- stub モードのみテスト済み。API キーを設定して実 API 呼び出しは未検証
- Discord gateway は未実装。CP-01 は CLI ハーネスで代替している

---

## Approval Needed

なし（ローカル実行のみ）

---

## Memory Candidates

- CP-00 / CP-01 が完了したこと
- `scripts/run_local.py` が CP-01 の検証ハーネスであること
- sys.path 設定方式（PoC 用）

---

## Skill Candidates

- CP-01 verification checklist (run_local.py の使い方)

---

## Recommended Next Step

**CP-02: Safety Gates の実装**

1. `apps/takumi-core/policy/danger_classifier.py` — 危険操作の分類
2. `apps/takumi-core/policy/approval_policy.py` — Auto Allow / Approval Required / Deny 判定
3. `apps/takumi-core/state/approval_store.py` — 承認待ち状態の永続化
4. `apps/takumi-core/orchestration/job_runner.py` に承認フローを組み込む
5. retry 上限の実装
6. 停止理由を report に含める

CP-02 タグ: `cp-02-safety-gates`
