//! Film grain on a layer (the `grain` effect, fields.py): a GPU shader over the layer's own look, after its other
//! effects and colour, so the grain sits on what you see and only where the layer is (its alpha). A grain cell is
//! `size` px of the composition (scaled with the preview like any length), placed from the layer's box, so it moves
//! with the layer; `frame` (eval.rs: the frame number now) changes the picture each frame unless `still` is on.
//! Same seed, same frame, same grain: preview and export draw it alike.

use super::eval::Item;
use super::stage::escape;

type R<T> = Result<T, String>;

/// A cheap hash (Dave Hoskins' hash12, no sine: steady at large coordinates) → a cell's value in 0..1.
pub(crate) const PROGRAM: &str = "uniform shader src; uniform float4 box; uniform float size; uniform float amount; uniform float seed; \
uniform float frame; uniform float colour;
float h(float2 c, float k) { float3 p = fract(float3(c.xyx) * 0.1031 + k * 0.1373); p += dot(p, p.yzx + 33.33); return fract((p.x + p.y) * p.z); }
half4 main(float2 p) {
    float4 c = float4(src.eval(p));
    if (c.a <= 0.0) { return half4(c); }
    float2 cell = floor((p - box.xy) / max(size, 0.5)) + float2(mod(frame, 997.0) * 113.0, mod(frame, 991.0) * 71.0) + seed * 17.0;
    float n = h(cell, 0.0) - 0.5;
    float3 d = colour > 0.5 ? float3(n, h(cell, 1.0) - 0.5, h(cell, 2.0) - 0.5) : float3(n);
    float3 rgb = c.rgb / c.a;
    // Strongest in the mid-tones, as film's: half as much in deep black or pure white.
    float l = dot(rgb, float3(0.2126, 0.7152, 0.0722));
    rgb = clamp(rgb + d * amount * (0.5 + 2.0 * l * (1.0 - l)), 0.0, 1.0);
    return half4(float4(rgb * c.a, c.a));
}";

/// The layer's look under its grain effects (unchanged when it has none): one filter per grain, in order.
pub fn wrap(it: &Item, mut body: String) -> R<String> {
    for (i, g) in it.effects.iter().filter(|e| e.kind == "grain").enumerate() {
        let size = g.num("size");
        if !(size > 0.0) {
            return Err(format!("{}.size: a grain's size must be above 0 px (got {size})", g.id));
        }
        let frame = if g.on("still") { 0.0 } else { g.num("frame") };
        let uniforms = format!("*size {size};amount {};seed {};frame {frame};colour {}", g.num("amount"), g.num("seed"), u8::from(g.on("colour")));
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
