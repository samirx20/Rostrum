//! Where each letter of a text layer goes when it is drawn letter by letter (stage_type.rs): on its lines as the
//! normal text sits, or along `path`, each letter turned to the path's direction. One placement for both, so a
//! text on a path can also play its keys letter by letter. Advances are the font's own (type_font.rs).

use kurbo::{BezPath, ParamCurve, ParamCurveArclen, PathSeg, Point, Shape};

use super::eval::Item;
use super::type_font;

type R<T> = Result<T, String>;

const ACCURACY: f64 = 0.01;

/// One visible letter: its point on the baseline (the middle of its advance, in the layer's own px), the angle
/// its baseline turns to (degrees), its advance, and the unit (letter or word) it is ordered by.
pub struct Letter {
    pub ch: char,
    pub unit: usize,
    pub x: f64,
    pub y: f64,
    pub angle: f64,
    pub advance: f64,
}

/// The letters, the layer's box (w × h) and each letter box's line height and baseline (from its top).
pub struct Placed {
    pub letters: Vec<Letter>,
    pub w: f64,
    pub h: f64,
    pub line: f64,
    pub baseline: f64,
}

pub fn place(it: &Item) -> R<Placed> {
    if it.num("boxWidth") != 0.0 {
        return Err(format!("{}.boxWidth: text wrapped in a box is not drawn letter by letter yet (boxWidth 0, or no path and letterDelay 0)", it.id));
    }
    let lines: Vec<&str> = it.str("body").split('\n').collect();
    let measures = lines.iter().map(|l| type_font::measure(it, l)).collect::<R<Vec<_>>>()?;
    let line = it.num("lineHeight") * it.num("size");
    let (ascent, descent) = measures.first().map_or((0.0, 0.0), |m| (m.ascent, m.descent));
    let baseline = (line - ascent - descent) / 2.0 + ascent;
    let widths: Vec<f64> = measures.iter().map(|m| m.advances.iter().sum()).collect();
    let path = it.str("path");
    let mut letters = vec![];
    let mut units = Units::new(it.str("letterSplit") == "words");
    if path.is_empty() {
        let w = widths.iter().copied().fold(0.0, f64::max);
        for (i, (text, m)) in lines.iter().zip(&measures).enumerate() {
            let mut pen = match it.str("align") { "left" => 0.0, "right" => w - widths[i], _ => (w - widths[i]) / 2.0 };
            for (ch, adv) in text.chars().zip(&m.advances) {
                if let Some(unit) = units.next(ch) {
                    letters.push(Letter { ch, unit, x: pen + adv / 2.0, y: i as f64 * line + baseline, angle: 0.0, advance: *adv });
                }
                pen += adv;
            }
            units.next('\n');
        }
        return Ok(Placed { letters, w, h: lines.len() as f64 * line, line, baseline });
    }
    if lines.len() > 1 {
        return Err(format!("{}.body: text on a path is one line (no line breaks)", it.id));
    }
    let along = Along::new(it, path)?;
    // A text following a path layer sits on the part of it that is drawn (its trim window, follow.rs).
    let followed = super::follow::window(it);
    let (from, to) = followed.map_or((0.0, along.total), |((a, b), _)| (a * along.total, b.max(a) * along.total));
    // Past either end of the path a letter is left out ("hide", the default), or the path goes on straight; a
    // letter on the trimmed-off part of a followed path is always left out.
    let straight = it.str("pathOverflow") == "straight";
    let lo = if straight && from <= 0.0 { f64::NEG_INFINITY } else { from };
    let hi = if straight && to >= along.total { f64::INFINITY } else { to };
    let mut pen = match it.str("pathAlign") { "end" => to - widths[0], "center" => from + (to - from - widths[0]) / 2.0, _ => from } + it.num("pathOffset");
    for (ch, adv) in lines[0].chars().zip(&measures[0].advances) {
        let centre = pen + adv / 2.0;
        if let Some(unit) = units.next(ch).filter(|_| (lo..=hi).contains(&centre)) {
            let (p, angle) = along.at(centre);
            letters.push(Letter { ch, unit, x: p.x, y: p.y, angle, advance: *adv });
        }
        pen += adv;
    }
    let (w, h) = followed.map_or_else(|| { let b = along.path.bounding_box(); (b.x1.max(0.0), b.y1.max(0.0)) }, |(_, size)| size);
    Ok(Placed { letters, w, h, line, baseline })
}

/// Counts units: every letter, or every word (spaces and line breaks belong to none).
struct Units {
    words: bool,
    count: usize,
    gap: bool,
}

impl Units {
    fn new(words: bool) -> Units {
        Units { words, count: 0, gap: true }
    }

    fn next(&mut self, ch: char) -> Option<usize> {
        if ch.is_whitespace() {
            self.gap = true;
            return None;
        }
        if !self.words || self.gap {
            self.count += 1;
        }
        self.gap = false;
        Some(self.count - 1)
    }
}

/// A path walked by length: its segments (zero-length ones left out) and where each starts.
struct Along {
    path: BezPath,
    segs: Vec<(PathSeg, f64, f64)>,
    total: f64,
}

impl Along {
    fn new(it: &Item, d: &str) -> R<Along> {
        let path = BezPath::from_svg(d).map_err(|e| format!("{}.path: {e}", it.id))?;
        let mut segs = vec![];
        let mut total = 0.0;
        for s in path.segments() {
            let len = s.arclen(ACCURACY);
            if len > 1e-9 {
                segs.push((s, total, len));
                total += len;
            }
        }
        if segs.is_empty() {
            return Err(format!("{}.path: the path has no length", it.id));
        }
        Ok(Along { path, segs, total })
    }

    /// The point at length `s` along the path and the direction there (degrees); before the start and past the
    /// end the path goes on straight.
    fn at(&self, s: f64) -> (Point, f64) {
        let i = self.segs.iter().rposition(|(_, from, _)| *from <= s).unwrap_or(0);
        let (seg, from, len) = &self.segs[i];
        let local = s - from;
        let t = if local <= 0.0 { 0.0 } else if local >= *len { 1.0 } else { seg.inv_arclen(local, ACCURACY) };
        let (a, b) = (seg.eval((t - 1e-4).max(0.0)), seg.eval((t + 1e-4).min(1.0)));
        let d = (b - a).normalize();
        let over = if local < 0.0 { local } else if local > *len { local - len } else { 0.0 };
        (seg.eval(t) + d * over, d.y.atan2(d.x).to_degrees())
    }
}

/// Each letter's place in the animate-on order (0 = first; equal places start together), by `letterOrder`.
pub fn ranks(it: &Item, letters: &[Letter]) -> Vec<f64> {
    let n = letters.last().map_or(0, |l| l.unit + 1);
    let of_unit: Vec<f64> = match it.str("letterOrder") {
        "backward" => (0..n).map(|i| (n - 1 - i) as f64).collect(),
        "center" => {
            let mid = (n as f64 - 1.0) / 2.0;
            let near = if n % 2 == 0 { 0.5 } else { 0.0 };
            (0..n).map(|i| (i as f64 - mid).abs() - near).collect()
        }
        "random" => shuffled(n, it.num("letterSeed") as u64),
        _ => (0..n).map(|i| i as f64).collect(),
    };
    letters.iter().map(|l| of_unit[l.unit]).collect()
}

/// A shuffled order of n places (Fisher–Yates on splitmix64), the same for the same seed on every machine.
fn shuffled(n: usize, seed: u64) -> Vec<f64> {
    let mut state = seed;
    let mut next = || {
        state = state.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = state;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    };
    let mut order: Vec<usize> = (0..n).collect();
    for i in (1..n).rev() {
        order.swap(i, (next() % (i as u64 + 1)) as usize);
    }
    let mut rank = vec![0.0; n];
    for (place, unit) in order.into_iter().enumerate() {
        rank[unit] = place as f64;
    }
    rank
}
