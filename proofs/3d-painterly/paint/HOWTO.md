# Painting textures with `brush.py`: a how-to for painter agents

`brush.py` is a small brush engine: you write a Python script of strokes, render it to a PNG, **look** at the PNG, and change the script. `look.py` holds the seeing tools. These are tools only. They don't set a style; the look comes from your strokes.

Run with permissive libraries only:

```
uv run --with numpy --with pillow python -I my_painting.py
```

Because of `-I`, your script must add the paint folder to the path itself:
`sys.path.insert(0, r"C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-painterly\paint")`.

## Colour space

The canvas holds **sRGB-encoded** values from 0 to 1, the same numbers you'd see in a colour picker divided by 255. You're painting a texture by eye, not light values. In the 3D scene, load the PNG as an sRGB colour (albedo) texture.

## The API

```python
from brush import Canvas, curve

c = Canvas(2048, 2048, fill=(0.85, 0.8, 0.7), grain_seed=0, grain_size=3.0)
c = Canvas.load("start.png")            # or start from an existing image

c.stroke(points, color, size, opacity=1.0, tip="round", hardness=0.5, spacing=0.1,
         jitter=0.0, seed=0, angle=None, wet=0.0, grain=0.0, mode="normal", mask=None,
         color_jitter=0.04, size_pressure=0.8, opacity_pressure=0.3)

pts = curve((x0, y0), (x1, y1), (x2, y2), n=32, pressure=(0.3, 1.0, 0.1))
m = c.mask_from_polygon([(x, y), ...], feather=0)   # m.inverted() for the outside
c.fill_region(m, color, size, angle=20, gap=0.7, length=4, bend=0.15, seed=1, tip="flat", grain=0.4)

c.save("out.png"); c.save_log("out.json")
c2 = Canvas.replay("out.json")          # gives exactly the same image again
```

- `points` is a list of `(x, y, pressure)` in canvas pixels, where pressure runs from 0 to 1. `(x, y)` alone means a pressure of 1. Don't draw straight lines point by point. Use `curve(...)`, which makes a smooth line through your points with a pressure that eases from start to middle to end.
- **Every stroke is recorded** in `c.log`. `save_log` writes it as JSON so the painting can be replayed, compared or edited later. Masks are recorded as their polygon, so always make them with `mask_from_polygon`. A raw numpy array is refused on purpose, because it couldn't be replayed.
- `fill_region` is a **block-in tool**. It fills a masked area with many overlapping strokes running at `angle` degrees. It passes any other keyword (`tip`, `grain`, `opacity`, `wet`, `color_jitter` …) to each stroke. Use it to lay in a base fast, then paint over it by hand.

## What each parameter does, visually

| Parameter | What you see |
|---|---|
| `tip="round"` | Clean, even mark. `hardness=0.9` gives a crisp edge, `0.1` a soft airbrush. |
| `tip="bristle"` | Many thin streaks along the stroke. The bristles run dry at different points, so the end breaks into hairs. Bigger `size` means more bristles. |
| `tip="flat"` | Wide, solid band with faint streaks and ragged start and end, like a flat brush pulled sideways. With `angle=None` it sits across the stroke. With a fixed `angle` it makes chisel or calligraphic marks that get thick and thin as the stroke turns. |
| `tip="chalk"` | Round mark whose edge breaks up into dry speckle, like dry brush or pastel. |
| `size` | Width in pixels at full pressure. |
| `size_pressure` | How much low pressure thins the stroke. `0` gives an even width, `1` lets it taper to a point. |
| `opacity_pressure` | How much low pressure fades the stroke. |
| `opacity` | Highest coverage. A stroke never covers itself twice, so `0.5` stays an even 50 % even where the stroke overlaps itself. |
| `angle` | `None` means the tip follows the stroke direction. A number fixes the tip angle in degrees. |
| `spacing` | Distance between stamps, as a share of the tip. The default is fine. Raise it for speed only. |
| `jitter` | Scatters stamp positions (as a share of `size`) for a wobbly edge. |
| `color_jitter` | Slow drift of hue, saturation and value along the stroke, plus colour streaks across the bristles. `0` gives one flat colour. Try `0.04`–`0.15`. |
| `wet` | `0` lays plain paint. Higher values let the brush pick up the paint underneath and drag it forward, mixing into what's there. `1` is a pure smudge with no new paint. |
| `grain` | Paper or canvas tooth. Thin paint (low pressure, low opacity, edges) breaks up on it, while thick paint stays solid. `0.3`–`0.6` reads as textured paint. `grain_seed` and `grain_size` on the Canvas set the tooth pattern. |
| `mode="multiply"` | Glaze: darkens and tints what's under it, like a transparent wash. Use low opacity and a soft round tip for shadow and colour glazes. |
| `mask` | Paint stays inside the region. `feather` softens the region's edge. |
| `seed` | Picks the bristle pattern, ragged ends and colour drift. Give each stroke its own seed so the strokes don't look identical. |

## The look loop

1. Paint a few strokes. Save `out.png` and `out.json`.
2. **Look.** View the whole texture with the Read tool. Then zoom in where it matters:
   ```
   python look.py view out.png view.png --zoom 400 300 512 384 --grid 64
   ```
   The grid labels are **canvas pixels**, so you can read off the exact `(x, y)` for your next stroke.
3. For UV textures, check where the paint lands on the model. The lead supplies the UV guide image (white lines and labels on transparent, same size as the texture):
   ```
   python look.py guide out.png uv_guide.png check.png --opacity 0.6
   ```
4. Compare before and after a change: `python look.py compare old.png new.png cmp.png`.
5. Sample a colour that is already on the canvas: `python look.py pick out.png 812 455 --radius 3` prints `r g b` in 0–1.
6. Change the script and repeat. Look at the actual pixels every time; don't trust that a stroke landed where you meant it to.

## Working tips (technique, not style)

- Work in layers: block in large shapes (`fill_region` or big strokes), then add form with mid-size strokes, then glaze (`mode="multiply"`, low opacity), then add small accents last.
- Let stroke direction follow the form, for example around a jug's curve or along a table's grain. Directional tips (`bristle`, `flat`) only show direction if your `points` run that way.
- On UV textures, leave a few pixels of paint past each UV island edge so seams don't show bare canvas.
- Keep the script as the source of the painting. Change a stroke and re-run, rather than painting on top of an old PNG.

## Speed and limits

- About 30 strokes a second on a 2048×2048 canvas (strokes 20–90 px wide, 150–500 px long, CPU only). 300 strokes take about 10 s. Wet strokes are about 3× slower because they lay down more stamps.
- Very wide bristle or flat tips (over ~150 px) show slight stair-steps along the streak edges.
- Masks are hard-edged unless you set `feather`.
- No undo inside a script: re-run it instead (replay is exact).
- Smudge (`wet`) doesn't rotate the paint it carries with the brush. On sharp turns it smears sideways a little.
