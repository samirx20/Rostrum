//! Motion blur's still layers drawn once per frame (E2). A motion-blurred frame paints its stage once per shutter
//! sample (serve.rs `frame`). The stage's top-level pieces (restage.rs) that are the same markup in every sample are
//! the same picture in every sample, so a run of them in a row is painted once into a kept picture and drawn in their
//! place for each sample (blitz-paint `runs.rs`, anyrender `draw_cached`).
//!
//! Exact only where "over" regroups: a run's pieces drawn one by one onto the picture below equal the run drawn on its
//! own and then laid over that picture, when every piece in it composites normally. A piece with a blend mode (its own
//! or a child's: multiply, screen, a glow's plus-lighter or `data-glow`), a backdrop effect (frosted glass), a held element or a tap
//! for the node cache is drawn every sample as before, and it ends the run. Pieces are never moved past one another,
//! so a still piece above a moving one stays above it.

use std::collections::HashMap;
use std::ops::Range;

use blitz_paint::Run;
use blitz_traits::node_id::NodeId;

/// The runs of still pieces, in stage order: piece index ranges, each of pieces that are the same in every sample and
/// composite normally. Empty when the samples don't cut into the same number of pieces.
pub fn of(samples: &[Vec<String>]) -> Vec<Range<usize>> {
    let Some(first) = samples.first() else { return vec![] };
    if samples.len() < 2 || samples.iter().any(|s| s.len() != first.len()) {
        return vec![];
    }
    let keep = |i: usize| samples.iter().all(|s| s[i] == first[i]) && regroups(&first[i]);
    let mut runs = vec![];
    let mut start = None;
    for i in 0..=first.len() {
        match (start, i < first.len() && keep(i)) {
            (None, true) => start = Some(i),
            (Some(a), false) => {
                runs.push(a..i);
                start = None;
            }
            _ => {}
        }
    }
    runs
}

/// The piece composites with plain "over" all through: no blend mode but normal, no backdrop, held or tapped element.
fn regroups(piece: &str) -> bool {
    const KEY: &str = "mix-blend-mode:";
    let blends_plainly = piece.match_indices(KEY).all(|(at, _)| piece[at + KEY.len()..].trim_start().starts_with("normal"));
    blends_plainly && !["backdrop-filter", "data-shutter-held", "data-tap", "data-glow", "mix-blend-mode=", "mix-blend-mode :"].iter().any(|k| piece.contains(k))
}

/// The paint plan that draws only run `r` (every other stage child skipped).
pub fn only(kids: &[NodeId], runs: &[Range<usize>], r: usize) -> HashMap<NodeId, Run> {
    kids.iter().enumerate().filter(|(i, _)| !runs[r].contains(i)).map(|(_, &k)| (k, Run::Skip)).collect()
}

/// The paint plan that draws each run's kept picture (`k` = the run's index) at its first piece, its other pieces skipped.
pub fn kept(kids: &[NodeId], runs: &[Range<usize>]) -> HashMap<NodeId, Run> {
    let mut plan = HashMap::new();
    for (k, r) in runs.iter().enumerate() {
        plan.insert(kids[r.start], Run::Cached(k));
        for i in r.start + 1..r.end {
            plan.insert(kids[i], Run::Skip);
        }
    }
    plan
}

/// How many pieces the runs hold.
pub fn count(runs: &[Range<usize>]) -> usize {
    runs.iter().map(|r| r.len()).sum()
}

// Grouped sub-frames (scene_serve.rs `stage_at`, crate::motion `sub_frames_grouped`): within a group only the frame
// moves, so a top-level layer's piece differs from its group's middle sample only in its frame wrapper's matrix
// (frame/mod.rs `place`). Such a piece is painted once at the middle sample and kept; each other sample of the group
// draws that picture moved by its own matrix after the kept one's inverse (anyrender `draw_cached_moved`). Exact up
// to resampling (the picture moved by fractions of a px, sampled smoothly) and, at the frame's edge, the few px a
// move uncovers, which take the picture's edge px (the stage clips at the frame, so nothing past it was drawn).

/// The order a grouped frame's samples are drawn in: each group's middle sample (its base) before the others of its
/// group (the sum is the same in any order). In order when not grouped.
pub fn order(bases: &[usize], n: usize) -> Vec<usize> {
    if bases.len() != n {
        return (0..n).collect();
    }
    let mut out = Vec::with_capacity(n);
    for i in 0..n {
        if i == 0 || bases[i] != bases[i - 1] {
            out.push(bases[i]);
        }
        if bases[i] != i {
            out.push(i);
        }
    }
    out
}

/// A frame wrapper's piece cut round its matrix: (text before the numbers, the matrix, text after).
fn split(piece: &str) -> Option<(&str, [f64; 6], &str)> {
    const KEY: &str = "transform:matrix(";
    if !piece.starts_with("<div id=\"cam~") {
        return None;
    }
    let tag = piece.find('>')?;
    let at = piece[..tag].find(KEY)? + KEY.len();
    let end = at + piece[at..tag].find(')')?;
    let mut m = [0.0; 6];
    let mut parts = piece[at..end].split(',');
    for v in &mut m {
        *v = parts.next()?.trim().parse().ok()?;
    }
    parts.next().is_none().then_some((&piece[..at], m, &piece[end..]))
}

/// The layer id a frame wrapper's piece names (`cam~<id>`, as written), when it is one and holds no other wrapper.
pub fn wrapper_id(piece: &str) -> Option<&str> {
    let rest = piece.strip_prefix("<div id=\"cam~")?;
    (piece.matches("id=\"cam~").count() == 1).then(|| &rest[..rest.find('"').unwrap_or(0)])
}

/// The piece with its frame matrix written as `matrix` (`matrix(…)`, frame/mod.rs `matrix_of`).
pub fn with_matrix(piece: &str, matrix: &str) -> Option<String> {
    let (a, _, b) = split(piece)?;
    Some(format!("{}{matrix}{}", &a[..a.len() - "matrix(".len()], &b[1..]))
}

/// The piece's frame matrix, when it is a frame wrapper that composites plainly (`regroups`): a piece that may be kept
/// and moved.
pub fn movable(piece: &str) -> Option<[f64; 6]> {
    split(piece).filter(|_| regroups(piece)).map(|(_, m, _)| m)
}

/// `piece` is `kept` (a movable piece) with only the frame matrix changed: its matrix.
pub fn moved(piece: &str, kept: &str) -> Option<[f64; 6]> {
    let (a, m, b) = split(piece)?;
    let (ka, _, kb) = split(kept)?;
    (a == ka && b == kb).then_some(m)
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

/// The farthest two pieces' moves may differ and still be drawn as one picture (device px; the matrix's turn and scale
/// alike to this over a picture's width are far under a px).
const ALIKE: f64 = 1e-3;

/// The pictures a grouped frame's base sample `base` keeps of its moving pieces (scene_serve.rs `stage_at`): movable
/// pieces in a row (none in a `still` run) that every other sample of the group (`bases[j] == base`) moves alike are one
/// picture, painted together and moved as one: (the pieces, the base's frame matrix of the first). Kept one per piece,
/// a whip pan over 200 depth layers kept 200 full-frame pictures per group and laid each over every sample: seconds a
/// frame and the graphics card's memory full (Undertow, 2026-10-29). A piece some sample of the group doesn't merely
/// move is a picture of its own, as before (that sample is then drawn whole).
pub fn moving_runs(cuts: &[Vec<String>], bases: &[usize], base: usize, still: &[Range<usize>], view: (f32, f32, f32)) -> Vec<(Range<usize>, [f64; 6])> {
    let pieces = &cuts[base];
    let others: Vec<usize> = (0..bases.len()).filter(|&j| bases[j] == base && j != base && cuts[j].len() == pieces.len()).collect();
    // Each movable piece: its matrix at the base and its move in every other sample (None: some sample changes more).
    let moves = |p: usize| -> Option<([f64; 6], Option<Vec<[f64; 6]>>)> {
        let m = movable(&pieces[p]).filter(|_| !still.iter().any(|r| r.contains(&p)))?;
        let d = others.iter().map(|&j| delta(moved(&cuts[j][p], &pieces[p])?, m, view)).collect::<Option<Vec<_>>>();
        Some((m, d))
    };
    let alike = |a: &[[f64; 6]], b: &[[f64; 6]]| a.iter().zip(b).all(|(x, y)| x.iter().zip(y).enumerate().all(|(k, (u, v))| (u - v).abs() <= if k < 4 { 1e-6 } else { ALIKE }));
    let mut out: Vec<(Range<usize>, [f64; 6])> = vec![];
    let mut last: Option<Vec<[f64; 6]>> = None;              // the moves of the run being grown
    for p in 0..pieces.len() {
        // Kept only when every other sample merely moves it (B1): a piece some sample changes is drawn per sample anyway,
        // so its kept picture was a paint spent for nothing (and stopped that sample using the others' pictures).
        let Some((m, Some(d))) = moves(p) else {
            last = None;
            continue;
        };
        let d = Some(d);
        let joins = matches!((&d, &last, out.last()), (Some(d), Some(l), Some((r, _))) if r.end == p && alike(d.as_slice(), l.as_slice()));
        if joins {
            let last_run = out.len() - 1;               // joins: there is one, ending here
            out[last_run].0.end = p + 1;
        } else {
            out.push((p..p + 1, m));
        }
        last = d;
    }
    out
}

/// A still piece that blends (or sits in a frosted glass, a held or tapped element) must never be drawn once and laid
/// over: the picture would be silently wrong. Moving pieces split runs and keep their order.
#[cfg(test)]
mod tests {
    fn p(s: &str) -> String {
        format!("<div style=\"opacity:1;{s}\"></div>")
    }

    #[test]
    fn only_still_plainly_blended_pieces_in_a_row_are_runs() {
        let plain = p("mix-blend-mode:normal;");
        let a = vec![plain.clone(), plain.clone(), p("left:1px;"), plain.clone(), p("mix-blend-mode:multiply;"), plain.clone(), p("backdrop-filter:blur(4px);"), plain.clone()];
        let mut b = a.clone();
        b[2] = p("left:2px;");
        assert_eq!(super::of(&[a.clone(), b]), vec![0..2, 3..4, 5..6, 7..8]);
        let mut glow = a.clone();
        glow[1] = format!("<div style=\"mix-blend-mode:normal;\"><div style=\"filter:blur(3px);mix-blend-mode:plus-lighter;\"></div></div>");
        assert_eq!(super::of(&[glow.clone(), glow])[0], 0..1);
        assert!(super::of(&[a.clone()]).is_empty(), "one sample: nothing to share");
        assert!(super::of(&[a.clone(), a[..3].to_vec()]).is_empty(), "samples cut differently: drawn as before");
    }

    #[test]
    fn a_frame_wrapper_moves_only_when_its_matrix_alone_changed() {
        let w = |m: &str, blur: &str| format!("<div id=\"cam~a\" style=\"position:absolute;transform-origin:0 0;transform:matrix({m});filter:blur({blur}px);\"><div style=\"left:3px;\"></div></div>");
        let (a, b) = (w("1.000000, 0.000000, 0.000000, 1.000000, 0.000, -10.000", "2.000"), w("1.000000, 0.000000, 0.000000, 1.000000, 0.000, -14.500", "2.000"));
        assert_eq!(super::movable(&a), Some([1.0, 0.0, 0.0, 1.0, 0.0, -10.0]));
        let to = super::moved(&b, &a).unwrap();
        assert_eq!(super::delta(to, super::movable(&a).unwrap(), (1.0, 0.0, 0.0)).unwrap(), [1.0, 0.0, 0.0, 1.0, 0.0, -4.5]);
        assert_eq!(super::delta(to, super::movable(&a).unwrap(), (0.5, 100.0, 0.0)).unwrap()[5], -2.25, "a half-size view moves half as far");
        assert!(super::moved(&w("1.000000, 0.000000, 0.000000, 1.000000, 0.000, -14.500", "3.000"), &a).is_none(), "its blur changed too");
        assert!(super::movable("<div style=\"transform:matrix(1, 0, 0, 1, 0, 0);\"></div>").is_none(), "not a frame wrapper");
        assert!(super::movable(&a.replace("filter:", "mix-blend-mode:screen;filter:")).is_none(), "it blends");
        assert_eq!(super::order(&[1, 1, 1, 4, 4, 4], 6), vec![1, 0, 2, 4, 3, 5]);
        assert_eq!(super::wrapper_id(&a), Some("a"));
        assert_eq!(super::with_matrix(&a, "matrix(1.000000, 0.000000, 0.000000, 1.000000, 0.000, -14.500)").as_deref(), Some(w("1.000000, 0.000000, 0.000000, 1.000000, 0.000, -14.500", "2.000").as_str()));
    }

    #[test]
    fn pieces_in_a_row_that_move_alike_are_kept_as_one_picture() {
        // Five depth wrappers: a, b at one depth (moved alike), c at another, d blends, e alike to a but after d.
        let w = |id: &str, y: f64, k: f64| format!("<div id=\"cam~{id}\" style=\"transform:matrix(1.000000, 0.000000, 0.000000, 1.000000, 0.000, {:.3});\"></div>", y * k);
        let cut = |y: f64| vec![w("a", y, 1.0), w("b", y, 1.0), w("c", y, 2.0), w("d", y, 1.0).replace("style=\"", "style=\"mix-blend-mode:screen;"), w("e", y, 1.0)];
        let cuts = vec![cut(-10.0), cut(-12.0), cut(-14.0)];
        let runs = super::moving_runs(&cuts, &[1, 1, 1], 1, &[], (1.0, 0.0, 0.0));
        let ranges: Vec<_> = runs.iter().map(|(r, _)| r.clone()).collect();
        assert_eq!(ranges, vec![0..2, 2..3, 4..5], "a and b share a picture; c moves twice as far; d blends; e is not next to a");
        assert_eq!(runs[0].1[5], -12.0, "the base's matrix of the run's first piece");
        assert_eq!(super::moving_runs(&cuts, &[1, 1, 1], 1, &[0..1], (1.0, 0.0, 0.0)).iter().map(|(r, _)| r.clone()).collect::<Vec<_>>(), vec![1..2, 2..3, 4..5], "a still piece is not moved");
        let mut changed = cuts.clone();
        changed[2][2] = changed[2][2].replace("></div>", "><i></i></div>");
        assert_eq!(super::moving_runs(&changed, &[1, 1, 1], 1, &[], (1.0, 0.0, 0.0)).iter().map(|(r, _)| r.clone()).collect::<Vec<_>>(), vec![0..2, 4..5], "c changes in a sample: not kept");
    }
}
