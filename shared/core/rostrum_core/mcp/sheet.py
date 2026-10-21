"""Pictures made with Pillow for the look tools: scaling a frame and the labelled contact sheet."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..errors import RostrumError, codes

LABEL_H, GAP, MARGIN = 26, 8, 10
BACK, TEXT = (22, 23, 27), (232, 232, 236)


def _open(path: Path) -> Image.Image:
    try:
        return Image.open(path).convert("RGB")
    except OSError as e:
        raise RostrumError(codes.RENDER_FAILED, "look", str(path), f"was drawn but cannot be read back as a picture: {e}") from e


def _save_whole(img: Image.Image, dest: Path):
    part = dest.with_name(dest.stem + ".partial" + dest.suffix)
    img.save(part, "PNG")
    part.replace(dest)


def scaled_copy(src: Path, width: int, dest: Path) -> tuple[int, int]:
    """Write `src` at `width` (never enlarged) to `dest`; returns the size written."""
    img = _open(src)
    if width < img.width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    _save_whole(img, dest)
    return img.width, img.height


def contact_sheet(tiles: list[tuple[Path, str]], tile_w: int, cols: int, dest: Path) -> tuple[int, int]:
    """A grid of (png, label) tiles, each labelled underneath; written whole to `dest`. Returns the size."""
    pictures = [_open(p) for p, _ in tiles]
    tile_h = round(tile_w * pictures[0].height / pictures[0].width)
    cols = max(1, min(cols, len(tiles)))
    rows = -(-len(tiles) // cols)
    W = MARGIN * 2 + cols * tile_w + (cols - 1) * GAP
    H = MARGIN * 2 + rows * (tile_h + LABEL_H) + (rows - 1) * GAP
    sheet = Image.new("RGB", (W, H), BACK)
    draw, font = ImageDraw.Draw(sheet), ImageFont.load_default(size=LABEL_H - 10)
    for i, (pic, (_, label)) in enumerate(zip(pictures, tiles)):
        x, y = MARGIN + (i % cols) * (tile_w + GAP), MARGIN + (i // cols) * (tile_h + LABEL_H + GAP)
        sheet.paste(pic.resize((tile_w, tile_h), Image.LANCZOS), (x, y))
        draw.text((x, y + tile_h + 4), label, fill=TEXT, font=font)
    _save_whole(sheet, dest)
    return W, H
