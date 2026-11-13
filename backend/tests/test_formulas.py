"""Unit tests for the formula registry (backend/formulas.py) and the Markdown clean-up in
backend/convert.py. Standard library only; the code-generation tests need sympy and
antlr4-python3-runtime 4.11 and are skipped without them.

    python -m unittest discover -s backend/tests -v
"""

import ast
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import convert  # noqa: E402
import formulas  # noqa: E402

FIX = HERE / "fixtures"


def sympy_ready() -> bool:
    return not isinstance(formulas._sympy_parser(), Exception)


def load_module(source: str):
    path = Path(tempfile.mkdtemp()) / "generated_formulas.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("generated_formulas", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MarkerMarkdown(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = formulas.build((FIX / "marker_raw.md").read_text(encoding="utf-8"))
        cls.fs = cls.reg["formulas"]["formulas"]
        cls.vars = {v["symbol"]: v for v in cls.reg["variables"]["variables"]}

    def display(self):
        return [f for f in self.fs if f["kind"] == "display"]

    def test_schema_versions(self):
        self.assertEqual(self.reg["formulas"]["schema"], 1)
        self.assertEqual(self.reg["variables"]["schema"], 1)

    def test_finds_display_and_inline_but_not_code_or_citations(self):
        d = self.display()
        self.assertEqual(len(d), 5)
        latex = [f["latex"] for f in self.fs]
        self.assertNotIn("not math", " ".join(latex))  # inside a code fence
        self.assertNotIn("8", latex)  # "[\[8\]](#page-15-0)" is a citation, not math

    def test_equation_numbers_are_split_off(self):
        nums = [f["number"] for f in self.display()]
        self.assertEqual(nums, ["1", "2", "3", None, "2.1"])
        self.assertTrue(self.display()[0]["latex"].startswith("A_T :="))
        self.assertNotIn("(3)", self.display()[2]["latex"])

    def test_pages_and_sections(self):
        first, third = self.display()[0], self.display()[2]
        self.assertEqual((first["page"], first["section"]), (1, "1. Introduction"))
        self.assertEqual((third["page"], third["section"]), (2, "2. Pricing"))

    def test_sentences(self):
        f1, f2 = self.display()[:2]
        self.assertIn("time average of the asset price", f1["sentence"])
        self.assertIn("$$", f1["sentence"])
        r = next(f for f in self.fs if f["latex"] == "r")
        self.assertTrue(r["sentence"].startswith("where $r$ denotes the risk-free rate"))
        self.assertNotIn("<span", f1["sentence"])

    def test_symbols(self):
        f1 = self.display()[0]
        self.assertEqual(f1["symbols"], ["A_T", "T", "S_t", "t"])  # dt is a differential
        call = self.display()[2]
        self.assertNotIn("e", call["symbols"])  # e^{-rT}
        self.assertIn("d_1", call["symbols"])
        cases = self.display()[4]
        self.assertEqual(cases["symbols"], ["J_{BS}", "k", r"\beta", r"\xi"])  # \text{} and \begin{cases} dropped
        expansion = next(f for f in self.fs if f["latex"].startswith("J(k)"))
        self.assertEqual(expansion["symbols"], ["J", "k"])  # no "O" from O(…), no "log"

    def test_definitions(self):
        self.assertEqual(self.vars["r"]["definition"], "the risk-free rate")
        self.assertEqual(self.vars["q"]["definition"], "the dividend yield")
        self.assertEqual(self.vars[r"\sigma"]["definition"], "the volatility")
        self.assertEqual(self.vars["S_t"]["definition"], "the price of the stock at time $t$")
        self.assertEqual(self.vars["K"]["definition"], "the strike")
        self.assertEqual(self.vars[r"\beta"]["definition"], "the solutions of two equations")
        self.assertEqual(self.vars[r"\xi"]["definition"], "the solutions of two equations")
        self.assertIsNone(self.vars["C"]["definition"])
        d = self.vars["r"]["definitions"][0]
        self.assertEqual((d["pattern"], d["page"], d["section"]), ("where", 1, "1. Introduction"))

    def test_variable_occurrences(self):
        s_t = self.vars["S_t"]
        self.assertEqual(s_t["first"]["formula"], "f1")
        self.assertEqual(s_t["ident"], "S_t")
        self.assertIn("f2", s_t["formulas"])

    def test_every_display_formula_is_accounted_for(self):
        s = self.reg["summary"]
        self.assertEqual(s["parsed"] + s["unparsed"], s["display"])
        for f in self.display():
            self.assertTrue(f["python"] or f["parse_error"], f)

    def test_summary_line(self):
        line = formulas.summary_line(self.reg["summary"])
        self.assertIn("5 display", line)


@unittest.skipUnless(sympy_ready(), "needs sympy + antlr4-python3-runtime 4.11")
class GeneratedPython(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = formulas.build((FIX / "marker_raw.md").read_text(encoding="utf-8"))
        cls.mod = load_module(cls.reg["python"])
        cls.cap = formulas.build((FIX / "mathpix_style.md").read_text(encoding="utf-8"))
        cls.capm = load_module(cls.cap["python"])

    def test_module_compiles_and_has_metadata(self):
        ast.parse(self.reg["python"])
        self.assertEqual(self.mod.SCHEMA, 1)
        self.assertEqual(set(self.mod.FORMULAS), {"eq_1_A_T", "eq_3_C", "f10_d_1"})

    def test_black_scholes(self):
        import math

        N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))  # noqa: E731
        d1 = self.mod.f10_d_1(K=100, S_0=100, T=1, r=0.05, sigma=0.2)
        self.assertAlmostEqual(d1, 0.35, places=12)
        d2 = d1 - 0.2
        c = self.mod.eq_3_C(K=100, N=N, S_0=100, T=1, d_1=d1, d_2=d2, r=0.05)
        self.assertAlmostEqual(c, 10.450583572185565, places=9)

    def test_integral_formula(self):
        self.assertAlmostEqual(float(self.mod.eq_1_A_T(S_t=2.0, T=3.0)), 2.0)

    def test_unparsed_keeps_reason(self):
        reasons = {u["number"]: u["reason"] for u in self.mod.UNPARSED}
        self.assertIn("cases environment", reasons["2.1"])
        self.assertIn("sympy could not parse", reasons["2"])

    def test_docstring_has_latex_location_and_definitions(self):
        doc = self.mod.eq_3_C.__doc__
        self.assertIn(r"C = S_0 N(d_1)", doc)
        self.assertIn("page 2", doc)
        self.assertIn("equation (3)", doc)
        self.assertIn("r: the risk-free rate", doc)
        self.assertIn("K: the strike", doc)

    def test_product_and_multi_letter_names(self):
        self.assertAlmostEqual(self.capm.eq_4_E_i(E_m=0.08, beta_i=1.5, r_f=0.02), 0.11)
        self.assertAlmostEqual(self.capm.f9_SR(mu_p=0.1, r_f=0.02, sigma_p=0.2), 0.4)
        self.assertEqual(self.capm.UNPARSED, [])

    def test_sum_needs_builtins_import(self):
        md = "$$PV = \\sum_{k=1}^{n} \\frac{c}{(1+y)^k} + \\frac{F}{(1+y)^n}. \\tag{6}$$\n"
        mod = load_module(formulas.build(md)["python"])
        self.assertAlmostEqual(mod.eq_6_PV(F=100, c=5, n=10, y=0.05), 100.0)

    def test_ambiguous_notation_is_refused(self):
        f = formulas.Formula("f1", "display", "", r"\Sigma_0^2(k) = \sigma^2 \frac{\log^2 k}{2J(k)}", 0, 0)
        self.assertIn("ambiguous", formulas._codegen(f, formulas._sympy_parser()))
        f = formulas.Formula("f2", "display", "", r"A_t^{(\mu)} = \int_0^t e^{2B_s} ds", 0, 0)
        self.assertIn("ambiguous", formulas._codegen(f, formulas._sympy_parser()))
        f = formulas.Formula("f3", "display", "", r"C = e^{-rT} \mathbb{E}[(S_T - K)^+]", 0, 0)
        self.assertIn("expectation", formulas._codegen(f, formulas._sympy_parser()))

    def test_chains_and_conditions(self):
        f = formulas.Formula("f1", "display", "", r"x := a + b = c, \quad a > 0", 0, 0)
        g = formulas._codegen(f, formulas._sympy_parser())
        self.assertEqual((g.name, g.args, g.body), ("x", ["a", "b"], "return a + b"))
        self.assertIn("first equality", g.note)


class OtherConverters(unittest.TestCase):
    """Markdown with \\( \\), \\[ \\], equation environments and <!-- page N --> markers."""

    @classmethod
    def setUpClass(cls):
        cls.reg = formulas.build((FIX / "mathpix_style.md").read_text(encoding="utf-8"))
        cls.fs = cls.reg["formulas"]["formulas"]
        cls.vars = {v["symbol"]: v for v in cls.reg["variables"]["variables"]}

    def test_delimiters(self):
        d = [f for f in self.fs if f["kind"] == "display"]
        self.assertEqual([f["latex"] for f in d], [r"E_i = r_f + \beta_i (E_m - r_f)",
                                                   r"SR = \frac{\mu_p - r_f}{\sigma_p}"])
        self.assertEqual(d[0]["number"], "4")
        self.assertEqual([f["page"] for f in d], [3, 4])
        self.assertNotIn("5", [f["latex"] for f in self.fs])  # "\$5" is a price

    def test_definitions_with_denotes(self):
        self.assertEqual(self.vars["r_f"]["definition"], "the risk-free rate")
        self.assertEqual(self.vars[r"\beta_i"]["definition"], "the sensitivity of asset $i$ to the market")
        self.assertEqual(self.vars["E_m"]["definition"], "the expected market return")
        self.assertIn("SR", self.vars)


class PlainTextSymbols(unittest.TestCase):
    def test_unicode_greek_definitions(self):
        md = ("# Model\n\n$$dS = \\mu S dt + \\sigma S dW$$\n\n"
              "where σ is the volatility and μ denotes the drift.\n")
        reg = formulas.build(md)
        defs = {v["symbol"]: v["definition"] for v in reg["variables"]["variables"]}
        self.assertEqual(defs[r"\sigma"], "the volatility")
        self.assertEqual(defs[r"\mu"], "the drift")
        self.assertNotIn("dS", defs)


class Helpers(unittest.TestCase):
    def test_split_number(self):
        self.assertEqual(formulas.split_number(r"(3) \quad x = 1"), ("x = 1", ["3"]))
        self.assertEqual(formulas.split_number(r"x = 1 \qquad (2.1)"), ("x = 1", ["2.1"]))
        self.assertEqual(formulas.split_number(r"x = 1 \tag{A.4}"), ("x = 1", ["A.4"]))
        self.assertEqual(formulas.split_number(r"f(2) = 1"), ("f(2) = 1", []))
        rows = r"\begin{aligned} (61) \quad b &= 0 \\ (65) \quad c &= 1 \end{aligned}"
        self.assertEqual(formulas.split_number(rows),
                         (r"\begin{aligned} b &= 0 \\ c &= 1 \end{aligned}", ["61", "65"]))

    def test_ident(self):
        self.assertEqual(formulas.ident(r"\sigma"), "sigma")
        self.assertEqual(formulas.ident("S_{t}"), "S_t")
        self.assertEqual(formulas.ident(r"\hat{\beta}_i"), "hat_beta_i")
        self.assertEqual(formulas.ident(r"\lambda"), "lambda_")

    def test_symbols_canonical(self):
        self.assertEqual(formulas.symbols(r"S_{t} + \beta_{i} r_f"), ["S_t", r"\beta_i", "r_f"])
        self.assertEqual(formulas.symbols(r"\Sigma_{\text{LN}}"), [r"\Sigma_{LN}"])
        self.assertEqual(formulas.symbols(r"B_{\lambda t}"), [r"B_{\lambda t}"])
        self.assertEqual(formulas.symbols(r"\hat{\sigma}^2 + \mathbb{E}[X]"), [r"\hat{\sigma}", "X"])
        self.assertEqual(formulas.symbols(r"\int_0^T f(t) \, dt"), ["T", "f", "t"])

    def test_page_ranges(self):
        self.assertEqual(convert.parse_pages("1-3,5", 10), [0, 1, 2, 4])
        self.assertIsNone(convert.parse_pages(None, 10))
        with self.assertRaises(ValueError):
            convert.parse_pages("4-12", 10)
        with self.assertRaises(ValueError):
            convert.parse_pages("x", 10)

    def test_tidy_markdown(self):
        raw = ("\n\n{0}------------------------------------------------\n\nText\n"
               "$$(1) \\quad x = 1$$\nmore text ![](_page_0_Figure_2.jpeg)\n\n"
               "{1}------------------------------------------------\n\nEnd\n")
        md = convert.tidy_markdown(raw, {"_page_0_Figure_2.jpeg": "images/page_1_figure_2.jpg"})
        self.assertEqual(md, "<!-- page 1 -->\n\nText\n\n$$x = 1 \\tag{1}$$\n\nmore text "
                             "![](images/page_1_figure_2.jpg)\n\n<!-- page 2 -->\n\nEnd\n")
        q = convert.quality(md)
        self.assertEqual((q["pages"], q["display"], q["numbered"], q["images"]), (2, 1, 1, 1))

    def test_write(self):
        reg = formulas.build((FIX / "mathpix_style.md").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as d:
            files = formulas.write(reg, d)
            self.assertEqual(files, ["formulas.json", "variables.json", "formulas.py"])
            data = json.loads((Path(d) / "formulas.json").read_text(encoding="utf-8"))
            self.assertEqual(data["schema"], 1)
            keys = {"id", "kind", "latex", "number", "numbers", "page", "section", "sentence", "symbols", "offset", "raw"}
            self.assertTrue(keys <= set(data["formulas"][0]))


if __name__ == "__main__":
    unittest.main()
