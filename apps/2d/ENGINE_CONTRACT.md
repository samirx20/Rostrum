# Rostrum2D engine contract — the scene description

*Team Sam, brief S5, 2026-10-21. Version **3** (picture and painted fill per use, painted fill P2, 2026-10-24). Between the Python layer (`apps/2d/python/rostrum2d/`) and the Rust engine (`apps/2d/engine/`, Team Hem).*

The Python layer owns the document (OPERATIONS.md § 1). It sends the engine a **scene description**: one composition, every item's still values, and the keys of its animated fields. The **engine evaluates the scene per frame** (keys, easing, then drawing), so scrubbing is fast and the canvas, the look tools and the export all draw the same way (AGENTS.md rule 5: preview ≡ export).

## 1. The conversation (`serve`, one JSON object per line each way)

The engine holds the scene and evaluates every frame itself. The request header of `render/src/scene_serve.rs` is the full detail.

| Request | Reply | Meaning |
|---|---|---|
| `{"scene": {…scene…}, "cpu"?: true}` | `{"ok": true, "items": N, "width", "height", "fps", "duration", "fonts": ["Inter", "Arial", …], "gpu", "adapter", "fallback"}` | Load or replace the scene. Checked whole: anything unknown or undrawable fails (§ 5). Opens a drawing session at the comp's size if none is open at that size (`cpu`: draw on the CPU, for machines or tests without a GPU). With no working graphics driver (or `ROSTRUM2D_NO_GPU=1`) it draws the same frames on the CPU and `fallback` says so in plain words (null on the GPU). |
| `{"frame": {"t": 1.25, "image": "C:\…\f.png", "index"?: n}}` | `{"ok": true, "timing": {…, "evalMs"}}` | Draw the scene at `t` seconds into a PNG. `index` (the frame number, used by anything that varies per frame) defaults to round(t · fps), so a still is the same picture as that frame of the export. |
| `{"frame": {"t": 1.25, "pixels": true}}` | `{"ok": true, "width", "height", "timing", "shm": {"name": "Local\rostrum2d-<pid>-<n>", "size", "offset", "bytes", "stride", "format": "rgba8", "seq", "width", "height"}}` | The frame for the live canvas, written into one of two alternating slots of a named block of shared memory (no PNG, no pipe): the same straight-alpha bytes as an image would hold (`rgba64le` at depth 16). The reader is done with a slot before it asks for the frame after next; a new block (new `name`) comes when the frame size changes. Python: `mmap.mmap(-1, size, tagname=name)` (`Engine.pixels`). Windows now; Mac (`shm_open`, name `/rostrum2d-<pid>-<n>`) still refused with a message. |
| `{"frame": {"t": 1.25, "pixels": true, "scale": 0.5}}` | as above, `width` / `height` (and `shm`'s) the smaller size | A smaller live-canvas frame, for playing: the same scene, laid out once at the comp's size, drawn through a view scale of `scale` × the comp's size (round(w · scale) × round(h · scale)). Nothing is laid out again, so text and layout are identical; blur, glow and shadow radii are in comp pixels and shrink with the picture. `scale` is 1 (the default), 0.5 or 0.25; any other value, or `scale` ≠ 1 on anything but a `pixels` frame (a picture, `rgba`, scopes, an export), is refused. A smaller frame writes nothing to the comp cache. The screen uses it only while playing; a paused frame and every export are full size. |
| `{"export": {"start"?, "end"?, "encode": {…ffmpeg…}, "file"?, "images"?, "progress"?}}` | `{"ok": true, "frames": 90, "timing"}` | Every frame from `start` (default 0) to `end` (default the comp's duration) at the comp's fps, into the encoder; `file` is checked to exist and not be empty afterwards. Or `"images": "C:\…\f-{frame}.png"`: each frame to a picture. With `"progress": true` a line `{"progress": i, "of": n}` comes after each frame, before the reply. |
| `{"edit": [{"id": "title", "props"?: {"x": 700}, "anim"?: {"y": [keys] \| null}}, …]}` | `{"ok": true, "edits": n}` | Small changes to the held scene without resending it (a drag). **All or nothing**: the whole list is checked as a load is, and nothing is applied if any part fails. |
| `{"frame": {"t": 1.25, "pixels": true, "view": {"x": 1241, "y": 231, "w": 318, "h": 138, "scale": 4}}}` | as above, `width` / `height` = round(w · scale) × round(h · scale) | Part of the comp drawn larger: the zoomed-in canvas past Full, sharp. The comp px crop x..x+w, y..y+h (inside the comp), drawn through the same paint as any frame with a view of `scale` (above 0, at most 64; the picture at most 8192 px a side): nothing laid out again, nothing preview-only. Only on `pixels` frames, not with `scale`; writes nothing to the comp cache. |
| `{"frame": {"t": 1.25, "pixels": true, "world": {"x": -400, "y": -120, "w": 2900, "h": 1500, "scale": 0.4}}}` | as `pixels`, `width` / `height` = round(w · scale) × round(h · scale), plus `"quad": [[x, y] × 4]` (the frame's corners in world px at t: top-left, top-right, bottom-right, bottom-left), `"world"` (the rectangle) and `"pass"` (`"world"`, `"export"` or `"both"`) | The world picture (camera spec § 8.4; FRAME.md › The world view): any world px rectangle of the endless canvas, at any `scale` (above 0, at most 64; at most 8192 px a side). Layers are placed by the world view's maths (§ 8.3), so page px are world px; the background fills the rectangle; a layer wholly outside it is not drawn. The frame's quad holds the export's own picture of the same time (whole-picture effects, motion blur), drawn in a second set of surfaces and laid in, so the inside of the outline is the export. A frame at home and not motion-blurred: one pass (the world page; inside the frame it equals the export); a rectangle inside an upright frame: the export's `view` crop alone. With `boxes`, boxes in world px; with `place`, places in world px. The stage's clip at the frame is lifted only while the world is drawn: exports stay byte for byte. Writes nothing to the comp cache. Only on `pixels` frames. |
| `{"frame": {"t": 1.25, …, "place": ["card"]}}` | as the frame, plus `"place": {…}` as `place`'s `layers` | The places of those layers in the frame just drawn (a layer it doesn't draw is left out): the screen's edge while painting follows the picture. |
| `{"place": {"t": 1.25, "ids": ["card"]}}` | `{"ok": true, "layers": {"card": {"m": [9 numbers], "w", "h", "edge": "M… L… Z"}}}` | Where each layer is drawn at `t`, from the page laid out as the frame draws it (through its parent groups, the camera and 3D tilt): `m` maps its own px to comp px as a 3×3 projective matrix, row-major ((x', y', w') = m (x, y, 1), then x'/w', y'/w'); `w` × `h` its own box (the box its paint is stretched over); `edge` its true outline in comp px, flattened (M / L / Z): a shape's rounded corners or ellipse, an image's or video's rounded box, a path's fill and stroke outline, a text's letters; any other layer its box. A layer not drawn at `t` (hidden, out of its time, fully see-through, unknown) is refused, naming it. Painting's one mapping (`rostrum2d/placement.py`: the pen and `paint.stroke` / `paint.fill` in comp px invert `m`). | With `"world": {"x", "y", "w", "h"}`: where the canvas's world view draws each layer (world px, camera spec § 8.3).
| `{"bones": {"t": 1.25}}` | `{"ok": true, "rigs": {"<rig id>": {"bones": {"<id>": {"x", "y", "tipX", "tipY", "angle"}}, "iks": {"<id>": {"targetX", "targetY", "gap", "bones"}}}}}` | Every rig's posed bones (pivot, tip, angle) and each IK's (held) target and how far its tip misses it (two-bone and long chains alike; `bones` = the chain's bones, top first), at `t`, in comp px (tilt left out). The agents' eyes on a character ([`RIG.md`](RIG.md)). |
| `{"outline": {"id": "p", "t": 0.5}}` | `{"ok": true, "d": "M …"}` (`d` null for an even stroke, "" when nothing shows) | A path's varied stroke (tapers, width profile) as the filled outline the stage draws, in the path's px: the Lottie export carries it as a fill (`rostrum2d/io/lottie_outline.py`). |
| `{"measure": {"items": [{"id": "title", "body", "font", "size", "weight", "stretch", "tracking", "lineHeight", "align", "boxWidth", "italic"?, "features"?, "axes"?, "ligatures"?, "figures"?, "smallCaps"?, "slant"?, "grade"?, "path"?, "pathOffset"?, "pathAlign"?, "pathOverflow"?, "letterDelay"?, "letterSplit"?}, …]}}` | `{"ok": true, "sizes": {"title": [w, h]}}` | Each text's box in its own px (before scale and turn): the box the renderer lays it out in, by the same code that draws it (one line, or `boxWidth` wide and wrapped; letter by letter or on a path, the box its letters are placed in). The fields are the text's evaluated values (no time: evaluate keys first); a type field left out is fields.py's default. The whole list is one round trip and one layout. Needs no scene; with one loaded, its fonts. A font not found, or a field the text doesn't have or with a wrong value, fails as `scene` does, naming the id. Python: `Engine.measure`, cached by `rostrum2d/textsize.py`. |
| `{"shapes": {"items": [{"id": "s", "shape": "star", "w", "h", …the shape's fields}, …]}}` | `{"ok": true, "paths": {"s": {"d": "M…", …}}}` | Each parametric shape (arc, triangle, polygon, star, line, arrow, spiral) as the path it is drawn as: `d` in its own box px plus the path fields its own don't already give (a line or spiral: its stroke from its fill and line). Fields a shape doesn't have are left out, so a document layer goes as it is; a wrong value fails as `scene` does. Needs no scene. Python: `Engine.shapes`, through `ops_path.shape_paths` (Convert to path, combining). |

Errors are `{"error": "…"}` naming the item id and field; the process keeps serving. The engine never draws a frame it couldn't fully understand.

The page-markup requests (`open`, `frame {stage}`, `page`, `finish`) stay in `serve` for the renderer's own tests and proofs; the Python layer no longer uses them.

## 2. The scene

```json
{
  "format": "rostrum-2d-scene", "version": 3,
  "comp": {
    "id": "intro", "type": "comp",
    "props": {"width": 1920, "height": 1080, "fps": 30, "duration": 3.0, "background": "#05050a"},
    "layers": [
      {"id": "frame", "type": "camera",
       "props": {"x": 960, "y": 540, "zoom": 1, "rotation": 0, "homeX": 960, "homeY": 540, "ridePath": "", "…": "…"}},
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
- **The frame** (`type: "camera"`, FRAME.md): what the export shows, the scene's camera. At most one, **first** in the
  comp's own `layers` (Python always sends one); fields `x`, `y` (the world point at its centre), `zoom` (above 0),
  `rotation`, `homeX`, `homeY` (not keyable) and the ride; no `start`, `end`, `effects`, `masks`, `depth`,
  `screenLock`. It is never drawn. Each top-level layer is seen through it by its `depth` (`screenLock`: pinned to it),
  wrapped in one `cam~<id>` div with one matrix, **only when the frame ever leaves home** (a key on its move, a ride, a
  still value away from home, or home away from the output centre); otherwise the page is byte for byte the page of a
  scene without it. Refused when the scene loads: two frames, a frame not first or inside a group or rig, effects or
  masks on it, a zoom of 0 or less in any key.
- **Layers draw in list order**: the first is at the bottom. A `group` has its own `layers`, drawn inside its box.
- `effects` and `masks` belong to the layer; effects, masks and layers may each have `anim`.
- Ids are unique in the scene. Times are **seconds**; lengths are **px** in the composition's frame; angles **degrees**; colours `#rrggbb`, or `#rrggbbaa` (see-through; keys mix the alpha too; a gradient stop multiplies it into its `opacity`).
- Produced by `rostrum2d.scene.describe(doc.data, comp_id)`.
- **`fonts`** (optional, top level, beside `comp`): `{"Family": "D:/My Film/fonts/Display.ttf", …}` (absolute paths), the project's own fonts. They win over the app's and the computer's; each file is checked when the scene loads. The `scene` reply lists the families the scene's texts use (`fonts`); `{"fonts": {}}` lists every family a text may name: `{"ok": true, "families": [{"family", "source": "shipped" | "project" | "installed", "weights", "range", "variable", "italic", "upright", "files"}], "aliases": […]}` (also `rostrum2d-render fonts`).
- **`drawing`** (added S6, same version): a layer drawn frame by frame with the shared painting kit. `props` has `w`, `h`
  (its box, px) and the usual transform; `frames: [{"at": 0, "src": "C:\…\<key>_800x1000.png"}, …]`, sorted by `at`
  (a frame number). At time `t` the engine shows the `src` of the last frame with `at <= floor(t · fps)`; nothing
  before the first. Each `src` is a straight-alpha RGBA PNG of exactly `w × h`, made once by the painting kit and named by
  its content (never changes under the same name): the engine only reads it, stretched to the box like an image with
  `fit: stretch`. Masks and effects apply as on any layer. Python sends only the drawings that can show: with the
  document's "Draw each frame" off, only the first (`rostrum2d/drawing.py` `shown_frames`).
- **`paint`** (added H29, same version): paint on an element. A `shape`, `text`, `image`, `video` or `path` may carry
  `paint: {"frames": [{"at", "src"}, …], "inside": true}`: its drawings, picked at `t` by the drawing rule above, each
  a straight-alpha PNG of the element's paint canvas, stretched over the element's own box (0, 0)..(w, h) (a text's:
  its laid-out box, the `measure` size) in the layer's transform, so it moves, scales, turns and fades with it. It is
  drawn over the element's own look, before masks and effects (they see element and paint together; a shadow then
  follows both, as a drop shadow; a glow in its own colours glows the paint too). `inside` true: drawn source-atop,
  so it shows only where the element itself is drawn (its fill, letters, picture, stroke); false: over the whole box.
- **`fillFrames`** (added P2, version 3): a painted fill. A `shape` or `path` may carry `fillFrames: [{"at", "src"}, …]`:
  the drawings of the painting that fills it (comp frame numbers, already shifted by the layer's start and its Start at
  drawing, a boil's loop written out by Python), picked at `t` by the drawing rule above; the one showing is the layer's
  `fillPicture` at that frame (§ 4 › Picture and painted fill). Layers sharing a painting name the same files: one
  picture per drawing, decoded once. Every file must exist.
- **`path`** (added S8, same version): a vector path. `props.d` is SVG path data with absolute commands only — `M x y`,
  `L x y`, `C x1 y1 x2 y2 x y`, `Z` (numbers separated by spaces or commas; a command's numbers may repeat; extra pairs
  after `M` are lines; after `Z` a new `M` is needed) — in the layer's own px from its box's top-left. `w × h` is its box
  (at least 1 px; the anchor and gradients use it; the curve may reach outside it and is still drawn). A `d` the engine
  can't read is refused, naming `id.d`. `d` may be keyed (keys carry `d`, path data; § 3 Shapes); `w`, `h`, `fillRule`,
  `cap`, `join` are still.
- **`video`** (added S8, same version): a layer with `src`, `w`, `h`, `fit`, `radius`, `offset` (s into the clip),
  `speed`, `loop` and the transform. Like a drawing it carries `frames: [{"at": i, "src": png}, …]`, `i` = 0..n−1 over
  the clip decoded at the comp's fps and at `w × h` (the fit applied at decode). At frame `n = floor(t·fps)` the picture
  is `frames[k]`, `k = floor((n − start·fps)·speed + 1e-6) + round_ties_even(offset·fps)`; `loop` is "off" (k held at 0..count−1), "loop" (k wraps, `rem_euclid(count)`) or "pingpong" (there and back, each end
  shown once; `stage_fx.rs fold`, the same rule as `looping.py`). Python decodes once with the `ffmpeg` program into a cache
  folder keyed by the file's content, size, w × h, fit, fps and decoder version (`rostrum2d/video.py`). `w`, `h`,
  `offset`, `speed` can't be animated. No frames, or a missing picture, is an error. The video's own sound is not read.
- **`rig`** (added H10, same version): a layer with a group's fields (`w`, `h`, `clip`) and `layers`, plus `rig: [...]`,
  its `bone`, `ik` and `bind` items (every field present, `anim` on bone and ik fields). The engine poses the bones and
  moves or bends the bound layers every frame; a bend bind is drawn through a warp mesh. Fields, evaluation and load
  checks: [`RIG.md`](RIG.md).

## 3. Evaluation (the reference is `rostrum2d/evaluate.py` and `easing.py`)

- A field with an `anim` list is **animated**: its keys alone decide its value; the value in `props` is ignored. Otherwise it is still.
- Keys are sorted by `t`. Before the first key and after the last, the value holds. Between key *a* and key *b*, progress `p = ease_a((t − a.t) / (b.t − a.t))` and the value is `a + (b − a) · p`. `p` may leave 0..1 (spring, custom curves overshoot).
- **Spatial handles** (a number key only; in practice `x` and `y`, the path a moving layer or the frame travels): a key may
  carry `out` (the handle leaving it) and `in` (the handle arriving at it), offsets from its value in the field's own
  units (px for x / y). For the stretch from *a* to *b*: if *a* has no `out` and *b* no `in`, the value is
  `a + (b − a) · p` exactly as before. Otherwise it is the cubic Bézier through `a`, `a + a.out`, `b + b.in`, `b` at
  parameter `p` (a missing handle is a third of the way along the straight line: `(b − a)/3` out, `−(b − a)/3` in);
  `p` outside 0..1 carries the curve on. x and y each do this with their own ease, so x and y keys with the same ease
  travel a true 2D Bézier path. Known simplification: the speed along the curve follows `p`, not the distance
  travelled (no re-timing by arc length). `out` / `in` on a colour, shape or width-profile key is refused at load,
  naming the id and field. Reference: `rostrum_core/keys/spatial.py` `between`; engine: `scene/eval.rs` `between`.
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
- **shape:** `rect` (corner `radius`) or `ellipse`; `filled` → `fill` (with `filled` off only the outline is drawn); optional outline (`stroke`, `strokeColor`, `strokeWidth`), drawn inside the box.
- **Picture and painted fill** (shape, path; P2, version 3): with the layer filled and `fillPicture` a file (or
  `fillFrames`' picture now), the fill is, bottom to top: `fillUnder` (a colour; a fully see-through one, `#00000000`, is
  none), then the picture blended onto it by `fillBlend` (`normal`, `multiply`, `screen`, `overlay`; only over a colour
  under it), all of it at `fillOpacity`, clipped to the outline. The picture's size by `fillFit`: `fill` covers the box,
  `fit` sits inside it, `tile` is its own size repeated, each times `fillScale` and centred, then moved by `fillOffsetX`,
  `fillOffsetY` (px, keyable); `stretch` is the box itself (scale and offset don't apply). A tile also turns by
  `fillRotation` (°, keyable) about the box's centre and slides by `fillDriftX`, `fillDriftY` (px per second, in the
  element's axes) × (t − `start`). Tiles are one repeating picture (no seam where tiles meet, at any scale, turn or
  transform). A picture that can't be read, or a scale ≤ 0 (not stretch), is an error naming the layer and field.
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
- **Solid fill opacity:** shape, path and text carry `fillOpacity` (0 … 1, keyable; the fill colour's own alpha times it; the outline is not touched; the scene carries it like every field).
- **text:** `body`, `font` (family name: first the scene's `fonts`, then the app's folder `apps/2d/engine/fonts/` (installed: `fonts\` beside the program; `ROSTRUM2D_FONTS` overrides), then the fonts installed on the computer; each file is listed under its family name and also without a trailing " Variable". A family found nowhere is refused when the scene loads or is edited, never drawn in another font: `subtitle: font "Helvetica Neue" not found: it is not in the project, the app or on this computer; close: …`), `size` px, `weight` (a family of separate weights is drawn in its nearest face, the CSS way; a variable font's axis) and `stretch`, `italic` (the family's italic faces; refused if it has none), optical size = font size automatically, `tracking` (em), `lineHeight`, `align`, `color`, optional outline.
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
  is no layer beside it, the layer itself, the frame, or a layer that has a matte of its own.
- **Riding a path layer** (every layer and the frame, whose `x`, `y` are its centre; `scene/follow.rs`, the same place a text's `pathLayer` is
  resolved): `ridePath` = the id of a `path` layer beside it (same group or comp; "" = none). At every time the layer's
  anchor sits on that path as it is then (its `d`, box and transform: anchor, rotation, scale, stretch; tilt and smear
  are left out): `rideAt` `end` = the tip of the drawn-on part (`trimEnd`, never before `trimStart`), `start` =
  `trimStart`, `along` = `rideAlong` (0..1, keyable) of the whole length, subpath after subpath as trim counts. The
  layer's own `x`, `y` are added as an offset from that point (0, 0 = the anchor on the line); `rideTurn` on adds the
  path's direction there (in the path's parent) to its own `rotation`. A path with no length leaves the layer at its
  own x, y. Refused when the scene loads or is edited: a `ridePath` that names nothing beside it or a layer that isn't a
  path, a path that itself rides one (no chains), or a text that also follows a path layer (`pathLayer`).
- **Blend:** `blend` is one of the modes in `apps/2d/python/rostrum2d/blends.txt`, the one list (Python reads it at
  import; the engine compiles it in, `scene/blends.rs`): normal, multiply, screen, add, overlay, soft-light,
  hard-light, darken, lighten, color-dodge, color-burn, difference, exclusion, hue, saturation, color, luminosity.
  Each is written as the CSS `mix-blend-mode` in that file's second column (`add` = `plus-lighter`) and drawn by Skia's
  blend of the same name. A layer seen through a moving frame or a track matte carries its blend on the wrapper (`blends::style`).
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
- H67: number keys may carry spatial handles `out` / `in` (§ 3). An optional key field: same version; a scene without them evaluates bit for bit as before.
- S7: the Python stopgap is deleted; drawing layers are drawn by the engine; `scene` takes `cpu`, `frame.index` defaults to round(t · fps), `export` takes `images` and `progress`, `edit` is all or nothing.
- S9 (same version): text `pathOverflow`.
- S10 (same version): text `pathLayer` (a text follows a path layer, per frame); a text on a path now takes its colour and outline when not played letter by letter.
- H41 (same version): every layer may ride a path layer (`ridePath`, `rideAt`, `rideAlong`, `rideTurn`), per frame.
- F2 (**version 2**, 2026-10-24): cameras become the scene's one frame (`type: "camera"` with `homeX`, `homeY`, no `start` / `end`; first in the comp's layers; wrappers only when it leaves home); motion blur's sub-frames never cross a jump (a key after a `hold` key) on any field; the `bones` reply's per-rig matrix is `frame` (was `camera`). Python converts older documents' cameras before sending (FRAME.md › Older files).
- P2 (**version 3**, 2026-10-24): shape and path `fillOffsetX`, `fillOffsetY`, `fillRotation`, `fillDriftX`, `fillDriftY`,
  `fillUnder`, `fillBlend` (required fields), `fillOpacity` now also fades a picture fill, `fillFrames` (a painted fill);
  `stretch` no longer takes `fillScale`; tiles are one repeating picture (the 2,000-tile limit is gone).
- E9 (same version): the camera rides a path too; colours may be `#rrggbbaa`; the `shapes` request; an arrow is one merged outline.
- H10 (same version): rig layers, bones, IK, binds; the `bones` request.
- H16 (same version): the `measure` request (a text's laid-out box, for auto layout and the screen's boxes).
- H29 (same version): `paint` on shape, text, image, video and path layers.
- F3 (same version): `frame.world` (the world picture), `place.world`; an export frame's `boxes` each add `world` (where the world view draws it).
- H30 (same version): the `place` request (and `frame.place`); `frame.view` (a crop of the comp at any scale).
- S8 (same version): `path` and `video` layers; text features, axes, text on a path, letter by letter; gradient `conic` and centre; `backdrop`; masks feather / invert / `angle` for every shape; scene `fonts` and the `scene` reply's font list; `pixels` written out.
