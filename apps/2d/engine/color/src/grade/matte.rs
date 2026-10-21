//! G3's HSL qualifier and the matte seam (GRADING.md §3.1; mod.rs doc "Mattes").
//!
//! A layer's matte gives a coverage 0 … 1 per pixel; the layer's weight is `mix · coverage`. The qualifier keys the
//! STACK'S INPUT (the picture as it enters the grade, ACEScg), measured in ACEScct with the shared HSL measurement
//! (hsl.rs), so moving the base grade never moves a matte:
//!
//! - hue: `d` = angular distance (degrees, wrapped) from `centre`; coverage 1 for `d ≤ width / 2`, a smoothstep down to
//!   0 over the next `soft` degrees (`soft` 0: a hard edge). `width` 360 selects every hue. Greys have hue 0, so a hue
//!   key alone selects greys near 0° (a hue key wants a `sat` floor).
//! - sat, lum (0 … 1 on the measurement): `lo`, `hi` with a smoothstep over `softLo` below `lo` and `softHi` above `hi`.
//! - key = the product of the ranges given.
//!
//! Matte finesse, in this order: **denoise** (a bilateral filter on the matte: 9 × 9 taps spaced `denoise / 4` px, a
//! Gaussian in tap space (σ 2 taps) times a Gaussian in matte value (σ [`DENOISE_RANGE`]): flat areas smooth, a real
//! edge stays), **shrink** (an erode over a disc of radius `shrink` px: comp/morph.rs, the comp's own grow / erode), **grow** (a dilate, radius `grow` px;
//! shrink then grow removes specks), **blur** (a Gaussian of σ `blur` px, edges renormalised: the picture's border never
//! fades a matte), then per pixel **clean** (levels: `(m − black) / (white − black)` clamped, black < white), then
//! **invert** (`1 − m`; a layer's `matte.invert` is applied after that again). Lengths are px of the edit's frame.
//!
//! The first four need neighbours, which a colour filter has not: `Qualify::spatial()`. They run as the compositor's
//! matte stages (`Grade::matte_stages`, see mod.rs "The matte seam"); clean and invert are per pixel and always run in
//! the grade's own program. [`Qualify::coverage_image`] is the CPU reference of the whole chain.
use super::hsl::hsl;
use super::window::Window;
use crate::{Curve, Rgb};

/// Matte values differing by this much (0 … 1) are still one surface to the denoise filter.
pub const DENOISE_RANGE: f64 = 0.12;
/// The denoise filter's taps each way (so 9 × 9).
pub const DENOISE_TAPS: i32 = 4;
/// Most spatial mattes in one grade: each takes one channel of the matte image the grade reads.
pub const MAX_SPATIAL: usize = 3;
/// Slots a matted layer takes in the grade uniforms, after its `mix`.
pub const MATTE_SLOTS: usize = 15;

/// A hue range, degrees.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct HueRange {
    pub centre: f32,
    pub width: f32,
    pub soft: f32,
}

/// A sat or lum range: full between `lo` and `hi`, soft below and above.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Range {
    pub lo: f32,
    pub hi: f32,
    pub soft_lo: f32,
    pub soft_hi: f32,
}

/// G3's HSL qualifier (module doc).
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Qualify {
    pub hue: Option<HueRange>,
    pub sat: Option<Range>,
    pub lum: Option<Range>,
    pub invert: bool,
    /// Clean black / clean white: the matte levels.
    pub clean: Option<[f32; 2]>,
    pub denoise: f32,
    pub shrink: f32,
    pub grow: f32,
    pub blur: f32,
}

/// A layer's matte: the qualifier and G4's power windows (window.rs: their combined coverage multiplies the qualifier's),
/// then `invert` over the whole.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Matte {
    pub qualify: Option<Qualify>,
    pub windows: Vec<Window>,
    pub invert: bool,
}

fn smoothstep(a: f64, b: f64, x: f64) -> f64 {
    super::smoothstep(a, b, x)
}
/// 0 below `a`, 1 above `b`, smooth between; a hard step at `b` when the edge has no width.
fn rise(x: f64, a: f64, b: f64) -> f64 {
    if b > a { smoothstep(a, b, x) } else if x >= b { 1.0 } else { 0.0 }
}
fn fall(x: f64, a: f64, b: f64) -> f64 {
    if b > a { 1.0 - smoothstep(a, b, x) } else if x <= a { 1.0 } else { 0.0 }
}
fn band(x: f64, r: &Range) -> f64 {
    let (lo, hi) = (r.lo as f64, r.hi as f64);
    rise(x, (r.lo - r.soft_lo) as f64, lo) * fall(x, hi, (r.hi + r.soft_hi) as f64)
}
fn hue_cov(h: f64, r: &HueRange) -> f64 {
    let d = ((h * 360.0 - r.centre as f64 + 180.0).rem_euclid(360.0) - 180.0).abs();
    let e = r.width as f64 * 0.5;
    fall(d, e, e + r.soft as f64)
}

impl Qualify {
    /// Whether any range is given (a qualifier with none is an error).
    pub fn has_key(&self) -> bool {
        self.hue.is_some() || self.sat.is_some() || self.lum.is_some()
    }

    /// Whether the matte needs neighbours (denoise, shrink, grow or blur): it then runs as matte stages.
    pub fn spatial(&self) -> bool {
        self.denoise > 0.0 || self.shrink > 0.0 || self.grow > 0.0 || self.blur > 0.0
    }

    /// The key at one ACEScg colour: the product of the ranges, before any finesse.
    pub fn key(&self, acescg: [f64; 3]) -> f64 {
        let cct = acescg.map(|c| Curve::AcesCct.encode64(c));
        let p = hsl(cct);
        let mut k = 1.0;
        if let Some(h) = &self.hue {
            k *= hue_cov(p.hue, h);
        }
        if let Some(s) = &self.sat {
            k *= band(p.sat, s);
        }
        if let Some(l) = &self.lum {
            k *= band(p.luma, l);
        }
        k
    }

    /// The per-pixel finesse on a matte value: clean black / white, then invert.
    pub fn finish(&self, m: f64) -> f64 {
        let m = match self.clean {
            Some([b, w]) => ((m - b as f64) / ((w - b) as f64).max(1e-6)).clamp(0.0, 1.0),
            None => m,
        };
        if self.invert { 1.0 - m } else { m }
    }

    /// The uniform slots of the key (`qual[11]`: hue centre, width, soft; sat lo, hi, softLo, softHi; lum ...).
    pub fn key_slots(&self) -> [f32; 11] {
        let h = self.hue.map_or([0.0, 360.0, 0.0], |h| [h.centre, h.width, h.soft]);
        let r = |r: &Option<Range>| r.map_or([0.0; 4], |r| [r.lo, r.hi, r.soft_lo, r.soft_hi]);
        let (s, l) = (r(&self.sat), r(&self.lum));
        [h[0], h[1], h[2], s[0], s[1], s[2], s[3], l[0], l[1], l[2], l[3]]
    }

    /// The raw key of every pixel (ACEScg, `w × h`), then the spatial finesse: denoise, shrink, grow, blur (module
    /// doc). Not yet cleaned or inverted.
    pub fn spatial_matte(&self, px: &[Rgb], w: usize, h: usize) -> Vec<f32> {
        let key: Vec<f32> = px.iter().map(|p| self.key(p.map(f64::from)) as f32).collect();
        self.filter(key, w, h)
    }

    /// The spatial finesse on a key image.
    pub fn filter(&self, mut m: Vec<f32>, w: usize, h: usize) -> Vec<f32> {
        if self.denoise > 0.0 {
            m = denoise(&m, w, h, self.denoise);
        }
        if self.shrink > 0.0 {
            m = morph(&m, w, h, self.shrink, false);
        }
        if self.grow > 0.0 {
            m = morph(&m, w, h, self.grow, true);
        }
        if self.blur > 0.0 {
            m = blur(&m, w, h, self.blur as f64);
        }
        m
    }

    /// The qualifier's whole coverage image on `px` (ACEScg, `w × h`): key, spatial finesse, clean, invert.
    pub fn coverage_image(&self, px: &[Rgb], w: usize, h: usize) -> Vec<f32> {
        self.spatial_matte(px, w, h).into_iter().map(|m| self.finish(m as f64) as f32).collect()
    }
}

impl Matte {
    /// Whether the qualifier needs neighbours (denoise, shrink, grow, blur): it then runs as matte stages.
    pub fn spatial(&self) -> bool {
        self.qualify.as_ref().is_some_and(Qualify::spatial)
    }

    /// Channels of the matte image this matte takes: one for a spatial qualifier, one for its windows.
    pub fn channels(&self) -> usize {
        self.spatial() as usize + !self.windows.is_empty() as usize
    }

    /// The coverage of a pixel when the qualifier needs no neighbours (or `key` is its already filtered key) and the windows
    /// are not given: `finish`, then the matte's own invert.
    pub fn coverage_of(&self, key: f64) -> f64 {
        self.coverage_with(key, 1.0)
    }

    /// The coverage from the qualifier's key and the windows' combined coverage `win` (1 with no windows): the qualifier
    /// (clean, invert) times the windows (an intersect), then the matte's own invert.
    pub fn coverage_with(&self, key: f64, win: f64) -> f64 {
        let m = self.qualify.as_ref().map_or(key, |q| q.finish(key)) * win;
        if self.invert { 1.0 - m } else { m }
    }

    /// The per-pixel coverage from a colour (no neighbours: a spatial finesse is not applied; `Matte::coverage_image` does).
    pub fn coverage(&self, acescg: [f64; 3]) -> f64 {
        self.coverage_of(self.qualify.as_ref().map_or(1.0, |q| q.key(acescg)))
    }

    /// The whole coverage image of the matte on `px` (ACEScg, `w × h`): the qualifier's, times the windows', dithered for an
    /// 8-bit output (window.rs).
    pub fn coverage_image(&self, px: &[Rgb], w: usize, h: usize) -> Vec<f32> {
        let win = (!self.windows.is_empty()).then(|| super::window::coverage_image(&self.windows, w, h, super::window_sksl::DITHER_8BIT));
        let key = self.qualify.as_ref().map_or_else(|| vec![1.0; w * h], |q| q.spatial_matte(px, w, h));
        key.iter().enumerate().map(|(i, k)| self.coverage_with(*k as f64, win.as_ref().map_or(1.0, |v| v[i] as f64)) as f32).collect()
    }

    /// The uniform slots a matted layer takes after its mix ([`MATTE_SLOTS`]): the key's 11, clean black, clean
    /// white, the qualifier's invert and the matte's invert (1 or 0).
    pub fn slots(&self) -> [f32; MATTE_SLOTS] {
        let q = self.qualify.clone().unwrap_or_default();
        let k = q.key_slots();
        let c = q.clean.unwrap_or([0.0, 1.0]);
        let mut s = [0.0; MATTE_SLOTS];
        s[..11].copy_from_slice(&k);
        s[11] = c[0];
        s[12] = c[1];
        s[13] = q.invert as u8 as f32;
        s[14] = self.invert as u8 as f32;
        s
    }
}

/// A bilateral filter on the matte (module doc); taps outside the picture do not count.
fn denoise(m: &[f32], w: usize, h: usize, radius: f32) -> Vec<f32> {
    let step = radius / DENOISE_TAPS as f32;
    let off = |i: i32| (i as f32 * step + 0.5).floor() as i32;
    let mut out = vec![0.0; m.len()];
    for y in 0..h as i32 {
        for x in 0..w as i32 {
            let c = m[y as usize * w + x as usize] as f64;
            let (mut acc, mut wsum) = (0.0, 0.0);
            for j in -DENOISE_TAPS..=DENOISE_TAPS {
                for i in -DENOISE_TAPS..=DENOISE_TAPS {
                    let (sx, sy) = (x + off(i), y + off(j));
                    if sx < 0 || sy < 0 || sx >= w as i32 || sy >= h as i32 {
                        continue;
                    }
                    let v = m[sy as usize * w + sx as usize] as f64;
                    let ws = (-((i * i + j * j) as f64) / 8.0).exp();
                    let wr = (-((v - c) * (v - c)) / (2.0 * DENOISE_RANGE * DENOISE_RANGE)).exp();
                    acc += ws * wr * v;
                    wsum += ws * wr;
                }
            }
            out[y as usize * w + x as usize] = (acc / wsum) as f32;
        }
    }
    out
}

/// An erode or dilate (`dilate`) of a one-channel matte over a disc of `r` px: the comp's `matteMorph` twin (comp/morph.rs),
/// so the qualifier's shrink / grow is round like the comp's (a square window stamps blocks along a soft matte's contour).
fn morph(m: &[f32], w: usize, h: usize, r: f32, dilate: bool) -> Vec<f32> {
    let px: Vec<[f32; 4]> = m.iter().map(|&v| [v, v, v, 1.0]).collect();
    crate::comp::morph::morph(&px, w, h, r, !dilate).into_iter().map(|p| p[0]).collect()
}

/// A separable Gaussian of σ `sigma` px (kernel to 3σ), the weights renormalised at the borders.
fn blur(m: &[f32], w: usize, h: usize, sigma: f64) -> Vec<f32> {
    let r = (sigma * 3.0).ceil().max(1.0) as i32;
    let k: Vec<f64> = (-r..=r).map(|d| (-((d * d) as f64) / (2.0 * sigma * sigma)).exp()).collect();
    let pass = |src: &[f32], horizontal: bool| {
        let mut out = vec![0.0f32; src.len()];
        for y in 0..h {
            for x in 0..w {
                let (mut acc, mut ws) = (0.0, 0.0);
                for (n, kv) in k.iter().enumerate() {
                    let d = n as i32 - r;
                    let (sx, sy) = if horizontal { (x as i32 + d, y as i32) } else { (x as i32, y as i32 + d) };
                    if sx < 0 || sy < 0 || sx >= w as i32 || sy >= h as i32 {
                        continue;
                    }
                    acc += kv * src[sy as usize * w + sx as usize] as f64;
                    ws += kv;
                }
                out[y * w + x] = (acc / ws) as f32;
            }
        }
        out
    };
    pass(&pass(m, true), false)
}

// ── SkSL ────────────────────────────────────────────────────────────────────────────────────────────

/// The SkSL of the qualifier's per-pixel maths (the twin of `rise`, `fall`, `band`, `hue_cov`, `finish`): needs hsl.rs's
/// `hslOf`.
pub(super) fn sksl_helpers() -> &'static str {
    "float qRise(float x, float a, float b) { return b > a ? smoothstep(a, b, x) : (x >= b ? 1.0 : 0.0); }\n\
     float qFall(float x, float a, float b) { return b > a ? 1.0 - smoothstep(a, b, x) : (x <= a ? 1.0 : 0.0); }\n\
     float qBand(float x, float lo, float hi, float sl, float sh) { return qRise(x, lo - sl, lo) * qFall(x, hi, hi + sh); }\n\
     float qHue(float h, float c, float w, float s) { float d = abs(mod(h * 360.0 - c + 180.0, 360.0) - 180.0); return qFall(d, w * 0.5, w * 0.5 + s); }\n\
     float qFinish(float m, float cb, float cw, float inv) { m = clamp((m - cb) / max(cw - cb, 1e-6), 0.0, 1.0); return inv > 0.5 ? 1.0 - m : m; }\n"
}

impl Qualify {
    /// The key as an SkSL expression over the ACEScct-encoded colour `t` (a `float3`) and the 11 slots `q(k)`.
    pub(super) fn key_expr(&self, t: &str, q: &dyn Fn(usize) -> String) -> String {
        let mut terms = vec![];
        let hv = format!("hslOf({t})");
        if self.hue.is_some() {
            terms.push(format!("qHue({hv}.x, {}, {}, {})", q(0), q(1), q(2)));
        }
        if self.sat.is_some() {
            terms.push(format!("qBand({hv}.y, {}, {}, {}, {})", q(3), q(4), q(5), q(6)));
        }
        if self.lum.is_some() {
            terms.push(format!("qBand({hv}.z, {}, {}, {}, {})", q(7), q(8), q(9), q(10)));
        }
        if terms.is_empty() { "1.0".into() } else { terms.join(" * ") }
    }
}

/// The denoise stage as an SkSL shader (`uniform shader src`: the key image, one channel set; `radius` px).
pub(super) fn denoise_sksl() -> String {
    format!(
        "uniform shader src;\nuniform float radius;\nhalf4 main(float2 p) {{\n    half4 c0 = src.eval(p); float c = float(c0.r + c0.g + c0.b);\n    \
         float step = radius / {taps}.0; float acc = 0.0; float wsum = 0.0; half4 acc4 = half4(0.0); \n    \
         for (int j = -{taps}; j <= {taps}; j++) {{\n        for (int i = -{taps}; i <= {taps}; i++) {{\n            \
         float2 o = floor(float2(float(i), float(j)) * step + 0.5);\n            half4 s = src.eval(p + o);\n            \
         float v = float(s.r + s.g + s.b);\n            float ws = exp(-float(i * i + j * j) / 8.0) * float(s.a);\n            \
         float wr = exp(-((v - c) * (v - c)) / {rr}) * ws;\n            acc4 += s * half(wr); wsum += wr;\n        }}\n    }}\n    \
         return acc4 / half(max(wsum, 1e-6));\n}}\n",
        taps = DENOISE_TAPS,
        rr = crate::view::sksl::f((2.0 * DENOISE_RANGE * DENOISE_RANGE) as f32),
    )
}
