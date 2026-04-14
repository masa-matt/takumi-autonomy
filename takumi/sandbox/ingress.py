"""takumi.sandbox.ingress — sandbox へのファイル・repo 取り込み

copy-in / repo clone を担当する。
ホスト上の元ファイルや元 repo を直接操作せず、sandbox の input/ / repos/ にコピー・clone する。
"""

import shutil
import subprocess
from pathlib import Path

from takumi.sandbox.workspace import Workspace


# ── ファイル取り込み ──────────────────────────────────────────────────────────

def copy_file(ws: Workspace, src: Path, dest_name: str | None = None) -> Path:
    """ホスト上のファイルを sandbox の input/ にコピーする。

    Args:
        ws:         対象 workspace
        src:        コピー元ファイルパス（ホスト上）
        dest_name:  input/ 配下のファイル名。None なら src のファイル名を使う。

    Returns:
        コピー先のパス（ws.input / dest_name）

    Raises:
        FileNotFoundError: src が存在しない場合
        ValueError: dest が workspace 外を指す場合（sandbox 境界違反）
    """
    src = Path(src).resolve()
    if not src.exists():
        raise FileNotFoundError(f"copy_file: source not found: {src}")

    name = dest_name or src.name
    dest = ws.input / name

    if not ws.is_within_bounds(dest):
        raise ValueError(f"copy_file: destination is outside sandbox: {dest}")

    ws.input.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def copy_directory(ws: Workspace, src: Path, dest_name: str | None = None) -> Path:
    """ホスト上のディレクトリを sandbox の input/ にコピーする（再帰）。

    Returns:
        コピー先のパス（ws.input / dest_name）
    """
    src = Path(src).resolve()
    if not src.is_dir():
        raise NotADirectoryError(f"copy_directory: not a directory: {src}")

    name = dest_name or src.name
    dest = ws.input / name

    if not ws.is_within_bounds(dest):
        raise ValueError(f"copy_directory: destination is outside sandbox: {dest}")

    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest


# ── Repo clone ────────────────────────────────────────────────────────────────

def clone_repo(
    ws: Workspace,
    repo_url: str,
    repo_name: str | None = None,
    branch: str | None = None,
    depth: int | None = 1,
) -> Path:
    """repo を sandbox の repos/ に clone する。

    元 repo の直編集を避けるため、repos/ 配下に clone する。

    Args:
        ws:         対象 workspace
        repo_url:   clone 元 URL（または ローカルパス）
        repo_name:  repos/ 配下のディレクトリ名。None なら URL の末尾から推定。
        branch:     checkout するブランチ。None なら default branch。
        depth:      shallow clone の depth。None なら full clone。

    Returns:
        clone 先のパス（ws.repos / repo_name）

    Raises:
        subprocess.CalledProcessError: git clone が失敗した場合
        ValueError: clone 先が workspace 外の場合
    """
    if repo_name is None:
        repo_name = Path(repo_url).stem.replace(".git", "")

    dest = ws.repos / repo_name

    if not ws.is_within_bounds(dest):
        raise ValueError(f"clone_repo: destination is outside sandbox: {dest}")

    ws.repos.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "clone"]
    if depth is not None:
        cmd += ["--depth", str(depth)]
    if branch is not None:
        cmd += ["--branch", branch]
    cmd += [repo_url, str(dest)]

    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return dest


def clone_local_repo(
    ws: Workspace,
    local_path: Path,
    repo_name: str | None = None,
) -> Path:
    """ローカルの git repo を sandbox の repos/ に clone する。

    元 repo を直接編集させず、sandbox 内の clone を作業対象にする。
    """
    local_path = Path(local_path).resolve()
    if not (local_path / ".git").exists():
        raise ValueError(f"clone_local_repo: not a git repo: {local_path}")

    return clone_repo(
        ws,
        repo_url=str(local_path),
        repo_name=repo_name or local_path.name,
        depth=None,  # ローカル clone は full clone
    )
