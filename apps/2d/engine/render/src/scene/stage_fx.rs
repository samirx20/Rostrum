//! Stage pieces of S8-C (ENGINE_CONTRACT.md § 4; gradients are stage_fill.rs): frosted glass (`backdrop`), masks that
//! feather, invert and turn (soft wipes), and video layers. stage.rs calls these; what it can't draw is refused.

use std::fmt::Write;

use serde_json::Value;

use super::eval::Item;
use super::stage::{percent, v};
use super::Node;

type R<T> = Result<T, String>;

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
/// clip-path; a feathered, inverted or turned one is an SVG `<mask>` (alpha) built from gradient pieces (below), whose
/// `<svg>` is added to `defs`.
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
    // The renderer draws a mask's shapes and gradients but not its filters, so the soft edge is built from gradient
    // pieces (vendor/PATCHES.md › Transition masks; the gradients live inside the <mask>, the only part the renderer reads): a solid core, four edge bands with linear ramps and four corner
    // squares with radial ramps, never overlapping. The edge fades over `feather` px centred on the shape's edge (a hard
    // turned or inverted edge gets 1 px so it antialiases). Inverted: each piece's ramp reversed, plus everything outside.
    let f = feather.max(1.0);
    let hf = f / 2.0;
    let (cx, cy) = (x + w / 2.0, y + h / 2.0);
    let (x0, y0, x1, y1) = (x - hf, y - hf, x + w + hf, y + h + hf);
    let mut grads = String::new();
    let mut body = String::new();
    let rect = |b: &mut String, (ax, ay, bx, by): (f64, f64, f64, f64), fill: &str| {
        // Each piece reaches 0.5 px into its neighbours: abutting antialiased edges would leave a faint seam.
        if bx - ax > 1e-6 && by - ay > 1e-6 {
            let _ = write!(b, "<rect x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"{fill}\"/>", ax - 0.5, ay - 0.5, bx - ax + 1.0, by - ay + 1.0);
        }
    };
    // A ramp's stops from `from` (offset where the fade starts, alpha 1) to `to` (alpha 0), smoothstep-shaped.
    let stops = |from: f64, to: f64| -> String {
        (0..=6).map(|i| {
            let s = i as f64 / 6.0;
            let a = 1.0 - s * s * (3.0 - 2.0 * s);
            format!("<stop offset=\"{:.5}\" stop-color=\"#000\" stop-opacity=\"{:.5}\"/>", (from + (to - from) * s).clamp(0.0, 1.0), if invert { 1.0 - a } else { a })
        }).collect()
    };
    if ellipse {
        let (rx, ry) = (w / 2.0 + hf, h / 2.0 + hf);
        let inner = ((rx.min(ry) - f) / rx.min(ry)).max(0.0) * 0.5;
        let _ = write!(grads, "<radialgradient id=\"{id}-e\" cx=\"0.5\" cy=\"0.5\" r=\"0.5\">{}</radialgradient>", stops(inner * 2.0, 1.0));
        rect(&mut body, (x0, y0, x1, y1), &format!("url(#{id}-e)"));
    } else {
        let c = r.max(hf).min(w / 2.0 + hf).min(h / 2.0 + hf);
        let edge = (f / c).min(1.0);
        let solid = ((c - f) / c).max(0.0);
        for (n, (ax, ay, bx, by)) in [("t", (0, 1, 0, 0)), ("b", (0, 0, 0, 1)), ("l", (1, 0, 0, 0)), ("r", (0, 0, 1, 0))] {
            // Linear ramps run from the outer edge (alpha 0) inward; written as alpha-1-to-0 from the inner side.
            let _ = write!(grads, "<lineargradient id=\"{id}-{n}\" x1=\"{ax}\" y1=\"{ay}\" x2=\"{bx}\" y2=\"{by}\">{}</lineargradient>", stops(1.0 - edge, 1.0));
        }
        for (n, gx, gy) in [("tl", 1, 1), ("tr", 0, 1), ("bl", 1, 0), ("br", 0, 0)] {
            let _ = write!(grads, "<radialgradient id=\"{id}-{n}\" cx=\"{gx}\" cy=\"{gy}\" r=\"1\">{}</radialgradient>", stops(solid, 1.0));
        }
        let (ix0, iy0, ix1, iy1) = (x0 + c, y0 + c, x1 - c, y1 - c);
        if !invert {
            rect(&mut body, (ix0, iy0, ix1, iy1), "#000");
        }
        for (n, b) in [("t", (ix0, y0, ix1, iy0)), ("b", (ix0, iy1, ix1, y1)), ("l", (x0, iy0, ix0, iy1)), ("r", (ix1, iy0, x1, iy1)),
            ("tl", (x0, y0, ix0, iy0)), ("tr", (ix1, y0, x1, iy0)), ("bl", (x0, iy1, ix0, y1)), ("br", (ix1, iy1, x1, y1))] {
            rect(&mut body, b, &format!("url(#{id}-{n})"));
        }
    }
    if invert {
        // Everything outside the shape's soft box, far enough to cover the layer however the mask is turned.
        let (bw, bh) = if layer.props.contains_key("w") { (layer.num("w"), layer.num("h")) } else { (8192.0, 8192.0) };
        let far = bw.abs() + bh.abs() + x.abs() + y.abs() + w + h + 1000.0;
        for b in [(x0 - far, y0 - far, x1 + far, y0), (x0 - far, y1, x1 + far, y1 + far), (x0 - far, y0, x0, y1), (x1, y0, x1 + far, y1)] {
            rect(&mut body, b, "#000");
        }
    }
    let _ = write!(defs, "<svg width=\"0\" height=\"0\" style=\"position:absolute;left:0;top:0;\"><defs><mask id=\"{id}\" style=\"mask-type:alpha\">{grads}<g transform=\"rotate({angle} {cx} {cy})\">{body}</g></mask></defs></svg>");
    Ok(format!("mask-image:url(#{id});"))
}
