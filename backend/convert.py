#!/usr/bin/env python3
"""Formula Snip paper conversion: PDF -> Markdown + formula registry. Offline, no AI.

    convert.py convert paper.pdf --out DIR [--pages 1-12] [--mode ocr|fast|balanced] [--force]
                       [--batch-pages 10] [--max-pages N] [--json] [--stdin-control]
    convert.py formulas paper.md --out DIR [--json]

`convert` runs marker's full-document pipeline (layout, tables, equations) and writes

    DIR/paper.md        Markdown, $inline$ / $$display$$ math, Markdown tables,
                        <!-- page N --> before each page, equation numbers as \\tag{N}
    DIR/images/         extracted figures (linked from paper.md)
    DIR/meta.json       source sha256, page count, marker version, timings, counts
    DIR/formulas.json   \\
    DIR/variables.json   } the formula registry (see formulas.py)
    DIR/formulas.py     /

Conversions are cached by the PDF's sha256 (and page range / mode), so a second call is
instant; --force reconverts. `formulas` builds only the registry, from any Markdown file
(e.g. one made by another converter).

With --json, stdout carries one JSON object per line and nothing else:
    {"event": "start", ...} {"event": "progress", "stage": ...} {"event": "done", ...}
    {"event": "error", "error": "..."}
Exit code 0 on success, 1 on failure, 2 on bad arguments. See docs/convert.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import sys
import threading
import _thread
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import formulas  # noqa: E402

SCHEMA = 1
VERSION = os.environ.get("FORMULA_SNIP_VERSION", "dev")
CACHE_LAYOUT = 2  # bump when the cached files change meaning
# marker settings per --mode (see docs/convert.md for the comparison)
MODES = {
    # layout from marker's fast detector, then every block OCR'd on its own: display
    # equations stay whole and numbered, inline math becomes $…$, tables keep their cells
    "ocr": {"mode": "fast", "force_ocr": True, "ocr_full_page": False},
    # PDF text layer, OCR only for equations and garbled text: quickest, but inline math
    # stays plain text (S<sup>t</sup>)
    "fast": {"mode": "fast"},
    # marker's balanced mode (VLM layout + full-page OCR): inline math, but display
    # equations are sometimes cut into pieces
    "balanced": {"mode": "balanced"},
}
OUTPUTS = ["paper.md", "images", "meta.json", "formulas.json", "variables.json", "formulas.py"]


class Reporter:
    """Progress as JSON lines on stdout (--json) or as text on stderr."""

    def __init__(self, as_json: bool):
        self.as_json = as_json
        if as_json:  # keep stdout for our JSON only: libraries print, so point fd 1 at stderr
            self.out = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
            os.dup2(2, 1)
            sys.stdout = sys.stderr
        else:
            self.out = sys.stdout

    def event(self, event: str, text: str = "", **data) -> None:
        if self.as_json:
            self.out.write(json.dumps({"event": event, **data}, ensure_ascii=False) + "\n")
            self.out.flush()
        elif text:
            print(text, file=sys.stderr, flush=True)

    def result(self, text: str) -> None:
        if not self.as_json:
            print(text, file=self.out, flush=True)


def cache_root() -> Path:
    if os.environ.get("FORMULA_SNIP_CACHE"):
        return Path(os.environ["FORMULA_SNIP_CACHE"])
    if sys.platform == "darwin":
        base = Path.home() / "Library/Caches"
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "formula-snip" / "papers"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_pages(spec: str | None, count: int) -> list[int] | None:
    """'1-3,7' (1-based, inclusive) -> [0, 1, 2, 6]."""
    if not spec:
        return None
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        m = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", part)
        if not m:
            raise ValueError(f"bad page range {part!r} (use e.g. 1-12 or 1,3,5-7)")
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        if a < 1 or b < a:
            raise ValueError(f"bad page range {part!r}")
        if b > count:
            raise ValueError(f"page {b} is beyond the last page ({count})")
        pages.update(range(a - 1, b))
    return sorted(pages)


def page_count(pdf: Path) -> int:
    import pypdfium2

    doc = pypdfium2.PdfDocument(str(pdf))
    try:
        return len(doc)
    finally:
        doc.close()


def versions() -> dict:
    from importlib.metadata import PackageNotFoundError, version

    out = {}
    for pkg in ("marker-pdf", "surya-ocr", "sympy"):
        try:
            out[pkg] = version(pkg)
        except PackageNotFoundError:
            out[pkg] = None
    return out


# ---------------------------------------------------------------------------
# Markdown clean-up (deterministic)

PAGE_SEP_RE = re.compile(r"^\{(\d+)\}-{10,}[ \t]*$", re.M)
DISPLAY_RE = re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$", re.S)


def tidy_markdown(md: str, image_names: dict[str, str]) -> str:
    """marker Markdown -> paper.md: page comments, numbered equations as \\tag{}, display math
    on its own lines, images under images/."""
    md = PAGE_SEP_RE.sub(lambda m: f"<!-- page {int(m.group(1)) + 1} -->", md)

    def display(m):
        latex, numbers = formulas.split_number(m.group(1))
        if len(numbers) == 1:
            latex = f"{latex} \\tag{{{numbers[0]}}}"
        elif numbers:  # one number per row: keep marker's "(N) \quad" rows as they are
            latex = " ".join(m.group(1).split())
        return f"\n\n$${latex}$$\n\n"

    md = DISPLAY_RE.sub(display, md)
    for old, new in image_names.items():
        md = md.replace(f"]({old})", f"]({new})")
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


def image_name(name: str) -> str:
    """marker's "_page_0_Figure_2.jpeg" -> "page_1_figure_2" (1-based pages, like paper.md)."""
    stem = Path(name).stem.strip("_").lower()
    return re.sub(r"^page_(\d+)", lambda m: f"page_{int(m.group(1)) + 1}", stem)


def quality(md: str) -> dict:
    """Simple counts for checking a conversion (see docs/convert.md)."""
    fs = formulas.find_formulas(md)
    inline = [f for f in fs if f.kind == "inline"]
    # inline math split into pieces: $S$ $_t$, $x$$^2$ …
    split = sum(1 for a, b in zip(inline, inline[1:])
                if re.fullmatch(r"\s*", md[a.end:b.start]) and re.match(r"\s*[_^]", b.latex))
    tables = len(re.findall(r"^\|(?:\s*:?-{3,}:?\s*\|)+\s*$", md, re.M)) + md.lower().count("<table")
    return {
        "pages": len(re.findall(r"^<!-- page \d+ -->$", md, re.M)),
        "tables": tables,
        "images": len(re.findall(r"!\[[^\]]*\]\(images/", md)),
        "display": sum(f.kind == "display" for f in fs),
        "numbered": sum(f.number is not None for f in fs),
        "inline": len(inline),
        "inline_split": split,
    }


# ---------------------------------------------------------------------------
# Conversion

def batches(pages: list[int], size: int) -> list[list[int]]:
    return [pages[i:i + size] for i in range(0, len(pages), max(1, size))]


def run_marker(pdf: Path, pages: list[int], mode: str, dest: Path, partial: Path, batch_size: int,
               rep: Reporter) -> dict:
    """Convert `pages` (0-based) in batches of `batch_size` pages. Each finished batch is kept in
    `partial`, so a cancelled or failed run resumes where it stopped."""
    os.environ.setdefault("TQDM_DISABLE", "1")
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    groups = batches(pages, batch_size)
    models, converter_cls, settings = None, None, None
    t_models = t_convert = 0.0
    done_pages, parts, metas = 0, [], []
    try:
        for i, group in enumerate(groups, 1):
            CANCEL.check()
            bdir = partial / f"{group[0] + 1:05d}-{group[-1] + 1:05d}"
            span = [group[0] + 1, group[-1] + 1]
            if not (bdir / "done").is_file():
                if models is None:
                    t0 = time.time()
                    rep.event("progress", "Loading marker models …", stage="loading_models")
                    from marker.converters.pdf import PdfConverter as converter_cls
                    from marker.models import create_model_dict
                    from marker.settings import settings
                    models = create_model_dict()
                    t_models = time.time() - t0
                rep.event("progress", f"Pages {span[0]}-{span[1]} (batch {i}/{len(groups)}) …",
                          stage="converting", batch=i, batches=len(groups), pages=span,
                          done_pages=done_pages, total_pages=len(pages))
                t1 = time.time()
                config = {"paginate_output": True, "disable_tqdm": True, "use_llm": False,
                          "page_range": group, **MODES[mode]}
                rendered = converter_cls(config=config, artifact_dict=models)(str(pdf))
                CANCEL.check()
                shutil.rmtree(bdir, ignore_errors=True)
                (bdir / "images").mkdir(parents=True)
                md = rendered.markdown
                ext = settings.OUTPUT_IMAGE_FORMAT.lower().replace("jpeg", "jpg")
                for name, img in sorted(rendered.images.items()):
                    new = f"images/{image_name(name)}.{ext}"
                    (img if img.mode == "RGB" else img.convert("RGB")).save(bdir / new, settings.OUTPUT_IMAGE_FORMAT)
                    md = md.replace(f"]({name})", f"]({new})")
                (bdir / "raw.md").write_text(md, encoding="utf-8")
                (bdir / "marker.json").write_text(json.dumps(rendered.metadata, default=str), encoding="utf-8")
                (bdir / "done").write_text(str(round(time.time() - t1, 2)))
                t_convert += time.time() - t1
            else:
                rep.event("progress", f"Pages {span[0]}-{span[1]} (batch {i}/{len(groups)}) from an earlier run",
                          stage="resumed", batch=i, batches=len(groups), pages=span,
                          done_pages=done_pages, total_pages=len(pages))
            done_pages += len(group)
            parts.append((bdir / "raw.md").read_text(encoding="utf-8"))
            metas.append(json.loads((bdir / "marker.json").read_text(encoding="utf-8")))
            if (bdir / "images").is_dir():
                shutil.copytree(bdir / "images", dest / "images", dirs_exist_ok=True)
    finally:
        if models is not None:
            from marker.models import shutdown_models
            shutdown_models(models)

    (dest / "paper.md").write_text(tidy_markdown("".join(parts), {}), encoding="utf-8")
    (dest / "marker.json").write_text(json.dumps({"batches": metas}, indent=1), encoding="utf-8")
    if (dest / "images").is_dir() and not any((dest / "images").iterdir()):
        (dest / "images").rmdir()
    return {"models_s": round(t_models, 2), "convert_s": round(t_convert, 2),
            "batches": len(groups), "batch_pages": batch_size}


class Cancel:
    """Cancellation from a controlling program: with --stdin-control, a line "cancel" on stdin
    (or stdin closing) stops the conversion after marker's current step. SIGTERM does the same."""

    def __init__(self):
        self.flag = threading.Event()

    def check(self) -> None:
        if self.flag.is_set():
            raise KeyboardInterrupt

    def trigger(self) -> None:
        if not self.flag.is_set():
            self.flag.set()
            _thread.interrupt_main()

    def watch_stdin(self) -> None:
        def run():
            for line in sys.stdin:
                if line.strip() == "cancel":
                    break
            self.trigger()
        threading.Thread(target=run, daemon=True).start()


CANCEL = Cancel()


def check_out_dir(out: Path) -> None:
    """Refuse to overwrite files that a previous conversion didn't write."""
    meta = out / "meta.json"
    ours = False
    if meta.is_file():
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
            ours = isinstance(m, dict) and "schema" in m and "converter" in m
        except (OSError, ValueError):
            pass
    clash = [n for n in OUTPUTS if (out / n).exists()]
    if clash and not ours:
        raise FileExistsError(f"{out} already contains {', '.join(clash)} not written by formula-snip; "
                              "choose an empty or new folder")


def convert(args, rep: Reporter) -> int:
    t_start = time.time()
    pdf = Path(args.pdf).expanduser().resolve()
    if not pdf.is_file():
        raise FileNotFoundError(f"no such file: {pdf}")
    out = Path(args.out).expanduser().resolve()
    if out.is_dir():
        check_out_dir(out)
    digest = sha256(pdf)
    count = page_count(pdf)
    pages = parse_pages(args.pages, count)
    selected = len(pages) if pages is not None else count
    if args.max_pages and selected > args.max_pages:
        raise ValueError(f"{pdf.name} has {selected} pages to convert; the limit is {args.max_pages} "
                         "(choose a page range)")
    mode = args.mode
    rep.event("start", f"{pdf.name}: {count} pages, sha256 {digest[:12]}…", source=str(pdf),
              sha256=digest, page_count=count, pages=[p + 1 for p in pages] if pages else None,
              mode=mode, out=str(out))

    vers = versions()
    key = hashlib.sha256(json.dumps([CACHE_LAYOUT, pages, MODES[mode], vers["marker-pdf"]]).encode()).hexdigest()[:12]
    cached = cache_root() / digest / key
    hit = (cached / "paper.md").is_file() and (cached / "timings.json").is_file() and not args.force
    if hit:
        rep.event("progress", "Using cached conversion", stage="cached", cache=str(cached))
        timings = json.loads((cached / "timings.json").read_text())
    else:
        tmp = cached.with_name(key + f".tmp{os.getpid()}")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        try:
            partial = cached.with_name(f"{key}.partial-{args.batch_pages}")
            if args.force:
                shutil.rmtree(partial, ignore_errors=True)
            all_pages = pages if pages is not None else list(range(count))
            timings = run_marker(pdf, all_pages, mode, tmp, partial, args.batch_pages, rep)
            (tmp / "timings.json").write_text(json.dumps(timings))
            shutil.rmtree(cached, ignore_errors=True)
            tmp.rename(cached)
            shutil.rmtree(partial, ignore_errors=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # copy into DIR (only the files we own)
    out.mkdir(parents=True, exist_ok=True)
    check_out_dir(out)
    for name in OUTPUTS:
        p = out / name
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    shutil.copy2(cached / "paper.md", out / "paper.md")
    if (cached / "images").is_dir() and any((cached / "images").iterdir()):
        shutil.copytree(cached / "images", out / "images")

    md = (out / "paper.md").read_text(encoding="utf-8")
    rep.event("progress", "Building formula registry …", stage="formulas")
    t_reg = time.time()
    reg = formulas.build(md, source="paper.md")
    files = formulas.write(reg, out)
    reg_s = round(time.time() - t_reg, 2)

    meta = {
        "schema": SCHEMA,
        "formula_snip": VERSION,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {"path": args.pdf, "name": pdf.name, "sha256": digest, "page_count": count},
        "pages": [p + 1 for p in pages] if pages is not None else list(range(1, count + 1)),
        "converter": {"name": "marker", "version": vers["marker-pdf"], "surya": vers["surya-ocr"],
                      "mode": mode, "settings": MODES[mode]},
        "sympy": vers["sympy"],
        "cached": hit,
        "timings": {**timings, "formulas_s": reg_s, "total_s": round(time.time() - t_start, 2)},
        "quality": quality(md),
        "summary": reg["summary"],
        "files": ["paper.md"] + (["images/"] if (out / "images").is_dir() else []) + files + ["meta.json"],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    rep.event("done", f"Wrote {out}", out=str(out), cached=hit, meta=meta)
    rep.result(f"{out / 'paper.md'}\n" + formulas.summary_line(reg["summary"]))
    return 0


def registry_only(args, rep: Reporter) -> int:
    src = Path(args.markdown).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(f"no such file: {src}")
    out = Path(args.out).expanduser().resolve() if args.out else src.parent
    rep.event("start", f"{src.name}", source=str(src), out=str(out))
    reg = formulas.build(src.read_text(encoding="utf-8"), source=src.name)
    files = formulas.write(reg, out)
    rep.event("done", f"Wrote {', '.join(files)} to {out}", out=str(out), files=files, summary=reg["summary"])
    rep.result(formulas.summary_line(reg["summary"]))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="formula-snip", description="Convert papers to Markdown + a formula registry (offline).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert", help="PDF -> DIR/paper.md, images/, meta.json and the formula registry")
    c.add_argument("pdf")
    c.add_argument("--out", required=True, metavar="DIR")
    c.add_argument("--pages", metavar="RANGE", help="1-based, e.g. 1-12 or 1,3,5-7 (default: all)")
    c.add_argument("--mode", choices=list(MODES), default="ocr",
                   help="ocr (default): OCR every block, best math; fast: PDF text layer, inline math "
                        "stays plain text; balanced: marker's balanced mode")
    c.add_argument("--force", action="store_true", help="ignore the cache and convert again")
    c.add_argument("--batch-pages", type=int, default=10, metavar="N",
                   help="convert N pages at a time; finished batches survive a cancel (default 10)")
    c.add_argument("--max-pages", type=int, default=0, metavar="N",
                   help="refuse PDFs (or page ranges) longer than N pages (default: no limit)")
    c.add_argument("--json", action="store_true", help="JSON lines on stdout")
    c.add_argument("--stdin-control", action="store_true",
                   help='stop when stdin sends "cancel" or closes (for programs that run this)')
    f = sub.add_parser("formulas", help="Markdown -> formulas.json, variables.json, formulas.py")
    f.add_argument("markdown")
    f.add_argument("--out", metavar="DIR", help="default: next to the Markdown file")
    f.add_argument("--json", action="store_true", help="JSON lines on stdout")
    args = ap.parse_args(argv)

    if args.cmd == "convert" and args.batch_pages < 1:
        ap.error("--batch-pages must be at least 1")
    rep = Reporter(args.json)
    signal.signal(signal.SIGTERM, lambda *_: CANCEL.trigger())
    if getattr(args, "stdin_control", False):
        CANCEL.watch_stdin()
    try:
        return convert(args, rep) if args.cmd == "convert" else registry_only(args, rep)
    except KeyboardInterrupt:
        rep.event("cancelled", "cancelled", error="cancelled")
        return 1
    except Exception as e:  # noqa: BLE001 - report every failure the same way
        plain = (FileNotFoundError, FileExistsError, ValueError)
        msg = str(e) if isinstance(e, plain) else f"{type(e).__name__}: {e}"
        rep.event("error", f"error: {msg}", error=msg)
        return 1


if __name__ == "__main__":
    sys.exit(main())
