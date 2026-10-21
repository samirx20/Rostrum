//! The keyer's programs (COMP_CORE §4, §6). They read the plate (premultiplied, working space), compute in linear
//! ACEScg whatever `rostrumWorking` is, and return in the working space. `screen` and `replace` are ACEScg; `channel`
//! is the screen channel by index (1 g, 2 b; the "other" channel is then b, g); `m` is the screen picture (straight,
//! alpha 1, working space: `screenFill`'s output or the clean plate) and is read only when `local` > 0.5.
//!
//! ```text
//! d(x)   = x.k − (balance · x.r + (1 − balance) · x.o)          k = channel, o = the other of g / b
//! raw    = clamp(1 − d(x) / d(s) · gain, 0, 1)                   (d(s) ≤ 1e-6: raw 1)
//! alpha0 = clamp((raw − black) / (white − black), 0, 1) ^ gamma · plate alpha          keyAlpha
//! w      = raw (gain 1) < threshold                                                  screenWeight: (x·w, w)
//! spill  = max(0, x.k − L) · amount; L = balance-weighted r / o | (r + o) / 2 | max(r, o)   (method 0 / 1 / 2)
//! x.k −= spill; x += replace · spill; keepLuma: x += spill · Y.k (AP1)                 despill (plate alpha)
//! ```
//!
//! Difference matting (`key.difference`): `n` = the clean plate (premultiplied, working space), `wt` = the channel weights.
//!
//! ```text
//! dist   = sqrt(Σ wt_i · (x_i − n_i)² / Σ wt_i)        x, n straight ACEScg       diffDistance (grey; plate alpha 0: 0)
//! alpha0 = levels(ramp(blur(dist)), black, white, gamma) · plate alpha                diffAlpha
//! ramp   = clamp((d − threshold) / softness, 0, 1)    (softness ≤ 1e-6: d > threshold)
//! ```
//!
//! `edgeWeight` → blur → `edgeExtend` pulls the colour of solid foreground (α ≥ `solid`) into the soft edge. The blur is
//! not normalised: its alpha `W` is how much solid lies within reach, so the pull is `amount · min(2W, 1)` (full at the
//! solid's border, where W ≈ ½, fading to none past the blur's reach) toward the fill colour `rgb / W`. A full pull
//! wherever any solid was in reach cut a hard step where the reach ends (thin partial structures, e.g. a glasses tip);
//! `core` > 0 (`edge.inset`) also repaints near-opaque pixels at the solid's own rim, where less than `core` of the reach is
//! solid (W < core), with a pull fading from full at W = ½ to none at W = core: a ring of old-background colour left in
//! almost-opaque pixels (a sky's lavender at a leaf outline) takes the deeper foreground's colour, alpha untouched.
//! `wrapBand` (grey 1 − α) → blur → `norm`, times the blurred background, is the light `lightWrap` adds into the edge.

use super::{Program, Uniforms, ap1_y, from_cg, grey, pre, prelude, to_cg, u3, uf, unpre};
use crate::pipeline::Working;

/// The screen measurement's settings (`keyAlpha`, `screenWeight`, `despill`, `spill` uniforms).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Screen {
    pub color: [f32; 3],
    pub channel: usize,
    pub balance: f32,
}

impl Screen {
    fn d(&self, x: [f32; 3]) -> f32 {
        let (k, o) = if self.channel == 2 { (2, 1) } else { (1, 2) };
        x[k] - (self.balance * x[0] + (1.0 - self.balance) * x[o])
    }

    /// `raw` of ACEScg `x` against the screen colour `s`.
    pub fn raw(&self, x: [f32; 3], s: [f32; 3], gain: f32) -> f32 {
        let ds = self.d(s);
        let m = if ds <= 1e-6 { 0.0 } else { self.d(x) / ds * gain };
        (1.0 - m).clamp(0.0, 1.0)
    }

    /// The spill of ACEScg `x` by method 0 weighted, 1 average, 2 limit.
    pub fn spill(&self, x: [f32; 3], method: usize, amount: f32) -> f32 {
        let (k, o) = if self.channel == 2 { (2, 1) } else { (1, 2) };
        let l = match method {
            0 => self.balance * x[0] + (1.0 - self.balance) * x[o],
            1 => (x[0] + x[o]) * 0.5,
            _ => x[0].max(x[o]),
        };
        (x[k] - l).max(0.0) * amount
    }
}

fn screen_of(u: Uniforms) -> Screen {
    Screen { color: u3(u, "screen"), channel: uf(u, "channel").round() as usize, balance: uf(u, "balance") }
}

fn straight_cg(w: Working, c: [f32; 4]) -> ([f32; 3], f32) {
    let p = unpre(c);
    (to_cg(w, [p[0], p[1], p[2]]), p[3])
}

/// The screen colour a pixel keys against: the picture `m` (local) or the uniform.
fn local_screen(u: Uniforms, w: Working, m: [f32; 4]) -> [f32; 3] {
    if uf(u, "local") > 0.5 { straight_cg(w, m).0 } else { u3(u, "screen") }
}

/// The difference key's distance of ACEScg `x` from the clean plate's `n`: weighted RMS over the channels (weights' sum > 0).
pub fn diff_distance(x: [f32; 3], n: [f32; 3], weights: [f32; 3]) -> f32 {
    let sum = weights[0] + weights[1] + weights[2];
    if sum <= 0.0 {
        return 0.0;
    }
    ((0..3).map(|i| weights[i] * (x[i] - n[i]) * (x[i] - n[i])).sum::<f32>() / sum).sqrt()
}

/// The difference key's ramp: 0 at or under `threshold`, 1 at `threshold + softness` and over.
pub fn diff_ramp(d: f32, threshold: f32, softness: f32) -> f32 {
    if softness <= 1e-6 { if d > threshold { 1.0 } else { 0.0 } } else { ((d - threshold) / softness).clamp(0.0, 1.0) }
}

/// The despilled straight ACEScg colour and its spill.
pub fn despill(s: &Screen, x: [f32; 3], method: usize, amount: f32, replace: [f32; 3], keep_luma: bool) -> ([f32; 3], f32) {
    let sp = s.spill(x, method, amount);
    let k = if s.channel == 2 { 2 } else { 1 };
    let y = ap1_y()[k];
    let mut o = x;
    o[k] -= sp;
    let luma = if keep_luma { sp * y } else { 0.0 };
    (std::array::from_fn(|i| o[i] + replace[i] * sp + luma), sp)
}

pub(crate) fn eval(name: &str, u: Uniforms, w: Working, m: [f32; 4], c: [f32; 4]) -> Option<[f32; 4]> {
    let s = screen_of(u);
    Some(match name {
        "screenWeight" => {
            let p = unpre(c);
            if p[3] <= 0.0 {
                return Some([0.0; 4]);
            }
            let x = to_cg(w, [p[0], p[1], p[2]]);
            let wt = if s.raw(x, s.color, 1.0) < uf(u, "threshold") { 1.0 } else { 0.0 };
            [p[0] * wt, p[1] * wt, p[2] * wt, wt]
        }
        "screenFill" => {
            if c[3] <= 1e-3 { pre(from_cg(w, s.color), 1.0) } else { [c[0] / c[3], c[1] / c[3], c[2] / c[3], 1.0] }
        }
        "keyAlpha" => {
            let (x, a) = straight_cg(w, c);
            if a <= 0.0 {
                return Some(grey(0.0));
            }
            let raw = s.raw(x, local_screen(u, w, m), uf(u, "gain"));
            grey(super::matte::levels(raw, uf(u, "black"), uf(u, "white"), uf(u, "gamma"), false) * a)
        }
        "diffDistance" => {
            let (x, a) = straight_cg(w, c);
            if a <= 0.0 {
                return Some(grey(0.0));
            }
            grey(diff_distance(x, straight_cg(w, m).0, u3(u, "weights")))
        }
        "diffAlpha" => {
            let a = unpre(c)[3];
            if a <= 0.0 {
                return Some(grey(0.0));
            }
            let t = diff_ramp(m[0], uf(u, "threshold"), uf(u, "softness"));
            grey(super::matte::levels(t, uf(u, "black"), uf(u, "white"), uf(u, "gamma"), false) * a)
        }
        "despill" | "spill" => {
            let (x, a) = straight_cg(w, c);
            if a <= 0.0 {
                return Some(if name == "spill" { grey(0.0) } else { c });
            }
            let (o, sp) = despill(&s, x, uf(u, "method").round() as usize, uf(u, "amount"), u3(u, "replace"), uf(u, "keepLuma") > 0.5);
            if name == "spill" { grey(sp * a) } else { pre(from_cg(w, o), a) }
        }
        "edgeWeight" => {
            let p = unpre(c);
            let wt = if p[3] > 0.0 && p[3] >= uf(u, "solid") { 1.0 } else { 0.0 };
            [p[0] * wt, p[1] * wt, p[2] * wt, wt]
        }
        "edgeExtend" => {
            let (a, core) = (c[3], uf(u, "core"));
            if a <= 0.0 || m[3] <= 1e-4 {
                return Some(c);
            }
            let k = if a < uf(u, "solid") {
                uf(u, "amount") * (2.0 * m[3]).min(1.0)
            } else if core > 0.5 && m[3] < core {
                uf(u, "amount") * ((core - m[3]) / (core - 0.5)).clamp(0.0, 1.0)
            } else {
                return Some(c);
            };
            let keep = uf(u, "keepLuma");
            let px = [c[0] / a, c[1] / a, c[2] / a];
            let mut fill = [m[0] / m[3], m[1] / m[3], m[2] / m[3]];
            if keep > 0.0 {
                // The fill's colour at the pixel's own brightness; a partial pixel's brightness is first cleared of the old background's share.
                let y = ap1_y();
                let luma = |x: [f32; 3]| y[0] * x[0] + y[1] * x[1] + y[2] * x[2];
                let (xp, xf) = (to_cg(w, px), to_cg(w, fill));
                let yp = luma(xp);
                let est = if a < uf(u, "solid") { ((yp - (1.0 - a) * uf(u, "bgLuma")) / a.max(0.05)).max(0.0) } else { yp };
                let g = 1.0 + keep * ((est / luma(xf).max(1e-4)).clamp(0.0, 4.0) - 1.0);
                fill = from_cg(w, xf.map(|v| v * g));
            }
            std::array::from_fn(|i| if i == 3 { a } else { (px[i] + k * (fill[i] - px[i])) * a })
        }
        "wrapBand" => grey(1.0 - c[3]),
        "lightWrap" => {
            let a = c[3];
            if a <= 0.0 {
                return Some(c);
            }
            let k = uf(u, "amount");
            let l = [m[0] * k, m[1] * k, m[2] * k];
            if uf(u, "blend") < 0.5 {
                [c[0] + l[0] * a, c[1] + l[1] * a, c[2] + l[2] * a, a]
            } else {
                let f = [c[0] / a, c[1] / a, c[2] / a];
                std::array::from_fn(|i| if i == 3 { a } else { (f[i] + l[i] - f[i] * l[i]) * a })
            }
        }
        _ => return None,
    })
}

/// SkSL for the screen measurement, shared by the programs that key.
const MEASURE: &str = "float dOf(float3 x) {
    return channel > 1.5 ? x.b - (balance * x.r + (1.0 - balance) * x.g) : x.g - (balance * x.r + (1.0 - balance) * x.b);
}
float rawOf(float3 x, float3 s, float gain) {
    float ds = dOf(s);
    float m = ds <= 1e-6 ? 0.0 : dOf(x) / ds * gain;
    return clamp(1.0 - m, 0.0, 1.0);
}
float spillOf(float3 x, float method, float amount) {
    float o = channel > 1.5 ? x.g : x.b;
    float l = method < 0.5 ? balance * x.r + (1.0 - balance) * o : method < 1.5 ? (x.r + o) * 0.5 : max(x.r, o);
    return max((channel > 1.5 ? x.b : x.g) - l, 0.0) * amount;
}
";

pub(crate) fn programs() -> Vec<Program> {
    let p = prelude();
    let y = ap1_y();
    let screen = "uniform float3 screen;\nuniform float channel;\nuniform float balance;\n";
    let despill_u = "uniform float local;\nuniform float method;\nuniform float amount;\nuniform float3 replace;\nuniform float keepLuma;\n";
    let despill_body = format!(
        "    float4 u = unpre(float4(c));
    float3 x = toCg(u.rgb);
    float sp = spillOf(x, method, amount);
    float3 o = x - (channel > 1.5 ? float3(0.0, 0.0, sp) : float3(0.0, sp, 0.0)) + replace * sp + float3(keepLuma > 0.5 ? sp * (channel > 1.5 ? {} : {}) : 0.0);
",
        super::lit(y[2]),
        super::lit(y[1])
    );
    let prog = |name, blender, uniforms, body: String| Program { name, blender, code: format!("{p}{body}"), uniforms };
    vec![
        prog("screenWeight", false, &["screen", "channel", "balance", "threshold"], format!(
            "{screen}uniform float threshold;
{MEASURE}half4 main(half4 c) {{
    float4 u = unpre(float4(c));
    if (u.a <= 0.0) {{ return half4(0.0); }}
    float w = rawOf(toCg(u.rgb), screen, 1.0) < threshold ? 1.0 : 0.0;
    return half4(float4(u.rgb * w, w));
}}
")),
        prog("screenFill", false, &["screen"], "uniform float3 screen;
half4 main(half4 c) {
    float4 p = float4(c);
    return half4(p.a <= 1e-3 ? float4(fromCg(screen), 1.0) : float4(p.rgb / p.a, 1.0));
}
".into()),
        prog("keyAlpha", true, &["screen", "local", "channel", "balance", "gain", "black", "white", "gamma"], format!(
            "{screen}uniform float local;
uniform float gain;
uniform float black;
uniform float white;
uniform float gamma;
{MEASURE}half4 main(half4 m, half4 c) {{
    float4 u = unpre(float4(c));
    if (u.a <= 0.0) {{ return half4(grey(0.0)); }}
    float3 s = local > 0.5 ? toCg(unpre(float4(m)).rgb) : screen;
    float t = clamp((rawOf(toCg(u.rgb), s, gain) - black) / max(white - black, 1e-6), 0.0, 1.0);
    t = t <= 0.0 ? 0.0 : pow(t, gamma);
    return half4(grey(t * u.a));
}}
")),
        prog("diffDistance", true, &["weights"], "uniform float3 weights;
half4 main(half4 m, half4 c) {
    float4 u = unpre(float4(c));
    if (u.a <= 0.0) { return half4(grey(0.0)); }
    float3 d = toCg(u.rgb) - toCg(unpre(float4(m)).rgb);
    float sum = weights.r + weights.g + weights.b;
    return half4(grey(sum <= 0.0 ? 0.0 : sqrt(dot(weights, d * d) / sum)));
}
".into()),
        prog("diffAlpha", true, &["threshold", "softness", "black", "white", "gamma"], "uniform float threshold;
uniform float softness;
uniform float black;
uniform float white;
uniform float gamma;
half4 main(half4 m, half4 c) {
    float a = float(c.a);
    if (a <= 0.0) { return half4(grey(0.0)); }
    float d = float(m.r);
    float r = softness <= 1e-6 ? (d > threshold ? 1.0 : 0.0) : clamp((d - threshold) / softness, 0.0, 1.0);
    float t = clamp((r - black) / max(white - black, 1e-6), 0.0, 1.0);
    t = t <= 0.0 ? 0.0 : pow(t, gamma);
    return half4(grey(t * a));
}
".into()),
        prog("despill", true, &["screen", "local", "channel", "balance", "method", "amount", "replace", "keepLuma"], format!(
            "{screen}{despill_u}{MEASURE}half4 main(half4 m, half4 c) {{
    if (float(c.a) <= 0.0) {{ return c; }}
{despill_body}    return half4(float4(fromCg(o) * u.a, u.a));
}}
")),
        prog("spill", true, &["screen", "local", "channel", "balance", "method", "amount", "replace", "keepLuma"], format!(
            "{screen}{despill_u}{MEASURE}half4 main(half4 m, half4 c) {{
    if (float(c.a) <= 0.0) {{ return half4(grey(0.0)); }}
{despill_body}    return half4(grey(sp * u.a));
}}
")),
        prog("edgeWeight", false, &["solid"], "uniform float solid;
half4 main(half4 c) {
    float4 u = unpre(float4(c));
    float w = u.a > 0.0 && u.a >= solid ? 1.0 : 0.0;
    return half4(float4(u.rgb * w, w));
}
".into()),
        prog("edgeExtend", true, &["amount", "solid", "core", "keepLuma", "bgLuma"], format!("uniform float amount;
uniform float solid;
uniform float core;
uniform float keepLuma;
uniform float bgLuma;
half4 main(half4 m, half4 c) {{
    float4 p = float4(c);
    float a = p.a;
    float w = float(m.a);
    if (a <= 0.0 || w <= 1e-4) {{ return c; }}
    float3 s = p.rgb / a;
    float k = 0.0;
    if (a < solid) {{ k = amount * min(2.0 * w, 1.0); }}
    else if (core > 0.5 && w < core) {{ k = amount * clamp((core - w) / (core - 0.5), 0.0, 1.0); }}
    else {{ return c; }}
    float3 f = float3(m.rgb) / w;
    if (keepLuma > 0.0) {{
        float3 yw = float3({}, {}, {});
        float3 xf = toCg(f);
        float yp = dot(toCg(s), yw);
        float est = a < solid ? max((yp - (1.0 - a) * bgLuma) / max(a, 0.05), 0.0) : yp;
        float g = 1.0 + keepLuma * (clamp(est / max(dot(xf, yw), 1e-4), 0.0, 4.0) - 1.0);
        f = fromCg(xf * g);
    }}
    return half4(float4((s + k * (f - s)) * a, a));
}}
", super::lit(y[0]), super::lit(y[1]), super::lit(y[2]))),
        prog("wrapBand", false, &[], "half4 main(half4 c) {\n    return half4(grey(1.0 - float(c.a)));\n}\n".into()),
        prog("lightWrap", true, &["amount", "blend"], "uniform float amount;
uniform float blend;
half4 main(half4 m, half4 c) {
    float4 p = float4(c);
    float a = p.a;
    if (a <= 0.0) { return c; }
    float3 l = float3(m.rgb) * amount;
    if (blend < 0.5) { return half4(float4(p.rgb + l * a, a)); }
    float3 f = p.rgb / a;
    return half4(float4((f + l - f * l) * a, a));
}
".into()),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    const W: Working = Working::AcesCg;
    const S: Screen = Screen { color: [0.02, 0.16, 0.03], channel: 1, balance: 0.5 };

    #[test]
    fn a_screen_pixel_keys_to_zero_and_a_foreground_pixel_to_one() {
        assert_eq!(S.raw(S.color, S.color, 1.0), 0.0);
        assert_eq!(S.raw([0.3, 0.2, 0.15], S.color, 1.0), 1.0);
        // Half as much screen difference: half transparent.
        // Half the screen's difference d(s) = 0.135: half transparent.
        assert!((S.raw([0.1, 0.1 + 0.0675, 0.1], S.color, 1.0) - 0.5).abs() < 1e-5);
    }

    /// `edge.inset` (uniform `core`): a near-opaque rim pixel carrying the old background's colour takes the deeper foreground's
    /// colour where less than `core` of the reach is solid; off, or deep in the solid, it is untouched; alpha never changes.
    #[test]
    fn edge_inset_repaints_the_near_opaque_rim_only() {
        let rim = pre([0.6, 0.5, 0.8], 0.99);
        let fill = [0.1 * 0.7, 0.3 * 0.7, 0.1 * 0.7, 0.7];
        let u = |core: f32| vec![("solid", vec![0.95]), ("amount", vec![1.0]), ("core", vec![core])];
        assert_eq!(eval("edgeExtend", &u(0.0), W, fill, rim), Some(rim), "off: unchanged");
        let o = eval("edgeExtend", &u(0.9), W, fill, rim).unwrap();
        let s = unpre(o);
        assert!(o[3] == rim[3] && (s[0] - 0.35).abs() < 1e-4 && (s[1] - 0.4).abs() < 1e-4 && (s[2] - 0.45).abs() < 1e-4, "half pulled: {s:?}");
        let deep = [0.1 * 0.95, 0.3 * 0.95, 0.1 * 0.95, 0.95];
        assert_eq!(eval("edgeExtend", &u(0.9), W, deep, rim), Some(rim), "deep in the solid: unchanged");
    }

    /// `edge.keepLuma`: the repainted colour is the fill's chroma at the pixel's own brightness (a rim pixel keeps its luma; a
    /// partial pixel's luma is first cleared of the old background's share), so the fill's flat average does not wipe the texture.
    #[test]
    fn edge_keep_luma_repaints_the_chroma_and_keeps_the_pixels_brightness() {
        let y = ap1_y();
        let luma = |x: [f32; 3]| y[0] * x[0] + y[1] * x[1] + y[2] * x[2];
        let fill = [0.1 * 0.7, 0.3 * 0.7, 0.1 * 0.7, 0.7];
        let u = |keep: f32| vec![("solid", vec![0.95]), ("amount", vec![1.0]), ("core", vec![0.9]), ("keepLuma", vec![keep]), ("bgLuma", vec![0.8])];
        let rim = pre([0.6, 0.5, 0.8], 0.99);
        let flat = unpre(eval("edgeExtend", &u(0.0), W, [fill[0], fill[1], fill[2], 0.5], rim).unwrap());
        let kept = unpre(eval("edgeExtend", &u(1.0), W, [fill[0], fill[1], fill[2], 0.5], rim).unwrap());
        let (to, from) = (to_cg(W, [0.6, 0.5, 0.8]), to_cg(W, [kept[0], kept[1], kept[2]]));
        assert!((luma(to) - luma(from)).abs() < 2e-3 * 4.0, "rim luma kept: {} vs {}", luma(to), luma(from));
        assert!(kept[1] > kept[2] && kept[1] > kept[0], "chroma is the fill's green: {kept:?}");
        assert!(flat[0] != kept[0], "off: the fill's flat colour");
        // A half transparent pixel over a bright background: its luma is the foreground's share only.
        let part = pre([0.6, 0.6, 0.6], 0.5);
        let o = unpre(eval("edgeExtend", &u(1.0), W, [fill[0], fill[1], fill[2], 0.9], part).unwrap());
        let est = ((luma(to_cg(W, [0.6, 0.6, 0.6])) - 0.5 * 0.8) / 0.5).max(0.0);
        assert!((luma(to_cg(W, [o[0], o[1], o[2]])) - est.min(luma(to_cg(W, [0.1, 0.3, 0.1])) * 4.0)).abs() < 5e-3, "partial luma {} vs {est}", luma(to_cg(W, [o[0], o[1], o[2]])));
    }

    #[test]
    fn a_difference_key_ramps_the_distance_from_the_clean_plate() {
        let n = [0.2, 0.3, 0.1];
        assert_eq!(diff_distance(n, n, [1.0; 3]), 0.0);
        // 0.3 off in red alone: RMS over three equal weights is 0.3 / √3; with only red weighted it is 0.3.
        assert!((diff_distance([0.5, 0.3, 0.1], n, [1.0; 3]) - 0.3 / 3f32.sqrt()).abs() < 1e-6);
        assert!((diff_distance([0.5, 0.3, 0.1], n, [1.0, 0.0, 0.0]) - 0.3).abs() < 1e-6);
        assert_eq!(diff_ramp(0.01, 0.02, 0.1), 0.0);
        assert!((diff_ramp(0.07, 0.02, 0.1) - 0.5).abs() < 1e-6);
        assert_eq!(diff_ramp(0.5, 0.02, 0.1), 1.0);
        assert_eq!(diff_ramp(0.03, 0.02, 0.0), 1.0);
        let u: Vec<(&str, Vec<f32>)> = vec![("threshold", vec![0.02]), ("softness", vec![0.1]), ("white", vec![1.0]), ("gamma", vec![1.0])];
        assert_eq!(eval("diffAlpha", &u, W, grey(0.07), [0.1, 0.1, 0.1, 0.5]), Some(grey(0.25)));
        let d = eval("diffDistance", &[("weights", vec![1.0, 0.0, 0.0])], W, pre(n, 1.0), pre([0.5, 0.3, 0.1], 0.5)).unwrap();
        assert!((d[0] - 0.3).abs() < 1e-6 && d[3] == 1.0);
    }

    #[test]
    fn despill_of_the_screen_colour_takes_its_green_to_the_limit() {
        let (o, sp) = despill(&S, S.color, 2, 1.0, [0.0; 3], false);
        assert!((0..3).all(|k| (o[k] - [0.02, 0.03, 0.03][k]).abs() < 1e-6), "{o:?}");
        assert!((sp - 0.13).abs() < 1e-6);
        // A pixel without spill is untouched; keepLuma puts the removed luminance back as grey.
        assert_eq!(despill(&S, [0.4, 0.2, 0.3], 0, 1.0, [0.0; 3], false).0, [0.4, 0.2, 0.3]);
        let (k, _) = despill(&S, S.color, 2, 1.0, [0.0; 3], true);
        let y = ap1_y();
        let lum = |c: [f32; 3]| c[0] * y[0] + c[1] * y[1] + c[2] * y[2];
        assert!((lum(k) - lum(S.color)).abs() < 1e-6);
    }

    #[test]
    fn key_alpha_scales_by_the_plate_alpha_and_light_wrap_adds_in_the_edge() {
        let u: Vec<(&str, Vec<f32>)> = vec![("screen", S.color.to_vec()), ("channel", vec![1.0]), ("balance", vec![0.5]), ("gain", vec![1.0]), ("white", vec![1.0]), ("gamma", vec![1.0])];
        let a = eval("keyAlpha", &u, W, [0.0; 4], [0.15, 0.1, 0.075, 0.5]).unwrap();
        assert_eq!(a, grey(0.5));
        let wrap = eval("lightWrap", &[("amount", vec![0.5]), ("blend", vec![0.0])], W, [0.2, 0.2, 0.2, 1.0], [0.1, 0.1, 0.1, 0.5]).unwrap();
        assert!((wrap[0] - (0.1 + 0.1 * 0.5)).abs() < 1e-6 && wrap[3] == 0.5);
    }
}
