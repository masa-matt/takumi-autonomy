# Handoff Note

Session: 2026-04-14

---

## Session Goal

CP-02 (Safety Gates) の実装・検証。

---

## Done

### CP-02 実装完了
- `packages/schemas/approval_request.py` — DangerLevel / ApprovalStatus / ApprovalRequest スキーマ
- `apps/takumi-core/policy/danger_classifier.py` — キーワードベース危険度分類 (DENY / APPROVAL_REQUIRED / AUTO_ALLOW)
- `apps/takumi-core/policy/approval_policy.py` — 承認判定ロジック (auto_approve フラグ対応)
- `apps/takumi-core/state/approval_store.py` — `runtime/approvals/{job_id}.json` 永続化
- `apps/takumi-core/orchestration/stop_conditions.py` — RetryState / retry 上限管理
- `apps/takumi-core/orchestration/job_runner.py` — 承認フロー + retry ループ組み込み
- `apps/executor-gateway/workspace_manager.py` — stop_reason フィールドを report に追加
- `scripts/run_local.py` — `--auto-approve` / `--max-retries` フラグ追加

### CP-02 通過条件確認
- [x] Auto Allow / Approval Required / Deny の3分類がある
- [x] 承認待ち状態を保存できる (`runtime/approvals/{job_id}.json`)
- [x] 承認なしで危険操作を実行しない (rm -rf → DENIED, workspace 未作成)
- [x] retry 上限を超えたら停止する (2回失敗 → stop_reason に記録)
- [x] 停止理由を report に残せる (`stop_reason` フィールド)

---

## Not Done

- Hermes 連携 (CP-03)
- MOR/PRR/PCR メトリクス (CP-02〜03)
- Discord bot / gateway

---

## Files Changed

### 新規作成
```
packages/schemas/approval_request.py
apps/takumi-core/policy/danger_classifier.py
apps/takumi-core/policy/approval_policy.py
apps/takumi-core/state/approval_store.py
apps/takumi-core/orchestration/stop_conditions.py
```

### 更新
```
apps/takumi-core/orchestration/job_runner.py
apps/executor-gateway/workspace_manager.py
scripts/run_local.py
docs/current-milestone.md
```

---

## Tests / Verification

```bash
# AUTO ALLOW
python scripts/run_local.py --task "read file contents"
# → status=done, stop_reason=null

# APPROVAL REQUIRED (auto-approve)
python scripts/run_local.py --task "delete config file" --auto-approve
# → status=done, danger=approval_required, resolved_by=auto

# DENY
python scripts/run_local.py --task "rm -rf /important/dir"
# → status=failed, stop_reason="Denied: destructive file removal"

# RETRY EXHAUSTION (requires FailingExecutor in code)
# → status=failed, stop_reason="Stopped after 2 attempt(s): ..."
```

---

## Risks / Concerns

- danger_classifier はキーワードベースで単純。誤検知・見落としあり（CP-02 の PoC としては許容）
- approval_store は JSON ファイル。状態の競合は考慮していない
- retry は全失敗に対して行う（一時エラーと恒久エラーを区別していない）

---

## Recommended Next Step

**CP-03: Recall / Save の実装**

1. `apps/hermes-bridge/` の最小実装
   - `session_search_api.py` — 過去セッション検索 (file-based stub)
   - `memory_api.py` — memory_write (file-based stub)
2. `job_runner.py` に recall-first / save-after を組み込む
3. report に recall/save 実行有無を記録
4. MOR / PRR の計測を開始

CP-03 タグ: `cp-03-recall-save-enabled`
