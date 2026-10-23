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
}
