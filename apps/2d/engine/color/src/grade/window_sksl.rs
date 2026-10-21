//! The SkSL twin of window.rs: one shader per matted layer that draws all its windows into one channel of the matte image
//! (mod.rs "The matte seam"). `half4 main(float2 p)` in filter space; `box` (x, y, w, h: the layer's border box, set by the
//! renderer) gives the frame's size and origin. It reads no picture, so the renderer runs it as a plain shader filling the
//! layer's box, not as an image filter (anyrender_skia `runtime_window_filter`: Skia's runtime-shader builder takes no uniform
//! arrays, so the uniforms are packed by offset). The code depends on the structure only (which shapes, in which order,
//! with which modes, how many polygon points); every parameter is in `wp` (the windows' [`Window::slots`], one after the
//! other) and `dither`.
use super::window::{Kind, Mode, Window};
use crate::view::Sksl;
use std::fmt::Write;

/// The dither amplitude of an 8-bit output: one code step.
pub const DITHER_8BIT: f32 = 1.0 / 255.0;

const HELPERS: &str = "float wIgn(float2 p) { return fract(52.982918 * fract(0.06711056 * p.x + 0.00583715 * p.y)); }\n\
float2 wPlace(float2 f, float2 sz, float4 xf, float2 rot, float2 pv) {\n    float2 v = (f - pv) * sz * xf.zw;\n    \
return pv * sz + xf.xy * sz + float2(rot.x * v.x - rot.y * v.y, rot.y * v.x + rot.x * v.y);\n}\n";

/// The shape's coverage `c` at `q` (px in the frame) for the window whose slots start at `b`.
fn shape(w: &Window, b: usize) -> String {
    let at = |k: usize| format!("wp[{}]", b + k);
    let place = |k: usize| format!("wPlace(float2({}, {}), sz, xf, rot, pv)", at(k), at(k + 1));
    match w.kind() {
        Kind::Ellipse => format!(
            "float2 ce = {}; float2 r = float2({}, {}) * sz * xf.zw; float2 v = q - ce;\n        \
             float2 u = float2({c} * v.x + {s} * v.y, -{s} * v.x + {c} * v.y);\n        \
             float k0 = length(u / r); float k1 = length(u / (r * r));\n        \
             float d = k1 < 1e-6 ? min(r.x, r.y) : -(k0 * (k0 - 1.0) / k1);\n        float c = smoothstep(-so, si, d);",
            place(11), at(13), at(14), c = at(15), s = at(16)
        ),
        Kind::Band => format!(
            "float2 a = {}; float2 e = {} - a;\n        float dist = abs(dot(q - a, float2(-e.y, e.x))) / max(length(e), 1e-9);\n        \
             float c = smoothstep(-so, si, {} * sz.y * (xf.z + xf.w) * 0.25 - dist);",
            place(11), place(13), at(15)
        ),
        Kind::Ramp => format!("float2 a = {}; float2 e = {} - a;\n        float c = clamp(1.0 - dot(q - a, e) / max(dot(e, e), 1e-9), 0.0, 1.0);", place(11), place(13)),
        Kind::Poly(n) => format!(
            "float dm = 1e9; bool ins = false;\n        float2 pa = wPlace(float2({}, {}), sz, xf, rot, pv);\n        \
             for (int k = 0; k < {n}; k++) {{\n            \
             float2 pb = wPlace(float2(wp[{b} + 11 + 2 * k], wp[{b} + 12 + 2 * k]), sz, xf, rot, pv);\n            \
             float2 e = pb - pa; float t = clamp(dot(q - pa, e) / max(dot(e, e), 1e-12), 0.0, 1.0);\n            \
             dm = min(dm, length(q - pa - e * t));\n            \
             if ((pa.y > q.y) != (pb.y > q.y) && q.x < (pb.x - pa.x) * (q.y - pa.y) / (pb.y - pa.y) + pa.x) {{ ins = !ins; }}\n            \
             pa = pb;\n        }}\n        float c = smoothstep(-so, si, ins ? dm : -dm);",
            at(11 + 2 * (n - 1)), at(12 + 2 * (n - 1))
        ),
    }
}

/// The shader that draws `ws` into the channel selected by `mask` (a `float3` like `float3(0.0, 1.0, 0.0)`), with its uniforms
/// (`wp` the slots, `dither` the noise amplitude: [`DITHER_8BIT`]).
pub(super) fn window_shader(ws: &[Window], mask: &str) -> Sksl {
    let slots: Vec<f32> = ws.iter().flat_map(Window::slots).collect();
    let mut body = String::new();
    let mut b = 0;
    for w in ws {
        let join = match w.mode {
            Mode::Add => "acc = max(acc, c);",
            Mode::Subtract => "acc = acc * (1.0 - c);",
            Mode::Intersect => "acc = acc * c;",
        };
        let _ = write!(
            body,
            "    {{\n        float4 xf = float4(wp[{b3}], wp[{b4}], wp[{b5}], wp[{b6}]); float2 rot = float2(wp[{b7}], wp[{b8}]); float2 pv = float2(wp[{b9}], wp[{b10}]);\n        \
             float si = max(wp[{b}] * sz.y, 0.5); float so = max(wp[{b1}] * sz.y, 0.5);\n        {}\n        {}c *= wp[{b2}];\n        {join}\n    }}\n",
            shape(w, b),
            if w.invert { "c = 1.0 - c; " } else { "" },
            b1 = b + 1, b2 = b + 2, b3 = b + 3, b4 = b + 4, b5 = b + 5, b6 = b + 6, b7 = b + 7, b8 = b + 8, b9 = b + 9, b10 = b + 10
        );
        b += w.slots().len();
    }
    let code = format!(
        "uniform float4 box;\nuniform float dither;\nuniform float wp[{}];\n{HELPERS}\
         half4 main(float2 p) {{\n    float2 sz = box.zw; float2 q = p - box.xy; float acc = 0.0;\n{body}    \
         float2 px = floor(q);\n    if (acc > 0.0 && acc < 1.0) {{ acc = clamp(acc + (wIgn(px) + wIgn(px + float2(37.0, 17.0)) - 1.0) * dither, 0.0, 1.0); }}\n    \
         return half4(half3({mask} * acc), 1.0);\n}}\n",
        slots.len()
    );
    Sksl { code, uniforms: vec![("wp", slots), ("dither", vec![DITHER_8BIT])] }
}
