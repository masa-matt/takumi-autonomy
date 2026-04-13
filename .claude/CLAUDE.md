# CLAUDE.md

このリポジトリは **Takumi Autonomy on VPS** の PoC 用です。

## Mission
このPoCの目的は、VPS上で安全に動く半自律型エージェント基盤を構築することです。  
以下の役割分担を前提にします。

- **Takumi Core** = オーケストレーター / 司令塔
- **Hermes** = 記憶 / 過去参照 / スキルの正本
- **Claude Executor / Claude Code** = 交換可能な実行エンジン
- **Discord** = 人間とのインターフェース

目標は一発のデモではなく、次のループを継続的に回せることです。

**Observe → Compare → Think → Act → Report → Save → Repeat**

## Non-negotiable rules
1. **Recall First**
   - 重要な設計判断や実装判断の前に、このrepo内の既存ドキュメントを確認すること。
   - 場当たり的な判断より、過去の決定・現在のマイルストーン・checkpoint基準を優先すること。

2. **Do not optimize for cleverness over reproducibility**
   - 巧妙さより、再現性と監査しやすさを優先すること。
   - 変更は小さく保つこと。
   - 暗黙の前提より、明示されたファイルと記録を優先すること。

3. **Do not perform risky actions without stopping**
   次の操作は、実行前に止まって確認を取ること。
   - 重要ファイルの削除
   - 権限変更
   - force push
   - 本番設定や実インフラの変更
   - secrets / tokens / SSH鍵 / 認証情報への接触
   - 広範囲かつ不可逆な変更

4. **Checkpoint discipline**
   - 現在のcheckpoint基準を満たすまで、次のphaseへ進まないこと。
   - 部分達成しかできていない場合は、その不足を明確に報告すること。

5. **No fake completion**
   - 証拠なしに完了を主張しないこと。
   - 実装タスクでは、変更ファイル・検証結果・残リスクを示すこと。

6. **Always leave a handoff trail**
   意味のある作業セッションの最後には、必ず次を更新または出力すること。
   - 何を試したか
   - 何を変更したか
   - 何が通ったか / 何が失敗したか
   - 何が残っているか
   - 次に取るべき推奨アクション

## Source-of-truth files
存在する場合、まず次の順で読むこと。

1. `docs/project-charter.md`
2. `docs/checkpoints.md`
3. `docs/current-milestone.md`
4. `docs/session-brief.md`
5. `docs/handoff.md` または最新の handoff note
6. `README.md`

これらが競合する場合は、次の優先順位で解釈すること。

- 直近の作業範囲は `current-milestone` / `session-brief`
- 受け入れ基準は `checkpoints`
- 全体方針は `project-charter`
- ローカル利用方法は `README`

## Required working style
- まずタスクを repo の文脈で言い換えること。
- 現在の phase / checkpoint を特定すること。
- 編集前に短い計画を示すこと。
- 小さい単位で実行すること。
- 可能なら tests / lint / 明示的な確認で検証すること。
- 結果を checkpoint 基準に照らして要約すること。

## Output format for substantial tasks
大きめのタスクでは、最終応答を次の構成にすること。

1. Goal
2. Current checkpoint
3. Plan
4. Changes made
5. Validation
6. Risks / blockers
7. Suggested next step

## Implementation bias
このPoCでは、次を優先すること。

- モジュール化された構成
- executor を差し替え可能な設計
- Takumi Core における明示的な state 管理
- 長期記憶の正本としての Hermes
- 隔離された workspace
- 安全なログと監査可能なレポート

次は避けること。

- model固有の前提を core architecture に埋め込むこと
- 状態をプロンプトの中だけに隠すこと
- checkpoint必要性のない広範なリファクタ
- Phase 1 / 2 が安定する前の過剰な複雑化

## When blocked
必要な情報が足りない場合、勝手に補完しないこと。  
代わりに次を報告すること。

- 何が不足しているか
- なぜそれが進行を止めているか
- 進めるために必要な最小の判断は何か

## Definition of good progress
良い進捗とは、次のいずれかが起きた状態を指す。

- checkpoint基準の一つを満たした
- 証拠付きで blocker を減らした
- 再利用可能な手順や文書を作った
- 危険な前提や曖昧さを明確化した