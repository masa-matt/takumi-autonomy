# Runbook: 単一 repo 調査・修正・検証（CP-05）

## 概要

1つの repo を sandbox に clone し、構造調査・テスト確認・最小差分修正・結果報告を行うワークフロー。

---

## ユーザー操作

Discord でリポジトリ URL とタスクを自然言語で依頼する。

```
例: https://github.com/org/repo のテストが落ちてる原因を調べて修正して
例: https://github.com/org/repo の lint エラーを直して
例: https://github.com/org/repo の構造を調べて説明して
```

---

## 内部動作フロー

```
Discord → job_runner.run_job()
  → sandbox 作成（takumi/jobs/<job_id>/）
  → executor_adapter.execute(job, workspace)
    → claude CLI 起動（--add-dir workspace/）
      → repos/ に repo clone
      → 構造調査
      → test / lint 実行
      → 修正（必要な場合）
      → output/changes.diff 保存
      → output/handoff.md 保存
      → output/result.md 保存
  → outbox/<slug>/ にコピー
  → Hermes memory/skill 保存
  → Discord に結果報告
```

---

## Claude Code への指示（prompt 内）

`job_runner._build_workspace_prompt()` が以下の手順をプロンプトに含める:

1. repo 構造を把握する（README, package.json / pyproject.toml / go.mod / Makefile 等）
2. テストと lint の現状を実行して確認する
3. failing test / lint があれば原因を特定する
4. 最小差分で修正する（関係ない箇所は変えない）
5. 修正後に再度テスト・lint を実行して確認する
6. 変更がある場合は `git diff` を output/changes.diff に保存する
7. output/handoff.md に調査・修正のサマリーを残す

---

## 出力ファイル

| ファイル | 内容 |
|---|---|
| `output/result.md` | Takumi としての結果報告（自然な話し言葉） |
| `output/changes.diff` | 修正内容の git diff（変更がある場合） |
| `output/handoff.md` | 調査サマリー・未解決問題・次のアクション |

outbox への自動コピー: `result.md` 以外の成果物（`changes.diff`, `handoff.md` 等）が `outbox/<slug>/` に置かれる。

---

## 制約・安全性

| 操作 | 扱い |
|---|---|
| repo の clone | Claude Code が自律的に実施 |
| sandbox 内でのテスト実行 | 許可 |
| sandbox 内でのファイル修正 | 許可（最小差分） |
| 元 repo への push | 禁止（BLOCKED） |
| PR の実作成 | 禁止（BLOCKED） |
| sandbox 外への書き込み | 禁止（--add-dir で制限） |

---

## 確認手順（CP-05 通過条件）

```bash
# 1. Discord でタスクを依頼
#    例: https://github.com/org/repo のテストを調べて

# 2. sandbox の確認
ls takumi/jobs/<job_id>/repos/          # clone 確認
ls takumi/jobs/<job_id>/output/         # 成果物確認
cat takumi/jobs/<job_id>/output/result.md
cat takumi/jobs/<job_id>/output/handoff.md
cat takumi/jobs/<job_id>/output/changes.diff  # 修正があれば

# 3. outbox の確認
ls outbox/
ls outbox/<slug>/
```

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| clone に失敗する | GitHub アクセス権なし / URL ミス | URL を確認・認証設定 |
| test コマンドが見つからない | 依存関係未インストール | Claude Code が自動で npm install 等を実施するはずだが、タスクに「依存関係のインストールも含めて」と追記 |
| handoff.md がない | Claude Code が生成しなかった | プロンプトの手順 7 を確認・再依頼 |
| changes.diff がない | 変更がなかった（調査のみ） | 正常。修正タスクでないなら期待通り |
