# shared/painting-kit — `rostrum_paint`, the shared painting kit

One brush engine and one set of painting tools, used by 2D Draw (now), 3D texture and projection painting and the
Editor's paint-over (later). People paint with a pen (pressure); agents paint with the same brushes and get tools to
see the canvas and know where each stroke landed (`docs/PLAN.md` › Tools for agents to paint). Shaped by P-PAINT
(Team Priyam, `proofs/paint/`) and Hem's painters' notes (`proofs/3d-painterly/README.md`).

## The idea

- **Strokes are items in the app's one document.** A host app puts a kit **canvas** in one of its own item types
  (2D: a drawing's `frame`). A canvas holds `paints` (paint layers, bottom first) and `paintmasks`; a paint layer
  holds `strokes` in painting order (and **fills**: a closed area kept as its outline, `fill.py`, laid like a
  stroke; `fill.region(alpha, at, gap)` finds the outline, with gap closing). So painting goes through `Document.apply` like every other change: one history,
  undo / redo per author, who painted what, script re-runs that never wipe a person's strokes.
- **A stroke batch is one call list**: `doc.apply([stroke.add, stroke.add, …], who)` = one change = one undo step,
  labelled and recorded with its author. A live pen stroke is one gesture (`stroke.add` once, then `stroke.set
  {points}` while drawing; release = one change).
- **Brushes are data**: every brush setting is a `Param` with range, importance and `valid_when` (`fields.BRUSH`);
  `fields.BAR` says which a screen shows in its tool bar while painting (the rest go to its panel: never both).
  The brush panel, the stroke inspector, the MCP schema and `stroke.add`'s checks all read it; a setting that doesn't
  apply right now is absent (wetness only with smudge, tip angle only when the tip doesn't turn with the stroke).
- **Pixels are a cache of the strokes**, never the truth: an agent or a person never waits for a full replay to look.
- **Seamless canvases** (`wrap.py`): a stroke with `wrap` lays every dab that crosses an edge again on the opposite side,
  the smudge reservoir reads across the joined edges, the paper's tooth repeats with the canvas, and `fill.region(...,
  wrap=True)` treats the edges as joined. A host says which canvases are seamless (`register(..., seamless=fn)`: 2D a
  seamless painting, 3D a texture that repeats); strokes made on one get `wrap` and keep it.

```python
import rostrum_paint
rostrum_paint.register(REGISTRY, canvas_types=("frame",))      # paint.add/set/move/remove/clear/unlock,
                                                               # stroke.add/set/remove, fill.set, paintmask.add/set
rostrum_paint.register(REGISTRY, canvas_types=("mesh",), layer_fields=[channel])   # a host's own paint layer fields
                                                               # (3D: what a layer paints), on paint.add and paint.set
KIND = DocKind(..., lists={..., "frame": rostrum_paint.CANVAS_LISTS, **rostrum_paint.LISTS})

doc.apply([{"op": "stroke.add", "target": "ink", "args": {"points": [[x, y, pressure], …], "color": "#ffb040",
            "size": 40, "brush": "bristle"}}, …], Who.agent("painter"))           # one batch, one undo step
from rostrum_paint import canvas, where, see
canvas.png(frame, w, h)                     # the picture (content-keyed file), what the 2D engine draws
where.what(frame, w, h, x, y)               # colour, each layer's colour, top stroke, masks there
where.landed(frame, w, h, "stroke_12")      # did the paint land on the path (mean / worst px off)
see.view(canvas.rgba8(frame, w, h), zoom=(x0, y0, x1, y1), grid=50)   # a look with a labelled pixel grid
see.view(canvas.rgba8(frame, w, h), zoom=(x0, y0, x1, y1), grid=0)    # the same, smooth: to judge texture
```

**Zooming in: pixels or smooth** (`sampling` on `see.view` / `see.before_after`, and on the 2D tools `look_drawing` /
`look_drawing` (`what: "change"`)). `"pixels"` blows each canvas pixel up into a sharp square: use it to place strokes on the
pixel grid. `"smooth"` resamples (bicubic up, Lanczos down), so bristle streaks, grain and soft edges look as they
will on screen: use it to judge texture. The default `"auto"` is pixels when a grid is drawn and smooth when it isn't
(`grid=0`), because the grid is for placing and no grid is for looking. Under 3× (and every look that shrinks the
canvas) both resample smoothly.

## Modules (each < 200 lines)

| Module | Does |
|---|---|
| `fields` | the item types and their fields: paint layer, stroke (the brush), paint mask; `BRUSH` |
| `ops` | the operations on a host's registry; `build`, the one item builder (also used by an app's script layer) |
| `marks`, `brush` | the brush engine (carried over from P-PAINT): tips round, bristle, chalk, flat, block, line; pressure; colour and hue drift; paper grain; wet smudge and pick-up; modes normal, multiply, erase, screen, add, and overlay, soft_light, color (blended with a copy of what was under the stroke, so it still lands as one mark). Seeded: same stroke, same pixels. A stroke is one mark: its dabs together lay its coverage once in every mode, and light strokes (add) sum without being cut down to the alpha (`marks.apply_paint`) |
| `canvas` | where pixels are made: chain-keyed layer states, content-keyed PNGs |
| `compose` | layers together (normal, multiply, screen, add over transparency); masks as pixels |
| `where` | `what` is at a pixel; `landed` (P-PAINT's measure) |
| `see` | the looks on arrays: zoom (sharp pixels or smooth) with a labelled grid and a checkerboard under transparency, before / after, values, small, side by side, onion skin |

## Where pixels are made: numpy now, behind one door (decision, S6)

**Decision: keep the numpy brush engine for now, with a cache that never replays to look; move stamping to Rust later
behind `canvas.stamp`, the only function that turns a stroke item into brush calls.**

- Why not Rust / Skia now: the 2D engine (`apps/2d/engine/`) is Team Hem's and is being moved in (H5); a second
  native build in `shared/` needs its own build and binding work, more than this brief's time. Measured below, the
  cache alone already brings a look under a second for a stroke or an undo; what stays slow is stamping many big or
  wet strokes, which is exactly what a native engine speeds up. The brush maths (`marks`, `brush`) is small and
  deterministic, so a port is straightforward and the replay test checks it pixel for pixel.
- How the cache works: each paint layer's state after its first *i* strokes has a key (the key after *i − 1* strokes +
  stroke *i*'s JSON + what it reads: its mask, and the layers below when it picks them up). A render takes the longest
  prefix it holds in memory and stamps only the strokes after it. A new stroke costs one stroke; undo / redo / a
  redrawn drawing cost the strokes after the nearest kept state (every 24 strokes during a replay, plus every state
  looked at; memory capped at 1.2 GB, oldest first). Finished canvases are PNG files named by their content in
  `C:\Users\<you>\.rostrum\cache\paint\` (capped at 1 GB, oldest first): the engine only reads them, and an unchanged drawing
  is never drawn again. Keys include a hash of the brush code, so a brush change never serves stale pixels.

Measured on the laptop (1920×1080 canvas; "look" = make the picture file + a 1200 px look image with grid):

| | empty canvas | 1,000 strokes already |
|---|---|---|
| one round stroke: apply + look | 0.001 + 0.47 s | 0.05 + 0.73 s |
| one wet (smudge + pick-up) stroke | 0.001 + 0.52 s | 0.05 + 0.83 s |
| a batch of 20 bristle strokes (8–40 px) | 0.00 + 1.02 s | 0.10 + 1.25 s |
| undo of two batches + look | 0.46 s | 0.32 s |
| full replay with no cache (what P-PAINT round 1 did on every look) | — | 32 s |

So: **a look is under a second for a stroke, a pen stroke and an undo; a 20-stroke batch takes about 1.2 s**, of which
~0.45 s is the fixed cost of a look at 1080p (compositing, converting, writing the PNG, the look image) and the rest is
stamping. Next, in order of gain: native stamping (Rust, behind `canvas.stamp`); composite and convert only the
changed box; keep layer states on disk so a reopened document doesn't restamp.

## Tests

`.venv\Scripts\python.exe -m pytest -q shared\painting-kit\tests` (about 2 s): cached pixels equal a full replay
(bristle, chalk with grain, wet pick-up, a multiply layer); undo of a batch gives back the exact document and pixels;
`landed` reports a 6 px miss as 6 px; a script re-run removes a stroke it no longer makes, but keeps one a person
changed (and says so).

## Not yet

- Pen tilt is stored with a point but not used by the brush; no eraser end of the pen.
- A stroke on a locked paint layer is refused; editing an existing stroke (`stroke.set`) inside a locked layer is not.
- Masks made from strokes or layers, perspective guides, image / underpaint layers, one stroke into several maps
  (colour + roughness + height), 3D camera painting: P-PAINT's list, for the 3D and Editor stages.
- `rostrum_core` copies the whole document once per call: fine at a few thousand strokes (0.05–0.1 s), to fix in the
  core (structural sharing) before 10,000-stroke paintings.

## Attribution rows

No new dependencies. numpy and Pillow are already used by other parts and proofs.

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| NumPy | from uv cache | BSD-3-Clause | `shared/painting-kit` (brush engine, compositing) | Python package | yes | Keep the notice | https://pypi.org/project/numpy/ |
| Pillow | from uv cache | MIT-CMU | `shared/painting-kit` (masks, PNG files, look images) | Python package | yes | Keep the notice | https://pypi.org/project/pillow/ |

## Native brushes (S9)

Dabs are laid by the 2D engine's native stamper (`apps/2d/engine/stamp/`, Hem H8) when it is built: the same pixels
as the numpy path, bit for bit, about 10–12× faster. Build it with `cargo build -p rostrum2d-stamp --profile agent`
in `apps/2d/engine` (or point `ROSTRUM_STAMP_LIB` at the library). Without it the kit still paints, the slow way, and
says so: `canvas.status()` always, and the first `look_drawing` reply carries the note as a warning.
