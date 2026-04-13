# Claude Code Operating Rules

## 目的

このファイルは、Claude (Executor) が Takumi Autonomy 上で動作する際に守るべきルールを定義する。
`.claude/CLAUDE.md` の 6 つの非交渉ルールを補足し、具体的な操作基準を提供する。

将来 Claude Code Team に移行した際、このファイルの内容は `.claude/` 配下の各ファイルに反映される。

---

## 1. Recall Rules (過去参照ルール)

**タスクが過去の決定に依存する可能性がある場合、実行前に Hermes の session_search を呼ぶこと。**

- Recall First: 設計判断・実装判断の前に `docs/` 配下の既存ドキュメントを確認する
- Hermes を長期記憶の正本として扱う (Claude 側の memory は補助)
- 過去に同様のタスクを実行したか不明な場合は session_search で確認する

```
recall が必要なタスクの例:
- インフラ変更
- 認証・認可に関わる変更
- 本番環境に影響する変更
- 過去に承認を得たことがある危険操作の再実行
```

---

## 2. Save Rules (保存ルール)

**タスク完了後、再利用できる学習内容を Hermes に保存すること。**

### 保存すべきもの
- 繰り返し使える手順
- 環境固有の注意事項
- 失敗パターンとその回避策
- 承認が必要だった操作の記録

### 保存してはいけないもの
- secrets / tokens / SSH鍵 / 認証情報
- 一時的な状態 (現在のセッション限りの内容)
- 推測や未検証の情報

### Skill 化の基準
- 同じ手順を 2 回以上実行した場合は skill 化を検討する
- 成功パターンのみ skill 化する (失敗パターンは memory に残す)

---

## 3. Safety Rules (安全操作ルール)

**以下の操作は実行前に止まって Takumi Core の承認を取ること。**

### Approval Required (承認が必要)
- 重要ファイルの削除
- 権限変更 (chmod, chown など)
- 永続設定の変更 (config ファイル、環境変数ファイル)
- 外部サービスへの書き込み
- 機密情報の送信
- 本番環境の操作
- force push
- secrets / tokens / SSH鍵 への接触
- 広範囲かつ不可逆な変更

### Auto Allow (自動許可)
- 読み取り操作
- ローカルファイルの編集 (workspace 内)
- lint / unit test の実行
- diff の確認
- 安全なログ収集
- Hermes への過去参照
- Hermes へのメモリ保存
- skill の保存

### Deny by Default (デフォルト拒否)
- ルール外の危険操作
- policy で未分類の高リスク実行
- 停止条件に抵触した再試行

---

## 4. Workspace Rules (ワークスペースルール)

**元 repo への直接編集を避け、割り当てられた workspace 内で作業すること。**

- 作業は `runtime/workspaces/jobs/{job_id}/` 内で行う
- 成果物は `artifacts/` に、ログは `logs/` に保存する
- 失敗した場合も workspace を削除しない (監査のため保持)
- workspace 外への書き込みは Takumi Core の承認なしに行わない

---

## 5. Reporting Rules (レポートルール)

**タスク完了時（成功・失敗を問わず）にレポートを保存すること。**

レポートに含めるもの:
- `job_id`
- `task` (実行したタスクの説明)
- `status` (done / failed)
- `workspace_path`
- `started_at` / `completed_at`
- `result` (出力または エラー)

**証拠なしに完了を主張しない。**
実装タスクでは変更ファイル・検証結果・残リスクをレポートに含める。

---

## 6. Handoff Rules (引き継ぎルール)

**意味のある作業セッションの最後には `docs/handoff.md` を更新すること。**

含める内容:
1. 何を試したか
2. 何を変更したか
3. 何が通ったか / 何が失敗したか
4. 何が残っているか
5. 次に取るべき推奨アクション

---

## Claude Code Team 移行時の対応

このファイルの各セクションは、将来以下に変換される予定:

| 現在 | 移行後 |
|---|---|
| §1 Recall Rules | `.claude/CLAUDE.md` — Recall セクション |
| §2 Save Rules | `.claude/CLAUDE.md` — Save セクション |
| §3 Safety Rules | `.claude/CLAUDE.md` — Safety セクション + `settings.json` permissions |
| §4 Workspace Rules | `.claude/hooks/` — workspace isolation hooks |
| §5 Reporting Rules | `.claude/hooks/` — post-session report hook |
| §6 Handoff Rules | `.claude/CLAUDE.md` — Handoff セクション |
