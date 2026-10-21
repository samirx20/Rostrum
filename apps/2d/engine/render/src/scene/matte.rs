//! Track mattes (ENGINE_CONTRACT.md § 4 matte): a layer whose `matte` names a sibling layer is seen through that
//! layer's drawing at the same frame: by its alpha or its luma (`matteMode`), or the inverse. The matte layer is
//! drawn only as the matte, never on its own; it animates as usual.
//!
//! The renderer reads a mask only as SVG (`mask-image: url(#id)`, vendor/PATCHES.md › Transition masks), so the
//! matte layer is written as SVG in its parent's space (matte_svg.rs) inside a `<mask>`. Every mode is the same two
//! nested masks: the inner one turns the matte into coverage (alpha, or luminance × alpha as SVG defines it), the
//! outer one paints a page-sized rect through it (or, inverted, a white page with that rect in black, read by
//! luminance: 1 − coverage). No filters, so nothing depends on the HTML parser keeping an attribute's case.

use std::fmt::Write;

use super::eval::Item;
use super::stage::escape;
use super::Node;

#[path = "matte_svg.rs"]
mod svg;
#[cfg(test)]
#[path = "matte_tests.rs"]
mod tests;

type R<T> = Result<T, String>;

pub const MODES: &[&str] = &["alpha", "alphaInverted", "luma", "lumaInverted"];

/// How far (px) the matted box reaches past its parent's box, so a matte or layer moving off the parent still works.
const PAD: f64 = 2048.0;

fn matte_of(n: &Node) -> &str {
    n.props.get("matte").and_then(|v| v.as_str()).unwrap_or("")
}

/// Checked when the scene loads and after every edit: each `matte` names another layer beside it (same group or
/// comp), and a matte layer has no matte of its own (so mattes never go round in a loop).
pub fn check(n: &Node) -> R<()> {
    for l in &n.layers {
        let name = matte_of(l);
        if name.is_empty() {
            continue;
        }
        if name == l.id {
            return Err(format!("{}.matte: a layer can't be its own matte", l.id));
        }
        let m = n.layers.iter().find(|s| s.id == name).ok_or_else(|| {
            let beside: Vec<&str> = n.layers.iter().filter(|s| s.id != l.id && s.kind != "camera").map(|s| s.id.as_str()).collect();
            format!("{}.matte: no layer \"{name}\" beside it (a matte is a layer in the same group or comp; beside it: {})", l.id, beside.join(", "))
        })?;
        if m.kind == "camera" {
            return Err(format!("{}.matte: the camera \"{name}\" can't be a matte", l.id));
        }
        if !matte_of(m).is_empty() {
            return Err(format!("{}.matte: \"{name}\" has a matte of its own; a matte layer can't have one", l.id));
        }
    }
    n.layers.iter().try_for_each(check)
}

/// Whether this layer is some sibling's matte (then it isn't drawn on its own). Asked of the scene, not the frame:
/// a matte stays hidden while the layer it shapes is outside its own times.
pub fn used(l: &Item, parent: &Item) -> bool {
    parent.node.layers.iter().any(|s| matte_of(s) == l.id)
}

/// The layer's markup seen through its matte (unchanged when it has none). A matte outside its times is empty:
/// the layer is hidden, or whole when inverted.
/// KNOWN OPEN (H14): the nested <mask> below draws nothing in the renderer yet (the matted layer showed whole on
/// every frame), so a matte is refused at draw time rather than shown wrong. Turn on once a contact sheet shows it.
const DRAWS: bool = false;

pub fn apply(l: &Item, parent: &Item, markup: String) -> R<String> {
    let name = l.props.get("matte").and_then(|v| v.as_str()).unwrap_or("");
    if name.is_empty() {
        return Ok(markup);
    }
    if !DRAWS {
        return Err(format!("{}.matte: track mattes are not drawn yet (KNOWN OPEN, H14: the renderer ignores this mask); use a mask on the layer for now", l.id));
    }
    let mode = l.str("matteMode");
    let content = match parent.layers.iter().find(|s| s.id == name) {
        Some(m) => svg::layer(m).map_err(|e| format!("{}.matte: {e}", l.id))?,
        None => String::new(),
    };
    let (w, h) = if parent.kind == "comp" { (parent.num("width"), parent.num("height")) } else { (parent.num("w"), parent.num("h")) };
    let id = format!("rmt-{}", l.id.chars().map(|c| if c.is_ascii_alphanumeric() || c == '_' { c.to_string() } else { format!("-{:x}-", c as u32) }).collect::<String>());
    let big = |fill: &str, extra: &str| format!("<rect x=\"0\" y=\"0\" width=\"{}\" height=\"{}\" fill=\"{fill}\"{extra}/>", w + 2.0 * PAD, h + 2.0 * PAD);
    // the reader needs the mask's box in pixels (vendor/PATCHES.md › Transition masks)
    let units = format!(" maskUnits=\"userSpaceOnUse\" x=\"0\" y=\"0\" width=\"{}\" height=\"{}\"", w + 2.0 * PAD, h + 2.0 * PAD);
    let inner_type = if mode.starts_with("alpha") { " style=\"mask-type:alpha\"" } else { "" };
    let inner = format!("<mask id=\"{id}-m\"{units}{inner_type}><g transform=\"translate({PAD} {PAD})\">{content}</g></mask>");
    let through = format!(" mask=\"url(#{id}-m)\"");
    let outer = if mode.ends_with("Inverted") {
        format!("<mask id=\"{id}\"{units}>{inner}{}{}</mask>", big("#ffffff", ""), big("#000000", &through))
    } else {
        format!("<mask id=\"{id}\"{units} style=\"mask-type:alpha\">{inner}{}</mask>", big("#000000", &through))
    };
    // The masked box holds the layer apart from what is under it, so it carries the layer's blend.
    let blend = match l.str("blend") { "normal" => String::new(), "add" => "mix-blend-mode:plus-lighter;".into(), b => format!("mix-blend-mode:{b};") };
    let mut out = String::new();
    let _ = write!(
        out,
        "<div data-matte=\"{}\" style=\"position:absolute;left:{}px;top:{}px;width:{}px;height:{}px;mask-image:url(#{id});{blend}\">\
         <svg width=\"0\" height=\"0\" style=\"position:absolute;left:0;top:0;\"><defs>{outer}</defs></svg>\
         <div style=\"position:absolute;left:{PAD}px;top:{PAD}px;width:{w}px;height:{h}px;\">{markup}</div></div>",
        escape(name), -PAD, -PAD, w + 2.0 * PAD, h + 2.0 * PAD
    );
    Ok(out)
}
