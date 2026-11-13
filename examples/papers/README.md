# Example papers

Test PDFs for `formula-snip convert`. Each one's unedited output is in [`out/`](out).

| File | Source | Licence |
|---|---|---|
| `sample.pdf` (from [`sample.tex`](sample.tex)) | Written for this repository: 2 pages, 6 numbered equations, inline math, a table | MIT, like the rest of the repo |
| `pirjol-2024-asian-options.pdf` | Dan Pirjol, *Subleading correction to the Asian options volatility in the Black-Scholes model*, [arXiv:2407.05142v3](https://arxiv.org/abs/2407.05142) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `schadner-2026-implied-volatility.pdf` | Wolfgang Schadner, *An Explicit Solution to Black–Scholes Implied Volatility*, [arXiv:2604.24480v4](https://arxiv.org/abs/2604.24480) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |

The two arXiv papers are redistributed unchanged under their CC BY 4.0 licences. The files
in `out/` are conversions of those papers (adaptations under the same licence, with
attribution as above).

Regenerate the output with:

```bash
for p in sample pirjol-2024-asian-options schadner-2026-implied-volatility; do
  formula-snip convert examples/papers/$p.pdf --out examples/papers/out/$p
done
```

## Quality checks

Output of `formula-snip convert` (default `ocr` mode, marker 2.1.0, Apple-silicon laptop):

| Paper | Pages | Tables | Display formulas | Equation numbers kept | Inline formulas | Inline split | In `formulas.py` | Symbols with definition | Conversion |
|---|---|---|---|---|---|---|---|---|---|
| sample | 2 | 1 of 1 | 6 | 6 of 6 | 24 | 0 | 5 (1 unparsed) | 6 of 29 | 10 s + 4 s model load |
| pirjol-2024-asian-options | 17 | 2 of 2 | 90 | 90 of 90 | 269 | 0 | 33 (57 unparsed) | 17 of 111 | 130 s |
| schadner-2026-implied-volatility | 22 | 1 of 1 | 41 | 37 of 41 (see below) | 244 | 0 | 9 (32 unparsed) | 9 of 73 | 100 s |

**What was checked:**

- *Tables survive.* Every table arrives as a Markdown table with the right rows and columns, and math in cells (`$\beta_i$`, `$\frac{2}{1.9}$`) stays math.
- *Display equations keep their numbering.* Equation numbers move into `\tag{N}` and `formulas.json`. In the Schadner paper, equations (16)–(19) are laid out as a two-column list ("variance-vega … (16)"). marker reads them as inline math with the number as text, so they are not display formulas there.
- *Inline math is not split.* `inline_split` in `meta.json` counts inline math cut into adjacent pieces (`$S$ $_t$`). It is 0 for all three papers.

**Known conversion flaw.** On page 2 of the sample, marker puts the heading "3 Discounting" after the first paragraph (a reading-order slip). Formulas on that page therefore get section "2 Risk and return" up to the heading.

**About the unparsed formulas.** Most of them are unparsed on purpose. They use notation that the generator refuses rather than guesses: expectations `\mathbb{E}[…]`, `cases` and `aligned` blocks, `\Sigma^2(K,T)`-style function powers, and superscript labels like `A^{(\mu)}`. `UNPARSED` in each `formulas.py` gives the reason for every one.
