# Lay out a screen

Arrange things the way a web page or a React app does: **boxes inside boxes**, each with padding, a gap between its
layers and an alignment. The box places and sizes what is made inside it, so you never add up x / y. Texts are
measured by the engine that draws them, so they wrap and fit where the box says. Read `start-here` first.

## The four containers

```python
with column("menu", padding=24, gap=16, w=520):       # h left out: it fits what is inside
    text(body="Trips", size=32, weight=700)
    with row(gap=12, align="center"):
        shape(w=40, h=40, radius=20, fill="#4f46e5")
        text(body="Lisbon dinner for two", size=18, grow=1)
```

- `row(id, …)` lays its layers left to right, `column` top to bottom, `grid(columns=3)` in cells, `stack` on top of
  each other (a label centred on a pill, a title in a card's corner). Each is a group with a `layout`, so
  `layer("menu")` keys, moves and restyles it like any group, and the settings panel shows the same fields.
- The box's words: `padding` (`padding_x`, `padding_y` for one axis), `gap` (`row_gap` between wrapped lines or grid
  rows), `justify` along the line (`start`, `center`, `end`, `between`, `around`, `evenly`), `align` across it
  (`start`, `center`, `end`, `stretch`, `baseline`), `wrap=True`, `columns=3` or `columns="1fr 2fr 200px"`,
  `bg="#hex"` and `radius` (its own background), `overflow="hidden"` (cut what runs past its edge; visible at first).
- **Which way `justify` and `align` act**, as CSS flexbox, always inside the padding:

  | box | `justify` moves its layers | `align` moves its layers |
  |---|---|---|
  | `row` | left ↔ right (`start` = left) | top ↕ bottom (`start` = top) |
  | `column` | top ↕ bottom (`start` = top) | left ↔ right (`start` = left) |
  | `stack` | left ↔ right, as a row (`start`, `center`, `end`) | top ↕ bottom, as a row |

  So a title in a card's bottom-left corner is `stack(…, justify="start", align="end")`; top-right is
  `justify="end", align="start"`; dead centre is `justify="center", align="center"`. A box's `align` starts at
  `stretch`: a text stretched down its box keeps its lines at the top, so it looks the same as `align="start"`.
  A layer is placed by its whole box (a text by its measured lines), whatever its anchor.
- Sizes, on a box and on a shape or image: `w=` / `h=` take px (`320`), a share of the parent box (`"50%"`), `"fill"`
  (the room the parent leaves) or, on a box, `"fit"` (hug what is inside; the default).
- **Leave a box's or a card's `h` out** unless the design needs that exact height: left out, it grows to fit its words,
  as a web page's box does. A fixed `h` (or `w`) too small for its words lets them run out past its edge, under the next
  block; the look names it (`text_spill`) with the h that fits: make it taller, or leave `h` out.
- Words a layer takes inside a box: `grow=1` (takes the room left along the line), `shrink=0` (never squeezed),
  `align_self=`, `margin=`, `span=2` (grid columns), `shift_x=` / `shift_y=` (moved off its place without pushing the
  others; key `shiftX` / `shiftY` for a slide-in).
- A text in a box reads from its slot's left edge (`align="left"`) and wraps at the slot's width; give `align="center"`
  or `"right"` for another.
- **x and y inside a box:** the box places the layer, so `x=` / `y=` there fail loudly. Add `apart=True` to the
  call to place a layer by hand at its own x / y (`shape("badge", x=300, y=-10, w=24, h=24, apart=True)`; it then takes
  no room): a badge on a card, a pointer over a screen. Or leave x / y out and let the box place it. A box made outside any
  box is placed by its `x`, `y` (its top-left); with no `x`, `y` it sits centred in its parent (the frame's middle).
- `anchor="center"` (or `"top-left"`, `"top"`, `"left"`, `"bottom-center"` … any corner or side, or a pair `(0, 1)`;
  `origin=` is the same word) on any layer is the point its `x`, `y` place and its pivot for scale and turn:
  `anchor="bottom"` grows a bar up from its floor. A laid-out layer still sits in its
  slot.
- `tw="flex flex-col gap-4 p-6 items-center"`: Tailwind layout words on any box or layer, on Tailwind's 4 px scale
  (`gap-4` = 16 px). Read: `flex`, `flex-row` / `flex-col`, `grid`, `grid-cols-N`, `flex-wrap`, `gap-N`, `gap-x-N`,
  `gap-y-N`, `p-N`, `px-N`, `py-N`, `m-N`, `items-*`, `justify-*`, `self-*`, `grow`, `shrink-0`, `w-` / `h-` (`full`,
  `fit`, `1/2`, `N`, `[320px]`), `col-span-N`, `rounded-*`, `bg-[#hex]`, `overflow-hidden`, `absolute`. Any other word
  fails, naming it; an argument you also write wins over a word.

## A phone app screen

```python
scr = device("phone", screen="#ffffff")       # its screen is a column filling the screen, layers stretched across
with scr:
    status_bar(); nav_bar("Trips", action="New")
    with column("feed", padding=20, gap=14):  # the content gets its own padding
        card("hero", h=170, title="Lisbon dinner", value="$168.00")
        list_rows([("Porto", "3 people", "$412.50"), ("Taxi", "2 people", "$24.50")])
        button("Request")
    tab_bar(["Home", "Trips", "You"])         # pinned to the bottom: a spacer made before it takes the room left
```

The screen has no colour of its own unless you give `screen=`: left out, the device's body shows. The blocks' starting
colours follow what they sit on (dark words on a light screen, light words on a dark one or on the body); `color=` /
`fill=` set your own. Content taller than the screen shows past its
edge (so you see it and fix it); `device(..., overflow="hidden")` cuts it at the rounded edge.

## A row of cards

```python
with row("plans", x=160, y=300, w=1600, gap=32, align="stretch"):
    for name in ("Free", "Team", "Business"):
        with column(f"plan_{name}", grow=1, padding=32, gap=12, bg="#111827", radius=24):
            text(body=name, size=40, weight=700, color="#ffffff")
            text(body="Everything in one place, for everyone you work with.", size=22, color="#9ca3af")
```

`grow=1` on each makes them share the row equally; `align="stretch"` gives them one height, the tallest's. A long
line wraps inside its card.

## A title lock-up

```python
with column("lockup", anchor="center", align="center", gap=18):
    with row(gap=20, align="center"):
        shape(w=72, h=72, radius=18, fill="#ff7a59")
        text(body="Rostrum", size=120, weight=780)
    text(body="Films from a script", size=36, color="#9ca3af")
```

With no `x`, `y` the lock-up's middle (`anchor="center"`) sits at the picture's centre whatever its size, and it grows
around it.

## A dashboard

```python
with grid("kpis", x=120, y=120, w=1680, columns=4, gap=24):
    for label, value in (("Users", "12,480"), ("Revenue", "$84k"), ("Churn", "2.1%"), ("NPS", "61")):
        with column(padding=24, gap=8, bg="#0f172a", radius=20):
            text(body=label, size=22, color="#94a3b8")
            counter(f"kpi_{label}", 0, 100, at=0.5, duration=1.2, size=56, weight=760, color="#ffffff")
    with column("trend", span=4, padding=24, bg="#0f172a", radius=20):
        bars([4, 7, 5, 9, 12, 10], h=260, labels=["M", "T", "W", "T", "F", "S"])
```

`span=4` lets the chart take the whole grid row. Animate a laid-out layer with `scale`, `opacity`, `shiftX` or
`shiftY` (they don't push the others); key its `w` / `h` and the others move to make room.

A layer outside its `start`..`end` takes no room in its row, column or grid: the row re-flows as layers come and go.
For cards that arrive one by one without re-flow, show them from the start and key `opacity` or `scale` from 0 (these,
and `shiftX` / `shiftY`, keep their slot), or put them in a `stack`. `hidden=True` frees a slot and `apart=True` takes
the layer out of the flow. The checks note a layer its layout jumps in one frame with no key moving it (`layout_jump`).

Check what the layout did with `look_frame` `what: "layout"` (each layer's place and size at a time) and `look_frame`.
