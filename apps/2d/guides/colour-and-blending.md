# Colour and blending

How a layer mixes with the layers under it (`blend`), and how to change a layer's colours (adjust, levels, curves, a
`.cube` LUT). Read `start-here` first. Fragments show how a tool is called; the numbers are placeholders.

## Blend modes

Every layer has `blend`. The layer is drawn, then combined with what is already drawn under it (in its group or the
composition) by this rule; opacity then fades the result. A group's blend applies to the group as a whole.

| `blend` | What it computes (layer = top, below = what is under it) |
|---|---|
| `normal` | the layer covers what is below |
| `multiply` | top × below: never lighter; white changes nothing, black gives black |
| `screen` | the opposite of multiply: never darker; black changes nothing |
| `add` | top + below: light adds up (glows, light leaks, flares); black changes nothing |
| `overlay` | multiply in the dark parts of below, screen in the light parts: more contrast |
| `soft-light` | a gentle overlay: the top lightens or darkens below a little |
| `hard-light` | overlay with the roles swapped: the top decides where it multiplies or screens |
| `darken` / `lighten` | the darker / lighter of the two, per channel |
| `color-dodge` / `color-burn` | brightens / darkens below by the top, strongly (burned highlights or shadows) |
| `difference` / `exclusion` | the distance between the two colours / a softer version of it |
| `hue`, `saturation`, `color`, `luminosity` | take that part from the top and the rest from below (`color` = hue and colour strength; `luminosity` = brightness) |

```python
orb = shape("orb", shape="ellipse", w=900, h=900, fill="#ff5a2e", blend="screen")
orb.effect("blur", id="orb_soft", radius=160)
```

Useful facts:
- With `screen` and `add`, black is invisible, so a black-to-white gradient is a light that only adds (a sweep).
- With `multiply`, white is invisible, so a white-to-colour gradient is a tint that only darkens (a vignette, a tint
  on white letters).
- To blend only inside a shape, give the blending layer a track matte (`matte`, see `ui-and-product-animation`).
- A layer with frosted glass (`backdrop`) can't have a blend other than normal (refused, loudly).
- The list lives in one file, `apps/2d/python/rostrum2d/blends.txt`; the settings panel's labels come from it.

## A see-through solid fill

A shape, path or text with a solid colour has its own `fillOpacity` (0 to 1, 1 by default, so older files look the
same): only the fill fades, not the outline and not the layer's other parts (the layer's `opacity` fades everything).
It is keyable like any number, and a letter-by-letter text follows it too.

```python
card = shape("card", w=900, h=500, fill="#4f8cff", fillOpacity=0.4)
card.key("fillOpacity", {0.0: 0.0, 1.0: 0.4})
```

- Agents: `layer.fill {target, type: "solid", color, opacity: 0.4}`; on an animated opacity it needs `at` (a key there).
  A gradient's opacity is each stop's (`"#7c4dff 100 80"`), so `opacity` on a gradient fill is refused.
- On the screen: open the Fill colour square; a solid colour has an opacity strip and percentage under the hue, like a
  gradient stop's. A colour of 100 % shows no change.
- Preview and export draw it the same way, with the same engine.
- A picture fill and a painted fill (a painting of the scene, [drawing.md](drawing.md) part 9) are not solid: their `fillOpacity` is the fill's own, and `layer.fill {opacity}` takes it for a picture or painted fill too.

## Colour effects

Pictures, videos, 3D renders, drawings, groups and rigs have four colour effects (a shape or path too while it is filled
with a picture; a flat colour or a text has none: change its colour instead). Each is off until you turn it on, and its
controls appear only then. They act on the layer's whole look (its content, masks and effects), in this order: adjust →
levels → curves → LUT. On a group they act on everything in it, so a group around the whole picture is a grade for the shot.
On the screen each is its own name in the settings panel: **+ Adjust colour**, **+ Levels**, **+ Curves** turn one on in a
click (− on its heading turns it off), and **+ Look file** takes a .cube file (the LUT).

| Effect | Turn on | Fields |
|---|---|---|
| Adjust | `adjust=True` | `exposure` (stops: +1 = twice the light), `contrast` (×, about mid grey), `saturation` (×, 0 = grey), `temperature` (+ warmer, − cooler), `tint` (+ greener, − magenta), `hue` (degrees round the colour wheel) |
| Levels | `levels=True` | `inBlack`, `inWhite` (these become black and white), `gamma` (above 1 brightens the middle), `outBlack`, `outWhite` (how bright black and white come out) |
| Curves | `curves=True` | `curve` (all channels), `curveR`, `curveG`, `curveB`: points `"x,y x,y …"` from 0 to 1 |
| LUT | `lut="C:/…/look.cube"` | `lutMix` (0 = none of it, 1 = all) |

```python
with group("shot", x=960, y=540, w=1920, h=1080, adjust=True, contrast=1.1, saturation=0.95,
           levels=True, inBlack=0.02, outBlack=0.03,
           curves=True, curve="0,0 0.25,0.21 0.75,0.8 1,1", curveB="0,0.03 1,0.97",
           lut=r"C:\Users\me\looks\warm.cube", lutMix=0.8) as shot:
    ...                                              # the layers of the shot
shot.key("exposure", {0.0: -3, 1.0: 0})             # a fade up from dark, in light
```

- **Numbers can be keyed** (exposure, contrast, levels, `lutMix` …). Curve points and the LUT (look) file can't.
- **Levels and curves work in screen brightness** (0 = black, 1 = white), as in a photo editor. A curve passes smoothly
  through its points and never overshoots them; beyond the first and last point it stays flat. `"0,0 1,1"` changes
  nothing. The red, green and blue curves act on the grade's own colour channels, so a strong channel curve can turn
  colours slightly differently from a photo editor's.
- **A LUT** is a `.cube` file (1D or 3D, any size), given by its absolute path. It takes and gives screen colours, as
  LUTs made for photos and video do. You can make your own: write the table with a short script (`LUT_3D_SIZE 17`, then
  17³ lines `r g b`, red changing fastest), or bake one from a grade with the engine's `sksl lut` command.
- Over-bright light is kept through adjust, levels and curves; a LUT clips to its own range.

## Checking it

Look at the result with `look_frame` (one time) and `look_sheet` (several); compare a frame with the effect on and off
by setting `adjust` / `levels` / `curves` to false or `lut` to "" and looking again. Errors are loud and name the layer
and field: a curve that isn't valid points (`shot.curve: point 2 "0.5" is not x,y …`), `inWhite` not above `inBlack`,
or a LUT that is missing, relative, or malformed (`shot.lut: …look.cube: .cube line 12: …`).
