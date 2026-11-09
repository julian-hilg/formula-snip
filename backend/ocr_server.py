#!/usr/bin/env python3
"""FormulaSnip OCR backend — turns an image of a formula into LaTeX, fully locally.

Uses the surya recognition model that ships with marker (marker-pdf). The app
starts this once and keeps it running so the model stays loaded.

Protocol (JSON lines):
    stdout  {"ready": true}                         once the model is loaded
    stdin   /path/to/image.png                      one image path per line
    stdout  {"ok": true, "latex": "...", "ms": 812} or {"ok": false, "error": "..."}

Standalone test:  python ocr_server.py --image examples/black_scholes.png
"""

import argparse
import html
import json
import os
import re
import sys
import time


def html_to_latex(s: str) -> str:
    """surya HTML (<p>, <math>, <math display="block">) -> LaTeX text.

    A snip that is a single formula becomes bare LaTeX (like Mathpix);
    anything mixed becomes text with $inline$ and \\[ display \\] math.
    """
    s = s.strip()
    only = re.fullmatch(r"(?:<p>)?\s*<math[^>]*>(.*?)</math>\s*(?:</p>)?", s, re.S)
    if only:
        return html.unescape(only.group(1)).strip()
    s = re.sub(r'<math display="block">(.*?)</math>',
               lambda m: f"\n\\[\n{m.group(1).strip()}\n\\]\n", s, flags=re.S)
    s = re.sub(r"<math[^>]*>(.*?)</math>", lambda m: f"${m.group(1).strip()}$", s, flags=re.S)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</p>\s*", "\n\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\n{3,}", "\n\n", html.unescape(s))
    return s.strip()


class FormulaOCR:
    def __init__(self):
        from surya.inference import SuryaInferenceManager
        from surya.recognition import RecognitionPredictor

        self.manager = SuryaInferenceManager()
        self.predictor = RecognitionPredictor(self.manager)
        self.predictor.disable_tqdm = True

    def close(self):
        self.manager.stop()

    def _html(self, image) -> str:
        from surya.layout.schema import LayoutBox, LayoutResult

        w, h = image.size
        box = LayoutBox(polygon=[[0, 0], [w, 0], [w, h], [0, h]], label="Text",
                        raw_label="Text", position=0, count=2000)
        res = self.predictor(images=[image], full_page=False,
                             layout_results=[LayoutResult(bboxes=[box], image_bbox=[0, 0, w, h])])
        block = res[0].blocks[0]
        if block.error:
            raise RuntimeError("recognition failed")
        return block.html or ""

    def latex(self, path: str) -> str:
        from PIL import Image

        image = Image.open(path).convert("RGB")
        scale = max(1.0, 64 / min(image.size))  # tiny snips read badly -> upscale
        if scale > 1:
            image = image.resize((round(image.width * scale), round(image.height * scale)),
                                 Image.LANCZOS)
        return html_to_latex(self._html(image))

    def warm_up(self):
        from PIL import Image
        self._html(Image.new("RGB", (64, 64), "white"))


def serve():
    # Keep the protocol channel clean: libraries print to stdout, so move them to stderr.
    proto = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    def send(obj):
        proto.write(json.dumps(obj) + "\n")
        proto.flush()

    try:
        ocr = FormulaOCR()
        ocr.warm_up()
    except Exception as e:
        send({"ready": False, "error": f"model failed to load: {e}"})
        return 1
    send({"ready": True})
    try:
        for line in sys.stdin:
            path = line.strip()
            if not path:
                continue
            t = time.time()
            try:
                send({"ok": True, "latex": ocr.latex(path), "ms": round((time.time() - t) * 1000)})
            except Exception as e:
                send({"ok": False, "error": str(e)})
    finally:
        ocr.close()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", nargs="+", help="OCR these images, print LaTeX, exit")
    args = ap.parse_args()
    if not args.image:
        return serve()
    ocr = FormulaOCR()
    try:
        for p in args.image:
            print(ocr.latex(p))
    finally:
        ocr.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
