# Skill Template

このファイルは skill の標準フォーマットを示すテンプレート。
実際の skill は `runtime/memory/skills/{skill_id}.json` に保存される。

---

## Skill JSON フォーマット

```json
{
  "skill_id": "skill-YYYYMMDD-XXXXXXXX",
  "name": "short_snake_case_name",
  "description": "この skill が何をするかの一文説明",
  "trigger_keywords": ["keyword1", "keyword2", "keyword3"],
  "source_job_id": "job-YYYYMMDD-XXXXXXXX",
  "source_task": "元になったタスクの説明文",
  "procedure_summary": "実行結果の要約 (最大1000文字)",
  "status": "draft | approved | deprecated",
  "created_at": "2026-04-14T00:00:00",
  "approved_at": null,
  "use_count": 0
}
```

---

## Skill 作成基準 (docs/skill-policy.md 参照)

- status=done かつ result.success=True のタスクのみ skill 化する
- 手順が再利用可能な場合のみ作成する
- 一時的・環境固有の手順は skill 化しない

## Skill レビュー基準

- 手順が明確で再現可能か
- trigger_keywords が適切に設定されているか
- procedure_summary に実用的な情報が含まれているか
