# Migration Guide: API Executor → Claude Code Team Executor

## Overview

Takumi Autonomy was designed from the start so that the executor layer is
replaceable without touching the orchestration logic.  This document covers
the concrete steps to swap from `AgentSdkExecutor` (Anthropic API direct) to
`ClaudeCodeExecutor` (Claude Code CLI, Team tier).

---

## What changes

| Layer | Before (CP-01–04) | After (CP-05+) |
|---|---|---|
| **Executor** | `AgentSdkExecutor` — calls `anthropic.messages.create` directly | `ClaudeCodeExecutor` — calls `claude -p "…" --output-format json` |
| **Auth** | `ANTHROPIC_API_KEY` env var | Claude Code auth (`claude auth login`) |
| **Billing** | API credits | Claude Code Team seat |
| **Hooks** | — | `.claude/hooks/` scripts run automatically |
| **CLAUDE.md rules** | Not applied | Applied on every run |
| **Tooling** | Python SDK | Claude Code CLI |

Everything else (Takumi Core, Hermes, JobRunner, approval gates, recall/save,
skill lifecycle, report format) stays identical.

---

## Prerequisites

1. **Claude Code CLI installed**

   ```bash
   npm install -g @anthropic-ai/claude-code   # or via brew / official installer
   claude --version
   ```

2. **Authenticated**

   ```bash
   claude auth login
   # Follow browser prompt to authorise with your Claude.ai Team account
   ```

3. **Working directory is the repo root**
   Hooks in `.claude/settings.json` are relative to the repo root — always run
   from `/path/to/takumi-autonomy/`.

---

## Step-by-step migration

### 1  Verify the executor interface

`ClaudeCodeExecutor` lives in `apps/executor-gateway/claude_code_executor.py`
and implements the same `Executor` abstract base as `AgentSdkExecutor`:

```python
class ClaudeCodeExecutor(Executor):
    def run(self, job) -> ExecutionResult: ...
    def stop(self, job_id: str) -> None: ...
```

No changes needed in `JobRunner`.

### 2  Select executor at runtime via `--executor` flag

```bash
# Default (unchanged) — AgentSdkExecutor
python scripts/run_local.py --task "describe the workspace" --auto-approve

# Claude Code executor
python scripts/run_local.py --task "describe the workspace" \
    --executor claude-code --auto-approve
```

### 3  Confirm hooks are firing

After running with `--executor claude-code`, check the audit logs:

```bash
cat runtime/logs/claude_code/pre_tool_use.jsonl  | tail -5
cat runtime/logs/claude_code/post_tool_use.jsonl | tail -5
```

Both files should have new entries from the run.

### 4  Verify CLAUDE.md rules are loaded

When Claude Code runs a job it reads `.claude/CLAUDE.md` automatically.
The file references the real implementation paths so Claude can call
`session_search_api.py`, `memory_api.py`, etc. during its own reasoning.

No additional setup required — the file is already in place.

### 5  Confirm report format is unchanged

```bash
ls -lt runtime/reports/ | head -3
cat runtime/reports/<latest>.json | python3 -m json.tool
```

`executor_mode` in the metadata will read `claude_code_cli` instead of
`anthropic_api` or `stub`.

---

## Stub / offline mode

If `claude` is not installed or you want to test the pipeline without a
running CLI, the executor falls back automatically:

```bash
python scripts/run_local.py --task "test" --executor claude-code --auto-approve
# Output: [STUB] ClaudeCodeExecutor: test
```

You can also force stub mode explicitly with `CLAUDE_CODE_STUB=1` (handled in
`ClaudeCodeExecutor.__init__` if you export that env var before running).

---

## Rollback

To revert to the API executor, omit `--executor` or pass `--executor agent-sdk`.
No files need to be changed — both executors coexist.

---

## Checklist

- [ ] `claude --version` returns a version string
- [ ] `claude auth login` completed
- [ ] `python scripts/run_local.py --task "hello" --executor claude-code --auto-approve` exits 0
- [ ] `runtime/logs/claude_code/pre_tool_use.jsonl` has new entries
- [ ] Report `metadata.mode` shows `claude_code_cli` (or `claude_code_stub` in offline)
