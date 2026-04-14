# Claude Code Handoff Pack for Takumi Local Autonomy V2

## 0. この資料の役割

この資料は、**Takumi Local Autonomy V2** を Claude Code にブレずに進めてもらうための作業パックです。

このV2では、Claude Code を「強い実行エンジン」として使います。  
ただし主役は Claude Code ではなく、次の構造です。

- **Takumi Core** = 司令塔
- **Hermes** = 記憶・過去参照・skill の正本
- **Claude Code** = sandbox 内で動く実行役
- **Discord** = 業務インターフェース
- **Local Host** = ホスト
- **Job Sandbox** = 実際の作業場

この資料の目的は、コンテキストが失われても次を見失わないことです。

1. このV2の境界
2. 何を作ってよく、何を作ってはいけないか
3. 今どの checkpoint か
4. 何をもって通過とするか
5. 次セッションへ何を引き継ぐか

---

## 1. まず守るべき結論

### 1.1 ローカルPC本体は作業場ではない
実際の作業は **1ジョブ1sandbox** を原則とする。

### 1.2 repo は sandbox 内で clone する
ホスト上の元 repo を直編集しない。

### 1.3 ファイルはコピーして渡す
必要な input だけ sandbox にコピーする。

### 1.4 成果物は回収してレビューする
output を人間が確認したうえで採用する。

### 1.5 Recall / Save は Hermes を正本にする
Claude Code セッション継続だけに依存しない。

### 1.6 危険判定は Takumi Core 側
push・外部書き込み・不可逆操作・広範囲変更は止まる。

---

## 2. このV2で実現したいユーザー体験

Discord でこんな依頼が自然にできる状態を目指します。

- 「この repo の failing test を直して」
- 「この issue の影響範囲を見て」
- 「この PR をレビューして」
- 「この複数 repo の差分を比較して」
- 「このファイルをもとに docs を作って」
- 「まず調査して、次に何を確認すべきか返して」

期待する返し方は、単なる「できた / できない」ではありません。

- 調査結果
- 実施内容
- 差分
- 検証結果
- 確認観点
- 残課題
- 次の最短手
- Hermes に保存すべき学び

---

## 3. Source of Truth

Claude Code は、存在する場合まず次を読むこと。

1. `.claude/CLAUDE.md`
2. `docs/project-charter.md`
3. `docs/checkpoints.md`
4. `docs/current-milestone.md`
5. `docs/session-brief.md`
6. 最新の `docs/handoff.md` または handoff note
7. `README.md`

優先順位は次の通り。

- 今回の作業範囲: `current-milestone.md` / `session-brief.md`
- 通過条件: `checkpoints.md`
- 全体方針: `project-charter.md`
- 実装上の補足: README / 設計メモ / 既存 docs

---

## 4. repo 推奨配置

```text
repo/
├─ .claude/
│  └─ CLAUDE.md
├─ docs/
│  ├─ project-charter.md
│  ├─ checkpoints.md
│  ├─ current-milestone.md
│  ├─ session-brief.md
│  ├─ handoff.md
│  ├─ architecture-baseline.md
│  └─ claude/
│     └─ handoff-pack.md
├─ takumi/
│  ├─ core/
│  ├─ discord/
│  ├─ hermes_bridge/
│  ├─ sandbox/
│  └─ jobs/
└─ README.md
```

---

## 5. このV2で作るべき最小構成

### A. Core
- job 受付
- job id 発行
- 状態遷移
- 承認待ち
- 停止条件
- result / handoff 管理

### B. Sandbox
- 1ジョブ1workspace
- input / repos / output / logs / state
- repo clone
- file copy-in / copy-out
- write 範囲制御

### C. Discord Bot
- 依頼受付
- ステータス通知
- 承認問い合わせ
- 完了報告
- follow-up 指示受信

### D. Hermes Bridge
- session_search
- memory_write
- skill_create / update

### E. 作業支援
- テスト実行
- lint
- diff 収集
- PR本文案
- PR review

---

## 6. 現段階で入れないもの

最初から次を実装しようとして複雑化しないこと。

- IAM が必要なログ調査
- 本番向けの直接権限
- 自動 push / 自動 merge / 自動 deploy
- ローカル全域検索
- 秘密情報の自動探索
- ホスト常駐アプリへの深い統合
- 危険な shell の自由化

---

## 7. 作業判断の基本ルール

### 7.1 Recall First
まず既存 docs と Hermes の過去記録を確認する。

### 7.2 Checkpoint discipline
今の checkpoint が通るまで次へ進まない。

### 7.3 Small diff
大きな設計ジャンプをしない。  
小さく作り、検証し、handoff を残す。

### 7.4 Sandbox first
ホストを触らずに sandbox で完結できる形を優先する。

### 7.5 Approval before irreversible actions
push / 外部書き込み / 本体反映は必ず止まる。

---

## 8. 典型的な実務フロー

### フロー1: 単一 repo の修正
1. Discord で依頼受領
2. job 作成
3. repo を sandbox に clone
4. Hermes で類似 task を検索
5. 調査
6. 修正
7. test / lint
8. diff と検証結果整理
9. handoff / report
10. memory / skill 保存

### フロー2: 複数 repo 比較
1. job 作成
2. 複数 repo clone
3. 比較対象の整理
4. 契約差分 / API差分 / 影響範囲調査
5. 要約
6. 次アクション提案
7. handoff 保存

### フロー3: PR review
1. 対象差分の取得
2. 既存 docs / 設計方針確認
3. 影響範囲確認
4. regression 観点洗い出し
5. review comment 下書き
6. 結果要約
7. handoff 保存

---

## 9. Claude Code に期待する出力形式

中規模以上の作業では、最終報告を次の順で返す。

1. Goal
2. Current checkpoint
3. Plan
4. Findings / Changes
5. Validation
6. Review points
7. Risks / Blockers
8. Suggested next step
9. Memory candidates
10. Skill candidates

---

## 10. 承認が必要な操作

次に到達したら止まること。

- ホストへの書き戻し
- 元 repo への push
- PR の実作成
- 外部サービス書き込み
- secrets 利用
- 大規模 rename / delete
- 複数 repo の広範囲変更
- sandbox 境界変更

---

## 11. 自動で進めてよい操作

- sandbox 作成
- input 配置
- repo clone
- 読み取り
- 調査
- sandbox 内編集
- test / lint
- diff 作成
- PR 本文案作成
- PR review 草案作成
- handoff 生成
- Hermes への保存候補整理

---

## 12. セッション開始時に Claude Code にやらせること

セッション開始時の初手は毎回これです。

1. source of truth を読む
2. 現在の phase / checkpoint を特定する
3. 受け入れ条件を列挙する
4. 今回の作業範囲を言い換える
5. 小さく安全な計画を出す
6. 危険操作があり得る場合は先に宣言する

---

## 13. セッション終了時に必ず残すもの

- 何をやったか
- 何が完了したか
- 何が未完了か
- 何が危険 / 未確定か
- 何を検証したか
- 次の最短手
- memory 候補
- skill 候補
- checkpoint 通過判定

---

## 14. Handoff の品質基準

良い handoff とは、次のセッションの自分や別の executor が読んですぐ再開できるものです。

最低限次を含めること。

- session goal
- current checkpoint
- done / not done
- changed files
- validation
- blocker / risk
- approval needed
- next recommended action
- memory / skill candidates

---

## 15. よくある失敗

- 現在 checkpoint を確認せずに実装を広げる
- ローカルホスト上の資産を安易に見に行く
- repo の直編集を前提にする
- 危険操作前に止まらない
- 検証なしに完了を主張する
- handoff を残さない
- 記憶候補を拾わない
- skill 化候補を放置する

---

## 16. この資料の使い方

### 人間側
- `docs/project-charter.md` にこのV2の憲法を置く
- `docs/checkpoints.md` に通過条件を置く
- `docs/current-milestone.md` に現在地点を置く
- `docs/session-brief.md` に今回の依頼範囲を書く
- `.claude/CLAUDE.md` に最小ルールを書く

### Claude Code 側
- まず読む
- 次に現在地点を特定する
- 次に最小計画を返す
- 実装は小さく進める
- 最後に handoff を残す

---

## 17. 結論

このV2で重要なのは、**Claude Code を強くすることではなく、仕事の境界を正しく与えること** です。

- ローカル本体を守る
- sandbox を作る
- 必要なものだけ渡す
- Recall / Save を Hermes に寄せる
- Discord から自然に頼める
- 危険なら止まる
- 次回に知見を残す

これを守れば、V2は「ローカルで安全に動く半自律作業代行」として実務に近づきます。
