"""rostrum_paint: Rostrum's shared painting kit (README.md). Paint layers, strokes and paint masks are items in the
host app's document (fields.py, ops.py); pixels are a cache of them (canvas.py); the agent sees (see.py) and asks
where (where.py)."""
from .fields import BRUSH, CANVAS_LISTS, FIELDS, HOLDS, LISTS, brush_defaults
from .ops import register

__all__ = ["BRUSH", "CANVAS_LISTS", "FIELDS", "HOLDS", "LISTS", "brush_defaults", "register"]
