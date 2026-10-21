//! The one grade (docs/phase0/COLOUR_PIPELINE.md §2.5, C7; docs/phase1/GRADING.md §1, §2, §4.1): an ordered list of
//! operations on scene-linear ACEScg, each in the space it is defined in, plus a mix over the ungraded light. A
//! layer (`Op::Layer`) is an operation holding its own list, run on a branch and blended back (table below). One
//! definition, three evaluations: the CPU reference (`apply`, apply.rs), the compositor's SkSL colour filter
//! (`sksl`, sksl.rs, generated from the same constants) and a baked `.cube` (`bake`, bake.rs).
//!
//! In ACEScct, "luma" `L` is always Rec.709 luma `0.2126 r + 0.7152 g + 0.0722 b` of the codes, and hue / sat are
//! the one measurement of hsl.rs (`hsl`, shared with the G3 qualifier): hue = the angle about the grey axis,
//! `atan2(√3/2 · (g − b), r − (g + b) / 2)` as 0 … 1 (0 red, 1/6 yellow, 1/3 green, 1/2 cyan, 2/3 blue, 5/6
//! magenta; 0 for a grey); sat = HSV's `(max − min) / max`, clamped to 0 … 1 (0 when max ≤ 0).
//!
//! | op | space | maths |
//! |---|---|---|
//! | `Exposure(stops)` | ACEScg linear | `x · 2^stops` |
//! | `WhiteBalance { kelvin, tint }` | ACEScg linear | CAT02 from the light's white (Planckian `kelvin`, Krystek 1985, offset `tint / 3000` in CIE 1960 Duv, + = greener light) to the 6500 K Planckian white: + kelvin warms the picture, + tint makes it magenta (Lightroom's sense). 6500 / 0 is the identity. |
//! | `Offset(rgb)` | ACEScg linear | `x + rgb` |
//! | `LiftGammaGain(Lgg)` | ACEScct | `t = (v − black) / (white − black)`; `t' = lift + (gain − lift) · t^(1/gamma)` (sign-mirrored power); `v' = black + t' · (white − black)`; lift = rgb + master, gamma and gain = rgb × master |
//! | `Contrast { contrast, pivot }` | ACEScct | `(v − pivot) · contrast + pivot` (pivot an ACEScct code; 18 % grey = `grey_pivot()`) |
//! | `Saturation { saturation, luma }` | ACEScct | `L + s · (v − L)`, `L = w · v`; `w` = AP1 luminance (default) or Rec.709 luma |
//! | `Hue(degrees)` | ACEScct | rotation about the grey axis (+ = red → yellow → green), then the grey shift that restores the luma: `p = v − mean(v)`, `r = mean(v) + cos θ · p + sin θ · (u × p)` (u = (1, 1, 1)/√3), `v' = r + (L(v) − L(r))`. Keeps luma, hue-plane chroma and greys; hue moves by exactly θ; 360° is the identity. |
//! | `Boost(amount)` | ACEScct | Resolve's colour boost, saturation weighted to the less saturated pixels: `L + (1 + amount · (1 − sat)) · (v − L)`. 0 is the identity; greys and fully saturated pixels do not move. |
//! | `OffsetCct(rgbm)` | ACEScct | Resolve's Offset wheel: `v + rgb + m` (codes) |
//! | `Log(LogWheels)` | ACEScct | Resolve's log wheels, offsets in three luma ranges: `v + S · shadow + M · mid + H · high` (each wheel rgb + m), with `S = 1 − smoothstep(e − k, e + k, L)`, `H = smoothstep(h − k, h + k, L)`, `M = max(1 − S − H, 0)` (e = shadowEnd, h = highStart, k = softness floored at 1e-6). S + M + H = 1 while the two transitions do not overlap (e + k ≤ h − k), so three equal wheels are one Offset. Defaults e 0.333, h 0.55 (Resolve's Low / High Range defaults, from its manual), k 0.08 (ours: Resolve's mask shape is unpublished). |
//! | `Curves(Curves)` | ACEScct | master on every channel, then r, g, b: tables sampled evenly over code 0 … 1, linear between samples, slope 1 beyond the ends |
//! | `HslCurves(HslCurves)` | ACEScct | Resolve's hue / lum / sat curves, all read off the input pixel's (hue, sat, L): `shift = hueHue(hue)` degrees, `ks = hueSat(hue) · lumSat(L) · satSat(sat)`, `kl = (1 + (hueLum(hue) − 1) · sat) · satLum(sat)` (hue vs lum weighted by sat: a grey has no hue); then `v = Hue(shift)(v)`, `v = L + ks · (v − L)`, `v = v + (kl − 1) · L`. Each table: N samples evenly over x = 0 … 1 inclusive (hue, L code, sat), linear between, held at the ends; the hue tables wrap (first and last samples are 0° and 360°, and must be equal). hueHue's values are degrees (0 = none), the others multipliers (1 = none). |
//! | `Lut(LutNode)` | its own | ACEScg → `input` space, the LUT (clamped to its domain), `output` space → ACEScg |
//! | `Layer(Layer)` | ACEScg linear | `base` = the running result (`from: Previous`) or the stack's input (`Input`); `g` = the layer's operations on `base`; `w = mix · coverage` (the matte's coverage: 1 with no matte; see Mattes); then per channel, with `cur` the running result: over `cur + w · (g − cur)`; add `cur + w · g`; multiply `cur · (1 + w · (g − 1))`; screen `cur + w · (S(cur, g) − cur)`, `S(a, b) = a + b − a · b` when a, b ≤ 1, else `max(a, b)` (screen on scene light: never darker than either input, continuous at 1). |
//!
//! Consecutive ACEScct operations share one encode / decode (a layer starts and ends in linear). `mix` blends the
//! graded light over the ungraded light in ACEScg: `src + mix · (graded − src)`.
//!
//! Resolve's Lum Mix has no operation: it sets how far Resolve's Y-only master controls keep saturation, and our
//! master controls are plain RGB maths (lum mix 0 in Resolve's terms), so the spec accepts `luma_mix` and it is the
//! identity (spec.rs).
//!
//! # Mattes and the matte seam
//!
//! A layer's matte (`Matte`) gives a coverage 0 … 1 per pixel; the layer's weight is `mix · coverage` (the table's
//! `Layer` row). G3 builds the HSL qualifier (matte.rs: hue / sat / lum ranges, clean, invert, and the spatial finesse
//! denoise, shrink, grow, blur); G4 adds window shapes to the same matte. The qualifier keys the stack's INPUT (the
//! picture as it enters the grade), so a matte never moves when an earlier layer changes.
//!
//! Where the coverage comes from depends on what the matte needs:
//! - **Per pixel** (ranges, clean, invert; no neighbours): inside the grade's one colour filter. The generated code
//!   (sksl.rs `coverage`) measures `src` in ACEScct, evaluates the ranges and declares `cov{N}`; uniform slots after
//!   the layer's mix (`Matte::slots`). The CPU twin is `Matte::coverage` (apply.rs `matte_coverage`).
//! - **Spatial** (`Qualify::spatial`: denoise, shrink, grow or blur): a colour filter has no neighbours, so the
//!   matte becomes an image. The grade's program turns into a runtime BLENDER `half4 main(half4 m, half4 c)` (`c` the
//!   picture, `m` the matte image) and `Grade::matte_stages` lists, per spatial matte, the stages that make its channel
//!   of `m`: a key colour filter (the raw key, in channel 0 / 1 / 2, alpha 1), a bilateral denoise shader
//!   (`DENOISE_TAPS`, `DENOISE_RANGE`), erode and dilate (feMorphology), a Gaussian blur (feGaussianBlur) and a
//!   renormalising colour filter (blur and erode leave alpha at the picture's border; dividing it out keeps the
//!   matte from fading there). Stages of different mattes are added into one image (feComposite arithmetic), up to
//!   `MAX_SPATIAL` (3, one channel each). The blender reads its channel, applies clean and invert per pixel, and grades.
//!   The host chains the stages as SVG filter primitives (src/engine/video/gradeProgram.ts `specStep`); the
//!   compositor runs them as Skia image filters (native/rostrum-motion: `feshader in2`, anyrender_skia
//!   `runtime_blender_filter`). `Grade::apply_image` and `Qualify::coverage_image` are the CPU reference of the chain.
//! - **Windows** (G4, window.rs; GPU twin window_sksl.rs) need pixel coordinates, which neither a colour filter nor a blender
//!   has: a layer's windows are one shader stage (`MatteStage::shader`) that draws all of them, combined and dithered, into one
//!   more channel of the same matte image (a plain runtime shader filling the frame's box, anyrender_skia `runtime_window_filter`).
//!   No blur or norm filters run on it (its edges are analytic). The blender reads that channel next to the qualifier's: coverage
//!   = qualifier (clean, invert) × windows, then the matte's own invert. A layer takes one channel for a spatial qualifier and
//!   one for its windows; the grade has at most `MAX_SPATIAL` (3) channels in all (`Grade::matte_channels`).
//!
//! `Grade::sksl_matte_view(id)` returns the program that shows layer `id`'s coverage as a grey picture (snap --matte).
mod apply;
mod bake;
pub mod fit;
mod hsl;
mod lut_sksl;
mod matte;
mod sksl;
mod spec;
mod white;
mod window;
mod window_sksl;
mod window_spec;

pub use hsl::{Hsl, LUMA_709, hsl, hue_rotate, table};
pub use lut_sksl::LutImage;
pub use matte::{DENOISE_RANGE, DENOISE_TAPS, HueRange, MATTE_SLOTS, MAX_SPATIAL, Matte, Qualify, Range};
pub use sksl::MatteStage;
pub use white::{NEUTRAL_KELVIN, TINT_SCALE, wb_matrix, white_xy};
pub use window::{BEZIER_STEPS, MAX_POINTS, MAX_WINDOWS, Mode, Node, Shape, Window, coverage_image as window_coverage};
pub use window_sksl::DITHER_8BIT;

use crate::convert::{Transform, convert};
use crate::{Curve, Interp, Lut};

/// ACEScct code of 18 % grey (the contrast pivot most grades want).
pub fn grey_pivot() -> f32 {
    Curve::AcesCct.encode(0.18)
}

/// The weights saturation takes its grey from.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Luma {
    /// AP1 luminance (ACEScg's Y row, from the crate's primaries): the grey of the light itself.
    Ap1,
    /// Rec.709 luma 0.2126 / 0.7152 / 0.0722 (OCIO's GradingPrimary and Resolve use these on any space).
    Rec709,
}

impl Luma {
    pub fn weights(self) -> [f64; 3] {
        match self {
            Luma::Ap1 => crate::Gamut::get("acescg").expect("acescg").to_xyz()[1],
            Luma::Rec709 => LUMA_709,
        }
    }
}

/// Lift / gamma / gain, each `[r, g, b, master]`, between the ACEScct codes `black` and `white`.
#[derive(Clone, Debug, PartialEq)]
pub struct Lgg {
    pub lift: [f32; 4],
    pub gamma: [f32; 4],
    pub gain: [f32; 4],
    pub black: f32,
    pub white: f32,
}

impl Default for Lgg {
    /// The identity, with black = ACEScct of linear 0 and white = ACEScct of linear 1.0.
    fn default() -> Lgg {
        Lgg { lift: [0.0; 4], gamma: [1.0; 4], gain: [1.0; 4], black: Curve::AcesCct.encode(0.0), white: Curve::AcesCct.encode(1.0) }
    }
}

/// Curve tables (2 … 256 samples each, evenly over ACEScct code 0 … 1; monotone is the caller's business).
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Curves {
    pub master: Option<Vec<f32>>,
    pub r: Option<Vec<f32>>,
    pub g: Option<Vec<f32>>,
    pub b: Option<Vec<f32>>,
}

impl Curves {
    /// (channel mask: `None` = all three, `Some(c)` = channel c; table), in the order they apply.
    pub fn tables(&self) -> impl Iterator<Item = (Option<usize>, &Vec<f32>)> {
        let own = [&self.r, &self.g, &self.b].into_iter().enumerate().filter_map(|(c, t)| t.as_ref().map(|t| (Some(c), t)));
        self.master.as_ref().map(|t| (None, t)).into_iter().chain(own)
    }
}

/// Resolve's log wheels (`[r, g, b, master]` offsets in ACEScct codes) and their luma ranges (module doc).
#[derive(Clone, Debug, PartialEq)]
pub struct LogWheels {
    pub shadow: [f32; 4],
    pub mid: [f32; 4],
    pub high: [f32; 4],
    /// ACEScct luma where the shadow mask is half way down.
    pub shadow_end: f32,
    /// ACEScct luma where the highlight mask is half way up.
    pub high_start: f32,
    /// Half width of each transition (ACEScct code).
    pub softness: f32,
}

/// Resolve's Log mode Low Range default (DaVinci Resolve manual, Log mode controls).
pub const LOG_SHADOW_END: f32 = 0.333;
/// Resolve's Log mode High Range default (same source).
pub const LOG_HIGH_START: f32 = 0.55;
/// Our transition half width (Resolve does not publish its mask shape).
pub const LOG_SOFTNESS: f32 = 0.08;

impl Default for LogWheels {
    fn default() -> LogWheels {
        LogWheels { shadow: [0.0; 4], mid: [0.0; 4], high: [0.0; 4], shadow_end: LOG_SHADOW_END, high_start: LOG_HIGH_START, softness: LOG_SOFTNESS }
    }
}

impl LogWheels {
    /// The (shadow, mid, high) masks at ACEScct luma `l`.
    pub fn masks(&self, l: f64) -> [f64; 3] {
        let k = (self.softness as f64).max(1e-6);
        let (e, h) = (self.shadow_end as f64, self.high_start as f64);
        let s = 1.0 - smoothstep(e - k, e + k, l);
        let hi = smoothstep(h - k, h + k, l);
        [s, (1.0 - s - hi).max(0.0), hi]
    }
}

/// GLSL's smoothstep.
pub(crate) fn smoothstep(a: f64, b: f64, x: f64) -> f64 {
    let t = ((x - a) / (b - a)).clamp(0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}

/// Which of the hue / lum / sat curves a table is.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum HslCurve {
    HueHue,
    HueSat,
    HueLum,
    LumSat,
    SatSat,
    SatLum,
}

impl HslCurve {
    pub const ALL: [HslCurve; 6] = [HslCurve::HueHue, HslCurve::HueSat, HslCurve::HueLum, HslCurve::LumSat, HslCurve::SatSat, HslCurve::SatLum];
    /// Keyed by hue (the table wraps).
    pub fn periodic(self) -> bool {
        matches!(self, HslCurve::HueHue | HslCurve::HueSat | HslCurve::HueLum)
    }
    /// The value meaning "no change": 0 degrees for hue vs hue, multiplier 1 for the rest.
    pub fn neutral(self) -> f32 {
        if self == HslCurve::HueHue { 0.0 } else { 1.0 }
    }
    /// The spec's field name.
    pub fn key(self) -> &'static str {
        ["hueHue", "hueSat", "hueLum", "lumSat", "satSat", "satLum"][self as usize]
    }
}

/// The hue / lum / sat curve tables (2 … 4096 samples each, evenly over 0 … 1 inclusive; module doc).
#[derive(Clone, Debug, Default, PartialEq)]
pub struct HslCurves {
    pub hue_hue: Option<Vec<f32>>,
    pub hue_sat: Option<Vec<f32>>,
    pub hue_lum: Option<Vec<f32>>,
    pub lum_sat: Option<Vec<f32>>,
    pub sat_sat: Option<Vec<f32>>,
    pub sat_lum: Option<Vec<f32>>,
}

impl HslCurves {
    pub fn get(&self, c: HslCurve) -> Option<&Vec<f32>> {
        [&self.hue_hue, &self.hue_sat, &self.hue_lum, &self.lum_sat, &self.sat_sat, &self.sat_lum][c as usize].as_ref()
    }
    pub fn slot(&mut self, c: HslCurve) -> &mut Option<Vec<f32>> {
        match c {
            HslCurve::HueHue => &mut self.hue_hue,
            HslCurve::HueSat => &mut self.hue_sat,
            HslCurve::HueLum => &mut self.hue_lum,
            HslCurve::LumSat => &mut self.lum_sat,
            HslCurve::SatSat => &mut self.sat_sat,
            HslCurve::SatLum => &mut self.sat_lum,
        }
    }
    /// The tables present, in `HslCurve::ALL` order (the rows of the GPU image).
    pub fn tables(&self) -> impl Iterator<Item = (HslCurve, &Vec<f32>)> {
        HslCurve::ALL.into_iter().filter_map(|c| self.get(c).map(|t| (c, t)))
    }
}

/// A LUT with the spaces it expects in and gives out (rostrum-color space ids, e.g. `rec709_display` for a
/// creative LUT, `slog3_sgamut3cine` → `rec709_display` for a camera LUT).
#[derive(Clone, Debug, PartialEq)]
pub struct LutNode {
    pub lut: Lut,
    /// 3D tables only (1D tables are linear per channel).
    pub interp: Interp,
    pub input: String,
    pub output: String,
    to_in: Transform,
    from_out: Transform,
}

impl LutNode {
    pub fn new(lut: Lut, interp: Interp, input: &str, output: &str) -> Result<LutNode, String> {
        let (to_in, from_out) = (convert("acescg", input)?, convert(output, "acescg")?);
        Ok(LutNode { lut, interp, input: input.into(), output: output.into(), to_in, from_out })
    }
}

/// Where a layer's grade starts from.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum Source {
    /// The running result (a serial node).
    #[default]
    Previous,
    /// The stack's input (a parallel branch).
    Input,
}

/// How a layer's graded light lands on the running result (module doc).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum Combine {
    #[default]
    Over,
    Add,
    Multiply,
    Screen,
}

impl Combine {
    /// One channel: the running result `cur`, the layer's light `g`, the weight `w` (mix · coverage).
    pub fn blend(self, cur: f64, g: f64, w: f64) -> f64 {
        match self {
            Combine::Over => cur + w * (g - cur),
            Combine::Add => cur + w * g,
            Combine::Multiply => cur * (1.0 + w * (g - 1.0)),
            Combine::Screen => cur + w * (screen(cur, g) - cur),
        }
    }
}

/// Screen on scene light: `a + b − a · b` on 0 … 1, the brighter of the two above.
pub fn screen(a: f64, b: f64) -> f64 {
    if a <= 1.0 && b <= 1.0 { a + b - a * b } else { a.max(b) }
}

/// One correction of a layered grade (module doc).
#[derive(Clone, Debug, PartialEq)]
pub struct Layer {
    pub id: String,
    pub ops: Vec<Op>,
    /// 0 … 1: the layer's weight in its combine.
    pub mix: f32,
    pub from: Source,
    pub combine: Combine,
    pub matte: Option<Matte>,
}

impl Layer {
    pub fn new(ops: Vec<Op>) -> Layer {
        Layer { id: String::new(), ops, mix: 1.0, from: Source::Previous, combine: Combine::Over, matte: None }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum Op {
    Exposure(f32),
    WhiteBalance { kelvin: f32, tint: f32 },
    Offset([f32; 3]),
    LiftGammaGain(Lgg),
    Contrast { contrast: f32, pivot: f32 },
    Saturation { saturation: f32, luma: Luma },
    Hue(f32),
    Boost(f32),
    OffsetCct([f32; 4]),
    Log(LogWheels),
    Curves(Curves),
    HslCurves(HslCurves),
    Lut(Box<LutNode>),
    Layer(Box<Layer>),
}

/// Where an operation runs: linear ACEScg, ACEScct, or a LUT node (which converts itself from linear).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Section {
    Linear,
    Cct,
}

impl Op {
    pub fn section(&self) -> Section {
        match self {
            Op::Exposure(_) | Op::WhiteBalance { .. } | Op::Offset(_) | Op::Lut(_) | Op::Layer(_) => Section::Linear,
            _ => Section::Cct,
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Grade {
    pub ops: Vec<Op>,
    /// 0 … 1: how much of the grade shows over the ungraded light.
    pub mix: f32,
    /// The values are measurements, not light (a depth, normal or velocity pass): the ACEScct operations work on the plain
    /// numbers (no log encoding; lift / gamma / gain between 0 and 1, contrast about 0.18), as Nuke's Grade does on any channel.
    pub data: bool,
}

impl Grade {
    pub fn new(ops: Vec<Op>) -> Grade {
        Grade { ops, mix: 1.0, data: false }
    }

    /// Loud errors for what the GPU form cannot hold (the CPU form never fails) and for what is not built yet.
    pub fn check(&self) -> Result<(), String> {
        let mut err = Ok(());
        walk(&self.ops, &mut |op| {
            if err.is_ok() {
                err = check_op(op);
            }
        });
        err?;
        match self.matte_channels() {
            n if n > MAX_SPATIAL => Err(format!("a grade has at most {MAX_SPATIAL} matte channels: a layer whose qualifier blurs, shrinks, grows or denoises takes one, and a layer with windows takes one (this grade needs {n})")),
            _ => Ok(()),
        }
    }
}

/// Every operation, depth first (a layer, then its operations): the order of uniform slots and child images.
pub(crate) fn walk<'a>(ops: &'a [Op], f: &mut impl FnMut(&'a Op)) {
    for o in ops {
        f(o);
        if let Op::Layer(l) = o {
            walk(&l.ops, f);
        }
    }
}

fn check_op(op: &Op) -> Result<(), String> {
    match op {
        Op::Curves(c) => match c.tables().find(|(_, t)| !(2..=256).contains(&t.len())) {
            Some((_, t)) => Err(format!("a grade curve has 2 … 256 samples; got {}", t.len())),
            None => Ok(()),
        },
        Op::HslCurves(c) => c.tables().try_for_each(|(k, t)| {
            if !(2..=4096).contains(&t.len()) {
                return Err(format!("a grade `{}` curve has 2 … 4096 samples; got {}", k.key(), t.len()));
            }
            let (a, b) = (t[0], t[t.len() - 1]);
            if k.periodic() && (a - b).abs() > 1e-4 * a.abs().max(1.0) {
                return Err(format!("a grade `{}` curve wraps: its first and last samples (hue 0° and 360°) must be equal; got {a} and {b}", k.key()));
            }
            Ok(())
        }),
        Op::Layer(l) => match &l.matte {
            Some(m) => check_matte(&l.id, m),
            None => Ok(()),
        },
        _ => Ok(()),
    }
}

fn check_matte(id: &str, m: &Matte) -> Result<(), String> {
    let at = format!("grade layer `{id}` matte");
    if m.windows.len() > MAX_WINDOWS {
        return Err(format!("{at}: at most {MAX_WINDOWS} windows; got {}", m.windows.len()));
    }
    for (i, w) in m.windows.iter().enumerate() {
        w.check(&format!("{at} window {}", i + 1))?;
    }
    if m.windows.first().is_some_and(|w| w.mode != Mode::Add) {
        return Err(format!("{at}: the first window must be an `add` (subtract and intersect take away from what is there)"));
    }
    let Some(q) = &m.qualify else {
        return if m.windows.is_empty() { Err(format!("{at}: has neither a qualifier nor windows")) } else { Ok(()) };
    };
    if !q.has_key() {
        return Err(format!("{at}: the qualifier has no range: give `hue`, `sat` or `lum`"));
    }
    let fin = |v: f32| v.is_finite();
    if let Some(h) = &q.hue {
        if !(fin(h.centre) && (0.0..=360.0).contains(&h.width) && h.soft >= 0.0 && fin(h.soft)) {
            return Err(format!("{at}: hue is centre (degrees), width 0 … 360 and soft ≥ 0 degrees; got centre {}, width {}, soft {}", h.centre, h.width, h.soft));
        }
    }
    for (name, r) in [("sat", &q.sat), ("lum", &q.lum)] {
        if let Some(r) = r {
            if !(fin(r.lo) && fin(r.hi) && r.lo <= r.hi && r.soft_lo >= 0.0 && r.soft_hi >= 0.0 && fin(r.soft_lo) && fin(r.soft_hi)) {
                return Err(format!("{at}: {name} is lo ≤ hi with softLo, softHi ≥ 0; got lo {}, hi {}, softLo {}, softHi {}", r.lo, r.hi, r.soft_lo, r.soft_hi));
            }
        }
    }
    if let Some([b, w]) = q.clean {
        if !(fin(b) && fin(w) && b < w) {
            return Err(format!("{at}: clean needs black < white; got black {b}, white {w}"));
        }
    }
    for (name, v, max) in [("denoise", q.denoise, 32.0), ("shrink", q.shrink, 64.0), ("grow", q.grow, 64.0), ("blur", q.blur, 200.0)] {
        if !(0.0..=max).contains(&v) {
            return Err(format!("{at}: {name} is 0 … {max} px; got {v}"));
        }
    }
    Ok(())
}

impl Grade {
    /// The matted layers, depth first (a layer, then its operations'): the order of the matte slots.
    pub fn mattes(&self) -> Vec<(&Layer, &Matte)> {
        let mut out = vec![];
        walk(&self.ops, &mut |op| {
            if let Op::Layer(l) = op {
                if let Some(m) = &l.matte {
                    out.push((&**l, m));
                }
            }
        });
        out
    }

    /// How many channels of the matte image the mattes take (at most [`MAX_SPATIAL`]): a spatial qualifier and a layer's windows
    /// run as matte stages, one channel each.
    pub fn matte_channels(&self) -> usize {
        self.mattes().iter().map(|(_, m)| m.channels()).sum()
    }

    /// The (qualifier, windows) channel of each matted layer, in `mattes()` order: qualifier first, then windows.
    pub(crate) fn channel_plan(&self) -> Vec<(Option<usize>, Option<usize>)> {
        let mut n = 0;
        let mut next = |on: bool| on.then(|| { n += 1; n - 1 });
        self.mattes().iter().map(|(_, m)| (next(m.spatial()), next(!m.windows.is_empty()))).collect()
    }
}
