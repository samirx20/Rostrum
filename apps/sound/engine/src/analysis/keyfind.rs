//! The key of a recording (analyze.rs): each of the 24 keys is scored on four witnesses, each on its
//! own evidence, and the best wins (the runner-up is named, so a close call can be said):
//! 1. The scale: the whole piece's pitch-class profile against the Krumhansl–Kessler profiles. A scale
//!    has two tonics (C major and A minor share their notes) and a neighbour a fifth away differs by
//!    one note, so this alone misreads (benchmark b07: Em–C–G–D as G major; a chip loop Em–C–D–Bm as
//!    B minor; a C-minor trailer whose G sounds in every part as G minor).
//! 2. The notes: how much of the bass (each moment's lowest note, 30 … 160 Hz), the melody (250 Hz … 2 kHz) and the chords
//!    (by time) is in the key's scale (a minor key's chords may raise the 7th: V and vii° are its own).
//! 3. The tonic: where the music stands and where it starts and ends — the bass on the tonic, the time
//!    on chords rooted there and the chords the piece opens and closes on (a loop or a cue opens on its
//!    tonic; a cadence ends on it).
//! 4. The mode: the time on the tonic chord in the key's quality against the other (a low root's 5th
//!    harmonic is its major third, which can fool the profile).

pub const NAMES: [&str; 12] = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

/// A chord name's root (pitch class), when it has one ("N" has none).
fn root_of(name: &str) -> Option<usize> {
    let two = name.get(..2).and_then(|p| NAMES.iter().position(|n| *n == p));
    two.or_else(|| name.get(..1).and_then(|p| NAMES.iter().position(|n| *n == p)))
}

fn correlate(c: &[f64; 12], p: &[f64; 12], root: usize) -> f64 {
    let (mx, my) = (c.iter().sum::<f64>() / 12.0, p.iter().sum::<f64>() / 12.0);
    let (mut num, mut dx, mut dy) = (0.0, 0.0, 0.0);
    for i in 0..12 {
        let (x, y) = (c[(i + root) % 12] - mx, p[i] - my);
        num += x * y;
        dx += x * x;
        dy += y * y;
    }
    num / (dx * dy).sqrt().max(1e-12)
}

/// How strongly the piece stands on `t`: bass root share + chord-time share + its opening and closing chords.
fn tonic_evidence(t: usize, bass: &[f64; 12], chords: &[(f64, f64, String)]) -> f64 {
    let bass_total = bass.iter().sum::<f64>();
    let bass_share = if bass_total > 0.0 { bass[t] / bass_total } else { 0.0 };
    let sounded: Vec<(f64, usize)> = chords.iter().filter_map(|(a, b, n)| root_of(n).map(|r| (b - a, r))).collect();
    let total: f64 = sounded.iter().map(|c| c.0).sum();
    let chord_share = if total > 0.0 { sounded.iter().filter(|c| c.1 == t).map(|c| c.0).sum::<f64>() / total } else { 0.0 };
    let ends = [sounded.first(), sounded.last()].iter().filter(|c| c.is_some_and(|c| c.1 == t)).count() as f64;
    bass_share + chord_share + 0.25 * ends
}

/// The notes of a key's scale (a minor key's with its raised 7th when `leading`: the harmonic minor's V).
fn scale(tonic: usize, minor: bool, leading: bool) -> Vec<usize> {
    let steps: &[usize] = if minor { &[0, 2, 3, 5, 7, 8, 10] } else { &[0, 2, 4, 5, 7, 9, 11] };
    let mut s: Vec<usize> = steps.iter().map(|d| (tonic + d) % 12).collect();
    if minor && leading {
        s.push((tonic + 11) % 12);
    }
    s
}

/// The chord shapes the chords are read as (name suffix, intervals from the root), and a chord's tones.
const SHAPES: [(&str, &[usize]); 8] = [("", &[0, 4, 7]), ("m", &[0, 3, 7]), ("7", &[0, 4, 7, 10]), ("maj7", &[0, 4, 7, 11]), ("m7", &[0, 3, 7, 10]), ("sus4", &[0, 5, 7]), ("dim", &[0, 3, 6]), ("5", &[0, 7])];

fn tones(name: &str) -> Option<Vec<usize>> {
    let root = root_of(name)?;
    let (_, iv) = SHAPES.iter().find(|(q, _)| *q == &name[NAMES[root].len()..])?;
    Some(iv.iter().map(|i| (root + i) % 12).collect())
}

/// The chord a pitch-class profile fits best (or None when it fits none well): the cosine against
/// each shape's template, its root weighted most and a seventh least, so a triad is not read as a
/// seventh chord whose root is a passing note (C–E–G with a little A is C, not Am7).
pub fn chord(c: &[f64; 12]) -> Option<String> {
    let norm = c.iter().map(|v| v * v).sum::<f64>().sqrt().max(1e-12);
    let mut best = (None, 0.0);
    for root in 0..12 {
        for (name, iv) in SHAPES {
            let w = |i: usize| if i == 0 { 1.0 } else if iv[i] >= 10 { 0.6 } else { 0.8 };
            let dot: f64 = (0..iv.len()).map(|i| w(i) * c[(root + iv[i]) % 12]).sum();
            let cos = dot / (norm * (0..iv.len()).map(|i| w(i) * w(i)).sum::<f64>().sqrt());
            if cos > best.1 {
                best = (Some(format!("{}{}", NAMES[root], name)), cos);
            }
        }
    }
    if best.1 > 0.55 { best.0 } else { None }
}

/// A frame's bass note (pitch class): its lowest clear peak from 30 to 160 Hz (a quarter of the
/// strongest there or more), read between bins; None when nothing sounds there.
pub fn bass_note(mag: &[f64], bin_hz: f64) -> Option<usize> {
    let (lo, hi) = ((30.0 / bin_hz).floor() as usize, ((160.0 / bin_hz).ceil() as usize).min(mag.len().saturating_sub(2)));
    let top = (lo..=hi).map(|k| mag[k]).fold(0.0, f64::max);
    if top <= 1e-9 {
        return None;
    }
    let k = (lo.max(1)..=hi).find(|&k| mag[k] >= 0.25 * top && mag[k] >= mag[k - 1] && mag[k] >= mag[k + 1])?;
    let (a, b, c) = ((mag[k - 1] + 1e-12).ln(), (mag[k] + 1e-12).ln(), (mag[k + 1] + 1e-12).ln());
    let shift = if a - 2.0 * b + c != 0.0 { (0.5 * (a - c) / (a - 2.0 * b + c)).clamp(-0.5, 0.5) } else { 0.0 };
    let hz = (k as f64 + shift) * bin_hz;
    Some(((69.0 + 12.0 * (hz / 440.0).log2()).round() as i64).rem_euclid(12) as usize)
}

/// The share of a profile on these notes.
fn share(p: &[f64; 12], notes: &[usize]) -> f64 {
    notes.iter().map(|n| p[*n]).sum::<f64>() / p.iter().sum::<f64>().max(1e-12)
}

/// The key ("E minor"), how far its score was ahead of the runner-up's, and the runner-up.
pub fn key(c: &[f64; 12], bass: &[f64; 12], melody: &[f64; 12], chords: &[(f64, f64, String)]) -> (String, f64, String) {
    const MAJOR: [f64; 12] = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88];
    const MINOR: [f64; 12] = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17];
    let sounded: Vec<(f64, Vec<usize>, Option<usize>)> = chords.iter().filter_map(|(a, b, n)| tones(n).map(|t| (b - a, t, root_of(n)))).collect();
    let time = sounded.iter().map(|c| c.0).sum::<f64>().max(1e-12);
    let score = |tonic: usize, minor: bool| -> f64 {
        let profile = correlate(c, if minor { &MINOR } else { &MAJOR }, tonic);
        let (plain, with_v) = (scale(tonic, minor, false), scale(tonic, minor, true));
        let fit = sounded.iter().filter(|(_, t, _)| t.iter().all(|n| with_v.contains(n))).map(|c| c.0).sum::<f64>() / time;
        let third = |m: bool| sounded.iter().filter(|(_, t, r)| *r == Some(tonic) && t.contains(&((tonic + if m { 3 } else { 4 }) % 12))).map(|c| c.0).sum::<f64>() / time;
        let (te, md) = (tonic_evidence(tonic, bass, chords), (third(minor) - third(!minor)) / (third(minor) + third(!minor)).max(1e-9));
        profile + share(bass, &plain) + share(melody, &plain) + fit + te + 0.2 * md
    };
    let mut all: Vec<(usize, bool, f64)> = (0..12).flat_map(|r| [(r, false, score(r, false)), (r, true, score(r, true))]).collect();
    all.sort_by(|a, b| b.2.total_cmp(&a.2));
    let name = |k: &(usize, bool, f64)| format!("{} {}", NAMES[k.0], if k.1 { "minor" } else { "major" });
    (name(&all[0]), all[0].2 - all[1].2, name(&all[1]))
}

#[cfg(test)]
mod tests {
    use std::f64::consts::PI;

    /// A loop of triads (MIDI notes), one bar each at 120 BPM, its root an octave and a half down in
    /// the bass, a kick on every beat; twice through, at 22050 Hz.
    fn progression(chords: &[[i32; 3]]) -> Vec<f32> {
        let sr = 22050.0;
        let hz = |m: i32| 440.0 * 2f64.powf((m - 69) as f64 / 12.0);
        let bar = 2.0;
        let len = (2.0 * bar * chords.len() as f64 * sr) as usize;
        (0..len)
            .map(|i| {
                let t = i as f64 / sr;
                let c = chords[(t / bar) as usize % chords.len()];
                let b = t % 0.5;
                let kick = (2.0 * PI * 55.0 * b).sin() * (-b * 30.0).exp() * 0.5;
                let triad: f64 = c.iter().map(|m| (2.0 * PI * hz(*m) * t).sin() * 0.1).sum();
                (kick + triad + (2.0 * PI * hz(c[0] - 24) * t).sin() * 0.25) as f32
            })
            .collect()
    }

    fn key_of(chords: &[[i32; 3]]) -> String {
        crate::analysis::analyze::analyze(&progression(chords), 22050.0, false)["key"]["name"].as_str().unwrap().to_string()
    }

    /// The same four chords' notes in a minor key and in its relative major (benchmark b07: Em–C–G–D was G major).
    #[test]
    fn tells_a_minor_key_from_its_relative_major() {
        let (em, c, g, d) = ([64, 67, 71], [60, 64, 67], [55, 59, 62], [62, 66, 69]);
        assert_eq!(key_of(&[em, c, g, d]), "E minor");
        assert_eq!(key_of(&[g, d, em, c]), "G major");
        let (am, f, gg) = ([57, 60, 64], [53, 57, 60], [55, 59, 62]);
        assert_eq!(key_of(&[am, f, c, gg]), "A minor");
        assert_eq!(key_of(&[c, gg, am, f]), "C major");
    }

    /// A neighbour a fifth away shares six notes (benchmark b7: a chip loop Em–C–D–Bm read as B minor):
    /// the C chord is not in B minor.
    #[test]
    fn tells_a_key_from_its_neighbour_a_fifth_away() {
        let (em, c, d, bm) = ([64, 67, 71], [60, 64, 67], [62, 66, 69], [59, 62, 66]);
        assert_eq!(key_of(&[em, c, d, bm]), "E minor");
    }
}
