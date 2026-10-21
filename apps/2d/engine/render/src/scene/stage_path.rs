//! A `path` layer's content (ENGINE_CONTRACT.md § 4 path): an inline `<svg>` the size of the layer's box with the
//! path's fill and stroke. Blitz keeps an inline svg's source and rebuilds it whenever an attribute inside it
//! changes (blitz-dom `layout/damage.rs`), so a kept page that changes `stroke-dasharray` repaints it.
//!
//! Dashes and trim are worked out here from the path's real length (kurbo), one `<path>` per subpath: dashes
//! start again at each subpath, and trim takes `trimStart..trimEnd` of the whole length, subpath after subpath.
//! The visible pieces become an explicit dash list, so dashes and trim combine with no special case. A stroke
//! with a taper or a width profile takes the same pieces and is drawn as a filled outline (stroke_width.rs).

use std::fmt::Write;

use kurbo::ParamCurveArclen;

use super::{escape, v, Item, Look, R};
use crate::scene::{stroke_width, width_profile};

/// More visible dash pieces than this in one frame is refused (a dash of 0.01 px over a long path).
const MAX_PIECES: usize = 20_000;

/// One subpath: its curve, its path data written back (absolute M L C Z) and its length in px.
struct Sub {
    path: kurbo::BezPath,
    d: String,
    len: f64,
}

/// `d` read (path_data.rs) and split into subpaths with their lengths. Errors name `id.d`.
fn parse(id: &str, d: &str) -> R<Vec<Sub>> {
    Ok(crate::scene::path_data::read(id, d)?.into_iter().map(|s| Sub { len: s.segments().map(|g| g.arclen(1e-3)).sum(), d: s.to_svg(), path: s }).collect())
}

/// The visible pieces `[a, b]` of one subpath of length `len`: its share of the trim window, cut into dashes.
fn pieces(window: (f64, f64), dash: Option<(f64, f64, f64)>, out: &mut Vec<(f64, f64)>) -> R<()> {
    let (a, b) = window;
    let Some((d, g, off)) = dash else {
        out.push((a, b));
        return Ok(());
    };
    let period = d + g;
    let mut k = ((a + off) / period).floor();
    loop {
        let (s, e) = (k * period - off, k * period - off + d);
        if s >= b {
            return Ok(());
        }
        if e > a {
            out.push((s.max(a), e.min(b)));
            if out.len() > MAX_PIECES {
                return Err(format!("more than {MAX_PIECES} dash pieces"));
            }
        }
        k += 1.0;
    }
}

/// Each subpath's visible pieces `[a, b]` (px from its start): its share of the trim window `s..e` of the whole
/// length `total`, cut into dashes.
fn visible(it: &Item, subs: &[Sub], (s, e): (f64, f64), dash: Option<(f64, f64, f64)>, total: f64) -> R<Vec<Vec<(f64, f64)>>> {
    let mut at = 0.0;
    subs.iter().map(|sub| {
        let window = ((s * total - at).max(0.0), (e * total - at).min(sub.len));
        at += sub.len;
        let mut list = vec![];
        if window.1 > window.0 {
            pieces(window, dash, &mut list).map_err(|why| format!("{}.dash: {why}; use longer dashes", it.id))?;
            list.retain(|(a, b)| b - a > 1e-3);
        }
        Ok(list)
    }).collect()
}

/// A stroke with a taper or a width profile is drawn as a filled outline (stroke_width.rs), not an SVG stroke.
fn varied(it: &Item) -> bool {
    it.num("taperStart") > 0.0 || it.num("taperEnd") > 0.0 || !it.str("widthProfile").is_empty()
}

/// The varied stroke's outline, one `<path>` filled with the stroke's paint. Width at u along the line (or along
/// the drawn part `s..e`, with taperAlong "drawn") = strokeWidth × profile(u) × taper(u) (width_profile.rs).
fn varied_stroke(it: &Item, subs: &[Sub], visible: &[Vec<(f64, f64)>], profile: &[(f64, f64)], (s, e): (f64, f64), total: f64, paint: &str) -> String {
    let (w, ts, te) = (it.num("strokeWidth"), it.num("taperStart").clamp(0.0, 1.0), it.num("taperEnd").clamp(0.0, 1.0));
    let drawn = it.str("taperAlong") == "drawn";
    let mut d = String::new();
    let mut at = 0.0;
    for (sub, list) in subs.iter().zip(visible) {
        let base = at;
        let width = |x: f64| {
            let g = (base + x) / total;
            let u = if drawn { (g - s) / (e - s) } else { g }.clamp(0.0, 1.0);
            w * width_profile::at(profile, u) * width_profile::taper(u, ts, te)
        };
        d += &stroke_width::outline(&sub.path, list, it.str("cap"), &width);
        at += sub.len;
    }
    if d.is_empty() { d } else { format!("<path d=\"{d}\" fill=\"{paint}\" fill-rule=\"nonzero\" stroke=\"none\"/>") }
}

/// The SVG gradient for a gradient effect over a w × h box (CSS geometry: angle 180 = top to bottom; radial =
/// the ellipse touching the box's nearest sides around its centre `cx`, `cy`, fractions of the box), as
/// `stage::gradient` writes it for CSS. SVG has no conic gradient: refused.
fn gradient_def(e: &Item, gid: &str, w: f64, h: f64) -> R<String> {
    let mut stops = format!("<stop offset=\"0\" stop-color=\"{}\"/>", v(e, "color1"));
    if e.on("middle") {
        let _ = write!(stops, "<stop offset=\"{}\" stop-color=\"{}\"/>", e.num("mid").clamp(0.0, 1.0), v(e, "color3"));
    }
    let _ = write!(stops, "<stop offset=\"1\" stop-color=\"{}\"/>", v(e, "color2"));
    match e.str("style") {
        "radial" => {
            let frac = |f: &str| e.props.get(f).and_then(|x| x.as_f64()).unwrap_or(0.5);
            let (cx, cy) = (frac("cx") * w, frac("cy") * h);
            let (rx, ry) = (cx.min(w - cx).abs().max(0.01), cy.min(h - cy).abs().max(0.01));
            Ok(format!("<radialGradient id=\"{gid}\" gradientUnits=\"userSpaceOnUse\" cx=\"0\" cy=\"0\" r=\"1\" gradientTransform=\"translate({cx:.3} {cy:.3}) scale({rx:.3} {ry:.3})\">{stops}</radialGradient>"))
        }
        "linear" => {
            let a = e.num("angle").to_radians();
            let (dx, dy) = (a.sin(), -a.cos());
            let half = (w * dx.abs() + h * dy.abs()) / 2.0;
            let (cx, cy) = (w / 2.0, h / 2.0);
            Ok(format!(
                "<linearGradient id=\"{gid}\" gradientUnits=\"userSpaceOnUse\" x1=\"{:.3}\" y1=\"{:.3}\" x2=\"{:.3}\" y2=\"{:.3}\">{stops}</linearGradient>",
                cx - dx * half, cy - dy * half, cx + dx * half, cy + dy * half
            ))
        }
        s => Err(format!("{}: a {s} gradient on a path is not drawn by this engine yet", e.id)),
    }
}

/// (style, inner markup) of a path layer's box.
pub fn content(it: &Item, look: Look) -> R<(String, String)> {
    let (w, h) = (it.num("w"), it.num("h"));
    if !(w > 0.0 && h > 0.0) {
        return Err(format!("{}.w: a path's box must be wider and taller than 0 px (it is {w} × {h})", it.id));
    }
    let subs = parse(it.id, it.str("d"))?;
    let id = escape(it.id);
    let gid = format!("{id}__fill");
    // The gradient fills the path; with no fill it colours the stroke. A glow's single colour paints both.
    let grad = look.gradient.and_then(|_| it.effects.iter().find(|e| e.kind == "gradient"));
    let filled = it.on("filled");
    let paint = |own: String, takes_gradient: bool| match (look.color, grad) {
        (Some(c), _) => c.to_string(),
        (None, Some(_)) if takes_gradient => format!("url(#{gid})"),
        _ => own,
    };
    let mut svg = format!("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{w}\" height=\"{h}\" viewBox=\"0 0 {w} {h}\" preserveAspectRatio=\"none\" style=\"display:block;overflow:visible;\">");
    if let (None, Some(e)) = (look.color, grad) {
        svg += &format!("<defs>{}</defs>", gradient_def(e, &gid, w, h)?);
    }
    let all: String = subs.iter().map(|s| s.d.as_str()).collect::<Vec<_>>().join(" ");
    if filled && !all.is_empty() {
        let _ = write!(svg, "<path d=\"{all}\" fill=\"{}\" fill-rule=\"{}\" stroke=\"none\"/>", paint(v(it, "fill"), true), it.str("fillRule"));
    }
    if it.on("stroke") && it.num("strokeWidth") > 0.0 {
        let mut common = format!(
            "fill=\"none\" stroke=\"{}\" stroke-width=\"{}\" stroke-linecap=\"{}\" stroke-linejoin=\"{}\" stroke-miterlimit=\"{}\"",
            paint(v(it, "strokeColor"), !filled), v(it, "strokeWidth"), it.str("cap"), it.str("join"), it.num("miter").max(1.0)
        );
        let (s, e) = (it.num("trimStart").clamp(0.0, 1.0), it.num("trimEnd").clamp(0.0, 1.0));
        let dash = (it.num("dash") > 0.0).then(|| (it.num("dash"), it.num("gap").max(0.0), it.num("dashOffset")));
        let total: f64 = subs.iter().map(|s| s.len).sum();
        if varied(it) {
            let profile = width_profile::read(it.id, it.str("widthProfile"))?;
            if e > s && total > 0.0 {
                svg += &varied_stroke(it, &subs, &visible(it, &subs, (s, e), dash, total)?, &profile, (s, e), total, &paint(v(it, "strokeColor"), !filled));
            }
        } else if (s, e) == (0.0, 1.0) && dash.is_none() {
            let _ = write!(svg, "<path d=\"{all}\" {common}/>");
        } else if e > s && total > 0.0 {
            common += " stroke-dasharray=\"";
            for (sub, list) in subs.iter().zip(visible(it, &subs, (s, e), dash, total)?) {
                let Some(&(first, _)) = list.first() else { continue };
                // Dash i, gap to dash i+1, …, then a gap longer than the subpath; the offset starts the list at `first`.
                let mut arr = vec![];
                for (i, &(a, b)) in list.iter().enumerate() {
                    arr.push(b - a);
                    arr.push(list.get(i + 1).map_or(sub.len + first + 1.0, |n| n.0 - b));
                }
                let period: f64 = arr.iter().sum();
                let nums = arr.iter().map(|x| format!("{x:.3}")).collect::<Vec<_>>().join(" ");
                let _ = write!(svg, "<path d=\"{}\" {common}{nums}\" stroke-dashoffset=\"{:.3}\"/>", sub.d, period - first);
            }
        }
    }
    svg += "</svg>";
    Ok((format!("width:{w}px;height:{h}px;"), svg))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn path_data_is_checked_and_measured() {
        let subs = parse("p", "M0 0 L100 0 L100,100Z M 10 10 C 10 20 20 20 20 10").unwrap();
        assert_eq!(subs.len(), 2);
        assert!((subs[0].len - (200.0 + 100.0 * 2f64.sqrt())).abs() < 1e-3);
        for bad in ["L0 0", "M0 0 l10 10", "M0 0 L10", "M0 0 Z L5 5", "M0 0 Lx 1"] {
            let e = parse("p", bad).err().unwrap_or_else(|| panic!("{bad} was taken"));
            assert!(e.starts_with("p.d: "), "{e}");
        }
    }

    #[test]
    fn dashes_are_cut_to_the_trim_window() {
        let mut out = vec![];
        pieces((15.0, 45.0), Some((10.0, 10.0, 0.0)), &mut out).unwrap();
        assert_eq!(out, vec![(20.0, 30.0), (40.0, 45.0)]);
    }
}
