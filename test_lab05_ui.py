"""Offline checks for the Lab 5 launcher. It never starts Streamlit or a model."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest


def load_ui():
    """Import helpers using a tiny Streamlit stub so no UI server is created."""
    stub = types.ModuleType("streamlit")
    previous = sys.modules.get("streamlit")
    sys.modules["streamlit"] = stub
    try:
        path = Path(__file__).with_name("lab05_ui.py")
        spec = importlib.util.spec_from_file_location("lab05_ui_under_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            sys.modules.pop("streamlit", None)
        else:
            sys.modules["streamlit"] = previous


ui = load_ui()


class Lab05UiTests(unittest.TestCase):
    def test_request_parses_ticker_peers_and_optional_price(self):
        self.assertEqual(ui.parse_request(" abc ", " xyz, DEF, xyz ", "12.50"),
                         ("ABC", ["XYZ", "DEF"], 12.5))
        self.assertEqual(ui.parse_request("ABC", "", ""), ("ABC", [], None))

    def test_request_rejects_invalid_price(self):
        for value in ("0", "-1", "not-a-number"):
            with self.assertRaises(ValueError):
                ui.parse_request("ABC", "", value)

    def test_marks_load_from_latest_verification_round(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "verification_round_1.json").write_text('{"marks":[{"mark":"Right"}]}')
            (folder / "verification_round_2.json").write_text('{"marks":[{"mark":"Wrong"}]}')
            self.assertEqual(ui.load_marks(folder), [{"mark": "Wrong"}])

    def test_fixed_ui_order_matches_required_graph_order(self):
        self.assertEqual(ui.NODE_ORDER, [
            "steps", "Research Analyst", "Financial Analyst", "Investment Advisor",
            "Strategy Manager", "Verifier",
        ])


if __name__ == "__main__":
    unittest.main()
