"""Keep the README chart tied to the actual synthetic evaluation."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("readme_visual", ROOT / "scripts/render_readme_visual.py")
visual = importlib.util.module_from_spec(spec)
spec.loader.exec_module(visual)


class ReadmeVisualTests(unittest.TestCase):
    def test_checked_in_figure_and_provenance_are_current(self):
        for name, content in visual.artifacts().items():
            self.assertEqual((visual.DEST / name).read_text(encoding="utf-8"), content)

    def test_svg_has_accessible_text_and_no_external_assets(self):
        svg = visual.figure(visual.checked_report())
        root = ET.fromstring(svg)
        ns = {"s": "http://www.w3.org/2000/svg"}
        self.assertEqual(root.attrib["role"], "img")
        self.assertTrue(root.find("s:title", ns).text)
        self.assertIn("synthetic", root.find("s:desc", ns).text)
        self.assertFalse(root.findall(".//s:image", ns))
        self.assertFalse(root.findall(".//s:script", ns))
        for count in ("17/19", "1/19", "0/19"):
            self.assertIn(f">{count}</text>", svg)

    def test_changed_method_results_need_a_new_story(self):
        report = deepcopy(visual.checked_report())
        row = next(r for r in report["per_query"] if r["split"] == "heldout" and r["method"] == "bm25")
        row["reciprocal_rank_at_k"] = 0.5
        with self.assertRaisesRegex(ValueError, "no longer tie"):
            visual.figure(report)


if __name__ == "__main__":
    unittest.main()
