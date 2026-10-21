//! LUT nodes on the GPU: the table as a child image (`LutImage`) and the node's SkSL function. 3D tables: tiles
//! of `size × size` (x = red, y = green), blue tile `b` at column `b mod cols`, row `b div cols` (cols = ⌈√size⌉);
//! 1D tables: entry `i` at x = `i mod 4096`, y = `i div 4096`. Interpolation and domain clamping as `lut::apply`.
use super::{HslCurves, LutNode};
use super::sksl::{m3, per_channel, v3};
use crate::view::sksl::f;
use crate::{Interp, Lut};

/// A LUT node's table as an image: `width × height` RGBA floats, row-major from the top.
#[derive(Clone, Debug, PartialEq)]
pub struct LutImage {
    pub width: usize,
    pub height: usize,
    pub rgba: Vec<f32>,
}

const ROW_1D: usize = 4096;

pub(super) fn lut_image(n: &LutNode) -> LutImage {
    match &n.lut {
        Lut::D3(l) => {
            let s = l.size;
            let cols = (s as f64).sqrt().ceil() as usize;
            let (w, h) = (cols * s, s.div_ceil(cols) * s);
            let mut rgba = vec![0.0; w * h * 4];
            for (i, v) in l.data.iter().enumerate() {
                let (r, g, b) = (i % s, i / s % s, i / (s * s));
                let (x, y) = (b % cols * s + r, b / cols * s + g);
                rgba[(y * w + x) * 4..][..4].copy_from_slice(&[v[0], v[1], v[2], 1.0]);
            }
            LutImage { width: w, height: h, rgba }
        }
        Lut::D1(l) => {
            let (n, w) = (l.data.len(), l.data.len().min(ROW_1D));
            let mut rgba = vec![0.0; w * n.div_ceil(w) * 4];
            l.data.iter().enumerate().for_each(|(i, v)| rgba[i * 4..][..4].copy_from_slice(&[v[0], v[1], v[2], 1.0]));
            LutImage { width: w, height: n.div_ceil(w), rgba }
        }
    }
}

/// The LUT node's function `float3 lutNode<i>(float3 cg)` (its table is the child `lut<i>`).
pub(super) fn lut_code(i: usize, n: &LutNode) -> String {
    let (enc, dec) = (n.to_in.encode.sksl_name(true), n.from_out.decode.sksl_name(false));
    let at = |d: [u8; 3]| format!("lut{i}At(bi + float3({}.0, {}.0, {}.0))", d[0], d[1], d[2]);
    let (fetch, size, min, max, interp) = match &n.lut {
        Lut::D3(l) => {
            let cols = (l.size as f64).sqrt().ceil();
            let fetch = format!(
                "float3 lut{i}At(float3 c) {{ return float3(lut{i}.eval(float2(mod(c.b, {cols:?}) * {s:?} + c.r + 0.5, floor(c.b / {cols:?}) * {s:?} + c.g + 0.5)).rgb); }}\n",
                s = l.size as f64
            );
            let interp = match n.interp {
                Interp::Tetrahedral => {
                    let t = |w: [&str; 4], p: [u8; 3], q: [u8; 3]| {
                        format!("o = ({}) * c000 + ({}) * {} + ({}) * {} + ({}) * c111;", w[0], w[1], at(p), w[2], at(q), w[3])
                    };
                    format!(
                        "    if (fr.r > fr.g) {{\n        if (fr.g > fr.b) {{ {} }}\n        else if (fr.r > fr.b) {{ {} }}\n        else {{ {} }}\n    }}\n    \
                         else if (fr.b > fr.g) {{ {} }}\n    else if (fr.b > fr.r) {{ {} }}\n    else {{ {} }}\n",
                        t(["1.0 - fr.r", "fr.r - fr.g", "fr.g - fr.b", "fr.b"], [1, 0, 0], [1, 1, 0]),
                        t(["1.0 - fr.r", "fr.r - fr.b", "fr.b - fr.g", "fr.g"], [1, 0, 0], [1, 0, 1]),
                        t(["1.0 - fr.b", "fr.b - fr.r", "fr.r - fr.g", "fr.g"], [0, 0, 1], [1, 0, 1]),
                        t(["1.0 - fr.b", "fr.b - fr.g", "fr.g - fr.r", "fr.r"], [0, 0, 1], [0, 1, 1]),
                        t(["1.0 - fr.g", "fr.g - fr.b", "fr.b - fr.r", "fr.r"], [0, 1, 0], [0, 1, 1]),
                        t(["1.0 - fr.g", "fr.g - fr.r", "fr.r - fr.b", "fr.b"], [0, 1, 0], [1, 1, 0]),
                    )
                }
                Interp::Trilinear => format!(
                    "    float3 x0 = mix(mix(c000, {}, fr.r), mix({}, {}, fr.r), fr.g);\n    \
                     float3 x1 = mix(mix({}, {}, fr.r), mix({}, c111, fr.r), fr.g);\n    o = mix(x0, x1, fr.b);\n",
                    at([1, 0, 0]), at([0, 1, 0]), at([1, 1, 0]), at([0, 0, 1]), at([1, 0, 1]), at([0, 1, 1])
                ),
            };
            let interp = format!("    float3 c000 = lut{i}At(bi); float3 c111 = lut{i}At(bi + 1.0);\n{interp}");
            (fetch, l.size, l.min, l.max, interp)
        }
        Lut::D1(l) => {
            let fetch = format!(
                "float3 lut{i}At(float k) {{ float y = floor(k / {w:?}); return float3(lut{i}.eval(float2(k - y * {w:?} + 0.5, y + 0.5)).rgb); }}\n",
                w = ROW_1D as f64
            );
            let ch = |c: &str| format!("mix(lut{i}At(bi.{c}).{c}, lut{i}At(bi.{c} + 1.0).{c}, fr.{c})");
            let interp = format!("    o = float3({}, {}, {});\n", ch("r"), ch("g"), ch("b"));
            (fetch, l.data.len(), l.min, l.max, interp)
        }
    };
    let (lo, hi) = (min.map(f64::from), max.map(f64::from));
    format!(
        "{fetch}float3 lutNode{i}(float3 cg) {{\n    float3 v = {} * cg; v = {};\n    \
         float3 p = clamp((v - {lo}) / ({hi} - {lo}), 0.0, 1.0) * {};\n    float3 bi = min(floor(p), float3({})); float3 fr = p - bi;\n    \
         float3 o;\n{interp}    return {} * {};\n}}\n",
        m3(&n.to_in.matrix), per_channel(&enc, "v"), f((size - 1) as f32), f((size - 2) as f32),
        m3(&n.from_out.matrix), per_channel(&dec, "o"), lo = v3(lo), hi = v3(hi)
    )
}

/// A hue / lum / sat curves operation's tables as one image: row `r` = the r-th table present (`HslCurves::tables`
/// order), `width` = the longest table, texel x = sample x. Multiplier tables hold `y − 1` (half floats keep more
/// of a small number than of one near 1), hue vs hue its degrees.
pub(super) fn hsl_image(c: &HslCurves) -> LutImage {
    let rows: Vec<_> = c.tables().collect();
    let w = rows.iter().map(|(_, t)| t.len()).max().unwrap_or(1);
    let mut rgba = vec![0.0; w * rows.len().max(1) * 4];
    for (r, (k, t)) in rows.iter().enumerate() {
        for (x, y) in t.iter().enumerate() {
            rgba[(r * w + x) * 4..][..4].copy_from_slice(&[y - k.neutral(), 0.0, 0.0, 1.0]);
        }
    }
    LutImage { width: w, height: rows.len().max(1), rgba }
}

/// The table reader of child `lut<i>` (an `hsl_image`): `float hslTable<i>(float x, float row, float n)`, the table
/// in that row (n samples) at x, plus the neutral value the caller adds back.
pub(super) fn hsl_code(i: usize) -> String {
    format!(
        "float hslTable{i}(float x, float row, float n) {{\n    float p = clamp(x, 0.0, 1.0) * (n - 1.0); float k = min(floor(p), n - 2.0);\n    \
         float a = float(lut{i}.eval(float2(k + 0.5, row + 0.5)).r); float b = float(lut{i}.eval(float2(k + 1.5, row + 0.5)).r);\n    \
         return a + (b - a) * (p - k);\n}}\n"
    )
}
