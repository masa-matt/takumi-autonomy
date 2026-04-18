# Runbook: Repo / File 取り込み（CP-03）

## 概要

Takumi はタスクに応じてファイルや git リポジトリを sandbox に取り込んで作業する。
元ファイル・元 repo は直接編集しない。sandbox 内の複製を作業対象にする。

---

## ファイルの取り込み（inbox → sandbox）

### ユーザー操作
1. `inbox/` ディレクトリにファイルを置く
2. Discord でタスクを依頼する（例: `このPDFをまとめて`）

### 内部動作
- タスク実行前に `inbox/` の全ファイルを `takumi/jobs/<job_id>/input/` にコピー
- Claude Code は `input/` を読み取り専用として扱う
- 成果物は `output/` に書く → タスク完了後に自動で `outbox/<スラグ名>/` に取り出される

### 実装
```
takumi/sandbox/ingress.py
  copy_from_inbox(ws, filename)  # 1ファイル
  copy_all_inbox(ws)             # inbox 全件（タスク実行前に自動呼び出し）
  copy_to_outbox(ws, dirname)    # output/ → outbox/
```

---

## リポジトリの取り込み（URL → sandbox）

### ユーザー操作
Discord でタスクに GitHub URL を含めて依頼するだけ。

```
例: https://github.com/org/repo のバグを調べて
例: https://github.com/org/repo のテストが落ちてる原因を特定して
```

### 内部動作
- Claude Code がプロンプトの指示に従い `repos/` にクローンする
- `repos/<repo_name>/` を作業対象として調査・修正を行う
- 元 repo への push / PR 作成は承認が必要（危険操作として BLOCKED）

### 実装
```
takumi/sandbox/ingress.py
  clone_repo(ws, repo_url, repo_name, branch, depth)
  clone_local_repo(ws, local_path, repo_name)
```

プロンプト側の指示（`job_runner.py::_build_workspace_prompt`）:
> タスクに GitHub URL や git リポジトリの URL が含まれる場合は repos/ にクローンして作業すること

---

## sandbox のディレクトリ構造

```
takumi/jobs/<job_id>/
  input/    ← inbox からのコピー（読み取り専用として扱う）
  repos/    ← git clone 先
  output/   ← 成果物（完了時に outbox へ自動コピー）
  logs/     ← 実行ログ
  state/    ← job.json（状態管理）
```

---

## 制約・安全性

| 操作 | 扱い |
|---|---|
| inbox → input/ コピー | 自動（タスク開始前） |
| output/ → outbox/ コピー | 自動（result.md 除外） |
| GitHub URL の clone | Claude Code が自律的に実施 |
| 元 repo への push | 承認必要（BLOCKED） |
| sandbox 外への書き込み | 禁止（`--add-dir` で制限） |

---

## 確認手順（CP-03 通過条件）

```bash
# 1. inbox にファイルを置く
cp some_file.txt inbox/

# 2. Discord でタスクを依頼
/task inbox のファイルを読んで要約して

# 3. repo clone の確認
# Discord で GitHub URL を含むタスクを依頼
# → takumi/jobs/<job_id>/repos/<repo_name>/ が生成される
```
