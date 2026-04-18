# V3 Phase Designs

`docs/v3-vision.md` で示した V3 のゴールを、実装者が順番に進められる形に分解した設計書群。

## Phase 一覧

| Phase | 設計書 | 目的 | 前提 |
|---|---|---|---|
| 2.1 | [phase-2.1-thread-as-session.md](./phase-2.1-thread-as-session.md) | スレッド内で workspace を再利用 | V2 完了 |
| 2.2 | [phase-2.2-repo-structure-cache.md](./phase-2.2-repo-structure-cache.md) | repo の構造調査結果を cache | 2.1 |
| 2.3 | [phase-2.3-skill-auto-injection.md](./phase-2.3-skill-auto-injection.md) | approved skill の自動注入・承認フロー | 2.1 |
| 2.4 | [phase-2.4-long-term-distillation.md](./phase-2.4-long-term-distillation.md) | 古いエントリを knowledge note に蒸留 | 2.1〜2.3 |
| 2.5 | [phase-2.5-parallel-sessions.md](./phase-2.5-parallel-sessions.md) | 複数セッションの並列実行 | 2.1 |

## 実装順序の推奨

**直列推奨**: 2.1 → 2.2 → 2.3 → 2.4 → 2.5

2.1 が土台。これができないと以降の phase で workspace / session の概念が使えない。
2.5 は最後。他の phase が単一プロセスで動いていれば、並列化は後から被せる形で入れられる。

**スキップ可**:
- 2.2（repo cache）は 2.3（skill injection）と独立。省いても 2.3 は進められる
- 2.4（distillation）は蓄積が十分になってからでよい。初期は省略可

## 設計書の読み方

各設計書は以下の章立てで書かれている。実装者はこの順に読めば実装着手できる。

1. **Goal** — 何を解決するか・なぜ重要か
2. **Acceptance Criteria** — 完了判定チェックリスト
3. **Data Model** — 新設する型・保存形式
4. **File Changes** — 新設・修正するファイル一覧
5. **Flow** — 実行時のシーケンス
6. **Edge Cases** — 失敗パターン・想定外の入力への対処
7. **Testing Plan** — 検証手順
8. **Non-goals** — この Phase では扱わないこと

## V2 からの引き継ぎ事項

実装者は以下を前提にしてよい:

- `takumi/core/job_state.py` で Job / JobStatus が定義済み
- `takumi/sandbox/workspace.py` で workspace 作成ロジックが存在
- `takumi/hermes/` で memory / skill の基盤あり
- `takumi/discord/gateway.py` で thread 作成・メッセージ分岐が動いている
- `runtime/memory/{entries,skills}/` にデータが蓄積している

逆に、以下は V2 の制約として残っている:

- スレッド内メッセージごとに新 workspace（2.1 で解決）
- skill は draft のまま蓄積のみ（2.3 で解決）
- Hermes エントリが単調増加（2.4 で解決）
- 同期実行のみ（2.5 で解決）
