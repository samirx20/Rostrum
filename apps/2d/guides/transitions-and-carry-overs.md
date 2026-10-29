# Transitions and carry-overs

Two script calls that link one section of a film to the next. Both only write ordinary things: keys, masks, blur
effects, a layer's Starts at / Ends at, and its place in the stacking order. After the run they are plain keys you can
see, key further and change by hand, like any other key. Nothing is chosen for you beyond what the call says.

A **section** is a group (or any layer) the script made: usually one group per shot, sized to the frame
(`with group("intro", w=1920, h=1080): …`). Make both sections first, then call `transition()` / `carry()`.

## `transition(kind, at=, dur=, out_of=, into=, ease=, …)`

```python
transition("push", at=4, dur=0.6, out_of=intro, into=features, direction="up", ease="easeInOut")
transition("wipe", at="#chapter2", dur=0.8, out_of="intro", into="features", softness=120)
```

What every kind writes:

- `out_of` gets **Ends at = at + dur** (a cut: `at`); `into` gets **Starts at = at**.
- `into` is moved to sit **directly above** `out_of` when both are in the same parent and it was below. In different
  parents the order stays as made.
- Keys go at `at` and `at + dur` with `ease` (any key ease; default `"smooth"`). The value at `at` is what the field
  is then (its keys read at that moment); the value at `at + dur` is what `into` is then. Keys you wrote yourself
  inside that window stay and still count.
- Distances are the **frame's view at `at`**: its width and height in scene px (at Zoom 1: the scene's size), divided
  by the scale of the groups the section sits in.

`out_of` / `into`: the handle `group(…)` gave, or its id. `at`: seconds or a marker time (`"#name+0.5"`). `dur`:
seconds, 0 or more.

| kind | parameters (default) | what it writes |
|---|---|---|
| `"cut"` | none | only Ends at / Starts at, both at `at` (`dur` is ignored) |
| `"fade"` | `hold_out` (False) | `into` opacity 0 → its own; `out_of` opacity its own → 0 (with `hold_out=True` `out_of` keeps its opacity and only `into` fades in over it). Halfway, both are partly see-through: what is under both shows. |
| `"push"` | `direction` ("left") | both keyed on x (left / right) or y (up / down): `out_of` from its place to one view width/height that way, `into` from one view the other side to its place |
| `"slide"` | `direction` ("left") | as push, but only `into` moves; `out_of` stays put under it |
| `"wipe"` | `direction` ("left"), `softness` (0 px) | a rect mask `<into>_wipe` on `into` covering the frame's view; its `w` (left / right) or `h` (up / down) keyed 0 → the view, and for left / up its `x` / `y` too, so the edge travels that way. `softness` is the mask's Feather; the mask is that much bigger on each side so the soft edge clears the frame at both ends |
| `"iris"` | `x`, `y` (the view's centre, scene px), `softness` (0) | an ellipse mask `<into>_iris` on `into`, from a point at (x, y) to a circle reaching the view's farthest corner (+ softness); keys on its x, y, w, h |
| `"zoom"` | `out_scale` (1.6), `in_scale` (0.6) | `out_of` scale × 1 → × out_scale and opacity → 0; `into` scale × in_scale → × 1 and opacity 0 → its own. Each scales around its own anchor (move it with `item.pivot(x, y)`) |
| `"blur"` | `radius` (40 px) | a blur effect `<out_of>_out_blur` keyed 0 → radius and opacity → 0 on `out_of`; `<into>_in_blur` keyed radius → 0 and opacity 0 → its own on `into` |

`direction` is the way the motion goes: `"left"`, `"right"`, `"up"`, `"down"`.

A wrong kind, a parameter the kind doesn't take, or a wrong direction fails with a plain error naming what is
accepted. Two transitions that make the same mask or effect id (`<into>_wipe` twice) fail as a doubled id; a section
takes one wipe-in and one iris-in.

Masks are in the section's own px and the frame's rotation is left out; a section the frame looks at turned, or a
group with tilt, needs its own mask keys.

## `carry(layer, into=, at=, dur=, to=dict(…), ease=, id=)`

A layer that lives on past its section's end and moves into the next one: it shrinks into a corner, travels through,
or grows to fill the frame.

```python
carry(logo, into=features, at=4, dur=0.8, to=dict(x=160, y=120, scale=0.4))
carry("dot", into="outro", at=9, dur=0.5, to=dict(scale=40))        # grows over the frame
```

What it writes, for a layer inside a group (a section):

- The layer itself gets **Ends at = at**: it is gone from its section from `at`.
- A **copy** of it (id `"<layer>_carry"`, or `id=`) is made **in the scene itself** (not in any group), with
  **Starts at = at** and the original's Ends at. Inside the copy every id is `"<copy id>_<old id>"`.
- The copy starts **where the layer showed at `at`**: its x, y, scale, rotation and opacity are the layer's combined
  with every group it was in (their x, y, anchor, scale, Stretch, rotation, opacity at `at`). Its own keys on those
  fields and on the fields in `to` are dropped; its other keys (colour, a mask …) stay.
- Each field in `to` is keyed from its value at `at` to the value given at `at + dur`, with `ease`. Values are in
  **scene px** (the scene's own coordinates). Any animatable field of that kind of layer may be in `to` (`w`, `h`,
  `color`, `radius` …).
- The copy is drawn directly above `into`'s top-level section (left out: on top of the scene).
- It returns the copy, to key further: `carry(…).key("rotation", {…})`.

A layer that already sits in the scene (not in a group) isn't copied: it only gets the `to` keys.

## Re-running

Both calls write the same ids every run (keys by field and time, `<into>_wipe`, `<layer>_carry` …), so re-running the
script under the same name gives the same document; nothing doubles. Removing the call and re-running removes what
it wrote.
