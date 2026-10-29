//! Paints a laid-out page with Skia into one surface: on the GPU (OpenGL through WGL; WGL needs a window
//! for its context, so a hidden one is made) or on the CPU, when asked or when no GL context can be made
//! (`Painter::best`, the one place that chooses: a PC with no working graphics driver). Same drawing code either way;
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
use glutin::context::{ContextApi, ContextAttributesBuilder, NotCurrentGlContext, PossiblyCurrentContext, Version};
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
    /// GPU timestamps around a paint's flush, when profiling (profile.rs).
    timer: Option<crate::profile::Timer>,
    /// glGetError, for the one check after each paint (`gpu_failed`).
    get_error: extern "system" fn() -> u32,
    _context: (PossiblyCurrentContext, GlSurface<WindowSurface>),
}

/// The surface the last picture is in: a plain paint, the motion-blur sum, or a held paint over it.
#[derive(Clone, Copy, PartialEq)]
enum Last {
    Frame,
    Sum,
    Held,
}

/// The part of the page a picture shows (comp px from (x0, y0), w × h) and its scale: the picture is round(w·scale) ×
/// round(h·scale) px. The whole comp at scale 1 is every export's and still's.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct View {
    pub scale: f32,
    pub x0: f32,
    pub y0: f32,
    pub w: f32,
    pub h: f32,
}

impl View {
    pub fn full(width: u32, height: u32) -> View {
        View { scale: 1.0, x0: 0.0, y0: 0.0, w: width as f32, h: height as f32 }
    }
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
    /// The world picture's second set of surfaces (`swap_aside`): the frame's export picture is drawn there while the
    /// world picture's surfaces keep their size, so neither is made again each frame.
    aside: Option<Aside>,
    gl: Option<Gl>,
    /// The surfaces' size: the view's (`set_view`).
    width: u32,
    height: u32,
    /// The view every paint draws through (`set_view`): scale and the page px at the picture's top-left.
    view: (f32, f32, f32),
    /// The working colour space every surface is tagged with (None: display values, unmanaged).
    space: Option<ColorSpace>,
    /// The last frame's time recording the drawing and submitting it to the GPU, reading it back (waiting for
    /// the GPU to finish it) and converting the pixels (ms), for profiling.
    /// The frame index of each readback in flight (`start_read`), oldest first, and the output step it went through on
    /// the GPU (spec, deep), if it did.
    in_flight: std::collections::VecDeque<(u32, Option<(crate::color::Spec, bool)>)>,
    pub last_draw_ms: f64,
    pub last_flush_ms: f64,
    pub last_read_ms: f64,
    /// Of `last_read_ms`: the wait for the GPU to finish the frame (`read`; 0 when read in flight).
    pub last_gpu_ms: f64,
    pub last_convert_ms: f64,
    /// Whether the last frame collected by `finish_read` came through the GPU's output step (the encoder's bytes).
    pub last_read_ready: bool,
    /// The comp-cache buffers the last paint tapped (anyrender_skia `finish_taps`): how many, and the time reading them
    /// back (ms); `taps_written` the time it waited for them to be written.
    pub last_taps: usize,
    pub last_tap_read_ms: f64,
    pub last_tap_write_ms: f64,
    /// Device px a paint leaves alone (`paint`): the frame's quad in the world picture, which the export fills.
    pub clip_out: Option<skia_safe::Path>,
    /// An output started on the GPU and not finished (`output_start`): deep, screen.
    out_pending: Option<(bool, bool)>,
}

/// One set of picture surfaces and their size and view (`swap_aside`).
struct Aside {
    surface: Surface,
    acc: Option<Surface>,
    held: Option<Surface>,
    last: Last,
    out8: Option<Out8>,
    width: u32,
    height: u32,
    view: (f32, f32, f32),
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

fn hidden_window() -> Result<(isize, isize), String> {
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
        if hwnd.is_null() {
            return Err("CreateWindowExW failed (no window for the GL context)".into());
        }
        Ok((hwnd as isize, hinst as isize))
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

/// Skia's GPU resource budget for a comp of this size. A busy frame's layers, blur passes and pictures need about
/// 20 frame-sized half-float textures; under Skia's default 256 MB they were thrown away and made again every frame
/// (H25: Lull's 13-18 s at 1080p, 37 ms a frame of which 20 ms was that, 18 ms with room). 32 frames' worth, at least
/// 512 MB and at most 1.5 GB (the laptop's GPU has 4 GB, shared with the 3D app); what goes unused is freed (`paint`).
pub(crate) fn gpu_budget(width: u32, height: u32) -> usize {
    let frame = width as usize * height as usize * 8;
    (32 * frame).clamp(512 << 20, 1536 << 20)
}

/// GPU resources not used for this long are freed after a paint, so a budget filled by an earlier scene goes back.
const GPU_UNUSED: std::time::Duration = std::time::Duration::from_secs(5);

/// What the person is told when frames are painted on the CPU because the GPU could not be used (serve's `fallback`).
pub const NO_GPU: &str = "No graphics driver, so drawing is slower";   // short: the top bar's status line has ~45 letters of room

/// `ROSTRUM2D_NO_GPU=1` makes `gl_context` fail as on a PC with no working graphics driver (to prove the CPU fallback).
const NO_GPU_SWITCH: &str = "ROSTRUM2D_NO_GPU";

pub fn gl_context() -> Result<Gl, String> {
    if std::env::var_os(NO_GPU_SWITCH).is_some_and(|v| v == "1") {
        return Err(format!("{NO_GPU_SWITCH}=1: no GL context, as asked"));
    }
    let (hwnd, hinst) = hidden_window()?;
    let mut wh = Win32WindowHandle::new(NonZeroIsize::new(hwnd).unwrap());
    wh.hinstance = NonZeroIsize::new(hinst);
    let raw_window = RawWindowHandle::Win32(wh);
    let display = unsafe { Display::new(RawDisplayHandle::Windows(WindowsDisplayHandle::new()), DisplayApiPreference::Wgl(Some(raw_window))) }.map_err(|e| format!("WGL display: {e}"))?;
    let config = unsafe { display.find_configs(ConfigTemplateBuilder::new().build()) }.map_err(|e| format!("GL configs: {e}"))?.next().ok_or("no GL config")?;
    // OpenGL 4.1 or later where the driver has it: Skia keeps compiled programs (program_cache.rs) as the driver's own
    // binaries only from 4.1 (glProgramBinary); on 3.3 it can keep only their source, compiled again each run. The
    // driver's default context is 3.3; one that can't make 4.1 gets that.
    let v41 = ContextAttributesBuilder::new().with_context_api(ContextApi::OpenGl(Some(Version::new(4, 1)))).build(Some(raw_window));
    let ctx = unsafe { display.create_context(&config, &v41) }
        .or_else(|_| unsafe { display.create_context(&config, &ContextAttributesBuilder::new().build(Some(raw_window))) })
        .map_err(|e| format!("GL context: {e}"))?;
    let attrs = SurfaceAttributesBuilder::<WindowSurface>::new().build(raw_window, NonZeroU32::new(64).unwrap(), NonZeroU32::new(64).unwrap());
    let gl_surface = unsafe { display.create_window_surface(&config, &attrs) }.map_err(|e| format!("GL surface: {e}"))?;
    let ctx = ctx.make_current(&gl_surface).map_err(|e| format!("make current: {e}"))?;
    let interface = Interface::new_load_with(|name| crate::profile::wrap(name, display.get_proc_address(&CString::new(name).unwrap()))).ok_or("no GL interface")?;
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
    // No GL error check after each of Skia's GL calls (E6): on NVIDIA's driver every glGetError waits for the driver's
    // own thread to catch up, ~314 of them a paint took 69 % of its time (E5). One check at each frame's read
    // (`gpu_failed`) still fails the frame when a GL call failed or the card ran out of memory (AGENTS.md rule 6).
    opts.skip_gl_error_checks = skia_safe::gpu::ganesh::context_options::Enable::Yes;
    // Programs built in earlier runs are loaded instead of compiled again (program_cache.rs): a first turned, blurred or
    // blended frame no longer waits for the driver's compiler.
    crate::program_cache::attach(&mut opts, &renderer);
    let mut gr = direct_contexts::make_gl(interface, Some(&opts)).ok_or("Skia GL context failed")?;
    let readback = Readback::new(|name| display.get_proc_address(name));
    let exact = crate::gpu_output::GpuOutput::new(|name| display.get_proc_address(name));
    let timer = crate::profile::Timer::new(|name| display.get_proc_address(name));
    let get_error = display.get_proc_address(c"glGetError");
    if get_error.is_null() {
        return Err("no glGetError".into());
    }
    let get_error = unsafe { std::mem::transmute::<*const std::ffi::c_void, extern "system" fn() -> u32>(get_error) };
    gr.reset(None);
    Ok(Gl { gr, renderer, readback, exact, timer, get_error, _context: (ctx, gl_surface) })
}

/// What failed on the GPU since the last check, in plain words: a GL error (out of memory first of all) or a lost
/// context. Called once at each frame's read (and after a paint whose taps were read back), where the CPU has waited
/// for the card anyway, in place of Skia's check after every GL call: on NVIDIA every check waits for the card (E16).
fn gpu_failed(gl: &mut Gl) -> Result<(), String> {
    let mut errors = vec![];
    for _ in 0..8 {
        match (gl.get_error)() {
            0 => break,
            0x0505 => errors.push("the graphics card ran out of memory (GL_OUT_OF_MEMORY)".to_string()),
            e => errors.push(format!("a graphics call failed (GL error 0x{e:04X})")),
        }
    }
    if gl.gr.abandoned() || gl.gr.is_device_lost() {
        errors.push("the graphics driver was lost (device lost or reset)".into());
    }
    if gl.gr.oomed() && !errors.iter().any(|e| e.contains("memory")) {
        errors.push("the graphics card ran out of memory".into());
    }
    if errors.is_empty() { Ok(()) } else { Err(format!("drawing on the GPU failed: {}", errors.join("; "))) }
}

impl Painter {
    /// The painter a render uses: on the GPU when it can be (`gl`: a context made beforehand, or None to make one now),
    /// else on the CPU, with the reason (`Err` of the second value: the technical one, for the log). The same drawing
    /// and output code either way (preview ≡ export); only the speed differs. The one place a render picks its painter.
    pub fn best(gl: Option<Result<Gl, String>>, width: u32, height: u32, space: Option<ColorSpace>) -> Result<(Self, Result<(), String>), String> {
        let why = match gl.unwrap_or_else(gl_context).and_then(|gl| Self::gpu_on(gl, width, height, space.clone())) {
            Ok(p) => return Ok((p, Ok(()))),
            Err(why) => why,
        };
        Ok((Self::cpu(width, height, space)?, Err(why)))
    }

    /// A GPU painter for the tests that need the GPU; fails (never falls back) when it cannot be used (a render goes
    /// through `best`). `space`: the working colour space (color.rs `surface_space`).
    #[cfg(test)]
    pub fn gpu(width: u32, height: u32, space: Option<ColorSpace>) -> Result<Self, String> {
        Self::gpu_on(gl_context()?, width, height, space)
    }

    /// A GPU painter on a context made beforehand (gl_context).
    pub fn gpu_on(mut gl: Gl, width: u32, height: u32, space: Option<ColorSpace>) -> Result<Self, String> {
        gl.gr.set_resource_cache_limit(gpu_budget(width, height));
        let surface = new_surface(Some(&mut gl), width, height, &space)?;
        Ok(Self { gl: Some(gl), surface, acc: None, held: None, last: Last::Frame, width, height, view: (1.0, 0.0, 0.0), space, in_flight: Default::default(), cache: SkiaSceneCache::default(), out8: None, last_draw_ms: 0.0, last_flush_ms: 0.0, last_read_ms: 0.0, last_gpu_ms: 0.0, last_convert_ms: 0.0, last_read_ready: false, last_taps: 0, last_tap_read_ms: 0.0, last_tap_write_ms: 0.0, aside: None, clip_out: None, out_pending: None })
    }

    pub fn cpu(width: u32, height: u32, space: Option<ColorSpace>) -> Result<Self, String> {
        let surface = new_surface(None, width, height, &space)?;
        Ok(Self { gl: None, surface, acc: None, held: None, last: Last::Frame, width, height, view: (1.0, 0.0, 0.0), space, in_flight: Default::default(), cache: SkiaSceneCache::default(), out8: None, last_draw_ms: 0.0, last_flush_ms: 0.0, last_read_ms: 0.0, last_gpu_ms: 0.0, last_convert_ms: 0.0, last_read_ready: false, last_taps: 0, last_tap_read_ms: 0.0, last_tap_write_ms: 0.0, aside: None, clip_out: None, out_pending: None })
    }

    /// Paints from now on the page's part `v` (ENGINE_CONTRACT.md § 1 `scale`, `view`): the whole comp at 1, a smaller
    /// playing preview, or a crop drawn larger (the zoomed-in canvas). The surfaces are made again at
    /// round(w·scale) × round(h·scale) when that size changes, and every draw goes through the root view (anyrender_skia
    /// `set_root_view`), so the page is not laid out again. Refused with frames in flight to an encoder (their surfaces would go).
    pub fn set_view(&mut self, v: View) -> Result<(), String> {
        let size = (((v.w * v.scale).round() as u32).max(1), ((v.h * v.scale).round() as u32).max(1));
        if size == (self.width, self.height) {
            self.view = (v.scale, v.x0, v.y0);
            return Ok(());
        }
        if !self.in_flight.is_empty() {
            return Err("a frame at another scale while frames are in flight to the encoder".into());
        }
        self.surface = new_surface(self.gl.as_mut(), size.0, size.1, &self.space)?;
        ((self.width, self.height), self.view) = (size, (v.scale, v.x0, v.y0));
        (self.acc, self.held, self.out8) = (None, None, None);
        self.last = Last::Frame;
        Ok(())
    }

    /// Ends this painter and gives back its GL context (None on the CPU), for the next painter: one process keeps one
    /// context. A second context made beside this one left the old one's resources freed while the new one was current
    /// (a larger comp loaded into a running engine failed its next frame with GL error 0x0501). Frames still in flight
    /// are collected and dropped first, so the next painter starts with no stale reads; the surfaces and cached images
    /// go while the context is still alive and current.
    pub fn into_gl(mut self) -> Option<Gl> {
        while self.reads_in_flight() > 0 {
            let _ = self.finish_read();
        }
        let mut gl = self.gl.take();
        drop(self);
        if let Some(g) = gl.as_mut() {
            while (g.get_error)() != 0 {} // the old painter's errors are not the next one's
        }
        gl
    }

    /// Skia's GPU resource budget, in bytes (an export's drawing workers share the card: export_crew.rs). Only what
    /// is kept between draws depends on it, never the pixels.
    pub fn set_budget(&mut self, bytes: usize) {
        if let Some(gl) = self.gl.as_mut() {
            gl.gr.set_resource_cache_limit(bytes);
        }
    }

    /// Frees the GPU memory kept between draws (textures, layers); its context and built programs stay: an export's
    /// idle drawing worker (export_pool.rs). The pixels never depend on it.
    pub fn release(&mut self) {
        if let Some(gl) = self.gl.as_mut() {
            gl.gr.purge_unlocked_resources(skia_safe::gpu::PurgeResourceOptions::AllResources);
        }
    }

    /// The size of the pictures it paints (`set_view`'s).
    pub fn size(&self) -> (u32, u32) {
        (self.width, self.height)
    }

    /// The GPU resource cache: (resources kept, their MB, the budget MB, MB of them unused now); `timing.gpuCache`.
    pub fn gpu_cache(&self) -> Option<(usize, f64, f64, f64)> {
        let gl = self.gl.as_ref()?;
        let u = gl.gr.resource_cache_usage();
        Some((u.resource_count, u.resource_bytes as f64 / 1048576.0, gl.gr.resource_cache_limit() as f64 / 1048576.0, gl.gr.resource_cache_purgeable_bytes() as f64 / 1048576.0))
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
        crate::profile::reset();
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
            // Every paint starts from the surface's own px and leaves the canvas as it found it: the scene painter's
            // root view must not stay on the canvas (a world picture at home left its zoom there, so the next one
            // clipped and laid the frame's export through it: a shrunk export and a stray copy round it).
            let depth = canvas.save();
            canvas.reset_matrix();
            if let Some(q) = self.clip_out.as_ref() {
                // Hard-edged, as draw_over's: the two sides of the frame's edge then share each pixel exactly (two
                // soft edges each half-cover an edge pixel, so the well showed through as a light seam).
                canvas.clip_path(q, skia_safe::ClipOp::Difference, false);
            }
            // Half-float images were decoded into the working space: anyrender_skia tags them with it.
            anyrender_skia::working_space::set(self.space.clone());
            self.cache.set_root_view(self.view.0, self.view.1, self.view.2);
            draw(&mut SkiaScenePainter::new(canvas, &mut self.cache));
            self.cache.set_root_view(1.0, 0.0, 0.0);
            canvas.restore_to_count(depth);
        }
        self.cache.held = None;
        self.cache.next_gen();
        let t1 = std::time::Instant::now();
        if let Some(gl) = self.gl.as_mut() {
            if let Some(t) = &gl.timer {
                t.mark(0);
            }
            gl.gr.flush_and_submit();
            let t_cleanup = std::time::Instant::now();
            gl.gr.perform_deferred_cleanup(GPU_UNUSED, None);
            // No GPU error check here (E16): on NVIDIA's driver it waits for the card to catch up (120 ms of a 0:15
            // paint), so the processor could not lay out the next sample while the card drew this one. GL errors
            // stay set until asked, so the check at the frame's read (`gpu_failed`) still fails the frame.
            crate::profile::parts([(t_cleanup - t1), t_cleanup.elapsed(), Default::default()].map(|d| d.as_secs_f64() * 1000.0));
        }
        self.last_draw_ms = (t1 - t0).as_secs_f64() * 1000.0;
        self.last_flush_ms = t1.elapsed().as_secs_f64() * 1000.0;
        // Profiling (profile.rs): waits for the GPU and writes where this paint's time went.
        if let Some(gl) = self.gl.as_mut().filter(|g| g.timer.is_some()) {
            let t = gl.timer.as_ref().unwrap();
            t.mark(1);
            let w = std::time::Instant::now();
            gl.gr.flush_submit_and_sync_cpu();
            let wait = w.elapsed().as_secs_f64() * 1000.0;
            crate::profile::row(self.last_draw_ms, self.last_flush_ms, wait, t.ms());
        }
        // The buffers the paint tapped for the comp's node cache, read back now that it is all submitted.
        (self.last_taps, self.last_tap_read_ms) = self.cache.finish_taps();
        // Those buffers are written to the comp cache before the frame is read: checked first (the card has finished).
        if let Some(gl) = self.gl.as_mut().filter(|_| self.last_taps > 0) {
            gpu_failed(gl)?;
        }
        // A shader that did not compile or link fails the frame (AGENTS.md rule 6), naming the effect and Skia's message.
        let shader_errors = anyrender::filters::shader_errors::take();
        if shader_errors.is_empty() { Ok(()) } else { Err(shader_errors.join("; ")) }
    }

    /// Keeps the last painted picture (a still run of a motion-blurred frame, still_runs.rs) as kept picture
    /// `cached().len()`, which a paint plan's `Run::Cached` then draws in its place.
    pub fn keep_cached(&mut self) {
        let image = self.surface.image_snapshot();
        self.cache.cached.push(image);
    }

    /// Keeps `image` (the picture of a motion-blurred frame's layers drawn so far, blurred.rs) as kept picture `cached().len()`.
    pub fn push_cached(&mut self, image: skia_safe::Image) {
        self.cache.cached.push(image);
    }

    /// Lets the kept pictures go (the frame is done).
    pub fn clear_cached(&mut self) {
        self.cache.cached.clear();
    }

    /// How many pictures are kept.
    pub fn cached_len(&self) -> usize {
        self.cache.cached.len()
    }

    /// The view every paint draws through: (scale, page px at the picture's left, top).
    pub fn view(&self) -> (f32, f32, f32) {
        self.view
    }

    /// Trades the picture surfaces (and their size, view and last picture) for the second set, made on first use at
    /// the current size; a second call trades them back. The world picture draws the frame's export in the second set.
    pub fn swap_aside(&mut self) -> Result<(), String> {
        if !self.in_flight.is_empty() {
            return Err("a world picture while frames are in flight to the encoder".into());
        }
        let mut a = match self.aside.take() {
            Some(a) => a,
            None => Aside { surface: new_surface(self.gl.as_mut(), self.width, self.height, &self.space)?, acc: None, held: None, last: Last::Frame, out8: None, width: self.width, height: self.height, view: self.view },
        };
        std::mem::swap(&mut self.surface, &mut a.surface);
        std::mem::swap(&mut self.acc, &mut a.acc);
        std::mem::swap(&mut self.held, &mut a.held);
        std::mem::swap(&mut self.last, &mut a.last);
        std::mem::swap(&mut self.out8, &mut a.out8);
        std::mem::swap(&mut self.width, &mut a.width);
        std::mem::swap(&mut self.height, &mut a.height);
        std::mem::swap(&mut self.view, &mut a.view);
        self.aside = Some(a);
        Ok(())
    }

    /// The last picture (a frame, the motion-blur sum or a held paint), kept as an image.
    pub fn last_image(&mut self) -> skia_safe::Image {
        self.last_surface().image_snapshot()
    }

    /// Draws `image` over the last picture inside the device px polygon `clip`, through `m` (image px → device px):
    /// the frame's export laid into its quad in the world picture.
    pub fn draw_over(&mut self, image: &skia_safe::Image, m: &skia_safe::Matrix, clip: &skia_safe::Path) {
        lay_in(self.last_surface().canvas(), image, m, clip);
    }

    /// Waits until the GPU has drawn everything submitted (timing one layer's paint, scene_export.rs).
    pub fn sync(&mut self) {
        if let Some(gl) = self.gl.as_mut() {
            gl.gr.flush_submit_and_sync_cpu();
        }
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
        add_weighted(canvas, &frame, weight);
        self.last = Last::Sum;
        Ok(())
    }

    /// Builds ahead the GPU programs the next frames will need (warmup.rs): `draw` paints the page through `base` (a turned
    /// or tilted view) into a scratch surface `w` × `h` with a cache of its own (nothing the frames keep is touched, no
    /// tap is written), then that picture is summed as a motion-blur sub-frame is and laid into a turned quad as the world
    /// picture lays the export in. Nothing on the CPU.
    pub fn warm(&mut self, base: skia_safe::M44, (w, h): (u32, u32), draw: impl FnOnce(&mut SkiaScenePainter<'_>)) -> Result<(), String> {
        let Some(gl) = self.gl.as_mut() else { return Ok(()) };
        let mut page = new_surface(Some(gl), w, h, &self.space)?;
        let mut sum = new_surface(Some(gl), w, h, &self.space)?;
        let mut cache = SkiaSceneCache::default();
        anyrender_skia::working_space::set(self.space.clone());
        cache.set_root_matrix(base);
        page.canvas().clear(Color::TRANSPARENT);
        draw(&mut SkiaScenePainter::new(page.canvas(), &mut cache));
        let image = page.image_snapshot();
        sum.canvas().clear(Color::TRANSPARENT);
        add_weighted(sum.canvas(), &image, 0.5);
        let (cx, cy) = (w as f32 / 2.0, h as f32 / 2.0);
        let m = skia_safe::Matrix::rotate_deg_pivot(23.0, (cx, cy));
        let quad: Vec<skia_safe::Point> = [(0.0, 0.0), (w as f32, 0.0), (w as f32, h as f32), (0.0, h as f32)].into_iter().map(|p| m.map_point(p)).collect();
        let quad = skia_safe::Path::polygon(&quad, true, None, None);
        lay_in(sum.canvas(), &image, &m, &quad);
        drop((image, page, sum, cache));
        self.gl.as_mut().unwrap().gr.flush_and_submit();
        Ok(())
    }
}

/// Adds `frame` to a motion-blur sum on `canvas` with `weight` (`accumulate`).
fn add_weighted(canvas: &skia_safe::Canvas, frame: &skia_safe::Image, weight: f32) {
    let mut paint = Paint::default();
    paint.set_blend_mode(BlendMode::Plus);
    // The weight scales alpha in a float colour matrix (unpremultiplied, so premultiplied colours scale with
    // it): a paint alpha is quantized to 8 bits on the GPU (1/14 → 18/255), and the sum came to 0.988.
    #[rustfmt::skip]
    let m = skia_safe::ColorMatrix::new(1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, weight, 0.0);
    paint.set_color_filter(skia_safe::color_filters::matrix(&m, None));
    canvas.draw_image(frame, (0, 0), Some(&paint));
}

/// Draws `image` on `canvas` inside the device px polygon `clip`, through `m` (image px → device px) (`draw_over`).
fn lay_in(canvas: &skia_safe::Canvas, image: &skia_safe::Image, m: &skia_safe::Matrix, clip: &skia_safe::Path) {
    canvas.save();
    canvas.reset_matrix();
    canvas.clip_path(clip, skia_safe::ClipOp::Intersect, false);     // hard-edged: see paint's clip_out
    canvas.concat(m);
    let sampling = skia_safe::SamplingOptions::new(skia_safe::FilterMode::Linear, skia_safe::MipmapMode::None);
    canvas.draw_image_with_sampling_options(image, (0, 0), sampling, None);
    canvas.restore();
}

impl Painter {

    /// The surface holding the last picture.
    fn last_surface(&mut self) -> &mut Surface {
        match self.last {
            Last::Frame => &mut self.surface,
            Last::Sum => self.acc.as_mut().unwrap(),
            Last::Held => self.held.as_mut().unwrap(),
        }
    }

    /// Starts reading the last picture (a frame, the motion-blur sum or a held paint) back for an encoder without
    /// waiting for it; `finish_read` collects it. On the GPU's exact output step when it can (gpu_output_queue.rs: the
    /// encoder's bytes, `spec` and `deep`, read back ready), else as stored (readback.rs). False on the CPU or without
    /// pixel buffers: use `read`.
    pub fn start_read(&mut self, index: u32, spec: &crate::color::Spec, deep: bool) -> Result<bool, String> {
        let (w, h) = (self.width, self.height);
        if let Some(codes) = crate::color::gpu_codes(spec, deep).filter(|_| self.gl.as_ref().is_some_and(|g| g.exact.is_ok())) {
            let tex = gpu::surfaces::get_backend_texture(self.last_surface(), skia_safe::surface::BackendHandleAccess::FlushRead)
                .and_then(|t| t.gl_texture_info())
                .filter(|i| i.target == 0x0DE1); // TEXTURE_2D
            if let Some(tex) = tex {
                let gl = self.gl.as_mut().unwrap();
                gl.gr.flush_and_submit();
                let started = gl.exact.as_mut().unwrap().queue_start(tex.id, (w, h), &codes, deep);
                gl.gr.reset(None);
                started?;
                self.in_flight.push_back((index, Some((*spec, deep))));
                return Ok(true);
            }
        }
        if self.gl.as_ref().map_or(true, |g| g.readback.is_none()) {
            return Ok(false);
        }
        let surface = self.last_surface();
        let Some(fbo) = gpu::surfaces::get_backend_render_target(surface, skia_safe::surface::BackendHandleAccess::FlushRead).and_then(|t| t.gl_framebuffer_info()).map(|i| i.fboid) else { return Ok(false) };
        let gl = self.gl.as_mut().unwrap();
        gl.gr.flush_and_submit();
        gl.readback.as_mut().unwrap().start(fbo, w, h, true);
        // The readback bound GL state behind Skia's back.
        gl.gr.reset(None);
        self.in_flight.push_back((index, None));
        Ok(true)
    }

    /// Frames started by `start_read` and not collected yet.
    pub fn reads_in_flight(&self) -> usize {
        self.in_flight.len()
    }

    /// The oldest started frame: its bytes, the frame index it was started with, and whether they are the encoder's
    /// already (the GPU's output step) or as stored (premultiplied half floats, for `color::output`).
    pub fn finish_read(&mut self) -> Result<(Vec<u8>, u32, bool), String> {
        let t0 = std::time::Instant::now();
        let (index, out) = self.in_flight.pop_front().ok_or("no readback in flight")?;
        let gl = self.gl.as_mut().ok_or("no readback in flight")?;
        let Some((spec, deep)) = out else {
            let r = gl.readback.as_mut().ok_or("no readback in flight")?.finish_oldest();
            self.last_read_ms = t0.elapsed().as_secs_f64() * 1000.0;
            gpu_failed(self.gl.as_mut().unwrap())?;
            self.last_read_ready = false;
            return r.map(|(raw, _)| (raw, index, false));
        };
        let (w, bpp) = (self.width as usize, if deep { 8 } else { 4 });
        let mut bytes = vec![0u8; w * self.height as usize * bpp];
        let done = gl.exact.as_mut().map_err(|e| e.clone())?.queue_finish(&mut bytes);
        gl.gr.reset(None);
        self.last_read_ms = t0.elapsed().as_secs_f64() * 1000.0;
        gpu_failed(gl)?;
        // The pixels the table can't answer (a see-through edge), from the frame's halves there, as `output` would.
        let t1 = std::time::Instant::now();
        for ([x0, y0, x1, _], raw) in &done?.cpu {
            let rw = (x1 - x0) as usize;
            let mut px = vec![0u8; raw.len() / 8 * bpp];
            crate::color::output_rect(&spec, raw, rw as u32, (*x0, *y0), deep, false, &mut px);
            for (k, row) in px.chunks_exact(rw * bpp).enumerate() {
                let at = ((*y0 as usize + k) * w + *x0 as usize) * bpp;
                bytes[at..at + row.len()].copy_from_slice(row);
            }
        }
        self.last_convert_ms = t1.elapsed().as_secs_f64() * 1000.0;
        self.last_read_ready = true;
        Ok((bytes, index, true))
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
        if let Err(e) = gpu_failed(self.gl.as_mut().unwrap()) {
            return Some(Err(e));
        }
        Some(if ok { Ok(out) } else { Err("frame readback (8-bit output) failed".into()) })
    }

    /// The last picture through the output step on the GPU, exact (gpu_output.rs): into `out` (the frame's size), the same
    /// bytes `color::output_into` gives from `read` (with `screen`, as `pixels::to_screen` turns them), at a fraction of the
    /// time. None where it can't run (on the CPU, or an output step without a channel table): use `read` and
    /// `color::output_into`.
    pub fn output_into(&mut self, spec: &crate::color::Spec, deep: bool, screen: bool, out: &mut [u8]) -> Option<Result<(), String>> {
        match self.output_start(spec, deep, screen, None)? {
            Ok(()) => Some(self.output_finish(spec, out).map(|_| ())),
            Err(e) => Some(Err(e)),
        }
    }

    /// `output_into` in two halves: the GPU's passes queued now, nothing waited for (`output_finish` reads them; the
    /// picture must not be painted over in between). `holds`: the canvas memory's slot the bytes go into (only what
    /// changed from what it holds is read back: gpu_output.rs).
    pub fn output_start(&mut self, spec: &crate::color::Spec, deep: bool, screen: bool, holds: Option<crate::gpu_output::Holds>) -> Option<Result<(), String>> {
        let codes = crate::color::gpu_codes(spec, deep)?;
        self.gl.as_ref()?.exact.as_ref().ok()?;
        let (w, h) = (self.width, self.height);
        let t0 = std::time::Instant::now();
        let tex = gpu::surfaces::get_backend_texture(self.last_surface(), skia_safe::surface::BackendHandleAccess::FlushRead)
            .and_then(|t| t.gl_texture_info())
            .filter(|i| i.target == 0x0DE1)?; // TEXTURE_2D
        let gl = self.gl.as_mut().unwrap();
        gl.gr.flush_and_submit();
        let started = gl.exact.as_mut().unwrap().start(tex.id, (w, h), &codes, deep, screen, holds);
        gl.gr.reset(None);
        self.out_pending = Some((deep, screen));
        self.last_flush_ms += t0.elapsed().as_secs_f64() * 1000.0;
        Some(started)
    }

    /// The output started by `output_start`, into `out`: waits for the GPU (`last_gpu_ms`), reads back the rows that
    /// changed (their count returned) and redoes on the CPU the pixels the GPU can't answer exactly (`last_convert_ms`).
    pub fn output_finish(&mut self, spec: &crate::color::Spec, out: &mut [u8]) -> Result<u32, String> {
        let (deep, screen) = self.out_pending.take().ok_or("output_finish without output_start")?;
        let w = self.width;
        let t0 = std::time::Instant::now();
        let gl = self.gl.as_mut().ok_or("no GPU")?;
        let done = gl.exact.as_mut().map_err(|e| e.clone())?.finish(out).and_then(|r| gpu_failed(gl).map(|_| r));
        gl.gr.reset(None);
        self.last_gpu_ms = t0.elapsed().as_secs_f64() * 1000.0;
        self.last_read_ms = self.last_gpu_ms;
        let done = done?;
        // The blocks the table can't answer, in rectangles (read as stored with the marks): converted as `output` would.
        let t1 = std::time::Instant::now();
        let bpp = if deep { 8 } else { 4 };
        for ([x0, y0, x1, _], raw) in &done.cpu {
            let rw = x1 - x0;
            let mut px = vec![0u8; raw.len() / 8 * bpp];
            crate::color::output_rect(spec, raw, rw, (*x0, *y0), deep, false, &mut px);
            if screen {
                crate::pixels::to_screen(&mut px);
            }
            for (k, row) in px.chunks_exact(rw as usize * bpp).enumerate() {
                let at = ((*y0 as usize + k) * w as usize + *x0 as usize) * bpp;
                out[at..at + row.len()].copy_from_slice(row);
            }
        }
        self.last_convert_ms = t1.elapsed().as_secs_f64() * 1000.0;
        Ok(done.rows_read)
    }

    /// Drops an output started and not finished.
    pub fn output_cancel(&mut self) {
        self.out_pending = None;
        if let Some(Ok(x)) = self.gl.as_mut().map(|g| &mut g.exact) {
            x.cancel();
        }
    }

    /// The canvas memory's slot `slot` was written without the GPU output step: what it holds is no longer known there.
    pub fn output_forget(&mut self, slot: usize) {
        if let Some(Ok(x)) = self.gl.as_mut().map(|g| &mut g.exact) {
            x.forget(slot);
        }
    }

    /// The last picture (a frame, the motion-blur sum or a held paint) as stored: premultiplied half floats, row by
    /// row, in the working space (color.rs `output` turns them into the output's pixels). Read as stored (a
    /// converting GPU readback hangs on this driver). A GL call that failed while drawing it is the `Err` (`gpu_failed`).
    pub fn read(&mut self) -> Result<Vec<u8>, String> {
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
        if let Some(gl) = self.gl.as_mut() {
            gpu_failed(gl)?;
        }
        Ok(raw)
    }
}

#[cfg(test)]
#[path = "handoff_tests.rs"]
mod handoff_tests;

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
            let raw = p.read().unwrap();
            for deep in [false, true] {
                let mut cpu = vec![];
                crate::color::output(&spec, &raw, w, deep, false, 0, &mut cpu);
                let mut gpu = vec![0u8; cpu.len()];
                assert!(crate::color::gpu_codes(&spec, deep).is_some(), "{color}: a channel table");
                if let Err(e) = &p.gl.as_ref().unwrap().exact {
                    panic!("{e}");
                }
                p.output_into(&spec, deep, false, &mut gpu).expect("the frame's texture").expect("the GPU output step");
                let off = gpu.iter().zip(&cpu).position(|(a, b)| a != b);
                assert!(off.is_none(), "{color} deep {deep}: first different byte {off:?} of {}", gpu.len());
            }
        }
    }

    /// With Skia's own GL checks off, a GL call that fails during a frame still fails that frame, at its read, in plain
    /// words (`gpu_failed`); the next frame is clean again. The failure is forced with an invalid `glEnable` while drawing.
    #[test]
    fn a_failed_gl_call_fails_the_frame() {
        #[link(name = "opengl32")]
        unsafe extern "system" {
            fn glEnable(cap: u32);
        }
        let mut p = Painter::gpu(32, 32, None).expect("GPU");
        p.paint(false, |_| {}).expect("a clean paint");
        p.read().expect("a clean frame");
        p.paint(false, |_| unsafe { glEnable(0xFFFF) }).expect("the paint itself does not wait to check");
        let e = p.read().expect_err("a failed GL call");
        assert!(e.starts_with("drawing on the GPU failed: a graphics call failed (GL error 0x0500)"), "{e}");
        p.paint(false, |_| {}).expect("clean again");
        p.read().expect("clean again");
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
        let raw = p.read().unwrap();
        let mut cpu = vec![];
        crate::color::output(&spec, &raw, w, false, true, 0, &mut cpu);
        let worst = gpu.iter().zip(&cpu).map(|(a, b)| (*a as i32 - *b as i32).abs()).max().unwrap();
        let off = gpu.iter().zip(&cpu).filter(|(a, b)| (**a as i32 - **b as i32).abs() > 1).count();
        assert!(worst <= 3 && off * 200 < gpu.len(), "GPU vs CPU output step: worst {worst} codes, {off} values over 1 code of {}", gpu.len());
    }
}
