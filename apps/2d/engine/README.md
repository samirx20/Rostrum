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
| `vendor/` | **our fork** of blitz-dom, blitz-paint, anyrender, anyrender_skia, parley and usvg (pinned versions, patched; every patch is listed in `vendor/PATCHES.md`) |
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
- Tests (fast, about 1 s once built): `cargo test --manifest-path apps\2d\engine\Cargo.toml --profile agent -p rostrum2d-render`.

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

The Python handle is `proofs/2d-renderer/driver/rostrum2d.py` (stdlib only). It runs the renderer built in this
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
Flex (`render/tests/fonts/`, SIL OFL 1.1) so the glyphs are the same on every machine.

## What's left

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
| Roboto Flex | 3.x (archive copy) | SIL OFL 1.1 | `apps/2d/engine/render/tests` (test font) | data | dev only | Keep the OFL text beside it; don't sell the font on its own | https://github.com/googlefonts/roboto-flex |
