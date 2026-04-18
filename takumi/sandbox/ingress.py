"""takumi.sandbox.ingress — sandbox へのファイル・repo 取り込み

copy-in / repo clone を担当する。
ホスト上の元ファイルや元 repo を直接操作せず、sandbox の input/ / repos/ にコピー・clone する。
"""

import os
import shutil
import subprocess
from pathlib import Path

from takumi.sandbox.workspace import Workspace

# inbox / outbox のデフォルトパス
INBOX_DIR = Path(os.environ.get("INBOX_DIR", "/app/inbox"))
OUTBOX_DIR = Path(os.environ.get("OUTBOX_DIR", "/app/outbox"))


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


# ── Inbox 取り込み ────────────────────────────────────────────────────────────

def list_inbox() -> list[Path]:
    """inbox にあるファイルの一覧を返す。ディレクトリは除外。"""
    if not INBOX_DIR.exists():
        return []
    return sorted(p for p in INBOX_DIR.iterdir() if p.is_file() and p.name != ".gitkeep")


def copy_all_inbox(ws: Workspace) -> list[Path]:
    """inbox の全ファイルを sandbox の input/ にコピーする。"""
    copied = []
    for src in list_inbox():
        try:
            copied.append(copy_file(ws, src, dest_name=src.name))
        except Exception:
            pass
    return copied


def copy_to_outbox(ws: Workspace, dirname: str) -> list[Path]:
    """sandbox の output/ を outbox/<dirname>/ にコピーして返す。"""
    if not ws.output.exists():
        return []
    dest_dir = OUTBOX_DIR / dirname
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in ws.output.iterdir():
        if src.is_file():
            shutil.copy2(src, dest_dir / src.name)
            copied.append(dest_dir / src.name)
    return copied


def copy_from_inbox(ws: Workspace, filename: str) -> Path:
    """inbox のファイルを sandbox の input/ にコピーする。

    Args:
        ws:       対象 workspace
        filename: inbox 内のファイル名（パス区切り・'..' は拒否）

    Returns:
        コピー先のパス（ws.input / filename）

    Raises:
        ValueError: filename にパストラバーサルが含まれる場合
        FileNotFoundError: inbox に filename が存在しない場合
    """
    # パストラバーサル防止
    if "/" in filename or "\\" in filename or ".." in filename:
        raise ValueError(f"copy_from_inbox: invalid filename: {filename!r}")

    src = INBOX_DIR / filename
    if not src.exists():
        raise FileNotFoundError(f"copy_from_inbox: not found in inbox: {filename}")

    return copy_file(ws, src, dest_name=filename)


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
