# Rostrum2D engine contract — the scene description

*Team Sam, brief S5, 2026-10-21. Version **1**. Between the Python layer (`apps/2d/python/rostrum2d/`) and the Rust engine (`apps/2d/engine/`, Team Hem).*

The Python layer owns the document (OPERATIONS.md § 1). It sends the engine a **scene description**: one composition, every item's still values, and the keys of its animated fields. The **engine evaluates the scene per frame** (keys, easing, then drawing), so scrubbing is fast and the canvas, the look tools and the export all draw the same way (AGENTS.md rule 5: preview ≡ export).

## 1. The conversation (`serve`, one JSON object per line each way)

The engine holds the scene and evaluates every frame itself. The request header of `render/src/scene_serve.rs` is the full detail.

| Request | Reply | Meaning |
|---|---|---|
| `{"scene": {…scene…}, "cpu"?: true}` | `{"ok": true, "items": N, "width", "height", "fps", "duration", "fonts": ["Inter", "Recursive", …]}` | Load or replace the scene. Checked whole: anything unknown or undrawable fails (§ 5). Opens a drawing session at the comp's size if none is open at that size (`cpu`: draw on the CPU, for machines or tests without a GPU). |
| `{"frame": {"t": 1.25, "image": "C:\…\f.png", "index"?: n}}` | `{"ok": true, "timing": {…, "evalMs"}}` | Draw the scene at `t` seconds into a PNG. `index` (the frame number, used by anything that varies per frame) defaults to round(t · fps), so a still is the same picture as that frame of the export. |
| `{"frame": {"t": 1.25, "pixels": true}}` | `{"ok": true, "width", "height", "timing", "shm": {"name": "Local\rostrum2d-<pid>-<n>", "size", "offset", "bytes", "stride", "format": "rgba8", "seq", "width", "height"}}` | The frame for the live canvas, written into one of two alternating slots of a named block of shared memory (no PNG, no pipe): the same straight-alpha bytes as an image would hold (`rgba64le` at depth 16). The reader is done with a slot before it asks for the frame after next; a new block (new `name`) comes when the frame size changes. Python: `mmap.mmap(-1, size, tagname=name)` (`Engine.pixels`). Windows now; Mac (`shm_open`, name `/rostrum2d-<pid>-<n>`) still refused with a message. |
| `{"export": {"start"?, "end"?, "encode": {…ffmpeg…}, "file"?, "images"?, "progress"?}}` | `{"ok": true, "frames": 90, "timing"}` | Every frame from `start` (default 0) to `end` (default the comp's duration) at the comp's fps, into the encoder; `file` is checked to exist and not be empty afterwards. Or `"images": "C:\…\f-{frame}.png"`: each frame to a picture. With `"progress": true` a line `{"progress": i, "of": n}` comes after each frame, before the reply. |
| `{"edit": [{"id": "title", "props"?: {"x": 700}, "anim"?: {"y": [keys] \| null}}, …]}` | `{"ok": true, "edits": n}` | Small changes to the held scene without resending it (a drag). **All or nothing**: the whole list is checked as a load is, and nothing is applied if any part fails. |
| `{"bones": {"t": 1.25}}` | `{"ok": true, "rigs": {"<rig id>": {"bones": {"<id>": {"x", "y", "tipX", "tipY", "angle"}}, "iks": {"<id>": {"targetX", "targetY", "gap", "bones"}}}}}` | Every rig's posed bones (pivot, tip, angle) and each IK's (held) target and how far its tip misses it (two-bone and long chains alike; `bones` = the chain's bones, top first), at `t`, in comp px (tilt left out). The agents' eyes on a character ([`RIG.md`](RIG.md)). |
| `{"outline": {"id": "p", "t": 0.5}}` | `{"ok": true, "d": "M …"}` (`d` null for an even stroke, "" when nothing shows) | A path's varied stroke (tapers, width profile) as the filled outline the stage draws, in the path's px: the Lottie export carries it as a fill (`rostrum2d/io/lottie_outline.py`). |
| `{"measure": {"items": [{"id": "title", "body", "font", "size", "weight", "stretch", "tracking", "lineHeight", "align", "boxWidth", "features"?, "axes"?, "ligatures"?, "figures"?, "smallCaps"?, "slant"?, "grade"?, "path"?, "pathOffset"?, "pathAlign"?, "pathOverflow"?, "letterDelay"?, "letterSplit"?}, …]}}` | `{"ok": true, "sizes": {"title": [w, h]}}` | Each text's box in its own px (before scale and turn): the box the renderer lays it out in, by the same code that draws it (one line, or `boxWidth` wide and wrapped; letter by letter or on a path, the box its letters are placed in). The fields are the text's evaluated values (no time: evaluate keys first); a type field left out is fields.py's default. The whole list is one round trip and one layout. Needs no scene; with one loaded, its fonts. A font not found, or a field the text doesn't have or with a wrong value, fails as `scene` does, naming the id. Python: `Engine.measure`, cached by `rostrum2d/textsize.py`. |

Errors are `{"error": "…"}` naming the item id and field; the process keeps serving. The engine never draws a frame it couldn't fully understand.

The page-markup requests (`open`, `frame {stage}`, `page`, `finish`) stay in `serve` for the renderer's own tests and proofs; the Python layer no longer uses them.

## 2. The scene

```json
{
  "format": "rostrum-2d-scene", "version": 1,
  "comp": {
    "id": "intro", "type": "comp",
    "props": {"width": 1920, "height": 1080, "fps": 30, "duration": 3.0, "background": "#05050a"},
    "layers": [
      {"id": "title", "type": "text",
       "props": {"body": "Rostrum", "size": 220, "weight": 780, "x": 960, "y": 540, "opacity": 1.0, "…": "…"},
       "anim": {"y": [{"t": 0.2, "v": 600, "ease": "snappy"}, {"t": 1.0, "v": 540, "ease": "smooth"}]},
       "effects": [{"id": "title_grad", "type": "gradient", "props": {"style": "linear", "angle": 180, "…": "…"}}],
       "masks": [{"id": "wipe", "type": "mask", "props": {"shape": "rect", "x": 0, "w": 0, "…": "…"},
                  "anim": {"w": [{"t": 0.2, "v": 0, "ease": "easeInOut"}, {"t": 1.2, "v": 1400, "ease": "smooth"}]}}]}
    ]
  }
}
```

- **Every field is present** in `props` (defaults filled in by Python), so the engine needs no defaults table of its own. The fields, their types and ranges are `rostrum2d/fields.py` (the one table).
- **Layers draw in list order**: the first is at the bottom. A `group` has its own `layers`, drawn inside its box.
- `effects` and `masks` belong to the layer; effects, masks and layers may each have `anim`.
- Ids are unique in the scene. Times are **seconds**; lengths are **px** in the composition's frame; angles **degrees**; colours `#rrggbb`.
- Produced by `rostrum2d.scene.describe(doc.data, comp_id)`.
- **`fonts`** (optional, top level, beside `comp`): `{"Family": "D:/My Film/fonts/Display.ttf", …}` (absolute paths), the project's own fonts. They win over the app's; each file is checked when the scene loads. The `scene` reply lists every family the text may name (`fonts`), for agents and the font picker.
- **`drawing`** (added S6, same version): a layer drawn frame by frame with the shared painting kit. `props` has `w`, `h`
  (its box, px) and the usual transform; `frames: [{"at": 0, "src": "C:\…\<key>_800x1000.png"}, …]`, sorted by `at`
  (a frame number). At time `t` the engine shows the `src` of the last frame with `at <= floor(t · fps)`; nothing
  before the first. Each `src` is a straight-alpha RGBA PNG of exactly `w × h`, made once by the painting kit and named by
  its content (never changes under the same name): the engine only reads it, stretched to the box like an image with
  `fit: stretch`. Masks and effects apply as on any layer.
- **`path`** (added S8, same version): a vector path. `props.d` is SVG path data with absolute commands only — `M x y`,
  `L x y`, `C x1 y1 x2 y2 x y`, `Z` (numbers separated by spaces or commas; a command's numbers may repeat; extra pairs
  after `M` are lines; after `Z` a new `M` is needed) — in the layer's own px from its box's top-left. `w × h` is its box
  (at least 1 px; the anchor and gradients use it; the curve may reach outside it and is still drawn). A `d` the engine
  can't read is refused, naming `id.d`. `d` may be keyed (keys carry `d`, path data; § 3 Shapes); `w`, `h`, `fillRule`,
  `cap`, `join` are still.
- **`video`** (added S8, same version): a layer with `src`, `w`, `h`, `fit`, `radius`, `offset` (s into the clip),
  `speed`, `loop` and the transform. Like a drawing it carries `frames: [{"at": i, "src": png}, …]`, `i` = 0..n−1 over
  the clip decoded at the comp's fps and at `w × h` (the fit applied at decode). At frame `n = floor(t·fps)` the picture
  is `frames[k]`, `k = floor((n − start·fps)·speed + 1e-6) + round_ties_even(offset·fps)`; with `loop` k wraps
  (`rem_euclid(count)`), otherwise it is held at 0..count−1. Python decodes once with the `ffmpeg` program into a cache
  folder keyed by the file's content, size, w × h, fit, fps and decoder version (`rostrum2d/video.py`). `w`, `h`,
  `offset`, `speed` can't be animated. No frames, or a missing picture, is an error. The video's own sound is not read.
- **`rig`** (added H10, same version): a layer with a group's fields (`w`, `h`, `clip`) and `layers`, plus `rig: [...]`,
  its `bone`, `ik` and `bind` items (every field present, `anim` on bone and ik fields). The engine poses the bones and
  moves or bends the bound layers every frame; a bend bind is drawn through a warp mesh. Fields, evaluation and load
  checks: [`RIG.md`](RIG.md).

## 3. Evaluation (the reference is `rostrum2d/evaluate.py` and `easing.py`)

- A field with an `anim` list is **animated**: its keys alone decide its value; the value in `props` is ignored. Otherwise it is still.
- Keys are sorted by `t`. Before the first key and after the last, the value holds. Between key *a* and key *b*, progress `p = ease_a((t − a.t) / (b.t − a.t))` and the value is `a + (b − a) · p`. `p` may leave 0..1 (spring, custom curves overshoot).
- Numbers: `v`. Colours: `c`, mixed in **linear light** (sRGB decoded, mixed, encoded).
- Shapes (a path's `d`): `d`, path data, blended point by point (`scene/morph.rs`): both become cubic segments; subpaths
  pair in order and must be as many; the one with fewer segments has its longest segment halved until the counts
  match; a closed pair is turned so the start points are nearest. A pair that can't be matched is refused at load,
  naming `id.d` and the two key times. `p` outside 0..1 carries the blend on.
- **Easing** (`ease` on the key that starts the stretch): `linear`; `hold` (stays at *a* until *b*); cubic-beziers `smooth (.25,.1,.25,1)`, `snappy (.16,1,.3,1)`, `natural (.4,0,.2,1)`, `heavy (.25,1,.5,1)`, `easeIn (.42,0,1,1)`, `easeOut (0,0,.58,1)`, `easeInOut (.65,0,.35,1)`; `custom` with `x1 y1 x2 y2`; `spring` with `stiffness`, `damping` (mass 1, the stretch read as one second, released at 0, settling on 1); `bounce` (the standard four-arc bounce).
- A layer is drawn only while `start ≤ t < end`.

## 4. Drawing (what each field means)

- **Transform:** the layer's anchor (`anchorX`, `anchorY`, fractions of its box; 0.5 = centre) sits at (`x`, `y`) in its parent's space. Order: tilt (`tiltX`, `tiltY`, 2.5D, perspective 1600 px per layer), then `rotation`, then scale (`scale·scaleX`, `scale·scaleY`), all about the anchor. Then `opacity`, then `blend` (`normal`, `screen`, `add`, `multiply`, `overlay`, `soft-light`).
- **Box:** shape and image `w × h`; group `w × h` (`clip` hides children outside it); text: its laid-out size (one line, or `boxWidth` wide and wrapped).
- **shape:** `rect` (corner `radius`) or `ellipse`; `fill`; optional outline (`stroke`, `strokeColor`, `strokeWidth`), drawn inside the box.
- **path:** `filled` → `fill` with `fillRule` (`nonzero`, `evenodd`); `stroke` → `strokeColor`, `strokeWidth`, centred on
  the line, `cap` (`butt`, `round`, `square`), `join` (`miter`, `round`, `bevel`), `miter` (limit, ≥ 1). Dashes: `dash` px
  drawn, `gap` px skipped (`dash` 0 = solid), shifted by `dashOffset`; they start again at each subpath. Trim: only
  `trimStart..trimEnd` (fractions 0..1 of the whole length, subpath after subpath) of the stroke is drawn — keying
  `trimEnd` 0 → 1 draws it on; dashes are cut to the trimmed part (more than 20,000 dash pieces is refused). A `gradient`
  fills the path (with `filled` off it colours the stroke), `linear` and `radial` only (a conic one is refused). A
  `shadow` follows the outline. Glow, blur and masks as on any layer.
  - **Varied width** (added H17, same version): `taperStart`, `taperEnd` (0..1, default 0, keyable): the fraction of the
    length over which the width grows from 0 at the start / shrinks to 0 at the end, eased as sin(π/2 · x) (x = how
    far into the taper; a pointed tip that meets the full width with no kink). `widthProfile` (text, default "", keyable: a key keeps its text in `d`):
    `"pos,mult pos,mult …"`, pos 0..1 along the length, each after the one before, mult ≥ 0 times `strokeWidth`; ""
    = an even width; between points a monotone cubic (no overshoot, never below 0), held before the first and after
    the last point; text the engine can't read is refused when drawn, naming `id.widthProfile` (a key's, at load, with
    its time). Between two keys the profile is, at every position of either key, both profiles' multipliers (an empty
    one is 1) mixed by the eased progress, never below 0 (`scene/width_profile.rs` `blend`). `taperAlong` (`line`
    default | `drawn`): u runs over the whole line (the ink stays as drawn while `trimEnd` moves) or over the drawn
    part `trimStart..trimEnd` (the tip stays tapered as it draws on). Width at u = `strokeWidth` × profile(u) ×
    taper(u). With a taper > 0 or a profile the stroke is not an SVG stroke but a filled outline the engine works out
    (`scene/stroke_width.rs`): each visible piece (trim and dashes as above) sampled every ≤ 2 px and ≤ 4° of turn,
    offset ± half the width along the normal, closed with its `cap` (round = a half circle as wide as the stroke there,
    `butt`, `square`); corners turning more than 10° get a round join whatever `join` says; a closed subpath shown
    whole is a ring with no caps. It is filled (nonzero) with the stroke's colour, gradient or glow colour.
- **text:** `body`, `font` (family name: first the scene's `fonts`, then the app's folder `apps/2d/engine/fonts/` (installed: `fonts\` beside the program; `ROSTRUM2D_FONTS` overrides); each file is listed under its family name and also without a trailing " Variable". A family found in neither is refused when the scene loads or is edited: `subtitle: font "Helvetica Neue" not found; there is: …`), `size` px, `weight` and `stretch` (variable-font axes), optical size = font size automatically, `tracking` (em), `lineHeight`, `align`, `color`, optional outline.
  - **Type:** `ligatures` (default on; off writes `liga 0, clig 0`), `figures` (`default` | `proportional lining` |
    `tabular lining` | `proportional old-style` | `tabular old-style`), `smallCaps` (`smcp`) and `features` (OpenType
    tags: `"ss01 ss03 salt"`, `"cv05=2"`, `"-kern"`; a later tag wins), all written as `font-feature-settings`. A feature
    the font doesn't have is refused, naming the layer, the field and the features it has (proportional and lining
    figures excepted: most fonts' own).
  - **Axes:** `weight` → `wght`, `stretch` → `wdth`; `opsz` = size, held to 8…144; `slant` → `slnt` and `grade` →
    `GRAD` when not 0 (both can be keyed); `axes` names any axis by tag (`"XTRA 468, CASL 1"`) and wins over the named
    ones. An axis the font doesn't have is refused; a value outside the axis's range is clamped (as CSS).
  - **Text on a path:** `path` is SVG path data (as a path layer's `d`) in the layer's own px; empty = normal text. The
    letters' baseline sits on the path, each letter turned to the path's direction, spaced by the font's own advance
    widths plus `tracking` (no kerning). `pathAlign` start / center / end on the path's length, then `pathOffset` px
    further along (can be keyed). A letter whose centre falls before the start or past the end is left out
    (`pathOverflow` "hide", the default) or carried on in a straight line ("straight"). The box runs from
    (0, 0) to the path's far corner. One line only (a line break is refused).
  - **Following a path layer:** `pathLayer` names a `path` layer beside the text (same composition or group). At
    every time the text takes that layer's `d`, its box (`w × h`) and its transform (x, y, anchor, rotation, scale,
    stretch, tilt) as they are then, and sits only on its drawn part: `pathAlign` and `pathOffset` work within
    `trimStart..trimEnd`, and letters on the trimmed-off part are left out (keying `trimEnd` draws the letters on with
    the line). The text's own transform is not used; its opacity, blend, colour and letter keys are. A `pathLayer` that
    names nothing beside it, or a layer that isn't a path, or one set together with `path`, is refused at load and at
    `edit` (resolved in `scene/follow.rs`, the one place).
  - **Letter by letter:** `letterDelay` s ≠ 0: each letter (`letterSplit` letters | words) plays the layer's own keys
    `letterDelay × its place` later; places follow `letterOrder` forward | backward | center | random (`letterSeed`, the
    same order on every machine). Keyed x / y move each letter from the layer's still x / y; keyed rotation, scale,
    stretch, tilt and opacity apply to each letter about its own centre; keyed colour, outline colour and width are per
    letter. A gradient spans the whole text. On a path or letter by letter, `boxWidth` ≠ 0 is refused (no wrapping
    yet); a letter the font can't measure is refused.
- **image** and **video:** `src` (absolute path), `fit` (`cover`, `contain`, `stretch`), corner `radius`. A gradient on an image, drawing or video is refused.
- **Order inside a layer:** content → masks → effects. A mask cuts the content; a glow or blur works on what the mask left.
- **mask:** `rect` / `ellipse` at (`x`, `y`, `w`, `h`) in the layer's own px from its top-left; `radius`, `feather` (soft
  edge, px, centred on the shape's edge), `invert`, `angle` (the mask turned about its centre: a feathered rect sweeping
  across at an angle is a soft wipe). Several masks intersect. A plain one is a `clip-path`; a feathered, inverted or
  turned one is an SVG alpha `<mask>` built from gradient pieces (solid core, linear edge bands, radial corners,
  smoothstep ramps; a hard turned or inverted edge gets 1 px), because the renderer draws no filters inside a mask.
- **Track matte:** `matte` = the id of a layer beside it (same group or comp; "" = none), `matteMode` `alpha` |
  `alphaInverted` | `luma` | `lumaInverted`. The layer (after its own masks and effects, with its blend) shows only where
  the matte layer is drawn (`alpha`: its coverage; `luma`: luminance × coverage), or only where it isn't (inverted), at
  the same frame. The matte layer is drawn only as the matte, never on its own, with its own keys, transform, opacity,
  effects and masks; outside its own times it is empty (the layer hidden; inverted: whole). Any layer type is a matte:
  the painter draws the matte layer's own markup (`data-track-matte`, vendor/blitz-paint/src/track_matte.rs) as the
  mask, so a matte looks exactly as that layer would on its own. Refused when the scene loads or is edited: a matte that
  is no layer beside it, the layer itself, the camera, or a layer that has a matte of its own.
- **Blend:** `blend` is one of the modes in `apps/2d/python/rostrum2d/blends.txt`, the one list (Python reads it at
  import; the engine compiles it in, `scene/blends.rs`): normal, multiply, screen, add, overlay, soft-light,
  hard-light, darken, lighten, color-dodge, color-burn, difference, exclusion, hue, saturation, color, luminosity.
  Each is written as the CSS `mix-blend-mode` in that file's second column (`add` = `plus-lighter`) and drawn by Skia's
  blend of the same name. A layer under a camera or a track matte carries its blend on the wrapper (`blends::style`).
- **Colour effects** (`scene/grade.rs`, every layer): `adjust` on → `exposure` (stops), `temperature` / `tint`
  (the grade's `warmth`), `contrast` (×, about mid grey), `saturation` (×), `hue` (degrees); `levels` on →
  `inBlack`, `inWhite`, `gamma`, `outBlack`, `outWhite` (screen brightness 0..1); `curves` on → `curve` (all channels),
  `curveR`, `curveG`, `curveB` (text `"x,y x,y …"`, 0..1, x rising, smooth through the points without overshoot);
  `lut` = an absolute path to a `.cube` (1D or 3D, screen colours in and out) at `lutMix`. In that order they make one
  rostrum-color grade (the same grade `sksl grade` serves), compiled to one SkSL colour filter that the painter runs on
  the layer's look (content, masks, effects; not a frosted-glass backdrop) as an `<feshader effect="grade">`; levels
  and curves become the grade's curve tables (`scene/grade_curve.rs`), the LUT's table an RHALF image in
  `~/.rostrum/cache/2d-lut`. Numbers can be keyed; the curve texts and the LUT file can't. Refused when the scene loads
  or is edited, naming the layer and field: a curve that isn't valid points, `inWhite` not above `inBlack`, a LUT file
  that is relative, missing or malformed (the `.cube` line number). Nothing changes in the markup while every effect is off.
- **Effects, in list order:** `gradient` fills the layer instead of its colour (a shape's fill, **a text's letters**, a group's background): `linear` at `angle` (CSS convention: 180 = top to bottom), `radial` (closest side, at `cx`, `cy`) or `conic` (from `angle`, 0 = up, clockwise, at `cx`, `cy`; `cx`, `cy` fractions of the box); `color1` → (`color3` at `mid` when `middle`) → `color2`. `blur` (`radius` px). `glow`: a blurred copy (`radius`) added behind, `strength` 0..4, the layer's own colours or `color`. `shadow`: offset `dx`, `dy`, softness `radius`, `color`, `strength`. `backdrop` (frosted glass): blurs what is behind the layer inside its box and corner
  radius (`radius` blur σ px, `saturate`, `brightness`), drawn before the content; the layer's fill shows over it at
  `fillAmount`; the layer's opacity applies to the glass and the content. Refused with a non-normal blend or with a
  feathered, inverted or turned mask.

## 5. Failing loudly

- Unknown `format` / `version`, item `type`, field name, ease name, or a value of the wrong type: the whole `scene` request is refused, naming the id and field.
- A feature the engine can't draw yet is refused the same way — never drawn as something else.

## 6. Versioning

`version` goes up when a field's meaning changes or a required field is added. Adding a new item type or effect with its own fields is a minor addition (same version, the engine refuses it until it knows it). The Python side sends the version it wrote; the engine answers `{"error": "scene version 2; this engine reads 1"}` when it can't read it.

## 7. History

- S5: version 1 written; until the engine took `scene`, Python evaluated each frame and sent page markup (the stopgap).
- H6: the engine evaluates scenes itself, pixel for pixel as the stopgap did (`proofs/2d-engine-scene/README.md`).
- S7: the Python stopgap is deleted; drawing layers are drawn by the engine; `scene` takes `cpu`, `frame.index` defaults to round(t · fps), `export` takes `images` and `progress`, `edit` is all or nothing.
- S9 (same version): text `pathOverflow`.
- S10 (same version): text `pathLayer` (a text follows a path layer, per frame); a text on a path now takes its colour and outline when not played letter by letter.
- H10 (same version): rig layers, bones, IK, binds; the `bones` request.
- H16 (same version): the `measure` request (a text's laid-out box, for auto layout and the screen's boxes).
- S8 (same version): `path` and `video` layers; text features, axes, text on a path, letter by letter; gradient `conic` and centre; `backdrop`; masks feather / invert / `angle` for every shape; scene `fonts` and the `scene` reply's font list; `pixels` written out.
