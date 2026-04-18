# Runbook: PR 本文案・PR Review（CP-07）

## 概要

git diff / commit 差分から PR タイトル・本文案・review コメント草案を生成するワークフロー。
**実際の PR 作成・push は承認境界の外にあり、このワークフローでは実行しない。**

---

## ユーザー操作

Discord で repo URL とタスクを自然言語で依頼する。

```
例: https://github.com/org/repo の main..feature/xxx の diff から PR 本文を作って
例: https://github.com/org/repo の最新コミットを review して
例: この diff を review して: <URL or 差分の説明>
```

---

## 内部動作フロー

```
Discord → job_runner.run_job()
  → sandbox 作成
  → executor_adapter.execute(job, workspace)
    → claude CLI 起動
      → repos/ に repo clone
      → git diff / git log で差分取得
      → PR タイトル案生成
      → PR 本文案生成（docs/templates/pr-body.md 参照）
      → review 観点整理
      → review コメント草案生成
      → output/pr-draft.md に保存して STOP（PR 作成は実行しない）
      → output/result.md に結果報告
  → outbox/<slug>/ にコピー
```

---

## 出力ファイル

| ファイル | 内容 |
|---|---|
| `output/pr-draft.md` | PR タイトル案・本文案・review コメント草案 |
| `output/result.md` | Takumi としての報告（草案の概要） |
| `output/handoff.md` | 残タスク・次のアクション |

---

## 承認境界

| 操作 | 扱い |
|---|---|
| diff 取得・分析 | 許可（sandbox 内） |
| PR タイトル / 本文案の生成 | 許可（output/ に保存のみ） |
| review コメント草案の生成 | 許可（output/ に保存のみ） |
| **実際の PR 作成（gh pr create）** | **禁止（承認が必要）** |
| **リモートへの push** | **禁止（承認が必要）** |

---

## テンプレート

- `docs/templates/pr-body.md` — PR 本文のフォーマット
- `docs/templates/pr-review.md` — review コメントのフォーマット

---

## 確認手順（CP-07 通過条件）

```bash
# 1. Discord で PR 依頼
#    例: https://github.com/org/repo の feature/xxx ブランチの PR 本文を作って

# 2. 成果物確認
cat takumi/jobs/<job_id>/output/pr-draft.md
# → タイトル案・本文案・review 観点が含まれること

# 3. PR が実際には作成されていないことを確認
#    → GitHub 上に PR が存在しないこと
```
