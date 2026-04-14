# Takumi Checkpoints

## CP-00 仕様固定 ✅

### 目的
PoC の設計境界を固定する。

### 通過条件
- [x] Takumi Core / Hermes / Executor / Discord / VPS の責務分離が文書化されている
- [x] API先行・Claude Code Team移行可能の前提が明記されている
- [x] 危険操作・承認原則・停止条件が明文化されている
- [x] MOR / PRR / PCR が定義されている
- [x] `.claude/CLAUDE.md` の初版がある

### 成果物
- `docs/project-charter.md` ✅
- `docs/architecture-baseline.md` ✅
- `docs/checkpoints.md` ✅
- `docs/claude-code-operating-rules.md` ✅
- `.claude/CLAUDE.md` ✅

### Git tag
- `cp-00-spec-frozen` ✅

---

## CP-01 最小実行縦断 ✅

### 目的
Task 投入から report 保存までの最小縦断を通す。

### 通過条件
- [x] task を投入できる
- [x] job id が発行される
- [x] 1 job 1 workspace が作成される
- [x] executor が 1 回実行される
- [x] report が保存される
- [x] 失敗時も記録が残る

### 成果物
- `scripts/run_local.py` ✅ (Discord 代替の CLI ハーネス)
- `apps/takumi-core/orchestration/job_runner.py` ✅
- `apps/executor-gateway/` ✅ (base, workspace_manager, agent_sdk_executor)
- `packages/schemas/` ✅ (task, execution_result)
- `packages/utils/ids.py` ✅
- `runtime/workspaces/` ✅
- `runtime/reports/` ✅

### Git tag
- `cp-01-minimum-vertical-slice` ✅

---

## CP-02 承認と停止条件 ✅

### 目的
危険操作を勝手に進めず、止まるべき時に止まる。

### 通過条件
- [x] Auto Allow / Approval Required / Deny by Default の3分類がある
- [x] 承認待ち状態を保存できる
- [x] 承認なしで危険操作を実行しない
- [x] retry 上限を超えたら停止する
- [x] 停止理由を report に残せる

### 成果物
- `apps/takumi-core/policy/approval_policy.py` ✅
- `apps/takumi-core/policy/danger_classifier.py` ✅
- `apps/takumi-core/orchestration/stop_conditions.py` ✅
- `packages/schemas/approval_request.py` ✅
- `apps/takumi-core/state/approval_store.py` ✅
- `runtime/approvals/` ✅

### Git tag
- `cp-02-safety-gates` ✅

---

## CP-03 Recall / Save ✅

### 目的
毎回ゼロから始めない最小導線を入れる。

### 通過条件
- [x] task 前に `session_search` を呼べる
- [x] task 後に `memory_write` を呼べる
- [x] save/no-save ルールがある
- [x] report に recall/save 実行有無が残る
- [x] MOR / PRR を計測できる

### 成果物
- `apps/hermes-bridge/session_search_api.py` ✅
- `apps/hermes-bridge/memory_api.py` ✅
- `apps/takumi-core/metrics/mor_prr.py` ✅
- `packages/schemas/memory_entry.py` ✅
- `runtime/memory/entries/` ✅
- `runtime/memory/metrics.json` ✅

### Git tag
- `cp-03-recall-save-enabled` ✅

---

## CP-04 手続き化 ✅

### 目的
成功パターンを skill 化して再利用する。

### 通過条件
- [x] task 完了後に skill draft を作れる
- [x] skill review の簡易フローがある
- [x] skill を保存できる
- [x] 次回 task でその skill を参照できる
- [x] PCR を計測できる

### 成果物
- `apps/hermes-bridge/skill_api.py` ✅
- `docs/skill-policy.md` ✅
- `packages/skills/templates/skill-template.md` ✅
- `packages/schemas/skill.py` ✅
- `runtime/memory/skills/` ✅ (skill-20260414-... 実例あり)

### Git tag
- `cp-04-proceduralization` ✅

---

## CP-05 Claude Code 移行準備 ✅

### 目的
Claude Code へ executor を差し替えやすくする。

### 通過条件
- [x] Claude 固有ルールが `.claude/` に集約されている
- [x] Recall First / Save / Safety が `CLAUDE.md` に反映されている
- [x] hooks 導線がある
- [x] Executor interface を変えずに差し替え可能

### 成果物
- `apps/executor-gateway/claude_code_executor.py` ✅
- `.claude/CLAUDE.md` ✅ (Recall/Save/Skill/Safety/Hooks sections)
- `.claude/settings.json` ✅ (PreToolUse/PostToolUse/Stop hooks)
- `.claude/hooks/` ✅ (pre_tool_use.sh, post_tool_use.sh, session_stop.sh)
- `docs/migration-to-claude-code-team.md` ✅
- `scripts/run_local.py` ✅ (--executor flag: agent-sdk / claude-code)

### Git tag
- `cp-05-claude-code-ready` ✅
