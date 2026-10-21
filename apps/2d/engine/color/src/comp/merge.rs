//! `merge` (COMP_CORE §2.1): a layer A (`m`, the SVG `in`) merged onto the running result B (`c`, `in2`), both
//! premultiplied. Ops 0–15 are exact on premultiplied data; 16–22 are the W3C separable blend modes `B(cb, cs)` on
//! unpremultiplied colour, composited source-over exactly as CSS `mix-blend-mode`:
//! `co = a(1 − αb) + b(1 − αa) + αa·αb·B(cb, cs)`, `αo = αa + αb − αa·αb`.
//! `display` = 1 runs the op on display-encoded values (sRGB curve, Rec.709 primaries: both inputs converted from the
//! working space and the result back); `amount` (the layer's `mix`; SkSL cannot name a uniform `mix`, its built-in)
//! blends the merge over B in the same space: `B + amount · (merge − B)`.

use super::{Program, from_display, pre, to_display, unpre};
use crate::pipeline::Working;

/// The ops in `op` index order.
pub const MERGE_OPS: [&str; 23] = [
    "over", "under", "in", "out", "atop", "xor", "plus", "multiply", "screen", "min", "max", "difference", "minus", "from",
    "stencil", "mask", "overlay", "softLight", "hardLight", "colorDodge", "colorBurn", "lighten", "darken",
];

/// The first display-only op (16 … 22).
pub const FIRST_DISPLAY_OP: usize = 16;

/// W3C blend `B(cb, cs)` of display op `o` on one channel (backdrop `cb`, source `cs`).
fn blend(o: usize, cb: f32, cs: f32) -> f32 {
    let multiply = |b: f32, s: f32| b * s;
    let screen = |b: f32, s: f32| b + s - b * s;
    let hard = |b: f32, s: f32| if s <= 0.5 { multiply(b, 2.0 * s) } else { screen(b, 2.0 * s - 1.0) };
    match o {
        16 => hard(cs, cb),
        17 => {
            if cs <= 0.5 {
                cb - (1.0 - 2.0 * cs) * cb * (1.0 - cb)
            } else {
                let d = if cb <= 0.25 { ((16.0 * cb - 12.0) * cb + 4.0) * cb } else { cb.max(0.0).sqrt() };
                cb + (2.0 * cs - 1.0) * (d - cb)
            }
        }
        18 => hard(cb, cs),
        19 => if cb <= 0.0 { 0.0 } else if cs >= 1.0 { 1.0 } else { (cb / (1.0 - cs)).min(1.0) },
        20 => if cb >= 1.0 { 1.0 } else if cs <= 0.0 { 0.0 } else { 1.0 - ((1.0 - cb) / cs).min(1.0) },
        21 => cb.max(cs),
        _ => cb.min(cs),
    }
}

/// Op `o` on premultiplied `a` (the layer) and `b` (the result).
fn op(o: usize, a: [f32; 4], b: [f32; 4]) -> [f32; 4] {
    let (aa, ab) = (a[3], b[3]);
    let over_a = aa + ab - aa * ab;
    let each = |f: &dyn Fn(f32, f32) -> f32| -> [f32; 4] { std::array::from_fn(|k| f(a[k], b[k])) };
    let rgb = |f: &dyn Fn(f32, f32) -> f32, alpha: f32| -> [f32; 4] { [f(a[0], b[0]), f(a[1], b[1]), f(a[2], b[2]), alpha] };
    match o {
        0 => each(&|a, b| a + b * (1.0 - aa)),
        1 => each(&|a, b| b + a * (1.0 - ab)),
        2 => each(&|a, _| a * ab),
        3 => each(&|a, _| a * (1.0 - ab)),
        4 => rgb(&|a, b| a * ab + b * (1.0 - aa), ab),
        5 => each(&|a, b| a * (1.0 - ab) + b * (1.0 - aa)),
        // Plus adds light; its alpha stays a coverage (≤ 1, CSS plus-lighter), so the result is still a premultiplied picture:
        // opaque passes added into a beauty would otherwise carry alpha n, and a later `over` subtracts n − 1 times what is below.
        6 => rgb(&|a, b| a + b, (aa + ab).min(1.0)),
        7 => rgb(&|a, b| a * b + a * (1.0 - ab) + b * (1.0 - aa), over_a),
        8 => each(&|a, b| a + b - a * b),
        9 => each(&|a, b| a.min(b)),
        10 => each(&|a, b| a.max(b)),
        11 => rgb(&|a, b| (a - b).abs(), over_a),
        12 => rgb(&|a, b| a - b, over_a),
        13 => rgb(&|a, b| b - a, over_a),
        14 => each(&|_, b| b * (1.0 - aa)),
        15 => each(&|_, b| b * aa),
        _ => {
            let (cs, cb) = (unpre(a), unpre(b));
            let ch = |k: usize| a[k] * (1.0 - ab) + b[k] * (1.0 - aa) + aa * ab * blend(o, cb[k], cs[k]);
            [ch(0), ch(1), ch(2), over_a]
        }
    }
}

/// Premultiplied working → premultiplied display-encoded, and back.
fn disp(w: Working, p: [f32; 4], forward: bool) -> [f32; 4] {
    if p[3] <= 0.0 {
        return p;
    }
    let u = unpre(p);
    let x = [u[0], u[1], u[2]];
    pre(if forward { to_display(w, x) } else { from_display(w, x) }, u[3])
}

/// The CPU twin of the `merge` program: op `o` (MERGE_OPS index) of the layer `a` onto the result `b`.
pub fn merge(o: usize, a: [f32; 4], b: [f32; 4], mix: f32, display: bool, w: Working) -> [f32; 4] {
    let (a, b) = if display { (disp(w, a, true), disp(w, b, true)) } else { (a, b) };
    let r = op(o.min(MERGE_OPS.len() - 1), a, b);
    let r: [f32; 4] = std::array::from_fn(|k| b[k] + mix * (r[k] - b[k]));
    if display { disp(w, r, false) } else { r }
}

pub(crate) fn program() -> Program {
    let code = format!(
        "{}uniform float op;
uniform float amount;
uniform float display;
float hardL(float b, float s) {{ return s <= 0.5 ? b * 2.0 * s : b + (2.0 * s - 1.0) - b * (2.0 * s - 1.0); }}
float blendCh(int o, float cb, float cs) {{
    if (o == 16) {{ return hardL(cs, cb); }}
    if (o == 17) {{
        if (cs <= 0.5) {{ return cb - (1.0 - 2.0 * cs) * cb * (1.0 - cb); }}
        float d = cb <= 0.25 ? ((16.0 * cb - 12.0) * cb + 4.0) * cb : sqrt(max(cb, 0.0));
        return cb + (2.0 * cs - 1.0) * (d - cb);
    }}
    if (o == 18) {{ return hardL(cb, cs); }}
    if (o == 19) {{ return cb <= 0.0 ? 0.0 : cs >= 1.0 ? 1.0 : min(cb / (1.0 - cs), 1.0); }}
    if (o == 20) {{ return cb >= 1.0 ? 1.0 : cs <= 0.0 ? 0.0 : 1.0 - min((1.0 - cb) / cs, 1.0); }}
    if (o == 21) {{ return max(cb, cs); }}
    return min(cb, cs);
}}
float4 mergeOp(int o, float4 a, float4 b) {{
    float aa = a.a;
    float ab = b.a;
    float ov = aa + ab - aa * ab;
    if (o == 0) {{ return a + b * (1.0 - aa); }}
    if (o == 1) {{ return b + a * (1.0 - ab); }}
    if (o == 2) {{ return a * ab; }}
    if (o == 3) {{ return a * (1.0 - ab); }}
    if (o == 4) {{ return float4(a.rgb * ab + b.rgb * (1.0 - aa), ab); }}
    if (o == 5) {{ return a * (1.0 - ab) + b * (1.0 - aa); }}
    if (o == 6) {{ return float4(a.rgb + b.rgb, min(aa + ab, 1.0)); }}
    if (o == 7) {{ return float4(a.rgb * b.rgb + a.rgb * (1.0 - ab) + b.rgb * (1.0 - aa), ov); }}
    if (o == 8) {{ return a + b - a * b; }}
    if (o == 9) {{ return min(a, b); }}
    if (o == 10) {{ return max(a, b); }}
    if (o == 11) {{ return float4(abs(a.rgb - b.rgb), ov); }}
    if (o == 12) {{ return float4(a.rgb - b.rgb, ov); }}
    if (o == 13) {{ return float4(b.rgb - a.rgb, ov); }}
    if (o == 14) {{ return b * (1.0 - aa); }}
    if (o == 15) {{ return b * aa; }}
    float3 cs = unpre(a).rgb;
    float3 cb = unpre(b).rgb;
    float3 f = float3(blendCh(o, cb.r, cs.r), blendCh(o, cb.g, cs.g), blendCh(o, cb.b, cs.b));
    return float4(a.rgb * (1.0 - ab) + b.rgb * (1.0 - aa) + aa * ab * f, ov);
}}
float4 disp(float4 p, bool fwd) {{
    if (p.a <= 0.0) {{ return p; }}
    float3 x = p.rgb / p.a;
    return float4((fwd ? toDisp(x) : fromDisp(x)) * p.a, p.a);
}}
half4 main(half4 m, half4 c) {{
    bool d = display > 0.5;
    float4 a = d ? disp(float4(m), true) : float4(m);
    float4 b = d ? disp(float4(c), true) : float4(c);
    float4 r = mergeOp(int(min(op, 22.0) + 0.5), a, b);
    r = b + amount * (r - b);
    return half4(d ? disp(r, false) : r);
}}
",
        super::prelude()
    );
    Program { name: "merge", blender: true, code, uniforms: &["op", "amount", "display"] }
}

#[cfg(test)]
mod tests {
    use super::*;
    const W: Working = Working::AcesCg;

    #[test]
    fn porter_duff_identities() {
        let a = [0.3, 0.2, 0.1, 0.5];
        let b = [0.1, 0.4, 0.2, 0.8];
        let over = merge(0, a, b, 1.0, false, W);
        assert_eq!(over, [0.3 + 0.1 * 0.5, 0.2 + 0.4 * 0.5, 0.1 + 0.2 * 0.5, 0.5 + 0.8 * 0.5]);
        // Over a transparent B is A; plus adds alpha up to 1 (colour unclamped); mix 0 is B.
        assert_eq!(merge(0, a, [0.0; 4], 1.0, false, W), a);
        assert_eq!(merge(6, [0.5, 0.5, 0.5, 0.7], [0.5, 0.5, 0.5, 0.6], 1.0, false, W), [1.0, 1.0, 1.0, 1.0]);
        assert_eq!(merge(6, [2.0, 0.5, 0.0, 1.0], [0.5, 0.5, 0.5, 1.0], 1.0, false, W), [2.5, 1.0, 0.5, 1.0]);
        assert_eq!(merge(6, [0.2, 0.2, 0.2, 0.3], [0.1, 0.1, 0.1, 0.4], 1.0, false, W)[3], 0.3 + 0.4);
        assert_eq!(merge(7, a, b, 0.0, false, W), b);
        // under is over with the inputs swapped; stencil + mask split B by A's alpha.
        assert_eq!(merge(1, a, b, 1.0, false, W), merge(0, b, a, 1.0, false, W));
        let (s, m) = (merge(14, a, b, 1.0, false, W), merge(15, a, b, 1.0, false, W));
        for k in 0..4 {
            assert!((s[k] + m[k] - b[k]).abs() < 1e-6);
        }
        assert_eq!(merge(4, a, b, 1.0, false, W)[3], b[3]);
    }

    #[test]
    fn display_modes_on_opaque_inputs_are_the_w3c_formulas() {
        // Opaque: co = B(cb, cs). Multiply-like hardLight with cs ≤ 0.5: cb · 2cs.
        let (a, b) = ([0.25, 0.75, 0.5, 1.0], [0.5, 0.5, 0.2, 1.0]);
        let r = merge(18, a, b, 1.0, false, W);
        assert!((r[0] - 0.5 * 0.5).abs() < 1e-6 && (r[1] - (0.5 + 0.5 - 0.5 * 0.5)).abs() < 1e-6);
        assert_eq!(merge(21, a, b, 1.0, false, W), [0.5, 0.75, 0.5, 1.0]);
        // Display round trip: lighten of a colour with itself is the colour, through the encode and back.
        let c = [0.18, 0.05, 0.4, 1.0];
        let r = merge(21, c, c, 1.0, true, W);
        assert!((0..3).all(|k| (r[k] - c[k]).abs() < 1e-5), "{r:?}");
    }
}
