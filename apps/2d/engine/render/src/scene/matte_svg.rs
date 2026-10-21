//! A matte layer written as SVG in its parent's space, for the mask that matte.rs builds: its shape, outline, path,
//! letters or picture, placed by its transform (the anchor lands on x, y, then rotation and scale about it, as
//! stage.rs's CSS does) at its opacity. What a matte can't be drawn as yet is refused by name, never drawn as
//! something else.

use std::fmt::Write;

use super::super::eval::Item;
use super::super::stage::{escape, path_svg, v};
use super::super::type_font;
use super::R;

/// The layer's SVG: `<g transform opacity>` around its own content.
pub fn layer(it: &Item) -> R<String> {
    if let Some(e) = it.effects.first() {
        return Err(format!("{}: a matte layer's {} effect is not drawn by this engine yet", it.id, e.kind));
    }
    if !it.masks.is_empty() {
        return Err(format!("{}: a matte layer's masks are not drawn by this engine yet", it.id));
    }
    if it.num("tiltX") != 0.0 || it.num("tiltY") != 0.0 {
        return Err(format!("{}: a tilted matte layer is not drawn by this engine yet", it.id));
    }
    let (w, h, inner) = content(it)?;
    let (sx, sy) = (it.num("scale") * it.num("scaleX"), it.num("scale") * it.num("scaleY"));
    Ok(format!(
        "<g transform=\"translate({} {}) rotate({}) scale({sx} {sy}) translate({} {})\" opacity=\"{}\">{inner}</g>",
        v(it, "x"), v(it, "y"), v(it, "rotation"), -it.num("anchorX") * w, -it.num("anchorY") * h, it.num("opacity").clamp(0.0, 1.0)
    ))
}

/// (box width, box height, SVG in the box's own px).
fn content(it: &Item) -> R<(f64, f64, String)> {
    let (w, h) = if it.props.contains_key("w") { (it.num("w"), it.num("h")) } else { (0.0, 0.0) };
    let mut s = String::new();
    match it.kind {
        "shape" => {
            // CSS draws the fill under the whole box and the outline inside its edge.
            let ellipse = it.str("shape") == "ellipse";
            let piece = |inset: f64, paint: &str| {
                let (iw, ih) = ((w - 2.0 * inset).max(0.0), (h - 2.0 * inset).max(0.0));
                if ellipse {
                    format!("<ellipse cx=\"{}\" cy=\"{}\" rx=\"{}\" ry=\"{}\" {paint}/>", w / 2.0, h / 2.0, iw / 2.0, ih / 2.0)
                } else {
                    let r = (it.num("radius") - inset).max(0.0).min(iw / 2.0).min(ih / 2.0);
                    format!("<rect x=\"{inset}\" y=\"{inset}\" width=\"{iw}\" height=\"{ih}\" rx=\"{r}\" ry=\"{r}\" {paint}/>")
                }
            };
            s += &piece(0.0, &format!("fill=\"{}\"", v(it, "fill")));
            if it.on("stroke") && it.num("strokeWidth") > 0.0 {
                let sw = it.num("strokeWidth");
                s += &piece(sw / 2.0, &format!("fill=\"none\" stroke=\"{}\" stroke-width=\"{sw}\"", v(it, "strokeColor")));
            }
            Ok((w, h, s))
        }
        "path" => Ok((w, h, path_svg(it)?)),
        "text" => text(it),
        "image" | "video" | "drawing" => {
            let src = if it.kind == "video" { it.str("picture") } else { it.str("src") };
            if it.kind != "drawing" && it.num("radius") != 0.0 {
                return Err(format!("{}: a picture with rounded corners as a matte is not drawn by this engine yet", it.id));
            }
            if !src.is_empty() {
                let fit = match it.props.get("fit").and_then(|f| f.as_str()).unwrap_or("stretch") {
                    "cover" => "xMidYMid slice",
                    "contain" => "xMidYMid meet",
                    _ => "none",
                };
                let _ = write!(s, "<image href=\"{}\" x=\"0\" y=\"0\" width=\"{w}\" height=\"{h}\" preserveAspectRatio=\"{fit}\"/>", escape(src));
            }
            Ok((w, h, s))
        }
        "group" | "rig" => {
            if it.on("clip") {
                return Err(format!("{}: a clipped group as a matte is not drawn by this engine yet", it.id));
            }
            for l in &it.layers {
                if l.props.get("matte").and_then(|m| m.as_str()).is_some_and(|m| !m.is_empty()) {
                    return Err(format!("{}: a matte layer's own layers can't use mattes yet", l.id));
                }
                s += &layer(l)?;
            }
            Ok((w, h, s))
        }
        k => Err(format!("{}: a {k} layer can't be a matte", it.id)),
    }
}

/// A text layer's lines as SVG text, measured with the font (type_font.rs) so the box, alignment and baselines
/// match the CSS layout: each line box is lineHeight × size, the glyphs centred in it.
fn text(it: &Item) -> R<(f64, f64, String)> {
    if super::super::stage_type::by_letter(it) || !it.str("path").is_empty() {
        return Err(format!("{}: letter-by-letter or on-a-path text as a matte is not drawn by this engine yet", it.id));
    }
    let size = it.num("size");
    let line_h = it.num("lineHeight") * size;
    let lines: Vec<&str> = it.str("body").split('\n').collect();
    let mut widths = vec![];
    let (mut ascent, mut descent) = (0.0, 0.0);
    for line in &lines {
        let m = type_font::measure(it, line)?;
        widths.push(m.advances.iter().sum::<f64>());
        (ascent, descent) = (m.ascent, m.descent);
    }
    let natural = widths.iter().cloned().fold(0.0, f64::max);
    let w = if it.num("boxWidth") != 0.0 { it.num("boxWidth") } else { natural };
    if natural > w + 0.5 {
        return Err(format!("{}: text that wraps in its box as a matte is not drawn by this engine yet", it.id));
    }
    let mut paint = format!("fill=\"{}\"", v(it, "color"));
    if it.on("stroke") {
        let _ = write!(paint, " stroke=\"{}\" stroke-width=\"{}\"", v(it, "strokeColor"), v(it, "strokeWidth"));
    }
    let mut s = format!(
        "<g font-family=\"{}\" font-size=\"{size}\" font-weight=\"{:.0}\" letter-spacing=\"{}\" {paint} style=\"white-space:pre\">",
        escape(it.str("font")), it.num("weight"), it.num("tracking") * size
    );
    for (i, (line, lw)) in lines.iter().zip(&widths).enumerate() {
        let x = match it.str("align") { "center" => (w - lw) / 2.0, "right" => w - lw, _ => 0.0 };
        let y = i as f64 * line_h + (line_h - ascent - descent) / 2.0 + ascent;
        let _ = write!(s, "<text x=\"{x}\" y=\"{y}\">{}</text>", escape(line));
    }
    s += "</g>";
    Ok((w, lines.len() as f64 * line_h, s))
}
