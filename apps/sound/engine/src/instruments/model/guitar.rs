//! An acoustic guitar: six waveguide strings (string.rs), each note on the string a player would use
//! (a new note on a string stops the one ringing there), plucked by a pick or a fingertip at a point
//! along the string, two polarisations per string (a slightly different pitch and decay, so a note
//! beats and decays in two stages like a real one), and all strings sounding through one wooden body —
//! a bank of the body's resonances (air, top and back modes), not a recorded impulse response.

use super::modal::{one_pole, Mode, Resonator};
use super::string::{t60_at, Material, StringLoop};
use super::{Note, Rng};
use crate::instruments::pan_gains;

pub struct Guitar {
    pub string: Material,
    /// The pluck: the contact's length in seconds at full velocity (a pick is short, a fingertip long).
    pub contact: f64,
    /// Where it is plucked, as a fraction of the string from the bridge.
    pub position: f64,
    /// The excitation's brightness: low-pass cutoff at velocity 0 and 1 (Hz).
    pub bright: (f64, f64),
    /// Pick scrape noise level.
    pub scrape: f64,
    /// Body resonances: Hz, Q, peak gain.
    pub body: &'static [(f64, f64, f64)],
    pub direct: f64,
    pub level: f64,
}

pub const STEEL: Guitar = Guitar {
    string: Material { t60_low: 14.0, t60_high: 6.0, loss: 0.12, stiffness: -0.18 },
    contact: 0.00025,
    position: 0.13,
    bright: (2200.0, 12000.0),
    scrape: 0.04,
    body: &[(102.0, 22.0, 2.4), (198.0, 30.0, 1.7), (238.0, 28.0, 1.3), (385.0, 30.0, 0.9), (470.0, 32.0, 0.8), (560.0, 35.0, 0.6), (690.0, 35.0, 0.5), (820.0, 40.0, 0.45), (1010.0, 40.0, 0.4), (1230.0, 40.0, 0.35), (1580.0, 45.0, 0.3), (2050.0, 45.0, 0.25), (2650.0, 50.0, 0.2), (3400.0, 50.0, 0.15)],
    direct: 0.45,
    level: 0.55,
};

pub const NYLON: Guitar = Guitar {
    string: Material { t60_low: 13.0, t60_high: 5.0, loss: 0.5, stiffness: -0.05 },
    contact: 0.0015,
    position: 0.2,
    bright: (1500.0, 7000.0),
    scrape: 0.0,
    body: &[(96.0, 20.0, 2.6), (190.0, 28.0, 1.9), (228.0, 26.0, 1.4), (370.0, 28.0, 1.0), (450.0, 30.0, 0.8), (530.0, 30.0, 0.6), (650.0, 32.0, 0.5), (780.0, 35.0, 0.4), (960.0, 35.0, 0.35), (1180.0, 38.0, 0.3), (1500.0, 40.0, 0.22), (1950.0, 42.0, 0.16)],
    direct: 0.35,
    level: 0.6,
};

/// Standard tuning, low to high (MIDI).
const OPEN: [f64; 6] = [40.0, 45.0, 50.0, 55.0, 59.0, 64.0];
/// After a note ends: the finger damps the string this fast (seconds to −60 dB), duller as it dies.
const DAMP_T60: f64 = 0.16;

fn midi(freq: f64) -> f64 {
    69.0 + 12.0 * (freq / 440.0).log2()
}

/// Which string plays each note: among the strings it fits on (fret 0 … 20), a free one with the
/// lowest fret, else the one whose note started earliest (that note stops).
fn assign(notes: &[Note]) -> Vec<usize> {
    let mut until = [0usize; 6];
    let mut started = [0usize; 6];
    notes
        .iter()
        .map(|n| {
            let m = midi(n.freq);
            let fits: Vec<usize> = (0..6).filter(|&s| m >= OPEN[s] - 0.5 && m - OPEN[s] <= 20.5).collect();
            let fits = if fits.is_empty() { vec![if m < OPEN[0] { 0 } else { 5 }] } else { fits };
            let free = fits.iter().copied().filter(|&s| until[s] <= n.start).max_by(|&a, &b| OPEN[a].total_cmp(&OPEN[b]));
            let s = free.unwrap_or_else(|| *fits.iter().min_by_key(|&&s| started[s]).unwrap());
            until[s] = n.start + n.len;
            started[s] = n.start;
            s
        })
        .collect()
}

/// The pluck's force: a rounded impulse (shorter and brighter when harder), pick scrape, then the
/// comb of the plucking point (the partials with a node there are missing).
fn excitation(g: &Guitar, n: &Note, rng: &mut Rng, sr: f64) -> Vec<f64> {
    let v = n.velocity.clamp(0.02, 1.0);
    // The note's touch: 0 a soft fingertip … 1 a hard pick (else the guitar's own).
    let contact = n.hardness.map_or(g.contact, |h| 0.0016 * (0.0002f64 / 0.0016).powf(h.clamp(0.0, 1.0)));
    let width = ((contact * (1.6 - 0.6 * v)) * sr).max(1.0);
    let period = sr / n.freq;
    let len = (width as usize + period as usize * 2).max(8);
    let mut e: Vec<f64> = (0..len).map(|i| {
        let x = i as f64 / width;
        let pulse = if x < 1.0 { 0.5 - 0.5 * (2.0 * std::f64::consts::PI * x).cos() } else { 0.0 };
        let scrape = if (i as f64) < 0.004 * sr { g.scrape * rng.next() * (1.0 - i as f64 / (0.004 * sr)) } else { 0.0 };
        pulse + scrape
    }).collect();
    let cutoff = g.bright.0 * (g.bright.1 / g.bright.0).powf(v.powf(1.3));
    one_pole(&mut e, cutoff, false, sr);
    one_pole(&mut e, cutoff * 1.4, false, sr);
    let at = ((n.position.unwrap_or(g.position).clamp(0.03, 0.5) * (0.9 + 0.2 * (rng.next() * 0.5 + 0.5))) * period).round() as usize;
    let mut out = e.clone();
    for i in at..len {
        out[i] -= e[i - at];
    }
    let norm = e.iter().map(|x| x.abs()).fold(0.0, f64::max).max(1e-9);
    out.iter().map(|x| x / norm * v.powf(1.1)).collect()
}

/// One note on its string, both polarisations, until it has died away after its end.
fn pluck(g: &Guitar, n: &Note, stop: usize, sr: f64) -> Vec<f64> {
    let mut rng = Rng::new(n.start as u64 * 31 + (n.freq * 100.0) as u64);
    let exc = excitation(g, n, &mut rng, sr);
    // Muted strings (the touch's damping): the ring shortens toward a palm mute's ~0.2 s and the highs go first.
    let mute = n.damping.unwrap_or(0.0).clamp(0.0, 1.0);
    let t60 = t60_at(&g.string, n.freq).powf(1.0 - mute) * 0.2f64.powf(mute);
    let detune = 2f64.powf((0.6 + 0.3 * rng.next()) / 1200.0);
    let mut a = StringLoop::new(n.freq, t60, &g.string, sr);
    let mut b = StringLoop::new(n.freq * detune, t60 * 1.45, &g.string, sr);
    if mute > 0.0 {
        a.damp(n.freq, t60, 0.3 * mute);
        b.damp(n.freq * detune, t60 * 1.45, 0.3 * mute);
    }
    let off = stop.min(n.len);
    let tail = (DAMP_T60 * 1.7 * sr) as usize;
    let mut out = Vec::with_capacity(off + tail);
    for i in 0..off + tail {
        if i == off {
            a.damp(n.freq, DAMP_T60, 0.35);
            b.damp(n.freq * detune, DAMP_T60, 0.35);
        }
        let t = i as f64 / sr;
        let f = n.freq * n.expression.map_or(1.0, |e| e.ratio(t));
        let x = exc.get(i).copied().unwrap_or(0.0);
        let s = 0.78 * a.tick(f, x) + 0.32 * b.tick(f * detune, x * 0.6);
        let gain = n.expression.map_or(1.0, |e| e.gain(t, n.len as f64 / sr));
        out.push(s * gain);
    }
    out
}

/// The bridge's force through the body: a little of it direct (high-passed), the rest through its resonances.
fn body(g: &Guitar, x: &[f64], sr: f64) -> Vec<f64> {
    let mut res: Vec<Resonator> = g.body.iter().map(|&(f, q, peak)| {
        let t60 = 6.907_755 * q / (std::f64::consts::PI * f);
        let r = (-6.907_755 / (t60 * sr)).exp();
        Resonator::new(&Mode { freq: f, t60, amp: 2.0 * peak * (1.0 - r) }, sr)
    }).collect();
    let mut lp = 0.0;
    x.iter().map(|&x| {
        lp = 0.995 * lp + 0.005 * x;
        g.direct * (x - lp) + res.iter_mut().map(|r| r.tick(x)).sum::<f64>()
    }).collect()
}

pub fn render(g: &Guitar, notes: &[Note], left: &mut [f32], right: &mut [f32], sr: f64) {
    if notes.is_empty() {
        return;
    }
    let strings = assign(notes);
    // Where each note stops: its end, or the next note on its string.
    let stops: Vec<usize> = notes.iter().enumerate().map(|(i, n)| {
        let next = notes[i + 1..].iter().zip(&strings[i + 1..]).find(|(_, s)| **s == strings[i]).map(|(m, _)| m.start - n.start);
        next.map_or(n.len, |d| d.max(1))
    }).collect();
    let rendered = crate::mix::par::map(notes.iter().zip(stops).collect::<Vec<_>>(), |(n, stop)| pluck(g, n, stop, sr));
    // Every string through the one body (it is linear, so once per side on the panned sum).
    let first = notes[0].start;
    let span = notes.iter().zip(&rendered).map(|(n, r)| n.start + r.len()).max().unwrap_or(0) - first + (0.8 * sr) as usize;
    let mut sums = [vec![0.0; span], vec![0.0; span]];
    for (n, r) in notes.iter().zip(&rendered) {
        let (gl, gr) = pan_gains(n.pan, 1.0);
        for (i, s) in r.iter().enumerate() {
            sums[0][n.start - first + i] += s * gl * std::f64::consts::SQRT_2;
            sums[1][n.start - first + i] += s * gr * std::f64::consts::SQRT_2;
        }
    }
    let outs = crate::mix::par::map(sums.to_vec(), |x| body(g, &x, sr));
    for (buf, out) in [&mut *left, &mut *right].into_iter().zip(outs) {
        for (o, s) in buf.iter_mut().skip(first).zip(out) {
            *o = (*o as f64 + s * g.level) as f32;
        }
    }
}
