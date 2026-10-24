# Easing and overlap: what each ease does and how to check overlap

A key's `ease` shapes the stretch that starts at that key. Same distance, same time, different feel. These describe the
curves, not what to choose; choose by what the move must say, then check by looking.

| Ease | What the value does |
|---|---|
| `linear` | Constant speed. Starts and stops abruptly. Right for things that never really start or stop: a continuous drift, a spinner, a scrub. |
| `hold` | Does not travel: stays at this key's value and jumps at the next key. A cut. |
| `smooth` | Gentle start, longer settle (CSS `ease`). A safe default for small changes. |
| `natural` | Gentle at both ends, a little more weight in the middle. Calm, even movements. |
| `easeIn` | Starts slow, ends at full speed. The value leaves; nothing slows it at the end. Used for things leaving the frame. |
| `easeOut` | Starts at full speed, slows into the end. Things arriving and settling. |
| `easeInOut` | Symmetrical slow-fast-slow. Things travelling between two resting places. |
| `snappy` | Almost all the travel happens in the first part, then a long soft settle. Reads as quick but not rough. |
| `heavy` | Like `snappy`, with an even longer, softer landing. The last part crawls. |
| `spring` | Overshoots the target and settles. Two words control it: `bounce` (0 none – 1 a lot) and `speed` (0 slow – 1 fast); the Key block's sliders are the same two. Experts may write `stiffness` and `damping` instead (bounce 0.6, speed 0.5 is stiffness 170, damping 12). The 0–1 of the stretch is read as one second, so a short stretch squeezes the wobble. |
| `bounce` | Falls onto the target and rebounds. Ends exactly on the value. |
| `custom` | Your own curve: `x1 y1 x2 y2` (x 0–1; y may go below 0 or above 1 to overshoot). |

`look_motion` reports `overshoot` for a move whose curve goes past its landing value, so you can see how far a spring
or custom curve really goes.

**Move length matters as much as the ease.** The same ease over 0.2 s and over 1.2 s reads very differently. `look_motion`
gives each move's start, end and peak rate (units per second); compare the peak rates of moves that should feel related.

## Overlap

Two entrances **overlap** when the second starts before the first has finished. Staggering them (each starts a little after
the last) is one way to get a read order; starting them all together is another. Neither is wrong: decide it, then check
that the file says what you decided.

- `look_motion` lists every pair of entrances that overlap with the overlap in seconds, and whether they start together.
  A stagger you meant as "one after another" that shows a large overlap, or a "together" that shows an offset, is a script
  mistake you can read without rendering.
- `layer.stagger {ids, by, order}` spreads layers so each starts `by` seconds after the one before, counting from the
  earliest start among them, in an order: `stack`, `picked`, `left_to_right`, `top_to_bottom`, `centre` (equal
  distances start together) or `random` (the same every time). Calling it again re-spreads them, so the rhythm is one
  number. In the screen: **Stagger…** at the top of the settings panel.
- A stagger in a script is easiest to keep consistent with a loop: the start time is `base + i * step`, so changing
  `step` changes the whole rhythm in one place.
- `look_sheet` over just the entrance window (`start`, `end`) shows what the overlap looks like.

## Checking an ease choice

1. `look_motion layers: [id]`: peak speed, where it peaks, overshoot, how long the move is.
2. `look_sheet` across the move (`start`/`end` = the move, `count` 8–12): the spacing between where things are from frame to
   frame is the ease. Bunched early tiles, wide-open later ones: slow-fast. The reverse: fast-slow.
3. `look_frame` on the landing frame and one frame after: the layer should be where you meant, and not still moving unless
   you meant it to.

## Retiming keys without re-keying

- `key.add {fields: "pose", t}` keys position, scale, rotation and opacity at once with their values now (K in the screen).
- `key.scale {around, by}` on keys stretches (`by` 2: twice as slow) or squeezes (0.5) them in time around a moment.
- `key.paste {from: [key ids], at}` on layers puts copies of those keys on the same settings, the first at `at`, the
  others keeping their spacing, values and eases.
- `key.set {ease}` on many keys at once changes them in one step; `key.handles` shapes a custom curve.

## Bending the path a layer travels

The ease decides how fast a layer goes; spatial handles decide which way. `key.path_handles {t, out: [dx, dy], in: [dx, dy]}`
on a layer or the frame bends the path at its position key at `t` (it needs an x and a y key there): `out` is the handle
leaving that key, `in` the one arriving at it, in px from the key's place; `null` removes one (a straight line again
when both ends of a stretch have none). Give the x and y keys the same ease for a true curve. The speed along the
curve follows the ease, not the distance. `look_path {layer}` reads the path back: per sample its own x / y and where it
is seen on screen, the keys with their handles, the path's length and its peak speed.
