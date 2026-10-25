# Rostrum2D engine (Rust)

The renderer that turns a 2D stage (HTML + CSS markup) into frames: **Blitz** lays the page out (Stylo for styles,
Taffy for boxes, Parley for text) and **Skia** paints it on the graphics card. Python drives it through a
long-lived process (`serve`, below). Moved in from the experiment in Stage 2 (Team Hem, brief H5), and four gaps
found by the Blitz-vs-Chrome proof (`proofs/2d-renderer/README.md`) fixed.

## What's here

| Folder | What it is |
|---|---|
| `render/` | `rostrum2d-render`, the renderer program (was the archive's `native/rostrum-motion`) |
| `color/` | `rostrum-color`, the one colour library (working spaces, view transforms, LUTs, grades, scopes; archive `native/rostrum-color`) |
| `stamp/` | `rostrum2d-stamp`, the painting kit's brush dabs laid natively, bit for bit numpy's pixels (H8; `stamp/README.md`) |
| `vendor/` | **our fork** of blitz-dom, blitz-paint, anyrender, anyrender_skia, parley and usvg (pinned versions, patched; every patch is listed in `vendor/PATCHES.md`) |
| `fonts/` | the app's shipped fonts (SIL OFL, each with its licence text; all variable): Inter (+ italic), Roboto Flex, Recursive, Montserrat (+ italic), Source Serif 4 (+ italic), Fraunces (+ italic), JetBrains Mono (+ italic), Caveat |
| `DEPENDENCIES.md` | every crate the engine builds with, and its licence |

**What moved, what stayed behind.** From the archive (tag `experiment-final`): the renderer's source and our
vendored crates, unchanged except for the fixes below. Left behind: the compositing commands (`matte`, `pass`,
comp jobs: the Editor's job, rule 8), the TypeScript timing harness (`proof`), the comp programs in `sksl`, and
the tests that only covered those. `rostrum-color` came over whole; its `comp`, `matte_stats` and `scope` parts
serve compositing and colour scopes and can move to the Editor's side when the Editor needs them. The lock file
went from 810 packages (shared with Sound and 3D in the archive) to 352.

## Build (Windows, this laptop)

```
pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "<team>: 2d engine build" build ^
  cargo build --manifest-path apps\2d\engine\Cargo.toml --profile agent -j 4 -p rostrum2d-render
```

- Output: `apps\2d\engine\target\agent\rostrum2d-render.exe`. A clean build takes about 10 minutes; a change to our
  code or the fork about 10 s – 1.5 min.
- `--profile agent` is the working build (our crates incremental, dependencies fully optimised); `--profile release`
  for shipping. `.cargo/config.toml` links with `rust-lld`.
- Skia comes as prebuilt binaries (skia-bindings downloads them on the first build).
- **Pitfall:** cargo fingerprints path crates by their path relative to the workspace and by file times. A build
  of another copy of this folder into the same `target` (or files with older times) can leave stale vendor crates:
  `cargo clean --profile agent -p blitz-dom -p blitz-paint -p anyrender -p anyrender_skia -p parley -p usvg` fixes it.
- No graphics driver: when no GL context can be made the engine paints on the CPU (same frames, slower) and the reply's `fallback` says so; `ROSTRUM2D_NO_GPU=1` forces that, to try it on a PC that has a GPU.
- Tests (fast, about 1 s once built): `cargo test --manifest-path apps\2d\engine\Cargo.toml --profile agent -p rostrum2d-render`.

## The scene: the engine evaluates every frame (H6)

The engine takes the scene description itself (`../ENGINE_CONTRACT.md` v1) and evaluates keys, easing and
timing per frame in Rust, so the canvas, the look tools and the export draw the same way (rule 5) and Python sends
the scene once. Code: `render/src/scene/` and `render/src/scene_serve.rs`.

| Module | Job |
|---|---|
| `scene/mod.rs` | loads and checks a scene whole: format, version, item types, every field present with the right kind of value, keys, ease names, unique ids, children only where allowed; `edit` |
| `scene/fields.rs` | the item types' field names and kinds (the meaning and defaults stay in `python/rostrum2d/fields.py`; a test checks the two agree) |
| `scene/ease.rs` | the easing curves, ported step for step from `easing.py` |
| `scene/eval.rs` | the animation model from `evaluate.py` / `scene.frame_at`: keys alone decide an animated field; colours mix in linear light (rounded half to even, as Python); layers outside start ≤ t < end are left out |
| `scene/stage.rs` | an evaluated frame → the stage markup (the Python stopgap's `stopgap_html.py`, moved here); images load by path through the asset cache instead of inline copies |
| `scene_serve.rs` | the serve requests below |
| `scene_export.rs` | `export`: a worker thread builds the next frames' stage markup (up to 2 ahead, in order, each checked) while the main thread lays out and paints the current one; any failure stops the export, and the encoder must have taken every frame once, in order (E7) |
| `still_runs.rs` | motion blur: the runs of top-level pieces that are the same in every shutter sample (and blend plainly) painted once and laid over each sample (E2) |
| `render_costs.rs` | the export's `timing.layers`: each top-level layer painted alone on 1 frame in 30 and timed; the 10 costliest, with their effects (E2) |
| `program_cache.rs`, `warmup.rs` | first-use GPU programs: Skia's compiled programs kept on disk (`~/.rostrum/cache/2d-programs/<build>-<gpu>`, 64 MB at most, other builds' folders pruned after 14 days unused); after a whole scene load, when nothing is asked for 150 ms, the page is painted turned and tilted into a scratch surface (plus a motion-blur sum and a turned lay-in) so the first turned or blurred frame does not wait for the driver's compiler |

| Request | Does | Reply |
|---|---|---|
| `{"scene": {…}, "cpu"?: true}` | load or replace the scene; refused whole if anything is unknown (the error names the item and field); every layer's stage is written once at load so a later frame never meets something it can't draw; opens a session the comp's size if none is open at that size | `{"ok": true, "items", "width", "height", "fps", "duration", "gpu", "adapter", "fallback"}` |
| `{"frame": {"t": 1.25, "image"? / "rgba"? / "boxes"? …}}` | the scene at `t` seconds, drawn as any frame (all of `frame`'s outputs); `index` defaults to round(t·fps) so a still equals the exported frame; `timing.evalMs` = keys + easing + markup | as `frame` |
| `{"export": {"start"?, "end"?, "encode": {"program", "args"}, "file"?, "progress"?}}` | every frame start..end at the comp's fps into the encoder (`file` checked to exist and not be empty after); or `"images": "C:\\…\\f-{frame}.png"` for one picture per frame; `progress: true` sends `{"progress": i, "of": n}` lines first | `{"ok": true, "frames", "fps", "code", "timing"}` |
| `{"edit": [{"id", "props"?: {…}, "anim"?: {field: [keys] \| null}}]}` | small changes to the held scene (a drag), checked as a load is, all or nothing | `{"ok": true, "edits": n}` |
| `{"place": {"t", "ids": [id, …]}}` (H30) | where layers are drawn at t, from the laid-out page (`render/src/place.rs`, through groups, camera and tilt): own px -> comp px as a 3×3 matrix, the own box, the true edge as path data; also `frame.place` | `{"ok": true, "layers": {id: {"m", "w", "h", "edge"}}}` |

The page requests (`open`, `page`, `frame {stage}`) still work; after an `open` or `page`, send the scene again.

**Incremental.** A frame's stage is applied to the kept page as edits (keep.rs): only the attributes that changed
are restyled and laid out again. Scrubbing Meridian forward: 5 edits a frame; moving one layer (`edit`) and
drawing the same time again: 1 edit. Paint is still the whole frame (Skia redraws every layer); that is where
the time goes (below).

**Tests** (`cargo test … -p rostrum2d-render scene::`, under a second): `render/tests/scene/reference.json` is
written by `make_reference.py` from the Python layer's own evaluator; the engine must give the same ease values
(1e-12), the same field table, the same values for a keyed scene at ten times (1e-9) and the same drawn frame
(pixel for pixel), and must refuse unknown names. **Re-run `make_reference.py` when `fields.py`, `easing.py`,
`evaluate.py` or the stage writer change** (S6's drawing layers will then fail the field-table test until the
engine draws them: on purpose).

**Measured (H6, 1920×1080, RTX 3050 shared, `C:\Users\Sam\.rostrum\waves\results\stage2\2d-engine\timings.json`).** Pixels: the Rust and
Python evaluators give identical frames, all 90 of Meridian and all 180 of the P-2D shot. Per frame, median:

| | Meridian (30 fps) | P-2D shot as a scene (60 fps) |
|---|---|---|
| evaluate + write the stage: Rust / Python | 0.18 / 0.46 ms | 0.19 / 0.57 ms |
| scrub forward, raw RGBA round trip (Rust) | 35.6 ms (diff 0.44, layout 0.38, paint 31.5) | 39.1 ms (paint 34.4) |
| scrub, random jumps (Rust) | 38.4 ms, worst 61 | 45.7 ms, worst 87 |
| one layer dragged (`edit` + frame) | 37.9 ms, 1 edit | 31.0 ms, 1 edit |
| export to H.264 (Rust / Python) | 40.4 / 46.0 ms a frame | 35.1 / 39.0 ms a frame |
| scene load (opens the GPU session and page) | 390 ms | 376 ms |

Evaluation is now well under 1 % of a frame; the rest is Skia painting the blurs and glows. The scrub numbers
include sending 8 MB of RGBA through the pipe (the contract's later `pixels` / shared memory frame removes that).

## Same frame whatever came before, pixels to the canvas, the app's fonts (H7)

**A frame is a function of its time alone (rule 5).** Measured first: the same Meridian frame drawn in a fresh
process and after other frames differed by 1–2 levels in up to 100 bytes; on the CPU never; drawing one frame
twice in a row never. Narrowed down step by step (`painter.rs` `gl_context`): clearing every GPU resource each
frame fixed it, clearing the resource cache or the font cache did not; removing every effect did not; removing
the text did. Skia's GPU **glyph atlas** was the source, and only for big letters (a 250 px title drifted; 44 px
text didn't): where a glyph landed in the atlas depended on what was drawn before, and its edge pixels with it.
Turning off distance-field text, padding atlas glyphs, a bigger atlas or the path-renderer switches changed nothing.

The fix: glyphs from 32 px on screen up (`GLYPH_OUTLINE_PX`) are drawn as **outlines** instead of atlas masks.
Two details mattered:

- The outlines are filled by Skia's multisampled path atlas, which keeps nothing between frames. At its default
  4 samples a big letter's edge had 3 in-between levels and stepped visibly, so it is set to **16 samples**: about
  as smooth as the glyph atlas was, and identical cold and warm. (Turning that renderer off gave smooth edges, but
  the drift came back through the triangulating renderer's own cache.)
- Outlines sit at their exact sub-pixel position. Atlas glyphs snapped to whole pixels vertically, which gave a
  1 px jitter on slow moves.

Small text keeps the atlas and its hinting. Paint time changed by less than the run-to-run noise.

- Proof: `render/src/cold_warm_tests.rs` draws text from 14 to 230 px cold, and warm after six other weights and
  positions, and compares bytes. It failed with Skia's old threshold (1,625 bytes differed) and passes now.
  Meridian: all 90 frames drawn fresh and after 40 random jumps are byte-identical.
- Look: `C:\Users\Sam\.rostrum\waves\results\stage2\2d-engine\meridian-title-before-after-h7.png` (before / after,
  zoom ×2). The letters are a hair truer to the font: square stem tops, no grey fringe.

**`pixels`: frames for the live canvas in shared memory** (`render/src/shm.rs`). `{"frame": {"t": 1.25, "pixels": true}}`
writes the frame's output pixels straight into one of two slots of a named block of memory and replies:

```json
{"ok": true, "width": 1920, "height": 1080, "timing": {…},
 "shm": {"name": "Local\rostrum2d-<pid>-<n>", "size": 16588800, "offset": 8294400, "bytes": 8294400,
         "stride": 7680, "format": "rgba8", "seq": 7, "width": 1920, "height": 1080}}
```

- Same bytes as `rgba` (straight-alpha RGBA, or `rgba64le` at depth 16; the same output step as stills and export).
- The slots alternate, so the canvas can read frame n while frame n + 1 is drawn. It must be done with a slot
  before it asks for the frame after next.
- `screen: true`: the screen's own form (`bgra8-premul`: BGRA, premultiplied, Qt's ARGB32_Premultiplied), so the
  canvas shows the frame without converting it on the screen thread (`render/src/handoff.rs`, `pixels.rs to_screen`).
- Only the rows that changed are copied back: a slot holds the frame before last, the GPU keeps the output of what each
  slot holds and compares (`gpu_output.rs`, `gpu_output.glsl`); `timing.rowsRead` counts the rows read.
- `ahead: t2` (playing): the engine draws the frame at `t2` right after answering and starts its output on the GPU;
  the next request for exactly that frame is answered from it (`render/src/serve_ahead.rs`).
- A new block (a new `name`) is made when the frame size changes.
- Reading it: Python `mmap.mmap(-1, size, tagname=name)`; Qt `OpenFileMappingW` + `MapViewOfFile`, or a
  `QImage` over the mapped pointer (no copy).
- Windows now. **Mac route:** `shm_open` + `mmap`, the same layout, name `/rostrum2d-<pid>-<n>`; until then the
  request fails with a message asking for `rgba` instead.

Scrubbing Meridian, round trip per frame as the canvas sees it, median (`…\2d-engine\scrub-pipe-vs-shared-memory-h7.json`):

| | pipe (`rgba`) | shared memory (`pixels`) |
|---|---|---|
| forward, frame after frame | 30.5 ms (worst 55) | **25.7 ms** (worst 49) |
| random jumps | 37.7 ms (worst 62) | **33.7 ms** (worst 57) |

The colour output step on the CPU (F16 → display RGBA) was about 13 ms of every frame; H8 moved it to the GPU,
exactly (below).

## The colour output step on the GPU, exact (H8)

`render/src/gpu_output.rs`, called by `Painter::output_into` (painter.rs). A still, a scrubbed frame, `rgba` and the
canvas's `pixels` go through it whenever the frame is on the GPU and the output step is one curve per channel (the
`channel_table` case: display and linear-display working spaces, the default). Its bytes are **the CPU's, bit for
bit**, so the export (which still converts on its writer thread, off the paint loop) and the preview agree.

- **No float maths on the GPU.** Each channel's half-float bits index a table of integer codes made on the CPU from
  the output step itself (color.rs `gpu_codes`, 65,536 entries, made once per colour setting). For 8 bits with
  dither, an entry holds the code at dither offset 0 and the exact dither value from which the code is one more: the
  CPU's rounding moves a value by at most one code, and only upwards as the offset grows, so one threshold says it
  all. The dither is the same integer hash on both sides. 16-bit frames: the entry is the code.
- **Pixels the table can't answer** (partly transparent: the colour is divided by the alpha first; or a channel not
  finite) are marked by a second small pass (one flag per 32 pixels of a row); the painter reads those rows as stored
  and converts them on the CPU. A frame with a background has none.
- Raw OpenGL 3.3 (Skia's runtime shaders have no integers), so a Mac's GL 4.1 can run it too. If it can't be built,
  frames convert on the CPU (the same bytes); a GL error during a frame fails the frame, loudly.
- Views that mix channels (AgX, ACES 2.0 on ACEScg) have no channel table: stills, export and scrub keep the exact CPU
  step there; only playing frames use the 3D table (`read_output8`, within 1/255), as before.

Measured: Meridian 1080p into shared memory, median per frame, before and after run alternately twice while other
teams used the machine (`C:\Users\Sam\.rostrum\waves\results\stage2\2d-engine\scrub-gpu-output-step-h8.json`,
driver `proofs/2d-engine-output/scrub.py`):

| | before (CPU step) | after (GPU step) |
|---|---|---|
| forward, frame after frame | 54.9 / 60.5 ms (read 15–16, convert 27–29) | **27.4 / 19.0 ms** (read 7–9, convert 0) |
| random jumps | 80.2 / 71.2 ms | **43.8 / 24.6 ms** |
| frame bytes | | **all 90 frames identical** to before |

On a quiet machine H7 measured 25.7 ms forward with the CPU step (13 ms of it converting); that step is now 0 ms and
the read is half the bytes. Test: `painter::tests::exact_gpu_output_step_gives_the_cpus_bytes` (random halves over the
whole range; opaque, transparent and partly transparent rows; odd width; 8 and 16 bits; dither on and off; two working
spaces: every byte equal).

**For Team Sam: contract changes proposed** (`ENGINE_CONTRACT.md` is yours):
1. § 1 `pixels` row: the reply's `shm` object as above (replacing the `…` placeholder).
2. § 2 scene: an optional top-level `"fonts": {"Family": "C:\…\file.ttf"}`, the project's own fonts. They win
   over the app's; each file is checked when the scene loads.
3. § 4 text `font`: resolved by family name. First the scene's `fonts`, then the app's folder
   (`apps/2d/engine/fonts/`; installed: `fonts\` beside the program; `ROSTRUM2D_FONTS` overrides). A font found in
   neither is refused when the scene loads or is edited: `subtitle: font "Helvetica Neue" not found; there is: …`.
4. The `scene` reply gains `"fonts": [family names]`, for agents and the font picker.

**The app's fonts** (`fonts/`, `render/src/scene/fonts.rs`). Each file is listed under its family name (the
typographic family if it has one), and also under that name without a trailing " Variable" ("Inter Variable" is
also "Inter").

- The archive's static Inter Regular is replaced by Inter's **variable** font, so `weight` works on Inter too.
- Roboto Flex moved here from `render/tests/fonts/`; the tests use this copy.
- The page shell embeds the listed fonts. A font file that can't be read is an error; before, it was skipped
  silently.

**One font registry, the computer's fonts too (2026-10-24).** `render/src/scene/fonts.rs` is the one list of every
face a text can name: the project's own fonts, the shipped folder, then the fonts installed on the computer
(`fonts_scan.rs`, through fontdb: Windows `C:\Windows\Fonts` and the person's own fonts folders; Mac `/Library/Fonts`,
`/System/Library/Fonts`, `~/Library/Fonts`), read once per run. A family comes whole from the first place that has
it. Each face carries its weight (a variable font's `wght` range) and slope; `pick` chooses the face a text is drawn
in the CSS way, and the page shell embeds only the faces of the families the scene's texts use, each with its
`font-weight` / `font-style` (a face inside a `.ttc` collection is copied out as a font of its own first). An edit
that changes which families are used puts the shell up again. The text field `italic` draws the family's italic; a
family without one is refused. `rostrum2d-render fonts` and serve's `{"fonts": {}}` list every family (`font_list.rs`:
source, real weights, italic, files), which is what Python's `rostrum2d/fontlist.py`, the font picker and the agents'
`inspect_fonts` read. A family found nowhere is refused when the scene loads, is measured or edited: never drawn in
another font. `ROSTRUM2D_NO_SYSTEM_FONTS=1` leaves the installed fonts out.

## The `serve` interface (what Python talks to)

`rostrum2d-render serve`: one JSON request per line on stdin, one JSON reply per line on stdout. The process
keeps the page, the GPU context and the encoder between frames. The full contract is the header of
`render/src/serve.rs`; in short:

| Request | Does | Reply |
|---|---|---|
| `{"open": {"width", "height", "html", "cpu"?, "depth"?, "color"?, "encode"?}}` | the page shell (styles, fonts, an empty `<div id="rostrum-stage">`); GPU unless `cpu`; `depth: 16` for 16-bit frames; `color` the working space / view; `encode: {"program", "args"}` starts ffmpeg, fed by the renderer itself | `{"ok": true, "gpu", "adapter", "depth", "timing"}` |
| `{"frame": {"stage", "index"?, "image"?, "rgba"?, "encode"?, "boxes"?, "samples"?, "scopes"?}}` | this frame's stage markup, applied as edits to the kept page, laid out and painted; written to `image` (PNG / JPEG), or `rgba` bytes after the reply, or sent to the encoder; `boxes` adds each layer's laid-out box; `samples` = motion-blur sub-frames | `{"ok": true, "timing", "boxes"?, "scopes"?}` |
| `{"page": {"html"}}` | a new page shell on the open session (GPU context and encoder kept) | `{"ok": true, "timing"}` |
| `{"warm": {"urls"}}` | pictures the next frames will use, decoded ahead | `{"ok": true, "queued"}` |
| `{"finish": {}}` | closes the encoder and waits for it | `{"ok": true, "code": 0}` or an error |

Errors reply `{"error": "…"}` and the process keeps serving. A frame whose shader or picture failed is an error,
never a frame drawn without it (rule 6). Other commands: `glyphs` (text as outlines), `styles` (computed CSS per
element), `cube`, `sksl`, `scope` (colour helpers).

The Python layer's handle is `apps/2d/python/rostrum2d/engine.py` (scene requests: `proofs/2d-engine-scene/engine.py.patch`). The proof driver `proofs/2d-renderer/driver/rostrum2d.py` (stdlib only) runs the renderer built in this
checkout, or the one `ROSTRUM2D_RENDER` names. Team Sam's Python layer builds on it.

## What was fixed (H5)

Checked by re-rendering P-2D's frames (`proofs/2d-renderer/driver/stills.py`) and comparing with Chrome 155 by eye
and with SSIM (1.0 = identical). Before = P-2D's run on the archive renderer.

| Frame | Before | After | What changed |
|---|---|---|---|
| `type` (metallic gradient title) | 0.813 | **0.970** | the title is gradient letters instead of a gradient bar; big and small text at Chrome's optical size and width |
| `glass` (frosted card, gradient "48") | 0.963 | **0.992** | gradient numerals |
| `reveal` (gradient "Pro", outlined text) | 0.732 | **0.992** | gradient "Pro"; the outline set in the stylesheet now shows |
| `depth` (tilted slabs under a parent `perspective`) | 0.920 | **0.991** | slabs tilt; blurred ones blur cleanly; the front slab (opacity / blend inside) is drawn |
| `depth-alt` (perspective on each slab) | 0.955 | **0.991** | no sliver, no sharp inner rectangle; paint 162 → 103 ms |
| `type-alt`, `reveal-alt` (SVG-text workaround) | 0.891, 0.929 | 0.909, 0.955 | not a goal (the workaround isn't needed any more); SVG `<text>` still falls back to a serif |

Pictures: `C:\Users\Sam\.rostrum\waves\results\stage2\2d-renderer\<frame>-before-after-vs-chromium.png`.

The fixes, each at the one place it belongs (details in `vendor/PATCHES.md` › Round 14):

1. **Gradient-filled letters** (`background-clip: text`). Stylo built for Servo drops several CSS properties it
   can't hold (`background-clip: text`, `-webkit-text-stroke`, `paint-order`, `url()` filters and masks). A new
   **property shim** (`vendor/blitz-dom/src/css_shim.rs`) copies each such declaration into a registered custom
   property before Stylo parses the text, so Stylo itself cascades it (specificity, order, inheritance or not), from
   stylesheets and `style=""` alike. The background is then painted through the element's glyphs.
   `-webkit-text-stroke` and `url(#…)` filters / masks from a stylesheet work through the same shim.
2. **Automatic optical size**: `font-optical-sizing: auto` sets `opsz` from the font size, unless
   `font-variation-settings` names it; `none` and other axes work too. Two drawing bugs were in the way and are
   fixed: Skia was given variable-font coordinates with the font's `avar` remap applied twice, and any value
   below an axis's default (for example `font-stretch: 88%`) was turned back into the wrong design value, so
   letters drew far narrower than their spacing.
3. **A parent's `perspective`** (and `perspective-origin`, `transform-style: preserve-3d`) reaches its 3D children
   through one matrix that paint, culling and `boxes` all read.
4. **Layers on 3D-tilted elements**: blur, opacity, blend modes and isolation on a tilted element are drawn in the
   element's own plane, then projected, as Chrome does. Before, blur came out cut or with a sharp inner rectangle,
   and any `opacity` or blending child made a tilted card vanish.

Tests (one small check per gap, a second each): `render/src/cliptext_tests.rs`, `opsz_tests.rs`,
`depth_tests.rs`, plus the kept `incremental_tests`, `seam_tests`, `shader_tests`, `tilt_tests`. They use Roboto
Flex (`fonts/`, SIL OFL 1.1) so the glyphs are the same on every machine.

## What's left

- Scene: what the stopgap couldn't draw, the engine refuses the same way (feathered or inverted rect masks, a
  gradient on an image); drawing layers (S6) have their place in `scene/fields.rs` and `scene/stage.rs`
  `content`. Paint is not incremental (Blitz repaints the whole page).
- `pixels` on the Mac (`shm.rs`: `shm_open` + `mmap`). The export could take the GPU output step too (half the bytes to read); today it converts on its writer thread.
- `background-clip: text` on an inline `<span>` (Blitz paints only a span's background colour, never its images).
- SVG `<text>` with web fonts falls back to a serif.
- `backface-visibility`; depth sorting of `preserve-3d` siblings (they paint in page order); a perspective parent
  whose child sits in an anonymous block.
- A layer under perspective whose clip and visible plane are both unbounded (the horizon on screen) still takes the
  old on-screen path.
- The shim doesn't cover the `mask` / `-webkit-mask` shorthands or the `-webkit-text-stroke-width` / `-color`
  longhands yet; a new unparsed property is one row in `css_shim.rs`.
- Mac: the painter opens OpenGL through a hidden Windows window; a Metal or Mac GL path is still to do.
- Upstream: none of the fork's patches have been sent upstream yet.

## Attribution rows

For the manager to add to `ATTRIBUTIONS.md` (8 columns). Every crate and its licence is in `DEPENDENCIES.md`: no
GPL / AGPL / LGPL crate; Stylo and its Servo crates are MPL-2.0 (file-level; we ship them unmodified).

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| Blitz (blitz-dom, blitz-paint, blitz-html, blitz-traits; dom and paint patched) | 0.3.0-beta.3 | MIT OR Apache-2.0 | `apps/2d/engine` (layout and paint) | vendored source (dom, paint) + static | ships | Keep the notice | https://github.com/DioxusLabs/blitz |
| AnyRender, anyrender_skia (patched) | 0.14.0, 0.12.0 | MIT OR Apache-2.0 | `apps/2d/engine` (paint API, Skia backend) | vendored source | ships | Keep the notice | https://github.com/DioxusLabs/anyrender |
| Parley (patched), fontique | 0.12.0 | Apache-2.0 OR MIT | `apps/2d/engine` (text layout) | vendored source / static | ships | Keep the notice | https://github.com/linebender/parley |
| usvg (patched) | 0.48.1 | Apache-2.0 OR MIT | `apps/2d/engine` (SVG) | vendored source | ships | Keep the notice | https://github.com/linebender/resvg |
| Stylo (stylo, stylo_traits, selectors, cssparser and the Servo crates) | 0.22.0 | MPL-2.0 | `apps/2d/engine` (CSS) | static | ships | Keep the notice; changes to MPL files stay MPL and their source is offered (we ship them unmodified) | https://github.com/servo/stylo |
| Taffy | 0.15.0 | MIT | `apps/2d/engine` (box layout) | static | ships | Keep the notice | https://github.com/DioxusLabs/taffy |
| skia-safe / skia-bindings, with Skia's prebuilt binaries | 0.153.3 | MIT (bindings), BSD-3-Clause (Skia) | `apps/2d/engine` (GPU paint) | static | ships | Keep both notices | https://github.com/rust-skia/rust-skia |
| skrifa, harfrust (fontations) | 0.44.0, 0.12.0 | MIT OR Apache-2.0, MIT | `apps/2d/engine` (font outlines, shaping) | static | ships | Keep the notice | https://github.com/googlefonts/fontations |
| glutin | 0.32.3 | Apache-2.0 | `apps/2d/engine` (OpenGL context) | static | ships | Keep the notice | https://github.com/rust-windowing/glutin |
| image, png, jpeg-encoder, exr, half | 0.25.10, 0.18.1, 0.7.1, 1.74.2, 2.7.1 | MIT OR Apache-2.0; jpeg-encoder adds IJG; exr BSD-3-Clause | `apps/2d/engine` (picture files) | static | ships | Keep the notices (IJG: credit the Independent JPEG Group) | https://github.com/image-rs |
| ICU4X crates (icu_*, zerovec, yoke …) | 2.3.x | Unicode-3.0 | `apps/2d/engine` (text segmentation, via Parley) | static | ships | Keep the notice | https://github.com/unicode-org/icu4x |
| Roboto Flex | 3.x (archive copy) | SIL OFL 1.1 | `apps/2d/engine/fonts` (app font; also the tests' font) | data | ships | Keep the OFL text beside it; don't sell the font on its own | https://github.com/googlefonts/roboto-flex |
| Recursive | 1.x (archive copy) | SIL OFL 1.1 | `apps/2d/engine/fonts` (app font) | data | ships | Keep the OFL text beside it; don't sell the font on its own | https://github.com/arrowtype/recursive |
| Inter (variable, InterVariable.ttf) | 4.1 | SIL OFL 1.1 | `apps/2d/engine/fonts` (app font) | data | ships | Keep the OFL text beside it; don't sell the font on its own | https://github.com/rsms/inter |
| OpenEXR (Python bindings, `OpenEXR` on PyPI) | 3.5.2 | BSD-3-Clause (ASWF) | `apps/2d/python/rostrum2d/io/readback.py` (reads an EXR export back to check it), `io` extra | dynamic (Python extension, 2.5 MB) | ships (with the io extra) | Keep the copyright notice | https://pypi.org/project/OpenEXR/ |
