# Runbook: 承認境界・停止条件（CP-08）

## 概要

Takumi が自律実行する操作と、人間の承認が必要な操作を明確に分離する。
この境界は実装（`job_runner.py`）と docs の両方で一致させる。

---

## 1. 完全拒否（DENY）

以下のパターンを含むタスクは即座に `FAILED` にして実行しない。

| パターン | 理由 |
|---|---|
| `rm -rf` / `rm -r` | ホスト全域の破壊的削除 |
| `dd if=` | ディスク上書き |
| `mkfs` | ファイルシステム初期化 |
| `chmod 777` | 過剰な権限付与 |
| `curl ... \| bash` / `wget ... \| bash` | 外部スクリプトの盲目的実行 |
| `/etc/shadow` | 認証情報への直接アクセス |
| fork bomb パターン | システム不能化 |

**実装**: `job_runner._DENY_PATTERNS` / `_classify()`

---

## 2. 承認待ち（BLOCKED）

以下のキーワードを含むタスクは `BLOCKED` 状態で停止し、Discord でユーザー確認を求める。

| キーワード | 想定される操作 |
|---|---|
| `delete` | データ・ファイルの削除 |
| `token` / `secret` / `password` | 認証情報の操作 |
| `production` | 本番環境への操作 |
| `push` | リモートへのプッシュ |
| `deploy` | デプロイ実行 |
| `drop table` | DB テーブル削除 |

Discord 上での操作:
- ✅ リアクションで承認 → `resume_job(approved=True)`
- ❌ リアクションで却下 → `resume_job(approved=False)` → FAILED

**実装**: `job_runner._APPROVAL_PATTERNS` / `gateway.py` の BLOCKED ハンドリング

---

## 3. プロンプト内 stop 条件

Claude Code 実行中に以下の操作に到達したら、実行せずに `output/result.md` に報告して止まる。

| 操作 | 条件 |
|---|---|
| 元 repo への push / PR 作成 | タスクに "push" や "PR 作成" が含まれる場合 |
| 複数 repo にまたがる変更 | 多 repo 比較タスクで修正が必要な場合 |
| sandbox 外への書き込み | `--add-dir` で制限（Claude Code の権限設定） |
| PR の実際の作成 | PR 支援タスク（草案出力のみ） |

**実装**: `job_runner._build_workspace_prompt()` の各 stop 条件記述

---

## 4. 実行前チェックフロー

```
Discord メッセージ受信
  ↓
_classify(task)
  ├─ "deny"              → FAILED（即座）
  ├─ "approval_required" → BLOCKED（Discord で確認）
  └─ "auto_allow"        → RUNNING → Claude Code 実行
                              ↓
                         プロンプト内 stop 条件
                              ├─ stop が発動 → output/result.md に報告・終了
                              └─ 正常完了    → output/result.md + handoff.md
```

---

## 5. handoff の義務

大きめの作業セッション終了時、Claude Code は `output/handoff.md` を残す。
Takumi セッション終了時は `docs/handoff.md` に引き継ぎノートを更新する。

含めるべき内容:
- 何をやったか
- 何が完了したか / 未完了か
- 何を検証したか
- 次の最短手
- memory / skill 候補

---

## 6. 要承認操作の完全リスト（実装 ↔ docs 対照）

| 操作 | 実装上の扱い | docs 上の明示箇所 |
|---|---|---|
| ホスト全域の破壊的操作 | DENY | 本 runbook §1 |
| 認証情報・secrets の操作 | BLOCKED | 本 runbook §2 |
| 本番環境への操作 | BLOCKED | 本 runbook §2 |
| リモートへの push | BLOCKED + prompt stop | 本 runbook §2, §3 |
| PR の実作成 | prompt stop | pr-workflow.md |
| 複数 repo 一括変更 | prompt stop | multi-repo-analysis.md |
| sandbox 境界変更 | 禁止（設計上） | CLAUDE.md §5 |
