# Skill Policy

## 目的

Skill とは、成功したタスクから抽出した再利用可能な手順のこと。
Hermes に保存し、同種のタスクが来たときに参照することで、ゼロスタートを避ける。

---

## Skill を作成すべきタスクの基準

### 作成する
- `status=done` かつ `result.success=True` のタスク
- 手順に再利用可能なパターンが含まれているもの
- 同じような依頼が繰り返し来ることが予想されるもの

### 作成しない
- `status=failed` のタスク（失敗した手順は skill にしない）
- policy に DENY されたタスク（実行されていないため手順がない）
- 一時的・環境固有の手順（特定の日時、特定の一時ファイル名など）
- secrets / tokens / passwords を含む出力

---

## Skill のライフサイクル

```
create_skill_draft()
      ↓
  status: draft
      ↓
  review (CLI: --skill-review)
      ↓
approve_skill()           reject_skill()
      ↓                         ↓
status: approved          status: deprecated
      ↓
  次回タスクの recall で参照される
  use_count++ ずつ積み上がる
```

---

## Skill Review 基準

レビュー時に以下を確認すること:

1. **name** がタスクの内容を端的に表しているか
2. **trigger_keywords** が次回の検索でヒットしそうか
3. **procedure_summary** に実用的な情報が含まれているか（単なる stub 出力ではないか）
4. 機密情報が含まれていないか

---

## PCR (Proceduralization Rate)

PCR = skill_creates / total_jobs

- 目標: 成功したタスクの50%以上を skill 化する
- `--skill-review` で draft を承認することで skill_approvals が増える
- 承認された skill が次回タスクで参照されると `use_count` が増える

---

## CLI 操作

```bash
# タスク実行 + skill draft 作成
python scripts/run_local.py --task "..." --skill

# pending draft を確認・承認
python scripts/run_local.py --skill-review

# metrics 確認 (MOR / PRR / PCR)
python scripts/run_local.py --metrics
```
