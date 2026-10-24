"""look_world's key labels never overlap (an agent reads them); each is placed clear of the ones before it."""
from PIL import Image, ImageDraw, ImageFont

from rostrum2d.mcp.world_picture import _free_spot


def test_labels_close_together_get_their_own_places():
    d, font, taken = ImageDraw.Draw(Image.new("RGB", (400, 300))), ImageFont.load_default(size=13), []
    for i in range(6):
        _free_spot(d, f"key {i}.00 s", font, (50 + i * 3, 100), taken, (400, 300))
    for i, a in enumerate(taken):
        for b in taken[i + 1:]:
            assert not (a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3])
