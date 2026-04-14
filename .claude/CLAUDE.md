# CLAUDE.md

このリポジトリは **Takumi Local Autonomy V2** 用です。

## Mission
このV2の目的は、Discord から自然言語で依頼できる、**ローカル向けの安全な半自律作業代行基盤** を作ることです。

役割分担は次を前提にします。

- **Takumi Core** = 司令塔
- **Hermes** = 記憶 / 過去参照 / skill の正本
- **Claude Code / Executor** = 実行エンジン
- **Discord** = 人間との窓口
- **Local Host** = ホスト
- **Job Sandbox** = 実際の作業場

目標は一発のデモではなく、次のループを継続的に回すことです。

**Observe → Recall → Think → Act → Review → Report → Save → Repeat**

## Non-negotiable rules

1. **Recall First**
   - 重要な判断の前に、この repo の docs と必要な過去記録を確認すること。
   - 以前の判断、現在の milestone、checkpoint 基準を優先すること。

2. **Host is not the workspace**
   - ローカルPC本体を直接作業場として扱わないこと。
   - 原則として 1ジョブ1sandbox で作業すること。

3. **Prefer copy-in / copy-out**
   - 入力は sandbox にコピーして受け取ること。
   - repo は sandbox 内で clone すること。
   - 成果物は output と diff で返すこと。

4. **Do not optimize for cleverness over reproducibility**
   - 巧妙さより再現性と監査しやすさを優先すること。
   - 変更は小さく保つこと。
   - 暗黙の前提より、明示された docs と state を優先すること。

5. **Do not perform risky actions without stopping**
   次の操作に到達したら実行前に止まること。
   - ホストへの書き戻し
   - 元 repo への push
   - PR の実作成
   - 外部サービスへの書き込み
   - secrets の使用
   - 広範囲かつ不可逆な変更
   - sandbox 境界変更

6. **Checkpoint discipline**
   - 現在の checkpoint 基準を満たすまで次の checkpoint に進まないこと。
   - 部分達成しかできていない場合は、その不足を明確に報告すること。

7. **No fake completion**
   - 証拠なしに完了を主張しないこと。
   - 実装タスクでは changed files、validation、remaining risks を示すこと。

8. **Always leave a handoff trail**
   大きめの作業セッションの最後には、必ず次を残すこと。
   - 何をやったか
   - 何が完了したか
   - 何が未完了か
   - 何を検証したか
   - 次の最短手
   - memory / skill 候補

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
- 実装補足は `README` や設計 docs

## Required working style
- まず今回の依頼を repo 文脈で言い換えること。
- 現在の phase / checkpoint を特定すること。
- 編集前に短い計画を示すこと。
- できるだけ sandbox 内で完結すること。
- 小さい単位で実行すること。
- test / lint / diff / 明示的確認で検証すること。
- 結果を checkpoint 基準に照らして要約すること。

## Output format for substantial tasks
大きめのタスクでは、最終応答を次の構成にすること。

1. Goal
2. Current checkpoint
3. Plan
4. Findings / Changes
5. Validation
6. Review points
7. Risks / blockers
8. Suggested next step
9. Memory candidates
10. Skill candidates

## Implementation bias
このV2では、次を優先すること。

- job ごとに閉じた workspace
- 限定権限の tool / MCP
- executor を差し替え可能な設計
- Takumi Core における明示的な state 管理
- Hermes を正本にした Recall / Save
- audit しやすい logs / reports / handoff

次は避けること。

- ローカル全域を前提にした設計
- model 固有前提を core に埋め込むこと
- 状態を会話だけに隠すこと
- checkpoint 未通過のまま広く作り始めること
- IAM が必要なログ調査を前提に組むこと

## When blocked
必要な情報が足りない場合、勝手に補完しないこと。  
代わりに次を報告すること。

- 何が不足しているか
- なぜそれが進行を止めているか
- 進めるために必要な最小判断は何か

## Definition of good progress
良い進捗とは、次のいずれかが起きた状態を指します。

- checkpoint 基準の一つを満たした
- 証拠付きで blocker を減らした
- 再利用可能な手順や docs を作った
- sandbox 境界や承認条件を明確にした
- memory / skill 候補を将来使える形で残した
