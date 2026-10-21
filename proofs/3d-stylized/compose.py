"""P-3D-3: put renders side by side with a label under each.

  python -I compose.py out.png a.png "Label A" b.png "Label B" [c.png "Label C" ...] [--height 540]

Each image is scaled to --height (aspect kept); a small dark gap sits between them and a dark
strip with white text under each. Any problem (missing input, odd argument count) exits non-zero.
Needs Pillow:  uv run --with pillow python -I compose.py ...
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

GAP, STRIP, BG = 12, 52, (18, 18, 20)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("pairs", nargs="+", help="image label [image label ...]")
    ap.add_argument("--height", type=int, default=540)
    a = ap.parse_args()
    if len(a.pairs) % 2:
        sys.exit("compose: every image needs a label (image label [image label ...])")
    items = list(zip(a.pairs[0::2], a.pairs[1::2]))
    missing = [p for p, _ in items if not os.path.isfile(p)]
    if missing:
        sys.exit("compose: input not found: " + ", ".join(missing))
    imgs = []
    for path, label in items:
        try:
            im = Image.open(path).convert("RGB")
        except Exception as e:
            sys.exit(f"compose: cannot read {path}: {e}")
        w = max(1, round(im.width * a.height / im.height))
        imgs.append((im.resize((w, a.height), Image.LANCZOS), label))
    font = ImageFont.load_default(size=28)
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    boxes = [draw.textbbox((0, 0), label, font=font) for _, label in imgs]
    slots = [max(im.width, b[2] - b[0] + 16) for (im, _), b in zip(imgs, boxes)]  # a long label widens its slot
    sheet = Image.new("RGB", (sum(slots) + GAP * (len(imgs) - 1), a.height + STRIP), BG)
    draw = ImageDraw.Draw(sheet)
    x = 0
    for (im, label), b, slot in zip(imgs, boxes, slots):
        sheet.paste(im, (x + (slot - im.width) // 2, 0))
        draw.text((x + (slot - (b[2] - b[0])) // 2 - b[0], a.height + (STRIP - (b[3] - b[1])) // 2 - b[1]),
                  label, fill="white", font=font)
        x += slot + GAP
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.save(a.out)
    print(f"wrote {a.out} ({sheet.width}x{sheet.height})")


if __name__ == "__main__":
    main()
