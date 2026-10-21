//! The output step on the GPU, exact (painter.rs `output_into`): a frame's half floats become the same bytes as
//! color.rs `output` gives, bit for bit, so a still, a scrubbed frame, the canvas's pixels and the export agree.
//!
//! No float maths is left on the GPU: each channel's half bits index a table of integer codes made on the CPU from the
//! output step itself (color.rs `gpu_codes`), and the dither is the same integer hash. That covers every opaque pixel
//! with finite channels (and transparent ones), which is every pixel of a frame with a background. A pixel the table
//! can't answer exactly (partly transparent: its colour is divided by its alpha; or a channel not finite) is marked,
//! and a second pass reports which rows hold one, in blocks of `BLOCK` pixels; the painter redoes those rows on the CPU.
//! Raw OpenGL 3.3 (Skia's runtime shaders have no integers); Skia's GL state is reset afterwards.

use std::ffi::{c_void, CString};

/// Pixels per flag (the second pass's fragment checks this many along a row).
pub const BLOCK: u32 = 32;

const VS: &str = "#version 330 core
void main() { vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2)); gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0); }";

const FS: &str = "
uniform sampler2D src;
uniform usampler2D codes;
uniform uint deep;
uniform int width;
// The half a value read from the F16 frame came from (exact: every half is an f32). Not finite: kept not finite.
uint bits(float v) {
    uint u = floatBitsToUint(v), s = (u >> 16u) & 0x8000u, e = (u >> 23u) & 0xFFu, m = u & 0x7FFFFFu;
    if (e == 255u) return s | 0x7C00u | (m != 0u ? 0x200u : 0u);
    if (e > 112u) return s | ((e - 112u) << 10u) | (m >> 13u);
    if (e < 103u) return s;
    return s | ((m | 0x800000u) >> (126u - e));
}
bool finite(uint h) { return (h & 0x7C00u) != 0x7C00u; }
// 0: transparent, 1: opaque with finite channels (the table answers), 2: the CPU's.
uint kind(uvec4 h) {
    if (!finite(h.a) || (h.a & 0x8000u) != 0u || h.a == 0u) return 0u;
    return h.a >= 0x3C00u && finite(h.r) && finite(h.g) && finite(h.b) ? 1u : 2u;
}
uvec4 halves(ivec2 p) { vec4 c = texelFetch(src, p, 0); return uvec4(bits(c.r), bits(c.g), bits(c.b), bits(c.a)); }
uint dither(uint x, uint y, uint c) {
    uint h = (x * 0x9E3779B1u) ^ (y * 0x85EBCA77u) ^ (c * 0xC2B2AE3Du);
    h ^= h >> 15u; h *= 0x2C1B3C6Du; h ^= h >> 12u; h *= 0x297A2D39u; h ^= h >> 15u;
    return h >> 8u;
}
uint code(uint h, uvec2 p, uint k) {
    uint e = texelFetch(codes, ivec2(int(h & 255u), int(h >> 8u)), 0).r;
    if (deep != 0u) return e;
    uint t = e >> 8u;
    return (e & 255u) + (t != 0u && dither(p.x, p.y, k) >= t ? 1u : 0u);
}
#ifdef FLAGS
layout(location = 0) out uint o;
void main() {
    int y = int(gl_FragCoord.y), x0 = int(gl_FragCoord.x) * BLOCK;
    o = 0u;
    for (int x = x0; x < min(x0 + BLOCK, width); x++) if (kind(halves(ivec2(x, y))) == 2u) { o = 1u; return; }
}
#else
layout(location = 0) out uvec4 o;
void main() {
    uvec2 p = uvec2(gl_FragCoord.xy);
    uvec4 h = halves(ivec2(p));
    if (kind(h) != 1u) { o = uvec4(0u); return; }
    o = uvec4(code(h.r, p, 0u), code(h.g, p, 1u), code(h.b, p, 2u), deep != 0u ? 65535u : 255u);
}
#endif
";

const TEXTURE_2D: u32 = 0x0DE1;
const FRAMEBUFFER: u32 = 0x8D40;
const COLOR_ATTACHMENT0: u32 = 0x8CE0;
const RGBA_INTEGER: u32 = 0x8D99;
const RED_INTEGER: u32 = 0x8D94;

macro_rules! gl_fns {
    ($($name:ident: fn($($a:ty),*) $(-> $r:ty)?;)*) => {
        #[allow(non_snake_case)]
        struct Fns { $($name: extern "system" fn($($a),*) $(-> $r)?,)* }
        impl Fns {
            fn load(load: &dyn Fn(&CString) -> *const c_void) -> Option<Fns> {
                Some(Fns { $($name: unsafe { std::mem::transmute::<*const c_void, extern "system" fn($($a),*) $(-> $r)?>({
                    let p = load(&CString::new(concat!("gl", stringify!($name))).unwrap());
                    if p.is_null() { return None } p }) },)* })
            }
        }
    };
}

gl_fns! {
    CreateShader: fn(u32) -> u32; ShaderSource: fn(u32, i32, *const *const u8, *const i32); CompileShader: fn(u32);
    GetShaderiv: fn(u32, u32, *mut i32); GetShaderInfoLog: fn(u32, i32, *mut i32, *mut u8); CreateProgram: fn() -> u32;
    AttachShader: fn(u32, u32); LinkProgram: fn(u32); GetProgramiv: fn(u32, u32, *mut i32);
    GetProgramInfoLog: fn(u32, i32, *mut i32, *mut u8); UseProgram: fn(u32); GetUniformLocation: fn(u32, *const u8) -> i32;
    Uniform1i: fn(i32, i32); Uniform1ui: fn(i32, u32); GenTextures: fn(i32, *mut u32); BindTexture: fn(u32, u32);
    TexImage2D: fn(u32, i32, i32, i32, i32, i32, u32, u32, *const c_void); TexParameteri: fn(u32, u32, i32);
    ActiveTexture: fn(u32); BindSampler: fn(u32, u32); GenFramebuffers: fn(i32, *mut u32); BindFramebuffer: fn(u32, u32);
    FramebufferTexture2D: fn(u32, u32, u32, u32, i32); CheckFramebufferStatus: fn(u32) -> u32; GenVertexArrays: fn(i32, *mut u32);
    BindVertexArray: fn(u32); BindBuffer: fn(u32, u32); Viewport: fn(i32, i32, i32, i32); Disable: fn(u32);
    ColorMask: fn(u8, u8, u8, u8); DrawArrays: fn(u32, i32, i32); PixelStorei: fn(u32, i32);
    ReadPixels: fn(i32, i32, i32, i32, u32, u32, *mut c_void); GetError: fn() -> u32;
}

/// One output target: its texture and framebuffer, at a size and format.
struct Target {
    tex: u32,
    fbo: u32,
    size: (u32, u32, u32),
}

pub struct GpuOutput {
    f: Fns,
    programs: [u32; 2],
    vao: u32,
    codes: u32,
    /// Which table is in `codes` (its address).
    codes_key: usize,
    out: Option<Target>,
    flags: Option<Target>,
}

impl GpuOutput {
    /// Loads GL 3.3 and builds both programs; an Err names what failed.
    pub fn new(load: impl Fn(&CString) -> *const c_void) -> Result<GpuOutput, String> {
        let f = Fns::load(&load).ok_or("the GPU output step needs OpenGL 3.3")?;
        let programs = [program(&f, "")?, program(&f, &format!("#define FLAGS\n#define BLOCK {BLOCK}\n"))?];
        let (mut vao, mut codes) = (0, 0);
        (f.GenVertexArrays)(1, &mut vao);
        (f.GenTextures)(1, &mut codes);
        Ok(GpuOutput { f, programs, vao, codes, codes_key: 0, out: None, flags: None })
    }

    /// Converts texture `src` (the frame, RGBA16F, w × h, top row first) with `codes` (color.rs `gpu_codes`) into `out`
    /// (RGBA8, or RGBA16 little-endian when `deep`), and returns per row whether it holds a pixel the CPU must redo.
    /// The caller has flushed Skia's work and resets Skia's GL state afterwards.
    pub fn run(&mut self, src: u32, (w, h): (u32, u32), codes: &std::sync::Arc<[u32]>, deep: bool, out: &mut [u8]) -> Result<Vec<bool>, String> {
        let f = &self.f;
        while (f.GetError)() != 0 {} // an earlier error is not ours
        assert_eq!(out.len(), (w * h) as usize * if deep { 8 } else { 4 }, "output buffer size");
        (f.BindBuffer)(0x88EB, 0); // PIXEL_PACK_BUFFER
        (f.BindBuffer)(0x88EC, 0); // PIXEL_UNPACK_BUFFER
        for p in [0x0CF2, 0x0D02, 0x0CF3, 0x0CF4, 0x0D03, 0x0D04] {
            (f.PixelStorei)(p, 0); // (UN)PACK_ROW_LENGTH, SKIP_ROWS, SKIP_PIXELS
        }
        (f.PixelStorei)(0x0CF5, 4); // UNPACK_ALIGNMENT
        (f.PixelStorei)(0x0D05, 1); // PACK_ALIGNMENT
        // The targets first: making one binds its texture.
        let fw = w.div_ceil(BLOCK);
        let (fmt, ty) = if deep { (0x8D76, 0x1403) } else { (0x8D7C, 0x1401) }; // RGBA16UI / RGBA8UI
        (f.ActiveTexture)(0x84C2);
        let outs = [target(f, &mut self.out, (w, h, fmt))?, target(f, &mut self.flags, (fw, h, 0x8232))?]; // R8UI
        (f.ActiveTexture)(0x84C1);
        (f.BindSampler)(1, 0);
        (f.BindTexture)(TEXTURE_2D, self.codes);
        let key = codes.as_ptr() as usize;
        if self.codes_key != key {
            nearest(f);
            (f.TexImage2D)(TEXTURE_2D, 0, 0x8236 as i32, 256, 256, 0, RED_INTEGER, 0x1405, codes.as_ptr() as *const c_void); // R32UI
            self.codes_key = key;
        }
        (f.ActiveTexture)(0x84C0);
        (f.BindSampler)(0, 0);
        (f.BindTexture)(TEXTURE_2D, src);
        nearest(f); // complete without mipmaps (Skia's own state is reset after)
        for cap in [0x0C11, 0x0BE2, 0x0B71, 0x0B90, 0x0B44, 0x809D, 0x8DB9] {
            (f.Disable)(cap); // scissor, blend, depth, stencil, cull, multisample, sRGB writes
        }
        (f.ColorMask)(1, 1, 1, 1);
        (f.BindVertexArray)(self.vao);
        for (k, &(fbo, tw, th)) in outs.iter().enumerate() {
            let prog = self.programs[k];
            (f.UseProgram)(prog);
            let loc = |n: &str| (f.GetUniformLocation)(prog, CString::new(n).unwrap().as_ptr() as *const u8);
            (f.Uniform1i)(loc("src"), 0);
            (f.Uniform1i)(loc("codes"), 1);
            (f.Uniform1ui)(loc("deep"), deep as u32);
            (f.Uniform1i)(loc("width"), w as i32);
            (f.BindFramebuffer)(FRAMEBUFFER, fbo);
            (f.Viewport)(0, 0, tw as i32, th as i32);
            (f.DrawArrays)(0x0004, 0, 3);
        }
        (f.BindFramebuffer)(FRAMEBUFFER, outs[0].0);
        (f.ReadPixels)(0, 0, w as i32, h as i32, RGBA_INTEGER, ty, out.as_mut_ptr() as *mut c_void);
        let mut flags = vec![0u8; (fw * h) as usize];
        (f.BindFramebuffer)(FRAMEBUFFER, outs[1].0);
        (f.ReadPixels)(0, 0, fw as i32, h as i32, RED_INTEGER, 0x1401, flags.as_mut_ptr() as *mut c_void);
        (f.BindFramebuffer)(FRAMEBUFFER, 0);
        match (f.GetError)() {
            0 => Ok(flags.chunks(fw as usize).map(|r| r.iter().any(|&b| b != 0)).collect()),
            e => Err(format!("the GPU output step: GL error 0x{e:x}")),
        }
    }
}

fn nearest(f: &Fns) {
    for p in [0x2801, 0x2800] {
        (f.TexParameteri)(TEXTURE_2D, p, 0x2600); // MIN / MAG filter: NEAREST
    }
    (f.TexParameteri)(TEXTURE_2D, 0x813D, 0); // MAX_LEVEL
}

/// The target at `size` (w, h, internal format), made or remade; (framebuffer, w, h).
fn target(f: &Fns, t: &mut Option<Target>, size: (u32, u32, u32)) -> Result<(u32, u32, u32), String> {
    if t.as_ref().is_none_or(|t| t.size != size) {
        let (mut tex, mut fbo) = t.as_ref().map_or((0, 0), |t| (t.tex, t.fbo));
        if tex == 0 {
            (f.GenTextures)(1, &mut tex);
            (f.GenFramebuffers)(1, &mut fbo);
        }
        (f.BindTexture)(TEXTURE_2D, tex);
        nearest(f);
        let format = if size.2 == 0x8232 { RED_INTEGER } else { RGBA_INTEGER };
        (f.TexImage2D)(TEXTURE_2D, 0, size.2 as i32, size.0 as i32, size.1 as i32, 0, format, 0x1401, std::ptr::null());
        (f.BindFramebuffer)(FRAMEBUFFER, fbo);
        (f.FramebufferTexture2D)(FRAMEBUFFER, COLOR_ATTACHMENT0, TEXTURE_2D, tex, 0);
        if (f.CheckFramebufferStatus)(FRAMEBUFFER) != 0x8CD5 {
            return Err(format!("the GPU output step: target {}×{} (format 0x{:x}) is not usable", size.0, size.1, size.2));
        }
        *t = Some(Target { tex, fbo, size });
    }
    let t = t.as_ref().unwrap();
    Ok((t.fbo, size.0, size.1))
}

fn program(f: &Fns, defines: &str) -> Result<u32, String> {
    let fs = format!("#version 330 core\n{defines}{FS}");
    let prog = (f.CreateProgram)();
    for (kind, text) in [(0x8B31u32, VS.to_string()), (0x8B30, fs)] {
        let sh = (f.CreateShader)(kind);
        let (ptr, len) = (text.as_ptr(), text.len() as i32);
        (f.ShaderSource)(sh, 1, &ptr, &len);
        (f.CompileShader)(sh);
        let mut ok = 0;
        (f.GetShaderiv)(sh, 0x8B81, &mut ok);
        if ok == 0 {
            return Err(format!("the GPU output step's shader: {}", log(|n, l, b| (f.GetShaderInfoLog)(sh, n, l, b))));
        }
        (f.AttachShader)(prog, sh);
    }
    (f.LinkProgram)(prog);
    let mut ok = 0;
    (f.GetProgramiv)(prog, 0x8B82, &mut ok);
    if ok == 0 {
        return Err(format!("the GPU output step's program: {}", log(|n, l, b| (f.GetProgramInfoLog)(prog, n, l, b))));
    }
    Ok(prog)
}

fn log(get: impl Fn(i32, *mut i32, *mut u8)) -> String {
    let mut buf = vec![0u8; 2048];
    let mut n = 0;
    get(buf.len() as i32, &mut n, buf.as_mut_ptr());
    String::from_utf8_lossy(&buf[..n.max(0) as usize]).into_owned()
}
