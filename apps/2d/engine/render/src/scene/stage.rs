//! One evaluated frame (eval.rs) → the stage markup the renderer lays out and paints (ENGINE_CONTRACT.md § 4).
//! The same markup the Python stopgap (`apps/2d/python/rostrum2d/stopgap_html.py`) wrote, moved here so the
//! engine draws a scene on its own; the kept page then takes it as edits (keep.rs), so a frame where little moved
//! restyles and repaints little. What it can't draw yet is refused, never drawn as something else.

use std::fmt::Write;

use serde_json::Value;

use super::eval::Item;

type R<T> = Result<T, String>;

/// A field's value as written in the scene (numbers as JSON writes them).
fn v(it: &Item, f: &str) -> String {
    match &it.props[f] {
        Value::String(s) => s.clone(),
        other => other.to_string(),
    }
}

/// The page shell: the scene's fonts (fonts.rs; a file that can't be read is an error) and an empty stage the comp's size.
pub fn shell(width: u32, height: u32, fonts: &[super::fonts::Font]) -> R<String> {
    let mut faces = String::new();
    let mut read: Vec<(&std::path::Path, String)> = vec![];
    for f in fonts {
        if !read.iter().any(|(p, _)| *p == f.path) {
            let bytes = std::fs::read(&f.path).map_err(|e| format!("font {}: {e}", f.path.display()))?;
            read.push((&f.path, base64(&bytes)));
        }
        let data = &read.iter().find(|(p, _)| *p == f.path).unwrap().1;
        let _ = writeln!(faces, "@font-face {{ font-family: \"{}\"; src: url(\"data:font/ttf;base64,{data}\"); }}", f.family);
    }
    Ok(format!("<html><head><style>{faces}html, body {{ margin: 0; background: #000; }}
#rostrum-stage {{ position: relative; width: {width}px; height: {height}px; overflow: hidden; }}</style></head><body><div id=\"rostrum-stage\"></div></body></html>"))
}

/// The stage markup of the comp at one time.
pub fn stage(comp: &Item) -> R<String> {
    let mut out = format!("<div style=\"position:absolute;left:0;top:0;width:100%;height:100%;background:{};\"></div>", v(comp, "background"));
    for l in &comp.layers {
        out += &layer(l)?;
    }
    Ok(out)
}

fn gradient(e: &Item) -> String {
    let mut stops = vec![v(e, "color1")];
    if e.on("middle") {
        stops.push(format!("{} {:.1}%", v(e, "color3"), e.num("mid") * 100.0));
    }
    stops.push(v(e, "color2"));
    if e.str("style") == "radial" {
        format!("radial-gradient(closest-side, {})", stops.join(", "))
    } else {
        format!("linear-gradient({}deg, {})", v(e, "angle"), stops.join(", "))
    }
}

fn transform(p: &Item) -> String {
    let mut parts = vec![format!("translate({:.3}%, {:.3}%)", -p.num("anchorX") * 100.0, -p.num("anchorY") * 100.0)];
    if p.num("tiltX") != 0.0 || p.num("tiltY") != 0.0 {
        parts.push(format!("perspective(1600px) rotateX({}deg) rotateY({}deg)", v(p, "tiltX"), v(p, "tiltY")));
    }
    if p.num("rotation") != 0.0 {
        parts.push(format!("rotate({}deg)", v(p, "rotation")));
    }
    let (sx, sy) = (p.num("scale") * p.num("scaleX"), p.num("scale") * p.num("scaleY"));
    if (sx, sy) != (1.0, 1.0) {
        parts.push(format!("scale({sx:.5}, {sy:.5})"));
    }
    parts.join(" ")
}

/// Overrides of a layer's own look: its gradient fill, or a glow's single colour.
#[derive(Clone, Copy, Default)]
struct Look<'a> {
    gradient: Option<&'a str>,
    color: Option<&'a str>,
}

/// (style, inner markup) of the layer's own box, for its type.
fn content(it: &Item, look: Look) -> R<(String, String)> {
    let grad = look.gradient;
    match it.kind {
        "shape" => {
            let mut s = format!("width:{}px;height:{}px;box-sizing:border-box;", v(it, "w"), v(it, "h"));
            s += &if it.str("shape") == "ellipse" { "border-radius:50%;".to_string() } else { format!("border-radius:{}px;", v(it, "radius")) };
            let _ = write!(s, "background:{};", look.color.map(str::to_string).or(grad.map(str::to_string)).unwrap_or_else(|| v(it, "fill")));
            if it.on("stroke") {
                let _ = write!(s, "border:{}px solid {};", v(it, "strokeWidth"), v(it, "strokeColor"));
            }
            Ok((s, String::new()))
        }
        "text" => {
            let size = it.num("size");
            let mut s = format!(
                "font-family:'{}';font-size:{}px;font-weight:{:.0};font-stretch:{}%;letter-spacing:{}em;line-height:{};text-align:{};font-variation-settings:'opsz' {:.0};",
                it.str("font"), v(it, "size"), it.num("weight"), v(it, "stretch"), v(it, "tracking"), v(it, "lineHeight"), it.str("align"), size.clamp(8.0, 144.0)
            );
            s += &if it.num("boxWidth") != 0.0 { format!("width:{}px;white-space:pre-wrap;", v(it, "boxWidth")) } else { "white-space:pre;".into() };
            if let Some(c) = look.color {
                let _ = write!(s, "color:{c};");
            } else if let Some(g) = grad {
                let _ = write!(s, "background:{g};-webkit-background-clip:text;background-clip:text;color:transparent;");
            } else {
                let _ = write!(s, "color:{};", v(it, "color"));
            }
            if it.on("stroke") {
                let _ = write!(s, "-webkit-text-stroke:{}px {};", v(it, "strokeWidth"), v(it, "strokeColor"));
            }
            Ok((s, escape(it.str("body"))))
        }
        "image" => {
            if grad.is_some() {
                return Err(format!("{}: a gradient on an image is not drawn by this engine yet", it.id));
            }
            let fit = match it.str("fit") { "stretch" => "fill", f => f };
            let s = format!("width:{}px;height:{}px;border-radius:{}px;overflow:hidden;", v(it, "w"), v(it, "h"), v(it, "radius"));
            let src = it.str("src");
            if src.is_empty() {
                return Ok((s, String::new()));
            }
            if !std::path::Path::new(src).is_file() {
                return Err(format!("{}.src: file not found: {src}", it.id));
            }
            Ok((s, format!("<img src=\"/__local_asset?p={}\" style=\"width:100%;height:100%;object-fit:{fit};\">", percent(src))))
        }
        "group" => {
            let mut s = format!("width:{}px;height:{}px;", v(it, "w"), v(it, "h")) + if it.on("clip") { "overflow:hidden;" } else { "" };
            if let Some(g) = grad {
                let _ = write!(s, "background:{g};");
            }
            let mut inner = String::new();
            for l in &it.layers {
                inner += &layer(l)?;
            }
            Ok((s, inner))
        }
        "drawing" => {
            if grad.is_some() {
                return Err(format!("{}: a gradient on a drawing is not drawn by this engine yet", it.id));
            }
            // The painting kit's picture of the drawing showing now (eval.rs), stretched to the canvas box.
            let s = format!("width:{}px;height:{}px;", v(it, "w"), v(it, "h"));
            match it.str("src") {
                "" => Ok((s, String::new())),
                src => Ok((s, format!("<img src=\"/__local_asset?p={}\" style=\"width:100%;height:100%;object-fit:fill;\">", percent(src)))),
            }
        }
        k => Err(format!("{}: a {k} layer is not drawn by this engine yet", it.id)),
    }
}

fn mask(m: &Item) -> R<String> {
    let (x, y, w, h) = (m.num("x"), m.num("y"), m.num("w"), m.num("h"));
    let ellipse = m.str("shape") == "ellipse";
    if m.num("feather") != 0.0 || m.on("invert") {
        if !ellipse {
            return Err(format!("{}: a feathered or inverted rect mask is not drawn by this engine yet", m.id));
        }
        let (cx, cy, rx, ry) = (x + w / 2.0, y + h / 2.0, w / 2.0, h / 2.0);
        let (inner, outer) = if m.on("invert") { ("transparent", "#000") } else { ("#000", "transparent") };
        let soft = (100.0 - m.num("feather") / rx.max(ry).max(1.0) * 100.0).max(0.0);
        let g = format!("radial-gradient({rx}px {ry}px at {cx}px {cy}px, {inner} {soft:.1}%, {outer} 100%)");
        return Ok(format!("mask-image:{g};-webkit-mask-image:{g};"));
    }
    if ellipse {
        return Ok(format!("clip-path:ellipse({}px {}px at {}px {}px);", w / 2.0, h / 2.0, x + w / 2.0, y + h / 2.0));
    }
    Ok(format!("clip-path:inset({}px calc(100% - {}px) calc(100% - {}px) {}px round {}px);", v(m, "y"), x + w, y + h, v(m, "x"), v(m, "radius")))
}

fn boxed(style: &str, inner: &str, full: bool) -> String {
    let size = if full { "width:100%;height:100%;" } else { "" };
    format!("<div style=\"position:absolute;left:0;top:0;{size}{style}\">{inner}</div>")
}

/// One layer: content → masks → effects (contract § 4), positioned by its transform.
fn layer(it: &Item) -> R<String> {
    let grad = it.effects.iter().find(|e| e.kind == "gradient").map(gradient);
    let look = Look { gradient: grad.as_deref(), color: None };
    let (mut style, inner) = content(it, look)?;
    let blur: f64 = it.effects.iter().filter(|e| e.kind == "blur").map(|e| e.num("radius")).sum();
    let filters = if blur != 0.0 { format!("filter:blur({blur}px);") } else { String::new() };
    if let Some(s) = it.effects.iter().find(|e| e.kind == "shadow") {
        let c = s.str("color");
        let ch = |i: usize| u8::from_str_radix(&c[i..i + 2], 16).unwrap_or(0);
        let rgba = format!("rgba({},{},{},{})", ch(1), ch(3), ch(5), v(s, "strength"));
        let prop = if it.kind == "text" { "text-shadow" } else { "box-shadow" };
        let _ = write!(style, "{prop}:{}px {}px {}px {rgba};", v(s, "dx"), v(s, "dy"), v(s, "radius"));
    }
    let masks = it.masks.iter().map(mask).collect::<R<Vec<_>>>()?;
    // Masks cut the content first; effects see the cut result.
    let masked = |content_style: &str, extra: &str| {
        let mut html = boxed(content_style, &inner, false);
        for m in &masks {
            html = boxed(m, &html, true);
        }
        boxed(extra, &html, true)
    };
    let mut body = masked(&style, &filters);
    for g in it.effects.iter().filter(|e| e.kind == "glow") {
        // A blurred copy behind, added light.
        let color = if g.on("ownColor") { None } else { Some(g.str("color")) };
        let (gs, _) = content(it, Look { color, ..look })?;
        body = masked(&gs, &format!("filter:blur({}px);opacity:{};mix-blend-mode:plus-lighter;", v(g, "radius"), g.num("strength").min(1.0))) + &body;
    }
    let size = if it.props.contains_key("w") { format!("width:{}px;height:{}px;", v(it, "w"), v(it, "h")) } else { String::new() };
    let sizer = if it.kind == "text" { format!("<div style=\"visibility:hidden;{style}\">{inner}</div>") } else { String::new() };
    let blend = match it.str("blend") { "add" => "plus-lighter", b => b };
    Ok(format!(
        "<div id=\"{}\" style=\"position:absolute;left:{}px;top:{}px;{size}transform-origin:{}% {}%;transform:{};opacity:{};mix-blend-mode:{blend};\">{sizer}{body}</div>",
        escape(it.id), v(it, "x"), v(it, "y"), it.num("anchorX") * 100.0, it.num("anchorY") * 100.0, transform(it), v(it, "opacity")
    ))
}

/// As Python's `html.escape`.
fn escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => out += "&amp;",
            '<' => out += "&lt;",
            '>' => out += "&gt;",
            '"' => out += "&quot;",
            '\'' => out += "&#x27;",
            c => out.push(c),
        }
    }
    out
}

fn percent(s: &str) -> String {
    s.bytes().map(|b| if b.is_ascii_alphanumeric() || b"-._~".contains(&b) { (b as char).to_string() } else { format!("%{b:02X}") }).collect()
}

fn base64(b: &[u8]) -> String {
    const A: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(b.len().div_ceil(3) * 4);
    for c in b.chunks(3) {
        let n = (c[0] as u32) << 16 | (*c.get(1).unwrap_or(&0) as u32) << 8 | *c.get(2).unwrap_or(&0) as u32;
        for i in 0..4 {
            out.push(if i <= c.len() { A[(n >> (18 - 6 * i) & 63) as usize] as char } else { '=' });
        }
    }
    out
}
