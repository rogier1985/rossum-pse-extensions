# Line-item discount

Rossum Python 3.12 serverless extension that reads the document-level number
field `discount_percentage` (10 means 10%) and writes amounts **after discount**:

| Source in `line_items` | Destination in the same row |
| --- | --- |
| `item_amount` | `item_amount_calculated` |
| `item_tax` | `item_tax_calculated` |
| `item_total_amount` | `item_total_amount_calculated` |

Each result is `source × (1 − discount_percentage / 100)`, rounded to two
decimal places using decimal half-up rounding. For each column separately, the
extension calculates the rounded discounted sum of the original values, then
adds the difference from the rounded row sum to the **last row of `line_items`**.
For example, three values of 0.05 at 10% become 0.05, 0.05, and 0.04, totaling
0.14. Negative source amounts (credit lines) are supported.

Columns reconcile independently; the extension does not force calculated
amount plus calculated tax to equal calculated total on every individual row.
The last-row adjustment can exceed one cent or change its sign when many tiny
rows accumulate rounding differences.

## Install

1. Ensure the queue schema contains the header number field and all six
   line-item number fields above within the `line_items` multivalue. Destination
   fields must be writable number fields, not formula fields.
2. Create a Serverless Function extension with runtime **Python 3.12** and paste
   the complete contents of `line_item_discount.py` into its code editor.
3. Subscribe to `annotation_content.initialize` and `annotation_content.user_update`
   to calculate after extraction and recalculate when users edit inputs.
4. Connect the required queues and activate. Test on a representative document.

Alternatively, use `hook.example.json` as the Hook API request body after
replacing the queue URL and code placeholder. No settings, credentials, or
network access are required.

Zero percent copies source amounts (subject to rounding); 100% writes zero.
Missing/invalid amounts or percentages, percentages outside 0–100, and missing
schema fields produce a document error and leave existing calculated values
unchanged. Empty tables produce no changes. Reruns always use the original
source fields, so discounts never compound. Use explicit zero for zero tax;
blank values are not assumed to be zero.

## Local verification

```sh
python3 -m unittest discover -s tests -v
```

Tests use a TxScript double; live tenant execution is not included.
Implementation follows [Rossum Transaction Scripts](https://elis.app.rossum.ai/api/docs/openapi/guides/rossum-transaction-scripts/).
