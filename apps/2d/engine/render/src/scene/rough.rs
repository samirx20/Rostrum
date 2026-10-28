//! Rough edges on a layer (the `rough` effect, fields.py): a GPU shader that moves each pixel of the layer's own look
//! by smooth noise, so every edge (a shape's, a letter's, a stroke's, a picture's) wobbles as if drawn by hand. Up to
//! `amount` px of the composition; `size` px is the noise's scale (bumps about that wide); `detail` octaves add finer
//! wobble on top, each half the size and half the reach. The noise is placed from the layer's box, so it moves with the
//! layer and a motion-blur sub-frame or a kept, moved picture (still_runs.rs) sees the same warp. `boil` above 0 picks
//! a new noise every `boil` frames (eval.rs writes the frame number now): the hand-drawn boil. The layer's bounds grow
//! by `amount` so the warp is never cut. The warp reads only inside the visible frame (`view`, given by the painter), so
//! a layer that runs off the frame (a full-frame paper or wash) keeps a clean border instead of notches. Same seed, same frame, same warp: preview and export draw it alike.

use super::eval::Item;
use super::stage::escape;

type R<T> = Result<T, String>;

/// Gradient noise (grain.rs `noise_sksl`) summed over octaves, each half the size and reach, turned so no grid shows;
/// one noise for x, another for y.
pub(crate) const PROGRAM: &str = concat!("uniform shader src; uniform float4 box; uniform float4 view; uniform float size; uniform float amount; uniform float detail; uniform float seed;
", super::grain::noise_sksl!(), "
half4 main(float2 p) {
    float2 q = (p - box.xy) / max(size, 0.5) + float2(mod(seed, 997.0) * 7.31, mod(seed, 991.0) * 5.17);
    float2 d = float2(0.0); float w = 1.0; float total = 0.0;
    for (int i = 0; i < 8; i++) {
        if (float(i) < detail) { d += w * float2(gn(q, 0.0), gn(q, 1.0)); total += w; }
        w *= 0.5;
        q = float2(1.6 * q.x - 1.2 * q.y, 1.2 * q.x + 1.6 * q.y) + 17.7;
    }
    // The sum is about -0.7..0.7, mostly within 0.3: 1.6x spreads it over the reach, clamped to it.
    d = clamp(d / max(total, 0.0001) * 1.6, -1.0, 1.0);
    // Read only inside the visible frame (`view`, the painter's): a layer running off the frame continues past its
    // border instead of showing the gap beyond it.
    return src.eval(clamp(p + d * amount, view.xy + 0.5, view.xy + view.zw - 0.5));
}");

/// The layer's look under its rough effects (unchanged when it has none): one filter per rough, in order.
pub fn wrap(it: &Item, mut body: String) -> R<String> {
    for (i, g) in it.effects.iter().filter(|e| e.kind == "rough").enumerate() {
        let (size, amount, boil) = (g.num("size"), g.num("amount"), g.num("boil"));
        if !(size > 0.0) {
            return Err(format!("{}.size: a rough's size must be above 0 px (got {size})", g.id));
        }
        if !(amount >= 0.0) || !(boil >= 0.0) {
            return Err(format!("{}: a rough's amount and boil must be 0 or more (got {amount}, {boil})", g.id));
        }
        if amount == 0.0 {
            continue;
        }
        // A boil re-seeds every `boil` frames (rounded to whole frames, at least 1).
        let seed = g.num("seed") + if boil > 0.0 { (g.num("frame") / boil.round().max(1.0)).floor() * 13.0 } else { 0.0 };
        let uniforms = format!("*size {size};*amount {amount};detail {};seed {seed}", g.num("detail").clamp(1.0, 8.0).round());
        let id: String = format!("rro{i}-{}", it.id.chars().map(|c| if c.is_ascii_alphanumeric() || c == '_' { c.to_string() } else { format!("-{:x}-", c as u32) }).collect::<String>());
        let reach = amount.ceil() + 1.0;
        body = format!(
            "<svg width=\"0\" height=\"0\" style=\"position:absolute;left:0;top:0;\"><defs><filter id=\"{id}\" color-interpolation-filters=\"sRGB\">\
             <feshader effect=\"rough\" in=\"SourceGraphic\" result=\"rough\" radius=\"{reach}\" grow=\"{reach}\" uniforms=\"{uniforms}\">{}</feshader></filter></defs></svg>\
             <div style=\"position:absolute;left:0;top:0;width:100%;height:100%;filter:url(#{id});\">{body}</div>",
            escape(PROGRAM)
        );
    }
    Ok(body)
}
