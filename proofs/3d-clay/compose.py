"""P-Clay proof: our Final next to a reference picture, for comparing by eye. Throwaway proof code.

    python -I compose.py <ours.png> <reference image> <out.png>
        [--label-left "Rostrum clay (proof)"] [--label-right "Reference: <artist>, Nomad Sculpt"] [--height 720]

Both pictures are scaled to the same height, centre-cropped to the same shape (the narrower of the two, so neither is
stretched), set side by side on a dark background with a small plain label under each. Needs Pillow. Reference
pictures stay private (C:\\Users\\Sam\\.rostrum\\references\\3d\\); so does the output.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BACKGROUND = (24, 24, 24)
TEXT = (200, 200, 200)
GAP = 24  # between and around the pictures
LABEL_SIZE = 20


def load(path):
    if not os.path.isfile(path):
        sys.exit(f"compose: no file {path}")
    try:
        im = Image.open(path)
        im.load()
    except Exception as e:  # noqa: BLE001 (any unreadable picture is the same failure here)
        sys.exit(f"compose: cannot read {path}: {e}")
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        flat = Image.new("RGB", im.size, BACKGROUND)
        flat.paste(im, mask=im.getchannel("A"))
        return flat
    return im.convert("RGB")


def fit(im, height, aspect):
    """Scale to `height`, then crop the width (centred) to height * aspect."""
    w = max(1, round(im.width * height / im.height))
    im = im.resize((w, height), Image.LANCZOS)
    want = min(w, round(height * aspect))
    left = (w - want) // 2
    return im.crop((left, 0, left + want, height))


def font():
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, LABEL_SIZE)
        except OSError:
            pass
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser(description="Our clay Final next to a reference picture.")
    ap.add_argument("ours")
    ap.add_argument("reference")
    ap.add_argument("out")
    ap.add_argument("--label-left", default="Rostrum clay (proof)")
    ap.add_argument("--label-right", default="Reference")
    ap.add_argument("--height", type=int, default=720)
    a = ap.parse_args()
    if a.height < 64:
        sys.exit("compose: --height must be at least 64")

    left, right = load(a.ours), load(a.reference)
    # the same shape for both: the narrower aspect, so cropping never needs to invent pixels
    aspect = min(left.width / left.height, right.width / right.height)
    left, right = fit(left, a.height, aspect), fit(right, a.height, aspect)

    f = font()
    label_h = LABEL_SIZE + GAP
    W = GAP * 3 + left.width + right.width
    H = GAP + a.height + label_h
    sheet = Image.new("RGB", (W, H), BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    x = GAP
    for im, label in ((left, a.label_left), (right, a.label_right)):
        sheet.paste(im, (x, GAP))
        tw = draw.textlength(label, font=f)
        draw.text((x + (im.width - tw) / 2, GAP + a.height + GAP // 3), label, fill=TEXT, font=f)
        x += im.width + GAP

    out_dir = os.path.dirname(os.path.abspath(a.out))
    os.makedirs(out_dir, exist_ok=True)
    partial = a.out + ".partial.png"
    try:
        sheet.save(partial, "PNG")
        os.replace(partial, a.out)
    except Exception as e:  # noqa: BLE001
        if os.path.exists(partial):
            os.remove(partial)
        sys.exit(f"compose: cannot write {a.out}: {e}")
    print(f"compose: wrote {a.out} ({W}x{H})")


if __name__ == "__main__":
    main()
