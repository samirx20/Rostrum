# Lower thirds and charts

Two script calls that make plain, editable layers: `lower_third` (a name and a role on a bar) and `chart` (bars or a
line with a y axis, gridlines and labels). Like the other screen blocks (`ui-and-product-animation`, "Building
blocks") they are groups of shapes and texts with ids made from the block's id, so you restyle, key or take them
apart like anything you made by hand. Every size and colour is a parameter; the defaults are a neutral start.

## Placing them

- **At the top level** a lower third sits in the picture's lower-left title-safe area: its bottom-left 8 % of the
  width in and 10 % of the height up. `x=` / `y=` move that corner. A chart there needs `x=` / `y=` (its top-left).
- **Inside a container** (a device's screen, a `column`, a `stack`, a card's body) the container places it; `x` / `y`
  then need `apart=True` (guide `lay-out-a-screen`). A lower third hugs its words (`align_self="start"`; pass another
  `align_self=`, `margin=` to move it). A chart fills the container's width.
- In a `row` next to other layers, give a chart its own `w=`: its sizes are worked out from the room it is made in.

## Sizes and colours

- Sizes come from the room the block is made in, so one call reads right in a phone, a laptop screen or a whole
  1920 x 1080 frame: a top-level lower third's name is 4.6 % of the picture's height; a chart's labels grow with its
  width, more slowly (about 13 px in a phone, 19 on a laptop screen, 31 across a full frame), its default height is the smaller of 55 % of its width and half the room's height.
  `size=` (and `role_size=`, `h=`, `radius=`, `width=` for the line, `pad=` for the bar) set them yourself.
- Colours follow what the block sits on. A lower third's bar takes the ground's ink (dark on a light screen, light
  on a dark picture) and its words the other way: `bar`, `color` (name), `muted` (role), `accent` (a strip on the
  bar's left, none by default). Chart: `color` (bars or
  line), `ink` (title), `muted` (tick and x labels, unit), `line` (gridlines).

## The axis

`chart(values, labels=, kind="bar" | "line", title=, unit=, ticks=4, top=)` runs its y axis from 0 to a round
number at or above the biggest value (`nice_ticks(0, max, ticks, extend=True)`, steps of 1, 2 or 5 x a power of ten),
or to `top=` when several charts must share one scale. Values are 0 or more. Bars stand on the bottom gridline;
`gap=` is the share of each slot left empty. For axes from negative numbers, a log scale or several series, build the
chart from `plot_area`, `nice_ticks` and `line_d` (`data-math-and-graphs`, "A chart from a table").

## Timing

`at=` takes seconds or a marker time (`"#stats+0.3"`, `marker("stats", 2) + 0.3`): the keys stay on the marker, so
dragging the marker moves them.

- `lower_third(..., at=, out=, enter="left", slide=, duration=0.5, ease="easeOut")`: an opacity key and a slide from
  the `enter` side (`left`, `right`, `below`, `above`, or `none` for only a fade); `out=` plays the same back. At the
  top level it keys `x` / `y`; inside a container `shiftX` / `shiftY`, so the layout keeps its place.
- `chart(..., at=, duration=0.8, stagger=0.06)`: each bar's `scaleY` from 0 (they grow from the floor), `stagger`
  seconds apart; a line's `trimEnd` from 0 to 1, each dot popping in as the line reaches it.

Without `at=` both are still. For any other motion, key the parts yourself.

## Taking them apart

```python
lt = lower_third("Ana Ruiz", role="Host", at="#intro")
layer("lower_third_name").set(color="#fde68a")          # one part restyled
c = chart([12, 30, 18], labels=["Q1", "Q2", "Q3"], title="Visits", unit="k", id="visits")
layer("visits_bar2").set(fill="#f97316")                # one bar picked out
for i, bar in enumerate(c):                              # the bars, left first (.group is the chart)
    bar.key("scaleY", {1 + i * 0.2: (0, "easeOut"), 1.6 + i * 0.2: 1})
```

Part ids: lower third `<id>` (the bar), `<id>_name`, `<id>_role`, with an accent `<id>_accent` and `<id>_words`.
Chart `<id>_title`, `<id>_unit`, `<id>_y0` … (tick labels, 0 first), `<id>_grid0` …, `<id>_bar0` … or `<id>_line`
and `<id>_dot0` …, `<id>_label0` … (x labels).

Look at the result with `run_script` and `look`: the last frame shows whether a long name or label fits.
