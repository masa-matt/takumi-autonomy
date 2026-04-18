# Phase 2.2: Repo Structure Cache

## Goal

同じ repo を何度も触るときに、毎回 `ls / README / package.json / test コマンドの探索` を最初からやらない。
一度調べた repo の「構造・技術スタック・test/lint コマンド・主要ファイル」を Hermes に cache し、次回以降プロンプトに注入する。

**解決する無駄**:
- 毎回「この repo の技術スタックは？」を Claude Code が探索する
- 毎回「テストの走らせ方は？」を試行錯誤する
- 同じ README を何度も読み直す

---

## Acceptance Criteria

- [ ] ジョブ完了時に触った repo の構造メタデータが `runtime/memory/repos/<slug>.json` に保存される
- [ ] 次回同じ repo URL がタスクに含まれた時、cache がプロンプトに注入される
- [ ] commit SHA が変わった時、cache が「古くなった可能性あり」とマークされる（更新は次回タスクで）
- [ ] cache の有無・古さに関する情報がプロンプトから Claude Code に伝わる
- [ ] cache がなくても既存の動作は壊れない（fallback）
- [ ] cache hit の有無がログに出る

---

## Data Model

### `takumi/hermes/models.py` への追加

```python
@dataclass
class RepoStructureCache:
    cache_id: str                    # "repo-<slug>"
    repo_url: str                    # "https://github.com/org/repo"
    slug: str                        # "org-repo"
    branch: str                      # "main" (default branch)
    last_seen_commit: str            # short SHA
    tech_stack: list[str]            # ["python", "django", "postgres"]
    entry_points: list[str]          # ["manage.py", "app.py"]
    test_command: str | None         # "pytest" / "npm test" / "go test ./..."
    lint_command: str | None
    build_command: str | None
    install_command: str | None      # "pip install -r requirements.txt"
    directory_summary: str           # 数文でざっくり構造を説明
    key_files: list[dict]            # [{"path": "config/settings.py", "purpose": "..."}]
    known_issues: list[str]          # 過去に遭遇した問題・落とし穴
    source_job_ids: list[str]        # この cache を作るのに使った job
    created_at: str
    updated_at: str
    stale: bool = False              # commit SHA が変わったら True

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "RepoStructureCache": ...
```

**保存先**: `runtime/memory/repos/<slug>.json`
  - slug の生成: `repo_url.replace("https://github.com/", "").replace("/", "-")`
  - 例: `https://github.com/org/repo` → `org-repo.json`

---

## File Changes

### 新設

| File | 内容 |
|---|---|
| `takumi/hermes/repo_cache.py` | RepoStructureCache の CRUD・URL からの slug 生成 |
| `takumi/hermes/repo_cache_test.py` | 単体テスト |

### 修正

| File | 変更内容 |
|---|---|
| `takumi/hermes/models.py` | `RepoStructureCache` 追加 |
| `takumi/hermes/__init__.py` | `get_repo_cache` / `save_repo_cache` を export |
| `takumi/discord/job_runner.py` | プロンプト構築時に cache を読む、完了後に cache を更新 |
| `takumi/core/executor_adapter.py` | 必要なら完了後の cache 抽出 hook |

### 環境変数

| 変数 | 役割 | デフォルト |
|---|---|---|
| `HERMES_REPOS_DIR` | repo cache の保存先 | `runtime/memory/repos` |
| `REPO_CACHE_STALE_DAYS` | この日数を超えたら stale 扱い | 30 |

---

## Cache の生成方法

2つの案。2.2 では **案 A** を採用。

### 案 A: プロンプトで「最後にメタデータを JSON で書け」と指示（採用）

`_build_workspace_prompt` に追記:

```
リポジトリ調査の最後に、output/repo-meta.json を以下のフォーマットで書くこと:
{
  "repo_url": "...",
  "branch": "...",
  "last_seen_commit": "...",
  "tech_stack": [...],
  "test_command": "...",
  "lint_command": "...",
  "install_command": "...",
  "directory_summary": "...",
  "key_files": [{"path": "...", "purpose": "..."}],
  "known_issues": [...]
}
```

ジョブ完了後、`executor_adapter.execute` から戻った後に `output/repo-meta.json` を読み、`save_repo_cache()` で保存。

**利点**: 追加の API 呼び出しなし・コスト最小
**欠点**: Claude Code が忘れると cache が作られない（警告ログのみ）

### 案 B: 完了後に別タスクで抽出（不採用）

完了後、claude CLI をもう一度呼んで `--p "この workspace の repo 構造を JSON で要約して"` を実行。

**利点**: 確実
**欠点**: API 呼び出しが毎回倍になる・コスト高

---

## Cache の利用方法

`_build_workspace_prompt()` を拡張:

```python
def _build_workspace_prompt(task: str, workspace) -> str:
    ...
    repo_cache_section = _build_repo_cache_context(task)  # 新規
    ...
    return f"""
    ...
    {repo_cache_section}
    ...
    """

def _build_repo_cache_context(task: str) -> str:
    """タスクに含まれる GitHub URL の cache を探してプロンプトセクションを返す。"""
    urls = _extract_github_urls(task)  # 既存の URL 抽出ロジック
    lines = []
    for url in urls:
        cache = get_repo_cache(url)
        if cache is None:
            continue
        lines.append(f"### {cache.repo_url}")
        lines.append(f"（過去の調査を元にした構造情報。stale={cache.stale}）")
        lines.append(f"- 技術スタック: {', '.join(cache.tech_stack)}")
        lines.append(f"- テスト: `{cache.test_command}`")
        lines.append(f"- lint: `{cache.lint_command}`")
        lines.append(f"- install: `{cache.install_command}`")
        lines.append(f"- 構造: {cache.directory_summary}")
        if cache.known_issues:
            lines.append(f"- 既知の問題: {'; '.join(cache.known_issues)}")
    if not lines:
        return ""
    return "\n## 既知のリポジトリ情報（Hermes cache）\n" + "\n".join(lines) + "\n"
```

プロンプトに追加する注意書き:

```
既知のリポジトリ情報は過去の調査結果です。stale=True なら内容が古い可能性があるので確認してください。
特に問題なければ、この情報を元に作業を始めて、構造調査をやり直さないこと。
```

---

## Stale 判定

cache 使用時に Claude Code に commit SHA を確認させる:

```
プロンプト:
- repos/<repo>/ が存在する場合、`git rev-parse HEAD` で現在の commit SHA を取得すること
- cache の last_seen_commit と異なる場合は「stale だった」と報告し、必要な差分だけ追跡すること
```

完了時の `repo-meta.json` に新しい commit SHA を入れれば、`save_repo_cache()` で上書き更新される。

---

## Flow

### 初回（cache なし）

```
User: リポジトリ URL を含むタスク
  ↓
_build_workspace_prompt
  ↓ get_repo_cache(url) → None
repo_cache_section = ""
  ↓
Claude Code 実行
  ↓ 通常通り構造調査
  ↓ 最後に output/repo-meta.json 書き出し
  ↓
ジョブ完了後
  ↓
save_repo_cache(RepoStructureCache(...))
  ↓
runtime/memory/repos/<slug>.json 作成
```

### 2回目以降（cache あり）

```
User: 同じリポジトリを含むタスク
  ↓
_build_workspace_prompt
  ↓ get_repo_cache(url) → RepoStructureCache(...)
repo_cache_section に情報注入
  ↓
Claude Code 実行
  ↓ 構造調査をスキップ（or 最小限で確認）
  ↓ commit SHA を確認
  ↓ 作業
  ↓ output/repo-meta.json を更新（新 commit SHA 等）
  ↓
ジョブ完了後
  ↓
save_repo_cache（既存に上書き）
```

---

## Edge Cases

| ケース | 対処 |
|---|---|
| `output/repo-meta.json` が生成されなかった | warning ログ・既存 cache は維持 |
| JSON パース失敗 | warning ログ・既存 cache は維持 |
| 同じ repo だが branch 違いが混在 | `<slug>-<branch>.json` とするか、branch を array で持つ。2.2 では最新 branch で上書き（シンプル） |
| Fork / mirror 等で URL 表記揺れ | 将来対応。2.2 では URL 完全一致のみ |
| cache ファイルが破損 | skip・cache なし扱い |
| GitHub 以外の URL（GitLab 等） | 2.2 では GitHub URL のみ対応（他は cache 無し扱い） |
| private repo で Claude Code が clone に失敗 | cache は作られない。既存挙動と同じ |

---

## Testing Plan

### 単体テスト (`repo_cache_test.py`)

- save → get で round-trip できる
- slug 生成（`https://github.com/org/repo.git` → `org-repo`、`.git` suffix 除去）
- 破損ファイル skip
- stale フラグのトグル

### 統合テスト（手動）

1. 初回タスク: `https://github.com/example/py-repo の README 見せて` → cache 生成確認
2. `ls runtime/memory/repos/example-py-repo.json` → 存在確認
3. 2回目タスク: 同じ repo で `テスト走らせて` → プロンプトに cache 情報が入ることをログで確認
4. `repo-meta.json` に commit SHA が書かれていること
5. cache を手動編集（commit SHA を変更）して stale 判定が動くこと

### ログ確認

```
INFO repo_cache: hit — org/repo (cache=<path>, stale=False)
INFO repo_cache: saved/updated — org/repo (commit=abc1234)
WARN repo_cache: missing repo-meta.json, skipping cache update
```

---

## Non-goals

- repo が削除された時の cache invalidation
- 複数 branch の同時 cache 管理
- GitHub 以外のホスティング
- cache の自動再検証（古くなったら自動で再調査）
- cache 同士の類似性検出・マージ

これらは V3 本番設計（Phase 3.x）で扱う。

---

## Dependencies

- Phase 2.1（session 化）に強く依存するわけではないが、session と併用することで効果が最大化
- 依存パッケージなし

docs 更新:
- `docs/runbooks/hermes-bridge.md` に repos/ cache セクション追記
