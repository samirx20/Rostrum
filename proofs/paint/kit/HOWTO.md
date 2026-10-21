# How an agent paints with the kit

You paint by writing small stroke scripts, then **looking** at what landed. Never paint blind: every round ends with a picture or a "what is here" answer. Commands below are run as

```
uv run --with numpy --with pillow python paint.py <doc.paint.json> <command> ...
```

(`paint.py` lives in the `kit/` folder; give the full path to it.) Every picture command writes a PNG, prints its path, and you open it with your Read tool. Bad arguments (a zoom box off the canvas, a stroke id that does not exist) stop with `error: ...` and exit code 2. They never produce a half result.

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
It walks along the path you gave the stroke and, across the stroke, finds where its paint actually centres. "landed" or "missed by N px". It also says how much of the path got no paint (a mask or the canvas edge ate it) and how much coverage fell outside the stroke's mask. Sharp corners show a large `max` with a small `mean`; that is the brush rounding the corner, not a miss. Get stroke ids from your script's `doc.stroke(...)` return value, from `history`, or from `what`.

### history, undo, redo
```
paint.py doc history     # #batch  'label'  author  ops, stroke ids
paint.py doc undo        # remove the last batch (saved)
paint.py doc redo
```
Undo works by batch, so label batches by idea ("hill edge", "window light"), not "fix 3". A new batch after an undo drops the redo.

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
