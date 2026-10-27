//! The painting kit's dabs, native (`shared/painting-kit` `brush.dabs`): a planned stroke (`brush.plan`: the path, the
//! random draws and the tip profiles stay in numpy) laid into a layer with the same pixels as numpy's, bit for bit, so
//! the kit's replay and cache stay exact whichever lays them. The Python side is the kit's `native.py` (ctypes).
//!
//! `rostrum2d_stamp_dabs(params, dabs, n, profiles, layer, cov, res, mask, paper_g, paper_f, tex, under, under_row,
//! err, err_len)`:
//! `params` (P_* below), `dabs` n rows of D_* f64, `profiles` four rows of `kr` f64 (prof, start, end, streak), `layer`
//! H×W×4 f32 changed in place, `cov` the stroke's coverage so far over its bbox (f32, grown in place), `res` the wet
//! reservoir (D×D×4 f32) or null: with P_RES_IN it starts as `res` (a stroke laid in pieces goes on from the last),
//! else as the first wet dab's pick-up; after the last dab it is written back. `mask` / `paper_g` / `paper_f` H×W f32
//! or null, `tex` the tip picture (P_TEX x P_TEX f32) or null, `under` the composite below (RGB f32, `under_row` floats a row, 4 a pixel) or null. 0, or 1 with a
//! message in `err`.
//!
//! `rostrum2d_stamp_straight8(px, px_row, out, out_row, h, w)`: premultiplied f32 RGBA (`px_row` floats a row) as
//! straight RGBA8 (`out_row` bytes a row), the kit's `compose.straight8` byte for byte.
//!
//! `rostrum2d_stamp_spacing(l, pr, n, k, out, cap)`: where a stroke's dabs go along its path, the kit's
//! `brush._spacing` (with `shape.step_scale`) number for number; `l` the path's lengths so far and `pr` its pressure (n
//! f64 each), `k` = step, size_pressure, size, the length the taper is sized by, taper start, taper end; the places
//! written to `out` (at most `cap`); how many, or -1 when `cap` is too few.
//!
//! `rostrum2d_stamp_fill(region, row, h, w, c, col)`: a fill's coverage `c` (h×w f32) laid on `h` rows of `w`
//! RGBA f32 (`row` floats apart) in one colour (`col`, 3 f32), the kit's `marks.apply_paint` (normal, from no coverage)
//! number for number.

mod paint;
mod tip;

use paint::Mode;
use tip::Tip;

/// The layout of `params` and `dabs` and the meaning of the tip / mode ids (the kit's native.py writes the same).
/// Bump it with any change to the call: native.py reads `rostrum2d_stamp_layout` on load and refuses another build.
pub const LAYOUT: f64 = 5.0;
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
const P_WRAP: usize = 21; // 1: a seamless canvas, its opposite edges joined (the kit's wrap.py)
const P_RES_IN: usize = 22; // 1: the reservoir goes on from `res`
pub const PARAMS: usize = 23;
pub const DAB: usize = 22; // x y r a cos sin t s lay take take_weak wv x0 x1 y0 y1 oy ox r g b again

pub struct Stroke<'a> {
    pub tip: Tip,
    pub mode: Mode,
    pub kr: usize,
    pub soft: f64,
    pub along: f64,
    pub cj: f64,
    pub wet: f64,
    pub sample_all: bool,
    /// The canvas's opposite edges are joined: the reservoir picks up across them, not the edge repeated.
    pub wrap: bool,
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
    /// Another part of the dab before it (a seamless canvas lays a dab crossing an edge on both sides): it lays with
    /// the reservoir that dab picked up, picking up nothing itself.
    pub again: bool,
}

impl Dab {
    fn from(row: &[f64]) -> Dab {
        let i = |k: usize| row[k] as i64;
        Dab {
            x: row[0], y: row[1], r: row[2], a: row[3], cos: row[4], sin: row[5], t: row[6], s: row[7],
            lay: row[8], take: row[9], take_weak: row[10] != 0.0, wv: row[11],
            bx: [i(12), i(13), i(14), i(15)], at: [i(16), i(17)], col: [row[18] as f32, row[19] as f32, row[20] as f32],
            again: row[21] != 0.0,
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
        kr, soft: p[P_SOFT], along: p[P_ALONG], cj: p[P_CJ], wet: p[P_WET], sample_all: p[P_SAMPLE_ALL] != 0.0, wrap: p[P_WRAP] != 0.0, grain,
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
    params: *const f64, dabs: *const f64, n: usize, profiles: *const f64, layer: *mut f32, cov: *mut f32, res: *mut f32,
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
        let d = p[P_D] as usize;
        let res = (!res.is_null()).then(|| (std::slice::from_raw_parts_mut(res, d * d * 4), p[P_RES_IN] != 0.0));
        if res.is_none() && p[P_RES_IN] != 0.0 {
            return Err("a reservoir to go on from needs its pixels".into());
        }
        lay(&st, &rows, (h, w), bbox, d, layer, cov, under, res)
    };
    match std::panic::catch_unwind(std::panic::AssertUnwindSafe(run)) {
        Ok(Ok(())) => 0,
        Ok(Err(e)) => message(&e, err, err_len),
        Err(_) => message("the native stamper failed (a panic; see stderr)", err, err_len),
    }
}

/// # Safety
/// `px` points at `h` rows of `w` RGBA f32 pixels `px_row` floats apart, `out` at `h` rows of `w` RGBA u8 `out_row`
/// bytes apart.
#[no_mangle]
pub unsafe extern "C" fn rostrum2d_stamp_straight8(px: *const f32, px_row: usize, out: *mut u8, out_row: usize, h: usize, w: usize) -> i32 {
    for y in 0..h {
        let src = std::slice::from_raw_parts(px.add(y * px_row), w * 4);
        let dst = std::slice::from_raw_parts_mut(out.add(y * out_row), w * 4);
        straight8_row(src, dst);
    }
    0
}

/// compose.straight8, one pixel at a time in its precision (f32): colour / max(alpha, 1e-6) (0 where alpha <= 1e-6),
/// alpha as it is, clipped to 0..1, × 255, + 0.5, cut to a byte (numpy's cast truncates; NaN gives 0).
fn straight8_row(src: &[f32], dst: &mut [u8]) {
    const TINY: f32 = 1e-6;
    let byte = |v: f32| (v.max(0.0).min(1.0) * 255.0f32 + 0.5f32) as u8;
    for (p, q) in src.chunks_exact(4).zip(dst.chunks_exact_mut(4)) {
        let a = p[3];
        let m = a.max(TINY);
        for ch in 0..3 {
            q[ch] = if a <= TINY { 0 } else { byte(p[ch] / m) };
        }
        q[3] = byte(a);
    }
}

/// # Safety
/// `l` and `pr` point at `n` f64 (n >= 1), `k` at 6 f64, `out` at `cap` f64.
#[no_mangle]
pub unsafe extern "C" fn rostrum2d_stamp_spacing(l: *const f64, pr: *const f64, n: usize, k: *const f64, out: *mut f64, cap: usize) -> i64 {
    let (l, pr, k) = (std::slice::from_raw_parts(l, n), std::slice::from_raw_parts(pr, n), std::slice::from_raw_parts(k, 6));
    spacing(l, pr, [k[0], k[1], k[2], k[3], k[4], k[5]], std::slice::from_raw_parts_mut(out, cap)).map_or(-1, |m| m as i64)
}

/// brush._spacing in its steps and order (f64 as Python's floats; Python's max / min keep their first argument on a
/// tie). The sine and power are the C library's, as Python's math.sin and ** are.
pub fn spacing(l: &[f64], pr: &[f64], k: [f64; 6], out: &mut [f64]) -> Option<usize> {
    let [step, sp, size, sized, start, end] = k;
    let (total, last) = (l[l.len() - 1], l.len() - 1);
    let flat = pr.iter().all(|&v| v == pr[0]);
    let (mut j, mut x, mut m) = (0usize, 0.0f64, 1usize);
    *out.first_mut()? = 0.0;
    while x < total {
        let p = if flat {
            pr[0]
        } else {
            while j < last && l[j + 1] <= x {
                j += 1;
            }
            if j == last || l[j] == x { pr[j] } else { (pr[j + 1] - pr[j]) / (l[j + 1] - l[j]) * (x - l[j]) + pr[j] }
        };
        let v = step * (1.0 - sp * (1.0 - p)) * step_scale(x, sized, size, start, end);
        x += if v > 0.3 { v } else { 0.3 };
        *out.get_mut(m)? = x;
        m += 1;
    }
    Some(m)
}

/// shape.step_scale.
fn step_scale(t: f64, l: f64, size: f64, start: f64, end: f64) -> f64 {
    if start <= 0.0 && end <= 0.0 {
        return 1.0;
    }
    let mut f = 1.0f64;
    for (amount, d) in [(start, t), (end, l - t)] {
        if amount > 0.0 {
            let (a, b) = (amount * size, l / 2.0);
            let least = if b < a { b } else { a };
            let span = if 1e-6 > least { 1e-6 } else { least };
            let q = d / span;
            let q = if 0.0 > q { 0.0 } else { q };
            let q = if 1.0 < q { 1.0 } else { q };
            f *= (q * std::f64::consts::PI / 2.0).sin().powf(0.8);
        }
    }
    if 0.04 > f { 0.04 } else { f }
}

/// # Safety
/// `region` points at `h` rows of `w` RGBA f32 pixels `row` floats apart, `c` at h×w f32, `col` at 3 f32.
#[no_mangle]
pub unsafe extern "C" fn rostrum2d_stamp_fill(region: *mut f32, row: usize, h: usize, w: usize, c: *const f32, col: *const f32) -> i32 {
    let col = std::slice::from_raw_parts(col, 3);
    for y in 0..h {
        let px = std::slice::from_raw_parts_mut(region.add(y * row), w * 4);
        fill_row(px, std::slice::from_raw_parts(c.add(y * w), w), [col[0], col[1], col[2]]);
    }
    0
}

/// marks.apply_paint, mode normal, k 1, from no coverage (c0 = 0) to `c`, in f32 as numpy: inc = 1 * (c - 0) /
/// (1.0001 - 0); colour += inc * (col - colour); alpha += inc * (1 - alpha).
fn fill_row(px: &mut [f32], c: &[f32], col: [f32; 3]) {
    for (q, &c1) in px.chunks_exact_mut(4).zip(c) {
        let inc = 1.0f32 * (c1 - 0.0f32) / (1.0001f64 as f32 - 0.0f32); // numpy: the Python float made f32
        for ch in 0..3 {
            q[ch] += inc * (col[ch] - q[ch]);
        }
        q[3] += inc * (1.0f32 - q[3]);
    }
}

unsafe fn message(e: &str, err: *mut u8, len: usize) -> i32 {
    let n = e.len().min(len.saturating_sub(1));
    std::ptr::copy_nonoverlapping(e.as_ptr(), err, n);
    *err.add(n) = 0;
    1
}
