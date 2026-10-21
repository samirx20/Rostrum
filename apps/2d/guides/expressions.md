# Expressions: one field driven by a formula or by another item

Use this when a field should follow something instead of being keyed by hand: a shadow that stays under a logo, a
wobble that never ends, a bar that is always half as wide as another. For a hand-made move, use keys
(`easing-and-overlap.md`).

## Two ways, one engine

- **Bind** a field to another item's field: value = other · scale + offset.
  `link.set {target: "shadow", prop: "x", of: "logo", field: "x", scale: 1, offset: 12}`
  Script: `shadow.link("x", of="logo", field="x", offset=12)`.
- **Write an expression**: `expr.set {target: "title", prop: "rotation", source: "sin(time * 2) * 6"}`.
  Script: `title.expr("rotation", "sin(time * 2) * 6")`.

A bind is only an expression written for you (`logo.x + 12`); the inspector shows it as one. `expr.clear {prop}` takes
either off. The field's own value and keys are **ignored while an expression is on it** (they come back when it is
cleared); the inspector says "overrides its keys".

## What you can write

| | |
|---|---|
| numbers, `#rrggbb` colours | `12`, `0.5`, `#ff7a59` |
| names | `time` (s), `frame`, `fps`, `duration`, `pi`, `e`, `true`, `false` |
| other items' fields, now | `logo.x` or `ref("my-logo.x")` (quoted ids may hold `-`) |
| other items' fields, shifted | `ref("logo.x", time - 0.2)`: the logo's x a fifth of a second ago |
| calculate | `+ - * / %`, `^` or `**` (`-2^2` is -4), brackets |
| compare, choose | `< <= > >= == !=` (give 1 or 0), `and or not`, `a if c else b` |
| functions | `sin cos` (radians) `abs sqrt floor ceil round min max clamp(x, lo, hi) lerp(a, b, p) noise(x[, seed])` |

`lerp` also blends two colours: `lerp(#ff0000, #0000ff, time / duration)` on a colour field. `noise` is smooth value
noise between -1 and 1, the same numbers on every machine; the formula is in `expr.py`'s header and `expr_lib.py`.
Anything else (a function that isn't listed, `x.y.z` that isn't an item's field, attribute tricks, text) is refused
with the item, the field and the **column** where it went wrong.

## Techniques

- **Follow with a delay (overlap):** `ref("leader.x", time - 0.15) + 40`. Several followers, each with a longer delay,
  give a trail.
- **A loop of motion:** `540 + sin(time * 2 * pi / 3) * 30` (period 3 s). `time % 3` is a ramp that restarts every 3 s.
- **Hand-held feel:** `noise(time * 2, 1) * 6` on x and `noise(time * 2, 2) * 6` on y: different seeds so they don't move
  together.
- **Stay on screen:** `clamp(logo.x, 100, 1180)`.
- **Switch at a moment:** `1 if time >= 1.5 else 0` (use `frame >= 45` to count frames).
- **Match sizes:** `link.set` with `scale` (a bar's width = 0.4 × another item's width).
- **Colour from another item:** bind `fill` to the other item's `fill`; to fade between colours use `lerp`.

## Rules that save time

- An expression sees other items **at the same moment** (or shifted with `ref(…, time - d)`), including fields that
  have keys or expressions of their own.
- **A loop is refused**: `a.x` reading `b.x` which reads `a.x` (even with a time shift). Say which one leads.
- Results are held inside the field's range, as a key would be (opacity stays 0..1); a colour field needs a colour
  result, a number field a number.
- `marker("name")` is not available yet: 2D documents keep no markers. Use `time` with a number for now.
- Check the result by looking: scrub the playhead, or `look` frames at a few times. The bake is the same on canvas and
  in the export (one key per frame).
- Dragging a layer on the canvas does not move a field an expression drives; clear the expression first.
