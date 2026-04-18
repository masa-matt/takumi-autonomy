# Example: 単一 repo 調査タスク

## タスク例

```
Discord: https://github.com/example/myapp のテストが落ちてる原因を特定して直して
```

---

## 期待される output/result.md

```
repos/myapp を調べた。pytest を走らせたら test_payment.py::test_refund が落ちてた。

原因は PaymentService のコンストラクタ引数の順番が最近のリファクタで変わったのに、
テスト側がまだ古い引数順を使ってたから。

修正は test_payment.py の3箇所だけ。アプリ本体には触ってない。
修正後の pytest は全部通った。diff は output/changes.diff に置いといた。

残ってる問題は test_invoice.py のいくつかがスキップされてることで、
これは別のチケットで対応予定らしい（TODO コメントにあった）。
```

---

## 期待される output/handoff.md

```markdown
# Handoff: myapp テスト修正

## 調査したこと
- pytest 実行 → 47 tests, 1 failed (test_payment.py::test_refund)
- 失敗の原因: PaymentService(amount, currency, ...) の引数順が v2.3 で変更されたが
  テストは旧シグネチャのまま

## 実施した修正
- test/test_payment.py の PaymentService() 呼び出し3箇所を新シグネチャに更新
- 修正後: pytest 47 tests passed

## 未解決の問題
- test_invoice.py に @pytest.mark.skip が5件ある（TODO: "fix after DB migration"）
  → 別タスクで対応すべき

## 次のアクション候補
- [ ] スキップテストの対応（DB migration 完了後）
- [ ] PR 作成（review 依頼）
```

---

## 期待される output/changes.diff

```diff
diff --git a/test/test_payment.py b/test/test_payment.py
index a1b2c3d..e4f5g6h 100644
--- a/test/test_payment.py
+++ b/test/test_payment.py
@@ -12,7 +12,7 @@ class TestRefund:
     def test_refund_success(self):
-        svc = PaymentService(100, "JPY", gateway=self.mock_gw)
+        svc = PaymentService("JPY", 100, gateway=self.mock_gw)
         result = svc.refund("order-001")
         assert result.status == "refunded"
```

---

## 実際の outbox 構造

```
outbox/
  0418-myappのテストが落ちてる原因/
    changes.diff
    handoff.md
```

（result.md は除外される）
