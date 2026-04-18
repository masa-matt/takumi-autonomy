# V3 Vision: One Takumi, Shared Brain

## 一言で

**Takumi は常に「たった一人の同じ人物」として動き、Hermes を共有の記憶として参照する。**
スレッドは同じ人物がこなす個別のタスクであり、並列スレッドは Takumi のマルチタスクである。

---

## 今の問題（V2 の限界）

V2 では 1 ジョブ = 1 sandbox / 1 Claude Code 呼び出し。これが生む無駄:

1. **毎回フレッシュに始まる** — 同じ repo を毎回 clone し、同じ調査を毎回やり直す
2. **文脈が続かない** — スレッド内の続きでも「前のジョブは別人」
3. **知識が活きない** — Hermes に記録はあるが、clone 済みファイルや調査済み構造までは再利用できない
4. **トークンと時間の浪費** — 同じことを毎回 Claude に教え直す

**V3 のゴール**: この無駄をなくし、ナレッジを効率的に次に繋げる。

---

## V3 のコア概念

### 1. 単一 Takumi アイデンティティ

- Discord で話す相手は常に「同じ Takumi」
- SOUL.md の人格 + Hermes の記憶 = Takumi の同一性
- ユーザーは「さっきの件だけど」と言える

### 2. 共有ブレイン（Hermes State）

- 全スレッド・全セッションが同じ Hermes を参照
- 過去の経験・学んだスキル・理解した repo 構造は全スレッドで活用可能
- 「前に hashport-wallet-backend 見たよね」が通じる

### 3. スレッド = タスク単位のセッション

- スレッド開始 = セッション開始
- スレッド内の続きのメッセージ = 同じセッションの続き（sandbox 共有）
- スレッド終了（archive 等） = セッション完了 → Hermes に蒸留保存

### 4. 並列スレッド = マルチタスク

- 別スレッドは別セッション、別 sandbox
- ただし Hermes は共有（並列タスクでも同じ記憶を参照）
- Takumi は「同時に複数の作業を進められる一人の人物」

---

## アーキテクチャのスケッチ

### セッション層（新設）

```
runtime/
  sessions/
    <session_id>.json    ← セッション状態
  memory/                ← Hermes（共有）
    entries/
    skills/
```

セッションの内容:
```json
{
  "session_id": "sess-20260418-xxxx",
  "thread_id": "discord-thread-id",
  "workspace_path": "takumi/jobs/<job_id>",
  "messages": [...],
  "cloned_repos": ["hashport-wallet-backend"],
  "known_facts": ["このスレッドでは Bitcoin ブランチの PR review が目的"],
  "started_at": "...",
  "last_active_at": "..."
}
```

### ワークスペース永続化

- スレッド初回メッセージ → 新 session + 新 workspace
- 継続メッセージ → 既存 session の workspace を再利用（repos/ そのまま残る）
- セッション完了時 → workspace を archive、重要事実は Hermes に蒸留

### Hermes 強化

- **Session-aware recall**: 同一 session の履歴を優先
- **Long-term distillation**: 古いセッションを要約して軽量な知識に圧縮
- **Approved skill injection**: セッション開始時に関連スキルを自動 load
- **Repo structure cache**: 一度調べた repo の構造・テスト方法をキャッシュ

### 並列実行

- 複数セッションを同時実行できる job queue / worker プール
- 各セッションは独立した Claude Code プロセスだが、同じ Hermes を共有
- Race condition 対策: entries/ への書き込みは atomic

---

## ナレッジ効率化の具体策

| 今の無駄 | V3 での解決 |
|---|---|
| 同じ repo を毎回 clone | セッション内で workspace 再利用 |
| 同じ repo 構造を毎回調査 | Hermes に repo structure cache |
| スレッド内で「前の文脈」を忘れる | session_id でメッセージ履歴を保持 |
| 同じスキル手順を毎回プロンプトに書く | approved skill を自動注入 |
| 古い記録が全部同じ重みで残る | 古いものは要約・蒸留して軽量化 |

---

## 段階的移行計画（V2 → V3）

### Phase 2.1: Thread = Session（最短の一歩）

- gateway で `thread_id → session_id` マップを作る
- スレッド内の続きメッセージは同じ workspace を使う
- プロンプトに session 内の過去メッセージを注入
- **これだけでユーザー体験が劇的に改善する**

### Phase 2.2: Hermes の repo structure cache

- ジョブ完了時に「この repo はこういう構造」を Hermes に蒸留
- 次回同じ repo を触る時、構造を再調査せずに cache から読む

### Phase 2.3: Skill の自動注入

- Hermes の approved skills をセッション開始時に load
- プロンプトに「このスキルが使えます」として注入

### Phase 2.4: Long-term distillation

- 古いエントリを要約して軽量な knowledge note に変換
- entries/ と knowledge/ を分離

### Phase 2.5: 並列セッション

- job queue / worker プール
- セッション間の排他制御

---

## 判断が必要な設計論点

1. **スレッド終了の判定**: Discord thread archive？タイムアウト？手動コマンド？
2. **workspace のライフサイクル**: セッション完了後どれくらい残す？
3. **蒸留のタイミング**: 完了時？定期バッチ？
4. **並列実行の上限**: 同時セッション数・CPU / メモリ制約
5. **Hermes の分離**: entries / skills / knowledge / repo-cache をどう分けるか

---

## 関連課題（既知の制約）

- 現状 Docker コンテナ内で Claude Code を呼ぶため、長時間ジョブ・並列ジョブのリソース設計が必要
- Hermes skill の承認フロー（approve/reject コマンド）が未実装 — V3 では必須
- 会話履歴の保持方法（どこまで Hermes に入れるか）を決める必要あり

---

## 次の最短手（提案）

1. この docs/v3-vision.md をレビュー・合意
2. Phase 2.1（Thread = Session）を V2 の延長として実装
   - ここまでは V2 のままでもいけるので検証コストが低い
3. 検証結果を見て V3 本番設計に進む
