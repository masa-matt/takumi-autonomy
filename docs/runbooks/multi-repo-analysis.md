# Runbook: 複数 repo 比較と影響範囲整理（CP-06）

## 概要

複数の repo を同一 sandbox に clone し、API / interface / config の差分比較・影響範囲の特定を安全に行うワークフロー。
広範囲な変更は実行せず、「何を変えれば良いか」を報告して止まる。

---

## ユーザー操作

Discord で複数の repo URL とタスクを自然言語で依頼する。

```
例: https://github.com/org/service-a と https://github.com/org/service-b の API インターフェースの差分を調べて
例: https://github.com/org/frontend と https://github.com/org/backend の設定ファイルで不一致を探して
例: この3つの repo の依存バージョンを比較して: <url1> <url2> <url3>
```

---

## 内部動作フロー

```
Discord → job_runner.run_job()
  → sandbox 作成（takumi/jobs/<job_id>/）
  → executor_adapter.execute(job, workspace)
    → claude CLI 起動（--add-dir workspace/）
      → repos/<name1>/ に repo-1 clone
      → repos/<name2>/ に repo-2 clone
      → 各 repo を独立して調査
      → 差分・影響範囲を比較
      → 広範囲変更 → STOP（report のみ）
      → output/comparison-report.md 保存
      → output/handoff.md 保存
      → output/result.md 保存
  → outbox/<slug>/ にコピー
  → Hermes memory/skill 保存
  → Discord に結果報告
```

---

## Claude Code への指示（prompt 内）

`job_runner._build_workspace_prompt()` が以下の手順をプロンプトに含める:

1. 各 repo を独立して把握する（技術スタック・ディレクトリ構造・主要設定・API 境界）
2. 目的の観点（API / interface / config / 依存バージョン等）で差分を比較する
3. 影響範囲を特定し、変更が必要な箇所を列挙する
4. 広範囲かつ不可逆な変更は**実行しない** — 「何を変えれば解決するか」を報告して止まる
5. output/comparison-report.md に repo ごとの観測結果と比較サマリーを残す
6. output/handoff.md に次のアクション候補を残す

---

## 出力ファイル

| ファイル | 内容 |
|---|---|
| `output/result.md` | Takumi としての比較結果報告（自然な話し言葉） |
| `output/comparison-report.md` | repo ごとの観測結果・差分表・影響範囲 |
| `output/handoff.md` | 未解決問題・次のアクション候補 |

outbox への自動コピー: `result.md` 以外の成果物が `outbox/<slug>/` に置かれる。

---

## 制約・安全性

| 操作 | 扱い |
|---|---|
| 複数 repo の clone | Claude Code が自律的に実施 |
| sandbox 内での読み取り / 比較 | 許可 |
| 個別 repo の最小修正（単一 repo 調査タスクの場合） | 許可 |
| **複数 repo にまたがる変更** | **禁止 — report のみ** |
| 元 repo への push | 禁止（BLOCKED） |
| sandbox 外への書き込み | 禁止（--add-dir で制限） |

---

## comparison-report.md のフォーマット

`docs/templates/comparison-report.md` を参照。

---

## 確認手順（CP-06 通過条件）

```bash
# 1. Discord で複数 repo タスクを依頼
#    例: <url1> と <url2> の API インターフェースの差分を調べて

# 2. sandbox の確認
ls takumi/jobs/<job_id>/repos/          # 複数 repo clone 確認
ls takumi/jobs/<job_id>/output/         # 成果物確認
cat takumi/jobs/<job_id>/output/comparison-report.md
cat takumi/jobs/<job_id>/output/handoff.md

# 3. 危険な操作で止まる確認
#    Discord で "複数 repo の○○を全部書き換えて" などを依頼
#    → report のみで変更なし、または BLOCKED
```

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| comparison-report.md がない | Claude Code が生成しなかった | 「comparison-report.md に比較をまとめて」と明示して再依頼 |
| 1つしか clone されない | URL が1つしかない / URL の解析ミス | URL を1行1つで明記して再依頼 |
| 勝手に変更が行われた | prompt の stop 条件が効かなかった | job の output/changes.diff を確認し、必要なら手動 revert |
