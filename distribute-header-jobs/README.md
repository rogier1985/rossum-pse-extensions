# Distribute header jobs and locations to line items

Paste-ready Rossum Python 3.12 serverless extension. Copies `header_lines.item_job`
to `line_items.item_job2` and `header_lines.item_location` to
`line_items.item_location2` based on document position, independent of table row order.
Both values come from the same matched header row, using the job field's position.
The location source does not need its own bounding box.

For example, job 328327 above two rows and job 3434454 above the next two rows
produce destination values `328327, 328327, 3434454, 3434454`.

## Install

1. Ensure the schema has tables `header_lines` and `line_items`, containing
   `item_job` and `item_location` in the header table, and `item_job2` and
   `item_location2` in the line table. Use writable text fields for job codes
   to retain leading zeros. Destinations must not be formula fields.
2. Create a Serverless Function extension using **Python 3.12**. Paste the complete
   contents of `main.py` into its code editor.
3. Subscribe to `annotation_content.initialize` and `annotation_content.updated`.
4. Connect the queue and activate. Test with representative documents.

No dependencies, credentials, or network calls are required. Optional settings
are shown in `settings.example.json`; omitted settings use those defaults.
If the actual table ID is `lines_items`, set `line_table_id` accordingly.

## Matching rules

Headers and rows are ordered by page number, then vertical bounding-box center.
Each row receives the last header at or above its center. By default a job carries
across pages until another header appears. Set `carry_across_pages` to `false`
to require a header on the same page.

The row center is the median center of its positioned cells, excluding the
two destination columns. Set `row_anchor_field_id` to a reliable column such as
`item_description` to use only that column instead. A row with cells spanning
multiple pages is skipped unless a suitable single-page anchor is configured.

Matched destination values are overwritten, including existing manual values.
A blank source value clears its corresponding destination in the matched group.
Reruns omit updates
when the destination already matches. Other cells and extraction positions remain
unchanged; the job header box is not copied into the line-item row.

Rows without usable positions, both unique destinations, or a preceding eligible
header remain unchanged, with a summary warning. A missing/ambiguous table,
missing/unpositioned job header, missing/duplicate location source, or different
jobs or locations at the exact same position
stops the whole update with a warning. This prevents an unreadable header from
silently extending the previous job group.

Assumes one vertical stream of job groups. Side-by-side tables or groups requiring
horizontal matching need a different rule. Multi-line cells with very different
heights are best handled by configuring a reliable row anchor.

## Verification

Run from this directory:

```sh
python3 -m unittest discover -s tests -v
```

Tests use synthetic Rossum payloads; live tenant execution is not included.
Payload and response formats follow the official
[Extensions guide](https://elis.rossum.ai/api/docs/openapi/guides/extensions/)
and [Annotation Content reference](https://elis.rossum.ai/api/docs/openapi/api/annotation-content/).
