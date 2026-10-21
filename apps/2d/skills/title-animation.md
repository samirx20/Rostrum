# Building a title animation with the script API

Techniques, one at a time. These fragments show how the API is used; the words, sizes, times and eases are placeholders for
your own decisions. Read `start-here` first; ease behaviour is in `easing-and-overlap`.

## 1. Stage it before you animate it

Decide, in order: what is on screen first, what the eye should land on, what supports it, how long each stays. Write this as a
list of times (`# 0.0 bg in; 0.3 headline lands; 1.4 subtitle; hold to 3.2`) at the top of the script, then write keys to
match. Then compose the **final frame first**: place every layer where it ends up, with its final values, and look at that
(`look_frame` at the last second). Animation is how it gets there; if the end state is wrong, easing won't fix it.

```python
comp("main", width=1920, height=1080, fps=30, duration=4, background="#0b0b10")
head = text("headline", body="…", size=180, weight=700, x=960, y=500)    # final position
sub = text("subtitle", body="…", size=48, x=960, y=660)
```

## 2. Entrances: pick what moves and from where

An entrance is a field going from "not there" to its final value: `opacity` 0 → 1, a position offset to its place, `scale` from
small, a mask opening, a gradient moving. Animate **toward the final value you already placed**: copy it as the last key.

```python
head.key("opacity", {0.3: 0, 0.8: 1}, ease="easeOut")
head.key("y", {0.3: 540, 0.9: 500}, ease="snappy")          # 40 px below its place, travelling up into it
```

Different fields on one layer can have different times and eases: a quick fade with a longer travel is two keys per field.
Keys of one field are written as `{time: value}`; `{time: (value, ease)}` changes the ease per key.

## 3. Reveal with a mask instead of a fade

A mask is the part of the layer that shows, in the layer's own pixels from its top-left. Animate its width or position:

```python
head.mask("reveal", x=0, y=0, w=0, h=300).key("w", {0.3: 0, 1.0: 1400})
```

Check the layer's own box size with `look_at` at a time when it is visible (it reports the approximate box).

## 4. Per-word entrances: one layer per word, one loop

For staggered type, make a text layer per word and drive start times from the loop index. Positions come from your layout
decision; compute them, don't eyeball.

```python
words = ["one", "two", "three"]
for i, w in enumerate(words):
    t = text(f"word_{i}", body=w, size=140, x=480 + i * 480, y=540)    # explicit ids so a re-run finds them
    t.key("opacity", {0.3 + i * 0.12: 0, 0.7 + i * 0.12: 1}, ease="easeOut")
```

The step (`0.12`) against the move length (`0.4`) decides how much the words overlap. `look_motion` prints the overlap.

## 5. Exits and holds

- A hold is time where nothing animates. It is how long the viewer gets to read. `look_motion` reports "Nothing moves from X to Y"
  for such stretches; check it is as long as the text needs, and that a hold at the very end is intended.
- An exit is an entrance run backwards. Pair it with an ease that starts slow and ends fast (`easeIn`) if leaving should
  accelerate away.
- A layer that has finished its exit but still sits at `opacity` 0 is fine. A layer whose opacity ends at 1 but is positioned
  off the frame is "not on screen at the end" in `look_motion`: that finding tells you which.

## 6. Type that changes while it is on screen

Text fields `size`, `weight`, `tracking`, `stretch` (variable-font width) are animatable numbers; `color` is an animatable
colour. A weight change from light to bold over 0.8 s on a held headline is a single `key("weight", {…})`. Effects have keys
too: `head.effect("glow", id="halo", radius=0).key("radius", {1.0: 0, 1.6: 60})` (the key belongs to the effect; `look_motion`
names it `halo.radius`).

## 7. The check loop (every pass)

1. `run_script` (same `name` every time so it merges, and with explicit ids).
2. `look_motion`: read the moves; fix findings that are mistakes (entrances overlap that you meant to be sequential, keys that do
   nothing, layers not on screen at the end).
3. `look_sheet` over the whole thing: is the order right? Is the end frame right?
4. `look_frame` at the landing times and at a hold: type crisp and where you placed it? Anything cut off or crowded?
5. `look_at` on any point you doubt: which layers are there and in what order?
6. Only then `render_video`.

If a person has moved something, your re-run reports it as held back. Leave it unless they asked you to put it back.
