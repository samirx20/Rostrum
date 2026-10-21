//! A `path` layer's content (ENGINE_CONTRACT.md § 4 path): an inline `<svg>` the size of the layer's box with the
//! path's fill and stroke. Blitz keeps an inline svg's source and rebuilds it whenever an attribute inside it
//! changes (blitz-dom `layout/damage.rs`), so a kept page that changes `stroke-dasharray` repaints it.
//!
//! Dashes and trim are worked out here from the path's real length (kurbo), one `<path>` per subpath: dashes
//! start again at each subpath, and trim takes `trimStart..trimEnd` of the whole length, subpath after subpath.
//! The visible pieces become an explicit dash list, so dashes and trim combine with no special case.

use std::fmt::Write;

use kurbo::{BezPath, ParamCurveArclen, Point};

use super::{escape, v, Item, Look, R};

/// More visible dash pieces than this in one frame is refused (a dash of 0.01 px over a long path).
const MAX_PIECES: usize = 20_000;

/// One subpath: its path data written back (absolute M L C Z) and its length in px.
struct Sub {
    d: String,
    len: f64,
}

/// `d` checked (absolute M, L, C, Z only; numbers by spaces or commas; a command's numbers may repeat, extra
/// pairs after M are lines), split into subpaths. Errors name `id.d`.
fn parse(id: &str, d: &str) -> R<Vec<Sub>> {
    let bad = |why: String| format!("{id}.d: {why} (path data takes absolute M x y, L x y, C x1 y1 x2 y2 x y, Z)");
    let mut toks = vec![];
    let mut rest = d.trim_start_matches([' ', ',', '\n', '\t', '\r']);
    while !rest.is_empty() {
        let c = rest.as_bytes()[0] as char;
        let n = if c.is_ascii_alphabetic() && !matches!(c, 'e' | 'E') {
            toks.push(Err(c));
            1
        } else {
            let end = rest.char_indices().skip(1).find(|&(i, ch)| {
                let prev = rest.as_bytes()[i - 1] as char;
                !(ch.is_ascii_digit() || ch == '.' || matches!(ch, 'e' | 'E') || (matches!(ch, '-' | '+') && matches!(prev, 'e' | 'E')))
            }).map_or(rest.len(), |(i, _)| i);
            let num: f64 = rest[..end].parse().map_err(|_| bad(format!("\"{}\" is not a number", &rest[..end])))?;
            if !num.is_finite() {
                return Err(bad(format!("{num} is not a finite number")));
            }
            toks.push(Ok(num));
            end
        };
        rest = rest[n..].trim_start_matches([' ', ',', '\n', '\t', '\r']);
    }
    let mut subs: Vec<BezPath> = vec![];
    let mut i = 0;
    let mut cmd = ' ';
    while i < toks.len() {
        if let Err(c) = toks[i] {
            cmd = c;
            i += 1;
        } else if cmd == ' ' || cmd == 'Z' {
            return Err(bad("numbers before a command".into()));
        }
        let want = match cmd {
            'M' | 'L' => 2,
            'C' => 6,
            'Z' => 0,
            c => return Err(bad(format!("unknown command \"{c}\""))),
        };
        let nums: Vec<f64> = toks[i..].iter().take(want).map_while(|t| t.ok()).collect();
        if nums.len() < want {
            return Err(bad(format!("{cmd} needs {want} numbers")));
        }
        i += want;
        let p = |k: usize| Point::new(nums[k], nums[k + 1]);
        match cmd {
            'M' => {
                subs.push(BezPath::new());
                subs.last_mut().unwrap().move_to(p(0));
                cmd = 'L';
            }
            'Z' => match subs.last_mut() {
                Some(s) => s.close_path(),
                None => return Err(bad("Z before any M".into())),
            },
            _ => {
                let s = subs.last_mut().filter(|s| !matches!(s.elements().last(), Some(kurbo::PathEl::ClosePath))).ok_or_else(|| bad(format!("{cmd} needs an M first")))?;
                if cmd == 'L' { s.line_to(p(0)) } else { s.curve_to(p(0), p(2), p(4)) }
            }
        }
    }
    Ok(subs.into_iter().map(|s| Sub { len: s.segments().map(|g| g.arclen(1e-3)).sum(), d: s.to_svg() }).collect())
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
        if (s, e) == (0.0, 1.0) && dash.is_none() {
            let _ = write!(svg, "<path d=\"{all}\" {common}/>");
        } else if e > s && total > 0.0 {
            common += " stroke-dasharray=\"";
            let mut at = 0.0;
            for sub in &subs {
                let window = ((s * total - at).max(0.0), (e * total - at).min(sub.len));
                at += sub.len;
                if window.1 <= window.0 {
                    continue;
                }
                let mut list = vec![];
                pieces(window, dash, &mut list).map_err(|why| format!("{}.dash: {why}; use longer dashes", it.id))?;
                list.retain(|(a, b)| b - a > 1e-3);
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
