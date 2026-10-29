//! A motion-blurred frame drawn (MOTION.md › Motion blur › One streak per layer): the page is laid out once, at the
//! frame's own time; each layer that only moves while the shutter is open is painted once and drawn as its streak (the
//! average of its picture under each sub-frame's move, one GPU pass: motion/streak.rs, blitz-paint `Run::Streak`); the
//! pieces that change while it is open are staged at each sub-frame and averaged, over what lies under them.
//!
//! The pieces are drawn in stage order, in steps: a step draws its pieces over the picture of the steps before it (kept
//! picture 0, drawn in place of the first piece). A step of pieces that are the same in every sub-frame is one paint: its
//! streaks first painted and kept, those that read none of each other's pictures together (at most `most_kept` pictures at once; past it the next streaks are the next
//! step); a streak that never reaches the frame isn't drawn, one whose picture runs past the frame's edge is painted at
//! each of its moves instead (no layout) and averaged. A step of pieces that change is painted at every sub-frame and averaged: over the same picture below, the
//! average is the layers' own average laid over it, exactly. Steps never reorder pieces, so blends and backdrops see what
//! is under them.

use std::collections::HashMap;
use std::ops::Range;

use blitz_paint::Run;
use blitz_traits::node_id::NodeId;

use crate::motion::streak::{Moves, Streak};
use crate::serve::{stage_kids, Session};

/// Paints and stages through `timed` (serve.rs `frame`: markup to stage, paint, held). Returns (pieces drawn once for the
/// whole shutter, streaks drawn). `own`: the frame's own stage and its pieces, staged when no sub-frame is.
#[allow(clippy::too_many_arguments)]
pub(crate) fn draw(
    s: &mut Session,
    own: (&str, Option<Vec<String>>),
    samples: &[&str],
    cuts: &[Vec<String>],
    streaks: &[Option<Streak>],
    most_kept: usize,
    held: bool,
    timed: &mut dyn FnMut(&mut Session, Option<&str>, bool, bool) -> Result<(), String>,
) -> Result<(usize, usize), String> {
    let n = cuts.first().or(own.1.as_ref()).map_or(0, Vec::len);
    let cut_alike = cuts.len() == samples.len() && cuts.iter().all(|c| c.len() == n);
    // The page staged once: the first sub-frame's stage (the pieces that don't change are the frame's own in each), or the frame's.
    match samples.first().copied() {
        Some(mk) => {
            s.next_pieces = cuts.first().cloned();
            timed(s, Some(mk), false, false)?;
        }
        None => {
            s.next_pieces = own.1;
            timed(s, Some(own.0), false, false)?;
        }
    }
    let kids = stage_kids(s);
    if kids.len() != n || !cut_alike || !(streaks.is_empty() || streaks.len() == n) {
        // The sub-frames draw different layers: each staged and painted whole, averaged.
        return whole(s, samples, cuts, timed).map(|_| (0, 0));
    }
    let varies: Vec<bool> = (0..n).map(|p| cuts.iter().any(|c| c[p] != cuts[0][p])).collect();
    let streak = |p: usize| streaks.get(p).and_then(Option::as_ref);
    let view = s.painter.view();
    let k = 1.0 / samples.len().max(1) as f32;
    let size = s.painter.size();
    // The sub-frame the page was last staged from.
    let (mut applied, mut base, mut p, mut once, mut drawn) = (0, false, 0, 0, 0);
    while p < n {
        let end;
        if varies[p] {
            end = (p..n).find(|&q| !varies[q]).unwrap_or(n);
            for (j, &mk) in samples.iter().enumerate() {
                if j != applied {
                    s.next_pieces = cuts.get(j).cloned();
                    timed(s, Some(mk), false, false)?;
                    applied = j;
                }
                blitz_paint::set_plan(around(&kids, base, p..end, HashMap::new()));
                crate::profile::label("mb-staged");
                timed(s, None, true, false)?;
                s.painter.accumulate(j == 0, k)?;
            }
        } else if let Some(st) = streak(p).filter(|st| st.blends) {
            // A layer that only moves but blends with what is under it: painted as laid out, moved to each sub-frame (a
            // tap per px of its path), over the picture below, and averaged. No layout.
            end = p + 1;
            let taps = taps(&st.moves, view, size);
            let w = 1.0 / taps.len() as f32;
            for (j, &i) in taps.iter().enumerate() {
                blitz_paint::set_plan(around(&kids, base, p..end, HashMap::from([(kids[p], Run::Shift(st.moves[i]))])));
                crate::profile::label("mb-blend");
                timed(s, None, true, false)?;
                s.painter.accumulate(j == 0, w)?;
            }
            once += 1;
        } else {
            // This step's streaks, each a run of pieces in a row that move alike.
            let mut runs: Vec<(Range<usize>, &Streak)> = vec![];
            let mut q = p;
            while q < n && !varies[q] && !streak(q).is_some_and(|st| st.blends) {
                let Some(m) = streak(q) else {
                    q += 1;
                    continue;
                };
                let r = q + 1 + (q + 1..n).take_while(|&r| !varies[r] && streak(r).is_some_and(|o| !o.blends && alike(&m.moves, &o.moves))).count();
                runs.push((q..r, m));
                q = r;
            }
            // A page drawn at its own size (an export, a still) keeps its streak pictures up to MARGIN px past the frame's
            // edges (`wide`), so a streak that reads past the edge within that reads the layer there. Past it, or in a
            // view, a run whose picture runs past the frame's edge (or whose size isn't known) would streak the frame's
            // edge px: it is painted at each of its moves instead, alone, and averaged into its picture (`edge`). One that
            // covers the whole frame (a backdrop) streaks its edge px, as its picture would continue past it.
            let (k, x0, y0) = (view.0 as f64, view.1 as f64, view.2 as f64);
            let seen = [x0, y0, x0 + size.0 as f64 / k, y0 + size.1 as f64 / k];
            let wide = view == (1.0, 0.0, 0.0) && blitz_paint::viewport().is_none();
            let far = if wide { [seen[0] - MARGIN, seen[1] - MARGIN, seen[2] + MARGIN, seen[3] + MARGIN] } else { seen };
            // How far past the frame each run's streak reads (device px; None: not known).
            let past: Vec<Option<f64>> = runs.iter().map(|(run, m)| {
                let r = reads(joined(run.clone().map(|i| streak(i).and_then(|st| st.reach)))?, &m.moves, seen, far, 1.0 / k);
                Some([seen[0] - r[0], seen[1] - r[1], r[2] - seen[2], r[3] - seen[3]].into_iter().fold(0.0, f64::max) * k)
            }).collect();
            let edge: Vec<bool> = runs.iter().zip(&past).map(|((run, m), past)| {
                let long = taps(&m.moves, view, size).len() > 2;   // a streak of 2 px or less smears the edge by that much at most
                let crossing = run.clone().any(|i| streak(i).is_none_or(|st| st.reach.is_none() || crosses(st.ink, seen)));
                long && crossing && !(wide && past.is_some_and(|p| p < MARGIN - 1.0))
            }).collect();
            // A run whose streak never reaches the frame isn't drawn.
            let off: Vec<bool> = runs.iter().map(|(run, _)| run.clone().all(|i| streak(i).and_then(|st| st.reach).is_some_and(|r| r[2] <= seen[0] || r[0] >= seen[2] || r[3] <= seen[1] || r[1] >= seen[3]))).collect();
            // Runs whose streaks read none of each other's pictures share one picture, painted together (`shares`); one
            // painted at each of its moves (`edge`) has its own. At most `most_kept` pictures a step, the runs past them
            // the next step's.
            let spots: Vec<Option<Spot>> = runs.iter().map(|(run, m)| {
                let ink = joined(run.clone().map(|i| streak(i).filter(|st| st.reach.is_some()).map(|st| st.ink)))?;
                let reach = joined(run.clone().map(|i| streak(i).and_then(|st| st.reach)))?;
                Some(Spot { reads: reads(reach, &m.moves, seen, far, 1.0 / k), ink })
            }).collect();
            let mut pictures: Vec<Vec<usize>> = vec![];
            let mut taken = runs.len();
            for i in 0..runs.len() {
                if off[i] {
                    continue;
                }
                let with = pictures.iter().position(|g| g.iter().all(|&o| !edge[o] && !edge[i] && shares(spots[o], spots[i])));
                match with {
                    Some(g) => pictures[g].push(i),
                    None if pictures.len() + 1 < most_kept => pictures.push(vec![i]),
                    None => {
                        taken = i;
                        break;
                    }
                }
            }
            q = if taken < runs.len() { runs[taken].0.start } else { q };
            let mut slot = vec![0; taken];
            // A run painted at each of its moves (`edge`) is its own picture, averaged; every other picture is made in one
            // paint, each run's pieces drawn into their picture (`Run::Keep`), in stage order.
            let mut keep: HashMap<NodeId, Run> = kids.iter().map(|&o| (o, Run::Skip)).collect();
            let mut kept = 0;
            for g in &pictures {
                if let [r] = g[..] {
                    if edge[r] {
                        let (run, m) = &runs[r];
                        let taps = taps(&m.moves, view, size);
                        let alone: HashMap<NodeId, Run> = kids.iter().enumerate().filter(|(i, _)| !run.contains(i)).map(|(_, &o)| (o, Run::Skip)).collect();
                        for (j, &t) in taps.iter().enumerate() {
                            let mut plan = alone.clone();
                            plan.extend(run.clone().map(|i| (kids[i], Run::Shift(m.moves[t]))));
                            blitz_paint::set_plan(plan);
                            crate::profile::label("mb-edge");
                            timed(s, None, true, false)?;
                            s.painter.accumulate(j == 0, 1.0 / taps.len() as f32)?;
                        }
                        let picture = s.painter.last_image();
                        s.painter.push_cached(picture);
                        slot[r] = s.painter.cached_len() - 1;
                        continue;
                    }
                }
                for &r in g {
                    keep.extend(runs[r].0.clone().map(|i| (kids[i], Run::Keep(kept))));
                    slot[r] = kept;
                }
                kept += 1;
            }
            if kept > 0 {
                // As far past the frame as the pictures' streaks read (what lies there is drawn, not culled).
                let margin = if !wide { 0.0 } else {
                    let most = (0..taken).filter(|&r| !off[r] && !edge[r]).filter_map(|r| past[r]).fold(0.0, f64::max);
                    if most > 0.0 { (most.ceil() + 2.0).min(MARGIN) } else { 0.0 }
                };
                if margin > 0.0 {
                    blitz_paint::set_viewport(Some(kurbo::Rect::new(seen[0] - margin, seen[1] - margin, seen[2] + margin, seen[3] + margin)));
                }
                s.painter.set_kept_margin(margin as i32);
                blitz_paint::set_plan(keep);
                crate::profile::label("mb-picture");
                let painted = timed(s, None, true, false);
                s.painter.set_kept_margin(0);
                blitz_paint::set_viewport(None);
                painted?;
                let first = s.painter.cached_len();
                s.painter.keep_drawn(kept)?;
                for g in pictures.iter().filter(|g| !matches!(g[..], [r] if edge[r])) {
                    g.iter().for_each(|&r| slot[r] += first);
                }
            }
            let (mut plan, mut moves) = (HashMap::new(), vec![]);
            for (i, (run, m)) in runs.iter().take(taken).enumerate() {
                if off[i] {
                    plan.extend(run.clone().map(|k| (kids[k], Run::Skip)));
                    continue;
                }
                if edge[i] {
                    plan.insert(kids[run.start], Run::Cached(slot[i]));
                    for k in run.start + 1..run.end {
                        plan.insert(kids[k], Run::Skip);
                    }
                    continue;
                }
                plan.insert(kids[run.start], Run::Streak(slot[i], moves.len()));
                for k in run.start + 1..run.end {
                    plan.insert(kids[k], Run::Skip);
                }
                // The run's reach: every piece's, joined (unknown for one: the whole frame).
                let reach = joined(run.clone().map(|i| streak(i).and_then(|st| st.reach)));
                let rect = reach.map(|b| [((b[0] - x0) * k).floor() as f32, ((b[1] - y0) * k).floor() as f32, ((b[2] - x0) * k).ceil() as f32, ((b[3] - y0) * k).ceil() as f32]);
                moves.push(blitz_paint::Streak { moves: on_device(&m.moves, view, size), rect });
            }
            end = q;
            once += end - p;
            drawn += moves.len();
            blitz_paint::set_streaks(moves);
            blitz_paint::set_plan(around(&kids, base, p..end, plan));
            crate::profile::label("mb-streaks");
            timed(s, None, true, false)?;
            if end == n && held {
                s.painter.accumulate(true, 1.0)?; // the stage is painted over the sum (serve.rs)
            }
        }
        p = end;
        if p < n {
            let so_far = s.painter.last_image();
            s.painter.clear_cached();
            s.painter.push_cached(so_far);
            base = true;
        }
    }
    crate::profile::label("frame");
    Ok((once, drawn))
}

/// How far past the frame's edges a page drawn at its own size keeps its streak pictures (device px, each side): a
/// 1080p picture with it is (1920 + 2 × 128) × (1080 + 2 × 128) half-float px, 23 MB.
const MARGIN: f64 = 128.0;

/// The plan of one step: the pieces before it as kept picture 0 (the steps before: `base`), the pieces after it skipped,
/// its own as `plan` says (drawn when it doesn't name them).
fn around(kids: &[NodeId], base: bool, step: Range<usize>, mut plan: HashMap<NodeId, Run>) -> HashMap<NodeId, Run> {
    for (i, &k) in kids.iter().enumerate().filter(|(i, _)| !step.contains(i)) {
        plan.insert(k, if i == 0 && base { Run::Cached(0) } else { Run::Skip });
    }
    plan
}

/// Every sub-frame staged and painted whole, averaged (the sub-frames draw different layers: one starts or ends inside
/// the shutter).
fn whole(s: &mut Session, samples: &[&str], cuts: &[Vec<String>], timed: &mut dyn FnMut(&mut Session, Option<&str>, bool, bool) -> Result<(), String>) -> Result<(), String> {
    blitz_paint::set_plan(Default::default());
    let k = 1.0 / samples.len().max(1) as f32;
    for (j, &mk) in samples.iter().enumerate() {
        s.next_pieces = cuts.get(j).cloned();
        timed(s, Some(mk), true, false)?;
        s.painter.accumulate(j == 0, k)?;
    }
    Ok(())
}

/// The picture `ink` runs past an edge of the frame `seen` (page px) without covering the whole frame.
fn crosses(ink: [f64; 4], seen: [f64; 4]) -> bool {
    let covers = ink[0] <= seen[0] && ink[1] <= seen[1] && ink[2] >= seen[2] && ink[3] >= seen[3];
    !covers && (ink[0] < seen[0] || ink[1] < seen[1] || ink[2] > seen[2] || ink[3] > seen[3])
}

/// A run's streak, for sharing a picture: where it reads that picture and where its own picture is (page px).
#[derive(Clone, Copy, Debug)]
struct Spot {
    reads: [f64; 4],
    ink: [f64; 4],
}

/// Two runs may share one picture: each run's size is known, and neither streak reads where the other's picture is
/// (so neither picks up the other's px). None: unknown, never shared.
fn shares(a: Option<Spot>, b: Option<Spot>) -> bool {
    let apart = |x: [f64; 4], y: [f64; 4]| x[2] <= y[0] || y[2] <= x[0] || x[3] <= y[1] || y[3] <= x[1];
    matches!((a, b), (Some(a), Some(b)) if apart(a.reads, b.ink) && apart(b.reads, a.ink))
}

/// Where a streak reads its picture (page px), as the GPU pass does (anyrender_skia `draw_cached_streak`): each px of
/// its `reach` inside the frame `seen` (the rect rounded out to whole device px) reads the picture at that px carried
/// back through every one of its `moves`, held inside the picture `kept` (the frame, or past it by a margin: the picture
/// is stretched past its edges), sampled smoothly. `slack`: what the rounding and the smooth sampling add, each side.
fn reads(reach: [f64; 4], moves: &Moves, seen: [f64; 4], kept: [f64; 4], slack: f64) -> [f64; 4] {
    use crate::rig::math::Aff;
    let grow = |r: [f64; 4]| [r[0] - slack, r[1] - slack, r[2] + slack, r[3] + slack];
    let held = |r: [f64; 4]| [r[0].clamp(seen[0], seen[2]), r[1].clamp(seen[1], seen[3]), r[2].clamp(seen[0], seen[2]), r[3].clamp(seen[1], seen[3])];
    let area = held(grow(reach));
    let corners = [(area[0], area[1]), (area[2], area[1]), (area[0], area[3]), (area[2], area[3])];
    let mut out = [f64::MAX, f64::MAX, f64::MIN, f64::MIN];
    for m in moves {
        // A move that can't be undone: it may read anywhere in the picture.
        let Some(back) = (Aff { a: m[0], b: m[1], c: m[2], d: m[3], e: m[4], f: m[5] }).inverse() else { return grow(kept) };
        for q in corners.map(|p| back.apply(p)) {
            out = [out[0].min(q.0), out[1].min(q.1), out[2].max(q.0), out[3].max(q.1)];
        }
    }
    let kept_in = |r: [f64; 4]| [r[0].clamp(kept[0], kept[2]), r[1].clamp(kept[1], kept[3]), r[2].clamp(kept[0], kept[2]), r[3].clamp(kept[1], kept[3])];
    grow(kept_in(out))
}

/// The rectangles joined (None when one isn't known, or there are none).
fn joined(mut rects: impl Iterator<Item = Option<[f64; 4]>>) -> Option<[f64; 4]> {
    rects.try_fold(None::<[f64; 4]>, |a, b| {
        let b = b?;
        Some(Some(a.map_or(b, |a| [a[0].min(b[0]), a[1].min(b[1]), a[2].max(b[2]), a[3].max(b[3])])))
    }).flatten()
}

/// Two streaks' moves are within a quarter px of each other over the frame: one picture, one streak.
fn alike(a: &Moves, b: &Moves) -> bool {
    a.len() == b.len() && a.iter().zip(b).all(|(x, y)| (0..4).all(|i| (x[i] - y[i]).abs() <= 1e-4) && (x[4] - y[4]).abs() <= 0.25 && (x[5] - y[5]).abs() <= 0.25)
}

/// Page px moves carried to the painter's device px (a view at `scale` whose top-left is page px (x0, y0)), thinned
/// to `taps`.
fn on_device(m: &Moves, view: (f32, f32, f32), size: (u32, u32)) -> Moves {
    let dev: Moves = m.iter().filter_map(|d| crate::still_runs::delta(*d, [1.0, 0.0, 0.0, 1.0, 0.0, 0.0], view)).collect();
    taps(m, view, size).into_iter().filter_map(|i| dev.get(i).copied()).collect()
}

/// Which of the moves a streak takes: one per device px of its longest path over the `w` × `h` picture (crate::motion
/// steps.rs GAP_PX), at least 2, evenly spread.
fn taps(m: &Moves, view: (f32, f32, f32), (w, h): (u32, u32)) -> Vec<usize> {
    let k = view.0 as f64;
    let (x0, y0) = (view.1 as f64, view.2 as f64);
    let corner = |d: &[f64; 6], (x, y): (f64, f64)| (d[0] * x + d[2] * y + d[4], d[1] * x + d[3] * y + d[5]);
    let page = [(x0, y0), (x0 + w as f64 / k, y0), (x0, y0 + h as f64 / k), (x0 + w as f64 / k, y0 + h as f64 / k)];
    let path: f64 = m.windows(2).map(|p| page.iter().map(|&c| {
        let (a, b) = (corner(&p[0], c), corner(&p[1], c));
        (b.0 - a.0).hypot(b.1 - a.1) * k
    }).fold(0.0, f64::max)).sum();
    let n = m.len();
    let taps = ((path - 1e-9).ceil() as usize).clamp(2, n.max(2));
    if taps >= n {
        return (0..n).collect();
    }
    (0..taps).map(|i| (((i as f64 + 0.5) * n as f64 / taps as f64) as usize).min(n - 1)).collect()
}

#[cfg(test)]
mod tests {
    use super::{reads, shares, Spot};

    /// A box sliding right from `x0` to `x1` page px over 9 sub-frames: its moves and its reach.
    fn slide(ink: [f64; 4], x0: f64, x1: f64) -> (super::Moves, [f64; 4]) {
        let moves = (0..9).map(|j| [1.0, 0.0, 0.0, 1.0, x0 + (x1 - x0) * j as f64 / 8.0, 0.0]).collect();
        (moves, [ink[0] + x0, ink[1], ink[2] + x1, ink[3]])
    }

    fn spot(ink: [f64; 4], x0: f64, x1: f64) -> Option<Spot> {
        let (moves, reach) = slide(ink, x0, x1);
        Some(Spot { reads: reads(reach, &moves, [0.0, 0.0, 1920.0, 1080.0], [0.0, 0.0, 1920.0, 1080.0], 1.0), ink })
    }

    #[test]
    fn streaks_share_a_picture_only_when_neither_reads_the_others() {
        // Far apart: one picture.
        assert!(shares(spot([100.0, 100.0, 140.0, 140.0], 0.0, 60.0), spot([600.0, 100.0, 640.0, 140.0], 0.0, 2.0)));
        // A dot sliding 60 px right, a still one 30 px behind where it starts: their reaches miss each other's pictures,
        // but the streak's px past its start read back over the still dot (the moves undone), so they don't share.
        assert!(!shares(spot([100.0, 100.0, 140.0, 140.0], 0.0, 60.0), spot([30.0, 100.0, 70.0, 140.0], 0.0, 2.0)));
        // Reads held inside the frame: a dot sliding in from past the left edge reads the frame's edge px only.
        assert!(shares(spot([-80.0, 100.0, -20.0, 140.0], 0.0, 120.0), spot([300.0, 100.0, 340.0, 140.0], 0.0, 2.0)));
        // A run whose size isn't known never shares.
        assert!(!shares(None, spot([600.0, 100.0, 640.0, 140.0], 0.0, 2.0)));
    }
}
