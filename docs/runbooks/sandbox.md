# Sandbox Runbook — Job Workspace の設計と操作

## 概要

Takumi Local Autonomy V2 では **1ジョブ1sandbox** を原則とする。

ローカル PC 本体（ホスト）を直接作業場にせず、
ジョブごとに隔離された workspace を作成し、そこで作業を完結させる。

---

## workspace 構造

```
takumi/jobs/<job-id>/
├── input/    ← ユーザーから渡されたファイル（read-only 扱い）
├── repos/    ← clone した repo（元 repo は直接編集しない）
├── output/   ← 生成物 / diff（人間がレビューして採用する）
├── logs/     ← 実行ログ
└── state/    ← job 状態 JSON
    └── job.json
```

---

## モジュール構成

| ファイル | 役割 |
|---|---|
| `takumi/sandbox/workspace.py` | workspace 作成・管理・境界チェック |
| `takumi/sandbox/ingress.py` | ファイル copy-in / repo clone |
| `takumi/sandbox/egress.py` | 成果物回収・読み出し |

---

## 基本的な使い方

### workspace を作成する

```python
from takumi.sandbox.workspace import create_workspace

ws = create_workspace("job-20260415-abc123")
# takumi/jobs/job-20260415-abc123/{input,repos,output,logs,state}/ が作られる
```

### ファイルを sandbox に取り込む

```python
from takumi.sandbox.ingress import copy_file, copy_directory, clone_repo, clone_local_repo
from pathlib import Path

# ファイルを input/ にコピー
copy_file(ws, Path("/path/to/spec.md"))

# ディレクトリを input/ にコピー
copy_directory(ws, Path("/path/to/docs"))

# リモート repo を repos/ に clone
clone_repo(ws, "https://github.com/owner/repo.git")

# ローカル repo を repos/ に clone（元 repo を直編集しない）
clone_local_repo(ws, Path("/path/to/local/repo"))
```

### 成果物を確認・回収する

```python
from takumi.sandbox.egress import list_outputs, read_output, summarize

# output/ のファイル一覧
outputs = list_outputs(ws)

# output/ のファイルを読む
content = read_output(ws, "result.md")

# workspace のサマリ（report 用）
summary = summarize(ws)
```

### 状態を更新する

```python
ws.write_state({
    "job_id": ws.job_id,
    "status": "running",
    "started_at": "2026-04-15T10:00:00Z",
})
```

---

## sandbox 境界チェック

すべての書き込みは workspace 配下に収まっていなければならない。
`workspace.py` の `is_within_bounds()` で確認できる。

```python
ws.is_within_bounds(ws.output / "result.txt")   # True
ws.is_within_bounds(Path("/tmp/evil.txt"))        # False
```

`ingress.py` の copy 系関数は境界外 dest が指定されると `ValueError` を raise する。

---

## 承認が必要な操作

次の操作は **自動で進めず、承認を取ってから実行** すること。

| 操作 | 理由 |
|---|---|
| `egress.export_output()` でホストに書き戻す | ホスト本体への変更 |
| `git push` (repos/ 内) | 元 repo への反映 |
| `sandbox.destroy_workspace()` 以外での削除 | 不可逆操作 |

---

## クリーンアップ

```python
from takumi.sandbox.workspace import destroy_workspace

# workspace ごと削除（不可逆。テストや明示的なクリーンアップ時のみ）
destroy_workspace(ws)
```

---

## CP-LV2-01 通過確認

| 条件 | 確認方法 |
|---|---|
| job id ごとに workspace を作成できる | `create_workspace("any-id")` → パスが作られる |
| 5サブディレクトリが分離される | `ls takumi/jobs/<id>/` → input/repos/output/logs/state |
| 書き込み範囲が job 配下に限定 | `is_within_bounds()` が False を返す / ingress が ValueError を raise |
| job 完了後に成果物を回収できる | `list_outputs()` / `read_output()` / `summarize()` |
| sandbox 境界の想定が文書化 | 本ドキュメント |
