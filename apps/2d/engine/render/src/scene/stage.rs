//! One evaluated frame (eval.rs) → the stage markup the renderer lays out and paints (ENGINE_CONTRACT.md § 4).
//! The same markup the Python stopgap (`apps/2d/python/rostrum2d/stopgap_html.py`) wrote, moved here so the
//! engine draws a scene on its own; the kept page then takes it as edits (keep.rs), so a frame where little moved
//! restyles and repaints little. What it can't draw yet is refused, never drawn as something else.

use std::fmt::Write;

use serde_json::Value;

use super::eval::Item;
use super::stage_type;

#[path = "stage_path.rs"]
mod path;
pub(crate) use path::outline_d;
#[path = "stage_paint.rs"]
mod paint;

type R<T> = Result<T, String>;

/// A field's value as written in the scene (numbers as JSON writes them).
pub(super) fn v(it: &Item, f: &str) -> String {
    match &it.props[f] {
        Value::String(s) => s.clone(),
        other => other.to_string(),
    }
}

/// The page shell: the faces of the scene's text fonts (fonts.rs `faces_of`; a file that can't be read is an error),
/// each with its weight and slope (a variable font's weight is its own axis), and an empty stage the comp's size.
/// Every picture on the stage (image, drawing, video, paint) is a block: an inline `<img>` sits on the text baseline, so
/// one shorter than a line of text (a 5 px mouth from a PSD) was pushed below its own clipped box and never drawn.
pub fn shell(width: u32, height: u32, fonts: &[super::fonts::Font]) -> R<String> {
    let mut faces = String::new();
    let mut read: Vec<((&std::path::Path, u32), String)> = vec![];
    for f in fonts {
        let key = (f.path.as_path(), f.index);
        if !read.iter().any(|(k, _)| *k == key) {
            read.push((key, base64(&super::fonts_scan::face_bytes(&f.path, f.index)?)));
        }
        let data = &read.iter().find(|(k, _)| *k == key).unwrap().1;
        let weight = if f.variable { String::new() } else { format!(" font-weight: {};", f.weight.0) };
        let style = if f.italic { "italic" } else { "normal" };
        let _ = writeln!(faces, "@font-face {{ font-family: \"{}\";{weight} font-style: {style}; src: url(\"data:font/ttf;base64,{data}\"); }}", f.family);
    }
    Ok(format!("<html><head><style>{faces}html, body {{ margin: 0; background: transparent; }}
#rostrum-stage {{ position: relative; width: {width}px; height: {height}px; overflow: hidden; }}
#rostrum-stage img {{ display: block; }}</style></head><body><div id=\"rostrum-stage\"></div></body></html>"))
}

/// The stage markup of the comp at one time.
pub fn stage(comp: &Item) -> R<String> {
    Ok(parts(comp)?.concat())
}

/// The stage markup of the comp at one time, one piece per top-level element (the background, then each top-level
/// layer): serve.rs stages only the pieces that changed since the last frame (restage.rs).
pub fn parts(comp: &Item) -> R<Vec<String>> {
    let mut out = vec![format!("<div style=\"position:absolute;left:0;top:0;width:100%;height:100%;background:{};\"></div>", v(comp, "background"))];
    // The camera (crate::camera): each top-level layer seen through it, by its depth; the camera itself isn't drawn.
    let view = crate::camera::View::of(comp)?;
    out.extend(each_sibling(comp, |l, markup| view.place(l, markup))?);
    Ok(out)
}

/// A comp's or group's layers in order, each seen through its track matte (matte.rs); a layer used as a matte isn't drawn on its own.
fn siblings(parent: &Item, place: impl FnMut(&Item, String) -> String) -> R<String> {
    Ok(each_sibling(parent, place)?.concat())
}

/// `siblings`, one piece per layer.
fn each_sibling(parent: &Item, mut place: impl FnMut(&Item, String) -> String) -> R<Vec<String>> {
    let mut out = vec![];
    for l in parent.layers.iter().filter(|l| l.kind != "camera" && !super::matte::used(l, parent)) {
        let own = place(l, layer(l)?);
        out.push(match super::matte::of(l, parent) {
            None => own,
            Some(m) => {
                let matte = m.map(|m| layer(m).map(|markup| place(m, markup))).transpose()?.unwrap_or_default();
                super::matte::wrap(l, &matte, own)
            }
        });
    }
    Ok(out)
}

/// A layer's box (w × h px), when it has one (a text's is its letters).
fn size(it: &Item) -> Option<(f64, f64)> {
    it.props.contains_key("w").then(|| (it.num("w"), it.num("h")))
}

fn transform(p: &Item) -> String {
    let mut parts = vec![format!("translate({:.3}%, {:.3}%)", -p.num("anchorX") * 100.0, -p.num("anchorY") * 100.0)];
    // A smear (crate::motion): a stretch along the layer's velocity, in its parent's space about the anchor.
    parts.extend(crate::motion::smear_css(p));
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
            s += &match it.str("shape") {
                "ellipse" => "border-radius:50%;".to_string(),
                _ if it.on("eachCorner") => format!("border-radius:{}px {}px {}px {}px;", v(it, "radiusTL"), v(it, "radiusTR"), v(it, "radiusBR"), v(it, "radiusBL")),
                _ => format!("border-radius:{}px;", v(it, "radius")),
            };
            let picture = super::stage_fill::picture(it, it.num("w"), it.num("h"), 0.0)?;
            if picture.is_some() && grad.is_some() {
                return Err(format!("{}: a shape has a picture fill and a gradient; it takes one fill", it.id));
            }
            let mut inner = String::new();
            match (look.color, grad, picture) {
                (None, None, Some(p)) if it.on("filled") => {
                    // The pictures clipped by the box's own corners.
                    s += "overflow:hidden;position:relative;";
                    inner = p;
                }
                (c, g, _) if it.on("filled") || c.is_some() || g.is_some() => {
                    let _ = write!(s, "background:{};", c.map(str::to_string).or(g.map(str::to_string)).unwrap_or_else(|| super::eval::faded(&v(it, "fill"), super::eval::fill_opacity(&it.props))));
                }
                _ => {}
            }
            if it.on("stroke") {
                let _ = write!(s, "border:{}px solid {};", v(it, "strokeWidth"), v(it, "strokeColor"));
            }
            Ok((s, inner))
        }
        "text" => {
            let mut s = format!(
                "font-family:'{}';font-size:{}px;font-weight:{:.0};font-style:{};font-stretch:{}%;letter-spacing:{}em;line-height:{};text-align:{};",
                it.str("font"), v(it, "size"), it.num("weight"), if it.on("italic") { "italic" } else { "normal" }, v(it, "stretch"), v(it, "tracking"), v(it, "lineHeight"), it.str("align")
            );
            s += &stage_type::font_css(it)?;
            s += &if it.num("boxWidth") != 0.0 { format!("width:{}px;white-space:pre-wrap;", v(it, "boxWidth")) } else { "white-space:pre;".into() };
            if stage_type::by_letter(it) {
                return stage_type::letters(it, s, grad, look.color);
            }
            if let Some(c) = look.color {
                let _ = write!(s, "color:{c};");
            } else if let Some(g) = grad {
                let _ = write!(s, "background:{g};-webkit-background-clip:text;background-clip:text;color:transparent;");
            } else {
                let _ = write!(s, "color:{};", super::eval::faded(&v(it, "color"), super::eval::fill_opacity(&it.props)));
            }
            if it.on("stroke") {
                let _ = write!(s, "-webkit-text-stroke:{}px {};", v(it, "strokeWidth"), v(it, "strokeColor"));
            }
            Ok((s, escape(it.str("body"))))
        }
        "video" => super::stage_fx::video(it, grad.is_some()),
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
        "group" | "rig" => {
            let mut s = format!("width:{}px;height:{}px;", v(it, "w"), v(it, "h")) + if it.on("clip") { "overflow:hidden;" } else { "" };
            if let Some(g) = grad {
                let _ = write!(s, "background:{g};");
            }
            Ok((s, siblings(it, |_, markup| markup)?))
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
        "path" => path::content(it, look),
        k => Err(format!("{}: a {k} layer is not drawn by this engine yet", it.id)),
    }
}

fn boxed(style: &str, inner: &str, full: bool) -> String {
    let size = if full { "width:100%;height:100%;" } else { "" };
    format!("<div style=\"position:absolute;left:0;top:0;{size}{style}\">{inner}</div>")
}

/// One layer: content → masks → effects (contract § 4), positioned by its transform.
fn layer(it: &Item) -> R<String> {
    let held;
    let it = if stage_type::animated(it) { held = stage_type::container(it); &held } else { it };
    // A parametric shape (shape_geom.rs) is drawn as the path of its outline.
    let outlined;
    let it = if super::shape_geom::is_path(it) { outlined = super::shape_geom::as_path(it)?; &outlined } else { it };
    let grad = it.effects.iter().find(|e| e.kind == "gradient").map(|e| super::stage_fill::css(e, size(it))).transpose()?;
    let look = Look { gradient: grad.as_deref(), color: None };
    let (mut style, inner) = content(it, look)?;
    let blur: f64 = it.effects.iter().filter(|e| e.kind == "blur").map(|e| e.num("radius")).sum();
    let mut filters = if blur != 0.0 { format!("blur({blur}px) ") } else { String::new() };
    if let Some(s) = it.effects.iter().find(|e| e.kind == "shadow") {
        let c = s.str("color");
        let ch = |i: usize| u8::from_str_radix(&c[i..i + 2], 16).unwrap_or(0);
        let rgba = format!("rgba({},{},{},{})", ch(1), ch(3), ch(5), v(s, "strength"));
        let prop = if it.kind == "text" { "text-shadow" } else { "box-shadow" };
        if paint::shows(it) {
            // A painted layer's shadow follows element and paint together (and is never painted on).
            let _ = write!(filters, "drop-shadow({}px {}px {}px {rgba}) ", v(s, "dx"), v(s, "dy"), v(s, "radius"));
        } else if it.kind == "path" {
            // A path's shadow follows its outline, not its box.
            let _ = write!(style, "filter:drop-shadow({}px {}px {}px {rgba});", v(s, "dx"), v(s, "dy"), v(s, "radius"));
        } else {
            let _ = write!(style, "{prop}:{}px {}px {}px {rgba};", v(s, "dx"), v(s, "dy"), v(s, "radius"));
        }
    }
    let filters = if filters.is_empty() { filters } else { format!("filter:{};", filters.trim_end()) };
    let mut defs = String::new();
    let masks = it.masks.iter().enumerate().map(|(i, m)| super::stage_fx::mask(it, i, m, &mut defs)).collect::<R<Vec<_>>>()?;
    // Masks cut the content (with its paint: stage_paint.rs) first; effects see the cut result.
    let masked = |content_style: &str, extra: &str, painted: bool| {
        let own = boxed(content_style, &inner, false);
        let mut html = if painted { paint::over(it, own) } else { own };
        for m in &masks {
            html = boxed(m, &html, true);
        }
        boxed(extra, &html, true)
    };
    // A glow is a blurred copy of the layer behind it, added light. When the copy would be the layer's own picture
    // (its own colours and paint, no shadow), the layer is written once and its glows marked on it (`data-glow`:
    // radius and strength per glow): the painter draws the layer once and blurs that picture (blitz-paint glow.rs).
    // A glow in a single colour (or under a shadow) is a different picture: a copy in that colour, as before.
    let mut copies = String::new();
    let mut own = vec![];
    for g in it.effects.iter().filter(|e| e.kind == "glow") {
        let color = if g.on("ownColor") { None } else { Some(g.str("color")) };
        let (gs, _) = content(it, Look { color, ..look })?;
        if gs == style && (color.is_none() || !paint::shows(it)) {
            own.push(format!("{} {}", v(g, "radius"), g.num("strength").min(1.0)));
        } else {
            copies = masked(&gs, &format!("filter:blur({}px);opacity:{};mix-blend-mode:plus-lighter;", v(g, "radius"), g.num("strength").min(1.0)), color.is_none()) + &copies;
        }
    }
    let mut body = masked(&style, &filters, true);
    if !own.is_empty() {
        body = body.replacen("<div ", &format!("<div data-glow=\"{}\" ", own.join(";")), 1);
    }
    let body = copies + &body;
    // Colour effects (grade.rs) act on the layer's own look and its effects; frosted glass stays as it sees what is behind.
    let body = super::grade::wrap(it, body)?;
    let body = super::grain::wrap(it, body)?;
    let (glass, opacity, body) = super::stage_fx::glass(it, !defs.is_empty(), body)?;
    let (warp, warp_defs) = crate::rig::warp_markup(it);
    let size = if it.props.contains_key("w") { format!("width:{}px;height:{}px;", v(it, "w"), v(it, "h")) } else { String::new() };
    let sizer = if it.kind == "text" { format!("<div style=\"visibility:hidden;{style}\">{inner}</div>") } else { String::new() };
    let blend = super::blends::css(it.str("blend"));
    Ok(format!(
        "<div id=\"{}\" style=\"position:absolute;left:{}px;top:{}px;{size}transform-origin:{}% {}%;transform:{};opacity:{opacity};mix-blend-mode:{blend};{warp}\">{defs}{warp_defs}{sizer}{glass}{body}</div>",
        escape(it.id), v(it, "x"), v(it, "y"), it.num("anchorX") * 100.0, it.num("anchorY") * 100.0, transform(it)
    ))
}

/// As Python's `html.escape`.
pub(super) fn escape(s: &str) -> String {
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

pub(super) fn percent(s: &str) -> String {
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
