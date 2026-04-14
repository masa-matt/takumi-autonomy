# Current Milestone

## Status: CP-03 Complete → CP-04 In Progress

Updated: 2026-04-14

---

## CP-00 完了 (Spec Frozen)

以下の成果物がすべて揃い、CP-00 の通過条件を満たした。

| 成果物 | 状態 |
|---|---|
| `docs/project-charter.md` | ✅ 全体アーキテクチャ設計完成 |
| `docs/architecture-baseline.md` | ✅ アーキテクチャ基準スナップショット |
| `docs/checkpoints.md` | ✅ 全 CP 基準定義済み |
| `docs/claude-code-operating-rules.md` | ✅ Claude 固有操作ルール |
| `.claude/CLAUDE.md` | ✅ 非交渉ルール v1 |

Git tag: `cp-00-spec-frozen`

---

## CP-01 進行中 (Minimum Vertical Slice)

### 目標
Task 投入から Report 保存までの最小縦断を通す。

### 通過条件チェックリスト

- [x] task を投入できる (`scripts/run_local.py`)
- [x] job id が発行される
- [x] 1 job 1 workspace が作成される (`runtime/workspaces/jobs/{job_id}/`)
- [x] executor が 1 回実行される (stub mode で検証済み / API キー設定で実 API)
- [x] report が保存される (`runtime/reports/{job_id}.json`)
- [x] 失敗時も記録が残る (import エラー時も report 保存確認)

### 実装対象ファイル

```
apps/
  takumi-core/
    orchestration/
      job_runner.py
  executor-gateway/
    base.py
    workspace_manager.py
    agent_sdk_executor.py
packages/
  schemas/
    task.py
    execution_result.py
  utils/
    ids.py
runtime/
  workspaces/
  reports/
scripts/
  run_local.py
```

### 検証コマンド

```bash
python scripts/run_local.py --task "list files in workspace"
```

期待される結果:
- `runtime/workspaces/jobs/job-YYYYMMDD-XXXXXXXX/` が作成されている
- `runtime/reports/job-YYYYMMDD-XXXXXXXX.json` が存在する
- report に `job_id`, `status: done`, `result` が含まれている

---

## 次の CP-01 完了後: CP-02

CP-01 検証完了後、CP-02 (Safety Gates) へ進む。

- Auto Allow / Approval Required / Deny の3分類実装
- 承認待ち状態の永続化
- retry 上限の実装
