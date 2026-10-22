"""Draws the apps' window / shortcut / file icons (.ico, 16–256 px) into a folder: a placeholder until real icons
are designed. Pillow (MIT-CMU) at build time only.

    python tools/release/icons.py <folder>
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ICONS = {"rostrum2d": ("2D", (64, 120, 255)), "rostrumsound": ("S", (236, 92, 64)),
         "document2d": ("2D", (40, 60, 110)), "documentsound": ("S", (110, 50, 40))}
FONT = Path(__file__).resolve().parents[2] / "apps" / "2d" / "engine" / "fonts" / "InterVariable.ttf"


def draw(text: str, colour, size=256) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, size - 8, size - 8), radius=size // 5, fill=colour + (255,))
    font = ImageFont.truetype(str(FONT), int(size * (0.42 if len(text) > 1 else 0.56)))
    font.set_variation_by_name("Bold")
    d.text((size / 2, size / 2), text, font=font, fill=(255, 255, 255, 255), anchor="mm")
    return img


def main(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    for name, (text, colour) in ICONS.items():
        draw(text, colour).save(folder / f"{name}.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
