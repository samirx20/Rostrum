# How an agent paints with the kit

You paint by writing small stroke scripts, then **looking** at what landed. Never paint blind: every round ends with a picture or a "what is here" answer. Commands below are run as

```
uv run --with numpy --with pillow python paint.py <doc.paint.json> <command> ...
```

(`paint.py` lives in the `kit/` folder; give the full path to it.) Every picture command writes a PNG, prints its path, and you open it with your Read tool. Pictures go to `C:\Users\Sam\.rostrum\waves\scratch\paint-look\<document name>\` (outside the worktree, the newest 40 per command are kept); `--out file.png` puts one somewhere else.

**Pixel cache.** Saving also writes `<doc>.paint.json.cache.npz` beside the document: the finished layer pixels, masks, which-stroke map, every stroke's coverage, and the last few states for undo. The next command loads that (about 2-3 s for a 1080p painting with 13 layers and 1,555 strokes) instead of replaying every op (about 66 s). The cache is only a copy: it is used only when it matches the document's op list *and* the kit's own code, otherwise the command replays, prints `note: ... replaying N batches` on stderr, and writes a fresh cache. Deleting it is always safe. Don't commit it. Bad arguments (a zoom box off the canvas, a stroke id that does not exist) stop with `error: ...` and exit code 2. They never produce a half result.

All coordinates are **canvas pixels**: the grid labels, zoom boxes, `what` and the outlines in before / after all use the same numbers you put in your strokes.

## The look loop

1. **Block in** with a stroke script (`run`). One `with doc.batch("label")` per idea, so each idea is one undo step.
2. **See it**: `small` first (does the big shape read?), then `values` (do the light and dark masses work?), then `see --zoom` on the part you care about.
3. **Check the hard bits by number**: `what x y` for "what colour and which layer is here", `landed <id>` for "did that stroke go where I meant".
4. **Compare**: `before-after` for the change you just made, `ref` against a reference when you have one.
5. **Fix**: `undo` if the batch was wrong, or paint a correcting batch. Go back to 1.

## The stroke script

A script is plain Python with `doc` already in scope. Do not open or save the document yourself; `run` does that after your script ends.

```python
# sky.py
doc.add_layer("sky")
doc.mask_polygon("hill", [(0, 600), (900, 480), (1920, 620), (1920, 1080), (0, 1080)])
with doc.batch("sky wash", author="agent:painter"):
    doc.gradient("sky", (0, 0), (0, 600), (0.25, 0.42, 0.75), (0.85, 0.80, 0.70))
with doc.batch("hill edge"):
    sid = doc.stroke("sky", [(0, 600, 1), (900, 480, 1), (1920, 620, 1)], (0.1, 0.12, 0.1), 14, brush="line")
    print("hill edge stroke id", sid)   # print what you will want to check; run shows your prints
```

Run it: `paint.py street.paint.json run sky.py` (add `--new 1920 1080` the first time to create the document).
Running a script twice paints twice. If you want a redo, `undo` the batch first, or write the script so it starts by adding only what is new. A person's edits made in the GUI stay: your script only adds batches.

## The commands

| Command | Use it for |
|---|---|
| `see` | Look at the canvas or a part of it, with a labelled pixel grid. |
| `before-after` | See what your last batch(es) changed. |
| `ref` | Your work beside a reference image. |
| `values` | Colour, greyscale, and a few flat value steps. |
| `small` | The picture as a viewer sees it from far away. |
| `what x y` | Everything about one pixel. |
| `landed id` | Did a stroke land on the path you gave it? |
| `history`, `undo`, `redo` | The batches, and stepping back and forward. |
| `export out.png` | The finished picture, full size, no grid. |
| `run script.py` | Paint. |

### see
```
paint.py doc see                                # whole canvas, grid chosen for you
paint.py doc see --zoom 600 400 200 120         # x y width height, canvas px
paint.py doc see --zoom 600 400 40 24 --grid 4  # pixel level: each canvas pixel is a big square
paint.py doc see --layer ink --zoom 0 0 400 300 # one layer alone over a checkerboard
paint.py doc see --size 1600 --grid 0           # wider picture; --grid 0 turns the grid off
```
Grid lines sit on pixel edges: the line labelled 600 is the left edge of pixel 600. When you zoom in a lot, pixels are drawn as sharp squares, so you see exactly what the brush wrote.

### before-after
```
paint.py doc before-after                       # last batch
paint.py doc before-after --batches 3 --zoom 400 300 600 400
```
Three panels: before, after, and a difference picture where every changed pixel glows yellow/red. A green box outlines the whole changed area in every panel. If the box is somewhere you did not expect, your stroke landed in the wrong place (then ask `landed`). "nothing changed" means your batch did nothing visible.

### ref
```
paint.py doc ref C:\path\to\reference.png
paint.py doc ref C:\path\to\reference.png --zoom 0 0 960 540 --diff
```
The reference is scaled to the canvas size, so the same zoom box shows the same part of both. `--diff` adds a third panel: brighter means further from the reference. Use it to find which region to fix next, not as a score to chase. Look at the pictures too.

### values
```
paint.py doc values
paint.py doc values --zoom 0 300 1920 600 --steps 4
```
Colour | greyscale | flat value steps, with the share of the area in each step. Squint test for paint: if the grey picture loses a shape you wanted, the shape is separated only by hue and will vanish in a dark room or on a phone.

### small
```
paint.py doc small                 # 480 px wide
paint.py doc small --width 160     # a thumbnail
```
What survives at this size is what a viewer actually gets. Fine brushwork that vanishes here is fine as texture, but it cannot carry the shape.

### what x y
```
$ paint.py doc what 1020 540
pixel (1020, 540) on a 1920x1080 canvas
  composite colour: #e63333  rgb (0.9, 0.2, 0.2)
  layers (top first):
    ink            colour #e63333 alpha 1.00  ...  <- top painted layer
    sky            colour #000000 alpha 0.00
    background     colour #1a1a1f alpha 1.00
  top stroke: id 2 on layer 'ink', brush round, batch #1 'road lines' by agent
  inside masks: road (1.00)
```
Use it before editing: "which layer do I need to be on to change this?", "which stroke made this mark?" (then `undo` its batch, or erase it), "is this point inside the mask I think?". A top stroke of `none` means only fills or gradients are here.

### landed id
```
$ paint.py doc landed 2
stroke 2: landed
  centre line vs path: mean 0.22 px, max 4.13 px (a miss is more than 2.0 px = max(2, 10% of size 10))
  path length 286 px, 100% of it got paint, clipped length 0 px (off the canvas or outside the mask)
```
It walks along the path you gave the stroke and, across the stroke, finds where its paint actually centres.
**The rule:** a stroke *landed* when the **mean** distance from its path is at most the limit (2 px, or 10 % of the brush size if bigger) **and** the **max** is at most 3 times that limit; otherwise it says "missed by N px on average" or "missed in one place by N px". At least half of the path must get paint. "Got paint" leaves out the first and last 8 % of the path, because every brush may taper or fray its ends on purpose (`flat` and `bristle` fade them by design). It also says how much of the path got no paint (a mask or the canvas edge ate it) and how much coverage fell outside the stroke's mask. Sharp corners show a larger `max` with a small `mean`; that is the brush rounding the corner, and the 3x allowance is for it. Get stroke ids from your script's `doc.stroke(...)` return value, from `history`, or from `what`.

### history, undo, redo
```
paint.py doc history     # #batch  'label'  author  ops, stroke ids
paint.py doc undo        # remove the last batch (saved)
paint.py doc redo
```
Undo works by batch, so label batches by idea ("hill edge", "window light"), not "fix 3". A new batch after an undo drops the redo. The redo list is saved inside the document, so `redo` works in a later command.
Setup ops made outside a `with doc.batch(...)` (`add_layer`, `set_layer`, `mask_polygon`, `mask_from_layer`) join the **next** batch, so they undo together with the painting that needed them. If no batch follows, they become one `setup` batch when the document is saved. Paint ops outside a batch are still one batch each.
Undo and redo are fast for the last 3 batches (kept in the cache); a fourth undo in a row replays the painting once (and says so), after which the next 3 are fast again.

## Working tips (technique, not looks)

- **Big to small.** Block in the large shapes with a big flat brush, check `small` and `values`, then go smaller. If the thumbnail is wrong, no amount of detail fixes it.
- **Zoom to the scale of the problem.** Size and edge questions: zoom 3-6x. Colour questions: `what`. Placement questions: `before-after` and the green box.
- **Test one stroke before a hundred.** Paint one, `see --zoom` it, `landed` it, then loop.
- **Mask first for hard edges.** A polygon mask (or a layer's alpha as a mask) keeps strokes inside a shape; then `landed` tells you how much paint the mask refused.
- **Keep ideas on their own layers** so `see --layer` and undo stay easy. One layer for everything makes later fixes expensive.
- **Compare like with like.** When matching a reference, zoom into the same box in both; don't judge from the whole frame alone.
- **Print as you go** in scripts (stroke ids, counts); `run` shows them.
- **Say what you could not check.** If a view looks off (labels hidden, grid crowded), change `--zoom` / `--grid` / `--size` instead of guessing.

<!-- BRUSHES: member engine writes the "Brushes" section below this line. Do not overwrite. -->

## Brushes

`doc.stroke(layer, points, color, size, brush="round", mask=None, **settings)`. `points` are `(x, y, pressure)` in canvas pixels; use `curve((x0, y0), (x1, y1), ..., n=32, pressure=(start, mid, end))` from `brush.py` for smooth paths. A wrong brush or setting name is refused, with the list of the right ones. A picture of every brush: `C:\Users\Sam\.rostrum\waves\results\stage1\p-paint\brush-sheet.png` (rows = brushes; columns = even pressure, tapered, small 10 and 3 px, wet 0.5, smudge, grain).

| Brush / setting | What you see |
|---|---|
| `round` | Clean, even mark. `hardness=0.9` gives a crisp edge (never sharper than about 1 px, so no jaggies); `0.1` a soft airbrush. |
| `bristle` | Many thin streaks along the stroke; the bristles run dry at different points, so the end breaks into hairs. Under ~6 px it turns into a broken dry line. |
| `chalk` | Round mark whose edge breaks into dry speckle, like pastel or dry brush. |
| `flat` | Wide band with faint streaks and ragged, fading start and end. With a fixed `angle` it makes chisel marks that go thick and thin as the stroke turns. |
| `block` | Square-ended block-in: a crisp-edged band with slightly ragged square ends and faint streaks. Use `size_pressure=0` for an even width (with pressure taper it becomes a wedge). For laying in shapes without leaf or flame tips. |
| `line` | Crisp thin line, antialiased, usable from 1 to 6 px. Pressure tapers it; below 1 px it fades instead of breaking into dots. Ignores `hardness`. |
| `size` | Width in pixels at full pressure. |
| `size_pressure` | How much low pressure thins the stroke. `0` = even width, `1` = tapers to a point. Default `0.8`. |
| `opacity`, `opacity_pressure` | Highest coverage, and how much low pressure fades it. A stroke never covers itself twice, so `0.5` stays an even 50 % where it overlaps itself. |
| `angle` | `None` = the tip follows the stroke; a number fixes the tip angle in degrees. |
| `color_jitter` | Value and saturation drift along the stroke, plus light / dark streaks across the bristles. Hue stays put. `0` = one flat colour, try `0.04`–`0.2`. |
| `hue_jitter` | Hue drift along the stroke, in degrees either way (`8` = up to ±8°). Separate from `color_jitter`; default `0`. |
| `wet` | `0` lays plain paint. Higher values pick up the paint already on **this layer** and drag it along, mixing it in; `1` is a pure smudge with no new paint. Smudging over transparent parts of the layer drags transparency in (it thins the paint). |
| `sample_all=True` | With `wet`, pick up what you **see** (this layer over everything below it) instead of this layer only. Lets you smudge colour from lower layers into an empty layer without touching them. |
| `grain` | Paper tooth: thin paint (low pressure, low opacity, edges) breaks up on it, thick paint stays solid. `0.3`–`0.6` reads as textured paint. The tooth pattern is the document's (`Doc.new(..., paper_seed, paper_size)`). |
| `mode="multiply"` | Darkens and tints paint **already on this layer** (nothing happens on an empty part). For a glaze over everything below, make a layer with `add_layer(name, mode="multiply")` and paint on it normally. |
| `mode="erase"` | Removes paint from this layer by the stroke's coverage (any tip, so a `block` erase gives a square-ended cut). |
| `mode="screen"`, `mode="add"` | Light: the paint brightens what is already on this layer and on empty parts lays itself down, so glows and haze **stack** instead of replacing each other. `screen` never goes past white and keeps colours soft; `add` is stronger and burns to white where light piles up. Put light on its own layer made with `add_layer(name, mode="screen")` (or `"add"`) to brighten everything below. |
| `mask` | A mask name (`"road"`) or its inverse (`"!road"`): paint stays inside. |
| `jitter` | Scatters stamp positions (share of `size`) for a wobbly edge. |
| `spacing` | Distance between stamps as a share of the tip. Leave it; raise it only for speed. |
| `seed` | Picks the bristle pattern, ragged ends and colour drift. Give each stroke its own seed so strokes don't repeat. |

Other paint ops: `doc.fill(layer, color, mask=None, opacity=1, mode="normal")`; `doc.gradient(layer, (x0, y0), (x1, y1), c0, c1, mask=None, opacity=1, mode="normal", shape="linear" or "radial", alpha0=None, alpha1=None)` for soft value areas and glows. A gradient paints **over** the layer by its own alpha: `c0` / `c1` may be RGBA, or give `alpha0` / `alpha1` (default 1). Fade `alpha1` to 0 for a glow that leaves the rest of the layer alone. A radial gradient (centre `(x0, y0)`, edge at `(x1, y1)`) paints nothing outside its circle; a linear one keeps its end colour and alpha beyond the end point. With `mode="screen"` many glows stack on one layer. (Gradients in documents saved before this have no `v` field and replay the old way, covering the whole layer, so old paintings keep their pixels.) `doc.fill_region(layer, mask, color, size, angle=0, gap=0.7, length=4, bend=0.15, pressure=(0.5, 1, 0.3), seed=0, brush="flat", **settings)` hatches a masked area with many strokes in one op (one stroke id). Each returns a stroke id.

Speed (1920×1080, strokes 20–90 px wide and 150–500 px long, grain on): about 37 strokes a second dry, about 9 wet. Undo of a recent batch is instant (kept states share the layers a batch did not touch, so many fit in memory); older ones replay from the nearest kept state.
