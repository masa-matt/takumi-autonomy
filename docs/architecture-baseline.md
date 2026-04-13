# Architecture Baseline

## Snapshot: CP-00 (2026-04-14)

このファイルは CP-00 時点のアーキテクチャ決定を固定するスナップショット。
詳細な設計根拠は `docs/project-charter.md` を参照すること。

---

## 核心的な設計決定

**Claude はシステムの中心ではない。Takumi Core が中心である。**

Claude は「交換可能な実行エンジン」として扱う。これにより:
- API 版から Claude Code Team 版への移行で、差し替えるのは Executor 層だけで済む
- ジョブ管理・承認・停止条件などの運用ロジックが Claude 依存にならない

---

## レイヤー構成

```
[Discord] → [Takumi Core] → [Executor Adapter] → [Workspace]
                ↕
          [Hermes Memory]
```

### Takumi Core (`apps/takumi-core/`)
- 司令塔。Claude が変わっても変えない
- ジョブ管理、承認フロー、停止条件、レポート生成、メトリクス

### Hermes Memory Layer (`apps/hermes-bridge/`)
- 唯一の長期記憶の正本
- Claude 側の memory は補助。Hermes が正本
- `session_search` / `memory_write` / `skill_create` の3本柱

### Executor Adapter (`apps/executor-gateway/`)
- API 版と Team 版の切替点
- 共通インターフェース: `run(job)` / `stop(job_id)`
- PoC: `agent_sdk_executor.py`
- 将来: `claude_code_executor.py`

### Discord Bot (`apps/discord-bot/`)
- 人間との実務インターフェース
- 承認フローの窓口

### VPS / Runtime (`runtime/`)
- 常駐・保存・スケジュール実行基盤
- `runtime/workspaces/jobs/` — 1 job = 1 workspace
- `runtime/reports/` — レポート保存先
- `runtime/logs/` — 監査ログ

---

## 固定するもの / 差し替えるもの

### 固定 (API 版でも Team 版でも共通)
- Discord bot
- task schema
- approval policy
- danger operation classifier
- Hermes memory schema
- session search API
- skill 保存ルール
- report format
- metrics format (MOR / PRR / PCR)
- workspace 構成
- job state machine

### 差し替える (移行時に変わる)
- Claude 実行経路 (`agent_sdk_executor` → `claude_code_executor`)
- 認証方法
- 実行時フックの張り方
- Claude 固有の共有パッケージ方法

---

## Job State Machine

```
PENDING → RUNNING → DONE
                  → FAILED
```

- 失敗時も workspace と report を保持する (監査のため)
- retry は Takumi Core 側で管理する (CP-02 以降)

---

## Workspace 構成 (1 job = 1 workspace)

```
runtime/workspaces/jobs/{job_id}/
├── artifacts/
├── logs/
└── result.json
```

`result.json` と `runtime/reports/{job_id}.json` の両方にレポートを保存する。

---

## メトリクス (CP-03 以降で実装)

| 指標 | 説明 |
|---|---|
| MOR | Memory Operation Rate — memory_write 呼び出し率 |
| PRR | Past Reference Rate — session_search 呼び出し率 |
| PCR | Proceduralization Rate — task 完了後の skill 化率 |

---

## Claude 依存にしてはいけないもの

- 長期記憶の正本
- 承認状態
- 危険操作ルール
- ジョブ履歴
- 再試行回数
- 停止条件
- 成果物メタデータ
- 評価指標
