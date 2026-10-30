# Markup films

You draw in HTML + inline SVG + CSS, written from a Python script. Rostrum adds keys on any attribute or CSS value,
a camera, light on shapes, motion blur, lip sync to RostrumSound voices, and the project's music and markers. Looks
and the export draw the same frames. Sections: `inspect_guide {"topic": "markup", "section": "<heading>"}`.

## Loop

`run_film {name, code}` (the whole script; a contact sheet back) → `look_film {name, at: [s]}` (full-size frames,
~0.1–0.3 s each) → change, `run_film` again (same name; omit `code` to re-run) → `render_film {name, file}` →
`look_film {name, every: 2}` to review the whole film, fix, render again.

## Script

Runs with `from rostrum2d.markup import *`, `math`, `random` in scope; must leave `film`.

- `film = Film(width, height, fps, duration, background)`
- `film.css(text)` — a stylesheet. `film.scene(markup or fn(t) -> markup)` — the world (seen through the camera).
  `film.overlay(markup or fn)` — fixed to the screen.
- Fonts by name (variable, weights 100–1000): Inter, Fraunces, Source Serif 4, Montserrat, Roboto Flex, Recursive,
  JetBrains Mono, Caveat.

## Keys

`film.key("#id", prop={t: value, t: (value, ease)}, …)` — a plain value is still.

- Inside SVG a prop is an attribute (`cx`, `d`, `fill`, `stop-color`, `opacity`, `stroke-dashoffset` …); on HTML a
  CSS property (`opacity`, `left`, `filter`, `clip-path`, `background` …). `"--name"`: a CSS variable. `style:` /
  `attr:` prefixes force one; `_` in names is `-`.
- Transform channels `x y rotate scale scaleX scaleY skewX` are applied after the element's own `transform`, in its own
  units, about `origin` (default its own `0 0`; on HTML any transform-origin). A part drawn with its joint at its own
  `0 0` (`<g transform="translate(0 140)">`) turns about that joint.
- Values: numbers; colours `#rgb #rrggbb #rrggbbaa` (mixed in linear light); any text with numbers (path `d`,
  `"blur(6px)"`, shadows, `polygon(…)`) blends number by number when both keys have the same shape, else holds.
- Ease (the key's ease shapes the stretch arriving at it): `linear smooth easeIn easeOut easeInOut snappy natural
  heavy spring bounce hold`; `{"ease": "custom", "x1", "y1", "x2", "y2"}`; `{"ease": "spring", "bounce": .4}`.
- In `scene(t)`: `keys({…})(t)`, `lerp(t, t0, t1, v0, v1, ease)`, `spring(t, start, bounce, speed)` (0→1),
  `wave(t, period, amount, phase)`, `clamp`, `mix(a, b, p)`.
- A keyed id missing from the markup is named in the reply's notes.

## Camera

`film.camera(x=, y=, zoom=, rotate=)` — values or keys; x, y = the world point at the frame's centre; zoom 1 = actual
size. Overlay markup is not moved.

## Light on shapes

`film.light(angle, elevation, colour, shadow, strength, soft, cast, castBlur, castColour, castOpacity)` — numbers may
be keys. Any HTML element (a `<div>`, or an `<svg>` as a whole) with `data-light` is shaded by the engine from its own
silhouette as a lit form, and casts its shadow when `cast` > 0; `data-light="soft: 60; cast: 20"` overrides per
element. `angle`: where the light is (0 above, 90 right). `elevation`: 90 = straight on (flat). `soft` px: how far
in the shading reaches (small: an edge; about half the shape's width: a round form). Parts inside one `<svg>` are one
silhouette; a part that should catch its own light goes in its own `<svg>` or `<div>`.

## Motion blur

`film.blur(shutter=180, samples=8)` — every frame averaged over the shutter; costs samples × a frame. `blur(0)`: off.

## Sound, voices, markers

The server works on the project your RostrumSound server has open: music, voice lines and markers made there are
this film's. `render_film` puts the project's main mix under the picture (`sound: false` for none).

- `mouth = film.lipsync("voice:<line id>", at=seconds)` (or a WAV path) → `mouth(t)`: `"X"` rest, `A` lips pressed
  (M B P), `B` slightly open, teeth together, `C` open, `D` wide open, `E` rounded, `F` puckered (oo, W), `G` teeth on
  lip (F V), `H` tongue up (L). `mouth.words`: each word's start/end; `mouth.talking(t)`.
- `film.marker("name")`, `film.marker("name+0.5")`: seconds of a project marker.

## What the engine draws

Like a browser: flexbox, grid, absolute layout; radius, box-shadow; CSS gradients; CSS `filter`; 2D/3D transforms on
HTML; `clip-path` shapes; gradient `mask-image`; blend modes; CSS variables, `calc()`; text, `text-shadow`; SVG in
`<img>`; emoji. In SVG: all shapes and paths, `viewBox`, gradients, `<use>`/`<symbol>`, nested transforms, dashes,
opacity, blend, markers, `<textPath>`, `<style>` inside the `<svg>`.

Not yet (run_film's notes name them when used), and what works instead:
- `filter=` / `mask=` on a shape inside an `<svg>`, `<pattern>`: put the filter on the `<svg>` or a `<div>` as
  `style="filter:url(#id)"`; stack `<svg>`s when one part needs its own.
- `feDropShadow`: CSS `drop-shadow()` or blur + offset + flood + composite + merge.
- CSS `transform` in a style inside SVG: the `transform` attribute (keys write it).
- `<foreignObject>`, `-webkit-text-fill-color`, `text-overflow: ellipsis`, repeating picture backgrounds,
  `currentColor` below the outer `<svg>`, `clipPathUnits="objectBoundingBox"`, page CSS aimed at SVG shapes (put it
  in a `<style>` inside the `<svg>`).
