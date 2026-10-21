//! The CPU reference: f64 maths per pixel (the LUT tables themselves are f32), one ACEScct encode / decode per
//! run of ACEScct operations. Per-grade constants (white-balance matrices) are prepared once per call.
use super::hsl::{self, hsl, hue_rotate};
use super::{Grade, HslCurve, HslCurves, Layer, Lgg, LogWheels, LutNode, Op, Section, Source, white};
use crate::matrix::{self, Mat3};
use crate::{Curve, Lut, Rgb};

type V = [f64; 3];

/// Sign-mirrored power (OCIO's convention for gamma on negatives).
pub(crate) fn spow(x: f64, p: f64) -> f64 {
    if x < 0.0 { -(-x).powf(p) } else { x.powf(p) }
}

fn lgg(v: V, g: &Lgg) -> V {
    let (b, w) = (g.black as f64, g.white as f64);
    std::array::from_fn(|c| {
        let lift = (g.lift[c] + g.lift[3]) as f64;
        let gamma = ((g.gamma[c] * g.gamma[3]) as f64).max(0.01);
        let gain = (g.gain[c] * g.gain[3]) as f64;
        let t = (v[c] - b) / (w - b);
        b + (lift + (gain - lift) * spow(t, 1.0 / gamma)) * (w - b)
    })
}

/// A curve table at code v: linear between samples over 0 … 1, slope 1 beyond the ends.
pub(crate) fn curve(t: &[f32], v: f64) -> f64 {
    if t.len() < 2 {
        return v;
    }
    let c = v.clamp(0.0, 1.0);
    let x = c * (t.len() - 1) as f64;
    let i = (x.floor() as usize).min(t.len() - 2);
    let (a, b) = (t[i] as f64, t[i + 1] as f64);
    a + (b - a) * (x - i as f64) + (v - c)
}

fn lut(v: V, n: &LutNode) -> V {
    let x = n.to_in.apply(v.map(|c| c as f32));
    let y = match &n.lut {
        Lut::D1(l) => l.apply(x),
        Lut::D3(l) => l.apply(x, n.interp),
    };
    n.from_out.apply(y).map(f64::from)
}

/// Chroma scaled by `k` about luma `l`.
fn chroma(v: V, l: f64, k: f64) -> V {
    v.map(|c| l + k * (c - l))
}

fn log_wheels(v: V, w: &LogWheels) -> V {
    let m = w.masks(hsl::luma(v));
    let d = |wh: &[f32; 4], c: usize| (wh[c] + wh[3]) as f64;
    std::array::from_fn(|c| v[c] + m[0] * d(&w.shadow, c) + m[1] * d(&w.mid, c) + m[2] * d(&w.high, c))
}

fn hsl_curves(v: V, c: &HslCurves) -> V {
    let p = hsl(v);
    let at = |k: HslCurve, x: f64| c.get(k).map_or(k.neutral() as f64, |t| hsl::table(t, x));
    let ks = at(HslCurve::HueSat, p.hue) * at(HslCurve::LumSat, p.luma) * at(HslCurve::SatSat, p.sat);
    let kl = (1.0 + (at(HslCurve::HueLum, p.hue) - 1.0) * p.sat) * at(HslCurve::SatLum, p.sat);
    let v = if c.hue_hue.is_some() { hue_rotate(v, at(HslCurve::HueHue, p.hue)) } else { v };
    chroma(v, p.luma, ks).map(|x| x + (kl - 1.0) * p.luma)
}

/// What an operation needs prepared once per call.
enum Prep {
    None,
    Wb(Mat3),
    /// The layer's operations, and where its matte's images are in `Ctx::spatial`: the qualifier's filtered key, the windows' coverage.
    Layer(Vec<Prep>, (Option<usize>, Option<usize>)),
}

/// `images`: how many matte images the layers met so far take (the index of the next one).
fn prepare(ops: &[Op], images: &mut usize) -> Vec<Prep> {
    let mut out = vec![];
    for o in ops {
        out.push(match o {
            Op::WhiteBalance { kelvin, tint } => Prep::Wb(white::wb_matrix(*kelvin as f64, *tint as f64)),
            Op::Layer(l) => {
                let mut next = |on: bool| on.then(|| { *images += 1; *images - 1 });
                let idx = l.matte.as_ref().map_or((None, None), |m| (next(m.spatial()), next(!m.windows.is_empty())));
                Prep::Layer(prepare(&l.ops, images), idx)
            }
            _ => Prep::None,
        });
    }
    out
}

/// What a layer's matte reads: the stack's input and, at this pixel, its images (spatial qualifiers' filtered keys, windows' coverage).
struct Ctx<'a> {
    src: V,
    spatial: &'a [f64],
    /// `Grade::data`: no ACEScct encoding around the ACEScct operations.
    data: bool,
}

fn op(o: &Op, v: V, wb: Option<&Mat3>) -> V {
    match o {
        Op::Exposure(s) => v.map(|c| c * 2f64.powf(*s as f64)),
        Op::WhiteBalance { .. } => matrix::apply(wb.expect("prepared"), v),
        Op::Offset(o) => std::array::from_fn(|c| v[c] + o[c] as f64),
        Op::LiftGammaGain(g) => lgg(v, g),
        Op::Contrast { contrast, pivot } => v.map(|c| (c - *pivot as f64) * *contrast as f64 + *pivot as f64),
        Op::Saturation { saturation, luma } => {
            let w = luma.weights();
            let l = w[0] * v[0] + w[1] * v[1] + w[2] * v[2];
            v.map(|c| l + *saturation as f64 * (c - l))
        }
        Op::Hue(d) => hue_rotate(v, *d as f64),
        Op::Boost(a) => {
            let p = hsl(v);
            chroma(v, p.luma, 1.0 + *a as f64 * (1.0 - p.sat))
        }
        Op::OffsetCct(o) => std::array::from_fn(|c| v[c] + (o[c] + o[3]) as f64),
        Op::Log(w) => log_wheels(v, w),
        Op::Curves(cv) => {
            let mut v = v;
            for (ch, t) in cv.tables() {
                match ch {
                    None => v = v.map(|c| curve(t, c)),
                    Some(k) => v[k] = curve(t, v[k]),
                }
            }
            v
        }
        Op::HslCurves(c) => hsl_curves(v, c),
        Op::Lut(n) => lut(v, n),
        Op::Layer(_) => unreachable!("layers run in `ops`"),
    }
}

/// A run of operations from linear `v` back to linear (`ctx.src`: the stack's input, for `from: Input` layers and mattes).
fn ops(list: &[Op], prep: &[Prep], mut v: V, ctx: &Ctx) -> V {
    let mut cct = false;
    for (o, p) in list.iter().zip(prep) {
        let want = o.section() == Section::Cct && !ctx.data;
        if want != cct {
            v = v.map(|c| if want { Curve::AcesCct.encode64(c) } else { Curve::AcesCct.decode64(c) });
            cct = want;
        }
        v = match (o, p) {
            (Op::Layer(l), Prep::Layer(lp, idx)) => layer(l, lp, v, ctx, matte_coverage(l, *idx, ctx)),
            (o, Prep::Wb(m)) => op(o, v, Some(m)),
            (o, _) => op(o, v, None),
        };
    }
    if cct {
        v = v.map(|c| Curve::AcesCct.decode64(c));
    }
    v
}

/// The layer's matte coverage at this pixel: 1 with no matte; else the qualifier's key of the stack's input (or its
/// filtered key, when the matte is spatial and the image was given) through clean and invert (matte.rs).
fn matte_coverage(l: &Layer, at: (Option<usize>, Option<usize>), ctx: &Ctx) -> f64 {
    let Some(m) = &l.matte else { return 1.0 };
    let image = |i: Option<usize>| i.and_then(|i| ctx.spatial.get(i)).copied();
    let key = image(at.0).unwrap_or_else(|| m.qualify.as_ref().map_or(1.0, |q| q.key(ctx.src)));
    m.coverage_with(key, image(at.1).unwrap_or(1.0))
}

/// A layer onto the running result `cur`, weighted by its mix and `coverage`.
fn layer(l: &Layer, prep: &[Prep], cur: V, ctx: &Ctx, coverage: f64) -> V {
    let base = if l.from == Source::Input { ctx.src } else { cur };
    let g = ops(&l.ops, prep, base, ctx);
    let w = l.mix as f64 * coverage;
    std::array::from_fn(|c| l.combine.blend(cur[c], g[c], w))
}

impl Grade {
    fn run(&self, prep: &[Prep], cg: Rgb, spatial: &[f64]) -> Rgb {
        let src = cg.map(f64::from);
        let v = ops(&self.ops, prep, src, &Ctx { src, spatial, data: self.data });
        let m = self.mix as f64;
        std::array::from_fn(|c| (src[c] + m * (v[c] - src[c])) as f32)
    }

    /// One ACEScg colour (straight alpha) through the grade. A colour has no neighbours and no place: a matte's spatial finesse
    /// (denoise, shrink, grow, blur) and its windows are skipped here (a window covers everything); `apply_image` has them.
    pub fn apply(&self, acescg: Rgb) -> Rgb {
        self.run(&prepare(&self.ops, &mut 0), acescg, &[])
    }

    /// Every pixel, in place (per-pixel mattes only, as `apply`).
    pub fn apply_all(&self, px: &mut [Rgb]) {
        let prep = prepare(&self.ops, &mut 0);
        px.iter_mut().for_each(|p| *p = self.run(&prep, *p, &[]));
    }

    /// A `w × h` picture (ACEScg, straight alpha, row by row) through the grade, the mattes' spatial finesse included:
    /// the CPU reference of the compositor's matte stages.
    pub fn apply_image(&self, px: &mut [Rgb], w: usize, h: usize) {
        let prep = prepare(&self.ops, &mut 0);
        let mut filtered: Vec<Vec<f32>> = vec![];
        for (_, m) in self.mattes() {
            if m.spatial() {
                filtered.push(m.qualify.as_ref().expect("spatial").spatial_matte(px, w, h));
            }
            if !m.windows.is_empty() {
                filtered.push(super::window::coverage_image(&m.windows, w, h, super::window_sksl::DITHER_8BIT));
            }
        }
        let mut at = vec![0.0; filtered.len()];
        for (i, p) in px.iter_mut().enumerate() {
            at.iter_mut().zip(&filtered).for_each(|(a, f)| *a = f[i] as f64);
            *p = self.run(&prep, *p, &at);
        }
    }

    /// The coverage image of the matte of layer `id` on a `w × h` picture (ACEScg), or a loud error.
    pub fn coverage_image(&self, id: &str, px: &[Rgb], w: usize, h: usize) -> Result<Vec<f32>, String> {
        let ids: Vec<&str> = self.mattes().iter().map(|(l, _)| l.id.as_str()).collect();
        let (_, m) = self.mattes().into_iter().find(|(l, _)| l.id == id).ok_or_else(|| format!("no layer `{id}` has a matte (matted layers: {})", if ids.is_empty() { "none".into() } else { ids.join(", ") }))?;
        Ok(m.coverage_image(px, w, h))
    }
}
