//! A picture or painted fill (ENGINE_CONTRACT.md § 4 › Picture and painted fill): a raster covering a shape's or a
//! path's box, laid out per use. A painted fill reaches here as a picture fill: the painting's drawing at this frame is
//! `fillPicture` (eval.rs, from the node's `fillFrames`), so 50 layers sharing a painting name one file, decoded once.
//!
//! Inside the fill, bottom to top: Colour under it (`fillUnder`, a see-through colour = none), the picture (blended onto
//! it by `fillBlend`), all of it at `fillOpacity`. Tile is ONE box with a repeating background (Blitz draws `repeat` as a
//! single fill with a repeating image shader), so tiles meet with no seam at any scale, offset, turn or transform.

use super::eval::{self, Item};
use super::stage::percent;

type R<T> = Result<T, String>;

/// The raster fill's markup over a w × h box placed `pad` px in from its parent's corner (the parent clips it); None
/// when there is neither a picture nor a colour under it.
pub fn picture(it: &Item, w: f64, h: f64, pad: f64) -> R<Option<String>> {
    let src = it.str("fillPicture");
    let under = it.str("fillUnder");
    let shows_under = eval::split_alpha(under).1 > 0.0;
    if src.is_empty() && !shows_under {
        return Ok(None);
    }
    let (bw, bh) = (w + 2.0 * pad, h + 2.0 * pad);
    let blend = if shows_under { super::blends::style(it.str("fillBlend")) } else { String::new() };
    let opacity = eval::fill_opacity(&it.props);
    let mut out = format!(
        "<div style=\"position:absolute;left:0;top:0;width:{bw:.3}px;height:{bh:.3}px;{}{}\">",
        if opacity < 1.0 { format!("opacity:{opacity:.4};") } else { String::new() },
        if blend.is_empty() { "" } else { "isolation:isolate;" }
    );
    if shows_under {
        out += &format!("<div style=\"position:absolute;left:0;top:0;width:{bw:.3}px;height:{bh:.3}px;background:{under};\"></div>");
    }
    if !src.is_empty() {
        let raster = raster(it, src, w, h, pad)?;
        out += &if blend.is_empty() { raster } else {
            format!("<div style=\"position:absolute;left:0;top:0;width:{bw:.3}px;height:{bh:.3}px;{blend}\">{raster}</div>")
        };
    }
    out += "</div>";
    Ok(Some(out))
}

/// The picture itself: sized by `fillFit` (fill = cover the box, fit = inside it, stretch = the box, tile = its own
/// size) times `fillScale` (not stretch), centred, moved by `fillOffsetX/Y` (not stretch); a tile also turns by
/// `fillRotation` about the box's centre and slides by `fillDriftX/Y` px per second since the layer's start.
fn raster(it: &Item, src: &str, w: f64, h: f64, pad: f64) -> R<String> {
    let (iw, ih) = image::image_dimensions(src).map_err(|e| format!("{}.fillPicture: can't read {src}: {e}", it.id))?;
    let (iw, ih, s) = (iw as f64, ih as f64, it.num("fillScale"));
    let fit = it.str("fillFit");
    if !(s > 0.0) && fit != "stretch" {
        return Err(format!("{}.fillScale: {s} must be more than 0", it.id));
    }
    let (tw, th) = match fit {
        "fill" => { let k = (w / iw).max(h / ih) * s; (iw * k, ih * k) }
        "fit" => { let k = (w / iw).min(h / ih) * s; (iw * k, ih * k) }
        "stretch" => (w, h),
        _ => (iw * s, ih * s),
    };
    let url = format!("/__local_asset?p={}", percent(src));
    let (ox, oy) = if fit == "stretch" { (0.0, 0.0) } else { (it.num("fillOffsetX"), it.num("fillOffsetY")) };
    if fit != "tile" {
        let (x, y) = (pad + (w - tw) / 2.0 + ox, pad + (h - th) / 2.0 + oy);
        return Ok(format!("<img src=\"{url}\" style=\"position:absolute;left:{x:.3}px;top:{y:.3}px;width:{tw:.3}px;height:{th:.3}px;\">"));
    }
    let since = it.t - it.num("start");
    let (mx, my) = (ox + it.num("fillDriftX") * since, oy + it.num("fillDriftY") * since);
    // The tiles live in a square box big enough to cover the w × h box (and its pad) at any turn, centred on it; the
    // grid's origin is the centred tile's corner, moved by offset + drift in the element's own axes.
    let side = (w + 2.0 * pad).hypot(h + 2.0 * pad).ceil();
    let (sin, cos) = (-it.num("fillRotation")).to_radians().sin_cos();
    let (lx, ly) = (side / 2.0 - tw / 2.0 + mx * cos - my * sin, side / 2.0 - th / 2.0 + mx * sin + my * cos);
    let (left, top) = (pad + w / 2.0 - side / 2.0, pad + h / 2.0 - side / 2.0);
    Ok(format!(
        "<div style=\"position:absolute;left:{left:.3}px;top:{top:.3}px;width:{side:.3}px;height:{side:.3}px;transform:rotate({:.4}deg);\
         background-image:url(&quot;{url}&quot;);background-repeat:repeat;background-size:{tw:.4}px {th:.4}px;background-position:{:.4}px {:.4}px;\"></div>",
        it.num("fillRotation"), lx.rem_euclid(tw), ly.rem_euclid(th)
    ))
}
