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
    fn a_move_is_carried_to_the_view() {
        let m = [1.0, 0.0, 0.0, 1.0, 0.0, -4.5];
        assert_eq!(super::delta(m, [1.0, 0.0, 0.0, 1.0, 0.0, 0.0], (1.0, 0.0, 0.0)).unwrap(), m);
        assert_eq!(super::delta(m, [1.0, 0.0, 0.0, 1.0, 0.0, 0.0], (0.5, 100.0, 0.0)).unwrap()[5], -2.25, "a half-size view moves half as far");
    }
}
