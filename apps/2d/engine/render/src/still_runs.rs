//! Which stage pieces a motion-blurred frame may paint once and lay over (blurred.rs, motion/streak.rs), and moves
//! carried to the painter's device px.
//!
//! Exact only where "over" regroups: a piece drawn on its own and then laid over the picture below equals it drawn onto
//! that picture, when everything in it composites normally. A piece with a blend mode (its own or a child's: multiply,
//! screen, a glow's plus-lighter or `data-glow`), a backdrop effect (frosted glass), a held element or a tap for the node
//! cache is staged per sub-frame instead.

/// The piece composites with plain "over" all through: no blend mode but normal, no backdrop, held or tapped element.
pub fn regroups(piece: &str) -> bool {
    const KEY: &str = "mix-blend-mode:";
    let blends_plainly = piece.match_indices(KEY).all(|(at, _)| piece[at + KEY.len()..].trim_start().starts_with("normal"));
    blends_plainly && !["backdrop-filter", "data-shutter-held", "data-tap", "data-glow", "mix-blend-mode=", "mix-blend-mode :"].iter().any(|k| piece.contains(k))
}

/// A motion-blurred frame may paint the piece once into a picture of its own and streak that picture (blurred.rs), laid
/// on with its layer's own blend `blend` (CSS): when it regroups, or when that blend averages exactly (the average of
/// the layer laid on at each move is the average picture laid on once: normal, plus-lighter, screen and multiply are
/// linear in the layer's picture) and nothing in it reads what is under it (frosted glass) or is drawn apart (held,
/// tapped). A layer that glows from its own picture (`data-glow`) is kept too: its glow adds onto its own isolated
/// group, so the picture is linear (blur r6: the 2-6/255 it was off came from the painter's halved blurs, fixed in
/// anyrender_skia `gaussian_blur`), seen through a track matte or not (blur r7: a matted layer kept is the painted
/// steps' picture exactly; the up to 33/255 its letter edges were off was the streak reading its picture smoothly at
/// fractions of a px, now read sharply for short streaks: anyrender_skia `draw_cached_streak`).
/// Blends inside the layer stay inside it: its element is a stacking context (it is always moved by a transform), an
/// isolated group for them (blitz-paint blend.rs).
pub fn keeps(piece: &str, blend: &str) -> bool {
    regroups(piece)
        || matches!(blend, "normal" | "plus-lighter" | "screen" | "multiply")
            && !["backdrop-filter", "data-shutter-held", "data-tap"].iter().any(|k| piece.contains(k))
}

/// The move that carries the picture drawn through matrix `from` to where matrix `to` draws it, in device px of a
/// view at `scale` whose top-left is page px (x0, y0): V · to · from⁻¹ · V⁻¹.
pub fn delta(to: [f64; 6], from: [f64; 6], view: (f32, f32, f32)) -> Option<[f64; 6]> {
    use crate::rig::math::Aff;
    let aff = |m: [f64; 6]| Aff { a: m[0], b: m[1], c: m[2], d: m[3], e: m[4], f: m[5] };
    let (k, x0, y0) = (view.0 as f64, view.1 as f64, view.2 as f64);
    let v = Aff::scale(k, k) * Aff::translate(-x0, -y0);
    let r = v * aff(to) * aff(from).inverse()? * v.inverse()?;
    Some([r.a, r.b, r.c, r.d, r.e, r.f])
}

#[cfg(test)]
mod tests {
    #[test]
    fn only_plainly_composited_pieces_regroup() {
        assert!(super::regroups("<div style=\"mix-blend-mode:normal;\"></div>"));
        assert!(!super::regroups("<div style=\"mix-blend-mode:multiply;\"></div>"));
        assert!(!super::regroups("<div style=\"mix-blend-mode:normal;\"><div style=\"mix-blend-mode:plus-lighter;\"></div></div>"), "a glow copy");
        assert!(!super::regroups("<div data-glow=\"8 1\" style=\"\"></div>"));
        assert!(!super::regroups("<div style=\"backdrop-filter:blur(4px);\"></div>"));
    }

    #[test]
    fn add_screen_and_multiply_layers_streak_as_one_picture() {
        let add = "<div style=\"transform:translate(-50%, -50%);mix-blend-mode:plus-lighter;\"></div>";
        assert!(!super::regroups(add));
        assert!(super::keeps(add, "plus-lighter") && super::keeps(add, "multiply"));
        assert!(!super::keeps(add, "overlay"), "an overlay's average isn't the average laid on");
        assert!(super::keeps("<div data-glow=\"8 1\" style=\"\"></div>", "normal"), "a glow is one picture");
        assert!(super::keeps("<div data-track-matte=\"alpha\"><div></div><div data-glow=\"8 1\"></div></div>", "normal"), "a glow seen through a matte too");
        assert!(!super::keeps("<div style=\"backdrop-filter:blur(4px);\"></div>", "normal"));
    }

    #[test]
    fn a_move_is_carried_to_the_view() {
        let m = [1.0, 0.0, 0.0, 1.0, 0.0, -4.5];
        assert_eq!(super::delta(m, [1.0, 0.0, 0.0, 1.0, 0.0, 0.0], (1.0, 0.0, 0.0)).unwrap(), m);
        assert_eq!(super::delta(m, [1.0, 0.0, 0.0, 1.0, 0.0, 0.0], (0.5, 100.0, 0.0)).unwrap()[5], -2.25, "a half-size view moves half as far");
    }

    /// A motion-blurred look drawn smaller than the comp (a final look's picture, the playing canvas) keeps its streaked
    /// layers' pictures as an export does. The view's own matrix was taken for a 3D plane, every kept picture was refused
    /// and left empty, and every streaked layer vanished from the look without a word (BUG-3b).
    #[test]
    fn a_layer_is_kept_under_a_smaller_view() {
        use blitz_dom::DocumentConfig;
        use blitz_html::HtmlDocument;
        use blitz_paint::Run;
        use blitz_traits::shell::{ColorScheme, Viewport};
        let (w, h) = (200, 100);
        let html = "<!DOCTYPE html><html><head></head><body style=\"margin:0\"><div id=\"rostrum-stage\">\
            <div id=\"tall\" style=\"position:absolute;left:0;top:-500px;width:200px;height:1200px;background:#fff\"></div></div></body></html>";
        let mut doc = HtmlDocument::from_html(html, DocumentConfig { viewport: Some(Viewport::new(w, h, 1.0, ColorScheme::Light)), ..Default::default() });
        doc.resolve(0.0);
        let node = doc.get_element_by_id("tall").unwrap();
        let mut painter = crate::painter::Painter::cpu(w, h, None).unwrap();
        painter.set_view(crate::painter::View { scale: 0.5, x0: 0.0, y0: 0.0, w: w as f32, h: h as f32 }).unwrap();
        blitz_paint::set_plan([(node, Run::Keep(0))].into());
        painter.paint(false, |scene| blitz_paint::paint_scene(scene, &mut doc, 1.0, w, h, 0, 0)).unwrap();
        painter.keep_drawn(1).expect("the layer's picture is kept under the view");
        blitz_paint::set_plan([(node, Run::Cached(0))].into());
        painter.paint(false, |scene| blitz_paint::paint_scene(scene, &mut doc, 1.0, w, h, 0, 0)).unwrap();
        blitz_paint::set_plan(Default::default());
        let mut px = vec![];
        crate::color::output(&crate::color::Spec::default(), &painter.read().unwrap(), w / 2, false, false, 0, &mut px);
        assert!(px[..4].iter().all(|&v| v > 200), "the kept picture is the white layer: {:?}", &px[..4]);
    }
}
