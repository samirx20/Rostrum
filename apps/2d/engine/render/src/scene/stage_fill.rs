//! A layer's fill beyond one colour (ENGINE_CONTRACT.md § 4): a gradient effect (its stops, or color1 / color2 /
//! middle when it has none, and its geometry) as CSS for boxes and text and as SVG for paths (a picture or painted
//! fill is stage_raster.rs).
//! A paint SVG has no form for (a conic gradient, a picture) fills an SVG-drawn outline as a CSS box cut by that
//! outline (`masked`): the same paint and the same render path in preview and export.

use super::eval::Item;
use super::stage::v;

type R<T> = Result<T, String>;

struct Stop {
    at: f64,
    hex: String,
    alpha: f64,
}

/// The stops in order of position: the `stops` children, else color1 (0), color3 at `mid` (middle on), color2 (1).
fn stops(e: &Item) -> Vec<Stop> {
    if !e.stops.is_empty() {
        let mut out: Vec<Stop> = e.stops.iter().map(|s| {
            // A see-through colour (#rrggbbaa, keyed ones mixed so too) multiplies into the stop's opacity.
            let (hex, a) = super::eval::split_alpha(s.str("color"));
            Stop { at: s.num("at"), hex: hex.into(), alpha: (s.num("opacity") * a).clamp(0.0, 1.0) }
        }).collect();
        out.sort_by(|a, b| a.at.total_cmp(&b.at));
        return out;
    }
    let mut out = vec![Stop { at: 0.0, hex: e.str("color1").into(), alpha: 1.0 }];
    if e.on("middle") {
        out.push(Stop { at: e.num("mid").clamp(0.0, 1.0), hex: e.str("color3").into(), alpha: 1.0 });
    }
    out.push(Stop { at: 1.0, hex: e.str("color2").into(), alpha: 1.0 });
    out
}

fn css_colour(s: &Stop) -> String {
    if s.alpha >= 1.0 {
        return s.hex.clone();
    }
    let ch = |i: usize| u8::from_str_radix(&s.hex[i..i + 2], 16).unwrap_or(0);
    format!("rgba({},{},{},{:.4})", ch(1), ch(3), ch(5), s.alpha)
}

/// The CSS stop list, each stop's position mapped by `line` (a stop's 0..1 → its place on CSS's gradient line).
fn css_stops(e: &Item, line: impl Fn(f64) -> f64) -> String {
    stops(e).iter().map(|s| format!("{} {:.4}%", css_colour(s), line(s.at) * 100.0)).collect::<Vec<_>>().join(", ")
}

/// The gradient as a CSS background over a w × h box (`size`; a text's letters have none). Box geometry: linear by
/// `angle` across the box, radial = the ellipse touching the nearest sides around (cx, cy), conic from `angle`
/// around it. With span "points": linear from (x1, y1) to (x2, y2), radial with radii rx, ry (fractions of the box).
pub fn css(e: &Item, size: Option<(f64, f64)>) -> R<String> {
    let at = format!("at {:.3}% {:.3}%", e.num("cx") * 100.0, e.num("cy") * 100.0);
    let points = e.str("span") == "points";
    Ok(match e.str("style") {
        "radial" if points => format!("radial-gradient({:.3}% {:.3}% {at}, {})", e.num("rx") * 100.0, e.num("ry") * 100.0, css_stops(e, |o| o)),
        "radial" => format!("radial-gradient(closest-side {at}, {})", css_stops(e, |o| o)),
        "conic" => format!("conic-gradient(from {}deg {at}, {})", v(e, "angle"), css_stops(e, |o| o)),
        _ if points => {
            let (w, h) = size.ok_or_else(|| format!("{}: a gradient from point to point on a text's letters is not drawn by this engine yet (use an angle)", e.id))?;
            let (x1, y1, x2, y2) = (e.num("x1") * w, e.num("y1") * h, e.num("x2") * w, e.num("y2") * h);
            let len = (x2 - x1).hypot(y2 - y1).max(1e-6);
            let (ux, uy) = ((x2 - x1) / len, (y2 - y1) / len);
            // CSS's line runs through the box's centre at this angle, long enough to reach its corners; the two points
            // are projected on it and the stops placed between them (stops past 0 % / 100 % widen the line: PATCHES.md).
            let half = ((w * ux.abs() + h * uy.abs()) / 2.0).max(1e-6);
            let t = |x: f64, y: f64| ((x - w / 2.0) * ux + (y - h / 2.0) * uy) / (2.0 * half) + 0.5;
            let (t1, t2) = (t(x1, y1), t(x2, y2));
            format!("linear-gradient({:.4}deg, {})", ux.atan2(-uy).to_degrees(), css_stops(e, |o| t1 + (t2 - t1) * o))
        }
        _ => format!("linear-gradient({}deg, {})", v(e, "angle"), css_stops(e, |o| o)),
    })
}

/// A conic gradient has no SVG form: an SVG-drawn outline takes it as a masked CSS box (`masked`).
pub fn css_only(e: &Item) -> bool {
    e.str("style") == "conic"
}

/// A conic gradient as the background of a box grown `pad` px past the w × h box on every side.
pub fn conic_padded(e: &Item, w: f64, h: f64, pad: f64) -> String {
    let at = format!("at {:.3}px {:.3}px", e.num("cx") * w + pad, e.num("cy") * h + pad);
    format!("background:conic-gradient(from {}deg {at}, {});", v(e, "angle"), css_stops(e, |o| o))
}

/// The SVG gradient over a w × h box, the CSS geometry (`css`) in px.
pub fn svg_def(e: &Item, gid: &str, w: f64, h: f64) -> R<String> {
    let stops: String = stops(e).iter().map(|s| {
        let alpha = if s.alpha < 1.0 { format!(" stop-opacity=\"{:.4}\"", s.alpha) } else { String::new() };
        format!("<stop offset=\"{:.4}\" stop-color=\"{}\"{alpha}/>", s.at, s.hex)
    }).collect();
    let points = e.str("span") == "points";
    match e.str("style") {
        "radial" => {
            let (cx, cy) = (e.num("cx") * w, e.num("cy") * h);
            let (rx, ry) = if points { (e.num("rx") * w, e.num("ry") * h) } else { (cx.min(w - cx), cy.min(h - cy)) };
            let (rx, ry) = (rx.abs().max(0.01), ry.abs().max(0.01));
            Ok(format!("<radialGradient id=\"{gid}\" gradientUnits=\"userSpaceOnUse\" cx=\"0\" cy=\"0\" r=\"1\" gradientTransform=\"translate({cx:.3} {cy:.3}) scale({rx:.3} {ry:.3})\">{stops}</radialGradient>"))
        }
        "linear" => {
            let (x1, y1, x2, y2) = if points {
                (e.num("x1") * w, e.num("y1") * h, e.num("x2") * w, e.num("y2") * h)
            } else {
                let a = e.num("angle").to_radians();
                let (dx, dy) = (a.sin(), -a.cos());
                let half = (w * dx.abs() + h * dy.abs()) / 2.0;
                (w / 2.0 - dx * half, h / 2.0 - dy * half, w / 2.0 + dx * half, h / 2.0 + dy * half)
            };
            Ok(format!("<linearGradient id=\"{gid}\" gradientUnits=\"userSpaceOnUse\" x1=\"{x1:.3}\" y1=\"{y1:.3}\" x2=\"{x2:.3}\" y2=\"{y2:.3}\">{stops}</linearGradient>"))
        }
        s => Err(format!("{}: a {s} gradient has no SVG form (it is drawn as a masked box)", e.id)),
    }
}

/// A box `pad` px bigger than w × h on every side painted with `background` (CSS) and `inner` (markup), cut by
/// `shapes` (SVG elements in the w × h box's px, drawn opaque) as an alpha mask (vendor/PATCHES.md › Transition masks).
pub fn masked(id: &str, w: f64, h: f64, pad: f64, (background, inner): (&str, &str), shapes: &str) -> String {
    let mid = format!("{id}__paint");
    let (bw, bh) = (w + 2.0 * pad, h + 2.0 * pad);
    format!(
        "<svg width=\"0\" height=\"0\" style=\"position:absolute;left:0;top:0;\"><defs><mask id=\"{mid}\" style=\"mask-type:alpha\" maskUnits=\"userSpaceOnUse\" x=\"0\" y=\"0\" width=\"{bw}\" height=\"{bh}\"><g transform=\"translate({pad} {pad})\">{shapes}</g></mask></defs></svg>\
         <div style=\"position:absolute;left:{}px;top:{}px;width:{bw}px;height:{bh}px;overflow:hidden;{background}mask-image:url(#{mid});\">{inner}</div>",
        -pad, -pad
    )
}
