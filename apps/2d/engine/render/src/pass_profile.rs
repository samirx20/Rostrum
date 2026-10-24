//! Measurement only (export speed): the graphics card's time per render pass, when profiling (`ROSTRUM2D_PROFILE`, profile.rs).
//! Every framebuffer bind Skia makes puts a GL timestamp in the card's queue; the span to the next bind is that pass's
//! card time, attributed to the pass's size (the viewport Skia sets after the bind), with its draws and multisample
//! resolves counted. Each profiled paint appends its passes, grouped by size, to `<profile>.passes.csv`, so it shows
//! whether the card's time goes to many small layers, a few frame-sized ones, or multisampled atlases.

use std::cell::RefCell;
use std::collections::BTreeMap;
use std::ffi::c_void;
use std::io::Write;
use std::sync::OnceLock;

type Gen = extern "system" fn(i32, *mut u32);
type Counter = extern "system" fn(u32, u32);
type Result64 = extern "system" fn(u32, u32, *mut u64);

static GL: OnceLock<(Gen, Counter, Result64)> = OnceLock::new();

const GL_TIMESTAMP: u32 = 0x8E28;
const GL_QUERY_RESULT: u32 = 0x8866;
const GL_FRAMEBUFFER: usize = 0x8D40;
const GL_DRAW_FRAMEBUFFER: usize = 0x8CA9;

/// One pass: its timestamp query, framebuffer, size, draws and resolves.
struct Pass {
    q: u32,
    fbo: usize,
    size: (usize, usize),
    draws: u64,
    blits: u64,
}

#[derive(Default)]
struct State {
    pool: Vec<u32>,
    passes: Vec<Pass>,
    /// The viewport now set (Skia sets it only when it changes, so a bind without one keeps it).
    viewport: (usize, usize),
}

thread_local! {
    static S: RefCell<State> = RefCell::new(State::default());
}

/// Loads the query functions (profile.rs `Timer::new`).
pub fn init(load: &impl Fn(&std::ffi::CStr) -> *const c_void) {
    let (g, c, r) = (load(c"glGenQueries"), load(c"glQueryCounter"), load(c"glGetQueryObjectui64v"));
    if !(g.is_null() || c.is_null() || r.is_null()) {
        let _ = GL.set(unsafe { (std::mem::transmute(g), std::mem::transmute(c), std::mem::transmute(r)) });
    }
}

fn query(s: &mut State) -> Option<u32> {
    let (gen, counter, _) = GL.get()?;
    if s.pool.is_empty() {
        let mut q = vec![0u32; 1024];
        gen(q.len() as i32, q.as_mut_ptr());
        s.pool = q;
    }
    let q = s.pool.pop()?;
    counter(q, GL_TIMESTAMP);
    Some(q)
}

/// A wrapped GL call is about to run (profile.rs's trampolines): `name` and its first four arguments.
pub fn before(name: &str, a: usize, b: usize, c: usize, d: usize) {
    S.with(|s| {
        let mut s = s.borrow_mut();
        match name {
            "glBindFramebuffer" if a == GL_FRAMEBUFFER || a == GL_DRAW_FRAMEBUFFER => {
                if let Some(q) = query(&mut s) {
                    let size = s.viewport;
                    s.passes.push(Pass { q, fbo: b, size, draws: 0, blits: 0 });
                }
            }
            "glViewport" => {
                s.viewport = (c, d);
                if let Some(p) = s.passes.last_mut() {
                    p.size = (c, d);
                }
            }
            "glBlitFramebuffer" => {
                if let Some(p) = s.passes.last_mut() {
                    p.blits += 1;
                }
            }
            n if n.starts_with("glDraw") => {
                if let Some(p) = s.passes.last_mut() {
                    p.draws += 1;
                }
            }
            _ => {}
        }
        let _ = (a, b);
    });
}

/// After a profiled paint has waited for the card: its passes grouped by size, appended to `<profile>.passes.csv`.
pub fn row(label: &str) {
    let Some(path) = crate::profile::path() else { return };
    let Some(&(_, _, result)) = GL.get() else { return };
    let passes = S.with(|s| {
        let mut s = s.borrow_mut();
        let end = query(&mut s);
        let passes = std::mem::take(&mut s.passes);
        let mut times: Vec<u64> = passes.iter().map(|p| { let mut t = 0; result(p.q, GL_QUERY_RESULT, &mut t); t }).collect();
        if let Some(q) = end {
            let mut t = 0;
            result(q, GL_QUERY_RESULT, &mut t);
            times.push(t);
            s.pool.push(q);
        }
        s.pool.extend(passes.iter().map(|p| p.q));
        passes.into_iter().zip(times.windows(2).map(|w| w[1].saturating_sub(w[0]))).collect::<Vec<_>>()
    });
    // By size: passes, frame buffers seen, draws, resolves, card ms.
    let mut by: BTreeMap<(usize, usize), (u64, std::collections::BTreeSet<usize>, u64, u64, f64)> = BTreeMap::new();
    for (p, ns) in &passes {
        let e = by.entry(p.size).or_default();
        e.0 += 1;
        e.1.insert(p.fbo);
        e.2 += p.draws;
        e.3 += p.blits;
        e.4 += *ns as f64 / 1e6;
    }
    let file = format!("{path}.passes.csv");
    let new = !std::path::Path::new(&file).exists();
    let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(&file) else { return };
    if new {
        let _ = writeln!(f, "label,w,h,passes,fbos,draws,resolves,gpuMs");
    }
    for ((w, h), (n, fbos, draws, blits, ms)) in by {
        let _ = writeln!(f, "{label},{w},{h},{n},{},{draws},{blits},{ms:.3}", fbos.len());
    }
    // Which code opened the paint's layers and surfaces, and how big (anyrender_skia's census).
    let file = format!("{path}.layers.csv");
    let new = !std::path::Path::new(&file).exists();
    let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(&file) else { return };
    if new {
        let _ = writeln!(f, "label,site,size,count,mpx");
    }
    for (site, size, n, mpx) in anyrender_skia::layer_census::take() {
        let _ = writeln!(f, "{label},{site},{size},{n},{mpx:.3}");
    }
}
