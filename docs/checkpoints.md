# Takumi Local V2 Checkpoints

## CP-LV2-00 仕様固定

### 目的
V2 の設計境界を固定する。

### 通過条件（**通過 2026-04-18**）
- [x] ローカル版の目的が明文化されている
- [x] ホストと sandbox の役割分離が明記されている
- [x] Discord / Core / Hermes / Claude Code / Sandbox の責務が明記されている
- [x] IAM が必要なログ調査がスコープ外であると明記されている
- [x] 危険操作・承認原則・停止条件が明文化されている
- [x] MOR / PRR / PCR と sandbox 境界観測の方針が定義されている
- [x] `.claude/CLAUDE.md` の V2 初版がある

### 成果物
- `docs/project-charter.md`
- `docs/checkpoints.md`
- `docs/claude/handoff-pack.md`
- `.claude/CLAUDE.md`

### Git tag
- `cp-lv2-00-spec-frozen`

---

## CP-LV2-01 Job Sandbox 基盤

### 目的
1ジョブ1sandbox を作れる状態にする。

### 通過条件（**通過 2026-04-18**）
- [x] job id ごとに workspace を作成できる
- [x] `input/`, `repos/`, `output/`, `logs/`, `state/` が分離される
- [x] 書き込み範囲が job 配下に限定される
- [x] job 完了後に成果物とログを回収できる
- [x] sandbox 境界の想定が文書化されている

### 成果物
- `takumi/sandbox/`
- `docs/architecture-baseline.md`
- `docs/runbooks/sandbox.md`

### Git tag
- `cp-lv2-01-sandbox-base`

---

## CP-LV2-02 Discord 受付とジョブ状態管理

### 目的
Discord から依頼してジョブとして扱える状態にする。

### 通過条件（**通過 2026-04-18**）
- [x] Discord から自然言語で依頼を受け取れる
- [x] job id を採番できる
- [x] job 状態を最低限 `queued / running / blocked / done / failed` で管理できる
- [x] 中間報告を返せる
- [x] 承認待ちメッセージを送れる

### 成果物
- `takumi/discord/`
- `takumi/core/job_state.*`
- `docs/runbooks/discord-ops.md`

### Git tag
- `cp-lv2-02-discord-intake`

---

## CP-LV2-03 Repo / File 取り込み

### 目的
ローカルファイルと複数 repo を sandbox に安全に取り込める状態にする。

### 通過条件（**通過 2026-04-18**）
- [x] ローカルファイルを sandbox の `input/` にコピーできる（inbox 経由）
- [x] 1つ以上の repo を sandbox に clone できる（Claude Code がプロンプト指示に従い repos/ にクローン）
- [x] 複数 repo を job 内で扱える（repos/ 以下に複数 clone 可能）
- [x] 元 repo の直編集を避ける設計になっている（clone-in / sandbox 境界）
- [x] repo / file の取り込みルールが文書化されている（`docs/runbooks/repo-and-file-ingress.md`）

### 成果物
- `takumi/core/input_ingress.*`
- `takumi/core/repo_manager.*`
- `docs/runbooks/repo-and-file-ingress.md`

### Git tag
- `cp-lv2-03-ingress`

---

## CP-LV2-04 Hermes Recall / Save 統合

### 目的
毎回ゼロから始めない状態を作る。

### 通過条件（**通過 2026-04-18**）
- [x] `hermes_session_search` が呼べる
- [x] `hermes_memory_write` が呼べる
- [x] `hermes_skill_create` または `hermes_skill_update` が呼べる
- [x] セッション終了時に memory 候補を残せる
- [x] hooks または同等機構で Recall / Save のログが取れる（コンテナログ INFO で確認）

### 成果物
- `takumi/hermes/` ✅（models / memory / skill）
- `docs/runbooks/hermes-bridge.md` ✅
- `docs/metrics.md` ✅

### Git tag
- `cp-lv2-04-hermes-bridge`

---

## CP-LV2-05 単一 repo 調査・修正・検証

### 目的
1つの repo に対する実務的な調査と修正を回せる状態にする。

### 通過条件（**通過 2026-04-18**）
- [x] 単一 repo の構造調査ができる
- [x] failing test / lint の原因調査ができる
- [x] 最小差分で修正できる
- [x] test / lint / diff を報告できる
- [x] handoff を残せる

### 成果物
- `takumi/core/executor_adapter.py` ✅
- `docs/runbooks/single-repo-workflow.md` ✅
- `docs/examples/single-repo-investigation.md` ✅

### Git tag
- `cp-lv2-05-single-repo-flow`

---

## CP-LV2-06 複数 repo 比較と影響範囲整理

### 目的
複数 repo を使った比較・調査を安全に回せる状態にする。

### 通過条件（**通過 2026-04-18**）
- [x] 複数 repo を同一 job で取り扱える（repos/ に複数 clone 可能）
- [x] API / interface / config の差分比較ができる（プロンプト手順で指示）
- [x] 影響範囲の要約を返せる（comparison-report.md テンプレート）
- [x] 危険な広範囲変更は実行せず止まれる（プロンプトの stop 条件）
- [x] handoff に repo ごとの観測結果を残せる（handoff.md + comparison-report.md）

### 成果物
- `docs/runbooks/multi-repo-analysis.md` ✅
- `docs/templates/comparison-report.md` ✅

### Git tag
- `cp-lv2-06-multi-repo`

---

## CP-LV2-07 PR 本文案と PR Review

### 目的
PR を作る前段の実務を支援できる状態にする。

### 通過条件（**通過 2026-04-18**）
- [x] 差分から PR タイトル案を作れる（プロンプト指示）
- [x] PR 本文案を作れる（pr-body.md テンプレート参照）
- [x] review 観点を整理できる（pr-review.md テンプレート）
- [x] PR review コメント草案を作れる（ファイル・行番号付き）
- [x] 実 PR 作成は承認境界の外にあると明示されている（runbook + prompt）

### 成果物
- `docs/runbooks/pr-workflow.md` ✅
- `docs/templates/pr-body.md` ✅
- `docs/templates/pr-review.md` ✅

### Git tag
- `cp-lv2-07-pr-support`

---

## CP-LV2-08 承認境界・停止条件・handoff 運用

### 目的
半自律運用として安全に回せる状態にする。

### 通過条件（**通過 2026-04-18**）
- [x] 要承認操作一覧が実装と docs の両方で一致している（approval-and-stop-conditions.md ↔ job_runner.py）
- [x] 停止条件が実際に機能する（_classify + プロンプト stop 条件）
- [x] blocked 時に理由と必要入力を返せる（gateway.py BLOCKED ハンドリング）
- [x] 毎セッションで handoff が残る（output/handoff.md 指示 + docs/handoff.md）
- [x] report / logs / memory candidates が残る（Hermes write_memory + create_skill_draft）

### 成果物
- `docs/runbooks/approval-and-stop-conditions.md` ✅
- `docs/handoff.md` ✅（更新）
- `docs/operating-rules.md` ✅

### Git tag
- `cp-lv2-08-ops-safety`

---

## CP-LV2-09 V2 運用試験

### 目的
Discord からの依頼を通じて、V2 を実務に近い形で連続運用する。

### 通過条件（**PoC 通過 2026-04-18 / 実運用継続中**）
- [x] 3件以上の実タスクを Discord 経由で処理した（5件以上確認）
- [x] 少なくとも1件で Recall が効いた（スクリーンショット確認）
- [x] 少なくとも1件で memory が保存された（ログ確認）
- [x] 少なくとも1件で skill 候補が出た（ログ確認）
- [x] 危険操作で少なくとも1回正しく停止した（deny / blocked 実装確認）
- [x] handoff / report の品質が維持された（docs/handoff.md 更新確認）

### 成果物
- `reports/v2-trial-report.md` ✅
- `docs/retrospectives/2026-04-18-phase1-complete.md` ✅
- `docs/metrics.md` ✅

### Git tag
- `cp-lv2-09-trial-run`

---

## 判定メモ

### checkpoint を通過とみなしてよい条件
- docs と実装の両方がそろっている
- 実際の確認手順が存在する
- handoff で次回に引き継げる
- 通過条件に対する証拠がある

### 通過とみなしてはいけない条件
- 実装だけあって docs がない
- docs だけあって実体がない
- 手動でしか分からない
- 危険操作が曖昧
- 次回に引き継げない
