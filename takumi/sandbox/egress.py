"""takumi.sandbox.egress — sandbox からの成果物回収

output/ / logs/ の内容をホスト側に回収する。
人間がレビューしたうえで採用するものだけをホストに返す、
copy-in / copy-out 方式の「out」側。
"""

import shutil
from pathlib import Path

from takumi.sandbox.workspace import Workspace, collect_artifacts


def list_outputs(ws: Workspace) -> list[Path]:
    """output/ 配下のファイル一覧を返す（再帰）。"""
    return collect_artifacts(ws)


def read_output(ws: Workspace, filename: str) -> str:
    """output/<filename> の内容を文字列で返す。"""
    target = ws.output / filename
    if not ws.is_within_bounds(target):
        raise ValueError(f"read_output: path outside sandbox: {target}")
    if not target.exists():
        raise FileNotFoundError(f"read_output: not found: {target}")
    return target.read_text(encoding="utf-8")


def export_output(ws: Workspace, dest_dir: Path, overwrite: bool = False) -> list[Path]:
    """output/ 配下を dest_dir にコピーして返す。

    Args:
        ws:         対象 workspace
        dest_dir:   コピー先ディレクトリ（ホスト側）
        overwrite:  True なら既存ファイルを上書きする

    Returns:
        コピーしたファイルのリスト

    Note:
        この操作はホスト側に書き戻すため、承認フローを経てから呼ぶこと。
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    for src in collect_artifacts(ws):
        rel = src.relative_to(ws.output)
        dst = dest_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and not overwrite:
            continue
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def read_log(ws: Workspace, log_name: str = "run.log") -> str:
    """logs/<log_name> の内容を返す。存在しなければ空文字列。"""
    log_file = ws.logs / log_name
    if not log_file.exists():
        return ""
    return log_file.read_text(encoding="utf-8")


def summarize(ws: Workspace) -> dict:
    """workspace の概要を dict で返す。report 用。"""
    outputs = list_outputs(ws)
    state = ws.read_state()
    return {
        "job_id": ws.job_id,
        "workspace_path": str(ws.path),
        "status": state.get("status", "unknown"),
        "output_files": [str(p.relative_to(ws.path)) for p in outputs],
        "output_count": len(outputs),
    }
