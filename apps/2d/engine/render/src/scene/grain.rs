//! Film grain on a layer (the `grain` effect, fields.py): a GPU shader over the layer's own look, after its other
//! effects and colour, so the grain sits on what you see and only where the layer is (its alpha). A grain cell is
//! `size` px of the composition (scaled with the preview like any length), placed from the layer's box, so it moves
//! with the layer; `smooth` blends the cells into soft round specks (off: square cells, the first look); `frame`
//! (eval.rs: the frame number now) changes the picture each frame unless `still` is on.
//! Same seed, same frame, same grain: preview and export draw it alike.

use super::eval::Item;
use super::stage::escape;

type R<T> = Result<T, String>;

/// SkSL shared with rough.rs: `h`, a cheap hash (Dave Hoskins' hash12, no sine: steady at large coordinates) → a
/// lattice point's value in 0..1, and `gn`, gradient noise: a random slope at each lattice point, blended (quintic). Its
/// specks are round, with no plateaus at the lattice points, so no grid shows at any size (value noise, the corners'
/// values blended, still reads as squares). About -0.7..0.7, spread 0.22.
macro_rules! noise_sksl {
    () => {
        "float h(float2 c, float k) { float3 p = fract(float3(c.xyx) * 0.1031 + k * 0.1373); p += dot(p, p.yzx + 33.33); return fract((p.x + p.y) * p.z); }
float slope(float2 i, float2 f, float k) { float a = h(i, k) * 6.2831853; return dot(float2(cos(a), sin(a)), f); }
float gn(float2 q, float k) {
    float2 i = floor(q); float2 f = fract(q); float2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    return mix(mix(slope(i, f, k), slope(i + float2(1.0, 0.0), f - float2(1.0, 0.0), k), u.x),
               mix(slope(i + float2(0.0, 1.0), f - float2(0.0, 1.0), k), slope(i + float2(1.0, 1.0), f - float2(1.0, 1.0), k), u.x), u.y);
}
"
    };
}
pub(crate) use noise_sksl;

pub(crate) const PROGRAM: &str = concat!("uniform shader src; uniform float4 box; uniform float size; uniform float amount; uniform float seed; uniform float frame; uniform float colour; uniform float soft;
", noise_sksl!(), "
// Smooth: gradient noise, soft round specks (1.33x: as strong as the cells). Off: each cell its own value, square cells (the first look).
float g(float2 q, float k) { return soft < 0.5 ? h(floor(q), k) - 0.5 : 1.33 * gn(q, k); }
half4 main(float2 p) {
    float4 c = float4(src.eval(p));
    if (c.a <= 0.0) { return half4(c); }
    float2 q = (p - box.xy) / max(size, 0.5) + float2(mod(frame, 997.0) * 113.0, mod(frame, 991.0) * 71.0) + seed * 17.0;
    float n = g(q, 0.0);
    float3 d = colour > 0.5 ? float3(n, g(q, 1.0), g(q, 2.0)) : float3(n);
    float3 rgb = c.rgb / c.a;
    // Strongest in the mid-tones, as film's: half as much in deep black or pure white.
    float l = dot(rgb, float3(0.2126, 0.7152, 0.0722));
    rgb = clamp(rgb + d * amount * (0.5 + 2.0 * l * (1.0 - l)), 0.0, 1.0);
    return half4(float4(rgb * c.a, c.a));
}");

/// The layer's look under its grain effects (unchanged when it has none): one filter per grain, in order.
pub fn wrap(it: &Item, mut body: String) -> R<String> {
    for (i, g) in it.effects.iter().filter(|e| e.kind == "grain").enumerate() {
        let size = g.num("size");
        if !(size > 0.0) {
            return Err(format!("{}.size: a grain's size must be above 0 px (got {size})", g.id));
        }
        let frame = if g.on("still") { 0.0 } else { g.num("frame") };
        let uniforms = format!("*size {size};amount {};seed {};frame {frame};colour {};soft {}", g.num("amount"), g.num("seed"), u8::from(g.on("colour")), u8::from(g.on("smooth")));
        let id: String = format!("rgr{i}-{}", it.id.chars().map(|c| if c.is_ascii_alphanumeric() || c == '_' { c.to_string() } else { format!("-{:x}-", c as u32) }).collect::<String>());
        body = format!(
            "<svg width=\"0\" height=\"0\" style=\"position:absolute;left:0;top:0;\"><defs><filter id=\"{id}\" color-interpolation-filters=\"sRGB\">\
             <feshader effect=\"grain\" in=\"SourceGraphic\" result=\"grain\" radius=\"0\" grow=\"0\" uniforms=\"{uniforms}\">{}</feshader></filter></defs></svg>\
             <div style=\"position:absolute;left:0;top:0;width:100%;height:100%;filter:url(#{id});\">{body}</div>",
            escape(PROGRAM)
        );
    }
    Ok(body)
}
