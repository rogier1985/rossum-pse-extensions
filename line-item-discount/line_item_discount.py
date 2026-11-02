"""Paste-ready Rossum Python 3.12 serverless line-item discount extension."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

CENT = Decimal("0.01")
FIELD_PAIRS = (
    ("item_amount", "item_amount_calculated"),
    ("item_tax", "item_tax_calculated"),
    ("item_amount_total", "item_total_amount_calculated"),
)


def as_decimal(value: object) -> Decimal:
    """Read a finite, unformatted Rossum number without float arithmetic."""
    if value is None or isinstance(value, bool):
        raise ValueError("A required numeric value is empty or invalid.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("A required numeric value is empty or invalid.") from exc
    if not result.is_finite():
        raise ValueError("All numeric values must be finite.")
    return result


def calculate_discounted_amounts(amounts, percentage):
    """Round each net amount and reconcile the column on its final row."""
    rate = as_decimal(percentage)
    if not Decimal(0) <= rate <= Decimal(100):
        raise ValueError("discount_percentage must be between 0 and 100.")
    values = [as_decimal(value) for value in amounts]
    if not values:
        return []
    # Keep multiplication and summation exact even for long decimal inputs.
    with localcontext() as context:
        context.prec = max(
            28,
            max(len(v.as_tuple().digits) + abs(v.as_tuple().exponent) for v in values)
            + len(rate.as_tuple().digits) + abs(rate.as_tuple().exponent)
            + len(str(len(values))) + 10,
        )
        factor = Decimal(1) - rate / Decimal(100)
        rounded = [(value * factor).quantize(CENT, rounding=ROUND_HALF_UP)
                   for value in values]
        target = (sum(values, Decimal(0)) * factor).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        rounded[-1] += target - sum(rounded, Decimal(0))
    return rounded


def rossum_hook_request_handler(payload: dict) -> dict:
    from txscript import TxScript

    transaction = TxScript.from_payload(payload)
    try:
        rows = list(transaction.field.line_items)
        if not rows:
            return transaction.hook_response()
        percentage = transaction.field.discount_percentage
        updates = []
        for source, destination in FIELD_PAIRS:
            # Validate every destination before making any changes.
            for row in rows:
                getattr(row, destination)
            amounts = calculate_discounted_amounts(
                [getattr(row, source) for row in rows], percentage
            )
            updates.append((destination, amounts))
    except (AttributeError, TypeError, ValueError, InvalidOperation) as exc:
        transaction.show_error(
            "Cannot calculate line-item discounts. Check discount_percentage, "
            "all source amounts, and the required schema fields. " + str(exc)
        )
        return transaction.hook_response()

    for destination, amounts in updates:
        for row, amount in zip(rows, amounts):
            setattr(row, destination, amount)
    return transaction.hook_response()
