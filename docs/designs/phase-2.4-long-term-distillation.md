# Phase 2.4: Long-term Distillation

## Goal

単調増加する Hermes memory entries を、古いものから要約（蒸留）して軽量な knowledge note に変換する。
記録を完全削除せず、「生エントリ」→「蒸留された事実」→「長期知識」の層を作る。

**解決する無駄**:
- 古い entry が全部同じ重みで recall 対象になり、ノイズが増える
- Recall のトークン消費が entry 数に比例して増える
- 似たタスクの重複 entry が分散していて「学んだこと」として見えづらい

---

## Acceptance Criteria

- [ ] 30日以上前の entries が `knowledge note` に蒸留される
- [ ] 蒸留対象の生 entry は `runtime/memory/entries_archive/` に移動する（削除ではない）
- [ ] knowledge note は `runtime/memory/knowledge/` に保存される
- [ ] `search_sessions` は entries + knowledge 両方を対象にする
- [ ] 手動コマンド `takumi-cli distill` で蒸留を走らせられる
- [ ] 蒸留は冪等（同じ入力なら同じ出力）
- [ ] 蒸留後の knowledge note にソース entry_id リストが残る（traceability）
- [ ] 蒸留が失敗しても元 entries は消えない（安全）

---

## Data Model

### `takumi/hermes/models.py` への追加

```python
@dataclass
class KnowledgeNote:
    note_id: str                    # "know-20260418-xxxxxxxx"
    title: str                      # 短いタイトル
    summary: str                    # 要約本文（200〜800 字）
    facts: list[str]                # 抽出された具体的な事実リスト
    tags: list[str]                 # 検索用タグ
    source_entry_ids: list[str]     # 蒸留元 entry_id
    confidence: float               # 0.0〜1.0（類似 entry が多いほど高い）
    created_at: str
    last_verified_at: str | None    # 最後に矛盾なしを確認した日時
    superseded_by: str | None       # より新しい note に置き換えられた場合
```

**保存先**: `runtime/memory/knowledge/<note_id>.json`
**Archive**: `runtime/memory/entries_archive/<entry_id>.json`

### 蒸留ジョブのメタデータ

```python
@dataclass
class DistillationRun:
    run_id: str
    started_at: str
    finished_at: str | None
    entries_processed: int
    notes_created: int
    entries_archived: int
    errors: list[str]
```

**保存先**: `runtime/memory/distillation_runs/<run_id>.json`（audit 用）

---

## File Changes

### 新設

| File | 内容 |
|---|---|
| `takumi/hermes/knowledge.py` | KnowledgeNote の CRUD |
| `takumi/hermes/distiller.py` | 蒸留ロジック本体 |
| `takumi/hermes/distiller_test.py` | 単体テスト |
| `takumi/cli/__init__.py` | CLI エントリポイント |
| `takumi/cli/distill.py` | `takumi-cli distill` コマンド |

### 修正

| File | 変更内容 |
|---|---|
| `takumi/hermes/models.py` | `KnowledgeNote` / `DistillationRun` 追加 |
| `takumi/hermes/memory.py` | `search_sessions` で knowledge も対象に（返す SearchHit に `source` フィールド追加） |
| `takumi/hermes/__init__.py` | 新関数 export |

### 環境変数

| 変数 | 役割 | デフォルト |
|---|---|---|
| `DISTILL_AGE_DAYS` | この日数より古い entry を蒸留対象に | 30 |
| `DISTILL_BATCH_SIZE` | 1回の蒸留で扱う entry 数 | 20 |
| `DISTILL_MODEL` | 蒸留に使うモデル | `claude-opus-4-7` |
| `DISTILL_CLUSTER_SIMILARITY` | 同じクラスタとみなす類似度閾値 | 0.3 |

---

## 蒸留のアルゴリズム

### ステップ1: 対象 entry の収集

```python
def collect_candidates(age_days: int) -> list[MemoryEntry]:
    """age_days より古い entries/ のエントリを返す。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=age_days)
    return [e for e in all_entries() if parse(e.saved_at) < cutoff]
```

### ステップ2: クラスタリング

似たエントリをグループ化する。初期は単純な Jaccard ベース:

```python
def cluster_entries(entries: list[MemoryEntry]) -> list[list[MemoryEntry]]:
    """キーワード重複でクラスタリング（union-find 風）。"""
    clusters = []
    for entry in entries:
        tokens = _tokenize(f"{entry.task} {entry.output_summary}")
        placed = False
        for cluster in clusters:
            # cluster の全 entry と平均 Jaccard を取る
            if avg_similarity(cluster, tokens) >= DISTILL_CLUSTER_SIMILARITY:
                cluster.append(entry)
                placed = True
                break
        if not placed:
            clusters.append([entry])
    return clusters
```

### ステップ3: LLM による要約

各クラスタを LLM に渡して KnowledgeNote を生成:

```python
def distill_cluster(cluster: list[MemoryEntry]) -> KnowledgeNote:
    prompt = f"""
以下は過去のジョブ記録の集まりです。これらから学べる「事実」「パターン」「注意点」を抽出し、
以下の JSON 形式で返してください。重複・ノイズは除き、今後のタスクで役立つ情報だけを残してください。

{{
  "title": "短いタイトル",
  "summary": "要約本文（200〜800 字）",
  "facts": ["事実1", "事実2", ...],
  "tags": ["タグ1", "タグ2", ...]
}}

エントリ:
{json.dumps([e.to_dict() for e in cluster], ensure_ascii=False, indent=2)}
"""
    response = _call_llm(prompt)
    data = json.loads(response)
    return KnowledgeNote(
        note_id=_generate_note_id(),
        title=data["title"],
        summary=data["summary"],
        facts=data["facts"],
        tags=data["tags"],
        source_entry_ids=[e.entry_id for e in cluster],
        confidence=min(1.0, len(cluster) / 10.0),
        created_at=now_iso(),
        last_verified_at=None,
        superseded_by=None,
    )
```

### ステップ4: Archive

成功したら元 entries を archive に移動:

```python
def archive_entries(entries: list[MemoryEntry]) -> None:
    for entry in entries:
        src = _ENTRIES_DIR / f"{entry.entry_id}.json"
        dst = _ARCHIVE_DIR / f"{entry.entry_id}.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
```

**注意**: LLM 呼び出しが失敗した場合は archive しない。失敗は `DistillationRun.errors` に残す。

---

## Recall への統合

`search_sessions` を拡張:

```python
def search_sessions(query: str, top_k: int = 3, recent_always: int = 3) -> SearchResult:
    # 既存: entries/ の検索
    entry_hits = _search_entries(query, ...)
    # 新規: knowledge/ の検索
    knowledge_hits = _search_knowledge(query, ...)

    # マージ: knowledge は confidence で boost、entries は recency で boost
    combined = _merge_and_rank(entry_hits, knowledge_hits, top_k)
    return SearchResult(query=query, hits=combined, ...)
```

`SearchHit` を拡張:

```python
@dataclass
class SearchHit:
    # 既存フィールド...
    source: str = "entry"   # "entry" | "knowledge"
```

プロンプトへの注入時、source=knowledge は「長期知識」セクションに、source=entry は「直近の記録」セクションに分けて表示する。

---

## CLI (`takumi-cli distill`)

```bash
# ドライラン（対象確認のみ、実行しない）
takumi-cli distill --dry-run

# 実行
takumi-cli distill

# 特定 age 以上のみ
takumi-cli distill --min-age-days 60

# 特定クラスタのみ（tag 指定）
takumi-cli distill --tag repo-investigation
```

実装: `takumi/cli/distill.py` で `argparse` + `distiller.run_distillation()` を呼ぶ。
`pyproject.toml` の `[project.scripts]` に `takumi-cli = "takumi.cli:main"` を追加。

---

## Flow

### 蒸留ラン（手動 or 定期）

```
takumi-cli distill
  ↓
collect_candidates(age_days=30) → [entry1, entry2, ...]
  ↓
cluster_entries(entries) → [[entry1, entry2], [entry3], ...]
  ↓ 各クラスタごとに
distill_cluster(cluster) → KnowledgeNote
  ├─ LLM 成功 → save_knowledge_note + archive_entries
  └─ LLM 失敗 → skip（errors に記録）
  ↓
save_distillation_run(run_id, stats)
  ↓
完了サマリーを stdout に出力
```

### Recall（蒸留後）

```
search_sessions(query)
  ↓
entry_hits = _search_entries(query)   # 直近 + 一致エントリ
knowledge_hits = _search_knowledge(query)  # 蒸留済み知識
  ↓
merged = _merge_and_rank(entry_hits, knowledge_hits)
  ↓
プロンプトに注入
  ├─ "## 長期知識" セクション（knowledge）
  └─ "## 直近の記録" セクション（entries）
```

---

## Edge Cases

| ケース | 対処 |
|---|---|
| LLM が JSON を返さない | skip・error ログ・archive しない |
| LLM 呼び出しコストが高い | DISTILL_BATCH_SIZE で制限・クラスタ上限を設ける |
| 同じ entries を二度蒸留する | archive 済みは対象から除外されるので二重蒸留は起きない |
| knowledge note が重複する | 2.4 では重複 OK（同じ内容の note が複数できる）。merge は将来対応 |
| knowledge note が誤情報を含む | `superseded_by` で置き換え可能・手動削除も可 |
| 蒸留中にサーバー停止 | DistillationRun を inflight 状態で残す・次回 resume する設計は将来。2.4 では冪等再実行で対応 |
| entries が少なすぎて蒸留する意味がない | `--min-entries-per-cluster 2` で単体エントリは蒸留しない（option） |
| 機密情報が knowledge に漏れる | LLM プロンプトに「secrets / tokens は要約に含めないこと」を明示 + 保存前に `_SENSITIVE_PATTERNS` でチェック（既存ロジック流用） |

---

## Testing Plan

### 単体テスト

- `cluster_entries` のロジック（類似度計算・境界値）
- `distill_cluster` のパース失敗時の挙動
- `archive_entries` が成功時にだけファイルを移動する
- `search_sessions` が entries + knowledge 両方を返す

### 統合テスト（手動）

1. ダミー entries を `runtime/memory/entries/` に10件投入（古い日付で）
2. `takumi-cli distill --dry-run` → 対象リスト表示を確認
3. `takumi-cli distill` → knowledge note が生成される
4. `ls runtime/memory/knowledge/` で note 確認
5. `ls runtime/memory/entries_archive/` で archive 確認
6. `cat runtime/memory/distillation_runs/run-xxx.json` で run log 確認
7. Discord で関連タスクを投げ、knowledge がプロンプトに入るかログで確認

### 冪等性テスト

同じ入力で2回 `takumi-cli distill` を走らせ、2回目は何も起きないこと。

---

## 運用ルール

- **初期運用**: 蒸留は手動（週次で `takumi-cli distill` を人間が走らせる）
- **中期**: Docker Compose に cron コンテナを追加し、週次自動実行
- **監視**: `distillation_runs/` のログを定期確認し、errors が増えていないか見る

---

## Non-goals

- 自動の重複 knowledge note 統合
- 蒸留結果の信頼性スコアリング（低 confidence note の自動破棄）
- Knowledge graph 化（関係性ネットワーク）
- 外部 vector store への移行
- 蒸留プロンプトの自動改善

これらは V3 本番設計で扱う。

---

## Dependencies

- LLM 呼び出し用に `anthropic` パッケージ（V2 ですでに import 済み）
- Phase 2.1〜2.3 完了を推奨（十分な entries / skills が蓄積されてから蒸留する意味が出る）

docs 更新:
- `docs/runbooks/distillation.md` 新設
- `docs/runbooks/hermes-bridge.md` に knowledge レイヤ追記
- `docs/metrics.md` に蒸留関連メトリクス追加（entries 数 / knowledge 数 / archive 率）
