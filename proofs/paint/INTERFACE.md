# P-PAINT kit: the interface members build against

Proof code (throwaway), Python, permissive libraries only: `numpy`, `pillow` (and `scipy` if needed, BSD).
Run everything with `uv run --with numpy --with pillow python -I <script>`; scripts add their own folder to `sys.path`.

## Files and owners

| File | Owner | What |
|---|---|---|
| `kit/brush.py` | engine | stamping a stroke onto an RGBA float layer (from Hem's `proofs/3d-painterly/paint/brush.py`) |
| `kit/doc.py` | engine | the painting document: layers, masks, operations, history, undo / redo, replay, composite |
| `kit/see.py` | eyes | seeing: view with grid, crop, zoom, before / after, reference side by side, value view, screen-size view |
| `kit/where.py` | eyes | "what is here" and "did my stroke land" |
| `kit/paint.py` | eyes | one CLI over doc + see + where, for agents |
| `kit/HOWTO.md` | eyes (engine adds the brush table) | how an agent paints with the kit |
| `model/*.py` | model | 3D: camera G-buffer, screen ↔ surface ↔ UV, painting from the camera, coverage, model view |

## The document (`kit/doc.py`)

A document is a folder-less JSON file (`<name>.paint.json`) plus a cache. **The JSON operation list is the truth**; pixels are rebuilt from it.

```python
from doc import Doc
d = Doc.new(1920, 1080, background=(0.1, 0.1, 0.12))   # sRGB 0..1; a "background" layer exists
d = Doc.open("street.paint.json")                         # replays to the same pixels
d.add_layer("sky", below=None, mode="normal", opacity=1.0) # modes: normal, multiply, screen
d.set_layer("sky", opacity=0.8, visible=True, mode="normal", locked=False)
m = d.mask_polygon("road", [(x, y), ...], feather=2)       # named mask, plain data; m.inverted() -> "!road"
with d.batch("block in the sky", author="agent:painter"):  # one batch = one undo step
    sid = d.stroke("sky", points, color, size, brush="bristle", **brush_params)  # returns stroke id (int)
    d.fill("sky", color, mask="road")                      # flat fill
    d.gradient("sky", (x0, y0), (x1, y1), c0, c1, mask=None)
    d.fill_region("sky", "road", color, size, angle=..)    # hatch block-in (Hem's), many strokes, one op
d.undo(); d.redo()                                         # by batch; redo is dropped by a new batch
d.history()          # [{batch, label, author, n_ops, stroke_ids}]
d.composite()        # HxWx3 float32 sRGB, all visible layers
d.layer_pixels("sky")  # HxWx4 float32 (premultiplied not required; state which in the docstring)
d.stroke_info(sid)   # the op dict: points, layer, brush, colour, bbox, batch
d.top_stroke_at(x, y) # id of the last stroke that changed this pixel (any layer), or None
d.stroke_coverage(sid) # HxW float32 alpha this stroke laid down (for where.landed)
d.save("street.paint.json"); d.export_png("street.png")
d.snapshot(batch_index) # composite as it was after batch k (for before / after)
```

- Masks: polygon or **layer alpha** (`d.mask_from_layer("jug_shape")`), stored as specs so they replay.
- Strokes on a locked or missing layer fail loudly. Every op records `author` and batch label.
- Speed: replaying the whole log for each undo is fine for this proof if it stays under ~20 s; better: cache the composite after each batch (in memory) up to a cap.

## Brushes (`kit/brush.py`)

`stamp_stroke(layer_rgba, points, color, size, brush, **params) -> coverage` paints into one layer and returns the stroke's coverage (for `top_stroke_at` / `stroke_coverage`). Points are `(x, y, pressure)`; optional 4th value tilt is ignored for now.
Brushes: Hem's `round, bristle, chalk, flat`, plus the gaps Hem's painters asked for: a **square-ended block-in** tip (`block`), a **crisp thin line** (`line`), **hue drift as its own setting** (`hue_jitter`, separate from value / saturation jitter), **wet blend** (`wet`, mixes with what is under it on the same layer, and with the composite below if `sample_all=True`), **smudge** (`wet=1`), **erase** mode, multiply glaze mode. Stamps must stay exact on replay (seeded).

## Seeing and where (`kit/see.py`, `kit/where.py`, `kit/paint.py`)

CLI (agents call these; every command writes a PNG the agent opens with its Read tool, and prints the path):

```
python paint.py <doc> see   [--zoom x y w h] [--grid N] [--size PX] [--layer NAME] [--out f.png]
python paint.py <doc> before-after [--batches K] [--zoom ...]     # last K batches: before | after | difference
python paint.py <doc> ref <ref.png> [--zoom ...] [--diff]          # reference beside the work, same scale
python paint.py <doc> values [--zoom ...]                          # greyscale + value-step posterize
python paint.py <doc> small  [--width 480]                          # as seen small (thumbnail / far view)
python paint.py <doc> what x y                                      # colour (composite + each layer), top layer, top stroke, masks
python paint.py <doc> landed <stroke_id>                            # intended path vs where paint landed: miss in px
python paint.py <doc> history | undo | redo
python paint.py <doc> run script.py                                 # run a stroke script against the doc as one or more batches
```

`landed` reports: the path's distance from the coverage centre line (mean, max, in px), how much of the coverage is outside the intended mask, and clipped length (strokes running off the canvas or out of the mask). A stroke "missed" when the paint's centre line is more than `max(2 px, 10 % of size)` from the path.

## 3D (`model/`)

Uses Hem's still-life scene (`proofs/3d-painterly/scene/make_scene.py`: `parts()`, `CAMERA`), imported read-only from **this** worktree. No USD library needed: the geometry is generated in Python.
- `gbuffer.py`: rasterize from the shot camera (same projection as the USD camera, 1920×1080 or any size): per pixel object name, triangle id, barycentrics, UV, world position, normal, depth.
- `lookup.py`: `screen_to_surface(x, y)` → object, material, UV, texel, position, normal, distance; `uv_to_screen(material, u, v)` → screen points (+ visible or hidden).
- `project.py`: paint from the camera: a stroke (or a whole kit layer) drawn on the screen is carried onto the material's texture through the G-buffer (texel → screen sample, only where the texel is seen by the camera and faces it), reported per stroke (which object, how many texels, miss).
- `coverage.py`: per texture, texels the camera sees (and at what screen size per texel), texels painted, seams.
- `view.py`: the texture on the model through the camera (quick raster, flat or simple sun + fill light): the painter's "see it on the model" view, seconds not minutes.
