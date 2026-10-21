# Painting a prop from the camera (P-PAINT, 3D half)

These tools let you paint the still life's textures **as the camera sees them**: you paint on a
flat picture of the shot, and the paint is carried onto the right spot of the texture. No Cycles
render is needed to see the result; every view takes a few seconds.

Run every command from `proofs/paint/model/` like this:

```
uv run --with numpy --with pillow --with scipy python -I <script> ...
```

Every picture a command writes is printed with its full path: open it and look before going on.

## The ideas in one paragraph

- **Frame pixels.** A place on screen is always given in pixels of the 1920 x 1080 shot
  (x to the right, y down), even in zoomed views (the grid labels show frame pixels).
- **Texels.** A place in a texture image is a column / row counted from the image's top-left.
  `v = 0` in UV terms is the image's bottom row (that is how Cycles reads it).
- **Shared textures.** All three pears use one texture (`pear.png`); the jug and its handle share
  `jug.png`; the table texture repeats. Painting one pear can show up on another pear where both
  use the same texels; the tools tell you when that happens.
- **Grazing.** Where a surface turns almost edge-on to the camera (more than 80 degrees by
  default), paint is not carried over: one screen pixel there covers a long smear of texture.

## 1. Look at the shot

```
python view.py --out shot.png                       # textures on the model, no lighting
python view.py --mode lit --out lit.png             # warm sun + cool fill (no shadows)
python view.py --mode objects --out objects.png     # which object is where, labelled
python view.py --zoom 350 250 500 400 --grid 50 --out jug_zoom.png   # sharp close-up + frame-pixel grid
python view.py --mode texel --out texel.png         # how many texture pixels share one screen pixel
python view.py --tex Jug=my_jug.png --mode lit --out try.png         # see a texture you're working on
```

`texel` view: green/yellow = about one texture pixel per screen pixel; blue = many texture pixels
squeezed into one screen pixel (fine detail there is lost; paint bigger); red = one texture pixel
spread over several screen pixels (paint there must be smooth or it looks blocky).

## 2. Find places both ways

```
python lookup.py what 600 400 --out here.png        # what is at frame point (600, 400)?
python lookup.py where Jug 1024 1100 --out there.png   # where does jug.png texel (1024, 1100) show?
python lookup.py where Pear --uv 0.5 0.4 --object Pear2
```

`what` prints object, material, UV, the texel in the texture file, the 3D position (cm), the
surface normal, the distance and how far the surface turns away from the camera. `where` lists
every place that texel lands (one per pear for the pear texture) and says visible or hidden and
why (behind another object, on the far side, off frame).

## 3. Paint on the screen, carry it onto the texture

Paint a layer with the 2D kit (`proofs/paint/kit`, see its HOWTO) at 1920 x 1080 over the shot,
or any transparent PNG of the same size. Draw on the flat view (`view.py --out shot.png`) so you
see what you paint over. Then:

```
python project.py Jug --doc jug.paint.json --layer blush --object Jug --out jug_new.png --check check_dir
python project.py Pear --png pear_spots.png --object Pear2 --out pear_new.png --check check_dir
```

- `--object` limits the paint to that object (needed for a shared texture: otherwise every
  object with the material takes paint where you painted over it).
- `--tex` starts from a texture other than the one in `paint/textures` (your work in progress);
  `--out` is never optional, so the original is only replaced if you name it.
- `--opacity 0.5` lays the layer on at half strength. `--grazing 70` is stricter at edges.

What the report tells you:

| field | meaning |
|---|---|
| `texels_changed` | texture pixels that took paint |
| `paint_px_landed` | screen pixels of your paint that hit the chosen object(s) |
| `paint_px_missed` | screen pixels of paint that fell on something else (by object, or `nothing`) |
| `paint_px_grazing_dropped` | paint on the object but at an edge-on spot, not carried over |
| `check.changed_outside_intended_mean_px / max_px` | how far the painted result sits from where you painted (the "miss", in frame pixels) |
| `check.changed_px_on_other_objects` | the same texels showing on other objects (shared texture) |

`--check DIR` writes `check_before.png`, `check_after.png` and `check_overlay.png`: magenta =
changed where you did not paint, cyan = painted but not carried over (edge-on), orange = the
change also shows on another object that shares the texture.

If no texel changes, nothing is written and the command fails with the reason.

## 4. Check the whole texture

```
python coverage.py Jug --out cover.png --before ../../3d-painterly/paint/textures/jug.png --after jug_new.png
```

Shows which part of the texture the camera sees (tinted by how big it appears), what you painted
(magenta) and the UV island edges (white). `painted_but_unseen` counts paint the camera will never
show (a few texels are normal: painted edges are grown 2 texels into unused texture space so the
seams don't show a line).

## A full round, start to finish

1. `view.py --out shot.png` and `view.py --mode texel --out texel.png`: where is the prop, how big.
2. Paint a stroke layer over `shot.png` with the kit (a script of `Doc.stroke` calls).
3. `project.py ... --check chk` and read the report; open `chk/check_overlay.png`.
4. `view.py --tex Jug=jug_new.png --mode lit --zoom ... --out look.png` to judge it on the model.
5. Repeat; when happy, copy the new texture over `paint/textures/<name>.png` and ask the lead for
   a Cycles render.

## Limits

- The views have no shadows, no bump / height and no depth of field; they are for placing and
  judging paint, Cycles stays the final look.
- One camera only (the shot camera). Paint the far side of a prop by another route (straight on the
  texture with the 2D kit plus `lookup.py where`).
- Only the colour texture is painted; roughness / height maps are not carried yet (same tool can
  carry them: pass that map as `--tex` and a grey layer).
- The G-buffer and texture caches live in `$ROSTRUM_MODEL_CACHE` or `model/.cache/` (~45 MB per
  resolution; rebuilt automatically when the scene files change).
