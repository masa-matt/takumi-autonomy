# Phase 2.3: Skill Auto-Injection & Approval Flow

## Goal

Hermes に蓄積された skill draft を、人間が承認 → 次回以降のタスクで自動的にプロンプトへ注入する。
同じ手順を何度も Takumi に教え直さなくていい状態にする。

**解決する無駄**:
- skill draft が `runtime/memory/skills/` に溜まっているが使われない
- 同じ手順（repo 調査・PR 草案等）を毎回プロンプトに書き下している
- 過去の成功手順が次の Claude Code 呼び出しに渡らない

---

## Acceptance Criteria

- [ ] Discord コマンド `!approve skill-<id>` / `!reject skill-<id>` で skill の状態を変更できる
- [ ] `!skills` コマンドで draft 一覧が確認できる
- [ ] Approved skill がタスク実行時に自動でプロンプトに注入される（trigger_keywords 一致で）
- [ ] Skill 使用時に `use_count` が増える
- [ ] Skill を更新できる（新しい経験を既存 skill に追記）
- [ ] Draft のままの skill は検索対象外（V2 のまま）
- [ ] 承認操作が Hermes memory に audit log として残る

---

## Data Model

### `takumi/hermes/models.py` の Skill 拡張

```python
class SkillStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"   # 新設: 置き換えられた古い skill

@dataclass
class Skill:
    skill_id: str
    name: str
    description: str
    trigger_keywords: list[str]
    procedure_summary: str
    source_job_id: str
    source_task: str
    status: SkillStatus = SkillStatus.DRAFT
    # 2.3 で追加
    approved_by: str | None = None          # Discord username
    approved_at: str | None = None
    use_count: int = 0
    success_count: int = 0
    last_used_at: str | None = None
    updated_at: str = ""
    version: int = 1                        # 更新時にインクリメント
    supersedes: str | None = None           # 旧 skill_id（置き換え時）
    notes: list[dict] = field(default_factory=list)
                                            # [{"at": "...", "who": "...", "text": "..."}]
```

### 新設: Skill 使用ログ

```python
@dataclass
class SkillUsage:
    skill_id: str
    job_id: str
    session_id: str | None
    used_at: str
    outcome: str          # "success" | "failure" | "unknown"
```

**保存先**: `runtime/memory/skill_usage/<skill_id>.jsonl` （追記専用 JSON Lines）

---

## File Changes

### 新設

| File | 内容 |
|---|---|
| `takumi/hermes/skill_approval.py` | approve / reject / update / deprecate 関数 |
| `takumi/hermes/skill_usage.py` | 使用ログの追記・集計 |
| `takumi/discord/commands.py` | `!approve` / `!reject` / `!skills` コマンドハンドラ |

### 修正

| File | 変更内容 |
|---|---|
| `takumi/hermes/models.py` | Skill 拡張（status enum 追加・使用統計フィールド） |
| `takumi/hermes/skill.py` | `search_skills` の trigger 一致ロジック強化・使用ログとの連携 |
| `takumi/hermes/__init__.py` | 新関数 export |
| `takumi/discord/gateway.py` | `on_message` で `!` プレフィクス検出 → commands に dispatch |
| `takumi/discord/job_runner.py` | プロンプト構築時に skill を注入、使用した skill のログを残す |

### 環境変数

| 変数 | 役割 | デフォルト |
|---|---|---|
| `SKILL_APPROVAL_USERS` | 承認できる Discord user ID のカンマ区切りリスト | 空 = 誰でも可 |
| `SKILL_INJECTION_TOP_K` | プロンプトに注入する skill 最大数 | 3 |
| `SKILL_TRIGGER_THRESHOLD` | 注入する skill の最低 trigger 一致率 | 0.2 |

---

## コマンド仕様

### `!skills`

draft 一覧を最新順に表示（最大10件）。

```
Discord 出力例:
📋 Skill drafts (3 件)
1. skill-20260418-a1b2c3d4 — repo_調査_テスト (draft)
   → Procedure for: https://github.com/... のテストを調べて
2. skill-20260417-xxx — pr_草案_作成 (draft)
...

✅ Approved skills (5 件)
1. skill-20260410-xxx — repo_調査 (use_count=12, last=2026-04-17)
...
```

### `!skills <skill_id>`

特定 skill の詳細を表示（procedure_summary 含む）。

### `!approve <skill_id>`

draft → approved に変更。`approved_by` / `approved_at` を記録。

権限チェック: `SKILL_APPROVAL_USERS` 環境変数に author ID がある場合のみ許可。空なら誰でも可。

```
Discord 出力:
✅ skill-20260418-a1b2c3d4 approved by masa-matt
```

### `!reject <skill_id>`

draft → rejected に変更。検索対象から外れる。

### `!update-skill <skill_id> <note text>`

既存 skill に note を追記。version をインクリメント。

```
Discord 出力:
📝 skill-xxx updated (v2) — note added
```

---

## 自動注入ロジック

`_build_workspace_prompt` の recall セクションを拡張:

```python
def _build_recall_context(task: str) -> str:
    mem_result = search_sessions(task, top_k=3, recent_always=3)
    skill_hits = search_skills(task, top_k=SKILL_INJECTION_TOP_K,
                               min_score=SKILL_TRIGGER_THRESHOLD)
    ...
    if skill_hits:
        lines.append("")
        lines.append("## 使えるスキル（過去タスクから蒸留した手順）")
        lines.append("該当する場合はこれらの手順を参考にし、ゼロから考え直さないこと。")
        for s in skill_hits:
            lines.append(f"### {s['name']} (使用回数: {s['use_count']})")
            lines.append(s['procedure_summary'])
            lines.append("")
    return "\n".join(lines)
```

### Skill の使用記録

Claude Code がどの skill を実際に使ったかを正確に判定するのは難しい。以下の2段階で対応:

**段階1 (2.3)**: プロンプトに入った skill = 「使った候補」として use_count を +1

**段階2 (将来)**: Claude Code に「使ったスキル ID を output/skills_used.json に書いて」と指示し、それを読む

2.3 では段階1で十分。

---

## Flow

### Skill 承認フロー

```
ジョブ完了
  ↓ create_skill_draft
skill draft 保存（status=draft）
  ↓ （Discord に通知メッセージ: "新しいスキル候補が見つかった: skill-xxx"）
ユーザーが !skills で確認
  ↓ !approve skill-xxx
approve_skill(skill_id, approver=user.id)
  ↓ status=approved, approved_at, approved_by 記録
次回タスクから _build_recall_context で自動注入
```

### Skill 使用フロー

```
新タスク受信
  ↓ search_skills(task, min_score=0.2) で approved skill を検索
関連 skill が見つかる
  ↓ プロンプトに注入
  ↓ skill_usage.log_usage(skill_id, job_id, session_id)
Claude Code 実行
  ↓ ジョブ完了
  ↓ outcome 判定（job.status == DONE → "success"、FAILED → "failure"）
  ↓ skill_usage 更新
```

---

## Audit Log

承認操作は memory entries と別の追記専用ログに残す:

**保存先**: `runtime/memory/audit/skill_approvals.jsonl`

```json
{"at": "2026-04-20T10:00:00Z", "action": "approve", "skill_id": "skill-xxx", "by": "masa-matt", "discord_user_id": "123..."}
{"at": "2026-04-20T10:05:00Z", "action": "reject", "skill_id": "skill-yyy", "by": "masa-matt", "discord_user_id": "123..."}
```

---

## 権限チェック

```python
def _can_approve(user_id: str) -> bool:
    allowed = os.environ.get("SKILL_APPROVAL_USERS", "").strip()
    if not allowed:
        return True  # 空なら誰でも可（V2 互換）
    allowed_ids = {x.strip() for x in allowed.split(",") if x.strip()}
    return user_id in allowed_ids
```

Discord メッセージの author ID と照合。権限がなければ:

```
❌ skill approval requires permission. Ask the admin.
```

---

## Edge Cases

| ケース | 対処 |
|---|---|
| 存在しない skill_id で approve | `❌ skill not found: skill-xxx` |
| すでに approved な skill を approve | idempotent（何も起きない + 確認メッセージ） |
| rejected を approve に戻したい | `!approve` でそのまま approved に遷移できる |
| 同じ task から同じ skill が何度も draft 作成される | 2.3 では重複 OK（全部 draft として残る）。重複検出は 2.4 の distillation で |
| skill の procedure_summary が長すぎてプロンプト爆発 | top_k 制限で緩和。さらに文字数上限を設ける（例: 1500 字/skill） |
| trigger_keywords が日本語のみ | 既存 _tokenize で対応できる（stop words に日本語助詞含む） |
| approve 後に skill を編集したい | `!update-skill <id> <note>` で notes 追記。procedure_summary の直編集は手動（ファイル編集） |
| concurrent approve（2人同時） | 2.3 では read-modify-write のまま。2.5 で file lock |

---

## Testing Plan

### 単体テスト

- approve / reject / update の状態遷移
- 権限チェック（allowed user / disallowed user）
- search_skills が approved のみ返す
- use_count のインクリメント
- audit log が追記される

### 統合テスト（手動）

1. ジョブを投げる → draft 作成
2. `!skills` → draft リストに表示
3. `!approve skill-xxx` → approved になる
4. 似たタスクを再度投げる → プロンプトに skill が入ることをログで確認
5. `cat runtime/memory/skill_usage/skill-xxx.jsonl` → 使用ログが増える
6. `!update-skill skill-xxx "この手順は ○○ で失敗した"` → notes に追記される

### ログ確認

```
INFO skill_approval: skill-xxx approved by user=masa-matt
INFO skill_injection: 2 skills injected for task (threshold=0.2)
INFO skill_usage: skill-xxx used in job=job-yyy, session=sess-zzz, outcome=success
```

---

## Non-goals

- Skill の自動評価（成功率から自動 deprecate 等）
- Skill 間の依存関係管理
- Skill の Web UI
- Skill の外部エクスポート / インポート
- Skill version の自動マージ

これらは V3 本番設計で扱う。

---

## Dependencies

- Phase 2.1 推奨（session_id と併用で使用ログが意味を持つ）
- 必須ではない（session_id が None でも動く）
- 依存パッケージなし

docs 更新:
- `docs/runbooks/skill-approval.md` 新設（承認フローの操作手順）
- `docs/runbooks/hermes-bridge.md` に skill ライフサイクル追記
