from decimal import Decimal
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from line_item_discount import (  # noqa: E402
    FIELD_PAIRS, calculate_discounted_amounts, rossum_hook_request_handler,
)


class DiscountTests(unittest.TestCase):
    def test_rounding_remainder_on_last_row(self):
        self.assertEqual(calculate_discounted_amounts(["0.05"] * 3, 10),
                         list(map(Decimal, ["0.05", "0.05", "0.04"])))
        self.assertEqual(calculate_discounted_amounts(["0.04"] * 3, 10),
                         list(map(Decimal, ["0.04", "0.04", "0.03"])))

    def test_positive_remainder(self):
        self.assertEqual(calculate_discounted_amounts(["0.03"] * 3, 20),
                         list(map(Decimal, ["0.02", "0.02", "0.03"])))

    def test_negative_credit_lines(self):
        self.assertEqual(calculate_discounted_amounts(["-0.05"] * 3, 10),
                         list(map(Decimal, ["-0.05", "-0.05", "-0.04"])))

    def test_boundary_and_fractional_percentages(self):
        self.assertEqual(calculate_discounted_amounts([100], "12.5"), [Decimal("87.50")])
        self.assertEqual(calculate_discounted_amounts([100], 0), [Decimal("100.00")])
        self.assertEqual(calculate_discounted_amounts([100], 100), [Decimal("0.00")])
        self.assertEqual(calculate_discounted_amounts([], 10), [])

    def test_invalid_inputs(self):
        for value in [None, "", "bad", "NaN", "Infinity", True]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    calculate_discounted_amounts([value], 10)
                with self.assertRaises(ValueError):
                    calculate_discounted_amounts([100], value)
        for rate in [-1, 101]:
            with self.assertRaises(ValueError):
                calculate_discounted_amounts([100], rate)

    def transaction(self):
        rows = [SimpleNamespace(**{
            "item_amount": "0.05", "item_tax": "0.03", "item_total_amount": "0.08",
            **{destination: None for _, destination in FIELD_PAIRS},
        }) for _ in range(3)]
        messages = []
        return SimpleNamespace(
            field=SimpleNamespace(discount_percentage=10, line_items=rows),
            show_error=messages.append,
            hook_response=lambda: {"messages": messages},
        )

    def run_handler(self, transaction):
        module = SimpleNamespace(
            TxScript=SimpleNamespace(from_payload=lambda p: transaction),
            is_empty=lambda value: value is None or value == "",
        )
        with patch.dict(sys.modules, {"txscript": module}):
            return rossum_hook_request_handler({})

    def test_handler_all_columns_and_rerun(self):
        tx = self.transaction()
        self.assertEqual(self.run_handler(tx), {"messages": []})
        for source, destination in FIELD_PAIRS:
            expected = calculate_discounted_amounts(
                [getattr(row, source) for row in tx.field.line_items], 10)
            self.assertEqual([getattr(row, destination) for row in tx.field.line_items], expected)
        self.assertEqual(self.run_handler(tx), {"messages": []})
        self.assertEqual(tx.field.line_items[-1].item_amount_calculated, Decimal("0.04"))
        tx.field.discount_percentage = 0
        self.run_handler(tx)
        self.assertEqual(tx.field.line_items[-1].item_amount_calculated, Decimal("0.05"))

    def test_invalid_final_column_prevents_partial_updates(self):
        tx = self.transaction()
        tx.field.line_items[-1].item_total_amount = ""
        self.assertTrue(self.run_handler(tx)["messages"])
        for row in tx.field.line_items:
            for _, destination in FIELD_PAIRS:
                self.assertIsNone(getattr(row, destination))

    def test_missing_destination_reports_error_before_updates(self):
        tx = self.transaction()
        del tx.field.line_items[-1].item_total_amount_calculated
        self.assertTrue(self.run_handler(tx)["messages"])
        self.assertIsNone(tx.field.line_items[0].item_amount_calculated)

    def test_empty_table(self):
        tx = self.transaction()
        tx.field.line_items = []
        self.assertEqual(self.run_handler(tx), {"messages": []})

    def test_empty_or_absent_percentage_calculates_at_zero_percent(self):
        for percentage in [None, "", "absent"]:
            with self.subTest(percentage=percentage):
                tx = self.transaction()
                for row in tx.field.line_items:
                    for _, destination in FIELD_PAIRS:
                        setattr(row, destination, Decimal("42.00"))
                if percentage == "absent":
                    del tx.field.discount_percentage
                else:
                    tx.field.discount_percentage = percentage
                self.assertEqual(self.run_handler(tx), {"messages": []})
                for row in tx.field.line_items:
                    for source, destination in FIELD_PAIRS:
                        self.assertEqual(getattr(row, destination), Decimal(getattr(row, source)))

    def test_empty_percentage_still_validates_source_amounts(self):
        tx = self.transaction()
        tx.field.discount_percentage = ""
        tx.field.line_items[0].item_amount = "invalid"
        self.assertTrue(self.run_handler(tx)["messages"])
        self.assertIsNone(tx.field.line_items[0].item_amount_calculated)


if __name__ == "__main__":
    unittest.main()
