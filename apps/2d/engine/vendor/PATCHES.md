# Vendored crates: what we patched

The Motion renderer (`docs/NATIVE_ENGINE.md` § Motion renderer) patches six crates from crates.io, copied here unchanged except where marked `Rostrum proof patch` in the source. `Cargo.toml` points `[patch.crates-io]` at them. All six are `MIT OR Apache-2.0`; their licence terms apply to these copies (parley and usvg ship their licence files; the others name them in `Cargo.toml`). Each patch is a candidate to send upstream.

| Crate (version) | Patch | Why |
|---|---|---|
| anyrender 0.14.0 | `PaintScene::push_transform_3d` / `pop_transform_3d` (default no-ops); `filters::images` (a registry of decoded images by id); `FilterEffect::Image`, `set_output` public | 3D transforms and `feImage` had no way through the paint API |
| anyrender_skia 0.12.0 | Base 4×4 matrices: `set_matrix` concatenates the pushed 3D matrix; `FilterEffect::Image` drawn with `image_filters::image`; `SourceAlpha` as an alpha colour matrix | perspective / rotateX / rotateY tilt; SVG filter inputs |
| blitz-dom 0.3.0-beta.3 | `resolve_3d_transform` + `mul4` (the element's transform as a 4×4 with its origin, when not 2D); web fonts also loaded into the SVG font database (`add_svg_font`); `svg_mask_tree` (an SVG `<mask>`'s content as a standalone tree; luminance masks through `luminanceToAlpha`) | Blitz flattened transforms to 2D; SVG `<text>` could not use `@font-face` fonts; `mask-image: url(#mask)` |
| blitz-paint 0.3.0-beta.3 | `svg_filter.rs` (an SVG `<filter>` → AnyRender filter graph: ColorMatrix, ComponentTransfer, Composite, GaussianBlur, DisplacementMap, Morphology, Flood, Offset, Turbulence, Image, Merge); `url_ref_id` (reads `filter` / `mask-image: url(#id)` from the inline style, because Stylo built for Servo cannot hold a url() filter); 3D transforms pushed around an element's painting; `mask-image: url(#id)` drawn from the SVG mask; gradient stops outside [0, 1] widen the gradient line; the gradient-tile cap only skips near-zero tiles | Rostrum's grade, key, depth and mattes are SVG filters; text masks; a 24 px grid on a 1080p frame (~3600 tiles) was silently dropped by a 500-tile cap |
| parley 0.12.0 | The line breaker starts in the root style's `text_wrap_mode` | `white-space: nowrap` around inline-blocks (split text) wrapped anyway |
| usvg 0.48.1 | `pathLength` rescales `stroke-dasharray` and `stroke-dashoffset` to the path's real length | drawOn / trace dashes came out broken |

Not crates, but part of the round-2 comparison (since removed with the Chromium renderer): a `fonts.mjs` inlined the app's Google Fonts into each Chromium-captured page, without which Blitz fell back to Arial.

## Round 3 (speed proof, 2026-10-13)

| Crate | Patch | Why |
|---|---|---|
| blitz-dom + blitz-paint | Inline spans with margin / border / padding get zero-height **spacer inline boxes** at their start and end (`SPACER_START` / `SPACER_END` ids, `TextLayout::span_edges`); their backgrounds cover padding and descendants' runs, and their borders are drawn | Blitz dropped all horizontal margin, padding and border of inline spans (KaTeX spacing, padded highlight words) |
| blitz-dom + blitz-paint | `position: relative` + `top` / `left` on inline spans moves their glyphs, backgrounds and inline-block children (`util::inline_relative_offset`) | ignored on inline spans (raised text, KaTeX nudges) |
| parley | Content-width measurement starts in the root's wrap mode, as the line breaker does (round 2) | under `nowrap`, boxes before any text counted as wrap points, so min-content collapsed (KaTeX delimiters measured 0) |
| blitz-dom | A table's baseline is its first row's when a first-row cell is `vertical-align: baseline` | Taffy's grid fell back to the bottom edge; inline-tables sat too high |

Known open: KaTeX blocks sit ~30 px off inside a flex-centred layer (nested inline-table layout); the formula itself reads right. Still open after round 4; fixed in round 11 (two-row inline-table baselines, inline SVG viewports).

## Round 4 (no browser, speed, blend modes; 2026-10-13)

| Crate | Patch | Why |
|---|---|---|
| anyrender_skia | `gaussian_blur`: above σ 8 the input is halved (bilinear at 2 × 2 centres) until σ fits, blurred with σ / 2^k and scaled back up (`image_filters::matrix_transform`) | saas-launch's 160 px glows: CPU paint 289 → 139 ms a frame; on the GPU Skia already rescales. SSIM vs the full-rate blur 0.997–0.998 |
| anyrender_skia | `path_from_shape` leaves out zero-length segments | Blitz hands a square-cornered box over as a rounded rect whose corner arcs are points; Skia then saw a non-convex path and rasterised its coverage on the CPU (~1 ms per full-frame background). kinetic-type paint 20 → 2–4 ms on the GPU |
| anyrender_skia | `runtime_shader_filter` (X4): a colour program (`half4 main(half4`) is a colour filter, a coordinate shader with `images` gets them as extra pictures: the k-th image drawn into the box moved k box-widths right (nearest) and merged with the input, the sample radius widened to reach them | skia-safe's `RuntimeShaderBuilder` has no `set_child`, so a coordinate shader had one child only; the AOV tools (fog, defocus, vectorBlur) read depth / velocity beside the picture at `p + (k·box.w, 0)` |
| anyrender_skia | `draw_box_shadow` under a perspective matrix: the shape drawn sharp into a layer blurred by `gaussian_blur`, not a mask filter | Skia blurs a mask filter's coverage on the CPU under perspective (saas-launch's tilted panel: ~4 → ~2 ms) |
| blitz-paint | `blend.rs` + `LayerManager::maybe_with_blend_layer` / `maybe_push_blend_layer`: `mix-blend-mode` (all 16 modes; `plus-lighter` as Plus) draws the element as a layer with that blend; a stacking context (transform, opacity, filter, clip-path, `isolation: isolate`, a blend of its own) with a blending element inside is an isolated layer; a layer only for blending is not clipped to the border box | Blitz painted everything `Mix::Normal` and never read `mix-blend-mode` (Motion's `blendMode`). Proof scene `blend` |
| blitz-paint | `render.rs`: an opacity / filter layer on an element with element children and `overflow: visible` is not clipped to its border box | A blurred or fading group cut its children's shadows to its own box (benchmark § 7 #10: a translucent rectangle during a blur-in) |

Not a crate: `rostrum-motion` paints on the discrete GPU of a hybrid laptop (`NvOptimusEnablement` / `AmdPowerXpressRequestHighPerformance` exported, `build.rs`), and Skia clears with draws (`use_draw_instead_of_clear`): on the AMD integrated GPU a hardware clear of a fresh render target was lost, which is why the first frame of a new context dropped a CSS mask (the old workaround painted it twice; removed).

## Round 5 (raster effect stack, 2026-10-14)

Motion's raster looks (`src/engine/effects/`: displace, edgeRough, paper, refract, pixelate, dither, threshold, halftone, misregister, rgbShift, scanlines, blockShift, glitch) are GPU shaders inside the same SVG filter graph as the other effects.

| Crate | Patch | Why |
|---|---|---|
| anyrender | `FilterEffect::RuntimeShader(RuntimeShaderFilter { program, uniforms, sample_radius, grow })`; its `grow` and a dilating `Morphology`'s radius enter `expansion_rect`; `filters::shader_errors` (errors collected during a paint) | a shader primitive had no way through the paint API; dilated outlines and displaced edges were cut at the layer's box |
| anyrender_skia | `RuntimeShader` → `image_filters::runtime_shader_with_options` (child `src` = the input, the sample radius passed on); the SkSL compiled once per process (thread-local cache by source); uniforms set by name and size-checked; a compile or uniform error is recorded, never silently skipped | Skia runtime effects on the GPU |
| blitz-paint | `svg_filter.rs`: `<feshader effect uniforms radius grow>SkSL</feshader>` → `RuntimeShader` (the layer's box as the `box` uniform; `*`-marked uniforms scaled like lengths; the effect's name prefixed to the program for errors); `render.rs`: `backdrop-filter: url(#id)` read as an SVG filter like `filter` | the raster looks; `refract` reads what is behind a layer |

`rostrum-motion serve` fails a frame whose shader failed (`the halftone effect's shader failed to compile: …`), so a broken effect is never exported as a frame without it (AGENTS.md rule 6).

## Round 6 (text paint, glass, shadows; 2026-10-14)

| Crate | Patch | Why |
|---|---|---|
| blitz-paint | `render.rs`: `backdrop-filter` is its own layer, clipped to the (rounded) border box and faded by the element's opacity, drawn before the content; the opacity / filter layer never carries it | the round-4 expanded clip (overflowing children) also applied to the backdrop, so each glass card blurred everything painted before it across the whole canvas; the backdrop was clipped to the bounding rect, not the rounded box |
| anyrender_skia | `draw_glyphs`: the brush alpha multiplies the colour's alpha | `set_alpha_f` replaced it: `color: rgba(…, 0.4)` text drew opaque |
| blitz-paint | `text.rs`: an inline run's `visibility` (not visible: not drawn) and the product of its inline ancestors' `opacity` (up to the inline root, whose own opacity is its layer), for glyphs and inline backgrounds | inline spans' opacity / visibility were ignored (typed text's untyped rest had to be `inline-block` boxes, which wrapped differently) |
| blitz-paint | `text.rs`: CSS `text-shadow` (all shadows, first on top, under all of the element's text; blur as a layer, σ by `filters::shadow_sigma`) | never drawn |
| blitz-paint | `text.rs` + `filters::inline_style_value`: `-webkit-text-stroke` and `paint-order` read from the inline style (Stylo for Servo does not parse them), the stroke drawn as a glyph stroke before or after the fill; inherited declarations resolved once per inline layout | text outlines were missing |
| blitz-paint | `box_shadow.rs`: the corner radius grows with the spread (CSS Backgrounds 3 § Shadow shape, small radii grow less); the blur radius becomes a sigma as Chromium does (`0.288675 r + 0.5`, scaled), inset shadows offset in device px | a spread shadow on a rounded box had the box's tighter corners; shadows were about twice as soft as the GUI's |
| blitz-paint | `svg_filter.rs`: `flood-color` parsed as any CSS colour with its own alpha (times `flood-opacity`); an `feImage` that does not load fails the frame (`shader_errors`) | only hex / rgb() were read and an rgba() alpha was dropped; a missing map image was skipped silently |

Timing (ms/frame, paint + readback, same exports): raster reel 25.8 → 18.9, text test 6.4 → 6.1, glass cards 8.4 → 7.9.

## Round 7 (finishing pack: LUTs, motion blur, 10-bit; 2026-10-14)

| Crate | Patch | Why |
|---|---|---|
| anyrender | `RuntimeShaderFilter.images` (child images by registered id) | a LUT is a table the shader reads; uniforms cannot hold 33³ entries |
| blitz-paint | `svg_filter.rs`: `<feshader images="name href;…">` loads each href like an feImage (a missing one fails the frame) | the grade's LUT step (`src/engine/video/lutShader.ts`) |
| anyrender_skia | a shader with images runs as a runtime **colour filter** (`half4 main(half4 color)`) whose `uniform shader` children are the images, read unfiltered (nearest, clamped); uniforms packed by their offsets | skia-safe's runtime image filter takes one child (the input); colour filters take any number of children |

Not crates (`src/`): `serve` lays the page out without Blitz's incremental layout (`DocumentConfig.incremental = false`; styles and the DOM are still kept). With it, two opacity edits on inline-block letters (`tl.textAnimate`) grew their line by the strut's descent (the inline-block lost its baseline on relayout), so a frame painted after edits sat 41 px above the same markup painted fresh — preview ≠ export, and a motion-blur frame (16 edits) showed a ghost. Full layout costs ~1 ms a frame (0.9 → 1.6 ms on a text scene). The incremental bug itself is left upstream (a candidate fix). `painter.rs` paints into an F16 surface for 10-bit delivery and sums motion-blur sub-frames into a second F16 surface (`accumulate`, Plus blend with weight 1/N); `pixels.rs` reads F16 back as 8- or 16-bit straight alpha.

## Round 8 (Motion pro animation pack: particles, raster warps; 2026-10-14)

| Crate | Patch | Why |
|---|---|---|
| blitz-paint | `particles.rs`: an element with `data-particles` (Rostrum's `<Emitter>`) does not draw its children: each element child is a sprite, painted once into a recorded `anyrender::Scene` and replayed per particle (`sprite x y rotation scaleX scaleY alpha rgb`, element px, around the sprite's centre) with its opacity and colour multiplied in (solid, gradient and glyph brushes; a layer inside the sprite carries the alpha once); `data-trails` (`n width rgb alpha x0 y0 …`) are polylines stroked with a head-to-tail fading gradient, under the sprites | thousands of particles a frame without thousands of DOM elements (one element, numbers in an attribute); sprites stay vectors, crisp at any scale; any layer can be a sprite |
| blitz-paint | `warp.rs` + `render.rs`: an element whose `filter: url(#id)` leads with `<fewarp x y w h cols rows pts>` is painted into a recording as usual (re-entry guarded by `BlitzDomPainter.warping`) and handed to `PaintScene::draw_warped` with the mesh (rest grid over x y w h, each grid point's deformed position, element px) | a raster deform / puppet warp of any layer (image, group, precomp) on the element hook every layer type already has |
| anyrender | `WarpMesh`; `PaintScene::draw_warped(content, mesh)` (default: the content unwarped) | the paint API had no way to draw a scene through a mesh |
| anyrender_skia | `draw_warped`: the recording painted into an offscreen surface made by the canvas (`Canvas::new_surface`: GPU when the canvas is; its colour type, so 10-bit renders stay 10-bit) at the element's on-screen scale (≤ 4096 px), base 3D matrices set aside while it records, then `draw_vertices` (triangles, the snapshot as a linear-sampled decal image shader) under the element's transform | the textured triangle mesh itself; exact at every vertex, no inverse map |

Known limits (both fixed in round 11): a warp inside a warped element drew unwarped (recordings replay through the default `draw_warped`); a warped element's own 3D tilt was not applied to the mesh (the tilt was pushed while recording, which a recording ignored). Particle elements and warps are native-only (the browser GUI shows the children / the unwarped layer).

## Round 10 (grading after the shutter, 2026-10-14)

| Crate | Patch | Why |
|---|---|---|
| anyrender | `PaintScene::draw_held()` (default: false, nothing held) | a way to draw a picture the backend holds (motion blur's summed sub-frames) inside an element's layers |
| anyrender_skia | `SkiaSceneCache.held` (set by the caller around one paint); `draw_held` draws it at device pixels (matrix reset), under whatever layers are pushed | the shutter's sum stays on the GPU (no readback, no re-upload) |
| blitz-paint | `particles.rs` `draw_held` + `render.rs`: an element with `data-shutter-held` draws the held picture in place of its children | the full-picture `<Adjust>`'s filter graph runs once on the average instead of once per sub-frame |

Not crates (`src/`): `painter.rs` keeps which surface holds the last picture (frame, sum, or a held paint into its own F16 surface, read like the sum — drawn into the 8-bit frame surface it truncated, ~1 level darker); `accumulate` weights sub-frames with a float alpha colour matrix (a paint alpha is quantized to 8 bits on the GPU: 14 sub-frames of 18/255 summed to alpha 252, so every motion-blurred frame was 1.2 % transparent); `serve` takes `frame.held`.

## Round 9 (speed pass: incremental layout back on; 2026-10-14)

| Crate | Patch | Why |
|---|---|---|
| blitz-dom | `LayoutData::measured_baselines` (the exact `LayoutInput`, the size and the baselines of a node's last measures, ≤ 8, cleared with its layout cache); `cache_store` records a measure's baselines, `cache_get` puts them back on a measure-cache hit with the same input and size | taffy's measure cache stores sizes only, so a cache hit returned no baselines: an inline-block letter whose cache survived an edit (opacity / transform only) sat on the line's baseline with its whole height above it, and the line grew by the descent — the round-7 bug (41 px), which had forced a full layout every frame. With it fixed `serve` uses incremental layout again (`src/incremental_tests.rs` checks a page edited frame by frame against each frame laid out fresh; the benchmark exports are frame-for-frame identical to full layout) |

Not crates (`src/`): `serve` parses each frame's stage markup into one kept scratch page (`keep::Scratch`: the page's children dropped, the same parser a new document uses) instead of a new document per frame (Stylo's set-up cost more than the parse: diff 3.0 → 1.7 ms a frame); paints submit without waiting for the GPU and read back through two GL pixel buffers one frame behind (`readback.rs`), with the straight-alpha conversion on the encoder's writer thread (`sink.rs`); the GL context is made as the process starts, while the host prepares the render.

## Round 11 (Motion fixes: split-text wrapping, nested / tilted warps, KaTeX, glyphs for the host; 2026-10-14)

| Crate | Patch | Why |
|---|---|---|
| parley | `line_break.rs`: an inline box is a soft wrap opportunity on both sides, each controlled by the `white-space` of the nearest common ancestor of the box and its neighbour (`data::common_wrap_mode`, walking `StyleMetrics::parent`), not by the wrap mode of whatever text came last; the opportunity before a box is marked, and a box that does not fit goes back to the last opportunity (or overflows when there is none) instead of always breaking right before itself. `data.rs`: the content-width measurer uses the same rule | split text (letters as inline-blocks) wrapped mid-word ("over th / e lazy"), or never again after one `white-space: pre` space (a lone "The", then one overflowing line) |
| blitz-dom | `inline.rs`: a shrink-to-fit inline box's width is rounded up to 1/64 px (Chromium's LayoutUnit), not a whole px | every per-letter inline-block grew by up to 1 px, so a split word ran ~2.5 % wider than the same text and wrapped sooner |
| anyrender | `RenderCommand::Warped` / `PushTransform3d` / `PopTransform3d` (a recording keeps `draw_warped` and 3D pushes; replayed as themselves by `append_scene`, `replay_tinted` and `Scene::append_scene`; a 3D matrix recorded under a transform T replays as T · M · T⁻¹) | a warp inside a warped element drew unwarped (the recording replayed through the default `draw_warped`); a 3D tilt inside a recording was dropped |
| blitz-paint | `render.rs`: a raster-warped element's own 3D transform (`element_3d`, split out of `render_element`) is pushed around its mesh, not recorded inside it | the warp is a filter, which applies in the element's own space before its transform: a warped element's tilt was not applied at all |
| blitz-dom | `layout/table.rs` + `mod.rs`: without a baseline-aligned cell in the first row, a table's baseline is the bottom of its first row (the row's cell heights from their latest layout; CSS 2.2 § 17.5.3), not the table's bottom | KaTeX's vlists are two-row inline-tables (the second row is the depth): fractions, limits and radicals sat their depth (~25 px at 60 px) too high in a centred layer |
| blitz-dom | `node/svg.rs` + `construct.rs` + blitz-paint `draw_svg`: an inline `<svg>` with a `viewBox` keeps its source and is parsed again for the box it is drawn in (`SvgImageData::tree_for_box`, cached for the last size): its viewport is its CSS box (SVG 2 § 8.2), so `preserveAspectRatio` (`slice` crops, `meet` letterboxes) maps the viewBox into it | KaTeX's radicals and big delimiters are `width="400em"` SVGs sliced into a narrow box: drawn at their attribute size scaled to fit, they shrank to nothing |
| blitz-dom | `node/serialize.rs`: an inline `<svg>`'s root gets its computed `fill` / `stroke` as presentation attributes (lowest priority; its own attributes still win) | CSS paint (`.katex svg { fill: currentColor }`) never reached usvg: path-only SVGs drew black |

Not crates (`src/`): `glyphs.rs` (`rostrum-motion glyphs`): a page's `[data-layer-id]` elements laid out by Blitz and their glyph runs written as outlines (skrifa, the same font instance and normalized coords the painter draws), in each element's own box — the host's text outlines (src/engine/typography/rendererGlyphs.ts). `skrifa = "=0.44.0"` (already in the lock through parley) is now a direct dependency.

## Round 12 (3D-tilted clipping parents; 2026-10-15)

| Crate | Patch | Why |
|---|---|---|
| blitz-paint | `render.rs`: an element's 3D transform (`element_3d`, now a public free function) is resolved before culling; a tilted element is not culled, and the clip it passes to its descendants starts unbounded (narrowed only by its own overflow clip), because their boxes are in its untilted plane while the incoming clip is where things land. `project_rect_bbox` (a rect through a base 4×4, divided by w) is public too | a `perspective` + `rotateX/Y` panel holds its `translate(-50%, -50%)` in the 4×4, so its children's untilted boxes sit half a panel right and down of where they are drawn; those past the frame's edge in that plane were culled against the frame (saas-launch: the "Publish" button and the "Blog" chip never drawn) |

Not crates (`src/`): `boxes.rs` projects every box, ink, glyph run and overflow clip through the 3D transforms above it (the painter's base matrix, `element_3d` · `project_rect_bbox`), so the rendered checks measure a tilted panel's children where they are drawn, not in its untilted plane. `src/tilt_tests.rs`: a tilted `overflow: hidden` panel whose children's untilted boxes lie past the frame — their boxes against the CSS geometry (within 1 px) and their pixels, the clipped child cut at the panel's edge.

## Round 13 (free-triangle warp meshes, PU3 spike; 2026-10-17)

| Crate | Patch | Why |
|---|---|---|
| anyrender | `WarpMesh` is now any triangle mesh: `points` (deformed, element px), `uvs` (rest positions inside `rest`), `tris` (corner indices); `WarpMesh::grid` builds the old regular grid; `is_valid` | a skinned character's mesh has free vertices, not a regular grid |
| blitz-paint | `warp.rs`: `<fewarp x y w h pts uvs tris>` (no `cols` / `rows`) is a free mesh; the grid form is read as before | the markup side of the same |
| anyrender_skia | `draw_warped` draws any valid mesh with `draw_vertices` (texture coordinates from `uvs`); an invalid mesh draws the layer unwarped | one path for grid and free meshes |

Not crates (`src/`): `warp_tests.rs`. TS side: `src/engine/deform/skinMesh.ts` (linear blend skinning on the CPU), `meshOutline.ts` (the mesh), `rasterWarp.ts` (the primitive).

## Shader failures are loud everywhere (team Sam, p2, 2026-10-17)
| Crate | Change | Why |
|---|---|---|
| anyrender_skia | the runtime colour filter / shader image filter record an error in `shader_errors` when Skia will not build them (colour filter from the data and children, image or shader of a child, image filter), as a compile error already was; `working_space::solid` records one instead of silently falling back to a plain colour | a failed build used to pass the input through (the effect silently missing) |
| rostrum-motion | `Painter::paint` returns the collected `shader_errors` as its `Err` (serve, proof and tests all fail the frame naming the effect and Skia's message) | one place instead of every caller remembering to take them |

## Round 9 (G3 matte seam; 2026-10-17)

| Crate | Patch | Why |
|---|---|---|
| blitz-paint | `svg_filter.rs`: `<feshader … in2="name">` takes a second input | a grade that reads a matte image needs the picture and the matte |
| anyrender_skia | `runtime_blender_filter`: a program `half4 main(half4 m, half4 c)` is a runtime **blender** (`make_for_blender`) in an image-filter blend: `in` is the source `m` (the matte image), `in2` the destination `c` (the picture); uniforms by offset, `rostrumWorking` from the painter, LUT / table images as children | a matted layer's coverage is read per pixel from an image the matte stages made (denoise, erode / dilate, blur): a colour filter has no second input and no neighbours |

## Round 10 (G4 power windows; 2026-10-17)

| Crate | Patch | Why |
|---|---|---|
| anyrender_skia | `runtime_window_filter`: an `<feshader effect="matteWindow">` is a plain runtime **shader** (`make_shader`, uniforms packed by offset) wrapped as a shader image filter (`image_filters::shader`), not a runtime-shader builder image filter | the windows' shader (rostrum-color grade/window_sksl.rs) needs uniform ARRAYS (the windows' parameters and polygon points), which Skia's `RuntimeShaderBuilder` cannot set; it reads no picture |

## Coordinate shaders read the working space (T5 grain, team Hem, 2026-10-17)
`runtime_shader_filter` (scene.rs): a coordinate shader (`half4 main(float2 p)`) that declares `uniform float rostrumWorking` now gets the painter's working space, as colour programs and blenders already did. The comp's `grain` program (rostrum-color `comp/grain.rs`) needs it to add noise in display-referred values in any working space.

## Round 11 (comp matte border; 2026-10-17)

| Crate | Patch | Why |
|---|---|---|
| anyrender | `Filter::region: Option<Rect>` (the crate's own TODO "bounds restricting where the filter applies") | a filter needs its region to crop primitives to |
| blitz-paint | `svg_filter.rs`: a `<filter>` that declares `x / y / width / height` (objectBoundingBox fractions or percentages of the element's box) sets the region; one without stays unbounded | |
| anyrender_skia | `convert_filter_effect`: with a region, every primitive's result is `image_filters::crop`ped to it (transparent outside, the SVG primitive subregion default) | Skia's image filters are unbounded: a colour program returns colour for the transparent outside (the comp's opaque grey mattes read opaque black there), so an erode ate the frame's border and a renormalised blur faded at it (V1: a light line along the right and top borders) |

## Transition masks: the mask format the renderer reads (F4 / F5, moved here from `transitionMask.ts` and the Editor docs, 2026-10-18)
`mask-image: url(#id)` is drawn by blitz-paint from the SVG `<mask>` that blitz-dom's `svg_mask_tree` turns into a standalone SVG tree (rows above). What that reader needs, and what `src/engine/stage/transitionMask.ts` therefore writes:
- **Alpha masks** (`style="mask-type:alpha"`): the shapes' opacity is the coverage, not their luminance. Edge masks of F4 wipes / irises (`transitionKernels.ts` `TransitionMask`) are fed this way; the clip is seen where the mask is opaque.
- **Gradients live inside the mask** and use only lowercase attributes with the default `objectBoundingBox` units: the HTML parser the page goes through does not keep `gradientUnits`' case, so a `gradientUnits="userSpaceOnUse"` would silently turn pixel coordinates into fractions.
- **Geometry is placed with `transform` on shapes**, not with gradient coordinates: a linear ramp is a long rectangle rotated onto the edge's angle, a circle iris a square centred on the iris, so the gradient's isolines are true in pixels. A hard edge still gets a 0.5 px band so it antialiases like a vector edge.
- `maskUnits="userSpaceOnUse"` with `x/y/width/height` of the clip's box; the mask's children are the only content read.

## X6 region of interest per node (team Hem R1, 2026-10-18)
- `anyrender` `Filter::crops`: per node a region (painter units); `blitz-paint` `svg_filter.rs` reads `data-roi="x0 y0 x1 y1"` (fractions of the box) on any primitive (feMerge: its last composite); `anyrender_skia` `convert_filter_node` crops the node to `region ∩ crop`. Written by `src/engine/comp/compRoi.ts`; never on colour-only steps (docs/phase2/COMP_CORE.md §11).

## Soft clip edges applied once (F7 seam, team Sam R19, 2026-10-20)

| Crate | Patch | Why |
|---|---|---|
| anyrender_skia | `push_clip_layer`: a clip whose edge falls between pixels (any non-rectangle, a rotation / skew / 3D base, or a rectangle off the whole-pixel grid) draws its content into a layer under a hard clip to the pixels the edge touches; `pop_layer` clears outside the shape with the edge's own anti-aliased coverage (an inverse-filled path, `Clear`), so the soft edge is applied once to the finished content. A rectangle on the pixel grid clips as before, with no layer (`clip_on_pixel_grid`) | Skia applies an anti-aliased clip to every draw on its own, so at an edge pixel what is drawn first shows through what is drawn over it (coverage conflation): a video layer's dark `#18181b` background under its frame made every rolling-shutter band's clipped top edge a dark row (10–20 % on flat colour) over a picture that should have matched. Test: `src/seam_tests.rs` (fails without the patch: 102 vs 128 at a seam) |

## feImage pictures kept, bounded (G5 footage, team Hem, 2026-10-21)

| Crate | Patch | Why |
|---|---|---|
| anyrender | `filters::images` registry bounded: past 384 MB the oldest registered pictures go (never the newest 64; blitz-paint's `image_id` registers a dropped one again when a paint names it) | a live session registers a new frame's comp pictures every frame (~26 MB a frame for a footage comp with passes and depth mattes) and kept them all for the life of the process |
| anyrender_skia | `filter_image` (scene.rs): an feImage's Skia image made once per registered picture and kept between paints (at most 48, keyed by id and registry entry) | every use in every paint copied the picture into a new Skia image, which the GPU then uploaded again |

## Comp-cache taps read back after the paint (G6 record, team Hem, 2026-10-21)

| Crate | Patch | Why |
|---|---|---|
| anyrender_skia | `write_tap` (scene.rs) only draws a tapped buffer on the GPU and queues it; `SkiaSceneCache::finish_taps` (called by painter.rs once the paint is submitted) reads them all back and writes each RHALF on a thread of its own, `taps_written` waits for them (serve.rs, before a frame is answered). A tap whose file is already there, or queued twice in one paint, is skipped (the file is named by its content) | each tap was a GPU round trip inside recording plus a 4 MB file write: the footage edit's 12–22 taps a frame made `recordMs` 125–620 ms. Now record 29–62 ms, the writes hidden behind the frame's read-back and conversion; same frames and same tap files byte for byte |

## Raw 8-bit pictures (G10, team Hem, 2026-10-21)

| Crate | Patch | Why |
|---|---|---|
| blitz-dom, blitz-paint | `RGBA8_MAGIC` (`RRGBA8`, u32 width, u32 height, straight sRGB RGBA8): `ImageHandler::parse` and `svg_filter`'s feImage take the pixels as they are, drawn as an untagged 8-bit picture | rostrum-motion assets.rs decodes an 8-bit display picture in a linear working space (playing footage) ahead, off the frame's path, and Skia converts it on the GPU; the encoded PNG was decoded again during layout |

## Round 14 (Stage 2, H5)

| Crate | Patch | Why |
|---|---|---|
| blitz-dom | `stylo_to_parley::font_variations(font_styles, font_size)`: `font-variation-settings` plus `opsz` = the font size in CSS px under `font-optical-sizing: auto` (the initial value; Stylo's servo build parses `auto` / `none`), unless the settings name `opsz` (explicit wins). Layout (`style`) and font metrics (`font_metrics.rs`, `ch` / `ic` / `ex`) read this one list | Chrome sets `opsz` from the font size; Blitz left variable fonts at their default `opsz`, so big titles came out lighter and narrower (Roboto Flex at 140 px laid out as opsz 14). Test: `render/src/opsz_tests.rs` |
| anyrender_skia | `get_or_cache_normalized_typeface` (scene.rs) undoes the font's `avar` segment maps (new `avar.rs`) before turning Parley's normalized coords into the design values Skia takes | Parley's coords are already past `avar`; Skia applies `avar` again, so the drawn outlines belonged to another instance than the shaped advances (Roboto Flex remaps `opsz`: opsz 40 was drawn as opsz 83). `avar` version 2's cross-axis part is not inverted |
| anyrender_skia | `get_or_cache_normalized_typeface`: a coordinate below the axis default lerps from the default towards the minimum (upstream lerped from the minimum) | `font-stretch: 88%` (wdth 88) on Roboto Flex drew as wdth ~37: letters far narrower than their shaped advances, in every renderer build since round 1. Test: `opsz_tests.rs` `glyphs_are_drawn_at_the_width_they_were_shaped_at` |
| blitz-dom | `node_3d_transform(node)` (stylo_to_kurbo.rs; with `resolve_perspective`, `affine4`): an element's 3D matrix = its containing block's `perspective` / `perspective-origin` (moved into the element's frame through its offset, minus the block's scroll, and its 2D transform) · its own 3D transform; flattened (z output dropped) unless the containing block is `transform-style: preserve-3d`; a preserve-3d element with no 3D transform of its own carries the perspective on to its 3D descendants | only `transform: perspective(…) rotateY(…)` on the element itself tilted it; a parent's `perspective` was ignored (frames `depth`, `depth-alt`) |
| blitz-paint | `element_3d` reads `blitz_dom::node_3d_transform` | paint, culling and `boxes.rs` (which calls `element_3d`) see the one matrix |
| anyrender_skia | `FlatLayer` (scene.rs `push_flat_layer` / `pop_flat_layer`): every layer under a perspective base matrix (filter, opacity, blend, isolation; not a backdrop filter) draws its content and filter into an offscreen picture of its own untilted plane (affine; region = its clip on the plane ∩ the part of the plane on screen grown by the filter's reach; ≤ 2 picture px per plane px, ≤ 4096 px), then draws that picture through the 3D matrix with the layer's opacity and blend. `draw_box_shadow` under perspective uses it too (the mask blur then runs affine) | Skia ran `filter: blur()` under perspective cut to a sliver or with a sharp inner rectangle, slowly (162 ms); a `saveLayer` opened under perspective came out empty, so a tilted card with `opacity`, `isolation` or a `mix-blend-mode` child vanished (frame `depth`'s front slab). CSS / Chrome draw a 3D element's group in its local plane, then project it. Test: `depth_tests.rs` |
| anyrender_skia | `plane.rs` (new): `visible_in_plane` (the device clip mapped back onto a plane), `in_front` (a rect cut to the visible plane and to w ≥ 1/64), `magnification`. `clip()` and the soft-clip edge cut a rect clip under perspective with `in_front` | a layer clip that reaches behind the viewer (blitz-paint's ±1e7 clip for an `overflow: visible` opacity / filter layer) folded over the horizon when projected |
| blitz-dom | `css_shim.rs` (new), the property shim: every declaration of a property Stylo for Servo cannot hold (`-webkit-text-stroke`, `paint-order`, `background-clip` / `-webkit-background-clip`, `filter`, `backdrop-filter` / `-webkit-`, `mask-image` / `-webkit-`) is copied right after itself into a custom property (`--rostrum-text-stroke` …) before Stylo parses the text: stylesheets (`make_stylesheet`, net.rs linked and `@import`ed sheets, CSSOM `insertRule`), style attributes (`flush_style_attribute`, CSSOM rule `cssText`) and `set_style_property` (one hunk in node/element.rs). The `background` shorthand feeds its layers' clip boxes (`initial` when none is `text`; its `text` becomes `border-box` in the original so Stylo keeps the shorthand). Each custom property is registered at document creation (`CSS.registerProperty`, syntax `*`) with its real property's inheritance; `css_shim::value(styles, Shim)` reads the cascaded value back | Stylo for Servo drops `background-clip: text` (Gecko-only keyword), `-webkit-text-stroke`, `paint-order` and url() filters as parse errors, so a stylesheet rule setting them vanished. Custom properties are cascaded by Stylo itself (specificity, order, `!important`, `var()`, inheritance or not), so no second cascade is written |
| blitz-paint | `filters::url_ref_id` reads the shim (so `filter` / `backdrop-filter` / `mask-image: url(#id)` work from stylesheets); `inline_style_value` (round 6) removed. `text.rs`: `text_stroke` reads `-webkit-text-stroke` / `paint-order` from the run's node through the shim (inherited by Stylo; the ancestor walk `outline_decls` is gone; `<color> <width>` order accepted); `run_placement` (one place for a run's offset, skew, embolden); `draw_text_clip_mask` (the glyphs and their outline in opaque black, where stroke_text draws them) | the outlined text in frame `reveal` was missing: its `-webkit-text-stroke` is in a stylesheet |
| blitz-paint | `render/background.rs`: `LayerClip` (a box or `Text`), `background_clips` (the shim's cascaded list, else Stylo's), `text_clip_group`: text-clipped layers (and the colour, if the last layer's clip is `text`) are drawn in a group whose close draws the element's text as a `Compose::DestIn` mask; `draw_text_mask` covers the element's own inline layout and its in-flow descendants' (anonymous blocks, block children), placed as render_element places them. A text-clipped layer's painting area is the border box | `background-clip: text` filled the whole box (frames `type`, `reveal`: a gradient bar instead of gradient letters). The mask is the drawn glyphs, so one gradient spans the box across every line and the edges anti-alias as the text does |

Not crates (`render/src`): `cliptext_tests.rs` (not yet in main.rs) — a stylesheet `background-clip: text` with a red→blue gradient and `color: transparent` lights only the letters (the box corner is the page, 5–70 % of the box lit, red letters left, blue right) and does not inherit (a child's own background fills its box); a stylesheet `-webkit-text-stroke` on a parent outlines its child span's letters. Not supported yet: `background-clip: text` on an inline `<span>` (blitz paints only a span's background colour, never its images), decorations in the text mask, the `mask` / `-webkit-mask` shorthands and `-webkit-text-stroke-width` / `-color` longhands in the shim.

Not crates (`render/src`): `depth_tests.rs` — a parent's `perspective: 800px` + child `rotateY(40deg)` lands where the child's own `perspective(800px) rotateY(40deg)` does (boxes within 0.5 px, pixels); a tilted card with `filter: blur(8px)` has no sharp step on its middle row / column and about the sharp card's light. Not supported yet: `backface-visibility`, depth sorting / intersection of preserve-3d siblings (they paint in DOM order), grouping properties (opacity, filter …) forcing a preserve-3d element flat, a perspective parent whose child sits in an anonymous block (the block is then the containing block).

## H15 (track mattes; 2026-10-21)
| Crate | Patch | Why |
|---|---|---|
| blitz-paint | `track_matte.rs` + `render.rs` hook: an element with `data-track-matte` (alpha, alphaInverted, luma, lumaInverted) draws its children after the first into an isolated layer, then the first child (the matte) as usual into a `DestIn` / `DestOut` layer; luma over opaque black through a `luminanceToAlpha` colour matrix | a track matte drawn by the same painting as every layer, so any layer type is a matte (the SVG `<mask>` copy of layer drawing drew nothing and is gone) |

## H29 (paint on an element; 2026-10-22)
| Crate | Patch | Why |
|---|---|---|
| blitz-paint | `track_matte.rs`: mode `atop` draws the first child (an element's paint) into a `SrcAtop` layer over the rest (the element) | paint kept inside any element's own pixels (a shape, a text's letters, a picture, a path) by one rule, with no second drawing of the element |

## H17 (rounded masks; 2026-10-22)
| Crate | Patch | Why |
|---|---|---|
| blitz-paint | `render/clip_path.rs`: `clip-path: inset(… round r)` honours its corner radii (per corner, resolved against the inset box, shrunk together when two corners would overlap, as CSS says; an elliptical corner takes its mean radius) | upstream left a `TODO` and drew every rounded inset as a square, so every rounded rect mask (`mask(shape="rect", radius=…)`) on any layer was square: the H16 phone's screen corners stuck out of its body |

## H24 (smaller playing preview; 2026-10-22)
| Crate | Patch | Why |
|---|---|---|
| anyrender_skia | `SkiaSceneCache::set_root_view(scale, x0, y0)` (scene.rs; H24 `set_root_scale`, H30 adds the crop origin): a scale (and the crop's origin) pushed as the bottom entry of `base_3d`, so `set_matrix`, `push_transform_3d`, captures, soft clips and flat layers all draw through it; 1 clears it. `write_tap` already skips any base, so no comp-cache buffer is written from a scaled paint. Under a scale, pixel-grid clips take the soft-clip path (`clip_on_pixel_grid` needs no base) | `frame` with `scale` 0.5 / 0.25 (the live canvas while playing, rostrum-motion painter.rs `set_scale`): the same laid-out page drawn smaller, blur / glow / shadow radii scaling with it, without laying the page out again at another size; H30: `frame` with `view` (a crop of the page at any scale: the zoomed-in canvas drawn sharp) |

## H27 (big comps play faster; 2026-10-22)
| Crate | Patch | Why |
|---|---|---|
| blitz-paint | `ink.rs` + `render.rs`: an opacity / filter layer on an element whose children may overflow it (overflow: visible) covers where its subtree paints (its boxes, grown by box / text shadows, CSS filters, outlines and a font size of glyph overhang), plus 2 device pixels so the clip's edge never meets an edge inside; unbounded as before when that can't be known (a transformed, fixed or SVG descendant, a filter by `url(#id)`) | the round-4 patch made such layers unbounded, so Skia sized each to the whole frame: a 1080p comp of 200 half-transparent layers cleared and composited 200 full frames, ≈ 26 ms of GPU a frame (now ≈ 5 ms); pictures unchanged (≤ 1/255 in blurred shadows, 6/255 on a few pixels) |

## H41 (2026-10-23)

| Crate | Patch | Why |
|---|---|---|
| blitz-paint | `layers.rs`: no 1024-layer cap; every wanted layer is pushed | upstream refused each layer past the 1024th of a frame and drew on without it, so a busy frame's late layers silently lost their blend, opacity, filter or clip (Night Bloom's multiply vignette drew as a white oval over the film for ~1 s at the drop, in look and export). Test: `render/src/blend_budget_tests.rs` |

## E2 (still layers drawn once per motion-blurred frame; 2026-10-23)

| Crate | Patch | Why |
|---|---|---|
| anyrender | `PaintScene::draw_cached(k)` (default false) | a backend's kept picture drawn in a node's place |
| anyrender_skia | `SkiaSceneCache::cached` (the kept pictures) and `draw_cached`: picture `k` at device pixels inside the pushed layers, as `draw_held` | a run of still layers painted once is laid over each motion-blur sample |
| blitz-paint | `runs.rs`: a per-thread paint plan by node (`Run::Skip`, `Run::Cached(k)`), checked at the top of `render_node`; an empty plan (the default) draws everything | the engine paints one run of still layers alone, then each sample with the run's picture in its place (render/src/still_runs.rs), and times each layer alone (render_costs.rs) |

## E3 (glow drawn from the layer's own picture; 2026-10-23)

| Crate | Patch | Why |
|---|---|---|
| anyrender | `PaintScene::push_glow_layer(glows, alpha, blend, transform, clip, filter)` (default false) | a layer whose content is drawn once and laid on as each glow and as itself |
| anyrender_skia | `push_glow_layer` as a `Capture` (X6's content-to-image layer, now `push_capture` / `draw_capture`): each glow is the image blurred, at its strength, `Plus`, under its own clip; then the image with the layer's alpha, blend and filter. Only when the layer's whole reach lies inside the enclosing clip and no base matrix is set (else false) | a glow was a second copy of the layer's markup: laid out and drawn twice (nested glows: 2^depth). Skia's filter layer reads content just off-canvas; a capture doesn't, so edge-crossing layers keep the old drawing |
| blitz-paint | `glow.rs`: `data-glow="radius strength;…"` read; `render_element` draws the content once into `push_glow_layer`, or (no hook, a blend inside reaching the element, an edge-crossing layer) once per glow as its own `Plus` layer, then as itself. `blend.rs`: a glow-marked element counts as blending (`blends_inside`), so its stacking context isolates it as the copy's `plus-lighter` did | the 2D stage (scene/stage.rs) writes a layer once with its glows marked, instead of a blurred copy per glow |

## E4 (glow pictures sized to the layer; 2026-10-23)

| Crate | Patch | Why |
|---|---|---|
| anyrender_skia | `SkiaSceneCache::origin`: where the canvas being drawn on sits in the frame. `push_glow_layer` captures into a picture covering only the layer's reach (its glows' and own clips, cut to the enclosing clip), not the whole canvas; `set_matrix` (through `base()`), `draw_held`, `draw_cached`, `draw_capture`, taps, flat layers and offscreen pictures all draw shifted by it (`draw_at_origin`) | E3 cleared and laid on a full-frame picture for every glowing layer (60 a frame in Night Bloom's garden, × 4 motion-blur samples), which cost what drawing the content once had saved |
| anyrender | `shader_errors`: one list per thread | two paints at once (the engine's tests, run in parallel as cargo runs them) took each other's shader errors |
| anyrender_skia | `skips`: `ROSTRUM2D_PROFILE_SKIP=glow,blur,gradient` leaves those effects out (gradients flat grey, blurs none) | E5, measurement only: time what each effect costs. Unset, nothing changes |
