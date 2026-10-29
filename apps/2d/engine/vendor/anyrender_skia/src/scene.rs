use std::sync::Arc;

use anyrender::filters::component_transfer::TransferFunction;
use anyrender::filters::composite::CompositeOperator;
use anyrender::filters::displacement::ColorChannel;
use anyrender::filters::lighting::{DistantLightSource, LightSource};
use anyrender::filters::morphology::MorphologyOperator;
use anyrender::filters::turbulence::TurbulenceType;
use anyrender::filters::{Filter, FilterEffect, FilterId, FilterInput};
use anyrender::{PaintScene, RenderContext};
use peniko::color::AlphaColor;
use skia_safe::{
    BlendMode as SkBlendMode, BlurStyle, Canvas, Color, ColorSpace, Font, FontArguments,
    FontHinting, FontMgr, FourByteTag, GlyphId, ImageFilter, MaskFilter, Paint, PaintCap, PaintJoin, PaintStyle,
    PathEffect, Point, Point3, RRect, Rect, Typeface,
    canvas::{GlyphPositions, SaveLayerRec},
    font::Edging,
    font_arguments::{VariationPosition, variation_position::Coordinate},
};

use crate::cache::{
    FontCacheKey, FontCacheKeyBorrowed, GenerationalCache, NormalizedTypefaceCacheKey,
    NormalizedTypefaceCacheKeyBorrowed,
};
use crate::scene::sk_peniko::color4f_from_alpha_color;

pub struct SkiaSceneCache {
    /// Base 4x4 matrices (3D transforms) every draw is mapped by: the product, innermost last.
    pub(crate) base_3d: Vec<skia_safe::M44>,
    paint: Paint,
    dash_intervals: Vec<f32>,
    #[cfg(any(target_os = "macos", target_os = "ios"))]
    extracted_font_data: GenerationalCache<(u64, u32), peniko::FontData>,
    typeface: GenerationalCache<(u64, u32), Typeface>,
    normalized_typeface: GenerationalCache<NormalizedTypefaceCacheKey, Typeface>,
    // The `Blob` is held alongside the `Image` because the image references the
    // pixels without owning them (see `image_from_image_data`).
    image_shader: GenerationalCache<u64, (skia_safe::Image, peniko::Blob<u8>)>,
    font: GenerationalCache<FontCacheKey, Font>,
    font_mgr: FontMgr,
    glyph_id_buf: Vec<GlyphId>,
    glyph_pos_buf: Vec<Point>,
    /// Rostrum patch (round 10): the picture `draw_held` draws (set by the caller around one paint).
    pub held: Option<skia_safe::Image>,
    /// Rostrum patch (E2): the pictures `draw_cached` draws (still runs of a motion-blurred frame, set by the caller).
    pub cached: Vec<skia_safe::Image>,
    /// Rostrum patch (streak blur, one paint): where each kept picture's top-left px lies in the frame (device px; none
    /// listed: (0, 0)). A picture made with a `kept_margin` reaches past the frame's edges.
    pub cached_at: Vec<(i32, i32)>,
    /// Rostrum patch (streak blur, one paint): the pictures this paint draws into (`begin_kept`), by number, and the
    /// canvas and origin drawing goes back to (`end_kept`); `take_kept` hands them over once the paint is done.
    kept: Vec<Option<(skia_safe::Surface, (i32, i32))>>,
    kept_prev: Option<(usize, (i32, i32))>,
    /// Rostrum patch (streak blur, one paint): how far past each edge of the canvas the next paint's kept pictures
    /// reach (device px), so a streak that reads past the frame's edge reads the layer there, not the edge px.
    pub kept_margin: i32,
    /// Rostrum patch (X6): one entry per open layer (push_layer / push_clip_layer), `Some` for a layer drawn offscreen
    /// because its filter writes buffers to the comp's node cache.
    captures: Vec<Option<Capture>>,
    /// Rostrum patch (E4): where the canvas being drawn on sits in the frame (device px): (0, 0) for the frame itself, a
    /// glow capture's top-left for its picture, which covers only the layer's reach. Every draw is shifted by it.
    origin: (i32, i32),
    /// Rostrum patch (F7 seam, R19): one entry per open layer, `Some` for a clip layer whose edge falls between pixels:
    /// its content is drawn into a layer under a hard clip to the pixels the edge touches, and the soft edge is
    /// applied once to the finished layer at pop (see `push_clip_layer`).
    soft_clips: Vec<Option<SoftClip>>,
    /// Rostrum patch (round 14, H5): one entry per open layer, `Some` for a filtered layer drawn in its own plane
    /// because the base matrix has perspective (see `FlatLayer`).
    flats: Vec<Option<FlatLayer>>,
    /// Rostrum patch (G6): tapped buffers drawn in this paint, read back and written by `finish_taps` once it is submitted.
    pending_taps: Vec<PendingTap>,
    /// Rostrum patch (G6): tapped buffers being written to disk (`finish_taps`), joined by `taps_written`.
    tap_writes: Vec<std::thread::JoinHandle<Result<(), String>>>,
}

/// Rostrum patch (G6): a tapped buffer drawn on the GPU, waiting to be read back over its region and written to `path`.
struct PendingTap {
    surface: skia_safe::Surface,
    x0: i32,
    y0: i32,
    w: i32,
    h: i32,
    path: String,
}

/// Rostrum patch (F7 seam, R19): a clip shape applied to its layer's content as a whole, at pop.
struct SoftClip {
    transform: kurbo::Affine,
    fill: peniko::Fill,
    path: kurbo::BezPath,
}

/// Rostrum patch (round 14, H5): a filtered layer under a perspective base matrix, drawn as CSS (and Chrome) draw a
/// filtered 3D element: its content and filter into an offscreen picture of its own, untilted plane (an affine
/// matrix, where Skia's filters are exact and fast), then that picture drawn through the 3D matrix. Skia run under
/// perspective cut the layer to a sliver or left a sharp inner rectangle, and blurred slowly (~160 ms).
struct FlatLayer {
    surface: skia_safe::Surface,
    /// The canvas drawing went to before (the painter's, or an enclosing layer's surface's).
    prev: usize,
    /// The base matrices set aside while the layer draws (its own base is the plane -> picture map).
    base_3d: Vec<skia_safe::M44>,
    /// The origin set aside while the layer draws (its picture is its own plane's, at (0, 0)).
    origin: (i32, i32),
    alpha: f32,
    blend: peniko::BlendMode,
    /// Picture px -> plane (the coordinates the base matrix maps to the screen).
    to_plane: kurbo::Affine,
}

/// Rostrum patch (round 14, H5): a device IRect as a kurbo rect.
fn irect_to_kurbo(r: skia_safe::IRect) -> kurbo::Rect {
    kurbo::Rect::new(r.left as f64, r.top as f64, r.right as f64, r.bottom as f64)
}

/// Rostrum patch (X6): a layer whose filter taps buffers (`Filter::taps`). Its content is drawn into a surface of the
/// canvas's size, so the content (the filter's SourceGraphic) is an image: each tapped buffer is computed from it and
/// written, then the whole filter runs on it as `saveLayer` would have run it on the layer.
/// Rostrum patch (E3): a glow layer is captured too: its content drawn once, then laid on as each glow and as itself.
struct Capture {
    surface: skia_safe::Surface,
    /// The canvas drawing went to before (the painter's, or an enclosing capture's surface's).
    prev: usize,
    /// Rostrum patch (E4): the frame px of this capture's (0, 0), and of the canvas before (`SkiaSceneCache::origin`).
    origin: (i32, i32),
    prev_origin: (i32, i32),
    alpha: f32,
    blend: peniko::BlendMode,
    transform: kurbo::Affine,
    fill: peniko::Fill,
    clip_rect: Option<kurbo::Rect>,
    clip_path: kurbo::BezPath,
    filter: Option<Arc<Filter>>,
    /// The glows drawn from the content before it (filter, strength, clip), added (`plus-lighter`).
    glows: Vec<(Arc<Filter>, f32, kurbo::Rect)>,
    /// A glow layer's own clip (None: no layer of its own, the content is laid on as it is).
    body_clip: Option<kurbo::Rect>,
}

impl SkiaSceneCache {
    /// Create a new `SkiaSceneCache`
    pub fn new() -> Self {
        Default::default()
    }

    /// Rostrum patch (H24, H30): a view under every draw of the next paint, as the bottom base matrix: page px (x, y) go
    /// to ((x - x0)·scale, (y - y0)·scale) (a smaller playing preview; a sharp zoomed-in crop of the page). Every matrix
    /// is mapped by it, so nothing is laid out again and blur, glow and shadow radii scale with it (Skia maps filters
    /// and mask blurs through the matrix). Taps are not written under it (`write_tap` skips any base), so a scaled or
    /// cropped picture never enters the comp cache. (1, 0, 0) clears it; call before each paint.
    pub fn set_root_view(&mut self, scale: f32, x0: f32, y0: f32) {
        self.base_3d.clear();
        if (scale, x0, y0) != (1.0, 0.0, 0.0) {
            #[rustfmt::skip]
            let m = [scale, 0.0, 0.0, -x0 * scale, 0.0, scale, 0.0, -y0 * scale, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0];
            self.base_3d.push(skia_safe::M44::row_major(&m));
        }
    }

    /// Rostrum patch (warm-up): any matrix as the view under every draw of the next paint (a turned or tilted one), so
    /// the page's draw kinds are built on the GPU ahead of the frames that first need them (render warmup.rs). Taps are
    /// not written under it, as under `set_root_view`.
    pub fn set_root_matrix(&mut self, m: skia_safe::M44) {
        self.base_3d.clear();
        self.base_3d.push(m);
    }

    /// Increment the generation on the caches. Should be called once per frame.
    /// Rostrum patch (streak blur, one paint): the pictures the last paint drew into (`begin_kept`), in number order
    /// (a number it skipped is None), each with where its top-left px lies in the frame (device px).
    pub fn take_kept(&mut self) -> Vec<Option<(skia_safe::Image, (i32, i32))>> {
        std::mem::take(&mut self.kept).into_iter().map(|s| s.map(|(mut s, at)| (s.image_snapshot(), at))).collect()
    }

    /// Where kept picture `k`'s top-left px lies in the frame (device px).
    fn cached_origin(&self, k: usize) -> (f32, f32) {
        self.cached_at.get(k).map_or((0.0, 0.0), |&(x, y)| (x as f32, y as f32))
    }

    pub fn next_gen(&mut self) {
        self.typeface.next_gen();
        self.normalized_typeface.next_gen();
        self.image_shader.next_gen();
        self.font.next_gen();
    }

    /// Rostrum patch (G6): reads back the buffers the last paint tapped, called once that paint was submitted to the GPU
    /// (one wait for the whole frame instead of a GPU round trip per tap inside recording), and starts writing them
    /// (RHALF), each on a thread of its own, while the caller reads and converts the frame; `taps_written` waits for
    /// them. A failed read-back is recorded with the shader errors. Returns how many were read and the time (ms).
    pub fn finish_taps(&mut self) -> (usize, f64) {
        let t0 = std::time::Instant::now();
        let mut n = 0;
        for mut tap in std::mem::take(&mut self.pending_taps) {
            let ri = skia_safe::ImageInfo::new((tap.w, tap.h), skia_safe::ColorType::RGBAF16, skia_safe::AlphaType::Premul, crate::working_space::get());
            // RHALF (blitz-dom net.rs RHALF_MAGIC): magic, width, height, then RGBA half floats.
            let mut out = vec![0u8; 16 + (tap.w * tap.h * 8) as usize];
            out[..8].copy_from_slice(b"RHALF\0\0\x01");
            out[8..12].copy_from_slice(&(tap.w as u32).to_le_bytes());
            out[12..16].copy_from_slice(&(tap.h as u32).to_le_bytes());
            if !tap.surface.read_pixels(&ri, &mut out[16..], (tap.w * 8) as usize, (tap.x0, tap.y0)) {
                anyrender::filters::shader_errors::push(format!("comp cache: reading back {}", tap.path));
                continue;
            }
            n += 1;
            let path = tap.path;
            self.tap_writes.push(std::thread::spawn(move || {
                let tmp = format!("{path}.{}.tmp", std::process::id());
                std::fs::write(&tmp, &out).and_then(|_| std::fs::rename(&tmp, &path)).map_err(|e| format!("comp cache: writing {path}: {e}"))
            }));
        }
        (n, t0.elapsed().as_secs_f64() * 1000.0)
    }

    /// Rostrum patch (G6): waits until every tapped buffer `finish_taps` started writing is on disk; the first failure.
    pub fn taps_written(&mut self) -> Result<(), String> {
        let mut first = Ok(());
        for h in self.tap_writes.drain(..) {
            let r = h.join().unwrap_or_else(|_| Err("comp cache: a tap writer panicked".into()));
            if first.is_ok() {
                first = r;
            }
        }
        first
    }
}

impl Default for SkiaSceneCache {
    fn default() -> Self {
        Self {
            base_3d: Vec::new(),
            paint: Paint::default(),
            dash_intervals: Vec::new(),
            #[cfg(any(target_os = "macos", target_os = "ios"))]
            extracted_font_data: GenerationalCache::new(10),
            typeface: GenerationalCache::new(1),
            normalized_typeface: GenerationalCache::new(1),
            image_shader: GenerationalCache::new(1),
            font: GenerationalCache::new(10),
            font_mgr: FontMgr::new(),
            glyph_id_buf: Default::default(),
            glyph_pos_buf: Default::default(),
            held: None,
            cached: Vec::new(),
            cached_at: Vec::new(),
            kept: Vec::new(),
            kept_prev: None,
            kept_margin: 0,
            captures: Vec::new(),
            origin: (0, 0),
            soft_clips: Vec::new(),
            flats: Vec::new(),
            pending_taps: Vec::new(),
            tap_writes: Vec::new(),
        }
    }
}

pub struct SkiaScenePainter<'a> {
    pub(crate) inner: &'a Canvas,
    pub(crate) cache: &'a mut SkiaSceneCache,
}

impl SkiaScenePainter<'_> {
    pub fn new<'a>(canvas: &'a Canvas, cache: &'a mut SkiaSceneCache) -> SkiaScenePainter<'a> {
        SkiaScenePainter {
            inner: canvas,
            cache,
        }
    }

    /// Rostrum patch (streak blur): the canvas's device-px rect (origin included), cut to `rect` when given; None when
    /// nothing of it is left (the draw is then skipped).
    fn streak_area(&self, rect: Option<[f32; 4]>) -> Option<skia_safe::Rect> {
        let info = self.inner.image_info();
        let (x0, y0) = (self.cache.origin.0 as f32, self.cache.origin.1 as f32);
        let mut area = skia_safe::Rect::from_xywh(x0, y0, info.width() as f32, info.height() as f32);
        if let Some([l, t, r, b]) = rect {
            if !area.intersect(skia_safe::Rect::new(l, t, r, b)) {
                return None;
            }
        }
        (!area.is_empty()).then_some(area)
    }

    /// Rostrum patch (streak blur): `paint` over `area` (device px, origin included), whatever the layer's matrix.
    fn fill_device(&mut self, area: skia_safe::Rect, paint: &Paint) {
        self.inner.save();
        self.inner.reset_matrix();
        self.inner.translate((-self.cache.origin.0 as f32, -self.cache.origin.1 as f32));
        self.inner.draw_rect(area, paint);
        self.inner.restore();
    }

    /// Rostrum patch (motion-blur buckets): kept picture `k` moved by `m` (as `draw_cached_moved`), over `area` only.
    fn draw_moved_over(&mut self, k: usize, m: [f64; 6], area: skia_safe::Rect, blend: peniko::BlendMode) -> bool {
        let Some(image) = self.cache.cached.get(k).cloned() else { return false };
        let [a, b, c, d, e, f] = m.map(|v| v as f32);
        let at = self.cache.cached_origin(k);
        let local = skia_safe::Matrix::new_all(a, c, e, b, d, f, 0.0, 0.0, 1.0) * skia_safe::Matrix::translate(at);
        let sampling = skia_safe::SamplingOptions::new(skia_safe::FilterMode::Linear, skia_safe::MipmapMode::None);
        let Some(shader) = image.to_shader(Some((skia_safe::TileMode::Clamp, skia_safe::TileMode::Clamp)), sampling, Some(&local)) else { return false };
        let mut paint = Paint::default();
        paint.set_shader(shader);
        paint.set_blend_mode(sk_peniko::blend_mode_from(blend));
        self.fill_device(area, &paint);
        true
    }

    /// Rostrum patch (round 8): `content` replayed under `transform` into a fresh transparent image of w × h px,
    /// made by this canvas (GPU when it is; its colour type, so 16-bit renders stay 16-bit).
    fn paint_offscreen(&mut self, content: &anyrender::Scene, transform: kurbo::Affine, w: f64, h: f64) -> Option<skia_safe::Image> {
        let (w, h) = (w.ceil().clamp(1.0, 8192.0) as i32, h.ceil().clamp(1.0, 8192.0) as i32);
        let base = self.inner.image_info();
        let info = skia_safe::ImageInfo::new((w, h), base.color_type(), skia_safe::AlphaType::Premul, base.color_space());
        crate::layer_census::note("paint_offscreen", w, h);
        let mut surface = self.inner.new_surface(&info, None).or_else(|| skia_safe::surfaces::raster_n32_premul((w, h)))?;
        {
            let canvas = surface.canvas();
            canvas.clear(Color::TRANSPARENT);
            let base_3d = std::mem::take(&mut self.cache.base_3d);
            let origin = std::mem::take(&mut self.cache.origin);
            let mut sub = SkiaScenePainter::new(canvas, &mut *self.cache);
            sub.append_scene(content.clone(), transform);
            self.cache.base_3d = base_3d;
            self.cache.origin = origin;
        }
        Some(surface.image_snapshot())
    }

    fn reset_paint(&mut self) {
        self.cache.paint.reset();
        self.cache.paint.set_anti_alias(true);
    }

    fn set_paint_alpha(&mut self, alpha: f32) {
        self.cache.paint.set_alpha_f(alpha);
    }

    fn set_paint_filter(&mut self, filter: ImageFilter) {
        self.cache.paint.set_image_filter(filter);
    }

    fn set_paint_blend_mode(&mut self, blend_mode: impl Into<peniko::BlendMode>) {
        self.cache
            .paint
            .set_blend_mode(sk_peniko::blend_mode_from(blend_mode.into()));
    }

    fn set_matrix(&self, transform: kurbo::Affine) {
        let m = sk_kurbo::m44_from_affine(transform);
        match self.base() {
            Some(base) => self.inner.set_matrix(&skia_safe::M44::concat(&base, &m)),
            None => self.inner.set_matrix(&m),
        };
    }

    /// The matrix under every draw on this canvas: the canvas's origin shift (E4), then the innermost base matrix.
    fn base(&self) -> Option<skia_safe::M44> {
        let (ox, oy) = self.cache.origin;
        let shift = ((ox, oy) != (0, 0)).then(|| skia_safe::M44::translate(-ox as f32, -oy as f32, 0.0));
        match (shift, self.cache.base_3d.last()) {
            (Some(s), Some(b)) => Some(skia_safe::M44::concat(&s, b)),
            (s, b) => s.or_else(|| b.cloned()),
        }
    }

    /// Rostrum patch (E4): `image`, a picture whose (0, 0) is frame px `at`, drawn at its place on this canvas.
    fn draw_at_origin(&self, image: &skia_safe::Image, at: (i32, i32), paint: Option<&Paint>) {
        self.inner.save();
        self.inner.reset_matrix();
        self.inner.draw_image(image, (at.0 - self.cache.origin.0, at.1 - self.cache.origin.1), paint);
        self.inner.restore();
    }

    fn concat_matrix(&self, transform: kurbo::Affine) {
        self.inner.concat(&sk_kurbo::matrix_from_affine(transform));
    }

    /// Rostrum patch (X6, E3): a layer whose content is drawn into a surface of the canvas's size (`Capture`), so it can be
    /// used as an image when the layer is popped. False when no surface could be made (nothing pushed).
    /// Rostrum patch (E4): with `region` (frame px, inside the enclosing clips), the surface covers only that.
    #[allow(clippy::too_many_arguments)]
    fn push_capture(&mut self, fill: peniko::Fill, blend: peniko::BlendMode, alpha: f32, transform: kurbo::Affine, clip: &impl kurbo::Shape, filter: Option<Arc<Filter>>, glows: Vec<(Arc<Filter>, f32, kurbo::Rect)>, body_clip: Option<kurbo::Rect>, region: Option<skia_safe::IRect>) -> bool {
        let base = self.inner.image_info();
        let (info, origin) = match region {
            Some(r) => (skia_safe::ImageInfo::new((r.width(), r.height()), base.color_type(), skia_safe::AlphaType::Premul, base.color_space()), (r.left, r.top)),
            None => (base, self.cache.origin),
        };
        crate::layer_census::note(if region.is_some() { "capture_region" } else { "capture_full" }, info.width(), info.height());
        let Some(mut surface) = self.inner.new_surface(&info, None) else { return false };
        // The enclosing clips stay: content outside them is not part of the layer, so not of the filter's source.
        let device_clip = self.inner.device_clip_bounds().filter(|_| region.is_none());
        let canvas = surface.canvas() as *const Canvas;
        let prev_origin = std::mem::replace(&mut self.cache.origin, origin);
        let cap = Capture { surface, prev: self.inner as *const Canvas as usize, origin, prev_origin, alpha, blend, transform, fill, clip_rect: clip.as_rect(), clip_path: clip.to_path(0.01), filter, glows, body_clip };
        // SAFETY: the canvas belongs to the surface, which the capture keeps alive until its pop_layer switches back.
        self.inner = unsafe { &*canvas };
        self.inner.clear(Color::TRANSPARENT);
        if let Some(c) = device_clip {
            self.inner.clip_irect(c, None);
        }
        self.inner.save();
        self.set_matrix(transform);
        self.clip(fill, clip);
        self.cache.captures.push(Some(cap));
        self.cache.soft_clips.push(None);
        self.cache.flats.push(None);
        true
    }

    /// A captured layer's content `src` laid on the canvas, with this alpha, blend and filter, under the layer's clip.
    fn draw_capture(&mut self, cap: &Capture, src: &skia_safe::Image, alpha: f32, blend: peniko::BlendMode, filter: Option<&Filter>, clip: Option<kurbo::Rect>) {
        self.reset_paint();
        self.set_paint_alpha(alpha);
        self.set_paint_blend_mode(blend);
        if let Some(filter) = filter.and_then(convert_filter) {
            self.set_paint_filter(filter);
        }
        self.inner.save();
        self.set_matrix(cap.transform);
        match clip {
            Some(r) => self.clip(cap.fill, &r),
            None => self.replay_clip(cap),
        }
        self.inner.save_layer(&SaveLayerRec::default().paint(&self.cache.paint));
        crate::layer_census::note_layer("draw_capture", self.inner);
        self.draw_at_origin(src, cap.origin, None);
        self.inner.restore();
        self.inner.restore();
    }

    fn replay_clip(&self, cap: &Capture) {
        match cap.clip_rect {
            Some(r) => self.clip(cap.fill, &r),
            None => self.clip(cap.fill, &cap.clip_path),
        }
    }

    /// Rostrum patch (X6): one tapped buffer of a captured layer's filter, computed from the layer's content `src` as the
    /// layer computes it, read back over the filter region and written as an RHALF file (premultiplied half float in the
    /// working space: the bytes an feImage of it loads as they are) by `finish_taps`. A region off the pixel grid or
    /// outside the canvas is not written (the next render computes it again).
    fn write_tap(&mut self, cap: &Capture, src: &skia_safe::Image, id: FilterId, path: &str) -> Result<(), String> {
        let filter = cap.filter.as_deref().ok_or("a tapped layer needs its filter")?;
        let region = filter.region.ok_or("a tapped filter needs a filter region")?;
        let (ox, oy) = self.cache.origin;
        let to_device = kurbo::Affine::translate((-ox as f64, -oy as f64)) * cap.transform;
        let dev = to_device.transform_rect_bbox(region);
        let info = self.inner.image_info();
        let (x0, y0, x1, y1) = (dev.x0.round(), dev.y0.round(), dev.x1.round(), dev.y1.round());
        let off_grid = [dev.x0 - x0, dev.y0 - y0, dev.x1 - x1, dev.y1 - y1].iter().any(|d| d.abs() > 1e-3);
        if !self.cache.base_3d.is_empty() || off_grid || x0 < 0.0 || y0 < 0.0 || x1 > info.width() as f64 || y1 > info.height() as f64 || x1 <= x0 || y1 <= y0 {
            return Ok(());
        }
        let mut surface = self.inner.new_surface(&info, None).ok_or("no surface for a tap")?;
        {
            let c = surface.canvas();
            c.clear(Color::TRANSPARENT);
            if let Some(clip) = self.inner.device_clip_bounds() {
                c.clip_irect(clip, None);
            }
            c.set_matrix(&sk_kurbo::m44_from_affine(to_device));
            match cap.clip_rect {
                Some(r) => {
                    c.clip_rect(sk_kurbo::rect_from(r), None, true);
                }
                None => {
                    let mut p = sk_kurbo::path_from_shape(&cap.clip_path);
                    p.set_fill_type(sk_peniko::path_fill_type_from_fill(cap.fill));
                    c.clip_path(&p, None, true);
                }
            }
            CONVERTED.with(|m| m.borrow_mut().clear());
            let f = convert_filter_effect(filter, id);
            CONVERTED.with(|m| m.borrow_mut().clear());
            let mut paint = Paint::default();
            if let Some(f) = f {
                paint.set_image_filter(f);
            }
            c.save_layer(&SaveLayerRec::default().paint(&paint));
            c.reset_matrix();
            c.draw_image(src, (cap.origin.0 - ox, cap.origin.1 - oy), None);
            c.restore();
        }
        // Read back and written once the paint is submitted (`SkiaSceneCache::finish_taps`).
        self.cache.pending_taps.push(PendingTap { surface, x0: x0 as i32, y0: y0 as i32, w: (x1 - x0) as i32, h: (y1 - y0) as i32, path: path.to_string() });
        Ok(())
    }

    /// Rostrum patch (F7 seam, R19): the clip is a rectangle whose device edges lie on whole pixels (no 3D base, no
    /// rotation or skew), so anti-aliasing its edge changes no pixel and a per-draw clip is exact.
    fn clip_on_pixel_grid(&self, transform: kurbo::Affine, clip: &impl kurbo::Shape) -> bool {
        let Some(r) = clip.as_rect() else { return false };
        if !self.cache.base_3d.is_empty() {
            return false;
        }
        let [a, b, c, d, _, _] = transform.as_coeffs();
        if b != 0.0 || c != 0.0 || a == 0.0 || d == 0.0 {
            return false;
        }
        let dev = transform.transform_rect_bbox(r);
        [dev.x0, dev.y0, dev.x1, dev.y1].iter().all(|v| (v - v.round()).abs() < 1e-3)
    }

    /// Rostrum patch (round 14, H5): a rect (in the current matrix's local coordinates) limited to what that matrix
    /// can project: the part of its plane on screen and in front of the viewer (plane.rs). None when the matrix has
    /// no perspective or the rect needs no cut.
    fn in_front(&self, rect: kurbo::Rect) -> Option<kurbo::BezPath> {
        let device = self.inner.device_clip_bounds().map(irect_to_kurbo);
        crate::plane::in_front(&self.inner.local_to_device(), rect, device)
    }

    /// Rostrum patch (round 14, H5): the innermost base matrix when it has perspective.
    fn perspective_base(&self) -> Option<skia_safe::M44> {
        self.base().filter(|b| crate::plane::has_perspective(b))
    }

    /// Rostrum patch (round 14, H5): opens a `FlatLayer` when the base matrix has perspective: drawing goes to an
    /// offscreen picture of the layer's plane, inside a layer that runs `filter` there. The picture covers the
    /// layer's clip on the plane (where `transform` maps `clip`), cut to the part of the plane on screen grown by
    /// `grow` (what the filter pulls in from outside: its expansion rect). False (nothing pushed) without a
    /// perspective base, or when neither the clip nor the visible plane is bounded (the caller layers on screen).
    #[allow(clippy::too_many_arguments)]
    fn push_flat_layer(&mut self, fill: peniko::Fill, blend: peniko::BlendMode, alpha: f32, transform: kurbo::Affine, clip: &impl kurbo::Shape, filter: Option<ImageFilter>, grow: kurbo::Rect) -> bool {
        let Some(base) = self.perspective_base() else { return false };
        let mut region = transform.transform_rect_bbox(clip.bounding_box());
        if let Some(v) = self.inner.device_clip_bounds().and_then(|d| crate::plane::visible_in_plane(&base, irect_to_kurbo(d))) {
            let s = transform.determinant().abs().sqrt();
            region = region.intersect(kurbo::Rect::new(v.x0 - grow.x1 * s, v.y0 - grow.y1 * s, v.x1 - grow.x0 * s, v.y1 - grow.y0 * s));
        }
        if !region.is_finite() || region.width().max(region.height()) > 16384.0 {
            return false;
        }
        // Picture px per plane unit: the plane's largest on-screen magnification (sharp at the near edge), bounded.
        let k = crate::plane::magnification(&base, region).unwrap_or(1.0).clamp(0.5, 2.0).min(4096.0 / region.width().max(region.height()).max(1.0));
        let (w, h) = ((region.width() * k).ceil().max(1.0) as i32, (region.height() * k).ceil().max(1.0) as i32);
        let info = self.inner.image_info();
        let info = skia_safe::ImageInfo::new((w, h), info.color_type(), skia_safe::AlphaType::Premul, info.color_space());
        let Some(mut surface) = self.inner.new_surface(&info, None) else { return false };
        let canvas = surface.canvas() as *const Canvas;
        let to_plane = kurbo::Affine::translate((region.x0, region.y0)) * kurbo::Affine::scale(1.0 / k);
        let base_3d = std::mem::replace(&mut self.cache.base_3d, vec![sk_kurbo::m44_from_affine(to_plane.inverse())]);
        let origin = std::mem::take(&mut self.cache.origin);
        self.cache.flats.push(Some(FlatLayer { surface, prev: self.inner as *const Canvas as usize, base_3d, origin, alpha, blend, to_plane }));
        self.cache.captures.push(None);
        self.cache.soft_clips.push(None);
        // SAFETY: the canvas belongs to the surface, which the flat layer keeps alive until its pop_layer switches back.
        self.inner = unsafe { &*canvas };
        self.inner.clear(Color::TRANSPARENT);
        self.reset_paint();
        if let Some(f) = filter {
            self.set_paint_filter(f);
        }
        self.inner.save();
        self.set_matrix(transform);
        self.clip(fill, clip);
        self.inner.save_layer(&SaveLayerRec::default().paint(&self.cache.paint));
        true
    }

    /// Rostrum patch (round 14, H5): closes a `FlatLayer`: its filtered picture drawn through the base matrix, with
    /// the layer's opacity and blend mode.
    fn pop_flat_layer(&mut self, flat: FlatLayer) {
        self.inner.restore();
        self.inner.restore();
        let mut surface = flat.surface;
        let image = surface.image_snapshot();
        // SAFETY: `prev` is the canvas in use when the layer was pushed, alive for longer than the layer.
        self.inner = unsafe { &*(flat.prev as *const Canvas) };
        self.cache.base_3d = flat.base_3d;
        self.cache.origin = flat.origin;
        self.reset_paint();
        self.set_paint_alpha(flat.alpha);
        self.set_paint_blend_mode(flat.blend);
        self.inner.save();
        self.set_matrix(flat.to_plane);
        let sampling = skia_safe::SamplingOptions::new(skia_safe::FilterMode::Linear, skia_safe::MipmapMode::None);
        self.inner.draw_image_with_sampling_options(&image, (0, 0), sampling, Some(&self.cache.paint));
        self.inner.restore();
    }

    fn clip(&self, fill: peniko::Fill, shape: &impl kurbo::Shape) {
        // Rostrum patch (round 14, H5): under perspective a rect is first cut to what can be projected: one reaching
        // behind the viewer (an `overflow: visible` layer's unbounded clip) folded over the horizon into a sliver.
        if let Some(front) = shape.as_rect().and_then(|r| self.in_front(r)) {
            self.inner.clip_path(&sk_kurbo::path_from_shape(&front), None, true);
            return;
        }
        if let Some(rect) = shape.as_rect() {
            self.inner.clip_rect(sk_kurbo::rect_from(rect), None, true);
        } else if let Some(rrect) = shape.as_rounded_rect() {
            self.inner
                .clip_rrect(sk_kurbo::rrect_from(rrect), None, true);
        } else {
            let mut path = sk_kurbo::path_from_shape(shape);
            path.set_fill_type(sk_peniko::path_fill_type_from_fill(fill));
            self.inner.clip_path(&path, None, true);
        }
    }

    /// Rostrum patch: on a linear surface a solid colour is a float shader uniform (working_space::solid). Ganesh hands a paint
    /// colour inside 0..1 to the GPU as 8-bit vertex colour, which in linear light crushes dark colours
    /// (#101010 came out #0d0d0d); display surfaces keep the plain colour (their 8 bits are the code).
    fn set_solid(&mut self, c: skia_safe::Color4f) {
        if crate::working_space::get().is_some() {
            self.cache.paint.set_color4f(skia_safe::Color4f::new(0.0, 0.0, 0.0, 1.0), None);
            self.cache.paint.set_shader(crate::working_space::solid(c));
        } else {
            self.cache.paint.set_color4f(c, &ColorSpace::new_srgb());
        }
    }

    fn set_paint_brush<'a>(
        &mut self,
        brush: impl Into<anyrender::PaintRef<'a>>,
        brush_transform: Option<kurbo::Affine>,
    ) {
        let brush: anyrender::PaintRef<'a> = brush.into();
        match brush {
            anyrender::Paint::Solid(alpha_color) => self.set_solid(sk_peniko::color4f_from_alpha_color(alpha_color)),
            anyrender::Paint::Gradient(_) if skips("gradient") => {
                self.cache.paint.set_color4f(skia_safe::Color4f::new(0.5, 0.5, 0.5, 0.5), None);
            }
            anyrender::Paint::Gradient(gradient) => match sk_peniko::shader_from_gradient(gradient, brush_transform) {
                Some(shader) => {
                    self.cache.paint.set_shader(shader);
                }
                // Rostrum patch: a gradient of no size (a radial `closest-side` whose centre is on the box's edge) has
                // no shader; CSS draws it as its edge colour: the last stop when padded, else the stops' mean.
                None => self.set_solid(sk_peniko::degenerate_colour(gradient)),
            },
            anyrender::Paint::Image(image_brush) => {
                // Rostrum patch (G7, hem): the image is kept, not the shader: the shader held the first draw's brush
                // transform and sampler, so the same picture drawn at another size or place reused them.
                let id = image_brush.image.data.id();
                let info = sk_peniko::image_info_from_image_data(image_brush.image);
                let kept = self.cache.image_shader.hit(&id).map(|(image, _)| image.clone()).filter(|image| *image.image_info() == info);
                let image = match kept {
                    Some(image) => image,
                    None => {
                        let image = sk_peniko::image_from_image_data(image_brush.image, &info);
                        self.cache.image_shader.insert(id, (image.clone(), image_brush.image.data.clone()));
                        image
                    }
                };
                let image_shader = sk_peniko::shader_from_image_brush(image_brush, image, brush_transform);
                self.cache.paint.set_shader(image_shader);
            }

            // Render unsupported custom paints as transparent
            anyrender::Paint::Resource(_) | anyrender::Paint::Custom(_) => {
                self.cache.paint.set_color4f(
                    sk_peniko::color4f_from_alpha_color(AlphaColor::TRANSPARENT),
                    &ColorSpace::new_srgb(),
                );
            }
        }
    }

    fn set_paint_style<'a>(&mut self, style: impl Into<peniko::StyleRef<'a>>) {
        match style.into() {
            peniko::StyleRef::Fill(_) => {
                self.cache.paint.set_style(PaintStyle::Fill);
            }
            peniko::StyleRef::Stroke(stroke) => {
                self.cache.paint.set_style(PaintStyle::Stroke);
                self.cache.paint.set_stroke(true);
                self.cache.paint.set_stroke_width(stroke.width as f32);
                self.cache.paint.set_stroke_miter(stroke.miter_limit as f32);
                self.cache.paint.set_stroke_join(match stroke.join {
                    kurbo::Join::Bevel => PaintJoin::Bevel,
                    kurbo::Join::Miter => PaintJoin::Miter,
                    kurbo::Join::Round => PaintJoin::Round,
                });
                self.cache.paint.set_stroke_cap(match stroke.start_cap {
                    kurbo::Cap::Butt => PaintCap::Butt,
                    kurbo::Cap::Square => PaintCap::Square,
                    kurbo::Cap::Round => PaintCap::Round,
                });
                if stroke.dash_pattern.is_empty() {
                    self.cache.paint.set_path_effect(None);
                } else {
                    self.cache.dash_intervals.clear();
                    self.cache
                        .dash_intervals
                        .extend(stroke.dash_pattern.iter().map(|dash| *dash as f32));
                    self.cache.paint.set_path_effect(PathEffect::dash(
                        self.cache.dash_intervals.as_slice(),
                        stroke.dash_offset as f32,
                    ));
                }
            }
        }
    }

    fn draw_shape(&mut self, shape: &impl kurbo::Shape) {
        self.draw_shape_with_fill(shape, None);
    }

    fn draw_shape_with_fill(
        &mut self,
        shape: &impl kurbo::Shape,
        fill: impl Into<Option<peniko::Fill>>,
    ) {
        if let Some(rect) = shape.as_rect() {
            self.inner
                .draw_rect(sk_kurbo::rect_from(rect), &self.cache.paint);
        } else if let Some(rrect) = shape.as_rounded_rect() {
            self.inner
                .draw_rrect(sk_kurbo::rrect_from(rrect), &self.cache.paint);
        } else if let Some(line) = shape.as_line() {
            self.inner.draw_line(
                (line.p0.x as f32, line.p0.y as f32),
                (line.p1.x as f32, line.p1.y as f32),
                &self.cache.paint,
            );
        } else if let Some(circle) = shape.as_circle() {
            self.inner.draw_circle(
                (circle.center.x as f32, circle.center.y as f32),
                circle.radius as f32,
                &self.cache.paint,
            );
        } else {
            let mut path = sk_kurbo::path_from_shape(shape);
            if let Some(fill) = fill.into() {
                path.set_fill_type(sk_peniko::path_fill_type_from_fill(fill));
            }
            self.inner.draw_path(&path, &self.cache.paint);
        }
    }

    fn get_or_cache_font(
        &mut self,
        font: &peniko::FontData,
        normalized_coords: &[anyrender::NormalizedCoord],
        font_size: f32,
        hint: bool,
    ) -> Option<Font> {
        let cache_key_borrowed = FontCacheKeyBorrowed {
            typeface_id: font.data.id(),
            typeface_index: font.index,
            normalized_coords,
            font_size: font_size.to_bits(),
            hint,
        };

        if let Some(cached) = self.cache.font.hit(&cache_key_borrowed) {
            return Some(cached.clone());
        }

        let typeface = self.get_or_cache_normalized_typeface(font, normalized_coords)?;

        let cache_key = FontCacheKey {
            typeface_id: font.data.id(),
            typeface_index: font.index,
            normalized_coords: normalized_coords.to_vec(),
            font_size: font_size.to_bits(),
            hint,
        };

        let mut font = Font::from_typeface(typeface, font_size);
        font.set_hinting(if hint {
            FontHinting::Normal
        } else {
            FontHinting::None
        });
        font.set_subpixel(true);
        font.set_edging(Edging::SubpixelAntiAlias);

        self.cache.font.insert(cache_key, font.clone());

        Some(font)
    }

    fn get_or_cache_normalized_typeface(
        &mut self,
        font: &peniko::FontData,
        normalized_coords: &[anyrender::NormalizedCoord],
    ) -> Option<Typeface> {
        fn f2dot14_to_f32(raw_value: i16) -> f32 {
            let int = (raw_value >> 14) as f32;
            let fract = (raw_value & !(!0 << 14)) as f32 / (1 << 14) as f32;
            int + fract
        }

        if normalized_coords.is_empty() {
            return self.get_or_cache_typeface(font);
        }

        let cache_key_borrowed = NormalizedTypefaceCacheKeyBorrowed {
            typeface_id: font.data.id(),
            typeface_index: font.index,
            normalized_coords,
        };

        if let Some(cached) = self.cache.normalized_typeface.hit(&cache_key_borrowed) {
            return Some(cached.clone());
        }

        let typeface = self.get_or_cache_typeface(font)?;

        let axes = typeface.variation_design_parameters().unwrap_or_default();

        if axes.is_empty() {
            return Some(typeface);
        }

        // Rostrum patch (H5): Parley's coords are past the font's `avar`; Skia applies `avar` to design values
        // itself, so undo it first (crate::avar) or shaping and drawing use different instances.
        let avar = typeface
            .copy_table_data(u32::from_be_bytes(*b"avar"))
            .map(|data| crate::avar::segment_maps(&data))
            .unwrap_or_default();
        // Rostrum patch (fonts): each coordinate to the axis of its `fvar` tag, not the one at its place in Skia's
        // list (crate::avar::fvar_tags; the lists' orders can differ).
        let tags = typeface
            .copy_table_data(u32::from_be_bytes(*b"fvar"))
            .map(|data| crate::avar::fvar_tags(&data))
            .unwrap_or_default();
        let coordinates: Vec<Coordinate> = normalized_coords
            .iter()
            .map(|c| f2dot14_to_f32(*c))
            .enumerate()
            .filter_map(|(i, factor)| {
                let axis = match tags.get(i) {
                    Some(tag) => axes.iter().find(|a| a.tag == FourByteTag::new(*tag))?,
                    None => axes.get(i)?,
                };
                Some((axis, avar.get(i).map_or(factor, |map| crate::avar::unmap(map, factor))))
            })
            .filter(|(_, value)| *value != 0.0)
            .map(|(axis, factor)| {
                // Rostrum patch (H5): below the default a coordinate runs from the default towards the minimum
                // (upstream lerped from the minimum, so `font-stretch: 88%` on Roboto Flex drew as wdth ~37).
                let value = if factor < 0.0 {
                    lerp_f32(axis.def, axis.min, -factor)
                } else {
                    lerp_f32(axis.def, axis.max, factor)
                };

                Coordinate {
                    axis: axis.tag,
                    value,
                }
            })
            .collect();
        let variation_position = VariationPosition {
            coordinates: &coordinates,
        };

        let normalized_typeface = typeface
            .clone_with_arguments(
                &FontArguments::new().set_variation_design_position(variation_position),
            )
            .unwrap();

        self.cache.normalized_typeface.insert(
            NormalizedTypefaceCacheKey {
                typeface_id: font.data.id(),
                typeface_index: font.index,
                normalized_coords: normalized_coords.to_vec(),
            },
            normalized_typeface.clone(),
        );

        Some(normalized_typeface)
    }

    fn get_or_cache_typeface<'a>(
        &'a mut self,
        #[allow(unused_mut)] mut font: &'a peniko::FontData,
    ) -> Option<Typeface> {
        let cache_key = (font.data.id(), font.index);

        #[cfg(any(target_os = "macos", target_os = "ios"))]
        #[allow(clippy::map_entry, reason = "Cannot early-return with entry API")]
        {
            use peniko::Blob;
            use std::sync::Arc;

            if let Some(collection) = oaty::Collection::new(font.data.data()) {
                if !self.cache.extracted_font_data.contains_key(&cache_key) {
                    let Some(data) = collection
                        .get_font(font.index)
                        .and_then(|font| font.copy_data())
                    else {
                        eprintln!(
                            "WARNING: failed to extract font {} {}",
                            cache_key.0, cache_key.1
                        );
                        return None;
                    };

                    let blob = Blob::new(Arc::new(data));
                    let font_data = peniko::FontData::new(blob, 0);
                    self.cache.extracted_font_data.insert(cache_key, font_data);
                }
                font = self.cache.extracted_font_data.hit(&cache_key).unwrap()
            }
        }

        if let Some(cached) = self.cache.typeface.hit(&cache_key) {
            return Some(cached.clone());
        }

        let Some(typeface) = self
            .cache
            .font_mgr
            .new_from_bytes(font.data.data(), font.index)
        else {
            let tf = Typeface::make_deserialize(font.data.data(), None);
            eprintln!(
                "WARNING: failed to load font {} {} {} {}",
                cache_key.0,
                cache_key.1,
                tf.is_some(),
                font.index
            );
            return None;
        };

        self.cache.typeface.insert(cache_key, typeface.clone());

        Some(typeface)
    }
}

impl RenderContext for SkiaScenePainter<'_> {}
impl PaintScene for SkiaScenePainter<'_> {
    fn reset(&mut self) {
        self.inner.clear(Color::WHITE);
    }

    fn push_transform_3d(&mut self, m: [f64; 16]) {
        let mf: [f32; 16] = m.map(|v| v as f32);
        let local = skia_safe::M44::row_major(&mf);
        let total = match self.cache.base_3d.last() {
            Some(base) => skia_safe::M44::concat(base, &local),
            None => local,
        };
        self.cache.base_3d.push(total);
    }

    fn pop_transform_3d(&mut self) {
        self.cache.base_3d.pop();
    }

    /// Rostrum patch (round 8): the recorded element painted into an offscreen image at its on-screen
    /// resolution (GPU when the canvas is), then drawn as a textured triangle mesh: each rest grid point's
    /// texel lands at its deformed position.
    /// Rostrum patch (round 10): the held picture at device pixels (its own size is the canvas's), over the layer.
    fn draw_held(&mut self) -> bool {
        let Some(image) = self.cache.held.clone() else { return false };
        self.draw_at_origin(&image, (0, 0), None);
        true
    }

    /// Rostrum patch (E2): kept picture `k` at device pixels, over the layer (as `draw_held`).
    fn draw_cached(&mut self, k: usize) -> bool {
        let Some(image) = self.cache.cached.get(k).cloned() else { return false };
        self.draw_at_origin(&image, (0, 0), None);
        true
    }

    /// Rostrum patch (motion-blur buckets): kept picture `k` drawn moved by `m` (device px), sampled smoothly; past its
    /// edges it is stretched (clamped), so a few px the move uncovers at the frame's edge are its edge px, not a gap.
    fn draw_cached_moved(&mut self, k: usize, m: [f64; 6]) -> bool {
        let Some(area) = self.streak_area(None) else { return true };
        self.draw_moved_over(k, m, area, peniko::BlendMode::default())
    }

    /// Rostrum patch (streak blur): kept picture `k` averaged over `moves` (each as `draw_cached_moved`'s, premultiplied,
    /// sampled smoothly and stretched past its edges) by one runtime shader, in place of a copy drawn per move; only
    /// over `rect` (device px as the canvas's own rect, origin included) when given, nothing when it misses the canvas.
    fn draw_cached_streak(&mut self, k: usize, moves: &[[f64; 6]], rect: Option<[f32; 4]>, blend: peniko::BlendMode) -> bool {
        if moves.is_empty() || moves.len() > STREAK_MOVES {
            return false;
        }
        let Some(area) = self.streak_area(rect) else { return true };
        match moves {
            [m] => return self.draw_moved_over(k, *m, area, blend),
            _ if moves.len() > STREAK_MOVES => return false,
            _ => {}
        }
        let Some(image) = self.cache.cached.get(k).cloned() else { return false };
        let Some(effect) = streak_effect() else { return false };
        // Each move's inverse, two rows of (x, y, 1) weights: a picture px read for each canvas px.
        let mut data = vec![0u8; effect.uniform_size()];
        let (Some(rows), Some(count)) = (effect.find_uniform("m"), effect.find_uniform("n")) else { return false };
        let mut put = |at: usize, v: f32| data[at..at + 4].copy_from_slice(&v.to_ne_bytes());
        for (i, m) in moves.iter().enumerate() {
            let a = kurbo::Affine::new(*m);
            if a.determinant().abs() < 1e-12 {
                return false;
            }
            let [ia, ib, ic, id, ie, iff] = a.inverse().as_coeffs();
            for (j, v) in [ia, ic, ie, 0.0, ib, id, iff, 0.0].into_iter().enumerate() {
                put(rows.offset() + (i * 8 + j) * 4, v as f32);
            }
        }
        put(count.offset(), moves.len() as f32);
        let sampling = skia_safe::SamplingOptions::new(skia_safe::FilterMode::Linear, skia_safe::MipmapMode::None);
        let at = skia_safe::Matrix::translate(self.cache.cached_origin(k));
        let Some(child) = image.to_shader(Some((skia_safe::TileMode::Clamp, skia_safe::TileMode::Clamp)), sampling, Some(&at)) else { return false };
        let children = [skia_safe::runtime_effect::ChildPtr::Shader(child)];
        let Some(shader) = effect.make_shader(skia_safe::Data::new_copy(&data), &children, None) else { return false };
        let mut paint = Paint::default();
        paint.set_shader(shader);
        paint.set_blend_mode(sk_peniko::blend_mode_from(blend));
        self.fill_device(area, &paint);
        true
    }

    fn begin_kept(&mut self, k: usize) -> bool {
        // Only between top-level layers: not inside a kept picture, a capture or a layer of a 3D plane.
        if self.cache.kept_prev.is_some() || !self.cache.base_3d.is_empty() {
            return false;
        }
        if self.cache.kept.len() <= k {
            self.cache.kept.resize_with(k + 1, || None);
        }
        let margin = self.cache.kept_margin.max(0);
        if self.cache.kept[k].is_none() {
            let info = self.inner.image_info();
            let info = info.with_dimensions((info.width() + 2 * margin, info.height() + 2 * margin));
            let Some(mut surface) = self.inner.new_surface(&info, None) else { return false };
            surface.canvas().clear(Color::TRANSPARENT);
            self.cache.kept[k] = Some((surface, (self.cache.origin.0 - margin, self.cache.origin.1 - margin)));
        }
        // The canvas's clips stay (what lies outside them is not drawn on it either), but for a margin past its edges.
        let clip = self.inner.device_clip_bounds().filter(|_| margin == 0);
        let (surface, origin) = self.cache.kept[k].as_mut().unwrap();
        let (canvas, origin) = (surface.canvas() as *const Canvas, *origin);
        self.cache.kept_prev = Some((self.inner as *const Canvas as usize, std::mem::replace(&mut self.cache.origin, origin)));
        // SAFETY: the canvas belongs to a surface the cache keeps until `take_kept`, after the paint (and `end_kept`).
        self.inner = unsafe { &*canvas };
        self.inner.save();
        if let Some(c) = clip {
            self.inner.clip_irect(c, None);
        }
        true
    }

    fn end_kept(&mut self) {
        let Some((prev, origin)) = self.cache.kept_prev.take() else { return };
        self.inner.restore();
        self.cache.origin = origin;
        // SAFETY: `prev` is the canvas in use when `begin_kept` switched, alive for the whole paint.
        self.inner = unsafe { &*(prev as *const Canvas) };
    }

    fn draw_warped(&mut self, content: &anyrender::Scene, mesh: &anyrender::WarpMesh) {
        let rest = mesh.rest;
        let s = mesh.transform.determinant().abs().sqrt().max(1e-3);
        let k = s.min(4096.0 / rest.width().max(rest.height()).max(1.0));
        // Recorded draws are in this canvas's device space: device → element px → offscreen px.
        let Some(to_element) = (mesh.transform.determinant().abs() > 1e-12).then(|| mesh.transform.inverse()) else { return };
        let off = kurbo::Affine::scale(k) * kurbo::Affine::translate((-rest.x0, -rest.y0)) * to_element;
        let Some(image) = self.paint_offscreen(content, off, rest.width() * k, rest.height() * k) else {
            return self.append_scene(content.clone(), kurbo::Affine::IDENTITY);
        };
        // Any triangle mesh: vertex i shows the picture at uvs[i] (offscreen px) and lands at points[i].
        if !mesh.is_valid() {
            return self.append_scene(content.clone(), kurbo::Affine::IDENTITY);
        }
        let positions: Vec<Point> = mesh.points.iter().map(|p| Point::new(p.x as f32, p.y as f32)).collect();
        let texs: Vec<Point> = mesh.uvs.iter().map(|t| Point::new(((t.x - rest.x0) * k) as f32, ((t.y - rest.y0) * k) as f32)).collect();
        let indices: Vec<u16> = mesh.tris.iter().map(|&i| i as u16).collect();
        let colors = vec![Color::WHITE; positions.len()];
        let vertices = skia_safe::Vertices::new_copy(skia_safe::vertices::VertexMode::Triangles, &positions, &texs, &colors, Some(&indices));
        let sampling = skia_safe::SamplingOptions::new(skia_safe::FilterMode::Linear, skia_safe::MipmapMode::None);
        let Some(shader) = image.to_shader((skia_safe::TileMode::Decal, skia_safe::TileMode::Decal), sampling, None) else { return };
        self.reset_paint();
        self.cache.paint.set_shader(shader);
        self.set_matrix(mesh.transform);
        self.inner.draw_vertices(&vertices, skia_safe::BlendMode::Modulate, &self.cache.paint);
    }

    /// Rostrum patch (round 8): every stamp of a sprite as one textured mesh — the sprite painted once into an
    /// offscreen image at the largest scale a stamp is drawn at (≤ 512 px), each stamp a quad carrying its
    /// tint and opacity as vertex colours (modulated with the image).
    fn draw_instances(&mut self, content: &anyrender::Scene, to_sprite: kurbo::Affine, bounds: kurbo::Rect, instances: &[anyrender::SpriteInstance]) {
        let mut k: f64 = 1e-3;
        for i in instances {
            let [a, b, c, d, _, _] = i.transform.as_coeffs();
            k = k.max((a * a + b * b).sqrt()).max((c * c + d * d).sqrt());
        }
        let k = k.min(512.0 / bounds.width().max(bounds.height()).max(1e-3));
        let off = kurbo::Affine::scale(k) * kurbo::Affine::translate((-bounds.x0, -bounds.y0)) * to_sprite;
        let Some(image) = self.paint_offscreen(content, off, bounds.width() * k, bounds.height() * k) else { return };
        let sampling = skia_safe::SamplingOptions::new(skia_safe::FilterMode::Linear, skia_safe::MipmapMode::None);
        let Some(shader) = image.to_shader((skia_safe::TileMode::Decal, skia_safe::TileMode::Decal), sampling, None) else { return };
        let corners = [(bounds.x0, bounds.y0), (bounds.x1, bounds.y0), (bounds.x1, bounds.y1), (bounds.x0, bounds.y1)];
        let texs_one: Vec<Point> = corners.iter().map(|&(x, y)| Point::new(((x - bounds.x0) * k) as f32, ((y - bounds.y0) * k) as f32)).collect();
        for chunk in instances.chunks(16000) {
            let mut positions = Vec::with_capacity(chunk.len() * 4);
            let mut texs = Vec::with_capacity(chunk.len() * 4);
            let mut colors = Vec::with_capacity(chunk.len() * 4);
            let mut indices: Vec<u16> = Vec::with_capacity(chunk.len() * 6);
            for (n, inst) in chunk.iter().enumerate() {
                let [r, g, b, a] = inst.color.map(|v| (v.clamp(0.0, 1.0) * 255.0).round() as u8);
                let col = Color::from_argb(a, r, g, b);
                for (c, &(x, y)) in corners.iter().enumerate() {
                    let p = inst.transform * kurbo::Point::new(x, y);
                    positions.push(Point::new(p.x as f32, p.y as f32));
                    texs.push(texs_one[c]);
                    colors.push(col);
                }
                let o = (n * 4) as u16;
                indices.extend_from_slice(&[o, o + 1, o + 2, o, o + 2, o + 3]);
            }
            let vertices = skia_safe::Vertices::new_copy(skia_safe::vertices::VertexMode::Triangles, &positions, &texs, &colors, Some(&indices));
            self.reset_paint();
            self.cache.paint.set_shader(shader.clone());
            self.set_matrix(kurbo::Affine::IDENTITY);
            self.inner.draw_vertices(&vertices, skia_safe::BlendMode::Modulate, &self.cache.paint);
        }
    }

    fn push_layer(
        &mut self,
        fill: peniko::Fill,
        blend: impl Into<peniko::BlendMode>,
        alpha: f32,
        transform: kurbo::Affine,
        clip: &impl kurbo::Shape,
        filter: Option<Arc<Filter>>,
        backdrop_filter: Option<Arc<Filter>>,
    ) {
        let blend: peniko::BlendMode = blend.into();

        // Rostrum patch (round 14, H5): every layer under a perspective base (filter, opacity, blend, isolation) is
        // drawn in its own plane (`FlatLayer`), then projected: a `saveLayer` opened under perspective came out
        // empty (an `opacity: .9` or a blending child made a tilted card vanish), and filters ran wrong and slowly.
        if backdrop_filter.is_none() && self.perspective_base().is_some() {
            let grow = filter.as_ref().map_or(kurbo::Rect::ZERO, |f| f.expansion_rect());
            if self.push_flat_layer(fill, blend, alpha, transform, clip, filter.as_ref().and_then(|f| convert_filter(f)), grow) {
                return;
            }
        }

        // Rostrum patch (X6): a filter with taps draws its content offscreen (see `Capture`).
        if filter.as_ref().is_some_and(|f| !f.taps.is_empty()) && backdrop_filter.is_none() && self.push_capture(fill, blend, alpha, transform, clip, filter.clone(), vec![], None, None) {
            return;
        }
        self.cache.captures.push(None);
        self.cache.soft_clips.push(None);
        self.cache.flats.push(None);

        self.reset_paint();
        self.set_paint_alpha(alpha);
        self.set_paint_blend_mode(blend);

        if let Some(filter) = filter.as_ref().and_then(|f| convert_filter(f)) {
            self.set_paint_filter(filter);
        }

        self.inner.save();

        self.set_matrix(transform);
        self.clip(fill, clip);

        let backdrop_filter = backdrop_filter.as_ref().and_then(|f| convert_filter(f));
        let mut save_layer_rec = SaveLayerRec::default().paint(&self.cache.paint);
        if let Some(backdrop_filter) = backdrop_filter.as_ref() {
            save_layer_rec = save_layer_rec.backdrop(backdrop_filter);
        }

        self.inner.save_layer(&save_layer_rec);
        crate::layer_census::note_layer(if filter.is_some() { "push_layer_filter" } else if alpha < 1.0 { "push_layer_alpha" } else { "push_layer_blend" }, self.inner);
    }

    fn push_clip_layer(
        &mut self,
        fill: peniko::Fill,
        transform: kurbo::Affine,
        clip: &impl kurbo::Shape,
    ) {
        self.cache.captures.push(None);
        self.cache.flats.push(None);
        self.inner.save(); // we need to do two saves because of pop_layer

        self.set_matrix(transform);
        // Rostrum patch (round 14, H5): the clip as it can be projected (`in_front`), for the soft edge too.
        let front = clip.as_rect().and_then(|r| self.in_front(r));
        // Rostrum patch (F7 seam, R19): an anti-aliased clip edge applied to every draw on its own lets what is drawn
        // first show through what is drawn over it at the edge pixels (coverage conflation): a video layer's dark
        // background under its frame made each rolling-shutter band's clipped top edge a dark hairline (10-20 % on
        // flat colour) over a picture it should have matched. Where the clip's edge falls between pixels, the content
        // is drawn into a layer under a hard clip to the pixels the edge touches, and the soft edge is applied once to
        // the whole layer at pop. A rectangle on the pixel grid (the common case) clips as before, with no layer.
        if self.clip_on_pixel_grid(transform, clip) {
            self.clip(fill, clip);
            self.cache.soft_clips.push(None);
            self.inner.save();
            return;
        }
        self.inner.save();
        self.clip(fill, clip);
        let bounds = self.inner.device_clip_bounds();
        self.inner.restore();
        self.inner.reset_matrix();
        self.inner.clip_irect(bounds.unwrap_or_default(), None);
        self.cache.soft_clips.push(Some(SoftClip { transform, fill, path: front.unwrap_or_else(|| clip.to_path(0.01)) }));
        self.inner.save_layer(&SaveLayerRec::default());
        crate::layer_census::note_layer("soft_clip", self.inner);
    }

    fn pop_layer(&mut self) {
        // Rostrum patch (F7 seam, R19): a soft clip's edge, applied once to its layer: what lies outside the shape is
        // cleared, by the edge's own coverage where it crosses a pixel.
        if let Some(sc) = self.cache.soft_clips.pop().flatten() {
            self.set_matrix(sc.transform);
            let mut p = sk_kurbo::path_from_shape(&sc.path);
            p.set_fill_type(sk_peniko::path_fill_type_from_fill(sc.fill));
            p.toggle_inverse_fill_type();
            let mut paint = Paint::default();
            paint.set_anti_alias(true);
            paint.set_blend_mode(SkBlendMode::Clear);
            self.inner.draw_path(&p, &paint);
        }
        let flat = self.cache.flats.pop().flatten();
        let Some(cap) = self.cache.captures.pop().flatten() else {
            match flat {
                // Rostrum patch (round 14, H5): a layer drawn in its own plane, now drawn through the 3D matrix.
                Some(flat) => self.pop_flat_layer(flat),
                None => {
                    self.inner.restore();
                    self.inner.restore();
                }
            }
            return;
        };
        // Rostrum patch (X6): the captured layer's content is its filter's source: write the taps, then draw it filtered.
        self.inner.restore();
        let mut surface = cap.surface.clone();
        let src = surface.image_snapshot();
        // SAFETY: `prev` is the canvas in use when the layer was pushed, alive for longer than the layer.
        self.inner = unsafe { &*(cap.prev as *const Canvas) };
        self.cache.origin = cap.prev_origin;
        for (id, path) in cap.filter.iter().flat_map(|f| f.taps.iter()) {
            // A tap's file is named by its content (compCache.ts): one already there, or drawn earlier in this paint, is kept.
            if self.cache.pending_taps.iter().any(|t| t.path == *path) || std::path::Path::new(path).exists() {
                continue;
            }
            if let Err(e) = self.write_tap(&cap, &src, *id, path) {
                anyrender::filters::shader_errors::push(format!("comp cache: {e}"));
            }
        }
        // Rostrum patch (E3): each glow is the content blurred, added; then the content itself.
        let plus = peniko::BlendMode::new(peniko::Mix::Normal, peniko::Compose::Plus);
        for (glow, strength, clip) in cap.glows.iter().filter(|_| !skips("glow")) {
            self.draw_capture(&cap, &src, *strength, plus, Some(glow), Some(*clip));
        }
        match (cap.glows.is_empty(), cap.body_clip) {
            (false, None) => self.draw_at_origin(&src, cap.origin, None),
            (_, clip) => self.draw_capture(&cap, &src, cap.alpha, cap.blend, cap.filter.as_deref(), clip),
        }
    }

    fn push_glow_layer(
        &mut self,
        glows: &[(Arc<Filter>, f32, kurbo::Rect)],
        alpha: f32,
        blend: Option<peniko::BlendMode>,
        transform: kurbo::Affine,
        clip: Option<kurbo::Rect>,
        filter: Option<Arc<Filter>>,
    ) -> bool {
        // The content is captured into a picture covering only the layer's reach (its clips, filters' spread included;
        // E4: it was the whole canvas), cut to where it shows. A blur reads past that: Skia's own filter layer reads what
        // is drawn just outside the frame too. So a layer whose reach crosses the enclosing clip is left to the caller's
        // layers, as is a layer under a base matrix (a view, a 3D plane).
        let Some(first) = glows.first() else { return false };
        let all = glows.iter().fold(clip.unwrap_or(first.2), |a, g| a.union(g.2));
        let (ox, oy) = (self.cache.origin.0 as f64, self.cache.origin.1 as f64);
        let reach = transform.transform_rect_bbox(all);
        let Some(c) = self.inner.device_clip_bounds() else { return false };
        let shown = irect_to_kurbo(c) + kurbo::Vec2::new(ox, oy);
        let inside = reach.x0 >= shown.x0 && reach.y0 >= shown.y0 && reach.x1 <= shown.x1 && reach.y1 <= shown.y1;
        let region = reach.expand().intersect(shown);
        if !inside || !self.cache.base_3d.is_empty() || region.is_zero_area() {
            return false;
        }
        let region = skia_safe::IRect::new(region.x0 as i32, region.y0 as i32, region.x1 as i32, region.y1 as i32);
        self.push_capture(peniko::Fill::NonZero, blend.unwrap_or(peniko::Mix::Normal.into()), alpha, transform, &all, filter, glows.to_vec(), clip, Some(region))
    }

    fn stroke<'a>(
        &mut self,
        style: &kurbo::Stroke,
        transform: kurbo::Affine,
        brush: impl Into<anyrender::PaintRef<'a>>,
        brush_transform: Option<kurbo::Affine>,
        shape: &impl kurbo::Shape,
    ) {
        self.set_matrix(transform);

        self.reset_paint();
        self.set_paint_brush(brush, brush_transform);
        self.set_paint_style(style);
        self.draw_shape(shape);
    }

    fn fill<'a>(
        &mut self,
        style: peniko::Fill,
        transform: kurbo::Affine,
        brush: impl Into<anyrender::PaintRef<'a>>,
        brush_transform: Option<kurbo::Affine>,
        shape: &impl kurbo::Shape,
    ) {
        self.set_matrix(transform);

        self.reset_paint();
        self.set_paint_brush(brush, brush_transform);
        self.set_paint_style(style);
        self.draw_shape_with_fill(shape, style);
    }

    fn draw_glyphs<'a, 's: 'a>(
        &'s mut self,
        #[allow(unused_mut)] mut font: &'a peniko::FontData,
        font_size: f32,
        hint: bool,
        normalized_coords: &'a [anyrender::NormalizedCoord],
        _embolden: kurbo::Vec2,
        style: impl Into<peniko::StyleRef<'a>>,
        brush: impl Into<anyrender::PaintRef<'a>>,
        brush_alpha: f32,
        transform: kurbo::Affine,
        glyph_transform: Option<kurbo::Affine>,
        glyphs: impl Iterator<Item = anyrender::Glyph>,
    ) {
        self.set_matrix(transform);

        if let Some(glyph_transform) = glyph_transform {
            self.concat_matrix(glyph_transform);
        }

        self.reset_paint();
        self.set_paint_brush(brush, None);
        self.set_paint_style(style);
        // Rostrum patch (round 6): the brush alpha multiplies the colour's own alpha (it used to replace it,
        // so `color: rgba(…, 0.4)` text drew opaque).
        let a = self.cache.paint.alpha_f();
        self.set_paint_alpha(a * brush_alpha);

        let Some(font) = self.get_or_cache_font(font, normalized_coords, font_size, hint) else {
            return;
        };

        let (min_size, _) = glyphs.size_hint();
        self.cache.glyph_id_buf.reserve(min_size);
        self.cache.glyph_pos_buf.reserve(min_size);

        for glyph in glyphs {
            self.cache.glyph_id_buf.push(GlyphId::from(glyph.id as u16));
            self.cache.glyph_pos_buf.push(Point::new(glyph.x, glyph.y));
        }

        self.inner.draw_glyphs_at(
            &self.cache.glyph_id_buf[..],
            GlyphPositions::Points(&self.cache.glyph_pos_buf[..]),
            Point::new(0.0, 0.0),
            &font,
            &self.cache.paint,
        );

        self.cache.glyph_id_buf.clear();
        self.cache.glyph_pos_buf.clear();
    }

    fn draw_box_shadow(
        &mut self,
        transform: kurbo::Affine,
        rect: kurbo::Rect,
        brush: peniko::Color,
        radius: f64,
        std_dev: f64,
    ) {
        // Rostrum patch (round 14, H5): under a perspective base the shadow is drawn in its own plane (a `FlatLayer`,
        // as filtered layers are), where the mask blur below is affine, then that picture through the 3D matrix.
        let reach = 3.0 * std_dev;
        let flat = std_dev > 0.0
            && self.push_flat_layer(peniko::Fill::NonZero, peniko::Mix::Normal.into(), 1.0, transform, &rect.inflate(reach, reach), None, kurbo::Rect::new(-reach, -reach, reach, reach));

        self.set_matrix(transform);

        self.reset_paint();
        self.set_paint_brush(brush, None);
        self.cache.paint.set_style(PaintStyle::Fill);

        // Rostrum patch: under perspective (a rotateX / rotateY tilt) Skia blurs a mask filter's coverage on
        // the CPU; the shape is drawn sharp into a layer that a (downscaled, GPU) blur filter blurs instead.
        // (Round 14: only left when no flat layer could be made.)
        let perspective = std_dev > 0.0 && self.inner.local_to_device_as_3x3().has_perspective();
        if std_dev > 0.0 && !perspective {
            self.cache.paint.set_mask_filter(
                MaskFilter::blur(BlurStyle::Normal, std_dev as f32, true).unwrap(),
            );
        }
        if perspective {
            let mut layer = Paint::default();
            layer.set_image_filter(gaussian_blur(std_dev as f32, None));
            self.inner.save_layer(&SaveLayerRec::default().paint(&layer));
        }

        let rrect = RRect::new_nine_patch(
            Rect::new(
                rect.x0 as f32,
                rect.y0 as f32,
                rect.x1 as f32,
                rect.y1 as f32,
            ),
            radius as f32,
            radius as f32,
            radius as f32,
            radius as f32,
        );

        self.inner.draw_rrect(rrect, &self.cache.paint);
        if perspective {
            self.inner.restore();
        }
        if flat {
            self.pop_layer();
        }
    }
}

fn lerp_f32(a: f32, b: f32, t: f32) -> f32 {
    a + (b - a) * t
}

/// Rostrum patch: a large Gaussian blur is run at a lower resolution. Above `FULL_RATE_SIGMA` the input is
/// halved (bilinear at the 2 × 2 centres: a box average) until σ fits, blurred with σ / 2^k, and scaled back
/// up. A Gaussian that wide has no detail at the scale the halving drops, so it looks the same, and it costs
/// 1 / 4^k of the pixels: a 160 px glow at 1080p is blurred on a ~110 × 110 image instead of ~1800 × 1800.
fn gaussian_blur(sigma: f32, input: Option<ImageFilter>) -> Option<ImageFilter> {
    use skia_safe::{image_filters, FilterMode, Matrix, MipmapMode, SamplingOptions};
    const FULL_RATE_SIGMA: f32 = 8.0;
    if skips("blur") {
        return input;
    }
    let mut levels = 0;
    while sigma / (1u32 << levels) as f32 > FULL_RATE_SIGMA && levels < 6 {
        levels += 1;
    }
    if levels == 0 {
        return image_filters::blur((sigma, sigma), None, input, None);
    }
    let linear = SamplingOptions::new(FilterMode::Linear, MipmapMode::None);
    let mut f = input;
    for _ in 0..levels {
        f = image_filters::matrix_transform(&Matrix::scale((0.5, 0.5)), linear, f);
    }
    let k = (1u32 << levels) as f32;
    f = image_filters::blur((sigma / k, sigma / k), None, f, None);
    image_filters::matrix_transform(&Matrix::scale((k, k)), linear, f)
}

/// Rostrum patch (E5), measurement only: `ROSTRUM2D_PROFILE_SKIP=glow,blur,gradient` leaves those effects out of
/// every paint (gradients become a flat half-grey, blurs nothing) to time what they cost. The pictures are wrong on
/// purpose; unset, nothing changes.
fn skips(what: &str) -> bool {
    static SKIP: std::sync::OnceLock<String> = std::sync::OnceLock::new();
    SKIP.get_or_init(|| std::env::var("ROSTRUM2D_PROFILE_SKIP").unwrap_or_default()).split(',').any(|w| w.trim() == what)
}

thread_local! {
    /// Rostrum patch (X6): the image filter made for each node of the graph being converted. A buffer read by several
    /// primitives (a comp's keyed foreground feeds its edge, wrap and merge) is one Skia filter object, so Skia's filter
    /// cache evaluates it once per draw instead of once per reader (the graph had become a tree: every fan-out doubled
    /// the work below it).
    static CONVERTED: std::cell::RefCell<std::collections::HashMap<u16, Option<ImageFilter>>> = Default::default();
}

fn convert_filter(filter: &Filter) -> Option<ImageFilter> {
    CONVERTED.with(|m| m.borrow_mut().clear());
    let out = convert_filter_effect(filter, filter.output());
    CONVERTED.with(|m| m.borrow_mut().clear());
    out
}

fn resolve_input(filter: &Filter, input: &Option<FilterInput>) -> Option<ImageFilter> {
    input.as_ref().and_then(|input| match input {
        // The layer itself is the source graphic (no input); its alpha alone is a colour matrix of it.
        FilterInput::Source(anyrender::filters::FilterSource::SourceAlpha) => skia_safe::image_filters::color_filter(
            skia_safe::color_filters::matrix_row_major(&[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0], None),
            None,
            None,
        ),
        FilterInput::Source(_) => None,
        FilterInput::Result(input_id) => convert_filter_effect(filter, *input_id),
    })
}

fn convert_filter_effect(filter: &Filter, id: FilterId) -> Option<ImageFilter> {
    if let Some(done) = CONVERTED.with(|m| m.borrow().get(&id.0).cloned()) {
        return done;
    }
    let out = convert_filter_node(filter, id);
    CONVERTED.with(|m| m.borrow_mut().insert(id.0, out.clone()));
    out
}

fn convert_filter_node(filter: &Filter, id: FilterId) -> Option<ImageFilter> {
    let node = &filter.nodes()[id.0 as usize];
    // Rostrum patch: the filter region crops every primitive (transparent outside); X6 ROI: and its region of interest.
    let crop = filter.crops.iter().find(|(f, _)| *f == id).map(|(_, r)| *r);
    let region = match (filter.region, crop) {
        (Some(r), Some(c)) => Some(r.intersect(c)),
        (r, c) => r.or(c),
    }
    .map(|r| skia_safe::Rect::new(r.x0 as f32, r.y0 as f32, r.x1.max(r.x0) as f32, r.y1.max(r.y0) as f32));
    let input = resolve_input(filter, &node.inputs.primary);
    // Secondary input ("in2" in SVG), used by filters that combine two inputs such as
    // composite, blend and displacement map.
    let secondary = resolve_input(filter, &node.inputs.secondary);

    // Clone to avoid borrow checking issues. Cloning is cheap as filters are refcounted.
    let input_clone = input.clone();

    use skia_safe::{color_filters, image_filters, shaders};

    let filter: Option<ImageFilter> = match &node.effect {
        FilterEffect::Flood(color) => {
            let rgba8 = color.to_rgba8();
            let sk_color = Color::from_argb(rgba8.a, rgba8.r, rgba8.g, rgba8.b);
            let shader = skia_safe::shaders::color(sk_color);
            image_filters::shader(shader, None)
        }
        FilterEffect::GaussianBlur(blur) => gaussian_blur(blur.std_deviation, input),
        FilterEffect::DropShadow(drop_shadow) => image_filters::drop_shadow(
            (drop_shadow.dx, drop_shadow.dy),
            (drop_shadow.std_deviation, drop_shadow.std_deviation),
            color4f_from_alpha_color(drop_shadow.color),
            None,
            input,
            None,
        ),
        FilterEffect::ComponentTransfer(ct) => {
            fn map_transfer_function(func: &TransferFunction) -> Option<[u8; 256]> {
                match func {
                    TransferFunction::Identity => None,
                    TransferFunction::Table(table) => {
                        if table.is_empty() {
                            None
                        } else {
                            let table = table.as_slice();
                            let n = table.len();

                            let mut values = [0; 256];
                            for (i, out) in values.iter_mut().enumerate() {
                                let c = i as f64 / 255.0;
                                let k = (c * (n - 1) as f64) as usize;
                                let v1 = table[k] as f64;
                                let v2 = table[(k + 1).min(n - 1)] as f64;
                                let val =
                                    255.0 * (v1 + (c * (n - 1) as f64 - k as f64) * (v2 - v1));
                                *out = val.clamp(0.0, 255.0) as u8;
                            }
                            Some(values)
                        }
                    }
                    TransferFunction::Discrete(items) => {
                        if items.is_empty() {
                            None
                        } else {
                            let items = items.as_slice();
                            let n = items.len();

                            let mut values = [0; 256];
                            for (i, out) in values.iter_mut().enumerate() {
                                let k = (((i * n) as f64 / 255.0) as usize).min(n - 1);
                                let val = 255.0 * items[k] as f64;
                                *out = val.clamp(0.0, 255.0) as u8;
                            }
                            Some(values)
                        }
                    }
                    TransferFunction::Linear(tf) => {
                        let mut values = [0; 256];
                        for (i, out) in values.iter_mut().enumerate() {
                            let val: f64 =
                                (tf.slope as f64 * i as f64) + (255.0 * tf.intercept as f64);
                            *out = val.clamp(0.0, 255.0) as u8;
                        }
                        Some(values)
                    }
                    TransferFunction::Gamma(tf) => {
                        let mut values = [0; 256];
                        for (i, out) in values.iter_mut().enumerate() {
                            let val: f64 = 255.0
                                * (tf.amplitude as f64
                                    * (i as f64 / 255.0).powf(tf.exponent as f64))
                                + tf.offset as f64;
                            *out = val.clamp(0.0, 255.0) as u8;
                        }
                        Some(values)
                    }
                }
            }

            let color_filter = color_filters::table_argb(
                map_transfer_function(&ct.alpha_function).as_ref(),
                map_transfer_function(&ct.red_function).as_ref(),
                map_transfer_function(&ct.green_function).as_ref(),
                map_transfer_function(&ct.blue_function).as_ref(),
            );

            color_filter.and_then(|cf| image_filters::color_filter(cf, input, None))
        }
        FilterEffect::ColorMatrix(color_matrix) => {
            let color_filter =
                color_filters::matrix_row_major(&color_matrix.0, color_filters::Clamp::Yes);
            image_filters::color_filter(color_filter, input, None)
        }
        FilterEffect::Offset(offset) => {
            image_filters::offset((offset.x as f32, offset.y as f32), input, None)
        }

        FilterEffect::Composite(composite_operator) => match composite_operator {
            // Arithmetic combination: result = k1*i1*i2 + k2*i1 + k3*i2 + k4, where i1 is the
            // primary input and i2 is the secondary input. Skia's `arithmetic` computes
            // k1*fg*bg + k2*fg + k3*bg + k4, so foreground = primary, background = secondary.
            CompositeOperator::Arithmetic(a) => {
                image_filters::arithmetic(a.k1, a.k2, a.k3, a.k4, false, secondary, input, None)
            }
            // Porter-Duff operators. The primary input is the source (foreground) and the
            // secondary input is the destination (background).
            _ => {
                let mode = match composite_operator {
                    CompositeOperator::Over => SkBlendMode::SrcOver,
                    CompositeOperator::In => SkBlendMode::SrcIn,
                    CompositeOperator::Out => SkBlendMode::SrcOut,
                    CompositeOperator::Atop => SkBlendMode::SrcATop,
                    CompositeOperator::Xor => SkBlendMode::Xor,
                    CompositeOperator::Arithmetic(_) => unreachable!(),
                };
                image_filters::blend(mode, secondary, input, None)
            }
        },
        FilterEffect::Blend(mix) => {
            // The primary input is the top layer (foreground) and the secondary input is the
            // bottom layer (background).
            let blend_mode = peniko::BlendMode {
                mix: *mix,
                compose: peniko::Compose::SrcOver,
            };
            let mode = sk_peniko::blend_mode_from(blend_mode);
            image_filters::blend(mode, secondary, input, None)
        }
        FilterEffect::Morphology(morphology_filter) => {
            let radius = (morphology_filter.radius, morphology_filter.radius);
            match morphology_filter.operator {
                MorphologyOperator::Dilate => image_filters::dilate(radius, input, None),
                MorphologyOperator::Erode => image_filters::erode(radius, input, None),
            }
        }
        FilterEffect::ConvolveMatrix(convolution_kernel) => {
            let size = convolution_kernel.size as i32;
            // Skia applies `gain` as a multiplier, so invert the divisor.
            let gain = if convolution_kernel.divisor != 0.0 {
                1.0 / convolution_kernel.divisor
            } else {
                1.0
            };
            // Center the kernel over each pixel (SVG default targetX/Y = floor(order / 2)).
            let offset = size / 2;
            image_filters::matrix_convolution(
                skia_safe::ISize::new(size, size),
                &convolution_kernel.values,
                gain,
                convolution_kernel.bias,
                skia_safe::IPoint::new(offset, offset),
                skia_safe::TileMode::Clamp,
                !convolution_kernel.preserve_alpha,
                input,
                None,
            )
        }
        FilterEffect::Turbulence(turbulence_filter) => {
            let base_frequency = (
                turbulence_filter.base_frequency,
                turbulence_filter.base_frequency,
            );
            let num_octaves = turbulence_filter.num_octaves as usize;
            let seed = turbulence_filter.seed as f32;
            let shader = match turbulence_filter.turbulence_type {
                TurbulenceType::FractalNoise => {
                    shaders::fractal_noise(base_frequency, num_octaves, seed, None)
                }
                TurbulenceType::Turbulence => {
                    shaders::turbulence(base_frequency, num_octaves, seed, None)
                }
            };
            shader.and_then(|shader| image_filters::shader(shader, None))
        }
        FilterEffect::DisplacementMap(displacement_map_filter) => {
            // The primary input provides the pixels to displace ("in"), the secondary input
            // provides the displacement vectors ("in2").
            image_filters::displacement_map(
                (
                    to_sk_color_channel(displacement_map_filter.x_channel),
                    to_sk_color_channel(displacement_map_filter.y_channel),
                ),
                displacement_map_filter.scale,
                secondary,
                input,
                None,
            )
        }
        FilterEffect::DiffuseLighting(diffuse_lighting_filter) => {
            // SVG lighting-color defaults to white.
            let light_color = Color::WHITE;
            let surface_scale = diffuse_lighting_filter.surface_scale;
            let kd = diffuse_lighting_filter.diffuse_constant;
            match &diffuse_lighting_filter.light_source {
                LightSource::Distant(distant) => image_filters::distant_lit_diffuse(
                    distant_light_direction(distant),
                    light_color,
                    surface_scale,
                    kd,
                    input,
                    None,
                ),
                LightSource::Point(point) => image_filters::point_lit_diffuse(
                    Point3::new(point.x, point.y, point.z),
                    light_color,
                    surface_scale,
                    kd,
                    input,
                    None,
                ),
                LightSource::Spot(spot) => image_filters::spot_lit_diffuse(
                    Point3::new(spot.x, spot.y, spot.z),
                    Point3::new(spot.points_at_x, spot.points_at_y, spot.points_at_z),
                    spot.specular_exponent,
                    spot.limiting_cone_angle.unwrap_or(90.0),
                    light_color,
                    surface_scale,
                    kd,
                    input,
                    None,
                ),
            }
        }
        FilterEffect::SpecularLighting(specular_lighting_filter) => {
            // SVG lighting-color defaults to white.
            let light_color = Color::WHITE;
            let surface_scale = specular_lighting_filter.surface_scale;
            let ks = specular_lighting_filter.specular_constant;
            let shininess = specular_lighting_filter.specular_exponent;
            match &specular_lighting_filter.light_source {
                LightSource::Distant(distant) => image_filters::distant_lit_specular(
                    distant_light_direction(distant),
                    light_color,
                    surface_scale,
                    ks,
                    shininess,
                    input,
                    None,
                ),
                LightSource::Point(point) => image_filters::point_lit_specular(
                    Point3::new(point.x, point.y, point.z),
                    light_color,
                    surface_scale,
                    ks,
                    shininess,
                    input,
                    None,
                ),
                LightSource::Spot(spot) => image_filters::spot_lit_specular(
                    Point3::new(spot.x, spot.y, spot.z),
                    Point3::new(spot.points_at_x, spot.points_at_y, spot.points_at_z),
                    spot.specular_exponent,
                    spot.limiting_cone_angle.unwrap_or(90.0),
                    light_color,
                    surface_scale,
                    ks,
                    shininess,
                    input,
                    None,
                ),
            }
        }

        // These require resources or bounds that aren't available at this layer, so they are
        // not yet implemented.
        // - `Image` needs to resolve an external image by id from a resource registry.
        // - `Tile` needs the filter primitive subregion (src/dst rects) to tile into.
        FilterEffect::Image(source) => anyrender::filters::images::get(source.image_id).and_then(|img| {
            // An feImage: the registered image drawn into the rectangle its transform maps it to (scale and translate).
            // Rostrum patch (comp, Wave 2): a half-float image is an RHALF picture (blitz-dom net.rs): premultiplied and already in
            // the working space, so it is tagged with it like an `<img>` (no conversion). 8-bit pictures are straight sRGB.
            let info = if img.half {
                skia_safe::ImageInfo::new((img.width as i32, img.height as i32), skia_safe::ColorType::RGBAF16, skia_safe::AlphaType::Premul, crate::working_space::get())
            } else {
                skia_safe::ImageInfo::new((img.width as i32, img.height as i32), skia_safe::ColorType::RGBA8888, skia_safe::AlphaType::Unpremul, None)
            };
            let bpp = if img.half { 8 } else { 4 };
            let image = filter_image(source.image_id, &img, &info, || skia_safe::images::raster_from_data(&info, skia_safe::Data::new_copy(&img.rgba), img.width as usize * bpp))?;
            let [a, _b, _c, d, e, f] = source.transform.unwrap_or([1.0, 0.0, 0.0, 1.0, 0.0, 0.0]);
            let src = Rect::new(0.0, 0.0, img.width as f32, img.height as f32);
            let dst = Rect::new(e, f, e + a * img.width as f32, f + d * img.height as f32);
            // Rostrum patch (X6): a picture laid pixel for pixel (a comp cache buffer) is copied, not filtered: linear sampling
            // at an exact 1:1 still moved values by a code value at some pixels.
            let exact = (a - 1.0).abs() < 1e-6 && (d - 1.0).abs() < 1e-6 && e.fract() == 0.0 && f.fract() == 0.0;
            let filter = if exact { skia_safe::FilterMode::Nearest } else { skia_safe::FilterMode::Linear };
            image_filters::image(image, Some(&src), Some(&dst), skia_safe::SamplingOptions::new(filter, skia_safe::MipmapMode::None))
        }),
        FilterEffect::Tile => None,
        FilterEffect::RuntimeShader(r) => runtime_shader_filter(r, input, secondary),
    };

    // If we do not implement given type of filter then the match statement above returns None
    // In that case, if we have an input then we pass that along instead. In the case of filter chains
    // with some unimplemented filters that allows the remaining filters to work
    let out = filter.or(input_clone);
    match region {
        Some(r) => image_filters::crop(r, None, out),
        None => out,
    }
}

/// Rostrum patch (G5, hem): an feImage's Skia image, made once per registered picture and kept between paints (it was
/// copied and made again at every use of every paint, and a new image is a new GPU upload). Known by the registry's id and
/// its entry, held here so its address cannot be reused by another picture while kept, and made again for another working space (the image is tagged with it) (an id registered again is made again);
/// at most `KEPT` (the whole set dropped past it).
/// Rostrum patch (G7, hem): the runtime-shader, colour-filter and blender children use it too, so one id may hold one
/// image per format (an feImage tags a picture premultiplied in the working space, a LUT child reads it untagged); the
/// entries of an older registration of the id are dropped when the new one is made.
fn filter_image(id: u32, img: &std::sync::Arc<anyrender::filters::images::FilterImage>, info: &skia_safe::ImageInfo, make: impl FnOnce() -> Option<skia_safe::Image>) -> Option<skia_safe::Image> {
    use std::cell::RefCell;
    use std::collections::HashMap;
    const KEPT: usize = 48;
    type Kept = Vec<(std::sync::Arc<anyrender::filters::images::FilterImage>, skia_safe::Image)>;
    thread_local! {
        static IMAGES: RefCell<HashMap<u32, Kept>> = RefCell::new(HashMap::new());
    }
    let hit = IMAGES.with(|m| {
        m.borrow().get(&id).and_then(|kept| kept.iter().find(|(e, i)| std::sync::Arc::ptr_eq(e, img) && i.image_info() == info).map(|(_, i)| i.clone()))
    });
    if hit.is_some() {
        return hit;
    }
    let image = make()?;
    IMAGES.with(|m| {
        let mut m = m.borrow_mut();
        if m.len() >= KEPT && !m.contains_key(&id) {
            m.clear();
        }
        let kept = m.entry(id).or_default();
        kept.retain(|(e, _)| std::sync::Arc::ptr_eq(e, img));
        kept.push((img.clone(), image.clone()));
    });
    Some(image)
}

/// Convert an anyrender displacement-map [`ColorChannel`] to the corresponding Skia channel.
fn to_sk_color_channel(channel: ColorChannel) -> skia_safe::ColorChannel {
    match channel {
        ColorChannel::Red => skia_safe::ColorChannel::R,
        ColorChannel::Green => skia_safe::ColorChannel::G,
        ColorChannel::Blue => skia_safe::ColorChannel::B,
        ColorChannel::Alpha => skia_safe::ColorChannel::A,
    }
}

/// Compute the direction vector towards a distant light source from its azimuth and elevation.
///
/// Angles are interpreted as degrees, following the SVG `feDistantLight` convention.
fn distant_light_direction(light: &DistantLightSource) -> Point3 {
    let azimuth = light.azimuth.to_radians();
    let elevation = light.elevation.to_radians();
    Point3::new(
        azimuth.cos() * elevation.cos(),
        azimuth.sin() * elevation.cos(),
        elevation.sin(),
    )
}

mod sk_peniko {
    use peniko::color::{AlphaColor, ColorSpaceTag, HueDirection, Srgb};
    use peniko::{
        BlendMode, Compose, Extend, Gradient, GradientKind, ImageAlphaType, ImageBrush, ImageData,
        ImageFormat, Mix,
    };
    use peniko::{Fill, color::DynamicColor};
    use skia_safe::AlphaType as SkAlphaType;
    use skia_safe::BlendMode as SkBlendMode;
    use skia_safe::Color4f as SkColor4f;
    use skia_safe::ColorType as SkColorType;
    use skia_safe::Data as SkData;
    use skia_safe::ImageInfo as SkImageInfo;
    use skia_safe::PathFillType as SkPathFillType;
    use skia_safe::SamplingOptions as SkSamplingOptions;
    use skia_safe::Shader as SkShader;
    use skia_safe::TileMode as SkTileMode;
    use skia_safe::gradient::Colors;
    use skia_safe::gradient_shader::interpolation::ColorSpace as SkGradientShaderColorSpace;
    use skia_safe::gradient_shader::interpolation::HueMethod as SkGradientShaderHueMethod;
    use skia_safe::shaders::{
        linear_gradient, radial_gradient, sweep_gradient, two_point_conical_gradient,
    };

    /// Rostrum patch (G7, hem): the Skia format an image brush's pixels are read with, so a kept image (`set_paint_brush`)
    /// made for another working space is made again.
    pub(super) fn image_info_from_image_data(image_data: &ImageData) -> SkImageInfo {
        // Rostrum patch: an image whose data holds 8 bytes a pixel is premultiplied half-float RGBA already in the
        // working colour space (blitz-dom's `RHALF` images, rostrum-motion assets.rs); it is tagged with that space
        // (crate::working_space) so Skia draws it unconverted. 8-bit images stay untagged (sRGB).
        let deep = image_data.data.data().len() == image_data.width as usize * image_data.height as usize * 8;
        SkImageInfo::new(
            (image_data.width as i32, image_data.height as i32),
            match image_data.format {
                _ if deep => SkColorType::RGBAF16,
                ImageFormat::Rgba8 => SkColorType::RGBA8888,
                ImageFormat::Bgra8 => SkColorType::BGRA8888,
                _ => unreachable!(),
            },
            match image_data.alpha_type {
                _ if deep => SkAlphaType::Premul,
                ImageAlphaType::Alpha => SkAlphaType::Unpremul,
                ImageAlphaType::AlphaPremultiplied => SkAlphaType::Premul,
            },
            if deep { crate::working_space::get() } else { None },
        )
    }

    /// The Skia image over an image brush's pixels, not copied: the caller keeps `image_data`'s blob alive as long as the
    /// image (`SkiaSceneCache::image_shader` holds both).
    pub(super) fn image_from_image_data(image_data: &ImageData, image_info: &SkImageInfo) -> skia_safe::Image {
        let pixels = unsafe {
            SkData::new_bytes(image_data.data.data()) // We have to ensure the src image data lives long enough
        };
        skia_safe::images::raster_from_data(image_info, pixels, image_info.min_row_bytes()).unwrap()
    }

    /// Rostrum patch (G7, hem): the shader is made per draw from a kept image (cheap; the image's GPU texture is what is
    /// worth keeping), so a picture drawn with another brush transform or sampler never reuses the first draw's.
    pub(super) fn shader_from_image_brush(
        image_brush: ImageBrush<&ImageData>,
        image: skia_safe::Image,
        brush_transform: Option<kurbo::Affine>,
    ) -> Option<SkShader> {
        let sampling = match image_brush.sampler.quality {
            peniko::ImageQuality::Low => {
                SkSamplingOptions::new(skia_safe::FilterMode::Nearest, skia_safe::MipmapMode::None)
            }
            peniko::ImageQuality::Medium => SkSamplingOptions::new(
                skia_safe::FilterMode::Linear,
                skia_safe::MipmapMode::Nearest,
            ),
            peniko::ImageQuality::High => {
                SkSamplingOptions::new(skia_safe::FilterMode::Linear, skia_safe::MipmapMode::Linear)
            }
        };

        skia_safe::shaders::image(
            image,
            (
                tile_mode_from_extend(image_brush.sampler.x_extend),
                tile_mode_from_extend(image_brush.sampler.y_extend),
            ),
            &sampling,
            &brush_transform.map(super::sk_kurbo::matrix_from_affine),
        )
    }

    /// Rostrum patch: None when Skia can make no shader for it (a gradient of no size: its brush transform can't be
    /// inverted; a radial `closest-side` centred on the box's edge); the caller draws `degenerate_colour`. It unwrapped,
    /// and the panic on an export's drawing thread left the whole export waiting forever (p1, 2026-10-25).
    pub(super) fn shader_from_gradient(
        gradient: &Gradient,
        brush_transform: Option<kurbo::Affine>,
    ) -> Option<SkShader> {
        fn rad_to_deg(rad: f32) -> f32 {
            if rad == 0.0 {
                return 0.0;
            }

            rad * 180.0 / std::f32::consts::PI
        }

        match gradient.kind {
            GradientKind::Linear(linear_gradient_position) => {
                let mut colors: Vec<SkColor4f> = vec![];
                let mut positions: Vec<f32> = vec![];

                for color_stop in gradient.stops.iter() {
                    colors.push(color4f_from_dynamic_color(color_stop.color));
                    positions.push(color_stop.offset);
                }
                let start = super::sk_kurbo::pt_from(linear_gradient_position.start);
                let end = super::sk_kurbo::pt_from(linear_gradient_position.end);

                let interpolation = skia_safe::gradient_shader::Interpolation {
                    color_space: gradient_shader_cs_from_cs_tag(gradient.interpolation_cs),
                    in_premul: skia_safe::gradient_shader::interpolation::InPremul::Yes,
                    hue_method: gradient_shader_hue_method_from_hue_direction(
                        gradient.hue_direction,
                    ),
                };

                linear_gradient(
                    (start, end),
                    &skia_safe::gradient::Gradient::new(
                        Colors::new(
                            &colors[..],
                            Some(&positions[..]),
                            tile_mode_from_extend(gradient.extend),
                            None,
                        ),
                        interpolation,
                    ),
                    &brush_transform.map(super::sk_kurbo::matrix_from_affine),
                )
            }
            GradientKind::Radial(radial_gradient_position) => {
                let mut colors: Vec<SkColor4f> = vec![];
                let mut positions: Vec<f32> = vec![];

                for color_stop in gradient.stops.iter() {
                    colors.push(color4f_from_dynamic_color(color_stop.color));
                    positions.push(color_stop.offset);
                }

                let start_center = super::sk_kurbo::pt_from(radial_gradient_position.start_center);
                let start_radius = radial_gradient_position.start_radius;
                let end_center = super::sk_kurbo::pt_from(radial_gradient_position.end_center);
                let end_radius = radial_gradient_position.end_radius;

                let interpolation = skia_safe::gradient_shader::Interpolation {
                    color_space: gradient_shader_cs_from_cs_tag(gradient.interpolation_cs),
                    in_premul: skia_safe::gradient_shader::interpolation::InPremul::Yes,
                    hue_method: gradient_shader_hue_method_from_hue_direction(
                        gradient.hue_direction,
                    ),
                };

                if start_center == end_center && start_radius == end_radius {
                    radial_gradient(
                        (start_center, start_radius),
                        &skia_safe::gradient::Gradient::new(
                            Colors::new(
                                &colors[..],
                                Some(&positions[..]),
                                tile_mode_from_extend(gradient.extend),
                                None,
                            ),
                            interpolation,
                        ),
                        &brush_transform.map(super::sk_kurbo::matrix_from_affine),
                    )
                } else {
                    two_point_conical_gradient(
                        (start_center, start_radius),
                        (end_center, end_radius),
                        &skia_safe::gradient::Gradient::new(
                            Colors::new(
                                &colors[..],
                                Some(&positions[..]),
                                tile_mode_from_extend(gradient.extend),
                                None,
                            ),
                            interpolation,
                        ),
                        &brush_transform.map(super::sk_kurbo::matrix_from_affine),
                    )
                }
            }
            GradientKind::Sweep(sweep_gradient_position) => {
                let mut colors: Vec<SkColor4f> = vec![];
                let mut positions: Vec<f32> = vec![];

                for color_stop in gradient.stops.iter() {
                    colors.push(color4f_from_dynamic_color(color_stop.color));
                    positions.push(color_stop.offset);
                }
                let center = super::sk_kurbo::pt_from(sweep_gradient_position.center);

                let interpolation = skia_safe::gradient_shader::Interpolation {
                    color_space: gradient_shader_cs_from_cs_tag(gradient.interpolation_cs),
                    in_premul: skia_safe::gradient_shader::interpolation::InPremul::Yes,
                    hue_method: gradient_shader_hue_method_from_hue_direction(
                        gradient.hue_direction,
                    ),
                };

                sweep_gradient(
                    center,
                    (
                        rad_to_deg(sweep_gradient_position.start_angle),
                        rad_to_deg(sweep_gradient_position.end_angle),
                    ),
                    &skia_safe::gradient::Gradient::new(
                        Colors::new(
                            &colors[..],
                            Some(&positions[..]),
                            tile_mode_from_extend(gradient.extend),
                            None,
                        ),
                        interpolation,
                    ),
                    &brush_transform.map(super::sk_kurbo::matrix_from_affine),
                )
            }
        }
    }

    /// Rostrum patch: the one colour a gradient with no size draws as (CSS Images: its edge colour): the last stop when
    /// padded, the mean of the stops when it repeats.
    pub(super) fn degenerate_colour(gradient: &Gradient) -> SkColor4f {
        let colours: Vec<SkColor4f> = gradient.stops.iter().map(|s| color4f_from_dynamic_color(s.color)).collect();
        match (gradient.extend, colours.last()) {
            (_, None) => SkColor4f::new(0.0, 0.0, 0.0, 0.0),
            (peniko::Extend::Pad, Some(last)) => *last,
            _ => {
                let n = colours.len() as f32;
                let sum = colours.iter().fold([0.0f32; 4], |a, c| [a[0] + c.r, a[1] + c.g, a[2] + c.b, a[3] + c.a]);
                SkColor4f::new(sum[0] / n, sum[1] / n, sum[2] / n, sum[3] / n)
            }
        }
    }

    pub(super) fn path_fill_type_from_fill(fill: Fill) -> SkPathFillType {
        match fill {
            Fill::NonZero => SkPathFillType::Winding,
            Fill::EvenOdd => SkPathFillType::EvenOdd,
        }
    }

    pub(super) fn color4f_from_alpha_color(color: AlphaColor<Srgb>) -> SkColor4f {
        SkColor4f::new(
            color.components[0],
            color.components[1],
            color.components[2],
            color.components[3],
        )
    }

    pub(super) fn color4f_from_dynamic_color(color: DynamicColor) -> SkColor4f {
        let color = color.to_alpha_color::<Srgb>();
        SkColor4f::new(
            color.components[0],
            color.components[1],
            color.components[2],
            color.components[3],
        )
    }

    pub(super) fn gradient_shader_cs_from_cs_tag(
        color_space: ColorSpaceTag,
    ) -> SkGradientShaderColorSpace {
        match color_space {
            ColorSpaceTag::Srgb => SkGradientShaderColorSpace::SRGB,
            ColorSpaceTag::LinearSrgb => SkGradientShaderColorSpace::SRGBLinear,
            ColorSpaceTag::Lab => SkGradientShaderColorSpace::Lab,
            ColorSpaceTag::Lch => SkGradientShaderColorSpace::LCH,
            ColorSpaceTag::Hsl => SkGradientShaderColorSpace::HSL,
            ColorSpaceTag::Hwb => SkGradientShaderColorSpace::HWB,
            ColorSpaceTag::Oklab => SkGradientShaderColorSpace::OKLab,
            ColorSpaceTag::Oklch => SkGradientShaderColorSpace::OKLCH,
            ColorSpaceTag::DisplayP3 => SkGradientShaderColorSpace::DisplayP3,
            ColorSpaceTag::A98Rgb => SkGradientShaderColorSpace::A98RGB,
            ColorSpaceTag::ProphotoRgb => SkGradientShaderColorSpace::ProphotoRGB,
            ColorSpaceTag::Rec2020 => SkGradientShaderColorSpace::Rec2020,
            _ => SkGradientShaderColorSpace::SRGB, // ToDo: overview unsupported color space tags and possibly document it, for now just fallback
        }
    }

    pub(super) fn gradient_shader_hue_method_from_hue_direction(
        direction: HueDirection,
    ) -> SkGradientShaderHueMethod {
        match direction {
            HueDirection::Shorter => SkGradientShaderHueMethod::Shorter,
            HueDirection::Longer => SkGradientShaderHueMethod::Longer,
            HueDirection::Increasing => SkGradientShaderHueMethod::Increasing,
            HueDirection::Decreasing => SkGradientShaderHueMethod::Decreasing,
            _ => unreachable!(),
        }
    }

    pub(super) fn tile_mode_from_extend(extend: Extend) -> SkTileMode {
        match extend {
            Extend::Pad => SkTileMode::Clamp,
            Extend::Repeat => SkTileMode::Repeat,
            Extend::Reflect => SkTileMode::Mirror,
        }
    }

    pub(super) fn blend_mode_from(blend_mode: BlendMode) -> SkBlendMode {
        if blend_mode.mix == Mix::Normal {
            match blend_mode.compose {
                Compose::Clear => SkBlendMode::Clear,
                Compose::Copy => SkBlendMode::Src,
                Compose::Dest => SkBlendMode::Dst,
                Compose::SrcOver => SkBlendMode::SrcOver,
                Compose::DestOver => SkBlendMode::DstOver,
                Compose::SrcIn => SkBlendMode::SrcIn,
                Compose::DestIn => SkBlendMode::DstIn,
                Compose::SrcOut => SkBlendMode::SrcOut,
                Compose::DestOut => SkBlendMode::DstOut,
                Compose::SrcAtop => SkBlendMode::SrcATop,
                Compose::DestAtop => SkBlendMode::DstATop,
                Compose::Xor => SkBlendMode::Xor,
                Compose::Plus => SkBlendMode::Plus,
                Compose::PlusLighter => SkBlendMode::Plus,
            }
        } else {
            match blend_mode.mix {
                Mix::Normal => unreachable!(), // Handled above
                Mix::Multiply => SkBlendMode::Multiply,
                Mix::Screen => SkBlendMode::Screen,
                Mix::Overlay => SkBlendMode::Overlay,
                Mix::Darken => SkBlendMode::Darken,
                Mix::Lighten => SkBlendMode::Lighten,
                Mix::ColorDodge => SkBlendMode::ColorDodge,
                Mix::ColorBurn => SkBlendMode::ColorBurn,
                Mix::HardLight => SkBlendMode::HardLight,
                Mix::SoftLight => SkBlendMode::SoftLight,
                Mix::Difference => SkBlendMode::Difference,
                Mix::Exclusion => SkBlendMode::Exclusion,
                Mix::Hue => SkBlendMode::Hue,
                Mix::Saturation => SkBlendMode::Saturation,
                Mix::Color => SkBlendMode::Color,
                Mix::Luminosity => SkBlendMode::Luminosity,
            }
        }
    }
}

mod sk_kurbo {
    use kurbo::{Affine, PathEl, Point};
    use kurbo::{Rect, RoundedRect, Shape};
    use skia_safe::M44 as SkM44;
    use skia_safe::Matrix as SkMatrix;
    use skia_safe::Path as SkPath;
    use skia_safe::PathBuilder as SkPathBuilder;
    use skia_safe::Point as SkPoint;
    use skia_safe::RRect as SkRRect;
    use skia_safe::Rect as SkRect;

    pub(super) fn rect_from(rect: Rect) -> SkRect {
        SkRect::new(
            rect.x0 as f32,
            rect.y0 as f32,
            rect.x1 as f32,
            rect.y1 as f32,
        )
    }

    pub(super) fn rrect_from(rrect: RoundedRect) -> SkRRect {
        let rect = rect_from(rrect.rect());
        let radii = rrect.radii();
        // Corner order: upper-left, upper-right, lower-right, lower-left
        SkRRect::new_rect_radii(
            rect,
            &[
                SkPoint::new(radii.top_left as f32, radii.top_left as f32),
                SkPoint::new(radii.top_right as f32, radii.top_right as f32),
                SkPoint::new(radii.bottom_right as f32, radii.bottom_right as f32),
                SkPoint::new(radii.bottom_left as f32, radii.bottom_left as f32),
            ],
        )
    }

    pub(super) fn m44_from_affine(affine: Affine) -> SkM44 {
        let m = affine.as_coeffs();
        let scale_x = m[0] as f32;
        let shear_y = m[1] as f32;
        let shear_x = m[2] as f32;
        let scale_y = m[3] as f32;
        let translate_x = m[4] as f32;
        let translate_y = m[5] as f32;

        SkM44::col_major(&[
            scale_x,
            shear_y,
            0.0,
            0.0,
            shear_x,
            scale_y,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            translate_x,
            translate_y,
            0.0,
            1.0,
        ])
    }

    pub(super) fn matrix_from_affine(affine: Affine) -> SkMatrix {
        let m = affine.as_coeffs();
        let scale_x = m[0] as f32;
        let shear_y = m[1] as f32;
        let shear_x = m[2] as f32;
        let scale_y = m[3] as f32;
        let translate_x = m[4] as f32;
        let translate_y = m[5] as f32;

        SkMatrix::new_all(
            scale_x,
            shear_x,
            translate_x,
            shear_y,
            scale_y,
            translate_y,
            0.0,
            0.0,
            1.0,
        )
    }

    pub(super) fn pt_from(p: Point) -> SkPoint {
        SkPoint::new(p.x as f32, p.y as f32)
    }

    /// Rostrum patch: segments of zero length are left out. A box with square corners comes from Blitz as a
    /// rounded rect whose corner arcs are points; with them Skia saw a non-convex path and rasterised its
    /// coverage on the CPU (~1 ms for a full-frame background); without them it is a rect (convex, on the GPU).
    pub(super) fn path_from_shape(shape: &impl Shape) -> SkPath {
        let mut sk_path = SkPathBuilder::new();
        let mut at = kurbo::Point::ZERO;
        let mut start = kurbo::Point::ZERO;

        if let Some(path_els) = shape.as_path_slice() {
            for path_el in path_els {
                append_path_el_to_sk_path(path_el, &mut sk_path, &mut at, &mut start);
            }
        } else {
            for path_el in shape.path_elements(0.1) {
                append_path_el_to_sk_path(&path_el, &mut sk_path, &mut at, &mut start);
            }
        }

        sk_path.detach()
    }

    fn append_path_el_to_sk_path(path_el: &PathEl, sk_path: &mut SkPathBuilder, at: &mut kurbo::Point, start: &mut kurbo::Point) {
        match path_el {
            PathEl::MoveTo(p) => {
                *at = *p;
                *start = *p;
                _ = sk_path.move_to(pt_from(*p));
                return;
            }
            PathEl::ClosePath => {
                *at = *start;
                _ = sk_path.close();
                return;
            }
            _ => {}
        }
        let end = path_el.end_point().unwrap();
        let degenerate = match path_el {
            PathEl::LineTo(p) => *p == *at,
            PathEl::QuadTo(p1, p2) => *p1 == *at && *p2 == *at,
            PathEl::CurveTo(p1, p2, p3) => *p1 == *at && *p2 == *at && *p3 == *at,
            _ => false,
        };
        if degenerate {
            return;
        }
        match path_el {
            PathEl::LineTo(p) => _ = sk_path.line_to(pt_from(*p)),
            PathEl::QuadTo(p1, p2) => _ = sk_path.quad_to(pt_from(*p1), pt_from(*p2)),
            PathEl::CurveTo(p1, p2, p3) => _ = sk_path.cubic_to(pt_from(*p1), pt_from(*p2), pt_from(*p3)),
            _ => {}
        };
        *at = end;
    }
}


/// A shader primitive (Rostrum patch, round 5): its SkSL compiled once per process (cached by source), its
/// uniforms set by name, run as a runtime-shader image filter on the input. A program that does not compile,
/// a uniform that does not fit, or a filter Skia will not build, is recorded in `anyrender::filters::shader_errors` (the caller fails the
/// frame with it) and the input passes through.
/// A colour program with child images (Rostrum patch, round 7: LUTs): a runtime colour filter whose
/// `uniform shader` children are the registered images, read by texel (nearest, clamped).
fn runtime_color_filter(r: &anyrender::filters::RuntimeShaderFilter, input: Option<ImageFilter>) -> Option<ImageFilter> {
    use skia_safe::runtime_effect::ChildPtr;
    use skia_safe::RuntimeEffect;
    use std::collections::HashMap;
    thread_local! {
        static EFFECTS: std::cell::RefCell<HashMap<Arc<str>, Result<RuntimeEffect, String>>> = Default::default();
    }
    let name = effect_name(&r.program).to_string();
    let effect = EFFECTS.with(|cache| cache.borrow_mut().entry(r.program.clone()).or_insert_with(|| RuntimeEffect::make_for_color_filter(&*r.program, None)).clone());
    let effect = match effect {
        Ok(e) => e,
        Err(e) => {
            anyrender::filters::shader_errors::push(format!("the {name} effect's shader failed to compile: {e}"));
            return None;
        }
    };
    let mut data = vec![0u8; effect.uniform_size()];
    // Rostrum patch: a colour program that reads the working space gets it from the painter (working_space::kind).
    if let Some(u) = effect.uniforms().iter().find(|u| u.name() == "rostrumWorking") {
        data[u.offset()..u.offset() + 4].copy_from_slice(&crate::working_space::kind().to_ne_bytes());
    }
    for (uname, values) in &r.uniforms {
        let Some(u) = effect.uniforms().iter().find(|u| u.name() == uname) else {
            if !anyrender::filters::PAINTER_UNIFORMS.contains(&uname.as_str()) {
                anyrender::filters::shader_errors::push(format!("the {name} effect's shader has no uniform \"{uname}\""));
            }
            continue;
        };
        if u.size_in_bytes() != values.len() * 4 {
            anyrender::filters::shader_errors::push(format!("the {name} effect's uniform \"{uname}\" takes {} floats; got {}", u.size_in_bytes() / 4, values.len()));
            continue;
        }
        for (i, v) in values.iter().enumerate() {
            data[u.offset() + i * 4..u.offset() + i * 4 + 4].copy_from_slice(&v.to_ne_bytes());
        }
    }
    let mut children = vec![];
    for child in effect.children() {
        let Some((id, img)) = r.images.iter().find(|(n, _)| n == child.name()).and_then(|(_, id)| anyrender::filters::images::get(*id).map(|i| (*id, i))) else {
            anyrender::filters::shader_errors::push(format!("the {name} effect's shader has no image for \"{}\"", child.name()));
            return None;
        };
        let (ct, bpp) = if img.half { (skia_safe::ColorType::RGBAF16, 8) } else { (skia_safe::ColorType::RGBA8888, 4) };
        let info = skia_safe::ImageInfo::new((img.width as i32, img.height as i32), ct, skia_safe::AlphaType::Unpremul, None);
        // Rostrum patch (G7, hem): kept between paints (`filter_image`).
        let Some(image) = filter_image(id, &img, &info, || skia_safe::images::raster_from_data(&info, skia_safe::Data::new_copy(&img.rgba), img.width as usize * bpp)) else {
            anyrender::filters::shader_errors::push(format!("the {name} effect's image \"{}\" could not be made a Skia image", child.name()));
            return None;
        };
        let sampling = skia_safe::SamplingOptions::new(skia_safe::FilterMode::Nearest, skia_safe::MipmapMode::None);
        let Some(shader) = image.to_shader((skia_safe::TileMode::Clamp, skia_safe::TileMode::Clamp), sampling, None) else {
            anyrender::filters::shader_errors::push(format!("the {name} effect's image \"{}\" could not be made a shader", child.name()));
            return None;
        };
        children.push(ChildPtr::Shader(shader));
    }
    // A linked effect Skia still refuses to build (uniform data or children that do not fit) fails the frame too.
    let Some(cf) = effect.make_color_filter(skia_safe::Data::new_copy(&data), Some(children.as_slice())) else {
        anyrender::filters::shader_errors::push(format!("the {name} effect's shader compiled but Skia could not build its colour filter (uniforms or children do not match the program)"));
        return None;
    };
    let filter = skia_safe::image_filters::color_filter(cf, input, None);
    if filter.is_none() {
        anyrender::filters::shader_errors::push(format!("the {name} effect's colour filter could not be applied to its input"));
    }
    filter
}

fn runtime_shader_filter(r: &anyrender::filters::RuntimeShaderFilter, input: Option<ImageFilter>, secondary: Option<ImageFilter>) -> Option<ImageFilter> {
    // Rostrum patch (G3, matte seam): a blender program `half4 main(half4 m, half4 c)` takes two inputs: `in` is the
    // source `m` (the matte image), `in2` the destination `c` (the picture).
    if r.program.contains("half4 main(half4 m, half4 c)") {
        return runtime_blender_filter(r, input, secondary);
    }
    // Rostrum patch (G4): the windows' matte shader reads no picture and takes uniform arrays (a runtime-shader builder cannot).
    if effect_name(&r.program) == "matteWindow" {
        return runtime_window_filter(r);
    }
    // Rostrum patch: a colour program (`half4 main(half4 …)`: a LUT, a view's inverse) is a colour filter.
    if r.program.contains("half4 main(half4") {
        return runtime_color_filter(r, input);
    }
    // Rostrum patch (X4): a coordinate shader with child images (the AOV tools: depth, velocity beside the picture). skia-safe's
    // runtime-shader builder has no `set_child`, so the images ride in the shader's one input: k-th image drawn into the box
    // moved k box-widths right (nearest, the box's size, tagged with the working space like an feImage), merged with the input;
    // the shader reads image k at `p + (k·box.w, 0)` and clamps picture reads into its box. The sample radius reaches them.
    let mut input = input;
    let mut sample_radius = r.sample_radius;
    if !r.images.is_empty() {
        let bx = r.uniforms.iter().find(|(n, _)| n == "box").map(|(_, v)| v.clone()).unwrap_or_default();
        if bx.len() != 4 {
            anyrender::filters::shader_errors::push(format!("the {} effect has child images but no box", effect_name(&r.program)));
            return None;
        }
        let mut parts = vec![input.clone()];
        for (k, (name, id)) in r.images.iter().enumerate() {
            let Some(img) = anyrender::filters::images::get(*id).filter(|i| i.half) else {
                anyrender::filters::shader_errors::push(format!("the {} effect's image \"{name}\" is missing or not a half-float picture", effect_name(&r.program)));
                return None;
            };
            let info = skia_safe::ImageInfo::new((img.width as i32, img.height as i32), skia_safe::ColorType::RGBAF16, skia_safe::AlphaType::Premul, crate::working_space::get());
            // Rostrum patch (G7, hem): kept between paints like an feImage's (`filter_image`), not copied and uploaded again each frame.
            let Some(image) = filter_image(*id, &img, &info, || skia_safe::images::raster_from_data(&info, skia_safe::Data::new_copy(&img.rgba), img.width as usize * 8)) else {
                anyrender::filters::shader_errors::push(format!("the {} effect's image \"{name}\" could not be made a Skia image", effect_name(&r.program)));
                return None;
            };
            let dx = (k as f32 + 1.0) * bx[2];
            let dst = skia_safe::Rect::new(bx[0] + dx, bx[1], bx[0] + dx + bx[2], bx[1] + bx[3]);
            parts.push(skia_safe::image_filters::image(image, None, Some(&dst), skia_safe::SamplingOptions::new(skia_safe::FilterMode::Nearest, skia_safe::MipmapMode::None)));
        }
        input = skia_safe::image_filters::merge(parts, None);
        sample_radius = sample_radius.max((r.images.len() as f32 + 1.0) * bx[2]);
    }
    use skia_safe::runtime_effect::RuntimeShaderBuilder;
    use skia_safe::RuntimeEffect;
    use std::collections::HashMap;
    thread_local! {
        static EFFECTS: std::cell::RefCell<HashMap<Arc<str>, Result<RuntimeEffect, String>>> = Default::default();
    }
    let effect = EFFECTS.with(|cache| {
        cache.borrow_mut().entry(r.program.clone()).or_insert_with(|| RuntimeEffect::make_for_shader(&*r.program, None)).clone()
    });
    let effect = match effect {
        Ok(e) => e,
        Err(e) => {
            anyrender::filters::shader_errors::push(format!("the {} effect's shader failed to compile: {e}", effect_name(&r.program)));
            return None;
        }
    };
    let mut builder = RuntimeShaderBuilder::new(effect.clone());
    // Rostrum patch: a coordinate shader that reads the working space (the comp's grain) gets it from the painter too.
    if effect.find_uniform("rostrumWorking").is_some() {
        let _ = builder.set_uniform_float("rostrumWorking", &[crate::working_space::kind()]);
    }
    for (name, values) in &r.uniforms {
        let Some(u) = effect.find_uniform(name) else {
            if !anyrender::filters::PAINTER_UNIFORMS.contains(&name.as_str()) {
                anyrender::filters::shader_errors::push(format!("the {} effect's shader has no uniform \"{name}\"", effect_name(&r.program)));
            }
            continue;
        };
        if u.size_in_bytes() != values.len() * 4 || builder.set_uniform_float(name, values).is_err() {
            anyrender::filters::shader_errors::push(format!("the {} effect's uniform \"{name}\" takes {} floats; got {}", effect_name(&r.program), u.size_in_bytes() / 4, values.len()));
        }
    }
    let filter = skia_safe::image_filters::runtime_shader_with_options(&builder, sample_radius, "src", input, false);
    if filter.is_none() {
        anyrender::filters::shader_errors::push(format!("the {} effect's shader linked but Skia could not build its image filter", effect_name(&r.program)));
    }
    filter
}

/// A shader that makes its output from `box` and its uniforms alone (G4's windows, rostrum-color grade/window_sksl.rs): its uniforms
/// are packed by offset (arrays too), and it fills the filter's region like any shader image filter.
fn runtime_window_filter(r: &anyrender::filters::RuntimeShaderFilter) -> Option<ImageFilter> {
    use skia_safe::RuntimeEffect;
    use std::collections::HashMap;
    thread_local! {
        static EFFECTS: std::cell::RefCell<HashMap<Arc<str>, Result<RuntimeEffect, String>>> = Default::default();
    }
    let effect = EFFECTS.with(|cache| cache.borrow_mut().entry(r.program.clone()).or_insert_with(|| RuntimeEffect::make_for_shader(&*r.program, None)).clone());
    let effect = match effect {
        Ok(e) => e,
        Err(e) => {
            anyrender::filters::shader_errors::push(format!("the matteWindow effect's shader failed to compile: {e}"));
            return None;
        }
    };
    let mut data = vec![0u8; effect.uniform_size()];
    for (uname, values) in &r.uniforms {
        let Some(u) = effect.uniforms().iter().find(|u| u.name() == uname) else {
            anyrender::filters::shader_errors::push(format!("the matteWindow effect's shader has no uniform \"{uname}\""));
            continue;
        };
        if u.size_in_bytes() != values.len() * 4 {
            anyrender::filters::shader_errors::push(format!("the matteWindow effect's uniform \"{uname}\" takes {} floats; got {}", u.size_in_bytes() / 4, values.len()));
            continue;
        }
        for (i, v) in values.iter().enumerate() {
            data[u.offset() + i * 4..u.offset() + i * 4 + 4].copy_from_slice(&v.to_ne_bytes());
        }
    }
    let filter = effect.make_shader(skia_safe::Data::new_copy(&data), &[], None).and_then(|s| skia_safe::image_filters::shader(s, None));
    if filter.is_none() {
        anyrender::filters::shader_errors::push("the matteWindow effect's shader compiled but Skia could not build its filter".to_string());
    }
    filter
}

/// Most moves one streak averages (`draw_cached_streak`): the shader's loop bound and its `m` array (two rows a move).
const STREAK_MOVES: usize = 128;

/// Rostrum patch (streak blur): the picture (`image`) averaged over `n` inverse moves, each two rows of `m`; the sum is
/// kept in float, as 128 adds in half would lose the low bits.
const STREAK_SKSL: &str = "uniform shader image;
uniform float4 m[256];
uniform float n;
half4 main(float2 p) {
    float4 sum = float4(0);
    for (int i = 0; i < 128; i++) {
        if (float(i) >= n) break;
        float4 r0 = m[2 * i];
        float4 r1 = m[2 * i + 1];
        sum += float4(image.eval(float2(dot(r0.xy, p) + r0.z, dot(r1.xy, p) + r1.z)));
    }
    return half4(sum / n);
}";

/// The streak shader, compiled once per thread (None, said once on stderr, if Skia refuses it: the caller draws copies).
fn streak_effect() -> Option<skia_safe::RuntimeEffect> {
    thread_local! {
        static EFFECT: Option<skia_safe::RuntimeEffect> = skia_safe::RuntimeEffect::make_for_shader(STREAK_SKSL, None)
            .map_err(|e| eprintln!("rostrum: the motion-blur streak shader failed to compile: {e}"))
            .ok();
    }
    EFFECT.with(|e| e.clone())
}

/// The effect a shader program belongs to (its first line, written by the SVG filter reader).
fn effect_name(program: &str) -> &str {
    program.lines().next().and_then(|l| l.strip_prefix("// rostrum effect: ")).unwrap_or("?")
}

/// A runtime blender (Rostrum patch, G3): `half4 main(half4 m, half4 c)` over two filter inputs, `m` from `in` (the
/// source) and `c` from `in2` (the destination, the picture), its uniforms set by their offsets and its LUT / table
/// images as children like `runtime_color_filter`. How a grade reads a matte image per pixel.
fn runtime_blender_filter(r: &anyrender::filters::RuntimeShaderFilter, source: Option<ImageFilter>, destination: Option<ImageFilter>) -> Option<ImageFilter> {
    use skia_safe::runtime_effect::ChildPtr;
    use skia_safe::RuntimeEffect;
    use std::collections::HashMap;
    thread_local! {
        static EFFECTS: std::cell::RefCell<HashMap<Arc<str>, Result<RuntimeEffect, String>>> = Default::default();
    }
    let name = effect_name(&r.program).to_string();
    let effect = EFFECTS.with(|cache| cache.borrow_mut().entry(r.program.clone()).or_insert_with(|| RuntimeEffect::make_for_blender(&*r.program, None)).clone());
    let effect = match effect {
        Ok(e) => e,
        Err(e) => {
            anyrender::filters::shader_errors::push(format!("the {name} effect's shader failed to compile: {e}"));
            return None;
        }
    };
    let mut data = vec![0u8; effect.uniform_size()];
    if let Some(u) = effect.uniforms().iter().find(|u| u.name() == "rostrumWorking") {
        data[u.offset()..u.offset() + 4].copy_from_slice(&crate::working_space::kind().to_ne_bytes());
    }
    for (uname, values) in &r.uniforms {
        let Some(u) = effect.uniforms().iter().find(|u| u.name() == uname) else {
            if !anyrender::filters::PAINTER_UNIFORMS.contains(&uname.as_str()) {
                anyrender::filters::shader_errors::push(format!("the {name} effect's shader has no uniform \"{uname}\""));
            }
            continue;
        };
        if u.size_in_bytes() != values.len() * 4 {
            anyrender::filters::shader_errors::push(format!("the {name} effect's uniform \"{uname}\" takes {} floats; got {}", u.size_in_bytes() / 4, values.len()));
            continue;
        }
        for (i, v) in values.iter().enumerate() {
            data[u.offset() + i * 4..u.offset() + i * 4 + 4].copy_from_slice(&v.to_ne_bytes());
        }
    }
    let mut children = vec![];
    for child in effect.children() {
        let Some((id, img)) = r.images.iter().find(|(n, _)| n == child.name()).and_then(|(_, id)| anyrender::filters::images::get(*id).map(|i| (*id, i))) else {
            anyrender::filters::shader_errors::push(format!("the {name} effect's shader has no image for \"{}\"", child.name()));
            return None;
        };
        let (ct, bpp) = if img.half { (skia_safe::ColorType::RGBAF16, 8) } else { (skia_safe::ColorType::RGBA8888, 4) };
        let info = skia_safe::ImageInfo::new((img.width as i32, img.height as i32), ct, skia_safe::AlphaType::Unpremul, None);
        // Rostrum patch (G7, hem): kept between paints (`filter_image`).
        let image = filter_image(id, &img, &info, || skia_safe::images::raster_from_data(&info, skia_safe::Data::new_copy(&img.rgba), img.width as usize * bpp))?;
        let sampling = skia_safe::SamplingOptions::new(skia_safe::FilterMode::Nearest, skia_safe::MipmapMode::None);
        children.push(ChildPtr::Shader(image.to_shader((skia_safe::TileMode::Clamp, skia_safe::TileMode::Clamp), sampling, None)?));
    }
    let blender = effect.make_blender(skia_safe::Data::new_copy(&data), Some(children.as_slice()))?;
    skia_safe::image_filters::blend(blender, destination, source, None)
}
