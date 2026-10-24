//! A render's colour (docs/phase0/COLOUR_WAVE_B.md): the working space the surfaces paint in, how a tagged image
//! enters it (assets.rs), and the one output step (working → output code → dither → quantise) every frame goes
//! through on its way out, preview and export alike. The rules themselves are `rostrum_color::pipeline`.
//!
//! `open.color`: `{ "working": "display" | "linear-display" | "acescg", "view", "target": "sdr" | "hdr1000",
//! "output", "dither" }`; absent keys are display / neutral / sdr / srgb_display / dither on, which paints and
//! reads back exactly as renders before Wave B did.

use half::f16;
use rostrum_color::pipeline::{Input, Output, Pipeline, Working};
use rostrum_color::view::Target;
use serde_json::Value;
use skia_safe::ColorSpace;

#[derive(Clone, Copy)]
pub struct Spec {
    pub pipeline: Pipeline,
    pub output: Output,
    pub dither: bool,
}

impl Default for Spec {
    fn default() -> Self {
        Spec::parse(&Value::Null).expect("the default colour spec is valid")
    }
}

impl Spec {
    pub fn parse(v: &Value) -> Result<Spec, String> {
        let s = |k: &str, d: &'static str| v.get(k).and_then(Value::as_str).unwrap_or(d).to_string();
        let working = match s("working", "display").as_str() {
            "display" => Working::Display,
            "linear-display" => Working::LinearDisplay,
            "acescg" => Working::AcesCg,
            w => return Err(format!("color.working is display, linear-display or acescg; got `{w}`")),
        };
        let target = match s("target", "sdr").as_str() {
            "sdr" => Target::Sdr,
            "hdr1000" => Target::Hdr1000,
            t => return Err(format!("color.target is sdr or hdr1000; got `{t}`")),
        };
        let pipeline = Pipeline::new(working, &s("view", "neutral"), target)?;
        let default_out = if target == Target::Sdr { "srgb_display" } else { "rec2100_pq" };
        let output = pipeline.output(&s("output", default_out))?;
        Ok(Spec { pipeline, output, dither: v.get("dither").and_then(Value::as_bool).unwrap_or(true) })
    }

    /// The colour space the surfaces are tagged with: none for display values (unmanaged, as before), linear sRGB,
    /// or linear ACEScg, so Skia converts CSS colours and 8-bit (sRGB) images into it.
    pub fn surface_space(&self) -> Option<ColorSpace> {
        match self.pipeline.working {
            Working::Display => None,
            Working::LinearDisplay => Some(ColorSpace::new_srgb_linear()),
            Working::AcesCg => Some(acescg_space()),
        }
    }
}

/// Linear ACEScg as a Skia colour space. skia-safe has no `makeRGB`, so it is deserialized from Skia's own layout
/// (4-byte header, 7 transfer-function floats, the 3×3 to-XYZ-D50 matrix). The matrix is Skia's sRGB matrix times
/// rostrum-color's ACEScg → Rec.709, so Skia's sRGB → ACEScg conversion is exactly ours (OCIO's Bradford).
pub fn acescg_space() -> ColorSpace {
    let srgb = ColorSpace::new_srgb_linear().serialize();
    let f = |i: usize| f32::from_le_bytes(srgb.as_bytes()[4 + 4 * i..8 + 4 * i].try_into().unwrap()) as f64;
    let srgb_xyz: [[f64; 3]; 3] = std::array::from_fn(|r| std::array::from_fn(|c| f(7 + 3 * r + c)));
    let to_709 = rostrum_color::convert::gamut_matrix("acescg", "lin_rec709").expect("registered gamuts");
    let m = rostrum_color::matrix::mul(&srgb_xyz, &to_709);
    let mut bytes = srgb.as_bytes()[..4].to_vec();
    for v in [1.0f32, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0].into_iter().chain(m.iter().flatten().map(|&v| v as f32)) {
        bytes.extend_from_slice(&v.to_le_bytes());
    }
    ColorSpace::deserialize(skia_safe::Data::new_copy(&bytes))
}

/// A decoded image (RGBA code values, straight or `premultiplied`) as an `RHALF` image in the working space: each
/// pixel's straight colour through `input`, premultiplied, half float (blitz-dom net.rs reads it; anyrender_skia
/// draws it tagged as the surface).
/// `grade`: the one grade on a scene-referred picture's light (ACEScg), before its view (a 3D scene's grade, C7).
/// The largest finite half float.
const HALF_MAX: f32 = 65504.0;

/// `under`: a 3D scene's background as ACEScg light (`Pipeline::display_to_scene` of its authored colour), laid under a
/// scene-referred picture before its grade and view, as the scene's own frame has it: the picture comes out opaque.
pub fn rhalf(pipeline: &Pipeline, input: &Input, grade: Option<&rostrum_color::grade::Grade>, under: Option<[f32; 3]>, width: u32, height: u32, rgba: &[f32], premultiplied: bool) -> Vec<u8> {
    rhalf_with(pipeline, input, grade, under, width, height, rgba, premultiplied, None)
}

/// `rhalf` with the scene's grade and view through `lut` (a playing preview's frame, `&fast=1`: SceneLut) instead of
/// exactly per pixel; everything else as rhalf.
#[allow(clippy::too_many_arguments)]
pub fn rhalf_with(pipeline: &Pipeline, input: &Input, grade: Option<&rostrum_color::grade::Grade>, under: Option<[f32; 3]>, width: u32, height: u32, rgba: &[f32], premultiplied: bool, lut: Option<&SceneLut>) -> Vec<u8> {
    let scene = |lin: [f32; 3]| match lut {
        Some(l) => l.apply(lin),
        None => pipeline.scene_in(grade.map_or(lin, |g| g.apply(lin))),
    };
    let mut out = Vec::with_capacity(16 + rgba.len() * 2);
    out.extend_from_slice(blitz_dom::net::RHALF_MAGIC);
    out.extend_from_slice(&width.to_le_bytes());
    out.extend_from_slice(&height.to_le_bytes());
    let mut px = vec![0u8; rgba.len() * 2];
    crate::pixels::bands(rgba.len() / 4, |range, dst: &mut [u8]| {
        for (i, o) in range.zip(dst.chunks_exact_mut(8)) {
            let p = &rgba[i * 4..i * 4 + 4];
            let mut a = p[3].clamp(0.0, 1.0);
            // Premultiplied light with alpha 0 (an EXR's additive glow, Nuke's "emission") is kept: it converts as light at
            // full strength and enters with alpha 0, so `over` adds it (hem-r13 e-premult F2: it was read as transparent black).
            let emit = premultiplied && a <= 0.0 && p[..3].iter().any(|&x| x != 0.0 && x.is_finite());
            let k = if premultiplied && a > 0.0 { 1.0 / a } else { 1.0 };
            // ±inf (a depth pass's miss: the sky) is held at the half float's largest value: through the matrices below
            // 0·inf would be NaN and leave as 0, so the sky would read as 0 m (2026-10-18: every sky pixel took defocus's
            // largest disc). The AOV programs read ≥ 6e4 as infinite. NaN stays NaN and is written as 0.
            let rgb = [p[0] * k, p[1] * k, p[2] * k].map(|x| x.clamp(-HALF_MAX, HALF_MAX));
            // A display-referred picture becomes light as Skia draws an sRGB colour; in a linear edit its clip's
            // filter then applies the inverse view (displayIn.ts), once, for the picture and its CSS alike.
            let c = match (input, under) {
                (Input::Scene { decode, to_acescg }, Some(u)) => {
                    let lin = rostrum_color::matrix::apply(to_acescg, rgb.map(|x| decode.decode(x) as f64)).map(|v| v as f32);
                    let lin = if emit { [0, 1, 2].map(|j| lin[j] + u[j]) } else if a > 0.0 { [0, 1, 2].map(|j| lin[j] * a + u[j] * (1.0 - a)) } else { u };
                    a = 1.0;
                    scene(lin)
                }
                _ if a <= 0.0 && !emit => [0.0; 3],
                (Input::Display, _) => pipeline.display_light(rgb),
                (Input::Scene { decode, to_acescg }, None) => {
                    let lin = rostrum_color::matrix::apply(to_acescg, rgb.map(|x| decode.decode(x) as f64)).map(|v| v as f32);
                    scene(lin)
                }
            };
            let s = if emit && a <= 0.0 { 1.0 } else { a };
            for (k, v) in [c[0] * s, c[1] * s, c[2] * s, a].into_iter().enumerate() {
                o[k * 2..k * 2 + 2].copy_from_slice(&f16::from_f32(if v.is_finite() { v } else { 0.0 }).to_le_bytes());
            }
        }
    }, &mut px, 8);
    out.extend_from_slice(&px);
    out
}

/// A scene-referred picture's grade and view (ACEScg light → working space) as a 3D table on a log2 shaper, for a
/// playing preview's frames: the ACES 2.0 view costs ~1 µs a pixel exactly (110 ms for a 960 px frame), the table
/// a trilinear look-up. Light below 2^LO is held at it, above 2^HI at it; negative light at 0 (looks right in a
/// moving preview; a still frame, Final and export convert exactly).
pub struct SceneLut {
    n: usize,
    table: Vec<[f32; 3]>,
}

const LUT_N: usize = 48;
const LUT_LO: f32 = -12.0;
const LUT_HI: f32 = 10.0;
/// Below this the shaper is linear to 0 (black stays black).
const LUT_FLOOR: f32 = 1.0 / 4096.0;

impl SceneLut {
    fn shape(x: f32) -> f32 {
        // [0, FLOOR] linear onto the first cell; above, log2 between LO and HI.
        let step = 1.0 / (LUT_N - 1) as f32;
        if x <= LUT_FLOOR {
            return (x.max(0.0) / LUT_FLOOR) * step;
        }
        let t = (x.log2() - LUT_LO) / (LUT_HI - LUT_LO);
        (step + t * (1.0 - step)).clamp(0.0, 1.0)
    }
    fn unshape(u: f32) -> f32 {
        let step = 1.0 / (LUT_N - 1) as f32;
        if u <= step {
            return u / step * LUT_FLOOR;
        }
        let t = (u - step) / (1.0 - step);
        (LUT_LO + t * (LUT_HI - LUT_LO)).exp2()
    }

    /// The table of `f` (exact grade + view), built on all cores.
    pub fn build(f: impl Fn([f32; 3]) -> [f32; 3] + Sync) -> SceneLut {
        let n = LUT_N;
        let mut table = vec![[0f32; 3]; n * n * n];
        let threads = std::thread::available_parallelism().map(|v| v.get()).unwrap_or(4).min(8);
        let per = (n * n * n).div_ceil(threads);
        let f = &f;
        std::thread::scope(|s| {
            for (k, chunk) in table.chunks_mut(per).enumerate() {
                s.spawn(move || {
                    for (j, o) in chunk.iter_mut().enumerate() {
                        let i = k * per + j;
                        let (r, g, b) = (i % n, (i / n) % n, i / (n * n));
                        let c = [r, g, b].map(|v| Self::unshape(v as f32 / (n - 1) as f32));
                        *o = f(c).map(|v| if v.is_finite() { v } else { 0.0 });
                    }
                });
            }
        });
        SceneLut { n, table }
    }

    pub fn apply(&self, c: [f32; 3]) -> [f32; 3] {
        let n = self.n;
        let m = (n - 1) as f32;
        let p = c.map(|v| Self::shape(v) * m);
        let i = p.map(|v| (v.floor() as usize).min(n - 2));
        let f = [p[0] - i[0] as f32, p[1] - i[1] as f32, p[2] - i[2] as f32];
        let at = |r: usize, g: usize, b: usize| self.table[r + g * n + b * n * n];
        let mut out = [0f32; 3];
        for (dr, wr) in [(0, 1.0 - f[0]), (1, f[0])] {
            for (dg, wg) in [(0, 1.0 - f[1]), (1, f[1])] {
                for (db, wb) in [(0, 1.0 - f[2]), (1, f[2])] {
                    let w = wr * wg * wb;
                    if w == 0.0 {
                        continue;
                    }
                    let v = at(i[0] + dr, i[1] + dg, i[2] + db);
                    for k in 0..3 {
                        out[k] += v[k] * w;
                    }
                }
            }
        }
        out
    }
}

/// A dither offset in [-0.5, 0.5) of one quantisation step, from the pixel and channel: deterministic (a preview
/// frame equals the exported one) and the same every frame, so a held picture stays bit-identical (no shimmer,
/// and an encoder sees no change).
fn dither(x: u32, y: u32, c: u32) -> f32 {
    offset(dither_hash(x, y, c))
}

/// The dither's 24-bit hash value of a pixel and channel.
#[inline]
pub(crate) fn dither_hash(x: u32, y: u32, c: u32) -> u32 {
    let mut h = x.wrapping_mul(0x9E37_79B1) ^ y.wrapping_mul(0x85EB_CA77) ^ c.wrapping_mul(0xC2B2_AE3D);
    h ^= h >> 15;
    h = h.wrapping_mul(0x2C1B_3C6D);
    h ^= h >> 12;
    h = h.wrapping_mul(0x297A_2D39);
    h ^= h >> 15;
    h >> 8
}

/// The dither offset of a 24-bit hash value `m` (the GPU output step computes the same hash; gpu_output.rs).
fn offset(m: u32) -> f32 {
    m as f32 / (1u32 << 24) as f32 - 0.5
}

/// One channel to 8 bits. A value within 0.2 of a code is that code (a `#hex` colour stays exact through half
/// floats and GPU maths, ~0.1 of a code); one between codes is dithered, so gradients do not band.
fn quantise8(q: f32, dither_on: bool, d: impl Fn() -> f32) -> u8 {
    let near = q.round();
    let v = if !dither_on || (q - near).abs() < 0.2 { near } else { (q + 0.5 + d()).floor() };
    v.clamp(0.0, 255.0) as u8
}

/// The output step: a premultiplied F16 frame in the working space → straight RGBA in the output's code values,
/// 16-bit little-endian (`deep`) or 8-bit with dither. `_frame`: the document frame index (kept for a temporal
/// dither; the pattern is static today). `fast`: a playing preview's frame (a JPEG): when the step mixes channels (no
/// channel table), 8-bit pixels go through the checked 3D table (`output_lut`, within 1/255 of `apply`); a still, an
/// export, a deep frame never do.
pub fn output(spec: &Spec, src: &[u8], width: u32, deep: bool, fast: bool, frame: u32, out: &mut Vec<u8>) {
    out.clear();
    out.resize(src.len() / 8 * if deep { 8 } else { 4 }, 0);
    output_into(spec, src, width, deep, fast, frame, out);
}

/// `output` into a buffer of exactly the frame's size (a shared-memory slot, shm.rs); every byte is written.
pub fn output_into(spec: &Spec, src: &[u8], width: u32, deep: bool, fast: bool, _frame: u32, out: &mut [u8]) {
    output_rows(spec, src, width, 0, deep, fast, out);
}

/// `output_into` for rows of a frame starting at row `y0` (the dither is placed by the pixel's place in the whole frame).
pub fn output_rows(spec: &Spec, src: &[u8], width: u32, y0: u32, deep: bool, fast: bool, out: &mut [u8]) {
    let table = crate::pixels::halves();
    let chan = channel_table(spec);
    let lut = if fast && !deep && chan.is_none() { output_lut(spec) } else { None };
    let px = src.len() / 8;
    let bpp = if deep { 8 } else { 4 };
    assert_eq!(out.len(), px * bpp, "output buffer size");
    // An opaque pixel of an 8-bit frame from the integer codes the GPU's step reads too (output8.rs): same bytes, no float maths.
    let codes = if deep { None } else { gpu_codes(spec, false) };
    crate::pixels::bands(px, |range, dst: &mut [u8]| {
        // The place in the frame by counting along (a division per pixel was the slowest step of an export).
        let (mut x, mut y) = (range.start as u32 % width, y0 + range.start as u32 / width);
        for (p, o) in src[range.start * 8..range.end * 8].chunks_exact(8).zip(dst.chunks_exact_mut(bpp)) {
            let (px_x, px_y) = (x, y);
            x += 1;
            if x == width {
                (x, y) = (0, y + 1);
            }
            if codes.as_ref().is_some_and(|c| crate::output8::opaque(c, p, (px_x, px_y), o)) {
                continue;
            }
            let bits = |k: usize| u16::from_le_bytes([p[k * 2], p[k * 2 + 1]]) as usize;
            let v = |k: usize| table[bits(k)];
            let a = if v(3).is_finite() { v(3).clamp(0.0, 1.0) } else { 0.0 };
            if a == 0.0 {
                o.fill(0);
                continue;
            }
            // An opaque pixel's channels are its stored halves as they are (÷ 1): through the channel table when the output
            // step is one curve per channel (the same numbers `apply` gives, without its maths per pixel).
            // A playing frame's pixel through the 3D table when it lies in a checked cell (an opaque one placed on the table by
            // its halves' bits, without a log per channel); anything else through `apply`.
            let c = match (&chan, &lut) {
                (Some(t), _) if a == 1.0 && (0..3).all(|k| v(k).is_finite()) => [t[bits(0)], t[bits(1)], t[bits(2)]],
                (_, Some(l)) => {
                    let w = [v(0) / a, v(1) / a, v(2) / a];
                    let at = if a == 1.0 { [0, 1, 2].map(|k| l.axis[bits(k)]) } else { w.map(|x| l.place(x)) };
                    l.get(at).unwrap_or_else(|| spec.output.apply(w))
                }
                _ => spec.output.apply([v(0) / a, v(1) / a, v(2) / a]),
            };
            for (k, c) in [c[0], c[1], c[2], a].into_iter().enumerate() {
                if deep {
                    o[k * 2..k * 2 + 2].copy_from_slice(&((c * 65535.0 + 0.5) as u16).to_le_bytes());
                } else {
                    o[k] = quantise8(c * 255.0, spec.dither && k < 3, || dither(px_x, px_y, k as u32));
                }
            }
        }
    }, out, bpp);
}

/// What a cached table depends on: the pipeline and the output step's own numbers (an output id is not kept on the Spec).
fn spec_key(spec: &Spec) -> String {
    let mut key = format!("{:p}|{:?}|{:?}", spec.pipeline.view, spec.pipeline.working, spec.pipeline.target);
    for c in [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [0.25, 0.5, 0.75], [2.0, 0.01, 0.3]] {
        key += &format!("|{:?}", spec.output.apply(c).map(f32::to_bits));
    }
    key
}

/// The output step of every finite half as a channel table (index: the half's bits), when the step is the same curve on each
/// channel alone (no matrix mixing them, no view across channels: a display or linear-display working space on its own
/// primaries' output). Checked, not assumed: probe colours mixing all three channels must come out as the table gives them
/// to a millionth of the code range (a gamut matrix that is the identity to f64 rounding; 1/15 of a 16-bit code), else None
/// (`apply` per pixel, as before). Preview and export both convert here, so they stay equal. Made once per colour (a few
/// ms) and kept for the process.
pub fn channel_table(spec: &Spec) -> Option<std::sync::Arc<[f32]>> {
    type Tables = Vec<(String, Option<std::sync::Arc<[f32]>>)>;
    static TABLES: std::sync::OnceLock<std::sync::Mutex<Tables>> = std::sync::OnceLock::new();
    let one = |x: f32| spec.output.apply([x, x, x]);
    let key = spec_key(spec);
    let tables = TABLES.get_or_init(Default::default);
    if let Some((_, t)) = tables.lock().unwrap_or_else(|e| e.into_inner()).iter().find(|(k, _)| *k == key) {
        return t.clone();
    }
    let halves = crate::pixels::halves();
    let same = |a: f32, b: f32| (a - b).abs() <= 1e-6 || a.to_bits() == b.to_bits() || (a.is_nan() && b.is_nan());
    // Probes: each channel beside the other two at many levels (negative, 0, the display range, above 1), and the primaries.
    let mut seed = 0x1234_5678u32;
    let mut rnd = || {
        seed ^= seed << 13;
        seed ^= seed >> 17;
        seed ^= seed << 5;
        let x = halves[(seed & 0xffff) as usize];
        if x.is_finite() { x } else { 1.0 }
    };
    let separable = (0..4096).all(|n| {
        let c = if n < 3 { [0, 1, 2].map(|k| if k == n { 1.0 } else { 0.0 }) } else { [rnd(), rnd(), rnd()] };
        let out = spec.output.apply(c);
        (0..3).all(|k| same(out[k], one(c[k])[0]))
    });
    // A gray must also come out the same on all three channels (one curve for every channel).
    let table: Option<std::sync::Arc<[f32]>> = separable
        .then(|| (0..=u16::MAX as usize).map(|h| if halves[h].is_finite() { one(halves[h])[0] } else { 0.0 }).collect::<Vec<_>>().into())
        .filter(|t: &std::sync::Arc<[f32]>| (0..=u16::MAX as usize).step_by(7).filter(|&h| halves[h].is_finite()).all(|h| one(halves[h]).iter().all(|&o| same(o, t[h]))));
    tables.lock().unwrap_or_else(|e| e.into_inner()).push((key, table.clone()));
    table
}

/// The output step of an opaque channel as integer codes for the GPU (gpu_output.rs), one per half's bits, when the step
/// has a channel table: `deep`, the 16-bit code; else the 8-bit code at the dither offset 0 in the low byte and, above
/// it, the first 24-bit dither hash value from which the code is one more (0: never). `quantise8` is monotone in the
/// offset and moves a value by at most one code, so this threshold is exact: the GPU gives `output`'s bytes, bit for bit.
pub fn gpu_codes(spec: &Spec, deep: bool) -> Option<std::sync::Arc<[u32]>> {
    type Codes = Vec<(String, std::sync::Arc<[u32]>)>;
    static CODES: std::sync::OnceLock<std::sync::Mutex<Codes>> = std::sync::OnceLock::new();
    let table = channel_table(spec)?;
    let key = format!("{}|{}|{deep}", spec_key(spec), spec.dither);
    let codes = CODES.get_or_init(Default::default);
    if let Some((_, c)) = codes.lock().unwrap_or_else(|e| e.into_inner()).iter().find(|(k, _)| *k == key) {
        return Some(c.clone());
    }
    let code = |c: f32| -> u32 {
        if deep {
            return (c * 65535.0 + 0.5) as u16 as u32;
        }
        let at = |m: u32| quantise8(c * 255.0, spec.dither, || offset(m)) as u32;
        let (lo, hi) = (at(0), at((1 << 24) - 1));
        if lo == hi {
            return lo;
        }
        assert_eq!(hi, lo + 1, "the dither moves a value by one code");
        let (mut a, mut b) = (0u32, (1 << 24) - 1); // at(a) = lo, at(b) = hi
        while b - a > 1 {
            let m = a + (b - a) / 2;
            if at(m) == lo { a = m } else { b = m }
        }
        lo | b << 8
    };
    let out: std::sync::Arc<[u32]> = par_fill(table.len(), |h| code(table[h])).into();
    codes.lock().unwrap_or_else(|e| e.into_inner()).push((key, out.clone()));
    Some(out)
}

/// The output step as a 3D table, for a playing preview's frames (`output(.., fast)`) when the step mixes channels (a view
/// such as AgX or ACES 2.0 on ACEScg: no channel table, ~1 µs a pixel exactly). Each axis is a working-space channel on a
/// shaper linear through 0 and logarithmic above its toe (sign(x)·ln(1 + |x|/OLUT_TOE)), from -OLUT_NEG to OLUT_HI; the
/// entries are `apply`'s code values, read by tetrahedral interpolation.
/// Checked, not assumed: a mixing view's clamps and gamut clips put kinks inside some cells, where no table is within a
/// code. So a cell whose corners straddle a clip (a channel at 0 or 1 at some corners, between at others) is dropped, and
/// every other cell is probed against `apply` (its centre and OLUT_PROBES - 1 points spread inside it) and kept only when
/// all are within OLUT_CELL_TOL; a pixel in a dropped cell, with a channel outside the range or not finite goes through
/// `apply`. Then random colours over the whole range (greys, primaries, the display range, highs, negatives): one that a
/// kept cell answers more than 1/255 off drops that cell too, and more than OLUT_MISSES of them mean the table does not
/// follow this step at all: no table (`apply` per pixel).
/// Measured on AgX (2026-10-21, a JS model of the view): 88% of cells kept, 96% of display-range colours answered, 1 in
/// 184k probes of kept cells beyond 1/255 (1.13 codes, beside a clip). A playing frame only; stills and exports are exact.
pub struct OutputLut {
    /// Each half's place on an axis (0 ..= OLUT_N - 1), NaN outside the range: an opaque pixel is placed by its bits.
    axis: Vec<f32>,
    table: Vec<[f32; 3]>,
    /// Per cell (index r + g·m + b·m², m = OLUT_N - 1): within OLUT_CELL_TOL at every probe.
    good: Vec<bool>,
    /// The shaper's ends.
    s0: f32,
    s1: f32,
}

const OLUT_N: usize = 65;
/// The shaper's toe, and the range (AgX holds every channel above ~16 at its top; ACEScg footage is rarely below -1/128).
const OLUT_TOE: f32 = 0.003;
const OLUT_NEG: f32 = 1.0 / 128.0;
const OLUT_HI: f32 = 16.0;
const OLUT_PROBES: u32 = 8;
const OLUT_CELL_TOL: f32 = 0.5 / 255.0;
const OLUT_TOL: f32 = 1.0 / 255.0;
/// Whole-range probes, and how many may miss (each dropping its cell) before the table is refused.
const OLUT_CHECKS: usize = 40_000;
const OLUT_MISSES: usize = 40;

/// Fills `len` values of `f(index)` on up to 8 threads.
fn par_fill<T: Copy + Default + Send>(len: usize, f: impl Fn(usize) -> T + Sync) -> Vec<T> {
    let mut out = vec![T::default(); len];
    let threads = std::thread::available_parallelism().map(|v| v.get()).unwrap_or(4).min(8);
    let per = len.div_ceil(threads).max(1);
    let f = &f;
    std::thread::scope(|s| {
        for (k, chunk) in out.chunks_mut(per).enumerate() {
            s.spawn(move || chunk.iter_mut().enumerate().for_each(|(j, o)| *o = f(k * per + j)));
        }
    });
    out
}

/// A deterministic number in [0, 1) from a seed (an integer hash).
fn unit(seed: u32) -> f32 {
    let mut h = seed.wrapping_mul(0x9E37_79B1) ^ 0x6A09_E667;
    h ^= h >> 15;
    h = h.wrapping_mul(0x2C1B_3C6D);
    h ^= h >> 12;
    h = h.wrapping_mul(0x297A_2D39);
    h ^= h >> 15;
    (h >> 8) as f32 / (1u32 << 24) as f32
}

impl OutputLut {
    fn shape(x: f32) -> f32 {
        x.signum() * (x.abs() / OLUT_TOE).ln_1p()
    }

    /// A working-space value's place on an axis, NaN outside the range (or NaN in).
    pub fn place(&self, x: f32) -> f32 {
        if !(-OLUT_NEG..=OLUT_HI).contains(&x) {
            return f32::NAN;
        }
        ((Self::shape(x) - self.s0) / (self.s1 - self.s0) * (OLUT_N - 1) as f32).clamp(0.0, (OLUT_N - 1) as f32)
    }

    /// The working-space value at a place on an axis.
    fn value(&self, u: f32) -> f32 {
        let s = self.s0 + u / (OLUT_N - 1) as f32 * (self.s1 - self.s0);
        (s.signum() * s.abs().exp_m1() * OLUT_TOE).clamp(-OLUT_NEG, OLUT_HI)
    }

    /// Tetrahedral interpolation in the cell at `i` (each < OLUT_N - 1), `f` the place inside it.
    fn interp(&self, i: [usize; 3], f: [f32; 3]) -> [f32; 3] {
        let n = OLUT_N;
        let step = [1, n, n * n];
        let base = i[0] + i[1] * n + i[2] * n * n;
        // The axes by falling fraction: the walk 000 → first axis → first two → 111.
        let (a, b, c) = if f[0] >= f[1] {
            if f[1] >= f[2] { (0, 1, 2) } else if f[0] >= f[2] { (0, 2, 1) } else { (2, 0, 1) }
        } else if f[2] >= f[1] {
            (2, 1, 0)
        } else if f[2] >= f[0] {
            (1, 2, 0)
        } else {
            (1, 0, 2)
        };
        let (v0, v1) = (self.table[base], self.table[base + step[a]]);
        let (v2, v3) = (self.table[base + step[a] + step[b]], self.table[base + step[0] + step[1] + step[2]]);
        let w = [1.0 - f[a], f[a] - f[b], f[b] - f[c], f[c]];
        [0, 1, 2].map(|k| w[0] * v0[k] + w[1] * v1[k] + w[2] * v2[k] + w[3] * v3[k])
    }

    /// The code values at three places, None when one is outside the range or the cell was not kept.
    pub fn get(&self, at: [f32; 3]) -> Option<[f32; 3]> {
        if !at.iter().all(|p| p.is_finite()) {
            return None;
        }
        let m = OLUT_N - 1;
        let i = at.map(|p| (p as usize).min(m - 1));
        if !self.good[i[0] + i[1] * m + i[2] * m * m] {
            return None;
        }
        Some(self.interp(i, [0, 1, 2].map(|k| at[k] - i[k] as f32)))
    }

    /// The table for the GPU output step (painter.rs `read_output8`): its size, the shaper's toe, range and ends
    /// ([toe, low, high, s0, s1]), and the entries as half-float RGBA laid out (r + g·n, b) in an n²×n image (alpha 1). The
    /// GPU reads every cell, kept or not (a dropped cell is a few codes off beside a clip), and holds colours outside the
    /// range at its edge: a playing frame only.
    pub fn gpu_table(&self) -> (usize, [f32; 5], Vec<u8>) {
        let one = f16::from_f32(1.0).to_le_bytes();
        let mut bytes = Vec::with_capacity(self.table.len() * 8);
        for c in &self.table {
            for v in c {
                bytes.extend_from_slice(&f16::from_f32(v.clamp(0.0, 1.0)).to_le_bytes());
            }
            bytes.extend_from_slice(&one);
        }
        (OLUT_N, [OLUT_TOE, -OLUT_NEG, OLUT_HI, self.s0, self.s1], bytes)
    }

    /// The table of `step` (the output step, `Output::apply`), checked against it; None when it does not follow it.
    fn build(step: impl Fn([f32; 3]) -> [f32; 3] + Sync) -> Option<OutputLut> {
        let (n, m) = (OLUT_N, OLUT_N - 1);
        let mut lut = OutputLut { axis: vec![], table: vec![], good: vec![], s0: Self::shape(-OLUT_NEG), s1: Self::shape(OLUT_HI) };
        let halves = crate::pixels::halves();
        lut.axis = halves.iter().map(|&h| lut.place(h)).collect();
        lut.table = par_fill(n * n * n, |i| {
            let c = [i % n, (i / n) % n, i / (n * n)].map(|v| lut.value(v as f32));
            step(c).map(|v| if v.is_finite() { v } else { 0.0 })
        });
        let ok = |a: [f32; 3], b: [f32; 3], tol: f32| (0..3).all(|k| (a[k] - b[k]).abs() <= tol);
        // A clip crossing the cell: some corner's channel held at 0 or 1, another's between.
        let straddles = |i: [usize; 3]| {
            let base = i[0] + i[1] * n + i[2] * n * n;
            let corners = [0, 1, n, n + 1, n * n, n * n + 1, n * n + n, n * n + n + 1].map(|d| lut.table[base + d]);
            (0..3).any(|k| {
                let held = corners.iter().any(|c| c[k] <= 0.0 || c[k] >= 1.0);
                held && corners.iter().any(|c| c[k] > 0.0 && c[k] < 1.0)
            })
        };
        lut.good = par_fill(m * m * m, |j| {
            let i = [j % m, (j / m) % m, j / (m * m)];
            !straddles(i)
                && (0..OLUT_PROBES).all(|q| {
                    let f = [0u32, 1, 2].map(|k| if q == 0 { 0.5 } else { unit((j as u32).wrapping_mul(OLUT_PROBES * 3) + q * 3 + k) });
                    let c = [0, 1, 2].map(|k| lut.value(i[k] as f32 + f[k]));
                    // The probe as a pixel would place it (the shaper's round trip), so cell and fractions are what `get` uses.
                    let at = c.map(|x| lut.place(x));
                    let i2 = at.map(|p| (p as usize).min(m - 1));
                    i2 != i || ok(lut.interp(i, [0, 1, 2].map(|k| at[k] - i[k] as f32)), step(c), OLUT_CELL_TOL)
                })
        });
        // The whole range: random colours in five families. One the table answers more than 1/255 off drops its cell.
        let fam = |n: u32| -> [f32; 3] {
            let r = |k: u32| unit(0x5EED_0000 ^ n.wrapping_mul(7).wrapping_add(k));
            let anywhere = |u: f32| lut.value(u * m as f32);
            match n % 5 {
                0 => [anywhere(r(0)), anywhere(r(1)), anywhere(r(2))],
                1 => [r(0) * 1.5, r(1) * 1.5, r(2) * 1.5],
                2 => [anywhere(r(0)); 3],
                // One channel slightly negative beside two in [0, 2].
                3 => {
                    let neg = (r(3) * 3.0) as u32;
                    [0u32, 1, 2].map(|k| if k == neg { -OLUT_NEG * r(k) } else { r(k) * 2.0 })
                }
                // Primaries and secondaries from black to the top of the range, over near-black.
                _ => {
                    let lvl = ([0.0, 0.18, 1.0, 4.0, OLUT_HI][(n / 5 % 5) as usize] * (0.5 + r(0))).min(OLUT_HI);
                    [0u32, 1, 2].map(|k| if ((n / 25) >> k) & 1 == 1 { lvl } else { r(k) * 0.01 })
                }
            }
        };
        let missed = par_fill(OLUT_CHECKS, |n| {
            let c = fam(n as u32);
            let at = c.map(|x| lut.place(x));
            match lut.get(at) {
                Some(o) if !ok(o, step(c), OLUT_TOL) => {
                    let i = at.map(|p| (p as usize).min(m - 1));
                    Some(i[0] + i[1] * m + i[2] * m * m)
                }
                _ => None,
            }
        });
        let missed: Vec<usize> = missed.into_iter().flatten().collect();
        if missed.len() > OLUT_MISSES {
            return None;
        }
        for j in missed {
            lut.good[j] = false;
        }
        // A table that answers under a quarter of its cells does not follow the step either.
        (lut.good.iter().filter(|&&g| g).count() * 4 >= lut.good.len()).then_some(lut)
    }
}

/// The output step's checked 3D table (OutputLut) for a playing frame, None when it does not follow `apply`. Made once
/// per colour (~50 ms for AgX, a few hundred for ACES 2.0, on all cores; the first playing frame pays it) and kept for
/// the process, as `channel_table`.
pub fn output_lut(spec: &Spec) -> Option<std::sync::Arc<OutputLut>> {
    type Luts = Vec<(String, Option<std::sync::Arc<OutputLut>>)>;
    static LUTS: std::sync::OnceLock<std::sync::Mutex<Luts>> = std::sync::OnceLock::new();
    let key = spec_key(spec);
    let luts = LUTS.get_or_init(Default::default);
    if let Some((_, l)) = luts.lock().unwrap_or_else(|e| e.into_inner()).iter().find(|(k, _)| *k == key) {
        return l.clone();
    }
    let lut = OutputLut::build(|c| spec.output.apply(c)).map(std::sync::Arc::new);
    luts.lock().unwrap_or_else(|e| e.into_inner()).push((key, lut.clone()));
    lut
}

#[cfg(test)]
mod tests {
    use super::*;

    fn json_spec(s: &str) -> Spec {
        Spec::parse(&serde_json::from_str(s).unwrap()).unwrap()
    }

    #[test]
    fn channel_table_gives_what_apply_gives() {
        // Per-channel outputs get a table equal to `apply` (to a millionth) on opaque pixels; a view mixing channels gets none.
        let halves = crate::pixels::halves();
        for spec in [json_spec("{}"), json_spec(r#"{"working":"linear-display"}"#)] {
            let t = channel_table(&spec).expect("a per-channel output step");
            let half = f16::from_f32(0.5).to_bits() as usize;
            for h in (0..=u16::MAX as usize).step_by(13).filter(|&h| halves[h].is_finite()) {
                let g = (h * 7) & 0x7bff;
                let want = spec.output.apply([halves[h], halves[g], 0.5]);
                let got = [t[h], t[g], t[half]];
                assert!((0..3).all(|k| (want[k] - got[k]).abs() <= 1e-6), "half {h:#06x}: {want:?} vs {got:?}");
            }
        }
        assert!(channel_table(&json_spec(r#"{"working":"acescg","view":"agx"}"#)).is_none(), "AgX mixes channels");
    }

    #[test]
    fn output_with_the_table_equals_apply_per_pixel() {
        // A frame through `output` (the table for opaque pixels) and through `apply` on every pixel: the same 16-bit values (± 1 at a code's edge).
        let spec = json_spec(r#"{"working":"linear-display"}"#);
        let mut src = vec![];
        let mut want = vec![];
        for i in 0..4096u32 {
            let a = if i % 5 == 0 { 0.5 } else { 1.0 };
            let c = [(i % 64) as f32 / 40.0, (i / 64) as f32 / 50.0, ((i * 31) % 97) as f32 / 90.0].map(|x| f16::from_f32(x * a).to_f32());
            src.extend(half_px([c[0], c[1], c[2], a]));
            let o = spec.output.apply([c[0] / a, c[1] / a, c[2] / a]);
            want.extend([o[0], o[1], o[2], a].map(|c| (c * 65535.0 + 0.5) as u16));
        }
        let mut out = vec![];
        output(&spec, &src, 64, true, false, 0, &mut out);
        let got: Vec<u16> = out.chunks(2).map(|b| u16::from_le_bytes([b[0], b[1]])).collect();
        assert_eq!(got.len(), want.len());
        assert!(got.iter().zip(&want).all(|(g, w)| g.abs_diff(*w) <= 1), "16-bit codes differ");
    }

    #[test]
    fn output_lut_follows_apply() {
        // AgX and the ACES 2.0 view on ACEScg: colours the table answers are within 1/255 of `apply` (a measured 1 in ~10^5
        // beside a clip may reach ~1.2 codes: none beyond 2), and it answers most of the display range (the speed-up).
        for view in ["agx", "aces2"] {
            let spec = json_spec(&format!(r#"{{"working":"acescg","view":"{view}"}}"#));
            let t = std::time::Instant::now();
            let lut = output_lut(&spec).unwrap_or_else(|| panic!("{view}: a table"));
            eprintln!("{view}: built in {:.0} ms", t.elapsed().as_secs_f64() * 1000.0);
            let (mut answered, mut over, mut worst) = (0, 0, 0f32);
            for n in 0..20_000u32 {
                let r = |k: u32| unit(0xC0FF_EE00 ^ n.wrapping_mul(5).wrapping_add(k));
                let c = if n % 2 == 0 { [r(0) * 1.5, r(1) * 1.5, r(2) * 1.5] } else { [0, 1, 2].map(|k| lut.value(r(k) * (OLUT_N - 1) as f32)) };
                let Some(o) = lut.get(c.map(|x| lut.place(x))) else { continue };
                answered += (n % 2 == 0) as u32;
                let e = (0..3).map(|k| (o[k] - spec.output.apply(c)[k]).abs()).fold(0f32, f32::max);
                over += (e > OLUT_TOL) as u32;
                worst = worst.max(e);
            }
            eprintln!("{view}: {answered} of 10000 display-range colours answered, {over} beyond 1/255, worst {:.2} codes", worst * 255.0);
            assert!(worst <= 2.0 / 255.0 && over <= 2, "{view}: worst {} codes, {over} beyond 1/255", worst * 255.0);
            assert!(answered >= 7_000, "{view}: only {answered} of 10000 display-range colours on the table");
        }
    }

    #[test]
    fn output_lut_refuses_a_step_it_cannot_follow() {
        // A step with no smoothness (a hash of its input): no table.
        let noise = |c: [f32; 3]| [unit(c[0].to_bits() ^ c[1].to_bits().rotate_left(11) ^ c[2].to_bits().rotate_left(22)); 3];
        assert!(OutputLut::build(noise).is_none());
    }

    #[test]
    fn fast_output_is_within_a_code_or_two_of_exact() {
        // A playing (fast) AgX frame vs the exact one: 8-bit codes within 2 (the table's 1/255 plus a dither step).
        let spec = json_spec(r#"{"working":"acescg","view":"agx"}"#);
        let mut src = vec![];
        for i in 0..4096u32 {
            let a = if i % 7 == 0 { 0.5 } else { 1.0 };
            let c = [(i % 64) as f32 / 30.0, (i / 64) as f32 / 40.0, ((i * 31) % 97) as f32 / 60.0];
            src.extend(half_px([c[0] * a, c[1] * a, c[2] * a, a]));
        }
        let (mut exact, mut fast) = (vec![], vec![]);
        output(&spec, &src, 64, false, false, 0, &mut exact);
        output(&spec, &src, 64, false, true, 0, &mut fast);
        assert!(exact.iter().zip(&fast).all(|(e, f)| e.abs_diff(*f) <= 2), "fast frame differs by more than 2 codes");
        // A deep frame never takes the table.
        let (mut d1, mut d2) = (vec![], vec![]);
        output(&spec, &src, 64, true, false, 0, &mut d1);
        output(&spec, &src, 64, true, true, 0, &mut d2);
        assert_eq!(d1, d2);
    }

    fn half_px(c: [f32; 4]) -> Vec<u8> {
        c.iter().flat_map(|v| f16::from_f32(*v).to_le_bytes()).collect()
    }

    // An export's bytes must not depend on which route an opaque pixel took: the integer codes (output8.rs) against the float step.
    #[test]
    fn integer_codes_give_the_float_steps_bytes() {
        let (w, h) = (97u32, 61u32);
        let mut s = 99u32;
        let mut rnd = || { s ^= s << 13; s ^= s >> 17; s ^= s << 5; s };
        let src: Vec<u8> = (0..w * h).flat_map(|_| {
            let c = [0, 1, 2].map(|_| match rnd() % 4 { 0 => rnd() as f32 / u32::MAX as f32 * 1.2 - 0.1, 1 => (rnd() % 256) as f32 / 255.0, _ => rnd() as f32 / u32::MAX as f32 });
            half_px([c[0], c[1], c[2], if rnd() % 5 == 0 { 0.5 } else { 1.0 }])
        }).collect();
        for dither_on in [true, false] {
            let spec = Spec { dither: dither_on, ..Spec::default() };
            let table = channel_table(&spec).unwrap();
            let mut got = vec![];
            output(&spec, &src, w, false, false, 0, &mut got);
            for (i, p) in src.chunks_exact(8).enumerate() {
                let bits = |k: usize| u16::from_le_bytes([p[k * 2], p[k * 2 + 1]]) as usize;
                if bits(3) != 0x3c00 { continue; }
                let (x, y) = (i as u32 % w, i as u32 / w);
                let want = [0, 1, 2].map(|k| quantise8(table[bits(k)] * 255.0, dither_on, || dither(x, y, k as u32)));
                assert_eq!(&got[i * 4..i * 4 + 3], &want, "pixel {i}, dither {dither_on}");
            }
        }
    }

    #[test]
    fn hex_colours_come_out_exact_under_dither() {
        let spec = Spec::default();
        for k in 0..=255u32 {
            let v = k as f32 / 255.0;
            let src: Vec<u8> = (0..64).flat_map(|_| half_px([v, v, v, 1.0])).collect();
            let mut out = vec![];
            output(&spec, &src, 8, false, false, 7, &mut out);
            assert!(out.chunks(4).all(|p| p[..3].iter().all(|&c| c as u32 == k)), "code {k}");
        }
    }

    #[test]
    fn dither_spreads_a_value_between_codes() {
        let spec = Spec::default();
        let v = 100.5 / 255.0;
        let src: Vec<u8> = (0..4096).flat_map(|_| half_px([v, v, v, 1.0])).collect();
        let mut out = vec![];
        output(&spec, &src, 64, false, false, 0, &mut out);
        let mean = out.chunks(4).map(|p| p[0] as f64).sum::<f64>() / 4096.0;
        assert!((mean - 100.5).abs() < 0.08, "mean {mean}");
        let mut again = vec![];
        output(&spec, &src, 64, false, false, 0, &mut again);
        assert_eq!(out, again, "deterministic");
    }

    #[test]
    fn premultiplied_half_to_straight_16_bit() {
        let spec = Spec::default();
        let mut out = vec![];
        output(&spec, &half_px([0.25, 0.0, 0.5, 0.5]), 1, true, false, 0, &mut out);
        let ch: Vec<u16> = out.chunks(2).map(|b| u16::from_le_bytes([b[0], b[1]])).collect();
        assert_eq!(ch, vec![32768, 0, 65535, 32768]);
    }

    #[test]
    fn acescg_space_converts_like_rostrum_color() {
        let cs = acescg_space();
        let srgb = ColorSpace::new_srgb_linear();
        // Skia's own conversion of linear sRGB red into the ACEScg space vs rostrum-color's matrix.
        let mut px = [1.0f32, 0.0, 0.0, 1.0];
        let src = skia_safe::ImageInfo::new((1, 1), skia_safe::ColorType::RGBAF32, skia_safe::AlphaType::Premul, srgb);
        let dst = skia_safe::ImageInfo::new((1, 1), skia_safe::ColorType::RGBAF32, skia_safe::AlphaType::Premul, cs);
        let pm = skia_safe::Pixmap::new(&src, bytemuck_slice(&mut px), 16).unwrap();
        let mut out = [0f32; 4];
        assert!(pm.read_pixels(&dst, bytemuck_slice(&mut out), 16, (0, 0)));
        let m = rostrum_color::convert::gamut_matrix("lin_rec709", "acescg").unwrap();
        for i in 0..3 {
            assert!((out[i] as f64 - m[i][0]).abs() < 1e-5, "{out:?} vs {m:?}");
        }
    }

    fn bytemuck_slice(v: &mut [f32]) -> &mut [u8] {
        unsafe { std::slice::from_raw_parts_mut(v.as_mut_ptr() as *mut u8, v.len() * 4) }
    }
}
