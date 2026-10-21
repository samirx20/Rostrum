# Sky again: cool top, warm low band, the hot spot on its own screen layer (black = no change).
from _geo import *

with doc.batch("sky values 2", author="agent:painter"):
    doc.gradient("sky", (0, 0), (0, 260), SKY_TOP, SKY_MID)
    doc.gradient("sky", (0, 260), (0, 620), SKY_MID, SKY_GLOW, mask=None)
    doc.mask_polygon("upper", [(0, 0), (1920, 0), (1920, 260), (0, 260)], feather=0)
    doc.gradient("sky", (0, 0), (0, 260), SKY_TOP, SKY_MID, mask="upper")
with doc.batch("glow layer", author="agent:painter"):
    doc.add_layer("glow", below="far", mode="screen")
    doc.gradient("glow", (1000, 540), (1000, 160), (0.55, 0.38, 0.18), (0, 0, 0), shape="radial")
