"""End-to-end test of `convert.py convert` on examples/papers/sample.pdf (2 pages).

Skipped when marker is not installed. Run it with marker's Python, e.g.
    ~/.local/pipx/venvs/marker-pdf/bin/python -m unittest discover -s backend/tests -v
The first run downloads the model weights.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend" / "convert.py"
SAMPLE = ROOT / "examples" / "papers" / "sample.pdf"


def run(*args, cache: str):
    env = {**os.environ, "FORMULA_SNIP_CACHE": cache, "TQDM_DISABLE": "1"}
    p = subprocess.run([sys.executable, "-u", str(SCRIPT), *args], capture_output=True, text=True,
                       env=env, timeout=1800)
    events = [json.loads(line) for line in p.stdout.splitlines() if line.strip()]
    return p.returncode, events, p.stderr


class Errors(unittest.TestCase):
    def test_missing_file_is_a_json_error(self):
        with tempfile.TemporaryDirectory() as d:
            code, events, _ = run("convert", str(Path(d) / "nope.pdf"), "--out", d, "--json", cache=d)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["event"], "error")
        self.assertIn("no such file", events[-1]["error"])

    def test_refuses_foreign_files(self):
        if importlib.util.find_spec("pypdfium2") is None:
            self.skipTest("needs pypdfium2 (installed with marker)")
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "images").mkdir()
            (Path(d) / "images" / "holiday.jpg").write_bytes(b"x")
            code, events, _ = run("convert", str(SAMPLE), "--out", d, "--json", cache=d)
            self.assertEqual(code, 1)
            self.assertIn("not written by formula-snip", events[-1]["error"])
            self.assertTrue((Path(d) / "images" / "holiday.jpg").exists())

    def test_page_limit(self):
        if importlib.util.find_spec("pypdfium2") is None:
            self.skipTest("needs pypdfium2 (installed with marker)")
        with tempfile.TemporaryDirectory() as d:
            code, events, _ = run("convert", str(SAMPLE), "--out", d, "--max-pages", "1", "--json", cache=d)
            self.assertEqual(code, 1)
            self.assertIn("limit is 1", events[-1]["error"])
            code, events, _ = run("convert", str(SAMPLE), "--out", d, "--max-pages", "1", "--pages", "9",
                                  "--json", cache=d)
            self.assertIn("beyond the last page", events[-1]["error"])

    def test_cancel_via_stdin(self):
        if importlib.util.find_spec("pypdfium2") is None:
            self.skipTest("needs pypdfium2 (installed with marker)")
        with tempfile.TemporaryDirectory() as d:
            env = {**os.environ, "FORMULA_SNIP_CACHE": d}
            p = subprocess.Popen([sys.executable, "-u", str(SCRIPT), "convert", str(SAMPLE), "--out", d,
                                  "--json", "--stdin-control"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, text=True, env=env)
            first = json.loads(p.stdout.readline())
            self.assertEqual(first["event"], "start")
            p.stdin.write("cancel\n")
            p.stdin.flush()
            rest = [json.loads(line) for line in p.stdout]
            self.assertEqual(p.wait(timeout=120), 1)
            self.assertEqual(rest[-1]["event"], "cancelled")

    def test_bad_page_range(self):
        if importlib.util.find_spec("pypdfium2") is None:
            self.skipTest("needs pypdfium2 (installed with marker)")
        with tempfile.TemporaryDirectory() as d:
            code, events, _ = run("convert", str(SAMPLE), "--out", d, "--pages", "2-9", "--json", cache=d)
        self.assertEqual(code, 1)
        self.assertIn("beyond the last page", events[-1]["error"])


@unittest.skipIf(importlib.util.find_spec("marker") is None, "marker-pdf is not installed")
class ConvertSample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "out"
        cls.cache = str(Path(cls.tmp.name) / "cache")
        cls.code, cls.events, cls.stderr = run("convert", str(SAMPLE), "--out", str(cls.out), "--json",
                                               "--batch-pages", "1", cache=cls.cache)
        cls.md = (cls.out / "paper.md").read_text(encoding="utf-8") if cls.code == 0 else ""

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_exit_code_and_events(self):
        self.assertEqual(self.code, 0, self.stderr[-2000:])
        kinds = [e["event"] for e in self.events]
        self.assertEqual(kinds[0], "start")
        self.assertEqual(kinds[-1], "done")
        self.assertIn("progress", kinds)

    def test_batches(self):
        conv = [e for e in self.events if e.get("stage") == "converting"]
        self.assertEqual([(e["batch"], e["batches"], e["pages"]) for e in conv], [(1, 2, [1, 1]), (2, 2, [2, 2])])
        self.assertIn("<!-- page 1 -->", self.md)
        self.assertIn("<!-- page 2 -->", self.md)

    def test_outputs(self):
        for name in ("paper.md", "meta.json", "formulas.json", "variables.json", "formulas.py"):
            self.assertTrue((self.out / name).is_file(), name)
        meta = json.loads((self.out / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["schema"], 1)
        self.assertEqual(meta["source"]["page_count"], 2)
        self.assertEqual(len(meta["source"]["sha256"]), 64)
        self.assertEqual(meta["converter"]["name"], "marker")
        self.assertFalse(meta["cached"])

    def test_display_equations_keep_numbering(self):
        for n in range(1, 7):
            self.assertIn(f"\\tag{{{n}}}$$", self.md)
        fs = json.loads((self.out / "formulas.json").read_text(encoding="utf-8"))["formulas"]
        self.assertEqual([f["number"] for f in fs if f["kind"] == "display"], [str(n) for n in range(1, 7)])

    def test_inline_math_is_not_split(self):
        meta = json.loads((self.out / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["quality"]["inline_split"], 0)
        self.assertGreaterEqual(meta["quality"]["inline"], 15)
        self.assertIn("$S_t$", self.md)
        self.assertIn("$\\beta_i$", self.md)

    def test_table_survives(self):
        self.assertRegex(self.md, r"\|\s*Stock A\s*\|\s*0\.80\s*\|\s*0\.42\s*\|")
        self.assertRegex(self.md, r"\|\s*Stock C\s*\|\s*1\.50\s*\|\s*0\.28\s*\|")

    def test_second_run_is_cached(self):
        out2 = Path(self.tmp.name) / "out2"
        t = time.time()
        code, events, err = run("convert", str(SAMPLE), "--out", str(out2), "--json", "--batch-pages", "1",
                                cache=self.cache)
        self.assertEqual(code, 0, err[-2000:])
        self.assertTrue(events[-1]["cached"])
        self.assertLess(time.time() - t, 20)
        self.assertEqual((out2 / "paper.md").read_text(encoding="utf-8"), self.md)


if __name__ == "__main__":
    unittest.main()
