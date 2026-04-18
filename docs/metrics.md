# Takumi V2 Metrics

## 計測項目

| 指標 | 計測方法 | 目標 |
|---|---|---|
| ジョブ完了率 | done / (done + failed) | > 80% |
| Recall ヒット率 | hits > 0 のジョブ数 / 総ジョブ数 | > 50%（蓄積後） |
| Memory 保存率 | saved = True のジョブ数 / 総ジョブ数 | > 70% |
| Skill draft 生成率 | created = True のジョブ数 / 総ジョブ数 | > 30% |
| handoff 作成率 | output/handoff.md あり / 総ジョブ数 | > 80%（repo タスク） |
| 危険操作停止率 | deny + blocked / 危険タスク総数 | 100% |

---

## 記録（2026-04-18 試験時点）

| 指標 | 値 | 備考 |
|---|---|---|
| 処理ジョブ数 | 5+ | 試験セッション |
| Recall 動作確認 | ✅ | スクリーンショット確認 |
| Memory 保存 | ✅ | ログで確認 |
| Skill draft 生成 | ✅ | ログで確認 |
| 危険操作停止 | ✅ | DENY / BLOCKED 実装確認 |
| handoff 作成 | ✅ | docs/handoff.md 更新 |

---

## ログの見方

```bash
# コンテナログで Hermes の動作確認
docker compose logs takumi | grep "Hermes"

# memory 保存確認
ls runtime/memory/entries/

# skill draft 確認
ls runtime/memory/skills/

# ジョブ状態確認
ls takumi/jobs/
cat takumi/jobs/<job_id>/state/job.json
```

---

## 継続計測

このファイルは運用を重ねるにつれて更新する。
定量データは将来的に `reports/` 以下に月次・週次で追記する。
