//! Stage pieces of S8-C (ENGINE_CONTRACT.md § 4): conic / off-centre gradients, frosted glass (`backdrop`), masks that
//! feather, invert and turn (soft wipes), and video layers. stage.rs calls these; what it can't draw is refused.

use std::fmt::Write;

use serde_json::Value;

use super::eval::Item;
use super::stage::{percent, v};
use super::Node;

type R<T> = Result<T, String>;

/// The CSS gradient of a gradient effect, given its colour stops (`linear`, `radial` or `conic`; centre as fractions of the box).
pub fn gradient(e: &Item, stops: &str) -> String {
    let at = format!("at {:.3}% {:.3}%", e.num("cx") * 100.0, e.num("cy") * 100.0);
    match e.str("style") {
        "radial" => format!("radial-gradient(closest-side {at}, {stops})"),
        "conic" => format!("conic-gradient(from {}deg {at}, {stops})", v(e, "angle")),
        _ => format!("linear-gradient({}deg, {stops})", v(e, "angle")),
    }
}

/// The clip picture showing at time `t`: source frame floor((n − start·fps)·speed) + round(offset·fps), n = floor(t·fps),
/// wrapped when `loop`, else held at the last frame (rostrum2d/video.py `pick` is the same rule). "" with no frames.
pub fn video_picture(node: &Node, t: f64, fps: f64) -> &str {
    let count = node.frames.len() as i64;
    if count == 0 {
        return "";
    }
    let num = |f: &str| node.props.get(f).and_then(Value::as_f64).unwrap_or(0.0);
    let n = (t * fps + 1e-6).floor();
    let i = ((n - num("start") * fps) * num("speed") + 1e-6).floor() as i64 + (num("offset") * fps).round_ties_even() as i64;
    let i = if node.props.get("loop") == Some(&Value::Bool(true)) { i.rem_euclid(count) } else { i.clamp(0, count - 1) };
    &node.frames[i as usize].1
}

/// (style, inner markup) of a video layer's box: the picture the frame time picked (eval.rs), like an image.
pub fn video(it: &Item, gradient: bool) -> R<(String, String)> {
    if gradient {
        return Err(format!("{}: a gradient on a video is not drawn by this engine yet", it.id));
    }
    let pic = it.str("picture");
    if pic.is_empty() {
        return Err(format!("{}: the video has no frames (src \"{}\")", it.id, it.str("src")));
    }
    let fit = match it.str("fit") { "stretch" => "fill", f => f };
    let s = format!("width:{}px;height:{}px;border-radius:{}px;overflow:hidden;", v(it, "w"), v(it, "h"), v(it, "radius"));
    Ok((s, format!("<img src=\"/__local_asset?p={}\" style=\"width:100%;height:100%;object-fit:{fit};\">", percent(pic))))
}

/// The layer's frosted glass: (glass markup before the content, the layer's outer opacity, the content wrapped).
/// Skia fills the glass layer from what is already painted, so the layer's opacity moves off the layer's own box
/// onto the glass and the content (a faded ancestor group or a blend mode would hide the backdrop: refused for the layer's own blend).
pub fn glass(it: &Item, soft_masks: bool, body: String) -> R<(String, String, String)> {
    let Some(g) = it.effects.iter().find(|e| e.kind == "backdrop") else {
        return Ok((String::new(), v(it, "opacity"), body));
    };
    if it.str("blend") != "normal" {
        return Err(format!("{}: a backdrop effect can't be used with the {} blend (the glass would see only the layer)", g.id, it.str("blend")));
    }
    if soft_masks {
        return Err(format!("{}: a backdrop effect can't be used with a feathered, inverted or turned mask (hard rect and ellipse masks work)", g.id));
    }
    let alpha = it.num("opacity");
    let radius = match it.kind {
        "shape" if it.str("shape") == "ellipse" => "50%".to_string(),
        "shape" | "image" | "video" => format!("{}px", v(it, "radius")),
        _ => "0".to_string(),
    };
    let mut filter = format!("blur({}px)", v(g, "radius"));
    if g.num("saturate") != 1.0 {
        let _ = write!(filter, " saturate({})", v(g, "saturate"));
    }
    if g.num("brightness") != 1.0 {
        let _ = write!(filter, " brightness({})", v(g, "brightness"));
    }
    let glass = format!("<div style=\"position:absolute;left:0;top:0;width:100%;height:100%;border-radius:{radius};backdrop-filter:{filter};opacity:{alpha};\"></div>");
    let wrapped = format!("<div style=\"position:absolute;left:0;top:0;width:100%;height:100%;opacity:{};\">{body}</div>", alpha * g.num("fillAmount"));
    Ok((glass, "1".into(), wrapped))
}

/// One mask as the style of a box that covers the layer (nesting boxes intersects masks). A plain rect or ellipse is a
/// clip-path; a feathered, inverted or turned one is an SVG `<mask>` (alpha) of the shape blurred by `feather` (σ = feather/4,
/// so the soft edge is `feather` px wide, centred on the edge), whose `<svg>` is added to `defs`.
pub fn mask(layer: &Item, index: usize, m: &Item, defs: &mut String) -> R<String> {
    let (x, y, w, h, r) = (m.num("x"), m.num("y"), m.num("w"), m.num("h"), m.num("radius"));
    let ellipse = m.str("shape") == "ellipse";
    let (feather, angle, invert) = (m.num("feather"), m.num("angle"), m.on("invert"));
    if feather == 0.0 && angle == 0.0 && !invert {
        if ellipse {
            return Ok(format!("clip-path:ellipse({}px {}px at {}px {}px);", w / 2.0, h / 2.0, x + w / 2.0, y + h / 2.0));
        }
        return Ok(format!("clip-path:inset({y}px calc(100% - {}px) calc(100% - {}px) {x}px round {r}px);", x + w, y + h));
    }
    let id: String = format!("rm-{}-{index}", layer.id.chars().map(|c| if c.is_ascii_alphanumeric() || c == '_' { c.to_string() } else { format!("-{:x}-", c as u32) }).collect::<String>());
    let sigma = feather / 4.0;
    let pad = 4.0 * sigma + 8.0;
    let (bw, bh) = if layer.props.contains_key("w") { (layer.num("w"), layer.num("h")) } else { (8192.0, 8192.0) };
    let (cx, cy, a) = (x + w / 2.0, y + h / 2.0, angle.to_radians());
    let rot = |px: f64, py: f64| (cx + (px - cx) * a.cos() - (py - cy) * a.sin(), cy + (px - cx) * a.sin() + (py - cy) * a.cos());
    let mut d = String::new();
    if invert {
        let _ = write!(d, "M{} {}H{}V{}H{}Z", -pad, -pad, bw + pad, bh + pad, -pad);
    }
    if ellipse {
        let (rx, ry) = (w / 2.0, h / 2.0);
        let (p0, p1) = (rot(cx - rx, cy), rot(cx + rx, cy));
        let _ = write!(d, "M{} {}A{rx} {ry} {angle} 1 0 {} {}A{rx} {ry} {angle} 1 0 {} {}Z", p0.0, p0.1, p1.0, p1.1, p0.0, p0.1);
    } else {
        let r = r.min(w / 2.0).min(h / 2.0).max(0.0);
        let q = |px: f64, py: f64| { let p = rot(px, py); format!("{} {}", p.0, p.1) };
        let arc = |px: f64, py: f64| if r > 0.0 { format!("A{r} {r} 0 0 1 {}", q(px, py)) } else { String::new() };
        let _ = write!(d, "M{}L{}{}L{}{}L{}{}L{}{}Z", q(x + r, y), q(x + w - r, y), arc(x + w, y + r), q(x + w, y + h - r),
            arc(x + w - r, y + h), q(x + r, y + h), arc(x, y + h - r), q(x, y + r), arc(x + r, y));
    }
    let shape = format!("<path d=\"{d}\" fill=\"#000\" fill-rule=\"evenodd\"/>");
    let (filter, body) = if sigma > 0.0 {
        // The blur's region follows the content's box: a faint pad rect makes it the layer's box plus the blur's reach.
        let pad_rect = format!("<rect x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"#000\" fill-opacity=\"0.001\"/>", -pad, -pad, bw + 2.0 * pad, bh + 2.0 * pad);
        (format!("<filter id=\"{id}-f\"><feGaussianBlur stdDeviation=\"{sigma}\"/></filter>"), format!("<g filter=\"url(#{id}-f)\">{pad_rect}{shape}</g>"))
    } else {
        (String::new(), shape)
    };
    let _ = write!(defs, "<svg width=\"0\" height=\"0\" style=\"position:absolute;left:0;top:0;\"><defs>{filter}<mask id=\"{id}\" style=\"mask-type:alpha\">{body}</mask></defs></svg>");
    Ok(format!("mask-image:url(#{id});"))
}
