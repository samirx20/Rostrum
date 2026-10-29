//! An export's still stage slid under a moving frame (export_crew.rs `draw_frames`). When only the camera moves between
//! a worker's frames (a slow drift over a still stretch), every layer's piece is the same markup but for its frame
//! wrapper's translation (frame/mod.rs `place`), so the layers are drawn once into a kept picture a `MARGIN` px wider
//! on every side (the page's clip lifted, as the world picture draws: scene_world.rs) and each frame is its background
//! with that picture laid over it, moved by whole px (blitz-paint `Run::Moved`; a whole-px move samples each px
//! exactly, no blur). Nothing is laid out or painted again but the background.
//!
//! The frame's position is snapped to a `grid` (¼ px by default): a slid frame is the picture drawn with every
//! wrapper moved by under ⅛ px, the same whichever kept picture it came from (one per ¼-px phase, at most `most`).
//! Drawn whole instead, as before: a frame with motion blur, an export with transparency (`alpha`), a wrapper
//! that blends, sits in a matte or turns/zooms between frames, wrappers that move unalike (layers at other depths, a
//! pinned one), a move past the margin. A kept picture is made only on a worker's second frame of the same still stage
//! (a moving stretch is never slowed by kept pictures it would not use).
//! Off unless asked (`"slide": true` in the export request, or `ROSTRUM_SLIDE=1` / `=<n>` for a 1/n px grid): measured on
//! Haiku's drift (2026-10-29) a still stretch drew 8-30 % faster, but 0.2-0.7 % of its px differed from the frame drawn
//! whole, by up to 95 of 255 at edges (the ⅛-px snap): the export would no longer be the canvas's picture (preview ≡
//! export), for a gain on a stage that was not the export's limit.

use std::collections::HashMap;
use std::hash::{Hash, Hasher};

use serde_json::{json, Value};

use crate::scene_serve::{draw, Held, Staged};
use crate::serve::{self, Session};
use crate::still_runs::regroups;

/// Px kept round the frame on every side of a kept picture: the farthest a frame slides from it.
const MARGIN: i64 = 32;
/// Kept pictures a worker holds at most (bytes): each is the frame plus its margin at the surface's half floats.
const MOST_BYTES: usize = 384 << 20;
/// A frame's still stage: its key (the pieces without their wrappers' translations, and the wrappers' offsets from the
/// first one) and the first wrapper's translation, in thousandths of a px (as the matrix is written: `{:.3}`).
struct Still {
    key: u128,
    at: (i64, i64),
}

/// One kept picture: drawn with the first wrapper at `at` (on the grid, thousandths of a px), kept in `slot`.
struct Base {
    at: (i64, i64),
    slot: usize,
}

/// A worker's kept pictures and its last frame's still key.
pub(crate) struct Slides {
    on: bool,
    /// Thousandths of a px between snapped positions (250: ¼ px).
    grid: i64,
    most: usize,
    key: Option<u128>,
    bases: Vec<Base>,
    last: Option<u128>,
    pub slid: u64,
    pub made: u64,
}

impl Slides {
    pub(crate) fn new(s: &Session, req: &Value) -> Slides {
        let env = std::env::var("ROSTRUM_SLIDE").ok();
        let asked = req["slide"].as_bool().unwrap_or_else(|| env.as_deref().is_some_and(|v| v != "0"));
        let on = asked && req["alpha"].as_bool() != Some(true);
        // ROSTRUM_SLIDE=<n>: a 1/n px grid (to measure the difference at other grids).
        let grid = env.and_then(|v| v.parse::<i64>().ok()).filter(|n| (2..=1000).contains(n)).map_or(250, |n| 1000 / n);
        let bytes = (s.width as usize + 2 * MARGIN as usize) * (s.height as usize + 2 * MARGIN as usize) * 8;
        Slides { on, grid, most: (MOST_BYTES / bytes.max(1)).min(16), key: None, bases: vec![], last: None, slid: 0, made: 0 }
    }

    /// Frame `f` (export_crew.rs's request for it) drawn from its kept picture when it can: its reply, with the kept
    /// picture's own drawing's steps added when it was made now. None: the caller draws it whole (`before_whole` first).
    pub(crate) fn try_slide(&mut self, held: &Held, s: &mut Session, f: &Value, staged: &Staged) -> Result<Option<Value>, String> {
        let still = if self.on && !staged.blurred() { still_of(staged.pieces()) } else { None };
        let Some(still) = still else {
            self.last = None;
            return Ok(None);
        };
        let seen = self.last.replace(still.key) == Some(still.key);
        // Another frame (a motion-blurred one) used the kept slots: these are gone.
        if self.bases.len() != s.painter.cached_len() {
            self.forget(s);
        }
        let q = (snap(still.at.0, self.grid), snap(still.at.1, self.grid));
        let fits = |b: &Base| ((q.0 - b.at.0) % 1000, (q.1 - b.at.1) % 1000) == (0, 0) && (q.0 - b.at.0).abs() <= MARGIN * 1000 && (q.1 - b.at.1).abs() <= MARGIN * 1000;
        let mut found = (self.key == Some(still.key)).then(|| self.bases.iter().find(|b| fits(b))).flatten().map(|b| (b.at, b.slot));
        let mut base_reply = Value::Null;
        if found.is_none() {
            if !seen || self.most < 1 {
                return Ok(None);
            }
            let near = |b: &Base| (q.0 - b.at.0).abs() <= MARGIN * 1000 && (q.1 - b.at.1).abs() <= MARGIN * 1000;
            if self.key != Some(still.key) || !self.bases.iter().any(near) {
                self.forget(s);
            }
            if self.bases.len() >= self.most {
                return Ok(None);
            }
            self.key = Some(still.key);
            let pieces = moved(staged.pieces(), (q.0 - still.at.0, q.1 - still.at.1), true).ok_or("slide: a frame wrapper could not be written again")?;
            base_reply = self.keep(held, s, f, staged.t, pieces)?;
            self.bases.push(Base { at: q, slot: s.painter.cached_len() - 1 });
            found = Some((q, s.painter.cached_len() - 1));
        }
        let (at, slot) = found.unwrap();
        // The page: the kept picture's stage with the frame's own background (its node is the one painted).
        let mut page = moved(staged.pieces(), (at.0 - still.at.0, at.1 - still.at.1), false).ok_or("slide: a frame wrapper could not be written again")?;
        page[0] = staged.pieces()[0].clone();
        s.next_pieces = Some(page.clone());
        serve::apply(s, &page.concat())?;
        let kids = serve::stage_kids(s);
        if kids.len() != page.len() {
            return Err(format!("slide: the stage has {} elements for {} pieces", kids.len(), page.len()));
        }
        let (dx, dy) = ((q.0 - at.0) / 1000 - MARGIN, (q.1 - at.1) / 1000 - MARGIN);
        let mut plan: HashMap<_, _> = kids[2..].iter().map(|&k| (k, blitz_paint::Run::Skip)).collect();
        plan.insert(kids[1], blitz_paint::Run::Moved(slot, [1.0, 0.0, 0.0, 1.0, dx as f64, dy as f64]));
        blitz_paint::set_plan(plan);
        let drawn = draw(held, s, f, Staged::of(staged.t, page));
        blitz_paint::set_plan(Default::default());
        let (mut reply, _) = drawn?;
        self.slid += 1;
        if let (Some(t), Some(b)) = (reply["timing"].as_object_mut(), base_reply["timing"].as_object()) {
            for (k, v) in b {
                if let (Some(a), Some(v)) = (t.get(k).and_then(Value::as_f64), v.as_f64()) {
                    t.insert(k.clone(), json!(a + v));
                }
            }
        }
        reply["timing"]["evalMs"] = json!(staged.eval_ms());
        Ok(Some(reply))
    }

    /// Before a frame is drawn whole: a motion-blurred frame keeps its own pictures from slot 0 (serve.rs), so these go.
    pub(crate) fn before_whole(&mut self, s: &mut Session, staged: &Staged) {
        if staged.blurred() {
            self.forget(s);
        }
    }

    /// The kept pictures let go (a new still stage, the export's end).
    pub(crate) fn forget(&mut self, s: &mut Session) {
        if !self.bases.is_empty() || s.painter.cached_len() > 0 {
            s.painter.clear_cached();
        }
        (self.bases, self.key) = (vec![], None);
    }

    /// The layers of `pieces` (background cleared) drawn in the second set of surfaces, the margin round the frame, and
    /// kept (painter.rs `keep_cached`). The frames in flight go to the encoder first (the surfaces trade only then).
    fn keep(&mut self, held: &Held, s: &mut Session, f: &Value, t: f64, pieces: Vec<String>) -> Result<Value, String> {
        serve::drain(s)?;
        let (w, h) = (s.width as i64 + 2 * MARGIN, s.height as i64 + 2 * MARGIN);
        let req = json!({ "t": t, "index": f["index"], "pixels": true, "noRead": true,
            "pageView": { "x": -MARGIN, "y": -MARGIN, "w": w, "h": h, "scale": 1.0 } });
        s.painter.swap_aside()?;
        let drawn = draw(held, s, &req, Staged::of(t, pieces));
        if drawn.is_ok() {
            s.painter.keep_cached();
        }
        s.painter.swap_aside()?;
        self.made += 1;
        Ok(drawn?.0)
    }
}

/// `v` thousandths of a px on the nearest grid point.
fn snap(v: i64, grid: i64) -> i64 {
    (v + grid / 2).div_euclid(grid) * grid
}

/// A frame's still stage when it may slide: a background, then frame wrappers that composite plainly (still_runs.rs
/// `movable`), none turned or sized unlike the frame before (their whole matrix but the translation is in the key).
fn still_of(pieces: &[String]) -> Option<Still> {
    if pieces.len() < 2 || pieces[0].starts_with("<div id=\"cam~") {
        return None;
    }
    let mut h = std::collections::hash_map::DefaultHasher::new();
    pieces[0].hash(&mut h);
    let mut first = None;
    for p in &pieces[1..] {
        let m = movable(p)?;
        let at = ((m[4] * 1000.0).round() as i64, (m[5] * 1000.0).round() as i64);
        let first = *first.get_or_insert(at);
        with_matrix(p, "M")?.hash(&mut h);
        m[..4].iter().for_each(|v| v.to_bits().hash(&mut h));
        (at.0 - first.0, at.1 - first.1).hash(&mut h);
    }
    let lo = h.finish() as u128;
    pieces.len().hash(&mut h);
    Some(Still { key: (h.finish() as u128) << 64 | lo, at: first? })
}

/// `pieces` with every wrapper moved by `by` thousandths of a px; `clear`: the background left out (a kept picture).
fn moved(pieces: &[String], by: (i64, i64), clear: bool) -> Option<Vec<String>> {
    let mut out = Vec::with_capacity(pieces.len());
    out.push(if clear { "<div style=\"position:absolute;left:0;top:0;width:100%;height:100%;\"></div>".to_string() } else { pieces[0].clone() });
    for p in &pieces[1..] {
        let m = movable(p)?;
        let (e, f) = ((m[4] * 1000.0).round() as i64 + by.0, (m[5] * 1000.0).round() as i64 + by.1);
        out.push(with_matrix(p, &format!("matrix({:.6}, {:.6}, {:.6}, {:.6}, {:.3}, {:.3})", m[0], m[1], m[2], m[3], e as f64 / 1000.0, f as f64 / 1000.0))?);
    }
    Some(out)
}

/// A frame wrapper's piece cut round its matrix: (text before the numbers, the matrix, text after) (frame/mod.rs writes
/// `<div id="cam~<id>" style="…transform:matrix(a, b, c, d, e, f);…">`).
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

/// The piece with its frame matrix written as `matrix` (`matrix(…)`).
fn with_matrix(piece: &str, matrix: &str) -> Option<String> {
    let (a, _, b) = split(piece)?;
    Some(format!("{}{matrix}{}", &a[..a.len() - "matrix(".len()], &b[1..]))
}

/// The piece's frame matrix, when it is a frame wrapper that composites plainly (still_runs.rs `regroups`): a piece that
/// may be drawn once and moved.
fn movable(piece: &str) -> Option<[f64; 6]> {
    split(piece).filter(|_| regroups(piece)).map(|(_, m, _)| m)
}

#[cfg(test)]
mod tests {
    fn w(id: &str, x: f64) -> String {
        format!("<div id=\"cam~{id}\" style=\"position:absolute;transform-origin:0 0;transform:matrix(1.000000, 0.000000, 0.000000, 1.000000, {x:.3}, 0.000);\"><i></i></div>")
    }

    #[test]
    fn a_drift_keeps_the_key_and_moves_the_position() {
        let bg = "<div style=\"background:#000;\"></div>".to_string();
        let a = super::still_of(&[bg.clone(), w("a", -0.02), w("b", -0.02)]).unwrap();
        let b = super::still_of(&[bg.clone(), w("a", -0.04), w("b", -0.04)]).unwrap();
        assert_eq!(a.key, b.key);
        assert_eq!((a.at, b.at), ((-20, 0), (-40, 0)));
        assert_ne!(super::still_of(&[bg.clone(), w("a", -0.04), w("b", -0.08)]).unwrap().key, a.key, "layers moving unalike");
        assert!(super::still_of(&[bg.clone(), w("a", 0.0).replace("style=\"", "style=\"mix-blend-mode:screen;")]).is_none(), "a blend");
        assert_eq!((super::snap(-130, 250), super::snap(-120, 250), super::snap(1130, 250)), (-250, 0, 1250));
        let m = super::moved(&[bg.clone(), w("a", -0.02)], (-230, 0), true).unwrap();
        assert_eq!(m[1], w("a", -0.25));
        assert!(!m[0].contains("background"));
    }
}
