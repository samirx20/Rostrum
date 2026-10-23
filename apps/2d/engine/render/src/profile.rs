//! Measurement only (E5): where a paint's time goes. Off unless `ROSTRUM2D_PROFILE=<file.csv>` is set; then every
//! paint waits for the GPU and appends a row: what was painted (`label`), recording on the CPU, flushing (Skia turning
//! its recorded ops into GL calls), waiting for the GPU after that, the GPU's own span (GL timestamp queries around
//! the flush), and GL calls counted and timed on the CPU through wrappers put into Skia's GL interface (`wrap`):
//! shader compiles / links, texture and buffer uploads, render-target switches, draws, waits and error checks.
//! Waiting after every paint removes the CPU / GPU overlap an export has; it is for splitting the time, not totals.
//! Windows x64 only (WGL); every wrapped GL function takes integer / pointer arguments, forwarded as 10 words (glBlitFramebuffer
//! takes 10: with 9 its filter was garbage and every blit failed while profiling, unseen with Skia's checks on).

use std::cell::RefCell;
use std::ffi::c_void;
use std::io::Write;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering::Relaxed};
use std::sync::OnceLock;

/// The file rows go to, when profiling.
pub fn path() -> Option<&'static str> {
    static P: OnceLock<Option<String>> = OnceLock::new();
    P.get_or_init(|| std::env::var("ROSTRUM2D_PROFILE").ok().filter(|p| !p.is_empty())).as_deref()
}

thread_local! {
    static LABEL: RefCell<String> = RefCell::new("frame".into());
}

/// Names the next paints' rows (a piece timed alone, render_costs.rs); `frame` again after.
pub fn label(l: &str) {
    LABEL.with(|x| *x.borrow_mut() = l.to_string());
}

type Word = usize;
type Fn10 = extern "system" fn(Word, Word, Word, Word, Word, Word, Word, Word, Word, Word) -> Word;

/// The GL calls counted: name, kind (index into `KINDS`).
const WRAPPED: [(&str, usize); 34] = [
    ("glCompileShader", 0),
    ("glLinkProgram", 1),
    ("glTexImage2D", 2),
    ("glTexSubImage2D", 2),
    ("glBufferData", 3),
    ("glBufferSubData", 3),
    ("glBindFramebuffer", 4),
    ("glBlitFramebuffer", 4),
    ("glDrawArrays", 5),
    ("glDrawElements", 5),
    ("glDrawRangeElements", 5),
    ("glDrawArraysInstanced", 5),
    ("glDrawElementsInstanced", 5),
    ("glDrawArraysInstancedBaseInstance", 5),
    ("glDrawElementsInstancedBaseVertexBaseInstance", 5),
    ("glUseProgram", 6),
    ("glFinish", 7),
    ("glClientWaitSync", 7),
    ("glWaitSync", 7),
    ("glFlush", 7),
    ("glGetError", 8),
    ("glTexStorage2D", 9),
    ("glCopyTexSubImage2D", 9),
    ("glGenerateMipmap", 9),
    ("glCheckFramebufferStatus", 10),
    ("glFramebufferTexture2D", 11),
    ("glFramebufferRenderbuffer", 11),
    ("glRenderbufferStorageMultisample", 11),
    ("glGenTextures", 12),
    ("glDeleteTextures", 12),
    ("glGenFramebuffers", 12),
    ("glDeleteFramebuffers", 12),
    ("glBindTexture", 13),
    ("glTexParameteri", 13),
];
pub const KINDS: [&str; 14] = ["compiles", "links", "texUploads", "bufUploads", "fboBinds", "draws", "useProgram", "syncs", "getError", "texAlloc", "fbStatus", "fbAttach", "genDelete", "bindTex"];

static ORIG: [AtomicUsize; 34] = [const { AtomicUsize::new(0) }; 34];
static COUNT: [AtomicU64; 14] = [const { AtomicU64::new(0) }; 14];
static NANOS: [AtomicU64; 14] = [const { AtomicU64::new(0) }; 14];

macro_rules! tramp {
    ($($i:literal),*) => {
        const TRAMPS: [Fn10; 34] = [$({
            extern "system" fn t(a: Word, b: Word, c: Word, d: Word, e: Word, f: Word, g: Word, h: Word, i: Word, j: Word) -> Word {
                let orig: Fn10 = unsafe { std::mem::transmute(ORIG[$i].load(Relaxed)) };
                let k = WRAPPED[$i].1;
                let t0 = std::time::Instant::now();
                let r = orig(a, b, c, d, e, f, g, h, i, j);
                NANOS[k].fetch_add(t0.elapsed().as_nanos() as u64, Relaxed);
                COUNT[k].fetch_add(1, Relaxed);
                r
            }
            t
        }),*];
    };
}
tramp!(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33);

/// Skia's GL loader goes through this: a counted function gets its wrapper when profiling.
pub fn wrap(name: &str, p: *const c_void) -> *const c_void {
    if path().is_none() || p.is_null() {
        return p;
    }
    match WRAPPED.iter().position(|w| w.0 == name) {
        Some(i) => {
            ORIG[i].store(p as usize, Relaxed);
            TRAMPS[i] as *const c_void
        }
        None => p,
    }
}

/// GL timestamp queries (GL 3.3 / ARB_timer_query).
pub struct Timer {
    gen: extern "system" fn(i32, *mut u32),
    counter: extern "system" fn(u32, u32),
    result: extern "system" fn(u32, u32, *mut u64),
    q: [u32; 2],
}

const GL_TIMESTAMP: u32 = 0x8E28;
const GL_QUERY_RESULT: u32 = 0x8866;

impl Timer {
    pub fn new(load: impl Fn(&std::ffi::CStr) -> *const c_void) -> Option<Timer> {
        path()?;
        let (g, c, r) = (load(c"glGenQueries"), load(c"glQueryCounter"), load(c"glGetQueryObjectui64v"));
        if g.is_null() || c.is_null() || r.is_null() {
            return None;
        }
        let mut t = unsafe { Timer { gen: std::mem::transmute(g), counter: std::mem::transmute(c), result: std::mem::transmute(r), q: [0; 2] } };
        (t.gen)(2, t.q.as_mut_ptr());
        Some(t)
    }
    pub fn mark(&self, i: usize) {
        (self.counter)(self.q[i], GL_TIMESTAMP);
    }
    /// The GPU's ms between the two marks (waits for them).
    pub fn ms(&self) -> f64 {
        let (mut a, mut b) = (0u64, 0u64);
        (self.result)(self.q[0], GL_QUERY_RESULT, &mut a);
        (self.result)(self.q[1], GL_QUERY_RESULT, &mut b);
        b.saturating_sub(a) as f64 / 1e6
    }
}

/// The flush split (E16): Skia's submit, its cleanup of unused GPU memory, our one error check after (painter.rs `paint`).
pub fn parts(ms: [f64; 3]) {
    PARTS.with(|p| p.set(ms));
}

thread_local! {
    static PARTS: std::cell::Cell<[f64; 3]> = const { std::cell::Cell::new([0.0; 3]) };
}

/// Clears the GL counters (a paint starts).
pub fn reset() {
    for k in 0..KINDS.len() {
        COUNT[k].store(0, Relaxed);
        NANOS[k].store(0, Relaxed);
    }
}

/// Appends one paint's row: label, record / flush / wait / gpu ms, the flush's parts (`parts`), then each GL kind's count and CPU ms.
pub fn row(record: f64, flush: f64, wait: f64, gpu: f64) {
    let Some(p) = path() else { return };
    let new = !std::path::Path::new(p).exists();
    let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(p) else { return };
    if new {
        let kinds: Vec<String> = KINDS.iter().flat_map(|k| [k.to_string(), format!("{k}Ms")]).collect();
        let _ = writeln!(f, "label,recordMs,flushMs,waitMs,gpuMs,submitMs,cleanupMs,checkMs,{}", kinds.join(","));
    }
    let gl: Vec<String> = (0..KINDS.len()).map(|k| format!("{},{:.3}", COUNT[k].load(Relaxed), NANOS[k].load(Relaxed) as f64 / 1e6)).collect();
    let l = LABEL.with(|x| x.borrow().clone());
    let [submit, cleanup, check] = PARTS.with(|p| p.get());
    let _ = writeln!(f, "{l},{record:.3},{flush:.3},{wait:.3},{gpu:.3},{submit:.3},{cleanup:.3},{check:.3},{}", gl.join(","));
}
