"""Paste-ready Python 3.12 Rossum function: distribute spatial job headers."""

from bisect import bisect_right
from math import isfinite
from statistics import median

DEFAULTS = {
    "header_table_id": "header_lines",
    "source_field_id": "item_job",
    "line_table_id": "line_items",
    "target_field_id": "item_job2",
    "row_anchor_field_id": None,
    "carry_across_pages": True,
}


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.get("children", []))


def location(cell):
    content = cell.get("content") or {}
    page, box = content.get("page"), content.get("position")
    if type(page) is not int or page < 1:
        return None
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    if any(type(v) not in (int, float) or not isfinite(v) for v in box):
        return None
    left, top, right, bottom = box
    if left >= right or top >= bottom:
        return None
    return page, (top + bottom) / 2


def row_location(row, settings):
    cells = [cell for cell in walk(row.get("children", []))
             if cell.get("category") == "datapoint"
             and cell.get("schema_id") != settings["target_field_id"]]
    anchor = settings["row_anchor_field_id"]
    if anchor:
        cells = [cell for cell in cells if cell.get("schema_id") == anchor]
    positions = [pos for cell in cells if (pos := location(cell)) is not None]
    if not positions or len({pos[0] for pos in positions}) != 1:
        return None
    return positions[0][0], median(pos[1] for pos in positions)


def rossum_hook_request_handler(payload):
    response = {"messages": [], "operations": []}

    def warn(message):
        response["messages"].append({"type": "warning", "content": message})

    supplied = payload.get("settings") or {}
    if not isinstance(supplied, dict):
        warn("Job distribution: settings must be an object.")
        return response
    settings = {**DEFAULTS, **supplied}
    for key in ("header_table_id", "source_field_id", "line_table_id", "target_field_id"):
        if not isinstance(settings[key], str) or not settings[key].strip():
            warn("Job distribution: invalid setting " + key)
            return response
    anchor = settings["row_anchor_field_id"]
    if ((anchor is not None and (not isinstance(anchor, str) or not anchor.strip()))
            or type(settings["carry_across_pages"]) is not bool
            or anchor == settings["target_field_id"]):
        warn("Job distribution: invalid anchor or carry_across_pages setting.")
        return response

    nodes = list(walk(payload.get("annotation", {}).get("content", [])))
    tables = []
    for key in ("header_table_id", "line_table_id"):
        matches = [node for node in nodes if node.get("schema_id") == settings[key]
                   and node.get("category") == "multivalue"]
        if len(matches) != 1:
            warn("Job distribution: expected one table " + settings[key])
            return response
        tables.append(matches[0])
    headers, lines = tables
    jobs = {}
    for row in headers.get("children", []):
        cells = [cell for cell in walk(row.get("children", []))
                 if cell.get("schema_id") == settings["source_field_id"]]
        if len(cells) != 1 or (pos := location(cells[0])) is None:
            warn("Job distribution: every header needs one positioned job field; no values changed.")
            return response
        value = (cells[0].get("content") or {}).get("value") or ""
        if pos in jobs and jobs[pos] != value:
            warn("Job distribution: conflicting jobs at the same position; no values changed.")
            return response
        jobs[pos] = value
    positions = sorted(jobs)
    skipped = 0
    for row in lines.get("children", []):
        targets = [cell for cell in walk(row.get("children", []))
                   if cell.get("schema_id") == settings["target_field_id"]]
        pos = row_location(row, settings)
        if pos is None or len(targets) != 1 or targets[0].get("id") is None:
            skipped += 1
            continue
        index = bisect_right(positions, pos) - 1
        if index < 0 or (not settings["carry_across_pages"]
                         and positions[index][0] != pos[0]):
            skipped += 1
            continue
        value = jobs[positions[index]]
        target = targets[0]
        if (target.get("content") or {}).get("value") != value:
            response["operations"].append({
                "op": "replace", "id": target["id"],
                "value": {"content": {"value": value}},
            })
    if skipped:
        warn(f"Job distribution: left {skipped} row(s) unchanged because a position, "
             "destination, or preceding job header was unavailable.")
    return response
