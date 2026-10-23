//! The painting kit's dabs, native (`shared/painting-kit` `brush.dabs`): a planned stroke (`brush.plan`: the path, the
//! random draws and the tip profiles stay in numpy) laid into a layer with the same pixels as numpy's, bit for bit, so
//! the kit's replay and cache stay exact whichever lays them. The Python side is the kit's `native.py` (ctypes).
//!
//! `rostrum2d_stamp_dabs(params, dabs, n, profiles, layer, cov, mask, paper_g, paper_f, tex, under, under_row, err,
//! err_len)`:
//! `params` (P_* below), `dabs` n rows of D_* f64, `profiles` four rows of `kr` f64 (prof, start, end, streak), `layer`
//! H×W×4 f32 changed in place, `cov` the stroke's bbox of f32 zeros (filled), `mask` / `paper_g` / `paper_f` H×W f32
//! or null, `tex` the tip picture (P_TEX x P_TEX f32) or null, `under` the composite below (RGB f32, `under_row` floats a row, 4 a pixel) or null. 0, or 1 with a
//! message in `err`.

mod paint;
mod tip;

use paint::Mode;
use tip::Tip;

/// The layout of `params` and `dabs` and the meaning of the tip / mode ids (the kit's native.py writes the same).
/// Bump it with any change to the call: native.py reads `rostrum2d_stamp_layout` on load and refuses another build.
pub const LAYOUT: f64 = 3.0;
const P_LAYOUT: usize = 0;
const P_TIP: usize = 1;
const P_MODE: usize = 2;
const P_KR: usize = 3;
const P_SOFT: usize = 4;
const P_ALONG: usize = 5;
const P_CJ: usize = 6;
const P_WET: usize = 7;
const P_SAMPLE_ALL: usize = 8;
const P_GRAIN: usize = 9; // 0: no grain
const P_R0: usize = 10;
const P_RL: usize = 11;
const P_LENGTH: usize = 12;
const P_BBOX: usize = 13; // x0, y0, x1, y1
const P_D: usize = 17;
const P_H: usize = 18;
const P_W: usize = 19;
const P_TEX: usize = 20; // the tip picture's side; 0: none
pub const PARAMS: usize = 21;
pub const DAB: usize = 21; // x y r a cos sin t s lay take take_weak wv x0 x1 y0 y1 oy ox r g b

pub struct Stroke<'a> {
    pub tip: Tip,
    pub mode: Mode,
    pub kr: usize,
    pub soft: f64,
    pub along: f64,
    pub cj: f64,
    pub wet: f64,
    pub sample_all: bool,
    pub grain: Option<f64>,
    pub r0: f64,
    pub rl: f64,
    pub length: f64,
    pub w: usize,
    pub prof: &'a [f64],
    pub start: &'a [f64],
    pub end: &'a [f64],
    pub streak: &'a [f64],
    pub mask: Option<&'a [f32]>,
    pub paper_g: Option<&'a [f32]>,
    pub paper_f: Option<&'a [f32]>,
    /// The tip picture (`tex_n` square, rows across the tip), or none.
    pub tex: Option<&'a [f32]>,
    pub tex_n: usize,
}

/// One dab's numbers (a row of `dabs`).
pub struct Dab {
    pub x: f64,
    pub y: f64,
    pub r: f64,
    pub a: f64,
    pub cos: f64,
    pub sin: f64,
    pub t: f64,
    pub s: f64,
    /// How much of the reservoir it lays and how much it takes up; `take_weak`: `take` is a Python float (numpy then
    /// takes it up in f32), else a NumPy scalar (f64).
    pub lay: f64,
    pub take: f64,
    pub take_weak: bool,
    pub wv: f64,
    pub bx: [i64; 4], // x0 x1 y0 y1
    pub at: [i64; 2], // the reservoir's window: oy, ox
    pub col: [f32; 3],
}

impl Dab {
    fn from(row: &[f64]) -> Dab {
        let i = |k: usize| row[k] as i64;
        Dab {
            x: row[0], y: row[1], r: row[2], a: row[3], cos: row[4], sin: row[5], t: row[6], s: row[7],
            lay: row[8], take: row[9], take_weak: row[10] != 0.0, wv: row[11],
            bx: [i(12), i(13), i(14), i(15)], at: [i(16), i(17)], col: [row[18] as f32, row[19] as f32, row[20] as f32],
        }
    }
}

mod stroke;
pub use stroke::lay;

/// Reads `params` into a Stroke (the slices borrowed from the caller's arrays).
#[allow(clippy::too_many_arguments)]
unsafe fn stroke<'a>(p: &[f64], profiles: *const f64, mask: *const f32, g: *const f32, f: *const f32, tex: *const f32) -> Result<Stroke<'a>, String> {
    if p[P_LAYOUT] != LAYOUT {
        return Err(format!("the native stamper reads layout {LAYOUT}, was given {}", p[P_LAYOUT]));
    }
    let (kr, hw) = (p[P_KR] as usize, p[P_H] as usize * p[P_W] as usize);
    let prof = std::slice::from_raw_parts(profiles, 4 * kr);
    let field = |q: *const f32| (!q.is_null()).then(|| std::slice::from_raw_parts(q, hw));
    let grain = (p[P_GRAIN] > 0.0).then_some(p[P_GRAIN]);
    let tex_n = p[P_TEX] as usize;
    let st = Stroke {
        tip: Tip::from_id(p[P_TIP]).ok_or("unknown tip")?,
        mode: Mode::from_id(p[P_MODE]).ok_or("unknown mode")?,
        kr, soft: p[P_SOFT], along: p[P_ALONG], cj: p[P_CJ], wet: p[P_WET], sample_all: p[P_SAMPLE_ALL] != 0.0, grain,
        r0: p[P_R0], rl: p[P_RL], length: p[P_LENGTH], w: p[P_W] as usize,
        prof: &prof[..kr], start: &prof[kr..2 * kr], end: &prof[2 * kr..3 * kr], streak: &prof[3 * kr..],
        mask: field(mask), paper_g: field(g), paper_f: field(f),
        tex: (!tex.is_null() && tex_n >= 2).then(|| std::slice::from_raw_parts(tex, tex_n * tex_n)), tex_n,
    };
    if tex_n > 0 && st.tex.is_none() {
        return Err("a tip picture needs its pixels (and a side of 2 or more)".into());
    }
    if (st.grain.is_some() && st.paper_g.is_none()) || (st.tip == Tip::Chalk && st.paper_f.is_none()) {
        return Err("grain and chalk need the paper".into());
    }
    Ok(st)
}

/// The layout this build reads (`LAYOUT`): what native.py checks before its first call.
#[no_mangle]
pub extern "C" fn rostrum2d_stamp_layout() -> f64 {
    LAYOUT
}

/// # Safety
/// Every pointer points at arrays of the sizes the module header gives (or is null where it may be).
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub unsafe extern "C" fn rostrum2d_stamp_dabs(
    params: *const f64, dabs: *const f64, n: usize, profiles: *const f64, layer: *mut f32, cov: *mut f32,
    mask: *const f32, paper_g: *const f32, paper_f: *const f32, tex: *const f32, under: *const f32, under_row: usize,
    err: *mut u8, err_len: usize,
) -> i32 {
    let p = std::slice::from_raw_parts(params, PARAMS);
    let run = || -> Result<(), String> {
        let st = stroke(p, profiles, mask, paper_g, paper_f, tex)?;
        let (h, w) = (p[P_H] as usize, p[P_W] as usize);
        let bbox = [P_BBOX, P_BBOX + 1, P_BBOX + 2, P_BBOX + 3].map(|k| p[k] as usize);
        let layer = std::slice::from_raw_parts_mut(layer, h * w * 4);
        let cov = std::slice::from_raw_parts_mut(cov, (bbox[3] - bbox[1]) * (bbox[2] - bbox[0]));
        let under = (!under.is_null()).then(|| (std::slice::from_raw_parts(under, (h - 1) * under_row + w * 4), under_row));
        let rows: Vec<Dab> = std::slice::from_raw_parts(dabs, n * DAB).chunks(DAB).map(Dab::from).collect();
        lay(&st, &rows, (h, w), bbox, p[P_D] as usize, layer, cov, under)
    };
    match std::panic::catch_unwind(std::panic::AssertUnwindSafe(run)) {
        Ok(Ok(())) => 0,
        Ok(Err(e)) => message(&e, err, err_len),
        Err(_) => message("the native stamper failed (a panic; see stderr)", err, err_len),
    }
}

unsafe fn message(e: &str, err: *mut u8, len: usize) -> i32 {
    let n = e.len().min(len.saturating_sub(1));
    std::ptr::copy_nonoverlapping(e.as_ptr(), err, n);
    *err.add(n) = 0;
    1
}
