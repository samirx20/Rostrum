# Markup films: HTML + SVG + CSS, keyed

You write the picture in the web's own language — inline `<svg>` (paths, gradients, filters, masks, clip paths,
`<text>`), HTML boxes with CSS (flexbox, grid, gradients, shadows, `border-radius`, `clip-path`, fonts) — from a
Python script. Python is the host: loops, helpers, maths, data. Rostrum then adds what the web lacks: **keys on any
attribute or CSS value**, a **camera**, **light on shapes**, **true motion blur**, **lip sync** to RostrumSound voices,
and the project's **music and markers**. What you write is what the engine draws; looks and the export draw the
same frames.

## The loop

1. `run_film {"name": "piece", "code": "<the whole script>"}` → a contact sheet of 8 frames.
2. `look_film {"name": "piece", "at": [3.2]}` → that frame at full size (about 0.1–0.3 s a frame). Look at the
   moments that matter as a client would: is anything cut off, empty, unreadable, stiff, off-model?
3. Change the script, `run_film` again with the same name (the whole script each time; omit `code` to re-run).
4. `render_film {"name": "piece", "file": "C:\\…\\piece.mp4"}` → the MP4, with the project's sound under it.
5. Review the whole film once more: `look_film {"name": "piece", "every": 2}` (a frame every 2 s), fix what you see,
   render again. Most of a film's quality is won in this pass.

## A script

```python
film = Film(1920, 1080, fps=30, duration=30, background="#101318")
film.css("""
  .title { position: absolute; left: 140px; top: 760px; font: 700 120px Fraunces; color: #f4ecdc; letter-spacing: -3px; }
""")

def scene(t):                       # the world at time t: return markup (a string)
    sway = wave(t, period=3, amount=4)
    return f'''
    <svg width="1920" height="1080" style="position:absolute; left:0; top:0">
      <defs>
        <radialGradient id="skin" cx=".4" cy=".35" r=".8"><stop offset="0" stop-color="#ffd2ad"/><stop offset="1" stop-color="#e09a72"/></radialGradient>
      </defs>
      <g id="head" transform="translate(960 420) rotate({sway})">
        <ellipse rx="120" ry="140" fill="url(#skin)"/>
        <ellipse id="eyeL" cx="-42" cy="-10" rx="12" ry="16" fill="#241a1a"/>
      </g>
    </svg>'''

film.scene(scene)
film.overlay('<div class="title" id="title">The Apprentice</div>')     # screen-fixed, outside the camera
film.key("#title", opacity={0: 0, 1.5: 1}, y={0: 30, 1.5: (0, "snappy")})
film.key("#eyeL", ry={2.0: 16, 2.08: (1, "easeIn"), 2.2: (16, "easeOut")})   # a blink
```

The script runs with `from rostrum2d.markup import *`, `math` and `random` already imported, and must leave `film`.
App fonts by name: Inter, Fraunces, Source Serif 4, Montserrat, Roboto Flex, Recursive, JetBrains Mono, Caveat (all
variable: any weight 100–1000).

## Keys on anything

`film.key("#id", prop={time: value, …}, …)` keys properties of the element with that id.

- **Inside SVG** a property is an attribute: `cx`, `r`, `d`, `fill`, `stroke-dashoffset`, `stop-color`, `opacity`,
  `stdDeviation`, `offset`, `points` … **On an HTML element** it is a CSS property: `opacity`, `left`, `width`,
  `background`, `filter`, `clip-path`, `letter-spacing`, `box-shadow` … `"--name"` is a CSS variable;
  `style:` / `attr:` before a name forces CSS or an attribute. Underscores become dashes (`stop_color`).
- **Transform channels** `x`, `y`, `rotate`, `scale`, `scaleX`, `scaleY`, `skewX`, about `origin` ("cx cy" in SVG
  units; any transform-origin on HTML), applied in the parent's space before the element's own transform. So a part
  drawn with `transform="translate(…)"` is moved/turned from where it was drawn.
- **Values**: numbers; colours `#rgb` / `#rrggbb` / `#rrggbbaa` (mixed in linear light); and any text with numbers in it
  — `"M 0 0 C 40 -20 80 -20 120 0"`, `"blur(6px)"`, `"0 20px 60px #0008"`, `"polygon(0 0, 100% 0, 100% 40%, 0 60%)"` —
  blended number by number when two keys have the same shape (same commands, same count). Different shapes hold, then
  jump at the next key.
- **Easing**: the ease written with a key shapes the stretch arriving at it: `{0: 0, 1.2: (300, "snappy")}`.
  `linear smooth easeIn easeOut easeInOut snappy natural heavy spring bounce hold`, or
  `(value, {"ease": "custom", "x1": .2, "y1": 0, "x2": 0, "y2": 1})`, `(value, {"ease": "spring", "bounce": .4})`.
- Keys are also values you can use inside `scene(t)`: `k = keys({0: 0, 2: (1, "smooth")}); k(t)`. Helpers:
  `lerp(t, t0, t1, v0, v1, ease)`, `spring(t, start, bounce, speed)` (0→1), `wave(t, period, amount, phase)`,
  `clamp(v, lo, hi)`, `mix(a, b, p)`.
- An id named by keys but missing from the markup is listed in the reply's notes (nothing else is changed).

Keys and `scene(t)` work together: draw procedurally (loops, follow-through as `k(t - 0.08)`, breathing as `wave`),
key the moments.

## Characters (rigs are nested groups)

A rig is just nested `<g>` with a pivot each: shoulder → elbow → wrist. Key `rotate` with `origin` at the joint:

```python
film.key("#upperArm", rotate={0: 10, 1: (-60, "snappy"), 1.6: (-50, "smooth")}, origin="0 0")   # joint at the group's 0,0
film.key("#forearm", rotate={0: 0, 1.08: (-40, "snappy"), 1.75: (-30, "smooth")}, origin="0 110") # lags the upper arm: follow-through
```

Draw each joint's group with its pivot at its own `0 0` (`<g id="upperArm" transform="translate(shoulderX shoulderY)">`
… `<g id="forearm" transform="translate(0 110)">`), then `origin="0 0"` is the joint. Overlap and follow-through: give
the child the same keys a few frames later. Heads turn by moving the face features sideways inside the head shape
(`x` keys on `#face`) and squashing the far eye; blinks are `ry` (or `scaleY`) keys on the eyes.

## Lip sync to a RostrumSound voice

Make the lines in RostrumSound (its `run_script` with a voice track, then `render_voice`), on the same project: this
server opens the project your Sound server has open. Then:

```python
mouth = film.lipsync("voice:line1", at=2.0)       # the line's made take, placed at 2.0 s of the film
MOUTHS = {"X": "M -30 0 Q 0 6 30 0", "A": "M -26 0 Q 0 2 26 0", "D": "M -30 -4 Q 0 40 30 -4 Z", …}
def scene(t):
    return f'… <path d="{MOUTHS.get(mouth(t), MOUTHS["X"])}" fill="#5a1f24"/> …'
```

`mouth(t)` is `"X"` (rest) or a Preston Blair shape: **A** lips pressed (M B P), **B** slightly open, teeth together
(most consonants, "ee"), **C** open ("eh", "a" in cat), **D** wide open ("ah"), **E** rounded ("aw", "er"), **F**
puckered ("oo", W), **G** top teeth on lower lip (F V), **H** tongue up (L). `mouth.words` lists each word's start/end
in film seconds; `mouth.talking(t)` says whether a word is being said. A path `d` per shape with the same commands blends
if you key it; picking per frame snaps, as drawn lip sync does. The voice and the music come out of the project's mix
in `render_film`; keep the music lower under the lines in RostrumSound.

`film.marker("drop")` / `film.marker("drop+0.5")`: seconds of a project marker (RostrumSound's moments included), to
time keys on the music.

## Light on shapes (Rostrum's engine)

Mark any HTML element — a `<div>`, or an inline `<svg>` as a whole — with `data-light`, and the engine shades it as a
lit, rounded form from its own silhouette, on the GPU; it can also cast its shadow:

```python
film.light(angle={0: -60, 30: 30}, elevation=40, colour="#fff1d6", shadow="#1b1430", strength=.6, soft=40, cast=30)
'<svg data-light="soft: 60" …>…</svg>'                 # an element's own settings win: soft, cast, strength, colours
```

- `angle`: where the light comes from (degrees: 0 above, 90 right, -90 left). `elevation`: how high (90 = straight
  on, flat). `soft` (px): how far into the shape the shading reaches — small (6–12) is an edge bevel / rim, about half
  the shape's width reads as a round form. `strength` 0–1. `colour`, `shadow`: the lit and the turned-away tint.
  `cast` (px, 0 = off), `castBlur`, `castColour`, `castOpacity`: the shadow laid behind, away from the light.
- Every field can be keyed (a moving light shades every marked shape at once).
- It works on page layers: SVG parts inside one `<svg>` are lit as one silhouette. Parts that should each catch
  their own light (a head over a body, an arm in front) go in their own `<svg>` (absolute, same size and viewBox), or
  their own `<div>`.

## Camera

`film.camera(x={…}, y={…}, zoom={…}, rotate={…})`: x, y = the world point at the frame's centre (default the
frame's centre), zoom 1 = the world at its own size. Everything from `film.scene` is seen through it; `film.overlay`
markup stays fixed on screen. A push-in: `zoom={4: 1, 6: (1.6, "smooth")}, x={4: 960, 6: (1240, "smooth")}`.

## Motion blur

`film.blur(shutter=180, samples=8)`: each frame is drawn `samples` times across the shutter and averaged — anything
that moves smears (keys, `scene(t)` changes, the camera). Costs samples × a frame: turn it on once the motion is set.

## What the engine draws

Blitz lays out HTML/CSS and Skia paints it; inline SVG goes through usvg. Measured against Chrome (42 probes,
2026-10-30):

- **Same as a browser:** flexbox, grid, absolute layout; border-radius, box-shadow; linear / radial / conic CSS
  gradients; CSS `filter` (blur, drop-shadow, colour); 2D and 3D transforms on HTML; `clip-path` shapes; gradient
  `mask-image`; `mix-blend-mode`; CSS variables, `calc()`; text with the app fonts, `text-shadow`, variable weights;
  SVG in `<img>`; colour emoji. In SVG: every shape and path, `viewBox`, linear / radial gradients (userSpaceOnUse,
  gradientTransform), `<use>` / `<symbol>`, nested `transform` groups, dashes, opacity, blend modes, markers,
  `<textPath>`, `<style>` inside the `<svg>`.
- **Not drawn yet, and what to write instead** (run_film's notes say so when your markup uses one):
  - `filter=` / `mask=` on a shape *inside* an `<svg>`, and `<pattern>` fills. Put the SVG filter on the `<svg>`
    element or a `<div>`: `style="filter:url(#glow)"` (the `<filter>` defined in any `<svg>` on the page). Split a
    picture into stacked `<svg>`s (same size and viewBox, absolute) when one part needs its own filter.
  - `feDropShadow`: use CSS `filter: drop-shadow(…)` or blur + offset + flood + composite + merge.
  - CSS `transform` in a `style` inside SVG (with transform-origin / transform-box): use the `transform` attribute;
    keys' x / y / rotate / scale write it for you, about `origin`.
  - `<foreignObject>`; `-webkit-text-fill-color` gradient text (use SVG `<text fill="url(#g)">` or
    `background-clip: text`); `text-overflow: ellipsis`; repeating picture backgrounds; `currentColor` below the
    outer `<svg>`; `clipPathUnits="objectBoundingBox"` (use user units); page CSS aimed at SVG shapes (put that CSS in
    a `<style>` inside the `<svg>`).
