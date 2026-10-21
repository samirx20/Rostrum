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

## 3. Evaluation (the reference is `rostrum2d/evaluate.py` and `easing.py`)

- A field with an `anim` list is **animated**: its keys alone decide its value; the value in `props` is ignored. Otherwise it is still.
- Keys are sorted by `t`. Before the first key and after the last, the value holds. Between key *a* and key *b*, progress `p = ease_a((t − a.t) / (b.t − a.t))` and the value is `a + (b − a) · p`. `p` may leave 0..1 (spring, custom curves overshoot).
- Numbers: `v`. Colours: `c`, mixed in **linear light** (sRGB decoded, mixed, encoded).
- **Easing** (`ease` on the key that starts the stretch): `linear`; `hold` (stays at *a* until *b*); cubic-beziers `smooth (.25,.1,.25,1)`, `snappy (.16,1,.3,1)`, `natural (.4,0,.2,1)`, `heavy (.25,1,.5,1)`, `easeIn (.42,0,1,1)`, `easeOut (0,0,.58,1)`, `easeInOut (.65,0,.35,1)`; `custom` with `x1 y1 x2 y2`; `spring` with `stiffness`, `damping` (mass 1, the stretch read as one second, released at 0, settling on 1); `bounce` (the standard four-arc bounce).
- A layer is drawn only while `start ≤ t < end`.

## 4. Drawing (what each field means)

- **Transform:** the layer's anchor (`anchorX`, `anchorY`, fractions of its box; 0.5 = centre) sits at (`x`, `y`) in its parent's space. Order: tilt (`tiltX`, `tiltY`, 2.5D, perspective 1600 px per layer), then `rotation`, then scale (`scale·scaleX`, `scale·scaleY`), all about the anchor. Then `opacity`, then `blend` (`normal`, `screen`, `add`, `multiply`, `overlay`, `soft-light`).
- **Box:** shape and image `w × h`; group `w × h` (`clip` hides children outside it); text: its laid-out size (one line, or `boxWidth` wide and wrapped).
- **shape:** `rect` (corner `radius`) or `ellipse`; `fill`; optional outline (`stroke`, `strokeColor`, `strokeWidth`), drawn inside the box.
- **text:** `body`, `font` (family name: first the scene's `fonts`, then the app's folder `apps/2d/engine/fonts/` (installed: `fonts\` beside the program; `ROSTRUM2D_FONTS` overrides); each file is listed under its family name and also without a trailing " Variable". A family found in neither is refused when the scene loads or is edited: `subtitle: font "Helvetica Neue" not found; there is: …`), `size` px, `weight` and `stretch` (variable-font axes), optical size = font size automatically, `tracking` (em), `lineHeight`, `align`, `color`, optional outline.
- **image:** `src` (absolute path), `fit` (`cover`, `contain`, `stretch`), corner `radius`.
- **Order inside a layer:** content → masks → effects. A mask cuts the content; a glow or blur works on what the mask left.
- **mask:** `rect` / `ellipse` at (`x`, `y`, `w`, `h`) in the layer's own px from its top-left; `radius`, `feather` (soft edge, px), `invert`. Several masks intersect.
- **Effects, in list order:** `gradient` fills the layer instead of its colour (a shape's fill, **a text's letters**, a group's background): `linear` at `angle` (CSS convention: 180 = top to bottom) or `radial`; `color1` → (`color3` at `mid` when `middle`) → `color2`. `blur` (`radius` px). `glow`: a blurred copy (`radius`) added behind, `strength` 0..4, the layer's own colours or `color`. `shadow`: offset `dx`, `dy`, softness `radius`, `color`, `strength`.

## 5. Failing loudly

- Unknown `format` / `version`, item `type`, field name, ease name, or a value of the wrong type: the whole `scene` request is refused, naming the id and field.
- A feature the engine can't draw yet is refused the same way — never drawn as something else.

## 6. Versioning

`version` goes up when a field's meaning changes or a required field is added. Adding a new item type or effect with its own fields is a minor addition (same version, the engine refuses it until it knows it). The Python side sends the version it wrote; the engine answers `{"error": "scene version 2; this engine reads 1"}` when it can't read it.

## 7. History

- S5: version 1 written; until the engine took `scene`, Python evaluated each frame and sent page markup (the stopgap).
- H6: the engine evaluates scenes itself, pixel for pixel as the stopgap did (`proofs/2d-engine-scene/README.md`).
- S7: the Python stopgap is deleted; drawing layers are drawn by the engine; `scene` takes `cpu`, `frame.index` defaults to round(t · fps), `export` takes `images` and `progress`, `edit` is all or nothing.
