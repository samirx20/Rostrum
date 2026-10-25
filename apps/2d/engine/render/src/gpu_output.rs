//! The output step on the GPU, exact (painter.rs `output_start` / `output_finish`): a frame's half floats become the same
//! bytes as color.rs `output` gives, bit for bit, so a still, a scrubbed frame, the canvas's pixels and the export agree.
//!
//! No float maths is left on the GPU: each channel's half bits index a table of integer codes made on the CPU from the
//! output step itself (color.rs `gpu_codes`), and the dither is the same integer hash. That covers every opaque pixel
//! with finite channels (and transparent ones), which is every pixel of a frame with a background. A pixel the table
//! can't answer exactly (partly transparent: its colour is divided by its alpha; or a channel not finite) is marked,
//! and a second pass reports which blocks of `BLOCK` pixels along a row hold one; the painter redoes only those blocks on
//! the CPU, in a few rectangles (`cpu_rects`): a picture whose edge falls between pixels (a comp drawn at any scale) or
//! whose background is see-through costs the CPU its edge pixels, never its whole rows.
//!
//! The hand-off to the canvas's shared memory (shm.rs) reads back only what changed: the output of the frame last
//! written into each of the memory's slots is kept on the GPU, and the second pass also marks the blocks that differ
//! from it; only rows holding one are read into the slot (the rest of the slot already holds those bytes). `start`
//! queues both passes and the marks' readback behind a fence without waiting, so a frame can be finished later
//! (`finish`, a frame drawn ahead while playing: serve_ahead.rs). Raw OpenGL 3.3 (Skia's runtime shaders have no
//! integers); Skia's GL state is reset afterwards.

use std::ffi::{c_void, CString};

/// Pixels per flag (the second pass's fragment checks this many along a row).
pub const BLOCK: u32 = 32;

const VS: &str = "#version 330 core
void main() { vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2)); gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0); }";

const FS: &str = include_str!("gpu_output.glsl");

const TEXTURE_2D: u32 = 0x0DE1;
const FRAMEBUFFER: u32 = 0x8D40;
const COLOR_ATTACHMENT0: u32 = 0x8CE0;
const RGBA_INTEGER: u32 = 0x8D99;
const RED_INTEGER: u32 = 0x8D94;
const PIXEL_PACK_BUFFER: u32 = 0x88EB;

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
    ReadPixels: fn(i32, i32, i32, i32, u32, u32, *mut c_void); GetError: fn() -> u32; GenBuffers: fn(i32, *mut u32);
    BufferData: fn(u32, isize, *const c_void, u32); FenceSync: fn(u32, u32) -> *const c_void;
    ClientWaitSync: fn(*const c_void, u32, u64) -> u32; DeleteSync: fn(*const c_void);
    MapBufferRange: fn(u32, isize, isize, u32) -> *const u8; UnmapBuffer: fn(u32) -> u8;
}

/// One output target: its texture and framebuffer, at a size and format.
struct Target {
    tex: u32,
    fbo: u32,
    size: (u32, u32, u32),
}

/// What a slot holds: the block (shm.rs), the slot, and the form of its bytes (w, h, deep, screen).
pub type Holds = (u64, usize, u32, u32, bool, bool);

/// The output of a frame started and not finished: where it goes and the fence after its marks' readback.
struct Pending {
    fence: *const c_void,
    /// The frame's texture (read again where the CPU redoes pixels).
    src: u32,
    holds: Option<Holds>,
    compare: bool,
    w: u32,
    h: u32,
    deep: bool,
}

/// A finished output: the rectangles the CPU must redo (x0, y0, x1, y1 px) with the frame's halves there as stored
/// (premultiplied RGBA16F, top row first), and how many rows were read back from the GPU.
pub struct Done {
    pub cpu: Vec<([u32; 4], Vec<u8>)>,
    pub rows_read: u32,
}

/// Rows per band of `cpu_rects`: a marked block's rectangle is at least this tall (fewer, larger reads).
const BAND: usize = 8;

/// The marked blocks (`flags`: `fw` per row, bit 0) as rectangles of px (x0, y0, x1, y1) in a frame `w` px wide: in
/// bands of BAND rows, each run of blocks marked in any of the band's rows; a run the band before had too grows down
/// (a straight edge is one tall rectangle, a slanting one a few blocks per band).
pub fn cpu_rects(flags: &[u8], fw: usize, w: u32) -> Vec<[u32; 4]> {
    let h = flags.len() / fw;
    let px = |b: usize| (b as u32 * BLOCK).min(w);
    let (mut done, mut open) = (vec![], Vec::<[u32; 4]>::new());
    let mut band = vec![false; fw];
    for y0 in (0..h).step_by(BAND) {
        let y1 = (y0 + BAND).min(h);
        band.fill(false);
        for row in flags[y0 * fw..y1 * fw].chunks(fw) {
            for (b, m) in band.iter_mut().zip(row) {
                *b |= m & 1 != 0;
            }
        }
        let mut next = vec![];
        let mut b = 0;
        while b < fw {
            if !band[b] {
                b += 1;
                continue;
            }
            let e = b + band[b..].iter().take_while(|&&m| m).count();
            let (x0, x1) = (px(b), px(e));
            match open.iter().position(|r| r[0] == x0 && r[2] == x1) {
                Some(i) => next.push([x0, open.swap_remove(i)[1], x1, y1 as u32]),
                None => next.push([x0, y0 as u32, x1, y1 as u32]),
            }
            b = e;
        }
        done.append(&mut open);
        open = next;
    }
    done.append(&mut open);
    done
}

pub struct GpuOutput {
    f: Fns,
    programs: [u32; 2],
    vao: u32,
    codes: u32,
    /// Which table is in `codes` (its address).
    codes_key: usize,
    /// The frame being output now.
    cur: Option<Target>,
    /// Per slot of the canvas's memory: the output it holds, and what it is (`Holds`).
    kept: [Option<(Target, Holds)>; 2],
    flags: Option<Target>,
    /// A framebuffer the frame's texture is attached to while the CPU's pixels are read from it.
    src_fbo: u32,
    pbo: (u32, usize),
    pending: Option<Pending>,
}

impl GpuOutput {
    /// Loads GL 3.3 and builds both programs; an Err names what failed.
    pub fn new(load: impl Fn(&CString) -> *const c_void) -> Result<GpuOutput, String> {
        let f = Fns::load(&load).ok_or("the GPU output step needs OpenGL 3.3")?;
        let programs = [program(&f, "")?, program(&f, &format!("#define FLAGS\n#define BLOCK {BLOCK}\n"))?];
        let (mut vao, mut codes, mut pbo, mut src_fbo) = (0, 0, 0, 0);
        (f.GenVertexArrays)(1, &mut vao);
        (f.GenFramebuffers)(1, &mut src_fbo);
        (f.GenTextures)(1, &mut codes);
        (f.GenBuffers)(1, &mut pbo);
        Ok(GpuOutput { f, programs, vao, codes, codes_key: 0, cur: None, kept: [None, None], flags: None, src_fbo, pbo: (pbo, 0), pending: None })
    }

    /// Queues the output of texture `src` (the frame, RGBA16F, w × h, top row first) with `codes` (color.rs `gpu_codes`):
    /// RGBA8 (RGBA16 little-endian when `deep`; BGRA, premultiplied, when `screen`: see `finish`), and the marks of rows
    /// the CPU redoes and, with `holds` (the slot it goes into and its form), of blocks differing from what that slot
    /// holds. Nothing waits. The caller has flushed Skia's work and resets Skia's GL state afterwards.
    pub fn start(&mut self, src: u32, (w, h): (u32, u32), codes: &std::sync::Arc<[u32]>, deep: bool, screen: bool, holds: Option<Holds>) -> Result<(), String> {
        self.cancel();
        let f = &self.f;
        while (f.GetError)() != 0 {} // an earlier error is not ours
        (f.BindBuffer)(PIXEL_PACK_BUFFER, 0);
        (f.BindBuffer)(0x88EC, 0); // PIXEL_UNPACK_BUFFER
        for p in [0x0CF2, 0x0D02, 0x0CF3, 0x0CF4, 0x0D03, 0x0D04] {
            (f.PixelStorei)(p, 0); // (UN)PACK_ROW_LENGTH, SKIP_ROWS, SKIP_PIXELS
        }
        (f.PixelStorei)(0x0CF5, 4); // UNPACK_ALIGNMENT
        (f.PixelStorei)(0x0D05, 1); // PACK_ALIGNMENT
        // The targets first: making one binds its texture.
        let fw = w.div_ceil(BLOCK);
        let fmt = if deep { 0x8D76 } else { 0x8D7C }; // RGBA16UI / RGBA8UI
        (f.ActiveTexture)(0x84C2);
        let out = target(f, &mut self.cur, (w, h, fmt))?;
        let flags = target(f, &mut self.flags, (fw, h, 0x8232))?; // R8UI
        let slot = holds.map(|k| k.1);
        let prev = slot.and_then(|s| self.kept[s].as_ref()).filter(|k| Some(k.1) == holds).map(|k| k.0.tex);
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
        for (k, (fbo, tw, th, _)) in [out, flags].into_iter().enumerate() {
            if k == 1 {
                // The marks read this frame's output and the slot's: units 3 and 4.
                for (unit, tex) in [(0x84C3, out.3), (0x84C4, prev.unwrap_or(out.3))] {
                    (f.ActiveTexture)(unit);
                    (f.BindSampler)(unit - 0x84C0, 0);
                    (f.BindTexture)(TEXTURE_2D, tex);
                }
                (f.ActiveTexture)(0x84C0);
            }
            let prog = self.programs[k];
            (f.UseProgram)(prog);
            let loc = |n: &str| (f.GetUniformLocation)(prog, CString::new(n).unwrap().as_ptr() as *const u8);
            for (n, v) in [("src", 0), ("codes", 1), ("cur", 3), ("prev", 4), ("width", w as i32)] {
                (f.Uniform1i)(loc(n), v);
            }
            for (n, v) in [("deep", deep), ("screen", screen), ("compare", prev.is_some())] {
                (f.Uniform1ui)(loc(n), v as u32);
            }
            (f.BindFramebuffer)(FRAMEBUFFER, fbo);
            (f.Viewport)(0, 0, tw as i32, th as i32);
            (f.DrawArrays)(0x0004, 0, 3);
        }
        // The marks into the pixel buffer, read when the fence has passed.
        let bytes = (fw * h) as usize;
        (f.BindBuffer)(PIXEL_PACK_BUFFER, self.pbo.0);
        if self.pbo.1 < bytes {
            (f.BufferData)(PIXEL_PACK_BUFFER, bytes as isize, std::ptr::null(), 0x88E1); // STREAM_READ
            self.pbo.1 = bytes;
        }
        (f.ReadPixels)(0, 0, fw as i32, h as i32, RED_INTEGER, 0x1401, std::ptr::null_mut());
        (f.BindBuffer)(PIXEL_PACK_BUFFER, 0);
        (f.BindFramebuffer)(FRAMEBUFFER, 0);
        let fence = (f.FenceSync)(0x9117, 0); // SYNC_GPU_COMMANDS_COMPLETE
        match (f.GetError)() {
            0 => {
                self.pending = Some(Pending { fence, src, holds, compare: prev.is_some(), w, h, deep });
                Ok(())
            }
            e => {
                (f.DeleteSync)(fence);
                Err(format!("the GPU output step: GL error 0x{e:x}"))
            }
        }
    }

    /// The started output into `out` (exactly its size): waits for the GPU, then reads the rows that changed (all of
    /// them without a slot or when the slot held something else) and are not all the CPU's; returns the CPU's rectangles. With a
    /// slot, `out` must be that slot's bytes, as last written (rows not read are left as they are).
    pub fn finish(&mut self, out: &mut [u8]) -> Result<Done, String> {
        let p = self.pending.take().ok_or("the GPU output step: nothing started")?;
        let f = &self.f;
        let waited = (f.ClientWaitSync)(p.fence, 0x1, u64::MAX); // SYNC_FLUSH_COMMANDS_BIT
        (f.DeleteSync)(p.fence);
        if waited == 0x911D {
            return Err("the GPU output step: waiting for the GPU failed".into());
        }
        let (w, h, bpp) = (p.w as usize, p.h as usize, if p.deep { 8 } else { 4 });
        assert_eq!(out.len(), w * h * bpp, "output buffer size");
        let fw = (p.w.div_ceil(BLOCK)) as usize;
        (f.BindBuffer)(PIXEL_PACK_BUFFER, self.pbo.0);
        let ptr = (f.MapBufferRange)(PIXEL_PACK_BUFFER, 0, (fw * h) as isize, 0x1); // MAP_READ_BIT
        if ptr.is_null() {
            (f.BindBuffer)(PIXEL_PACK_BUFFER, 0);
            return Err("the GPU output step: mapping its marks failed".into());
        }
        let flags = unsafe { std::slice::from_raw_parts(ptr, fw * h) };
        let rects = cpu_rects(flags, fw, p.w);
        // Per row: bit 1, it changed; bit 2, every block is the CPU's (nothing of it to read from the GPU).
        let marks: Vec<u8> = flags.chunks(fw).map(|r| r.iter().fold(0, |a, b| a | b) | if r.iter().all(|m| m & 1 != 0) { 4 } else { 0 }).collect();
        (f.UnmapBuffer)(PIXEL_PACK_BUFFER);
        (f.BindBuffer)(PIXEL_PACK_BUFFER, 0);
        // A row's blocks the CPU redoes are written over what is read (or kept) there: the CPU's blocks are not compared.
        let read = |m: u8| m & 4 == 0 && (!p.compare || m & 2 != 0);
        let ty = if p.deep { 0x1403 } else { 0x1401 };
        let cur = self.cur.as_ref().ok_or("the GPU output step: no output")?;
        (f.BindFramebuffer)(FRAMEBUFFER, cur.fbo);
        for (k, v) in [(0x0D05, 1), (0x0D02, 0), (0x0D03, 0), (0x0D04, 0)] {
            (f.PixelStorei)(k, v); // PACK_ALIGNMENT, ROW_LENGTH, SKIP_ROWS, SKIP_PIXELS: Skia may have set them since `start`
        }
        let (mut y, mut rows_read) = (0, 0);
        while y < h {
            if !read(marks[y]) {
                y += 1;
                continue;
            }
            let n = marks[y..].iter().take_while(|&&m| read(m)).count();
            (f.ReadPixels)(0, y as i32, w as i32, n as i32, RGBA_INTEGER, ty, out[y * w * bpp..].as_mut_ptr() as *mut c_void);
            rows_read += n as u32;
            y += n;
        }
        // The halves where the CPU redoes pixels, from the frame itself (the GPU has finished it: nothing waits).
        let mut cpu = Vec::with_capacity(rects.len());
        if !rects.is_empty() {
            (f.BindFramebuffer)(FRAMEBUFFER, self.src_fbo);
            (f.FramebufferTexture2D)(FRAMEBUFFER, COLOR_ATTACHMENT0, TEXTURE_2D, p.src, 0);
            for r @ [x0, y0, x1, y1] in rects {
                let mut raw = vec![0u8; ((x1 - x0) * (y1 - y0) * 8) as usize];
                (f.ReadPixels)(x0 as i32, y0 as i32, (x1 - x0) as i32, (y1 - y0) as i32, 0x1908, 0x140B, raw.as_mut_ptr() as *mut c_void); // RGBA, HALF_FLOAT
                cpu.push((r, raw));
            }
            (f.FramebufferTexture2D)(FRAMEBUFFER, COLOR_ATTACHMENT0, TEXTURE_2D, 0, 0);
        }
        (f.BindFramebuffer)(FRAMEBUFFER, 0);
        if let Some(e) = Some((f.GetError)()).filter(|&e| e != 0) {
            self.kept = [None, None];
            return Err(format!("the GPU output step: GL error 0x{e:x}"));
        }
        // The slot now holds this output: its target is kept for the next frame into that slot.
        if let Some(holds) = p.holds {
            let old = self.kept[holds.1].take().map(|k| k.0);
            self.kept[holds.1] = Some((self.cur.take().unwrap(), holds));
            self.cur = old;
        }
        Ok(Done { cpu, rows_read })
    }

    /// Drops an output started and not finished (the slot it was for keeps what it holds).
    pub fn cancel(&mut self) {
        if let Some(p) = self.pending.take() {
            (self.f.DeleteSync)(p.fence);
        }
    }

    /// A slot was written some other way: what it holds is no longer known here.
    pub fn forget(&mut self, slot: usize) {
        self.kept[slot] = None;
    }
}

fn nearest(f: &Fns) {
    for p in [0x2801, 0x2800] {
        (f.TexParameteri)(TEXTURE_2D, p, 0x2600); // MIN / MAG filter: NEAREST
    }
    (f.TexParameteri)(TEXTURE_2D, 0x813D, 0); // MAX_LEVEL
}

/// The target at `size` (w, h, internal format), made or remade; (framebuffer, w, h, texture).
fn target(f: &Fns, t: &mut Option<Target>, size: (u32, u32, u32)) -> Result<(u32, u32, u32, u32), String> {
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
    Ok((t.fbo, size.0, size.1, t.tex))
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
