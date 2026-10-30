# Markup films

You draw in HTML + inline SVG + CSS, written from a Python script. Rostrum adds keys on any attribute or CSS value,
a camera, light and grain on shapes, motion blur, lip sync to RostrumSound voices, and the project's music and
markers. Looks and the export draw the same frames. Any section: `look_film {guide: "<heading words>"}`.

## Loop

- `run_film {name, code}` (the whole script) or `{name, file}` (a .py you keep in your work folder and edit): a
  contact sheet comes back.
- `look_film {name, at: [s]}`: full-size frames, ~0.1–0.3 s each. `{every: 2, notes: true}`: a frame every 2 s
  across the film, with what a client would notice (text cut by the edge or covered, a small element sitting on text,
  near-empty or unmoving frames; text with or without an id, shapes inside an `<svg>` by their outline's box).
  `{at: [s], motion: true}`: 6 frames in a row from each time, to see movement (blur copies, jitter, holds).
- Change the script, `run_film` again (same name; omit `code` to re-run).
- `render_film {name, file}`: the MP4 with the project's sound; a review sheet of the delivered film comes back.
  `quality: "draft"`: a quick export to watch it move (motion blur at 2 samples). run_film's reply says how long a
  full export takes at the looks' speed.
- Every reply ends with the time since the session started, how much of it went to exports, and the time left when
  you have a time box.

## Script

Runs with `from rostrum2d.markup import *`, `math`, `random` in scope; must leave `film`. Plain Python: any import;
`print` comes back in the reply. `random` is seeded, so a re-run draws the same film (`random.seed(n)`: another
draw); inside `scene(t)` the same t always draws the same numbers.

- `film = Film(width, height, fps, duration, background)`
- `film.css(text)` — a stylesheet. `film.scene(markup or fn(t) -> markup)` — the world (seen through the camera).
  `film.overlay(markup or fn)` — fixed to the screen.
- Fonts by name (variable, weights 100–1000): Inter, Fraunces, Source Serif 4, Montserrat, Roboto Flex, Recursive,
  JetBrains Mono, Caveat.
- Any Google Fonts family by name (`font-family`, or its fonts.googleapis.com `@import` URL; fetched once, then kept);
  icons by name: Lucide / Tabler (`<i data-lucide="arrow-right">`, `<i class="ti ti-heart">`) become inline SVG.

## Keys

`film.key("#id", prop={t: value, t: (value, ease)}, …)` — a plain value is still.

- Inside SVG a prop is an attribute (`cx`, `d`, `fill`, `stop-color`, `opacity`, `stroke-dashoffset` …); on HTML a
  CSS property (`opacity`, `left`, `filter`, `clip-path`, `background` …); a bare number on a CSS length is px
  (`left: 500`), as in React. `"--name"`: a CSS variable. `style:` / `attr:` prefixes force one; `_` in names is `-`.
- Transform channels `x y rotate scale scaleX scaleY skewX` are applied after the element's own `transform`, in its own
  units, about `origin` (default its own `0 0`; on HTML any transform-origin). A part drawn with its joint at its own
  `0 0` (`<g transform="translate(0 140)">`) turns about that joint.
- Values: numbers; colours `#rgb #rrggbb #rrggbbaa` (mixed in linear light); any text with numbers (path `d`,
  `"blur(6px)"`, shadows, `polygon(…)`) blends number by number when both keys have the same shape, else holds.
- Ease (the key's ease shapes the stretch arriving at it): `linear smooth easeIn easeOut easeInOut snappy natural
  heavy spring bounce hold`; `{"ease": "custom", "x1", "y1", "x2", "y2"}`; `{"ease": "spring", "bounce": .4}`.
- In `scene(t)`: `keys({…})(t)`, `lerp(t, t0, t1, v0, v1, ease)`, `spring(t, start, bounce, speed)` (0→1, overshooting past 1 by `bounce`; settles in about 1/speed s),
  `wave(t, period, amount, phase)`, `clamp`, `mix(a, b, p)`.
- Keys reach every element with that id, whether `scene(t)` returns it, a string scene holds it or the overlay does.
  A keyed id missing from the markup is named in the reply's notes.

## Camera

`film.camera(x=, y=, zoom=, rotate=, focus=, aperture=)` — values or keys; x, y = the world point at the frame's
centre; zoom 1 = actual size. Overlay markup is not moved. focus / aperture: see Depth and focus.

## Depth and focus

`data-depth="d"` puts an element of the scene at depth d for the camera (the overlay has no depth). 1 = the world
(no data-depth); 0 = fixed to the screen; between 0 and 1 = further away, moving less; above 1 = in front, moving more.
The camera moves a depth-d element by d times its offset from the frame's centre and zooms it by zoom ** d; rotate
turns every depth alike.
- Read on a top-level element of the scene, and on a direct child of a top-level `<svg>` (`<g data-depth=".3">`).
  Deeper inside, the element moves with its parent.
- Each run of elements at one depth is its own box at the frame's top-left, in paint order: place them with
  `position: absolute` or as a full-frame `<svg>` (normal flow starts again at the top-left in each box).
- Keyable: `film.key("#hills", data_depth={0: .3, 4: .6})`. Light and grain work on parts at any depth.
- `film.camera(focus=, aperture=)` — depth of field: each depth blurred by |d − focus| × aperture px (both may be keys;
  without both, no blur).

## Light on shapes

`film.light(angle, elevation, colour, shadow, strength, soft, cast, castBlur, castColour, castOpacity)` (by name, or
values in that order) — numbers may be keys. An element with `data-light` is shaded by the engine from its own
silhouette as a lit form, and casts its shadow when `cast` > 0; `data-light="soft: 60; cast: 20"` overrides per element. `angle`: where the light is (0 above,
90 right). `elevation`: 90 = straight on (flat). `soft` px: how far in the shading reaches (small: an edge; about half
the shape's width: a round form).
- On an HTML element: that element and everything in it, one silhouette.
- On an element inside an `<svg>` (`<g>`, `<path>`, … at any depth): that element alone, with its keyed transforms.
- On an `<svg>` as a whole: each direct child of the svg is its own lit part (a child's own `data-light` adds to it).
- Parts keep their paint order: a part in front casts onto what is under it.

## Grain and texture

`film.grain(amount, size, seed, colour, smooth, still, frame=True)` (by name, or values in that order) — the
engine's film grain over the whole frame (background included); numbers may be keys. `frame=False`: only the settings `data-grain` elements start from.
`data-grain="amount: .3; size: 2"` on any element (HTML, an `<svg>` as a whole, a lit element): grain on its own look,
only where it is drawn. `amount`: strength (strongest in mid-tones). `size` px: grain cell size. `seed`: another
equally random grain. `colour: 1`: each colour channel its own grain. `smooth: 0`: square cells. `still: 1`: the same
grain every frame (a fixed texture); otherwise it changes each frame.

## Motion blur

`film.blur(shutter=180, samples=8)` — every frame averaged over the shutter; costs samples × a frame. `blur(0)`: off.
`shutter` may be keys (`{0: 180, 12: 0}`: off from 12 s). The samples are separate pictures: something moving
further in one frame than its own size ÷ samples shows as that many copies (`look_film {motion: true}` shows it).
`film.cut(t, …)`: hard cuts; a frame's samples never reach across one.
`data-blur="off"` on an element draws it sharp (its own keys held at the frame's moment; a moving parent still carries
it) while the rest keeps the film's blur; `data-blur="90"` gives it its own shutter in degrees.

## Sound, voices, markers

The server works on the project your RostrumSound server has open: music, voice lines and markers made there are
this film's. `render_film` puts the project's main mix under the picture (`sound: false` for none); a missing or
empty song exports silent. Any audio file you make goes in through RostrumSound's script (`track(...).clip(file, at=s)`).

- `mouth = film.lipsync("voice:<line id>", at=seconds)` (or a WAV path; `pronounce={"word": "ARPAbet"}` for a word
  the dictionary lacks) → `mouth(t)`: `"X"` rest, `A` lips pressed (M B P), `B` slightly open, teeth together, `C`
  open, `D` wide open, `E` rounded, `F` puckered (oo, W), `G` teeth on lip (F V), `H` tongue up (L).
  `mouth.words`: each word's start/end; `mouth.talking(t)`.
- `film.marker("name")`, `film.marker("name+0.5")`: seconds of a project marker.

## What the engine draws

Like a browser: flexbox, grid, absolute layout; radius, box-shadow; CSS gradients; CSS `filter`; `backdrop-filter`; 2D/3D transforms on
HTML; `clip-path` shapes; gradient `mask-image`; blend modes; CSS variables, `calc()`; text, `text-shadow`; SVG in
`<img>`; emoji. In SVG: all shapes and paths, `viewBox`, gradients, `<use>`/`<symbol>`, nested transforms, dashes,
opacity, blend, markers, `<textPath>`, `<style>` inside the `<svg>`; `currentColor` at any depth (from CSS `color`
on a parent, a part's style or its `color=` attribute); `<mask>` (luminance or `mask-type="alpha"`, any content, its
units and region) and `<clipPath>` (shapes, `<text>`, `clipPathUnits`, a clip on the clip), keys included; CSS
`mask: url(#id)` and `clip-path: url(#id)` on HTML. SVG `<filter>` as `filter=` on shapes, groups and text inside
an `<svg>` and as CSS `filter: url(#id)` on HTML: feGaussianBlur, feOffset, feFlood, feComposite, feMerge, feBlend,
feColorMatrix, feComponentTransfer, feDropShadow, feMorphology, feTurbulence, feDisplacementMap; region, units,
subregions, `color-interpolation-filters`, keys included.

Not yet (run_film's notes name them when used), and what works instead:
- `<pattern>`: CSS backgrounds or shapes repeated in Python.
- feDiffuseLighting, feSpecularLighting, feConvolveMatrix, feTile (each passes its input through); feImage in a
  `filter=` inside an `<svg>` (on a `<div>`'s `filter: url(#id)` it is drawn).
- CSS `transform` in a style inside SVG: the `transform` attribute (keys write it).
- `<foreignObject>`, `-webkit-text-fill-color`, `text-overflow: ellipsis`, repeating picture backgrounds,
  page CSS aimed at SVG shapes (put it
  in a `<style>` inside the `<svg>`).
