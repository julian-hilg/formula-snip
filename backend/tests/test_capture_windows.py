"""Selection geometry tests; no Windows desktop, tkinter or Pillow required."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capture_windows import selection_box


class SelectionBoxTests(unittest.TestCase):
    def test_drag_in_each_direction_selects_the_same_pixels(self):
        for start, end in [((10, 20), (80, 90)), ((80, 90), (10, 20)),
                           ((80, 20), (10, 90)), ((10, 90), (80, 20))]:
            with self.subTest(start=start, end=end):
                self.assertEqual(selection_box(start, end, (100, 100)), (10, 20, 80, 90))

    def test_drag_beyond_screen_edges_is_clamped(self):
        self.assertEqual(selection_box((-10, 15), (150, 120), (100, 80)), (0, 15, 100, 80))

    def test_clicks_and_narrow_selections_are_ignored(self):
        for end in [(10, 20), (12, 80), (80, 22)]:
            with self.subTest(end=end):
                self.assertIsNone(selection_box((10, 20), end, (100, 100)))

    def test_completely_outside_selection_is_ignored(self):
        self.assertIsNone(selection_box((110, 120), (140, 150), (100, 100)))


if __name__ == "__main__":
    unittest.main()
