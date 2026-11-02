import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("jobs", Path(__file__).parents[1] / "main.py")
jobs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jobs)


def cell(schema, value, y=None, page=1, identifier=1):
    return {"category": "datapoint", "schema_id": schema, "id": identifier,
            "content": {"value": value, "page": page,
                        "position": [10, y, 100, y + 10] if y is not None else None}}


def row(*cells):
    return {"category": "tuple", "children": list(cells)}


def payload(headers=None, lines=None, settings=None):
    return {"settings": settings or {}, "annotation": {"content": [
        {"category": "section", "children": [
            {"category": "multivalue", "schema_id": "header_lines", "children": headers or []},
            {"category": "multivalue", "schema_id": "line_items", "children": lines or []}]}]}}


def header(value, y, page=1):
    return row(cell("item_job", value, y, page))


def line(y, identifier=10, page=1, value="old"):
    return row(cell("description", "item", y, page),
               cell("item_job2", value, identifier=identifier))


class DistributionTests(unittest.TestCase):
    def run_hook(self, headers, lines, settings=None):
        return jobs.rossum_hook_request_handler(payload(headers, lines, settings))

    def test_example_and_unsorted_extraction_order(self):
        result = self.run_hook([header("3434454", 300), header("328327", 100)],
                               [line(400, 4), line(150, 1), line(450, 5), line(200, 2)])
        self.assertEqual([(op["id"], op["value"]["content"]["value"])
                          for op in result["operations"]],
                         [(4, "3434454"), (1, "328327"), (5, "3434454"), (2, "328327")])

    def test_page_order_and_continuation(self):
        result = self.run_hook([header("A", 800), header("B", 300, 2)],
                               [line(30, 1, 2), line(400, 2, 2)])
        self.assertEqual([op["value"]["content"]["value"] for op in result["operations"]], ["A", "B"])
        result = self.run_hook([header("A", 800)], [line(30, 1, 2)], {"carry_across_pages": False})
        self.assertEqual(result["operations"], [])
        self.assertTrue(result["messages"])

    def test_missing_positions_and_rows_above_header_preserved(self):
        result = self.run_hook([header("A", 100)], [line(None), line(20)])
        self.assertEqual(result["operations"], [])
        self.assertIn("2 row(s)", result["messages"][0]["content"])

    def test_invalid_header_aborts_instead_of_spreading_previous_job(self):
        result = self.run_hook([header("A", 100), header("B", None)], [line(400)])
        self.assertEqual(result["operations"], [])
        self.assertTrue(result["messages"])

    def test_blank_header_ends_previous_group(self):
        result = self.run_hook([header("A", 100), header("", 300)], [line(400)])
        self.assertEqual(result["operations"][0]["value"], {"content": {"value": ""}})

    def test_idempotence_and_destination_position_excluded(self):
        item = line(200, value="A")
        item["children"][1]["content"].update(page=9, position=[1, 1, 2, 2])
        self.assertEqual(self.run_hook([header("A", 100)], [item])["operations"], [])

    def test_anchor_overrides_other_cells(self):
        item = line(200)
        item["children"].append(cell("other", "x", 800, 2))
        self.assertEqual(self.run_hook([header("A", 100)], [item])["operations"], [])
        self.assertEqual(len(self.run_hook([header("A", 100)], [item],
                                         {"row_anchor_field_id": "description"})["operations"]), 1)

    def test_conflicting_headers(self):
        self.assertEqual(self.run_hook([header("A", 100), header("B", 100)],
                                      [line(200)])["operations"], [])

    def test_empty_tables(self):
        self.assertEqual(self.run_hook([], []), {"messages": [], "operations": []})

    def test_missing_target_does_not_affect_other_rows(self):
        result = self.run_hook([header("A", 100)],
                               [row(cell("description", "x", 200)), line(300)])
        self.assertEqual(len(result["operations"]), 1)
        self.assertTrue(result["messages"])

    def test_custom_table_id(self):
        data = payload([header("A", 100)], [line(200)], {"line_table_id": "lines_items"})
        data["annotation"]["content"][0]["children"][1]["schema_id"] = "lines_items"
        self.assertEqual(len(jobs.rossum_hook_request_handler(data)["operations"]), 1)

    def test_invalid_settings(self):
        result = self.run_hook([], [], {"carry_across_pages": "false"})
        self.assertTrue(result["messages"])


if __name__ == "__main__":
    unittest.main()
