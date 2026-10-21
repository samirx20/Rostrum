//! Paints a laid-out page with Skia into one surface: on the GPU (OpenGL through WGL; WGL needs a window
//! for its context, so a hidden one is made) or, when asked, on the CPU. Same drawing code either way;
//! frames are read back as stored (premultiplied half floats) and go through the output step (color.rs).
//!
//! Every surface is half float (F16) in the render's working colour space (color.rs `surface_space`), so
//! gradients, blurs and blends keep more than 8 bits whatever the output, and a preview is painted exactly as
//! the export (no 8-bit path). Motion blur sums sub-frames into a second F16 surface (`accumulate`), each weighted,
//! so N shutter samples average without 8-bit banding. A held paint (`paint` with `held`) then draws that sum
//! where the page marks it (`data-shutter-held`), inside the marked element's layers: a full-frame grade or
//! effect stack applied once after the shutter, as a camera's would be.

use std::ffi::CString;
use std::num::{NonZeroIsize, NonZeroU32};

use anyrender_skia::{SkiaSceneCache, SkiaScenePainter};
use glutin::config::ConfigTemplateBuilder;
use glutin::context::{ContextAttributesBuilder, NotCurrentGlContext, PossiblyCurrentContext};
use glutin::display::{Display, DisplayApiPreference, GlDisplay};
use glutin::surface::{Surface as GlSurface, SurfaceAttributesBuilder, WindowSurface};
use raw_window_handle::{RawDisplayHandle, RawWindowHandle, Win32WindowHandle, WindowsDisplayHandle};
use skia_safe::gpu::{self, direct_contexts, gl::Interface, Budgeted, DirectContext, SurfaceOrigin};
use skia_safe::{AlphaType, BlendMode, Color, ColorSpace, ColorType, ImageInfo, Paint, Surface};

use crate::readback::Readback;

/// A GL context with Skia on it. Making one takes ~0.2 s (the driver loads), so `serve` makes it as the
/// process starts, while the host is still preparing the render (serve.rs).
pub struct Gl {
    gr: DirectContext,
    /// GL_RENDERER: which GPU paints.
    renderer: String,
    /// Pipelined readback (readback.rs), when the driver has pixel buffers and fences.
    readback: Option<Readback>,
    /// The exact output step on the GPU (gpu_output.rs), or why it can't run here.
    exact: Result<crate::gpu_output::GpuOutput, String>,
    _context: (PossiblyCurrentContext, GlSurface<WindowSurface>),
}

/// The surface the last picture is in: a plain paint, the motion-blur sum, or a held paint over it.
#[derive(Clone, Copy, PartialEq)]
enum Last {
    Frame,
    Sum,
    Held,
}

// Field order is drop order: the surface and cached GPU images go before the GL context they live in
// (dropped after it, they hang the driver at exit).
pub struct Painter {
    surface: Surface,
    /// Motion blur's running sum of weighted sub-frames (F16), made on first use.
    acc: Option<Surface>,
    /// A held paint (F16, made on first use): the frame drawn over the sum, kept at the sum's precision.
    held: Option<Surface>,
    /// Which surface holds the last picture (what `read` / `start_read` read).
    last: Last,
    cache: SkiaSceneCache,
    /// The GPU output step of playing frames (`read_output8`), made on first use and kept while the table is the same.
    out8: Option<Out8>,
    gl: Option<Gl>,
    width: u32,
    height: u32,
    /// The working colour space every surface is tagged with (None: display values, unmanaged).
    space: Option<ColorSpace>,
    /// The last frame's time recording the drawing and submitting it to the GPU, reading it back (waiting for
    /// the GPU to finish it) and converting the pixels (ms), for profiling.
    /// The frame index of each readback in flight (`start_read`), oldest first.
    in_flight: std::collections::VecDeque<u32>,
    pub last_draw_ms: f64,
    pub last_flush_ms: f64,
    pub last_read_ms: f64,
    /// Of `last_read_ms`: the wait for the GPU to finish the frame (`read`; 0 when read in flight).
    pub last_gpu_ms: f64,
    pub last_convert_ms: f64,
    /// The comp-cache buffers the last paint tapped (anyrender_skia `finish_taps`): how many, and the time reading them
    /// back (ms); `taps_written` the time it waited for them to be written.
    pub last_taps: usize,
    pub last_tap_read_ms: f64,
    pub last_tap_write_ms: f64,
}

/// The output step on the GPU (`read_output8`): the program, the checked table it reads (color.rs `OutputLut::gpu_table`, as an
/// F16 image) and the 8-bit surface it draws into, for the table at `key` (its address).
struct Out8 {
    key: usize,
    effect: skia_safe::RuntimeEffect,
    uniforms: skia_safe::Data,
    lut: skia_safe::Image,
    target: Surface,
}

/// The output step as the CPU's playing frames take it (color.rs `output` with `fast`): each straight channel on the table's
/// shaper, tetrahedral interpolation between the cell's corners, alpha kept (straight colour out, as `output` writes it).
const OUT8_SKSL: &str = r#"
uniform shader src;
uniform shader lut;
uniform float n;
uniform float toe;
uniform float lo;
uniform float hi;
uniform float s0;
uniform float s1;

float3 at(float3 i) {
    return lut.eval(float2(i.r + i.g * n + 0.5, i.b + 0.5)).rgb;
}

half4 main(float2 p) {
    float4 c = float4(src.eval(p));
    float a = clamp(c.a, 0.0, 1.0);
    if (!(a > 0.0)) {
        return half4(0.0);
    }
    float3 x = clamp(c.rgb / a, lo, hi);
    float3 s = sign(x) * log(1.0 + abs(x) / toe);
    float3 q = clamp((s - s0) / (s1 - s0) * (n - 1.0), 0.0, n - 1.0);
    float3 i = min(floor(q), n - 2.0);
    float3 f = q - i;
    float3 c0 = at(i);
    float3 c1 = at(i + 1.0);
    float3 o;
    if (f.r >= f.g) {
        if (f.g >= f.b) {
            float3 a1 = at(i + float3(1, 0, 0)); float3 a2 = at(i + float3(1, 1, 0));
            o = c0 + f.r * (a1 - c0) + f.g * (a2 - a1) + f.b * (c1 - a2);
        } else if (f.r >= f.b) {
            float3 a1 = at(i + float3(1, 0, 0)); float3 a2 = at(i + float3(1, 0, 1));
            o = c0 + f.r * (a1 - c0) + f.b * (a2 - a1) + f.g * (c1 - a2);
        } else {
            float3 a1 = at(i + float3(0, 0, 1)); float3 a2 = at(i + float3(1, 0, 1));
            o = c0 + f.b * (a1 - c0) + f.r * (a2 - a1) + f.g * (c1 - a2);
        }
    } else if (f.b >= f.g) {
        float3 a1 = at(i + float3(0, 0, 1)); float3 a2 = at(i + float3(0, 1, 1));
        o = c0 + f.b * (a1 - c0) + f.g * (a2 - a1) + f.r * (c1 - a2);
    } else if (f.b >= f.r) {
        float3 a1 = at(i + float3(0, 1, 0)); float3 a2 = at(i + float3(0, 1, 1));
        o = c0 + f.g * (a1 - c0) + f.b * (a2 - a1) + f.r * (c1 - a2);
    } else {
        float3 a1 = at(i + float3(0, 1, 0)); float3 a2 = at(i + float3(1, 1, 0));
        o = c0 + f.g * (a1 - c0) + f.r * (a2 - a1) + f.b * (c1 - a2);
    }
    return half4(half3(clamp(o, 0.0, 1.0)), half(a));
}
"#;

fn hidden_window() -> (isize, isize) {
    use windows_sys::Win32::System::LibraryLoader::GetModuleHandleW;
    use windows_sys::Win32::UI::WindowsAndMessaging::*;
    let class: Vec<u16> = "RostrumMotionGL\0".encode_utf16().collect();
    unsafe {
        let hinst = GetModuleHandleW(std::ptr::null());
        let mut wc: WNDCLASSW = std::mem::zeroed();
        wc.style = CS_OWNDC;
        wc.lpfnWndProc = Some(DefWindowProcW);
        wc.hInstance = hinst;
        wc.lpszClassName = class.as_ptr();
        RegisterClassW(&wc);
        let hwnd = CreateWindowExW(0, class.as_ptr(), class.as_ptr(), WS_OVERLAPPEDWINDOW, 0, 0, 64, 64, std::ptr::null_mut(), std::ptr::null_mut(), hinst, std::ptr::null());
        assert!(!hwnd.is_null(), "CreateWindowExW failed");
        (hwnd as isize, hinst as isize)
    }
}

fn info(width: u32, height: u32, space: Option<ColorSpace>) -> ImageInfo {
    ImageInfo::new((width as i32, height as i32), ColorType::RGBAF16, AlphaType::Premul, space)
}

fn new_surface(gl: Option<&mut Gl>, width: u32, height: u32, space: &Option<ColorSpace>) -> Result<Surface, String> {
    let info = info(width, height, space.clone());
    match gl {
        Some(gl) => gpu::surfaces::render_target(&mut gl.gr, Budgeted::Yes, &info, None, SurfaceOrigin::TopLeft, None, false, None).ok_or_else(|| "GPU render target (F16) failed".to_string()),
        None => skia_safe::surfaces::raster(&info, None, None).ok_or_else(|| "CPU surface (F16) failed".to_string()),
    }
}

/// Device size (px) from which glyphs are drawn as outlines instead of atlas masks (see `gl_context`).
pub const GLYPH_OUTLINE_PX: f32 = 32.0;

pub fn gl_context() -> Result<Gl, String> {
    let (hwnd, hinst) = hidden_window();
    let mut wh = Win32WindowHandle::new(NonZeroIsize::new(hwnd).unwrap());
    wh.hinstance = NonZeroIsize::new(hinst);
    let raw_window = RawWindowHandle::Win32(wh);
    let display = unsafe { Display::new(RawDisplayHandle::Windows(WindowsDisplayHandle::new()), DisplayApiPreference::Wgl(Some(raw_window))) }.map_err(|e| format!("WGL display: {e}"))?;
    let config = unsafe { display.find_configs(ConfigTemplateBuilder::new().build()) }.map_err(|e| format!("GL configs: {e}"))?.next().ok_or("no GL config")?;
    let ctx = unsafe { display.create_context(&config, &ContextAttributesBuilder::new().build(Some(raw_window))) }.map_err(|e| format!("GL context: {e}"))?;
    let attrs = SurfaceAttributesBuilder::<WindowSurface>::new().build(raw_window, NonZeroU32::new(64).unwrap(), NonZeroU32::new(64).unwrap());
    let gl_surface = unsafe { display.create_window_surface(&config, &attrs) }.map_err(|e| format!("GL surface: {e}"))?;
    let ctx = ctx.make_current(&gl_surface).map_err(|e| format!("make current: {e}"))?;
    let interface = Interface::new_load_with(|name| display.get_proc_address(&CString::new(name).unwrap())).ok_or("no GL interface")?;
    let renderer = unsafe {
        const GL_RENDERER: u32 = 0x1F01;
        let get = display.get_proc_address(c"glGetString");
        let get: extern "system" fn(u32) -> *const std::ffi::c_char = std::mem::transmute(get);
        let p = get(GL_RENDERER);
        if p.is_null() { String::new() } else { std::ffi::CStr::from_ptr(p).to_string_lossy().into_owned() }
    };
    // Clears as draws: on the AMD integrated GPU (WGL) a hardware clear of a freshly allocated render target is
    // lost, so the first frame a context drew had garbage in new layers (a CSS mask's layer came out empty).
    let mut opts = gpu::ContextOptions::default();
    opts.use_draw_instead_of_clear = skia_safe::gpu::ganesh::context_options::Enable::Yes;
    // A frame is a function of its time alone (rule 5, H7): glyph masks in Skia's GPU atlas come out 1–2 levels
    // different at their edges depending on which glyphs went into the atlas before (only big glyphs: a 250 px
    // title drifted, 44 px text didn't). Glyphs from GLYPH_OUTLINE_PX device pixels up are drawn as outlines, which
    // are the same whatever was drawn before, and sit at their exact sub-pixel position (atlas glyphs snap to whole
    // pixels vertically, a 1 px jitter on slow moves). Small text keeps the atlas and its hinting. Paint time: within
    // the noise (Meridian). `cold_warm_tests` guards it.
    opts.glyphs_as_paths_font_size = GLYPH_OUTLINE_PX;
    // Distance-field text would sit between the two thresholds; with both equal there is none (Skia requires min <= max).
    opts.min_distance_field_font_size = GLYPH_OUTLINE_PX;
    // Outlines are filled through Skia's multisampled path atlas (the one path renderer that keeps no shapes between
    // frames; turning it off brought the drift back through the triangulating renderer's cache). At its default 4
    // samples a big letter's edge has 3 in-between levels and steps visibly; 16 is as smooth as the glyph atlas was.
    opts.internal_multisample_count = 16;
    let mut gr = direct_contexts::make_gl(interface, Some(&opts)).ok_or("Skia GL context failed")?;
    let readback = Readback::new(|name| display.get_proc_address(name));
    let exact = crate::gpu_output::GpuOutput::new(|name| display.get_proc_address(name));
    gr.reset(None);
    Ok(Gl { gr, renderer, readback, exact, _context: (ctx, gl_surface) })
}

impl Painter {
    /// A GPU painter; fails (never silently falls back) when the GPU cannot be used. `space`: the working colour
    /// space (color.rs `surface_space`).
    pub fn gpu(width: u32, height: u32, space: Option<ColorSpace>) -> Result<Self, String> {
        Self::gpu_on(gl_context()?, width, height, space)
    }

    /// A GPU painter on a context made beforehand (gl_context).
    pub fn gpu_on(mut gl: Gl, width: u32, height: u32, space: Option<ColorSpace>) -> Result<Self, String> {
        let surface = new_surface(Some(&mut gl), width, height, &space)?;
        Ok(Self { gl: Some(gl), surface, acc: None, held: None, last: Last::Frame, width, height, space, in_flight: Default::default(), cache: SkiaSceneCache::default(), out8: None, last_draw_ms: 0.0, last_flush_ms: 0.0, last_read_ms: 0.0, last_gpu_ms: 0.0, last_convert_ms: 0.0, last_taps: 0, last_tap_read_ms: 0.0, last_tap_write_ms: 0.0 })
    }

    pub fn cpu(width: u32, height: u32, space: Option<ColorSpace>) -> Result<Self, String> {
        let surface = new_surface(None, width, height, &space)?;
        Ok(Self { gl: None, surface, acc: None, held: None, last: Last::Frame, width, height, space, in_flight: Default::default(), cache: SkiaSceneCache::default(), out8: None, last_draw_ms: 0.0, last_flush_ms: 0.0, last_read_ms: 0.0, last_gpu_ms: 0.0, last_convert_ms: 0.0, last_taps: 0, last_tap_read_ms: 0.0, last_tap_write_ms: 0.0 })
    }

    pub fn is_gpu(&self) -> bool {
        self.gl.is_some()
    }

    /// The GPU that paints (GL_RENDERER), or None on the CPU.
    pub fn gpu_name(&self) -> Option<&str> {
        self.gl.as_ref().map(|g| g.renderer.as_str())
    }

    /// Paints a frame: records it and submits it to the GPU without waiting, so the next frame (or motion-blur
    /// sub-frame) is laid out and recorded while the GPU draws this one; `read` waits for it. `held`: the
    /// motion-blur sum is the picture a `data-shutter-held` element draws in place of its children. An effect shader
    /// that failed to compile or link is an `Err` naming it (shader_errors).
    pub fn paint(&mut self, held: bool, mut draw: impl FnMut(&mut SkiaScenePainter<'_>)) -> Result<(), String> {
        // An earlier paint's taps still being written (a caller that did not wait) are finished first.
        self.taps_written()?;
        self.last_gpu_ms = 0.0;
        let t0 = std::time::Instant::now();
        if held {
            self.cache.held = Some(self.acc.as_mut().ok_or("a held paint before accumulate")?.image_snapshot());
            if self.held.is_none() {
                self.held = Some(new_surface(self.gl.as_mut(), self.width, self.height, &self.space)?);
            }
        }
        self.last = if held { Last::Held } else { Last::Frame };
        {
            let canvas = if held { self.held.as_mut().unwrap().canvas() } else { self.surface.canvas() };
            canvas.clear(Color::TRANSPARENT);
            // Half-float images were decoded into the working space: anyrender_skia tags them with it.
            anyrender_skia::working_space::set(self.space.clone());
            draw(&mut SkiaScenePainter::new(canvas, &mut self.cache));
        }
        self.cache.held = None;
        self.cache.next_gen();
        let t1 = std::time::Instant::now();
        if let Some(gl) = self.gl.as_mut() {
            gl.gr.flush_and_submit();
        }
        self.last_draw_ms = (t1 - t0).as_secs_f64() * 1000.0;
        self.last_flush_ms = t1.elapsed().as_secs_f64() * 1000.0;
        // The buffers the paint tapped for the comp's node cache, read back now that it is all submitted.
        (self.last_taps, self.last_tap_read_ms) = self.cache.finish_taps();
        // A shader that did not compile or link fails the frame (AGENTS.md rule 6), naming the effect and Skia's message.
        let shader_errors = anyrender::filters::shader_errors::take();
        if shader_errors.is_empty() { Ok(()) } else { Err(shader_errors.join("; ")) }
    }

    /// Waits until the comp-cache buffers the last paint tapped are written (they are written while the frame is read
    /// and converted); a write that failed is the `Err`.
    pub fn taps_written(&mut self) -> Result<(), String> {
        let t = std::time::Instant::now();
        let r = self.cache.taps_written();
        self.last_tap_write_ms = t.elapsed().as_secs_f64() * 1000.0;
        r
    }

    /// Adds the last painted frame to the motion-blur sum with `weight` (the weights of one frame's
    /// sub-frames add up to 1); `first` starts a new sum. Premultiplied colours add linearly, so the sum is
    /// the shutter's average of every sub-frame (an average of "over" composites is "over" of the average).
    pub fn accumulate(&mut self, first: bool, weight: f32) -> Result<(), String> {
        if self.acc.is_none() {
            self.acc = Some(new_surface(self.gl.as_mut(), self.width, self.height, &self.space)?);
        }
        let frame = self.surface.image_snapshot();
        let canvas = self.acc.as_mut().unwrap().canvas();
        if first {
            canvas.clear(Color::TRANSPARENT);
        }
        let mut paint = Paint::default();
        paint.set_blend_mode(BlendMode::Plus);
        // The weight scales alpha in a float colour matrix (unpremultiplied, so premultiplied colours scale with
        // it): a paint alpha is quantized to 8 bits on the GPU (1/14 → 18/255), and the sum came to 0.988.
        #[rustfmt::skip]
        let m = skia_safe::ColorMatrix::new(1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, weight, 0.0);
        paint.set_color_filter(skia_safe::color_filters::matrix(&m, None));
        canvas.draw_image(&frame, (0, 0), Some(&paint));
        self.last = Last::Sum;
        Ok(())
    }

    /// The surface holding the last picture.
    fn last_surface(&mut self) -> &mut Surface {
        match self.last {
            Last::Frame => &mut self.surface,
            Last::Sum => self.acc.as_mut().unwrap(),
            Last::Held => self.held.as_mut().unwrap(),
        }
    }

    /// Starts reading the last picture (a frame, the motion-blur sum or a held paint) back without waiting for
    /// it (readback.rs); `finish_read` collects it. False on the CPU or without pixel buffers: use `read`.
    pub fn start_read(&mut self, index: u32) -> bool {
        if self.gl.as_ref().map_or(true, |g| g.readback.is_none()) {
            return false;
        }
        let (w, h) = (self.width, self.height);
        let surface = self.last_surface();
        let Some(fbo) = gpu::surfaces::get_backend_render_target(surface, skia_safe::surface::BackendHandleAccess::FlushRead).and_then(|t| t.gl_framebuffer_info()).map(|i| i.fboid) else { return false };
        let gl = self.gl.as_mut().unwrap();
        gl.gr.flush_and_submit();
        gl.readback.as_mut().unwrap().start(fbo, w, h, true);
        // The readback bound GL state behind Skia's back.
        gl.gr.reset(None);
        self.in_flight.push_back(index);
        true
    }

    /// Frames started by `start_read` and not collected yet.
    pub fn reads_in_flight(&self) -> usize {
        self.gl.as_ref().and_then(|g| g.readback.as_ref()).map_or(0, |r| r.in_flight())
    }

    /// The oldest started frame: its stored bytes (premultiplied half floats) and the frame index it was started with.
    pub fn finish_read(&mut self) -> Result<(Vec<u8>, u32), String> {
        let t0 = std::time::Instant::now();
        let r = self.gl.as_mut().and_then(|g| g.readback.as_mut()).ok_or("no readback in flight")?.finish_oldest();
        self.last_read_ms = t0.elapsed().as_secs_f64() * 1000.0;
        let index = self.in_flight.pop_front().unwrap_or(0);
        r.map(|(raw, _)| (raw, index))
    }

    /// A playing frame through the output step on the GPU: the last picture drawn through `lut` (color.rs `OutputLut`, the
    /// table the CPU's playing frames use) into an 8-bit surface and read back as straight RGBA8 (what `color::output` with
    /// `fast` gives, without its dither): half the bytes to read and no per-pixel step on the CPU. None on the CPU.
    pub fn read_output8(&mut self, lut: &std::sync::Arc<crate::color::OutputLut>) -> Option<Result<Vec<u8>, String>> {
        let gl = self.gl.as_mut()?;
        let (w, h) = (self.width, self.height);
        let key = std::sync::Arc::as_ptr(lut) as usize;
        if self.out8.as_ref().is_none_or(|o| o.key != key) {
            self.out8 = None;
            let (n, [toe, lo, hi, s0, s1], bytes) = lut.gpu_table();
            let effect = match skia_safe::RuntimeEffect::make_for_shader(OUT8_SKSL, None) {
                Ok(e) => e,
                Err(e) => return Some(Err(format!("the GPU output step: {e}"))),
            };
            let info = ImageInfo::new(((n * n) as i32, n as i32), ColorType::RGBAF16, AlphaType::Premul, None);
            let lut_image = skia_safe::images::raster_from_data(&info, skia_safe::Data::new_copy(&bytes), n * n * 8)?;
            let lut_image = gpu::images::texture_from_image(&mut gl.gr, &lut_image, gpu::Mipmapped::No, Budgeted::Yes).unwrap_or(lut_image);
            let info8 = ImageInfo::new((w as i32, h as i32), ColorType::RGBA8888, AlphaType::Premul, None);
            let target = gpu::surfaces::render_target(&mut gl.gr, Budgeted::Yes, &info8, None, SurfaceOrigin::TopLeft, None, false, None)?;
            let mut u = vec![];
            for v in [n as f32, toe, lo, hi, s0, s1] {
                u.extend_from_slice(&v.to_le_bytes());
            }
            self.out8 = Some(Out8 { key, effect, uniforms: skia_safe::Data::new_copy(&u), lut: lut_image, target });
        }
        let t0 = std::time::Instant::now();
        let frame = self.last_surface().image_snapshot();
        let o = self.out8.as_mut().unwrap();
        let nearest = skia_safe::SamplingOptions::new(skia_safe::FilterMode::Nearest, skia_safe::MipmapMode::None);
        let clamp = (skia_safe::TileMode::Clamp, skia_safe::TileMode::Clamp);
        let children = [frame.to_shader(clamp, nearest, None)?.into(), o.lut.to_shader(clamp, nearest, None)?.into()];
        let shader = o.effect.make_shader(o.uniforms.clone(), &children, None)?;
        let mut paint = Paint::default();
        paint.set_shader(shader);
        paint.set_blend_mode(BlendMode::Src);
        o.target.canvas().draw_paint(&paint);
        drop(frame);
        let info8 = ImageInfo::new((w as i32, h as i32), ColorType::RGBA8888, AlphaType::Premul, None);
        let mut out = vec![0u8; w as usize * h as usize * 4];
        if let Some(gl) = self.gl.as_mut() {
            gl.gr.flush_submit_and_sync_cpu();
        }
        self.last_gpu_ms = t0.elapsed().as_secs_f64() * 1000.0;
        let ok = self.out8.as_mut().unwrap().target.read_pixels(&info8, &mut out, w as usize * 4, (0, 0));
        self.last_read_ms = t0.elapsed().as_secs_f64() * 1000.0;
        Some(if ok { Ok(out) } else { Err("frame readback (8-bit output) failed".into()) })
    }

    /// The last picture through the output step on the GPU, exact (gpu_output.rs): into `out` (the frame's size), the same
    /// bytes `color::output_into` gives from `read`, at a fraction of the time (8-bit read back, no step per pixel on the
    /// CPU but for rows holding partly transparent pixels, which are read and converted here). None where it can't
    /// run (on the CPU, or an output step without a channel table): use `read` and `color::output_into`.
    pub fn output_into(&mut self, spec: &crate::color::Spec, deep: bool, out: &mut [u8]) -> Option<Result<(), String>> {
        let codes = crate::color::gpu_codes(spec, deep)?;
        self.gl.as_ref()?.exact.as_ref().ok()?;
        let (w, h) = (self.width, self.height);
        let t0 = std::time::Instant::now();
        let tex = gpu::surfaces::get_backend_texture(self.last_surface(), skia_safe::surface::BackendHandleAccess::FlushRead)
            .and_then(|t| t.gl_texture_info())
            .filter(|i| i.target == 0x0DE1)?; // TEXTURE_2D
        let gl = self.gl.as_mut().unwrap();
        gl.gr.flush_and_submit();
        let rows = gl.exact.as_mut().unwrap().run(tex.id, (w, h), &codes, deep, out);
        gl.gr.reset(None);
        self.last_gpu_ms = t0.elapsed().as_secs_f64() * 1000.0;
        self.last_read_ms = self.last_gpu_ms;
        let rows = match rows {
            Ok(r) => r,
            Err(e) => return Some(Err(e)),
        };
        // Rows the table can't answer, in runs: read as stored and converted as `output` would.
        let t1 = std::time::Instant::now();
        let bpp = if deep { 8 } else { 4 };
        let mut y = 0;
        while y < h as usize {
            if !rows[y] {
                y += 1;
                continue;
            }
            let n = rows[y..].iter().take_while(|&&r| r).count();
            let src = info(w, n as u32, self.space.clone());
            let mut raw = vec![0u8; src.min_row_bytes() * n];
            if !self.last_surface().read_pixels(&src, &mut raw, src.min_row_bytes(), (0, y as i32)) {
                return Some(Err("frame readback (rows for the output step) failed".into()));
            }
            let at = y * w as usize * bpp;
            crate::color::output_rows(spec, &raw, w, y as u32, deep, false, &mut out[at..at + n * w as usize * bpp]);
            y += n;
        }
        self.last_convert_ms = t1.elapsed().as_secs_f64() * 1000.0;
        Some(Ok(()))
    }

    /// The last picture (a frame, the motion-blur sum or a held paint) as stored: premultiplied half floats, row by
    /// row, in the working space (color.rs `output` turns them into the output's pixels). Read as stored (a
    /// converting GPU readback hangs on this driver).
    pub fn read(&mut self) -> Vec<u8> {
        let (w, h) = (self.width, self.height);
        let src = info(w, h, self.space.clone());
        let row = src.min_row_bytes();
        let mut raw = vec![0u8; row * h as usize];
        let t0 = std::time::Instant::now();
        // The GPU finishing the frame, timed apart from the copy (`timing.gpuMs`): the read would wait for it all the same.
        if let Some(gl) = self.gl.as_mut() {
            gl.gr.flush_submit_and_sync_cpu();
        }
        self.last_gpu_ms = t0.elapsed().as_secs_f64() * 1000.0;
        let surface = self.last_surface();
        assert!(surface.read_pixels(&src, &mut raw, row, (0, 0)), "frame readback failed");
        self.last_read_ms = t0.elapsed().as_secs_f64() * 1000.0;
        raw
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The exact GPU output step (`output_into`) gives the CPU's bytes (`read` + `color::output`), bit for bit: random halves
    /// over the whole range (negative, tiny, above 1, not finite), opaque, transparent and partly transparent rows, an odd
    /// width, 8 and 16 bits, dither on and off, two working spaces.
    #[test]
    fn exact_gpu_output_step_gives_the_cpus_bytes() {
        let (w, h) = (97u32, 61u32);
        let mut seed = 0x2545_F491u32;
        let mut rnd = || {
            seed ^= seed << 13;
            seed ^= seed >> 17;
            seed ^= seed << 5;
            seed
        };
        let mut px = vec![0u8; (w * h * 8) as usize];
        for y in 0..h {
            for x in 0..w {
                let r = rnd();
                // Mostly display-range colours; every 7th any half at all.
                let mut c = [0u16; 4].map(|_| if r % 7 == 0 { rnd() as u16 } else { half::f16::from_f32((rnd() % 1200) as f32 / 1000.0 - 0.05).to_bits() });
                c[3] = match y % 10 {
                    3 if x % 5 == 0 => half::f16::from_f32((rnd() % 1000) as f32 / 1000.0).to_bits(),
                    7 => 0,
                    _ => half::f16::ONE.to_bits(),
                };
                for (k, v) in c.into_iter().enumerate() {
                    let o = ((y * w + x) * 8) as usize + k * 2;
                    px[o..o + 2].copy_from_slice(&v.to_le_bytes());
                }
            }
        }
        for color in [serde_json::json!({}), serde_json::json!({ "dither": false }), serde_json::json!({ "working": "linear-display" })] {
            let spec = crate::color::Spec::parse(&color).unwrap();
            let mut p = Painter::gpu(w, h, spec.surface_space()).expect("GPU");
            let info = ImageInfo::new((w as i32, h as i32), ColorType::RGBAF16, AlphaType::Premul, spec.surface_space());
            let img = skia_safe::images::raster_from_data(&info, skia_safe::Data::new_copy(&px), w as usize * 8).unwrap();
            let mut paint = Paint::default();
            paint.set_blend_mode(BlendMode::Src);
            p.surface.canvas().draw_image(&img, (0, 0), Some(&paint));
            let raw = p.read();
            for deep in [false, true] {
                let mut cpu = vec![];
                crate::color::output(&spec, &raw, w, deep, false, 0, &mut cpu);
                let mut gpu = vec![0u8; cpu.len()];
                assert!(crate::color::gpu_codes(&spec, deep).is_some(), "{color}: a channel table");
                if let Err(e) = &p.gl.as_ref().unwrap().exact {
                    panic!("{e}");
                }
                p.output_into(&spec, deep, &mut gpu).expect("the frame's texture").expect("the GPU output step");
                let off = gpu.iter().zip(&cpu).position(|(a, b)| a != b);
                assert!(off.is_none(), "{color} deep {deep}: first different byte {off:?} of {}", gpu.len());
            }
        }
    }

    /// The GPU output step (`read_output8`) gives what the CPU's playing frames give (color.rs `output` with `fast`, the same
    /// table): a ramp of colours across the range, painted in ACEScg under AgX, read both ways (no dither on either).
    #[test]
    fn gpu_output_step_matches_the_cpu_table() {
        let spec = crate::color::Spec::parse(&serde_json::json!({ "working": "acescg", "view": "agx", "dither": false })).unwrap();
        let lut = crate::color::output_lut(&spec).expect("AgX has a checked table");
        let (w, h) = (256u32, 64u32);
        let mut p = Painter::gpu(w, h, spec.surface_space()).expect("GPU");
        // Light from 0 to ~12 across, the hue turning down the rows; opaque.
        let mut px = vec![0u8; (w * h * 8) as usize];
        for y in 0..h {
            for x in 0..w {
                let v = (x as f32 / (w - 1) as f32).powi(3) * 12.0;
                let c = [v, v * (y as f32 / h as f32), v * (1.0 - y as f32 / h as f32) * 0.5, 1.0];
                for (k, c) in c.into_iter().enumerate() {
                    let o = ((y * w + x) * 8) as usize + k * 2;
                    px[o..o + 2].copy_from_slice(&half::f16::from_f32(c).to_le_bytes());
                }
            }
        }
        let info = ImageInfo::new((w as i32, h as i32), ColorType::RGBAF16, AlphaType::Premul, spec.surface_space());
        let img = skia_safe::images::raster_from_data(&info, skia_safe::Data::new_copy(&px), w as usize * 8).unwrap();
        let mut paint = Paint::default();
        paint.set_blend_mode(BlendMode::Src);
        p.surface.canvas().draw_image(&img, (0, 0), Some(&paint));
        let gpu = p.read_output8(&lut).expect("on the GPU").expect("read");
        let raw = p.read();
        let mut cpu = vec![];
        crate::color::output(&spec, &raw, w, false, true, 0, &mut cpu);
        let worst = gpu.iter().zip(&cpu).map(|(a, b)| (*a as i32 - *b as i32).abs()).max().unwrap();
        let off = gpu.iter().zip(&cpu).filter(|(a, b)| (**a as i32 - **b as i32).abs() > 1).count();
        assert!(worst <= 3 && off * 200 < gpu.len(), "GPU vs CPU output step: worst {worst} codes, {off} values over 1 code of {}", gpu.len());
    }
}
