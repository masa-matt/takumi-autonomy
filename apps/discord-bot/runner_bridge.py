"""runner_bridge.py

sys.path を整えて JobRunner を返すファクトリ。
gateway.py はこれだけ import すればよい。
"""

import sys
from pathlib import Path

# ── repo ルートから各モジュールディレクトリを path に追加 ─────────────────────
_ROOT = Path(__file__).parent.parent.parent  # takumi-autonomy/

sys.path.insert(0, str(_ROOT / "packages"))
sys.path.insert(0, str(_ROOT / "apps" / "executor-gateway"))
sys.path.insert(0, str(_ROOT / "apps" / "takumi-core" / "orchestration"))
sys.path.insert(0, str(_ROOT / "apps" / "takumi-core" / "policy"))
sys.path.insert(0, str(_ROOT / "apps" / "takumi-core" / "state"))
sys.path.insert(0, str(_ROOT / "apps" / "takumi-core" / "metrics"))
sys.path.insert(0, str(_ROOT / "apps" / "hermes-bridge"))
# ─────────────────────────────────────────────────────────────────────────────

from job_runner import JobRunner          # noqa: E402
from mor_prr import get_metrics           # noqa: E402


def make_runner(executor_name: str = "agent-sdk") -> JobRunner:
    """auto_approve=True で JobRunner を生成して返す。"""
    if executor_name == "claude-code":
        from claude_code_executor import ClaudeCodeExecutor
        executor = ClaudeCodeExecutor()
    else:
        from agent_sdk_executor import AgentSdkExecutor
        executor = AgentSdkExecutor()

    return JobRunner(
        executor=executor,
        auto_approve=True,   # Discord 運用は auto-approve 固定
        max_retries=3,
        create_skill=False,
    )


def metrics_summary() -> dict:
    return get_metrics()
