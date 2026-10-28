# Data, maths and graphs

How to turn an equation, a function or a table into shapes that move: plots, axes, 3D-looking surfaces, charts, and one
design filled in from many rows. Read `start-here` first, and `shape-and-path-animation` for paths, trim and riding.

The idea: **Python does the maths, the document holds the result.** A curve is a `path` layer whose `d` you compute; a
bar is a `shape` whose height you compute; a number is a counting `text`. Once made, they are ordinary layers a
person can pick, move and retime.

Two ways in:

- **A script** (`run_script`, `source`): the helpers below are already there, with `math`. Scripts can't import or open
  files, so a table comes in as text (`parse_table`) or through `inspect_table`.
- **Full Python next to the document** (numpy, pandas, your own files): `from rostrum2d.plot import …` and
  `from rostrum2d.table import read_table`, compute, and write the script text that `run_script` takes (last section).

| Helper | Gives |
|---|---|
| `plot_area(x=(lo, hi), y=(lo, hi), rect=(left, top, w, h))` | `P(x, y)` → comp px, y up; `P.x(v)`, `P.y(v)` map one axis |
| `curve_points(f, x0, x1, n=200, ylim=None)` | `[(x, f(x)), …]`; `None` where f fails or leaves `ylim` (a gap) |
| `param_points(f, t0, t1, n)` / `polar_points(r, a0, a1, n)` | points of `f(t) -> (x, y)` / of `r(θ)` |
| `line_d(points, to=P, smooth=False, closed=False)` | path data through the points; `smooth` = a curve through every point |
| `lines_d(list_of_point_lists, to=…)` | many lines as one path (a grid, a wireframe) |
| `nice_ticks(lo, hi, count=5, extend=False)`, `tick_label(v, ticks, separator="")` | round tick values (1, 2, 5 steps) and their words (`separator=","` → "1,500") |
| `view3d(yaw, pitch, scale, center, distance=None)` | `V(x, y, z)` → comp px, z up; `distance` adds perspective |
| `surface_lines(f, (x0, x1), (y0, y1), lines=16, steps=48, fine=0.001)` | `z = f(x, y)` as wireframe lines for `lines_d(…, to=V)`; extra points where the surface bends sharply (a peak, a pit), so it never zigzags |
| `parse_table(text)` | CSV text → `[{column: value}, …]`, numbers as numbers |

A path made with `d` and none of `x`, `y`, `w`, `h` is read in comp px, so what `P` maps lands exactly there.

## Equation → path, axes and ticks

```python
comp("graph", width=1920, height=1080, fps=30, duration=4, background="#0c0d12")
P = plot_area(x=(0, 4 * math.pi), y=(-1.5, 1.5), rect=(200, 140, 1560, 800))
xt, yt = nice_ticks(0, 4 * math.pi, 6), nice_ticks(-1.5, 1.5, 6)

grid = [[(x, -1.5), (x, 1.5)] for x in xt] + [[(0, y), (4 * math.pi, y)] for y in yt]
path("grid", d=lines_d(grid, to=P), fill="none", stroke=True, strokeColor="#2a2d38", strokeWidth=2)
path("axes", d=lines_d([[(0, -1.5), (0, 1.5)], [(0, 0), (4 * math.pi, 0)]], to=P), fill="none", stroke=True, strokeColor="#8a8fa3", strokeWidth=3)
for x in xt:
    text(body=tick_label(x, xt), x=P.x(x), y=P.y(-1.5) + 40, size=28, color="#8a8fa3", align="center")
for y in yt:
    text(body=tick_label(y, yt), x=P.x(0) - 24, y=P.y(y), size=28, color="#8a8fa3", align="right")

f = lambda x: math.sin(x) * math.exp(-x / 10)
wave = path("wave", d=line_d(curve_points(f, 0, 4 * math.pi, 240), to=P, smooth=True),
            fill="none", stroke=True, strokeColor="#ffb547", strokeWidth=6, cap="round")
wave.key("trimEnd", {0.3: 0, 3.0: 1}, ease="easeInOut")                     # the curve draws on
shape("dot", shape="ellipse", w=26, h=26, fill="#ffffff", ridePath="wave", rideAt="end", x=0, y=0)   # rides its tip
```

- **Draw on:** key `trimEnd` 0 → 1 (`trimStart` takes it off again). **A dot riding the curve:** `ridePath` + `rideAt="end"`
  follows the drawn tip; `rideAt="along"` and keying `rideAlong` 0 → 1 moves it on its own clock. Its `x`, `y` become an
  offset from the path, so set them to 0. It shows from frame 0 at the curve's start; give it `start=` the draw-on's
  first key time (here `start=0.3`) if it should appear with the line.
- **Gaps:** `1/x`, `tan`, `log` break; `curve_points` leaves a `None` there and the line lifts. Pass `ylim=(lo, hi)` so a
  value shooting off to infinity becomes a gap instead of a near-vertical line.
- **Smooth or straight:** `smooth=True` bends through every sample (fewer samples look right); straight lines show the
  samples as corners, which is right for measured data.
- **Ticks:** `nice_ticks` stays inside the range; `extend=True` reaches past it so an axis ends on a round number
  (0 … 150 for data up to 128). `tick_label` gives each tick only the decimals its step needs.

## Typeset equations (fractions, sums, roots)

`math_text` typesets LaTeX-style maths into **ordinary path layers**: one path per symbol and per rule (a fraction bar and
a root's bar are paths too), held in a group. Nothing special to animate: key them, colour them, move them, draw them on. Write the formula as a raw string (`r"..."`) so `rac` keeps its backslash, and close every `\left` with a `
ight` and every `{` with a `}`: a piece typeset on its own (to highlight one term) must be balanced by itself, so cut the formula between terms, not inside a bracket pair.

```python
comp("eq", width=1920, height=1080, fps=30, duration=5, background="#0c0d12")
eq = math_text("fourier", r"f(x)=\frac{4}{\pi}\sum_{k=1}^{\infty}\frac{\sin((2k-1)x)}{2k-1}",
               x=240, y=380, size=110, color="#f4f1ea")      # x, y: the formula's top-left; size: font size in px

for i, part in enumerate(eq.parts):                           # reveal left to right
    part.key("opacity", {0.3 + i * 0.05: 0, 0.5 + i * 0.05: 1})
for part in eq.find("bar") + eq.find("sum"):                  # colour a kind of symbol
    part.set(fill="#ffb547")
for part in eq.span(6, 8):                                    # a term (parts 6 to 8 here: the 4 over pi), by its numbers
    part.key("fill", {3.0: "#f4f1ea", 3.4: "#5ec8ff"})

w = math_text("write", r"E=mc^2", x=240, y=800, size=140, fill="none", stroke=True, strokeColor="#f4f1ea", strokeWidth=3)
for i, part in enumerate(w.parts):                            # write-on: each symbol's outline draws, one after another
    part.key("trimEnd", {1.0 + i * 0.3: 0, 1.6 + i * 0.3: 1})
```

- **Input:** what LaTeX maths takes: `\frac{a}{b}`, `\sqrt{x}`, `\sqrt[3]{x}`, `\sum_{k=1}^{n}`, `\int`, `\pi \alpha \theta …`,
  `x^2`, `x_i`, `\pm \times \cdot \infty \leq \geq`, `\sin \cos \log`, `\left( … \right)`, `\mathrm{…}`. No `$` needed. A mistake
  (an open brace, a command it doesn't know) stops the script with the formula and what to fix.
- **Addressing a part:** every path has the id `<id>_<n>_<symbol>`, n counting from 1 in reading order (`fourier_5_equal`,
  `fourier_10_sum`, `fourier_15_bar`). From the returned group: `.parts` (all, in order), `.find("x")` (every x, "equal",
  "bar", "pi", "2" …), `.span(a, b)` (parts a to b, one term). Print the ids with `[p.id for p in eq.parts]`, or
  look at the layers list, to find the numbers of the term you want.
- **Reveal term by term:** key `opacity` 0 → 1 per part or per term (a term's parts get the same times, a short stagger
  per part reads as writing). **Highlight:** key `fill` on a term's parts; or `scale` 1 → 1.15 → 1 for a pop.
- **Write on:** give the paths `fill="none", stroke=True` and key `trimEnd` 0 → 1 per symbol; then key `fill` on and the
  stroke off (`strokeWidth` → 0) to let the letters fill in.
- **Move or morph:** each part is a path: key `x`, `y` to slide a term (the rest stays), or move the whole group. To turn one
  equation into another, fade matching symbols (same `find` name) and slide them to their new places.
- **Place it:** the group's box is the formula's size, so `eq.w`, `eq.h` give it; to centre on the comp,
  `x=(1920 - w) / 2` needs w first: make it once at x=0, read `eq.w`, and set `eq.x = 960` (the group's anchor is its centre).
- Outside a script the operation `math.add` (`tex`, `x`, `y`, `size`, `color`, `id`) makes the same group.

## Morphing one function into another

Key `d` with two curves. The engine pairs points one to one, so sample both with the **same `n` and the same `smooth`**:

```python
comp("shapes", width=1920, height=1080, fps=30, duration=4, background="#0c0d12")
P = plot_area(x=(-3, 3), y=(-1.2, 1.2), rect=(120, 240, 900, 600))
a = line_d(curve_points(lambda x: math.exp(-x * x), -3, 3, 120), to=P, smooth=True)
b = line_d(curve_points(lambda x: math.sin(2 * x) * 0.9, -3, 3, 120), to=P, smooth=True)
m = path("bell_to_wave", d=a, fill="none", stroke=True, strokeColor="#6cc4ff", strokeWidth=6)
m.key("d", {0.5: (a, "easeInOut"), 2.0: b})
```

A parameter sweep is the same: one key per value of the parameter (`{t: line_d(curve_points(lambda x: math.sin(k * x), …))}`
for k = 1, 2, 3 at 0, 1, 2 s). Gaps must fall in the same places in every key (the pieces pair in order).

## Parametric and polar curves

In the same comp:

```python
R = plot_area(x=(-1, 1), y=(-1, 1), rect=(1180, 140, 380, 380))
path("rose", d=line_d(polar_points(lambda a: math.cos(4 * a), n=720), to=R, smooth=True, closed=True),
     fill="none", stroke=True, strokeColor="#ff7aa8", strokeWidth=4)
L = plot_area(x=(-1, 1), y=(-1, 1), rect=(1180, 580, 380, 380))
liss = path("lissajous", d=line_d(param_points(lambda t: (math.sin(3 * t), math.sin(4 * t)), 0, 2 * math.pi, 600), to=L, smooth=True),
            fill="none", stroke=True, strokeColor="#b9f27c", strokeWidth=4)
liss.key("trimEnd", {0: 0, 3: 1}, ease="linear")
```

Give a square data range a square `rect`, or the curve stretches.

## 3D-looking plots

`view3d` turns (x, y, z) into the picture; `surface_lines` makes the wireframe of `z = f(x, y)`. To turn it, re-project
at several times and key `d` with `linear` eases (a key every 2-3 frames reads as a turn, not a blend):

```python
comp("surface", width=1920, height=1080, fps=30, duration=4, background="#0c0d12")
f = lambda x, y: math.sin(math.hypot(x, y) * 1.6) / (1 + 0.3 * math.hypot(x, y))
mesh = surface_lines(f, (-4, 4), (-4, 4), lines=24, steps=60)

def view(yaw):
    return lines_d(mesh, to=view3d(yaw=yaw, pitch=28, scale=105, center=(960, 600), distance=14))

s = path("mesh", d=view(20), fill="none", stroke=True, strokeColor="#7fd6c2", strokeWidth=2)
s.key("d", {i * 0.1: (view(20 + i * 3), "linear") for i in range(41)})
```

- `yaw` turns round the up axis, `pitch` looks down from above, `distance` (in data units) gives perspective; leave it
  out for a flat technical view. Any 3D points work the same way: `line_d([(x, y, z), …], to=V)` for a helix, an
  axis triad, a 3D curve.
- The wireframe is see-through (no hidden lines). For a solid look, colour the lines by depth as separate paths, or
  render the surface in Rostrum3D and bring it in (`3d-renders-in-2d`).

## A chart from a table

A table comes in as rows: pasted text with `parse_table`, or a file read by `inspect_table {path}` (CSV, TSV, JSON; the
reply has the rows and, for each number column, its min, max and round `ticks`), whose rows you paste into the script.

```python
rows = parse_table("""year,solar,wind
2019,42,61
2020,55,66
2021,71,74
2022,96,83
2023,128,90""")
comp("chart", width=1920, height=1080, fps=30, duration=5, background="#0c0d12")
yt = nice_ticks(0, max(r["solar"] for r in rows), 4, extend=True)
P = plot_area(x=(0, len(rows)), y=(0, yt[-1]), rect=(160, 160, 1000, 760))

for v in yt:
    shape(shape="rect", w=1000, h=2, x=P.x(0) + 500, y=P.y(v), fill="#2a2d38")
    text(body=tick_label(v, yt), x=P.x(0) - 20, y=P.y(v), size=26, color="#8a8fa3", align="right")
for i, r in enumerate(rows):
    at = 0.4 + i * 0.15
    bar = shape(f"bar{i}", shape="rect", w=120, h=P.y(0) - P.y(r["solar"]), x=P.x(i + 0.5), y=P.y(0),
                anchorY=1, fill="#ffb547", radius=6)                   # anchorY=1: grows up from the axis
    bar.key("scaleY", {at: (0, "easeOut"), at + 0.8: 1})
    n = text(f"n{i}", counter=True, count=0, start=at, x=P.x(i + 0.5), y=P.y(r["solar"]) - 34, size=34,
             color="#ffffff", align="center", figures="tabular lining")
    n.key("count", {at: (0, "easeOut"), at + 0.8: r["solar"]})                      # the number counts up
    n.key("y", {at: (P.y(0) - 34, "easeOut"), at + 0.8: P.y(r["solar"]) - 34})      # and rides the bar's top
    text(body=str(r["year"]), x=P.x(i + 0.5), y=P.y(0) + 36, size=28, color="#8a8fa3", align="center")

wind = path("wind", d=line_d([(i + 0.5, r["wind"]) for i, r in enumerate(rows)], to=P),
            fill="none", stroke=True, strokeColor="#6cc4ff", strokeWidth=5, join="round")
wind.key("trimEnd", {1.6: 0, 2.6: 1}, ease="easeInOut")

total, start = sum(r["solar"] for r in rows), 0
for i, r in enumerate(rows):                                         # a pie / donut: one arc per slice
    sweep = 360 * r["solar"] / total
    s = shape(f"slice{i}", shape="arc", w=440, h=440, x=1550, y=540, startAngle=start, sweep=0, hole=0.55,
              fill=["#ffb547", "#ff7aa8", "#6cc4ff", "#b9f27c", "#c49bff"][i])
    s.key("sweep", {2.6 + i * 0.12: (0, "easeOut"), 3.2 + i * 0.12: sweep})
    start += sweep
```

- **Bars grow** by keying `scaleY` (or `scaleX` with `anchorX=0` for horizontal bars) from 0; the bar's own `h` holds
  the value, so a person can still read and edit it. Stagger the start per row (`at = 0.4 + i * 0.15`), or use
  `layer.stagger` afterwards.
- **Counting numbers:** a text with `counter=True` shows its `count`; key it with the same times and ease as the bar.
  `start=at` keeps a "0" from sitting on every bar before its bar grows. `countDecimals`, `countPrefix`, `countSuffix`
  and `countSeparator` (`"comma"`, `"period"`, `"space"` or `"none"`) format it (`type-and-kinetic-text`); give the
  axis the same grouping with `tick_label(v, yt, separator=",")`.
- **Labels against lines:** a line chart drawn over bars crosses numbers that sit above the bars; put the numbers
  inside the bar tops (dark text) or the line behind the bars, and look at the last frame.
- **Pie and donut:** `shape="arc"`, `startAngle`, `sweep` (degrees; 0° is straight up, clockwise), `hole` 0-1
  (0 = a pie). Each slice starts where the last one ended; keying `sweep` from 0 grows it.
- **Line charts:** straight `line_d` through the data points, drawn on with `trimEnd`; a dot can ride it as above.

## One design → many videos from a table

Loop over the rows and make one composition per row in one script; every composition is its own video. Ids must be
different in each (put the row number in them).

```python
rows = parse_table("""city,temp,colour
Lisbon,24,#ffb547
Oslo,9,#6cc4ff
Cairo,35,#ff7a59""")
for i, r in enumerate(rows):
    comp(f"card_{i}", name=r["city"], width=1080, height=1080, fps=30, duration=3, background="#0c0d12")
    text(f"city_{i}", body=r["city"], size=120, weight=760, x=540, y=380, align="center", color="#ffffff")
    t = text(f"temp_{i}", counter=True, count=0, countSuffix="°", size=260, weight=800, x=540, y=640,
             align="center", color=r["colour"], figures="tabular lining")
    t.key("count", {0.3: (0, "easeOut"), 1.5: r["temp"]})
    bar = shape(f"bar_{i}", shape="rect", w=r["temp"] * 20, h=24, x=140, y=860, anchorX=0, fill=r["colour"], radius=12)
    bar.key("scaleX", {0.3: (0, "easeOut"), 1.5: 1})
```

Then check one or two (`look_frame {comp: "card_1", time: 2.5}`) and export each: `render_export {comp: "card_0",
format: "mp4", name: "Lisbon"}`, one call per row (each waits for its own file in the same call, `wait_s`; past it the reply gives the job to ask `inspect_job`). Re-running the script
with an edited table updates every card and keeps what a person moved by hand.

## Full Python: numpy, files, your own maths

When the maths wants numpy (a fit, a simulation, statistics) or the data is a file, compute in your own Python and
hand the result to the document as script text. The helpers work on numpy numbers too.

```python
import numpy as np
from rostrum2d.plot import plot_area, line_d
from rostrum2d.table import read_table

rows = read_table(r"C:\data\sales.csv")                     # CSV / TSV / JSON -> rows
y = np.array([r["sales"] for r in rows], float)
x = np.arange(len(y))
fit = np.polyfit(x, y, 2)
xs = np.linspace(0, len(y) - 1, 100)
P = plot_area(x=(0, len(y) - 1), y=(0, 300), rect=(160, 160, 1600, 760))
trend = line_d(zip(xs, np.polyval(fit, xs)), to=P, smooth=True)            # a plain string

source = f"""
comp("trend", width=1920, height=1080, fps=30, duration=3, background="#0c0d12")
dots = {[P(float(a), float(b)) for a, b in zip(x, y)]!r}
for i, (px, py) in enumerate(dots):
    shape(f"dot{{i}}", shape="ellipse", w=22, h=22, x=px, y=py, fill="#ffffff")
t = path("fit", d={trend!r}, fill="none", stroke=True, strokeColor="#ffb547", strokeWidth=5)
t.key("trimEnd", {{0.2: 0, 1.8: 1}}, ease="easeInOut")
"""
```

Send `source` to `run_script` (or save it as a `.py` file and pass its `path`). Python running beside the document can
also apply it directly: `doc.run_script("trend.py", run_source(source, "trend.py"))` (`from rostrum2d import run_source`).
Only numbers and strings cross over, so the document never depends on numpy.

## Check your work

- `look_frame` at the end of the draw-on and half way through a morph or a turn (`what: "sheet"` over the stretch).
- `look_motion` lists every `trimEnd`, `count` and `scaleY` move with its start, landing and ease.
- A full-size still: `render_export {comp, format: "png", time: 2.5, path: "<a new folder>"}`. PNG output is always a
  folder of numbered pictures (here one), so `path` names a folder that doesn't exist yet, not a `.png` file.
- A key on `d` with a different number of pieces is refused, naming the two key times: sample both the same way.
