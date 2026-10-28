# Tap and react

How a cursor presses something on a product screen and how the screen answers, with `pointer()` and `tap()`. The
tools only; what the screen does and how long it takes is yours. Read `ui-and-product-animation` ("A pointer and taps")
for making the pointer.

## One call aims, follows and reacts

`tap(cur, target, at=2.0)` glides the tip to the **centre** of `target`, lands at `at` (seconds or a marker, `"#pay"`),
and presses: the target dips and a ring spreads under the tip. Nothing to time by hand: the reaction starts on the
landing frame.

```python
cur = pointer()
tap(cur, pay, at="#pay")                                  # centre, press + ripple
tap(cur, pay, at=4, then=[("highlight", "#16a34a"), "ripple"])    # the button turns green and stays green
tap(cur, card, at=6, then=lambda t: card.key("shiftY", {t: 0, t + 0.4: -30}, ease="easeOut"))   # your own answer
```

## Where the tip lands

- Default: the target's centre.
- `spot=(fx, fy)`: a share of the target's box (`(0.9, 0.5)` is the right edge, in the middle).
- `spot="beside"`: clear of the target's words (right of a button's label, lower right of a card), for when the tip must
  not cover them.

## When the target moves

If the target moves while the pointer travels (its own keys, or a sheet or screen it sits in that slides), the tip chases
it and arrives on the target **where it is at `at`**. Nothing to change in the call. `hold=0.8` keeps the tip on the
target for that many seconds after the landing, for a button that keeps sliding, a card that is dragged or a list that
scrolls under a finger. A target that stands still gets two eased keys; a moving one gets a key every 1/15 s, so the
glide stays smooth. Don't tap something that is still off screen: key its arrival first, then tap it.

## What reacts: `then=`

One reaction or a list. Without `then=` it is `["press", "ripple"]`.

| reaction | what it does |
|---|---|
| `"press"` | the target scales down and back around its centre (`press=0.9` for deeper; `press=False` to drop it) |
| `"ripple"` | a ring spreads under the tip (`ripple=False` to drop it, `ripple_color=` to colour it) |
| `"highlight"` / `("highlight", "#hex")` | the target's first filled shape (a button's `<id>_bg`) takes the colour in 0.15 s and stays; default the pointer's outline colour |
| a function | `lambda t: ...` is called with the landing time; key anything at `t`: open a sheet, flip a toggle, count a number, ring a sound cue |

`then=` replaces the default list, so `then="highlight"` gives a highlight and neither press nor ripple. An unknown
name fails and lists the accepted ones. A highlight needs a filled shape: an outline button or a text has none (the
error says so); colour it in your own function instead.

## Habits that read well

- The pointer is a layer: key its `opacity` in and out inside the screen, and keep it in the screen you tap.
- The reaction belongs to the landing frame, not to the glide: key anything that answers the tap at `t`, never earlier.
- Several taps on one pointer chain on their own: each starts where the last ended, so taps closer than `move` seconds
  just glide faster.
- `tap` returns the pointer; the landing time is the `at` you gave (the function in `then=` receives it).
