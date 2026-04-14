"""takumi.sandbox.workspace — Job workspace の作成・管理・クリーンアップ

1ジョブ1workspaceの原則を実装する。

workspace 構造:
    takumi/jobs/<job-id>/
        input/    ← ユーザーから渡されたファイル
        repos/    ← clone した repo
        output/   ← 生成物 / diff
        logs/     ← 実行ログ
        state/    ← job 状態 JSON

書き込みは必ず job 配下に閉じる。ホスト本体への直接書き込みは行わない。
"""

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# repo ルートからの相対パスで jobs ディレクトリを決める
_REPO_ROOT = Path(__file__).parent.parent.parent
JOBS_DIR = _REPO_ROOT / "takumi" / "jobs"

_SUBDIRS = ["input", "repos", "output", "logs", "state"]


@dataclass
class Workspace:
    """job ひとつに対応する sandbox workspace。"""

    job_id: str
    path: Path
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # 各サブディレクトリへのショートカット
    @property
    def input(self) -> Path:
        return self.path / "input"

    @property
    def repos(self) -> Path:
        return self.path / "repos"

    @property
    def output(self) -> Path:
        return self.path / "output"

    @property
    def logs(self) -> Path:
        return self.path / "logs"

    @property
    def state(self) -> Path:
        return self.path / "state"

    def state_file(self) -> Path:
        return self.state / "job.json"

    def write_state(self, data: dict) -> None:
        """job 状態を state/job.json に保存する。"""
        self.state.mkdir(parents=True, exist_ok=True)
        with open(self.state_file(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def read_state(self) -> dict:
        """state/job.json を読んで返す。存在しなければ空 dict。"""
        sf = self.state_file()
        if not sf.exists():
            return {}
        with open(sf, encoding="utf-8") as f:
            return json.load(f)

    def is_within_bounds(self, target: Path) -> bool:
        """target が workspace 配下に収まっているかを確認する。

        sandbox 境界チェック。workspace 外への書き込みを検知するために使う。
        """
        try:
            target.resolve().relative_to(self.path.resolve())
            return True
        except ValueError:
            return False

    def __str__(self) -> str:
        return str(self.path)


def create_workspace(job_id: str) -> Workspace:
    """job_id に対応する workspace を作成して返す。

    すでに存在する場合はそのまま返す（冪等）。
    """
    ws_path = JOBS_DIR / job_id
    for subdir in _SUBDIRS:
        (ws_path / subdir).mkdir(parents=True, exist_ok=True)

    ws = Workspace(job_id=job_id, path=ws_path)

    # 状態ファイルが未作成なら初期化
    if not ws.state_file().exists():
        ws.write_state({
            "job_id": job_id,
            "status": "created",
            "created_at": ws.created_at,
        })

    return ws


def get_workspace(job_id: str) -> Workspace | None:
    """既存の workspace を返す。存在しなければ None。"""
    ws_path = JOBS_DIR / job_id
    if not ws_path.exists():
        return None
    return Workspace(job_id=job_id, path=ws_path)


def collect_artifacts(ws: Workspace) -> list[Path]:
    """output/ 配下のファイル一覧を返す。"""
    if not ws.output.exists():
        return []
    return sorted(p for p in ws.output.rglob("*") if p.is_file())


def destroy_workspace(ws: Workspace) -> None:
    """workspace ディレクトリごと削除する。

    注意: 不可逆操作。テストや明示的なクリーンアップ時のみ使うこと。
    """
    if ws.path.exists():
        shutil.rmtree(ws.path)
