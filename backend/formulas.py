"""Formula registry for a Markdown paper. Deterministic, no AI.

From Markdown with `$inline$` / `$$display$$` math (marker output, or any converter that
writes `$`, `$$`, `\\(…\\)`, `\\[…\\]` or `\\begin{equation}`), this builds:

    formulas.json   every formula: LaTeX, kind, page, section, equation number, sentence
    variables.json  every symbol: where it first appears, which formulas use it, and its
                    definition when the text says "where X denotes …", "let X be …", …
    formulas.py     one Python function per display formula that sympy can parse;
                    the rest are listed in UNPARSED with the reason

Only the standard library is needed for the JSON files. formulas.py needs sympy and
antlr4-python3-runtime 4.11 (sympy's LaTeX parser); without them every display formula
goes to UNPARSED.

Pages come from `<!-- page N -->` comments (1-based) or marker's `{N}------` separators
(0-based); without either, `page` is null.
"""

from __future__ import annotations

import json
import keyword
import re
from dataclasses import dataclass, field

SCHEMA = 1

# ---------------------------------------------------------------------------
# Markdown scanning

PAGE_RE = re.compile(r"^<!-- page (\d+) -->[ \t]*$|^\{(\d+)\}-{10,}[ \t]*$", re.M)
HEADING_RE = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$", re.M)
FENCE_RE = re.compile(r"^(```|~~~).*?^\1[ \t]*$", re.M | re.S)
MATH_RE = re.compile(
    r"""
      (?<!\\)\$\$(?P<d1>.+?)(?<!\\)\$\$
    | \\\[(?P<d2>.+?)\\\]
    | \\begin\{(?P<env>equation|align|gather|multline|eqnarray|displaymath)(?P<star>\*?)\}
          (?P<d3>.+?)\\end\{(?P=env)(?P=star)\}
    | \\\((?P<i2>.+?)\\\)
    | (?<![\\$])\$(?!\$)(?P<i1>(?:[^$\n\\]|\\.|\n(?![ \t]*\n))+?)(?<!\\)\$(?!\$)
    """,
    re.S | re.X,
)

# equation numbers: \tag{3}, "(3) \quad x = …" (marker) or "x = … \qquad (3)"
NUM = r"[0-9A-Z]{1,3}(?:\.[0-9]{1,3}){0,2}[a-z]?"
TAG_RE = re.compile(r"\\tag\*?\{\s*\(?(" + NUM + r")\)?\s*\}")
LEAD_NUM_RE = re.compile(r"^\s*\((" + NUM + r")\)\s*(?:\\q?quad|\\hspace\{[^}]*\}|~)\s*")
TRAIL_NUM_RE = re.compile(r"\s*(?:\\q?quad|\\hfill|\\hspace\{[^}]*\})\s*\((" + NUM + r")\)\s*[.,;]?\s*$")
LABEL_RE = re.compile(r"\\label\{[^}]*\}|\\nonumber|\\notag")


ROW_NUM_RE = re.compile(r"(\\begin\{[A-Za-z*]+\}\s*(?=\(" + NUM + r"\)\s*\S)|\\\\(?=\s*\(" + NUM
                        + r"\)\s*(?:\\q?quad|~)))\s*\((" + NUM + r")\)\s*(?:\\q?quad|~)?\s*")


def split_number(latex: str) -> tuple[str, list[str]]:
    """Remove equation numbers from display LaTeX: returns (latex, numbers).

    One number for an ordinary equation (`\\tag{3}`, `(3) \\quad …`, `… \\qquad (3)`), one per
    row for environments whose rows start with `(N) \\quad` (marker writes aligned blocks so)."""
    numbers: list[str] = []
    for rx in (TAG_RE, LEAD_NUM_RE, TRAIL_NUM_RE):
        m = rx.search(latex)
        if m:
            numbers = [m.group(1)]
            latex = latex[: m.start()] + " " + latex[m.end():]
            break
    if not numbers and "\\begin{" in latex:
        numbers = [m.group(2) for m in ROW_NUM_RE.finditer(latex)]
        latex = ROW_NUM_RE.sub(lambda m: m.group(1) + " ", latex)
    latex = LABEL_RE.sub("", latex)
    return " ".join(latex.split()), numbers


def clean_heading(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = s.replace("**", "").replace("\\", "")
    return " ".join(s.split()).strip("*_ ")


@dataclass
class Formula:
    id: str
    kind: str  # "display" | "inline"
    raw: str  # as written in the Markdown, delimiters included
    latex: str  # without delimiters and equation number
    start: int
    end: int
    number: str | None = None
    numbers: list[str] = field(default_factory=list)  # several for multi-row environments
    page: int | None = None
    section: str | None = None
    sentence: str = ""
    symbols: list[str] = field(default_factory=list)
    python: str | None = None
    parse_error: str | None = None

    def as_json(self) -> dict:
        d = {
            "id": self.id, "kind": self.kind, "latex": self.latex, "number": self.number, "numbers": self.numbers,
            "page": self.page, "section": self.section, "sentence": self.sentence,
            "symbols": self.symbols, "offset": [self.start, self.end], "raw": self.raw,
        }
        if self.kind == "display":
            d["python"] = self.python
            d["parse_error"] = self.parse_error
        return d


def _mask(md: str) -> str:
    """Blank out code fences and HTML comments (same length, so offsets stay valid)."""
    blank = lambda m: re.sub(r"[^\n]", " ", m.group(0))  # noqa: E731
    md = FENCE_RE.sub(blank, md)
    return re.sub(r"<!--.*?-->", blank, md, flags=re.S)


def _locator(md: str):
    pages = [(m.start(), int(m.group(1)) if m.group(1) else int(m.group(2)) + 1)
             for m in PAGE_RE.finditer(md)]
    heads = [(m.start(), clean_heading(m.group(1))) for m in HEADING_RE.finditer(_mask_fences(md))]

    def at(pos: int) -> tuple[int | None, str | None]:
        page = next((p for s, p in reversed(pages) if s <= pos), None)
        if page is None and pages:
            page = pages[0][1]
        sec = next((h for s, h in reversed(heads) if s <= pos), None)
        return page, sec

    return at


def _mask_fences(md: str) -> str:
    return FENCE_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), md)


def find_formulas(md: str) -> list[Formula]:
    masked = _mask(md)
    at = _locator(md)
    out = []
    for m in MATH_RE.finditer(masked):
        g = m.groupdict()
        body = g["d1"] or g["d2"] or g["d3"] or g["i1"] or g["i2"] or ""
        if not body.strip():
            continue
        if g["d2"] and "\n" not in body and not re.search(r"\\[A-Za-z]|[=^_]", body):
            continue  # an escaped bracket in text (marker writes "\[8\]"), not display math
        kind = "inline" if (g["i1"] or g["i2"]) else "display"
        latex, numbers = split_number(body) if kind == "display" else (" ".join(body.split()), [])
        page, sec = at(m.start())
        out.append(Formula(id=f"f{len(out) + 1}", kind=kind, raw=md[m.start():m.end()],
                           latex=latex, start=m.start(), end=m.end(),
                           number=numbers[0] if numbers else None, numbers=numbers,
                           page=page, section=sec))
    return out


# ---------------------------------------------------------------------------
# Sentences

PH = "\x00{}\x00"
PH_RE = re.compile(r"\x00(\d+)\x00")
SENT_SPLIT_RE = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[A-Z\x00(\[])")
ABBREV_RE = re.compile(r"\b(?:e\.g|i\.e|cf|resp|eq|eqs|Eq|Eqs|Fig|Figs|Sec|Secs|Ref|Refs|Thm|Prop|Lem|Def|vs|al|etc|approx|Ch|No|pp|Vol)\.$")


def _prose(s: str) -> str:
    s = re.sub(r"<(?:span|a)\b[^>]*>\s*</(?:span|a)>", "", s)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<sup>(.*?)</sup>", r"^\1", s)
    s = re.sub(r"<sub>(.*?)</sub>", r"_\1", s)
    s = re.sub(r"<[^>\x00]+>", "", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\(#[^)]*\)", r"\1", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\\([\[\]*_$#()&%{}])", r"\1", s)
    s = re.sub(r"(\*\*|__|(?<![\w*])\*(?!\s)|(?<!\S)_(?=\S))", "", s)
    s = re.sub(r"^\s{0,3}(?:[-+]|\d+\.)\s+", "", s)  # list markers
    return " ".join(s.split())


def _sentences(text: str) -> list[str]:
    parts = SENT_SPLIT_RE.split(text)
    merged: list[str] = []
    for p in parts:
        if merged and (ABBREV_RE.search(merged[-1]) or re.search(r"\b[A-Z]\.$", merged[-1])):
            merged[-1] += " " + p
        else:
            merged.append(p)
    return [s.strip() for s in merged if s.strip()]


@dataclass
class Sentence:
    text: str  # with \x00k\x00 placeholders for formula index k
    start: int
    formulas: list[int]


def _units(md: str, formulas: list[Formula]):
    """Document order list of ("sentence", Sentence) and ("display", formula index)."""
    masked = _mask(md)
    by_start = {f.start: i for i, f in enumerate(formulas)}
    units: list[tuple[str, object]] = []
    for blk in re.finditer(r"(?:[^\n]|\n(?![ \t]*\n))+", masked):
        a, b = blk.start(), blk.end()
        block = md[a:b]
        stripped = block.strip()
        if not stripped or HEADING_RE.fullmatch(stripped) or PAGE_RE.fullmatch(stripped):
            continue
        if stripped.startswith("|") or stripped.lower().startswith("<table"):
            continue
        # text runs between display formulas -> sentences; inline formulas -> placeholders
        run, pos = [], a
        for f_i in sorted(i for st, i in by_start.items() if a <= st < b):
            f = formulas[f_i]
            run.append(md[pos:f.start])
            pos = f.end
            if f.kind == "display":
                _flush(run, a, units)
                run = []
                units.append(("display", f_i))
            else:
                run.append(" " + PH.format(f_i) + " ")
        run.append(md[pos:b])
        _flush(run, a, units)
    return units


def _flush(run: list[str], start: int, units: list) -> None:
    text = _prose("".join(run))
    for sent in _sentences(text):
        units.append(("sentence", Sentence(sent, start, [int(k) for k in PH_RE.findall(sent)])))


def _render(text: str, formulas: list[Formula]) -> str:
    def rep(m):
        f = formulas[int(m.group(1))]
        return f"$${f.latex}$$" if f.kind == "display" else f"${f.latex}$"
    return " ".join(PH_RE.sub(rep, text).split())


CONTINUATION_RE = re.compile(r"^(?:[a-z,;.:]|\x00|(?:where|with|for|and|which|in|so|then|or)\b)")


def attach_sentences(units, formulas: list[Formula]) -> None:
    for i, (kind, u) in enumerate(units):
        if kind == "sentence":
            for f_i in u.formulas:
                formulas[f_i].sentence = _render(u.text, formulas)
        else:
            f = formulas[u]
            before = units[i - 1][1].text if i and units[i - 1][0] == "sentence" else ""
            after = ""
            if i + 1 < len(units) and units[i + 1][0] == "sentence":
                nxt = units[i + 1][1].text
                if CONTINUATION_RE.match(nxt):
                    after = nxt
            f.sentence = _render(" ".join(x for x in (before, PH.format(u), after) if x), formulas)


# ---------------------------------------------------------------------------
# Symbols

GREEK = set("""alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa
lambda mu nu xi omicron pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi
omega Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega ell""".split())
DECOR = set("""hat bar tilde vec dot ddot check breve widehat widetilde overline underline
mathbf mathbb mathcal mathscr mathfrak boldsymbol bm mathit mathsf""".split())
OPAQUE = set("""text textrm textit textbf textsf texttt textnormal mathrm operatorname mbox
label tag hspace vspace mathop begin end""".split())
FUNCNAMES = set("""exp log ln lg sin cos tan cot sec csc sinh cosh tanh arcsin arccos arctan
max min sup inf lim liminf limsup det arg deg dim ker sgn sign diag tr erf erfc Var Cov Corr
Pr var cov corr mod gcd lcm""".split())
NOT_VARIABLES = {r"\mathbb{E}", r"\mathbb{P}", r"\mathbb{Q}", r"\mathbb{R}", r"\mathbb{N}",
                 r"\mathbb{Z}", r"\mathbb{C}", r"\mathbb{V}", r"\mathbb{1}"}
GREEK_UNICODE = dict(zip(
    "αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΥΦΨΩϵϑϖϱςϕ",
    """alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi pi rho sigma
    tau upsilon phi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega
    varepsilon vartheta varpi varrho varsigma varphi""".split()))

TOKEN_RE = re.compile(r"\\[A-Za-z]+|\\.|[A-Za-z]+|\d+(?:\.\d+)?|\s+|.", re.S)


def _group(tokens: list[str], i: int) -> tuple[str, int]:
    """Read one argument starting at tokens[i]: a {…} group or a single token."""
    while i < len(tokens) and tokens[i].isspace():
        i += 1
    if i >= len(tokens):
        return "", i
    if tokens[i] != "{":
        t = tokens[i]
        if t.isalpha() and len(t) > 1:  # x_ab means x_a b
            tokens[i:i + 1] = [t[0], t[1:]]
            t = t[0]
        return t, i + 1
    depth, j = 0, i
    while j < len(tokens):
        depth += tokens[j] == "{"
        depth -= tokens[j] == "}"
        if depth == 0:
            return "".join(tokens[i + 1:j]), j + 1
        j += 1
    return "".join(tokens[i + 1:]), len(tokens)


def _canon_sub(content: str) -> str:
    c = re.sub(r"\\(?:text|mathrm|textrm|rm|mathit|textit)\s*\{([^{}]*)\}", r"\1", content)
    c = re.sub(r"(\\[A-Za-z]+)\s+(?=[A-Za-z])", "\\1\x01", " ".join(c.split()))
    c = c.replace(" ", "").replace("\x01", " ")
    if len(c) == 1 or re.fullmatch(r"\\[A-Za-z]+", c):
        return "_" + c if len(c) == 1 else "_{" + c + "}"
    return "_{" + c + "}"


LHS_NAME_RE = re.compile(r"^\s*((?!d[A-Za-z]\s*=)[A-Za-z]{2,4})\s*(?==[^=])")  # not dS = …


def symbols(latex: str) -> list[str]:
    """Variables in a LaTeX formula, canonical form (`\\sigma`, `r_f`, `S_t`, `J_{BS}`), in order.
    A short letter run on the left of "=" is one name (`SR = …`, `PV = …`); elsewhere letters
    next to each other are separate symbols, as in LaTeX."""
    found: list[str] = []
    lhs = LHS_NAME_RE.match(latex)
    if lhs and lhs.group(1) not in FUNCNAMES:
        found.append(lhs.group(1))
        latex = latex[lhs.end():]
    tokens = TOKEN_RE.findall(latex)
    i = 0

    def add(base: str, j: int) -> int:
        k = j
        while k < len(tokens) and tokens[k].isspace():
            k += 1
        sym = base
        if k < len(tokens) and tokens[k] == "_":
            content, k = _group(tokens, k + 1)
            sym += _canon_sub(content)
            j = k
        if sym not in NOT_VARIABLES and sym not in found:
            found.append(sym)
        return j

    while i < len(tokens):
        t = tokens[i]
        if t.startswith("\\") and len(t) > 1 and t[1:].isalpha():
            name = t[1:]
            if name in GREEK:
                i = add(t, i + 1)
            elif name in DECOR:
                arg, j = _group(tokens, i + 1)
                inner = symbols(arg)
                base = f"\\{name}{{{''.join(arg.split())}}}"
                if len(inner) == 1 or name in ("mathbb", "mathcal", "mathscr", "mathfrak"):
                    i = add(base, j)
                else:
                    i += 1  # e.g. \overline{x+y}: scan the inside normally
            elif name in OPAQUE:
                _, i = _group(tokens, i + 1)
            else:
                i += 1
        elif t.isalpha():
            nxt = next((x for x in tokens[i + 1:] if not x.isspace()), "")
            if t in FUNCNAMES or (t == "O" and nxt in ("(", "\\left")):  # log, big-O
                i += 1
                continue
            letters = list(t)
            if len(letters) >= 2 and letters[0] == "d":  # dt, dW_t: differentials
                letters = letters[1:]
            elif len(letters) == 1 and t == "d" and nxt.startswith("\\") and nxt[1:] in GREEK:
                letters = []
            for ch in letters[:-1]:
                if ch not in found:
                    found.append(ch)
            last = letters[-1] if letters else ""
            if last == "e" and nxt == "^":  # e^{…}: Euler's number
                i += 1
                continue
            i = add(last, i + 1) if last else i + 1
        else:
            i += 1
    return found


def ident(symbol: str) -> str:
    """Python identifier for a symbol: `\\sigma`→sigma, `S_{t}`→S_t, `\\hat{\\beta}_i`→hat_beta_i."""
    s = symbol.replace("\\", "").replace("{", "_").replace("}", "").replace("*", "")
    s = re.sub(r"[^0-9A-Za-z_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_") or "x"
    if s[0].isdigit():
        s = "x_" + s
    return s + "_" if keyword.iskeyword(s) else s


def _sym_from_math(latex: str) -> str | None:
    """The single symbol an inline formula consists of (`$\\sigma$`, `$C(K, T)$`), or None."""
    latex = latex.strip()
    m = re.fullmatch(r"(.+?)\s*(?:\\left)?\((?:[^()]|\([^()]*\))*(?:\\right)?\)", latex)
    if m and len(symbols(m.group(1))) == 1:  # function notation: C(K, T) -> C
        latex = m.group(1)
    syms = symbols(latex)
    if len(syms) != 1:
        return None
    rest = latex
    for junk in ("\\left", "\\right", "\\,", "\\;", " ", "{", "}", "\\boldsymbol", "\\mathbf",
                 "\\bm", "\\mathcal", "\\mathbb", "\\hat", "\\bar", "\\tilde", "\\vec", "\\dot"):
        rest = rest.replace(junk, "")
    return syms[0] if not re.search(r"[=<>+\-*/^()\[\],|]", rest) else None


# ---------------------------------------------------------------------------
# Definitions ("where X denotes …")

M = r"(?:\x00\d+\x00|[A-Za-zΑ-Ωα-ωϵϑϖϱςϕ](?:_\w)?)"  # a formula placeholder or a bare letter
MLIST = rf"{M}(?:\s*(?:,|and|,\s*and)\s*{M})*"
VERB = r"(?:is|are|denotes|denote|represents|represent|stands for|stand for|is given by|refers to|is defined as|are defined as)"
MSYM = r"(?:\x00\d+\x00|[Α-Ωα-ωϵϑϖϱςϕ])"  # placeholder or bare Greek letter (no Latin: "a", "I")
DEF_END = (r"(?=\s*(?:[;.](?:\s|$)|,\s*and\s+(?:the|a|an)\b|,\s*(?:and\s+)?(?:" + MSYM
           + r"\s+(?:is|are|denotes|the)\b|where\b|while\b|so\b)|\s+and\s+" + MSYM
           + r"\s+(?:is|are|denotes|represents)\b|$))")
DEF_PATTERNS = [  # (kind, regex), strongest first; "definition" uses the strongest match
    ("where", re.compile(rf"\b(?:where|here|and|with|in which)\s+(?P<m>{MLIST})\s+{VERB}\s+(?P<d>.+?){DEF_END}")),
    ("let", re.compile(rf"\b[Ll]et\s+(?P<m>{MLIST})\s+(?:be|denote)\s+(?P<d>.+?){DEF_END}")),
    ("denotes", re.compile(rf"(?:^|[,;]\s*|\s)(?P<m>{MSYM})\s+(?:denotes|represents|stands for)\s+(?P<d>.+?){DEF_END}")),
    ("with", re.compile(rf"\bwith\s+(?P<m>{MLIST})\s+(?P<d>(?:the|a|an)\s+.+?){DEF_END}")),
    ("is", re.compile(rf"(?:^|[,;]\s*)(?P<m>\x00\d+\x00)\s+(?:is|are)\s+(?P<d>(?:the|a|an)\s+.+?){DEF_END}")),
    ("denoted", re.compile(rf"\b(?P<d>(?:the|a|an)\s+[a-z][\w\- ]{{2,60}}?)\s+(?:denoted by|denoted|written)\s+(?P<m>\x00\d+\x00)")),
    ("apposition", re.compile(
        r"\b(?P<d>(?:the|a|an)\s+(?:(?!(?:of|for|with|in|on|at|by|to|and|or|from|is|are)\b)[a-z][\w\-]*\s+){0,4}?"
        r"[a-z][\w\-]*)\s+(?P<m>\x00\d+\x00)(?=\s*(?:[,.;:)]|$|\s(?:is|are|and|of|in|at|to|with|for|as|which|that|"
        r"can|will|has|have|follows|satisfies|denotes)\b))")),
]
KIND_RANK = {k: i for i, (k, _) in enumerate(DEF_PATTERNS)}
APPOSITION_STOP = set("""of in on to by for with that and or is are from at as be we have has
given using equation formula expression term value function""".split())


def _mentioned(mlist: str, formulas: list[Formula]) -> list[str]:
    out = []
    for tok in re.findall(r"\x00(\d+)\x00|([A-Za-zΑ-Ωα-ωϵϑϖϱςϕ](?:_\w)?)", mlist):
        if tok[0]:
            f = formulas[int(tok[0])]
            sym = _sym_from_math(f.latex) if f.kind == "inline" else None
        else:
            ch, sub = tok[1][0], tok[1][2:]
            if ch in ("a", "A", "I") and not sub:  # articles / pronoun, not symbols
                continue
            sym = ("\\" + GREEK_UNICODE[ch]) if ch in GREEK_UNICODE else ch
            sym += ("_" + sub) if sub else ""
        if sym:
            out.append(sym)
    return out


def find_definitions(units, formulas: list[Formula], at) -> dict[str, list[dict]]:
    defs: dict[str, list[dict]] = {}
    for kind, u in units:
        if kind != "sentence":
            continue
        for kind_, rx in DEF_PATTERNS:
            for m in rx.finditer(u.text):
                text = re.sub(r"(?:\s+(?:and|or|with|while|as))+$", "", _render(m.group("d"), formulas)).strip(" ,:")
                if not text or len(text) > 220:
                    continue
                if kind_ == "apposition":
                    words = text.split()
                    if words[-1] in APPOSITION_STOP - {"function"}:
                        continue
                    ing = [i for i, w in enumerate(words[:-1]) if w.endswith("ing")]
                    if ing:  # "a bond paying coupon $c$" -> "coupon"
                        text = " ".join(words[ing[-1] + 1:])
                page, sec = at(u.start)
                for sym in _mentioned(m.group("m"), formulas):
                    entry = {"text": text, "pattern": kind_, "sentence": _render(u.text, formulas),
                             "page": page, "section": sec}
                    lst = defs.setdefault(sym, [])
                    if all(e["text"] != text for e in lst):
                        lst.append(entry)
    return defs


# ---------------------------------------------------------------------------
# Python code generation (sympy)

def _sympy_parser():
    try:
        from sympy.parsing.latex import parse_latex
        parse_latex("x")
        return parse_latex
    except Exception as e:  # sympy or antlr4-python3-runtime missing / wrong version
        return e


DECOR_RE = re.compile(
    r"\\(?:hat|bar|tilde|vec|dot|ddot|check|breve|widehat|widetilde|overline|mathbf|boldsymbol"
    r"|bm|mathcal|mathscr|mathfrak|mathbb)\s*(?:\{[^{}]*\}|\\[A-Za-z]+|[A-Za-z])"
    r"(?:\s*_\s*(?:\{[^{}]*\}|\\[A-Za-z]+|[A-Za-z0-9]))?")
UNSUPPORTED_RE = re.compile(r"\\math(?:bb|bf|rm|cal)\{[EP]\}|\\Pr\b|\\operatorname\{(?:E|P|Pr|Var|Cov)\}|\\(?:in|sim|propto|to|mapsto|cdots|ldots|dots)\b")


def _drop_big_o(s: str) -> tuple[str, bool]:
    """Remove "+ O(…)" remainder terms."""
    out, dropped = s, False
    while True:
        m = re.search(r"[+-]\s*O\s*(?:\\left)?\(", out)
        if not m:
            return out, dropped
        depth, j = 0, m.end() - 1
        while j < len(out):
            depth += out[j] == "("
            depth -= out[j] == ")"
            if depth == 0:
                break
            j += 1
        out, dropped = out[: m.start()] + out[j + 1:], True


def _top_level(s: str, chars: str) -> list[int]:
    depth, out = 0, []
    for i, ch in enumerate(s):
        if ch in "{([":
            depth += 1
        elif ch in "})]":
            depth -= 1
        elif ch in chars and depth == 0:
            out.append(i)
    return out


def _variants(latex: str) -> tuple[list[tuple[str, list[str]]], dict[str, str]]:
    """LaTeX variants sympy might accept (most faithful first), each with notes for the
    docstring, plus a map of placeholder names for decorated symbols (\\hat{x} etc.)."""
    s = latex
    s = re.sub(r"\\(?:,|;|!|:|quad|qquad|displaystyle|textstyle|limits|nolimits)", " ", s)
    s = re.sub(r"\\(?:mathrm|operatorname)\{d\}", "d", s)
    s = re.sub(r"\\(?:mathrm|text|mathit|textrm)\{([A-Za-z]+)\}", r"\1", s)
    s = re.sub(r"\\(?:big|Big|bigg|Bigg)[lr]?", "", s)
    s = re.sub(r"=:|:=|\\coloneqq|\\eqqcolon|\\equiv|\\triangleq", "=", s)
    s = s.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    placeholders: dict[str, str] = {}

    def deco(m):
        name = f"zzdec{len(placeholders)}"
        sym = symbols(m.group(0))
        placeholders[name] = ident(sym[0] if sym else m.group(0))
        return f"\\mathit{{{name}}}"

    s = DECOR_RE.sub(deco, s)
    lhs = LHS_NAME_RE.match(s)
    if lhs and lhs.group(1) not in FUNCNAMES:
        s = f"\\mathit{{{lhs.group(1)}}}" + s[lhs.end():]
    s, dropped_o = _drop_big_o(s)
    s = re.sub(r"[\s.,;]+$", "", s).strip()
    notes0 = ["O(…) remainder terms were dropped."] if dropped_o else []

    cands = [(s, [])]
    commas = _top_level(s, ",")
    if commas:  # "f = …, K > S_0" or "a = …, \quad b = …": keep the part before the comma
        cands.append((s[: commas[-1]].strip(), ["Text after the last top-level comma was ignored."]))
        if len(commas) > 1:
            cands.append((s[: commas[0]].strip(), ["Text after the first top-level comma was ignored."]))
    out = []
    for c, notes in cands:
        eqs = [i for i in _top_level(c, "=") if c[i - 1:i] not in ("<", ">", "!", "\\")]
        if len(eqs) > 1:  # a = b = c: use the first equality
            c = c[: eqs[1]].strip()
            notes = notes + ["Chained equation: only the first equality is used."]
        out.append((c, notes0 + notes))
    return out, placeholders


POWER_CALL_RE = re.compile(r"(\\[A-Za-z]+|[A-Za-z])(_\{[^{}]*\}|_\\?[A-Za-z0-9]+)?\^(?:\{[^{}]*\}|[0-9A-Za-z])\s*(?:\\left)?\(")


def _ambiguous(latex: str) -> str | None:
    """Notation sympy would silently misread: refuse instead of generating wrong code."""
    if re.search(r"\^\s*\{\s*(?:\\left)?\(", latex):
        return "superscript in parentheses (like ^{(\\mu)}) is ambiguous: label or power"
    if re.search(r"_\{[^{}]*\\(?:frac|sqrt|int|sum)", latex):
        return "subscript contains an expression"
    eq = latex.find("=")
    for m in POWER_CALL_RE.finditer(latex):
        base = m.group(1) + (m.group(2) or "")
        if m.group(1) == "e":
            continue
        if (0 <= eq and m.start() < eq) or re.search(re.escape(base) + r"\s*(?:\\left)?\(", latex):
            return f"{m.group(0).rstrip('(').strip()}(…) is ambiguous: power of a function or product"
    return None


@dataclass
class Generated:
    name: str
    args: list[str]
    body: str
    imports: set[str]
    note: str = ""


def _codegen(formula: Formula, parse_latex) -> Generated | str:
    """sympy -> Python function source parts, or a string with the reason it failed."""
    import sympy
    from sympy.core.function import AppliedUndef
    from sympy.printing.pycode import MpmathPrinter, PythonCodePrinter

    if "\\begin{" in formula.latex:
        env = re.search(r"\\begin\{(\w+\*?)\}", formula.latex).group(1)
        return f"contains a {env} environment (not supported by the LaTeX parser)"
    bad = UNSUPPORTED_RE.search(formula.latex)
    if bad:
        return f"contains {bad.group(0)} (expectation, probability, set or series notation)"
    why = _ambiguous(formula.latex)
    if why:
        return why
    variants, placeholders = _variants(formula.latex)
    expr, err, notes = None, "", []
    for variant, vnotes in variants:
        try:
            cand = parse_latex(variant, strict=True)
        except Exception as e:  # noqa: BLE001 - the parser raises various errors
            err = err or (str(e).strip().splitlines() or [type(e).__name__])[0]
            continue
        # unknown commands (\approx, \hat …) come back as symbols named after the command
        cmds = set(re.findall(r"\\([A-Za-z]+)", variant)) - GREEK - {"mathit"}
        names = {str(x).split("_")[0] for x in cand.free_symbols} | {
            type(a).__name__ for a in cand.atoms(AppliedUndef)}
        if cmds & names:
            err = err or f"\\{sorted(cmds & names)[0]} is not supported"
            continue
        if isinstance(cand, sympy.logic.boolalg.BooleanAtom):
            err = err or "parses to a constant truth value"
            continue
        # \beta_i (E_m - r_f): a subscripted or Greek symbol before a sum is a product
        products = {a: sympy.Symbol(type(a).__name__) * a.args[0] for a in cand.atoms(AppliedUndef)
                    if len(a.args) == 1 and isinstance(a.args[0], sympy.Add)
                    and ("_" in type(a).__name__ or type(a).__name__.split("_")[0] in GREEK)}
        if products:
            cand = cand.xreplace(products)
            vnotes = vnotes + [f"{', '.join(sorted(ident(type(a).__name__) for a in products))}(…) read as a product."]
        expr, notes = cand, vnotes
        break
    if expr is None:
        return f"sympy could not parse it: {err}"[:300]

    lhs_name = None
    if isinstance(expr, sympy.Equality):
        lhs, rhs = expr.lhs, expr.rhs
        if isinstance(lhs, sympy.Symbol):
            lhs_name, body = ident(placeholders.get(lhs.name, lhs.name)), rhs
            note = f"Returns the right-hand side ({lhs_name} = …)."
        elif isinstance(lhs, AppliedUndef):
            lhs_name, body = ident(type(lhs).__name__), rhs
            note = f"Returns the right-hand side ({lhs_name}(…) = …)."
        else:
            body, note = lhs - rhs, "Returns lhs - rhs (zero when the equation holds)."
    elif isinstance(expr, sympy.core.relational.Relational):
        body, note = expr, "Returns whether the relation holds."
    else:
        body, note = expr, "Returns the expression's value."
    note = " ".join([note] + notes)

    # rename symbols / undefined functions to identifiers; e -> Euler's number
    repl = {}
    for s in body.free_symbols:
        repl[s] = sympy.E if s.name == "e" else sympy.Symbol(ident(placeholders.get(s.name, s.name)))
    body = body.xreplace(repl)
    funcs = {}
    for a in body.atoms(AppliedUndef):
        funcs[type(a)] = sympy.Function(ident(type(a).__name__))
    for old, new in funcs.items():
        body = body.replace(old, new)
    args = sorted({s.name for s in body.free_symbols} | {f.__name__ for f in funcs.values()})
    if lhs_name and lhs_name in args:
        lhs_name = lhs_name + "_"

    class _Undef:
        def _print_AppliedUndef(self, e):  # undefined functions are passed in as callables
            return f"{type(e).__name__}({', '.join(self._print(a) for a in e.args)})"

    for base in (PythonCodePrinter, MpmathPrinter):
        printer = type("P", (_Undef, base), {})({"strict": True, "fully_qualified_modules": True})
        try:
            code = printer.doprint(body)
        except Exception:  # noqa: BLE001 - not printable with this module
            continue
        imports = {mod for mod in printer.module_imports}
        return Generated(lhs_name or "", args, f"return {code}", imports, note)
    # e.g. limits, derivatives: evaluate with sympy at call time
    code = f"return _with_sympy({sympy.srepr(body)!r}, {{{', '.join(f'{a!r}: {a}' for a in args)}}})"
    return Generated(lhs_name or "", args, code, {"sympy"},
                     note + " Evaluated with sympy (no plain-Python form).")


def _docstring(f: Formula, args: list[str], variables: dict[str, dict], note: str) -> str:
    where = ", ".join(x for x in (f"page {f.page}" if f.page else "",
                                  f"section {f.section!r}" if f.section else "",
                                  f"equation ({f.number})" if f.number else "") if x)
    lines = [f"{f.latex}", "", f"Formula {f.id}" + (f", {where}" if where else "") + ". " + note]
    by_ident = {v["ident"]: v for v in variables.values()}
    defs = [(a, by_ident[a]["definition"]) for a in args if a in by_ident and by_ident[a]["definition"]]
    if defs:
        lines += ["", "Variables:"] + [f"    {a}: {d}" for a, d in defs]
    doc = "\n".join(lines).replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return '    """' + doc.replace("\n", "\n    ").replace("    \n", "\n") + '\n    """'


def generate_python(formulas: list[Formula], variables: dict[str, dict], source: str) -> tuple[str, dict]:
    parse_latex = _sympy_parser()
    displays = [f for f in formulas if f.kind == "display"]
    funcs, unparsed, imports, names = [], [], set(), set()
    for f in displays:
        if isinstance(parse_latex, Exception):
            f.parse_error = f"sympy LaTeX parser not available: {parse_latex}"[:300]
        else:
            res = _codegen(f, parse_latex)
            if isinstance(res, str):
                f.parse_error = res
            else:
                base = (f"eq_{re.sub(r'[^0-9A-Za-z]', '_', f.number)}" if f.number else f.id) + (f"_{res.name}" if res.name else "")
                name, k = base, 2
                while name in names:
                    name, k = f"{base}_{k}", k + 1
                names.add(name)
                f.python = name
                imports |= res.imports
                funcs.append(f"def {name}({', '.join(res.args)}):\n"
                             f"{_docstring(f, res.args, variables, res.note)}\n    {res.body}\n")
        if f.parse_error:
            unparsed.append({"id": f.id, "latex": f.latex, "number": f.number, "page": f.page,
                             "reason": f.parse_error})

    head = [f'"""Formulas from {source}, generated by formula-snip (schema {SCHEMA}).',
            "",
            "One function per display formula that sympy could parse. Arguments are the",
            "formula's symbols; undefined functions (like N in N(d_1)) are passed in as callables.",
            "Formulas that could not be turned into code are listed in UNPARSED with the reason.",
            "Generated deterministically from the paper's LaTeX: check against the paper before use.",
            '"""', ""]
    used = set(re.findall(r"\b(math|mpmath|builtins)\.", "\n".join(funcs)))
    head += [f"import {m}" for m in sorted(used)]
    head += ["", f"SCHEMA = {SCHEMA}", ""]
    tail = []
    if "sympy" in imports:
        tail += ["", "def _with_sympy(srepr, values):",
                 "    import sympy",
                 "    expr = eval(srepr, vars(sympy))",
                 "    for k, v in values.items():",
                 "        if callable(v):  # undefined function -> the callable passed in",
                 "            expr = expr.replace(sympy.Function(k), lambda *a, v=v: v(*a))",
                 "    expr = expr.subs({sympy.Symbol(k): v for k, v in values.items() if not callable(v)})",
                 "    return expr.doit()", ""]
    body = "\n\n".join(funcs)
    meta = ["", "FORMULAS = {"] + [f"    {f.python!r}: {{'id': {f.id!r}, 'number': {f.number!r}, "
                                    f"'page': {f.page!r}, 'latex': {f.latex!r}}},"
                                    for f in displays if f.python] + ["}", ""]
    meta += ["UNPARSED = ["] + [f"    {u!r}," for u in unparsed] + ["]", ""]
    src = "\n".join(head) + "\n" + "\n".join(tail) + ("\n" + body if body else "") + "\n".join(meta)
    return src, {"display": len(displays), "parsed": len(funcs), "unparsed": len(unparsed)}


# ---------------------------------------------------------------------------
# Registry

def build(md: str, source: str = "paper.md") -> dict:
    """Return {"formulas": {...}, "variables": {...}, "python": str, "summary": {...}}."""
    formulas = find_formulas(md)
    units = _units(md, formulas)
    attach_sentences(units, formulas)
    at = _locator(md)
    for f in formulas:
        f.symbols = symbols(f.latex)

    defs = find_definitions(units, formulas, at)
    variables: dict[str, dict] = {}
    for f in formulas:
        for s in f.symbols:
            v = variables.setdefault(s, {"symbol": s, "ident": ident(s),
                                         "first": {"formula": f.id, "page": f.page, "section": f.section},
                                         "formulas": [], "definition": None, "definitions": []})
            if f.id not in v["formulas"]:
                v["formulas"].append(f.id)
    for s, lst in defs.items():
        if s in variables:
            variables[s]["definitions"] = lst
            variables[s]["definition"] = min(lst, key=lambda e: KIND_RANK[e["pattern"]])["text"]

    python, py_counts = generate_python(formulas, variables, source)
    n_disp = sum(f.kind == "display" for f in formulas)
    summary = {
        "formulas": len(formulas), "display": n_disp, "inline": len(formulas) - n_disp,
        "numbered": sum(f.number is not None for f in formulas),
        "parsed": py_counts["parsed"], "unparsed": py_counts["unparsed"],
        "variables": len(variables),
        "variables_defined": sum(v["definition"] is not None for v in variables.values()),
    }
    summary["variables_undefined"] = summary["variables"] - summary["variables_defined"]
    return {
        "formulas": {"schema": SCHEMA, "source": source, "formulas": [f.as_json() for f in formulas]},
        "variables": {"schema": SCHEMA, "source": source,
                      "variables": sorted(variables.values(), key=lambda v: (int(v["first"]["formula"][1:]), v["symbol"]))},
        "python": python,
        "summary": summary,
    }


def write(registry: dict, out_dir) -> list[str]:
    from pathlib import Path

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "formulas.json").write_text(json.dumps(registry["formulas"], indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "variables.json").write_text(json.dumps(registry["variables"], indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "formulas.py").write_text(registry["python"], encoding="utf-8")
    return ["formulas.json", "variables.json", "formulas.py"]


def summary_line(s: dict) -> str:
    return (f"formulas: {s['formulas']} ({s['display']} display, {s['inline']} inline, {s['numbered']} numbered)\n"
            f"python:   {s['parsed']} parsed, {s['unparsed']} unparsed (see UNPARSED in formulas.py)\n"
            f"symbols:  {s['variables']} ({s['variables_defined']} with definition, "
            f"{s['variables_undefined']} without)")
