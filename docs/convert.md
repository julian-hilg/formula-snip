# Paper conversion and formula registry

`formula-snip convert` turns a PDF into Markdown and builds a registry of its formulas.
Everything runs locally: the conversion uses [marker](https://github.com/datalab-to/marker)'s
document pipeline, and the registry is built by deterministic rules and sympy's LaTeX parser.
No LLM is involved at any step, and nothing leaves your computer.

This page is the interface contract for programs that call the command (for example
Sourcebound). The command, its options, the output layout and the JSON schemas below are
stable. Any breaking change bumps `schema`.

## Commands

```bash
formula-snip convert PAPER.pdf --out DIR [--pages 1-12] [--mode ocr|fast|balanced] [--force]
                     [--batch-pages 10] [--max-pages N] [--json] [--stdin-control]
formula-snip formulas PAPER.md [--out DIR] [--json]
```

| Option | Meaning |
|---|---|
| `--out DIR` | Output folder. It is created if missing. It must be new, empty or an earlier output folder. Only the files listed below are replaced, and files from other sources are never overwritten. |
| `--pages RANGE` | 1-based and inclusive: `1-12`, `3`, `1,4,7-9`. The default is all pages. |
| `--mode` | `ocr` (default): marker's fast layout detector, then every block is OCR'd on its own. This gives the best math. `fast`: uses the PDF's text layer and OCRs only equations, so it's quicker, but inline math stays plain text. `balanced`: marker's balanced mode (VLM layout and full-page OCR). It gets inline math, but sometimes cuts display equations into pieces. |
| `--force` | Ignore the cache and convert again. |
| `--batch-pages N` | marker converts N pages at a time (default 10). Progress is reported per batch, and finished batches are kept, so a cancelled or failed run continues where it stopped. The result is the same as converting in one go. |
| `--max-pages N` | Refuse PDFs (or page ranges) with more than N pages. The default is no limit. The panel passes `--max-pages 100`. |
| `--json` | Machine-readable progress on stdout (see *Events*). |
| `--stdin-control` | For programs that run the converter: a line `cancel` on stdin, or stdin closing, stops it cleanly. SIGTERM always does. |

`formulas` builds only the registry (`formulas.json`, `variables.json`, `formulas.py`) from
an existing Markdown file. It works with any converter whose output uses `$…$`, `$$…$$`,
`\(…\)`, `\[…\]` or `\begin{equation}…\end{equation}`. The default output folder is the one
the Markdown file is in.

The commands are thin wrappers: the Rust binary writes its embedded copy of
`backend/convert.py` and `backend/formulas.py` to the app's data folder and runs them with
marker's Python (the `python` setting, or the pipx install). Running
`python backend/convert.py convert …` from a checkout does the same.

**Exit codes:**
- `0` success
- `1` failure (an `error` event explains it)
- `2` invalid arguments

## Output layout

```
DIR/
  paper.md          the paper as Markdown
  images/           figures, page_<N>_<type>_<k>.jpg, linked from paper.md
  meta.json         provenance, timings, counts
  formulas.json     every formula
  variables.json    every symbol
  formulas.py       one Python function per parseable display formula
```

`paper.md` conventions:

- `<!-- page N -->` (1-based) starts each page.
- Display math sits on its own lines as `$$…$$`, and equation numbers become `\tag{N}`. For example, `$$C = S_0 N(d_1) - K e^{-rT} N(d_2), \tag{1}$$`.
- Inline math is written as `$…$`.
- Tables are Markdown tables, and cells may contain inline math.
- Headings are ATX (`#`, `##`, …).
- A `$` in the text is escaped as `\$`.

## Cache

Conversions are cached by the PDF's sha256, the page range, the mode and the marker version.
The cache lives under:

| OS | Folder |
|---|---|
| macOS | `~/Library/Caches/formula-snip/papers/` |
| Linux | `$XDG_CACHE_HOME/formula-snip/papers/` |
| Windows | `%LOCALAPPDATA%\formula-snip\papers\` |

You can override the folder with `FORMULA_SNIP_CACHE`. A cached call only copies files and
rebuilds the registry, which takes about a second. The registry is never cached, so
improvements to the rules apply to old conversions too.

## Events (`--json`)

stdout carries one JSON object per line and nothing else. Logs from marker go to stderr.

```json
{"event": "start", "source": "/abs/paper.pdf", "sha256": "…", "page_count": 17, "pages": null, "mode": "ocr", "out": "/abs/DIR"}
{"event": "progress", "stage": "loading_models"}
{"event": "progress", "stage": "converting", "batch": 2, "batches": 2, "pages": [11, 17], "done_pages": 10, "total_pages": 17}
{"event": "progress", "stage": "cached", "cache": "…"}
{"event": "progress", "stage": "formulas"}
{"event": "done", "out": "/abs/DIR", "cached": false, "meta": { …meta.json… }}
{"event": "error", "error": "no such file: /abs/paper.pdf"}
{"event": "cancelled", "error": "cancelled"}
```

In a `converting` event, `pages` is the batch's first and last page (1-based), and `done_pages`
counts the pages finished before this batch. A batch kept from an earlier, interrupted run is
reported with `stage: "resumed"` instead. A cancelled run ends with `cancelled` and exit code 1.

- `pages` lists the 1-based pages, or is `null` for all of them.
- A cached run reports `stage: "cached"` instead of `loading_models` and `converting`.
- `loading_models` comes before the first batch that still needs converting.
- `formulas` emits `start` and `done`, where `done` carries `files` and `summary`.
- Callers should ignore unknown events and unknown keys.

## `meta.json` (schema 1)

```json
{
 "schema": 1,
 "formula_snip": "0.1.0",
 "created": "2026-11-10T05:30:14+00:00",
 "source": {"path": "paper.pdf", "name": "paper.pdf", "sha256": "…", "page_count": 17},
 "pages": [1, 2, 3],
 "converter": {"name": "marker", "version": "2.1.0", "surya": "0.23.0", "mode": "ocr",
               "settings": {"mode": "fast", "force_ocr": true, "ocr_full_page": false}},
 "sympy": "1.14.0",
 "cached": false,
 "timings": {"models_s": 3.7, "convert_s": 139.4, "batches": 2, "batch_pages": 10,
             "formulas_s": 2.3, "total_s": 145.4},
 "quality": {"pages": 17, "tables": 2, "images": 1, "display": 90, "numbered": 87,
             "inline": 269, "inline_split": 0},
 "summary": { …same as the summary below… },
 "files": ["paper.md", "images/", "formulas.json", "variables.json", "formulas.py", "meta.json"]
}
```

- `source.path` is the path as given on the command line.
- On a cached run, `timings` repeats the original conversion times.
- `quality.inline_split` counts inline math that the conversion cut into adjacent pieces (`$S$ $_t$`), and should be 0.

## `formulas.json` (schema 1)

```json
{
 "schema": 1,
 "source": "paper.md",
 "formulas": [
  {
   "id": "f3",
   "kind": "display",
   "latex": "A_T := \\frac{1}{T} \\int_0^T S_t dt.",
   "number": "1",
   "numbers": ["1"],
   "page": 1,
   "section": "1. Introduction",
   "sentence": "Asian options are derivatives with payoff linked to the time average of the asset price $$A_T := …$$",
   "symbols": ["A_T", "T", "S_t", "t"],
   "offset": [1234, 1290],
   "raw": "$$A_T := \\frac{1}{T} \\int_0^T S_t dt. \\tag{1}$$",
   "python": "eq_1_A_T",
   "parse_error": null
  }
 ]
}
```

| Field | |
|---|---|
| `id` | `f1`, `f2`, … in document order, stable for the same Markdown |
| `kind` | `display` or `inline` |
| `latex` | the formula without delimiters, equation number, `\label` or `\tag` |
| `number` | equation number without parentheses (`"3"`, `"2.1"`, `"A.4"`), or `null` |
| `numbers` | all numbers of the formula: one entry normally, one per row for aligned blocks whose rows are numbered (`["61", "65"]`), `[]` if none. `number` is the first. |
| `page` | 1-based page, or `null` if the Markdown has no page markers |
| `section` | nearest heading above, cleaned of markup, or `null` |
| `sentence` | the sentence around it. For display formulas: the sentence that introduces it, the formula, and a continuation such as "where …". Other formulas appear as `$…$` / `$$…$$`. |
| `symbols` | variables in canonical form, in order of appearance (see below) |
| `offset` | `[start, end]` character offsets of `raw` in the Markdown |
| `raw` | the formula as written, delimiters included |
| `python` | display only: the function name in `formulas.py`, or `null` |
| `parse_error` | display only: why there is no function, or `null` |

## `variables.json` (schema 1)

```json
{
 "schema": 1,
 "source": "paper.md",
 "variables": [
  {
   "symbol": "r_f",
   "ident": "r_f",
   "first": {"formula": "f2", "page": 3, "section": "The CAPM"},
   "formulas": ["f2", "f3", "f9"],
   "definition": "the risk-free rate",
   "definitions": [
    {"text": "the risk-free rate", "pattern": "where",
     "sentence": "where $r_f$ is the risk-free rate, …", "page": 3, "section": "The CAPM"}
   ]
  }
 ]
}
```

Canonical symbols:

- Greek letters as commands (`\sigma`).
- Subscripts attached: `r_f`, `\beta_i`, `S_t` (also for `S_{t}`), `J_{BS}` (also for `J_{\text{BS}}`), `x_{i,j}`.
- Decorations kept: `\hat{\beta}`, `\mathbf{x}`.
- Superscripts are not part of a symbol.

These are not counted as variables:

- Differentials (`dt`, `dW_t`)
- `e` before `^`
- Function names (`\log`, `\exp`, `max`, …)
- `O(…)`
- `\text{}` / `\operatorname{}` content
- `\mathbb{E}`, `\mathbb{P}`, `\mathbb{R}` and friends

A short letter run on the left of `=` is one name (`SR = …`, `PV = …`). Elsewhere, adjacent letters are separate symbols, as LaTeX treats them. `ident` is the Python name used in `formulas.py`.

Definitions are found with regular expressions on the sentences, strongest pattern first:

| `pattern` | Example |
|---|---|
| `where` | "where $r$ denotes / is / are / represents / stands for …" (also "and $q$ is …", "with $X$ is …") |
| `let` | "Let $S_t$ be the price …" |
| `denotes` | "…, $N$ denotes the normal CDF" |
| `with` | "with $K$ the strike" |
| `is` | "$\beta_i$ is the sensitivity …" at the start of a clause |
| `denoted` | "the strike price, denoted $K$" |
| `apposition` | "the forward price $A$ is given by" (weakest) |

`definition` is the text of the strongest match, and `definitions` lists all of them in
document order. Symbols in plain text, such as "where σ is", are also recognised (Unicode
Greek and single letters).

## `formulas.py`

This is a plain Python module. It needs `math`, plus `mpmath` or `sympy` only for the formulas that use them.

```python
SCHEMA = 1

def eq_3_C(K, N, S_0, T, d_1, d_2, r):
    """C = S_0 N(d_1) - K e^{-rT} N(d_2),

    Formula f9, page 2, section '2. Pricing', equation (3). Returns the right-hand side (C = …).

    Variables:
        K: the strike
        r: the risk-free rate
    """
    return -K*N(d_2)*math.exp(-T*r) + S_0*N(d_1)

FORMULAS = {"eq_3_C": {"id": "f9", "number": "3", "page": 2, "latex": "…"}, …}
UNPARSED = [{"id": "f11", "latex": "…", "number": "2.1", "page": 2,
             "reason": "contains a cases environment (not supported by the LaTeX parser)"}, …]
```

**Naming.** Functions are called `eq_<number>` for numbered equations and `<id>` otherwise. When the left-hand side is a symbol or function, `_<lhs>` is added.

**Arguments** are the formula's free symbols, sorted. Undefined functions such as `N` in `N(d_1)` are arguments too, and you pass a callable for them.

**What a function returns:**
- `x = expr` returns `expr`.
- Any other equation returns `lhs - rhs`.
- Inequalities return whether they hold.
- Plain expressions return their value.

**Printing.** Code is printed with `math` where possible, otherwise with `mpmath` (for example integrals with `mpmath.quad`). For limits and derivatives, it evaluates with sympy at call time.

Every display formula ends up in exactly one place: it gets a function or an `UNPARSED` entry
with the reason. To keep the generated code from being silently wrong, notation that sympy
would misread is refused:

- `X^2(k)` could be a power of a function or a product.
- A superscript in parentheses such as `^{(\mu)}` could be a label or a power.
- Subscripts can contain expressions.
- Expectation and probability operators: `\mathbb{E}`, `\mathbb{P}`.
- Set notation (`\in`, `\sim`) and series dots.
- Unknown commands.
- Environments (`cases`, `aligned`, matrices).

A few readings are made on purpose and stated in the docstring:

| Notation | Read as |
|---|---|
| `:=` | `=` |
| A chained `a = b = c` | its first equality |
| A trailing `, K > S_0` or `, \quad b = …` | dropped |
| `O(…)` remainder terms | dropped |
| A subscripted or Greek symbol before a sum, as in `\beta_i (E_m - r_f)` | a product |

## Summary on stdout

Without `--json`, the command prints the path of `paper.md` and:

```
formulas: 359 (90 display, 269 inline, 87 numbered)
python:   33 parsed, 57 unparsed (see UNPARSED in formulas.py)
symbols:  112 (18 with definition, 94 without)
```

The same numbers are in `meta.json` → `summary`:

- `formulas`, `display`, `inline`, `numbered`
- `parsed`, `unparsed`
- `variables`, `variables_defined`, `variables_undefined`

## Requirements

- `marker-pdf` (pipx), with `llama-server` from llama.cpp, the same as for snipping.
- For `formulas.py`: sympy (installed with marker) and `antlr4-python3-runtime` 4.11. The installers add it with `pipx inject marker-pdf "antlr4-python3-runtime==4.11.*"`.

Without that runtime, every display formula is listed in `UNPARSED`, with the reason "sympy LaTeX parser not available". The JSON files don't need it.

## Speed

On an Apple-silicon laptop (CPU/MPS), `ocr` mode takes about 4–8 s per page plus about 4 s
to load the models:

- the 2-page sample: about 25 s
- the 22-page and 17-page example papers: about 1½ and 2½ minutes
- a cached repeat: about 1–2 s

## Tests

```bash
~/.local/pipx/venvs/marker-pdf/bin/python -m unittest discover -s backend/tests -v
```

The conversion test runs `examples/papers/sample.pdf` end to end. It is skipped when marker
isn't installed, and the registry tests run with any Python 3.10+.
