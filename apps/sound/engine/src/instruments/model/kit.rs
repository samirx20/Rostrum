//! A drum kit by modal synthesis (modal.rs), every hit made from physics, not samples. Drums are
//! circular membranes (Bessel-zero mode ratios) whose pitch falls just after the hit (the head's tension
//! relaxes), struck at a point on the head (the centre rings the round modes, the edge the others);
//! the snare adds its wires — noise that buzzes for as long as the bottom head moves; the kick a felt
//! beater's click. Cymbals and hats are dense banks of inharmonic plate modes plus the shimmer that
//! blooms after the strike; an open hat is choked by the next closed one. Voices by General MIDI key.

use super::modal::{one_pole, pulse, Mode, Resonator};
use super::{mix_in, Note, Rng};

/// Circular membrane modes: ratio to the fundamental and nodal diameters (0: round).
const MEMBRANE: [(f64, u32); 12] = [(1.0, 0), (1.594, 1), (2.136, 2), (2.296, 0), (2.653, 3), (2.918, 1), (3.156, 4), (3.501, 2), (3.600, 0), (3.652, 5), (4.060, 3), (4.154, 6)];

#[derive(Clone, Copy, PartialEq, Debug)]
pub enum Piece { Kick, Snare, Rim, Clap, Tom(f64), ClosedHat, PedalHat, OpenHat, Crash, Ride, Bell, Shaker }

pub fn piece(key: u8) -> Piece {
    match key {
        35 | 36 => Piece::Kick,
        37 => Piece::Rim,
        38 | 40 => Piece::Snare,
        39 => Piece::Clap,
        41 => Piece::Tom(82.0),
        43 => Piece::Tom(98.0),
        45 => Piece::Tom(110.0),
        47 => Piece::Tom(131.0),
        48 => Piece::Tom(147.0),
        50 => Piece::Tom(165.0),
        42 => Piece::ClosedHat,
        44 => Piece::PedalHat,
        46 => Piece::OpenHat,
        51 | 59 => Piece::Ride,
        53 => Piece::Bell,
        69 | 70 | 82 => Piece::Shaker,
        _ => Piece::Crash,
    }
}

/// A struck membrane: `f` Hz, `t60` s for the fundamental, its pitch `drop` (fraction) relaxing over `relax` s.
fn drum(f: f64, t60: f64, drop: f64, relax: f64, pos: f64, contact: f64, len: usize, sr: f64) -> Vec<f64> {
    let modes: Vec<Mode> = MEMBRANE.iter().map(|&(r, m)| {
        let w = if m == 0 { 1.0 - 0.6 * pos } else { (2.2 * pos).powi(m.min(3) as i32).min(1.0) * 0.8 };
        Mode { freq: f * r, t60: t60 / r.powf(1.4), amp: w / r.sqrt() }
    }).collect();
    let mut res: Vec<Resonator> = modes.iter().map(|m| Resonator::new(m, sr)).collect();
    let exc = pulse(contact, sr);
    (0..len).map(|i| {
        let t = i as f64 / sr;
        if i % 8 == 0 && t < relax * 6.0 {
            let bend = 1.0 + drop * (-t / relax).exp();
            for (r, m) in res.iter_mut().zip(&modes) {
                r.set(m.freq * bend, m.t60, m.amp, sr);
            }
        }
        let x = exc.get(i).copied().unwrap_or(0.0);
        res.iter_mut().map(|r| r.tick(x)).sum::<f64>()
    }).collect()
}

/// A plate's dense inharmonic modes between `lo` and `hi` Hz (the same plate every hit: seeded by `seed`).
fn plate(seed: u64, count: usize, lo: f64, hi: f64, t60: f64, contact: f64, len: usize, sr: f64) -> Vec<f64> {
    let mut rng = Rng::new(seed);
    let modes: Vec<Mode> = (0..count).map(|k| {
        let u = (k as f64 + 0.5 + 0.45 * rng.next()) / count as f64;
        let f = lo * (hi / lo).powf(u);
        Mode { freq: f, t60: t60 * (0.6 + 0.4 * rng.next().abs()) * (2000.0 / f).powf(0.25).min(1.6), amp: (0.6 + 0.4 * rng.next()) * (f / 1500.0).powf(0.5).min(2.0) }
    }).collect();
    super::modal::ring(&modes, &pulse(contact, sr), len, None, 1.0, sr)
}

/// Noise shaped by a band (Hz) and an envelope.
fn noise(rng: &mut Rng, len: usize, lo: f64, hi: f64, env: impl Fn(f64) -> f64, sr: f64) -> Vec<f64> {
    let mut x: Vec<f64> = (0..len).map(|i| rng.next() * env(i as f64 / sr)).collect();
    one_pole(&mut x, hi, false, sr);
    one_pole(&mut x, lo, true, sr);
    one_pole(&mut x, lo, true, sr);
    x
}

/// One hit, `choke` samples in when a closed hat stops an open one.
pub fn hit(p: Piece, n: &Note, choke: Option<usize>, sr: f64) -> Vec<f64> {
    let v = n.velocity.clamp(0.02, 1.0);
    let hard = n.hardness.unwrap_or(0.6).clamp(0.0, 1.0);
    let pos = n.position.unwrap_or(0.25).clamp(0.0, 1.0);
    let mut rng = Rng::new(n.start as u64 * 2654435761 + 17);
    let secs = |s: f64| (s * sr) as usize;
    let contact = |soft: f64, hardest: f64| soft * (hardest / soft).powf(hard) * (1.3 - 0.5 * v);
    let mut out = match p {
        Piece::Kick => {
            let mut d = drum(52.0, 0.5, 0.45, 0.018, pos * 0.5, contact(0.004, 0.0008), secs(0.6), sr);
            let click = noise(&mut rng, secs(0.012), 1500.0, 9000.0, |t| (-t * 600.0).exp(), sr);
            d.iter_mut().zip(&click).for_each(|(o, c)| *o += c * 0.25 * (0.3 + hard));
            d.iter().map(|x| (x * 2.2).tanh() * 0.9).collect()
        }
        Piece::Snare => {
            let d = drum(188.0, 0.32, 0.06, 0.01, (pos + 0.2).min(1.0), contact(0.0012, 0.0003), secs(0.45), sr);
            // The wires buzz with the bottom head: their level follows the drum's.
            let mut follow = 0.0;
            let env: Vec<f64> = d.iter().map(|x| { follow = (x.abs()).max(follow * 0.9993); follow }).collect();
            let mut wires = noise(&mut rng, d.len(), 650.0, 2500.0 + 5000.0 * hard, |_| 1.0, sr);
            one_pole(&mut wires, 3000.0 + 5000.0 * hard, false, sr);
            let peak = env.iter().cloned().fold(1e-9, f64::max);
            d.iter().zip(&env).zip(&wires).map(|((x, e), w)| x * 0.9 + w * (e / peak).powf(0.8) * 1.5).collect()
        }
        Piece::Tom(f) => drum(f, 0.7, 0.1, 0.03, pos, contact(0.0016, 0.0004), secs(1.0), sr),
        Piece::Rim => {
            let modes = [Mode { freq: 420.0, t60: 0.05, amp: 0.6 }, Mode { freq: 1650.0, t60: 0.04, amp: 1.0 }, Mode { freq: 2380.0, t60: 0.03, amp: 0.7 }, Mode { freq: 3900.0, t60: 0.02, amp: 0.4 }];
            super::modal::ring(&modes, &pulse(0.0002, sr), secs(0.12), None, 1.0, sr)
        }
        Piece::Clap => {
            let env = |t: f64| [0.0, 0.011, 0.021, 0.034].iter().map(|&o| if t >= o { (-(t - o) * if o > 0.03 { 18.0 } else { 220.0 }).exp() } else { 0.0 }).sum::<f64>();
            noise(&mut rng, secs(0.35), 900.0, 3200.0, env, sr).iter().map(|x| x * 1.6).collect()
        }
        Piece::ClosedHat | Piece::PedalHat | Piece::OpenHat => {
            let t60 = match p { Piece::OpenHat => 3.5, Piece::PedalHat => 0.1, _ => 0.45 };
            let len = secs(t60 * 1.6 + 0.02);
            let mut x = plate(7, 70, if p == Piece::OpenHat { 3000.0 } else { 4500.0 }, 16000.0, t60, contact(0.0005, 0.00012), len, sr);
            let hiss = noise(&mut rng, len, 4000.0, 16000.0, |t| (-t * 6.907 / t60).exp(), sr);
            x.iter_mut().zip(&hiss).for_each(|(o, h)| *o = *o * 0.6 + h * 0.9);
            one_pole(&mut x, 2500.0, true, sr);
            let lvl = if p == Piece::PedalHat { 0.5 } else { 1.0 };
            x.iter().map(|s| s * lvl * 1.4).collect()
        }
        Piece::Crash | Piece::Ride => {
            let (t60, count, lo, seed) = if p == Piece::Crash { (8.0, 140, 300.0, 11) } else { (8.0, 120, 380.0, 23) };
            let len = secs(t60 * 1.3);
            let mut x = plate(seed, count, lo, 16000.0, t60, contact(0.0006, 0.00015), len, sr);
            // The shimmer blooms after the strike as energy spreads up into the high modes.
            let wash = if p == Piece::Crash { 1.0 } else { 0.35 };
            let bloom = noise(&mut rng, len, 3500.0, 14000.0, |t| (1.0 - (-t / 0.025).exp()) * (-t * 6.907 / (t60 * 0.6)).exp(), sr);
            x.iter_mut().zip(&bloom).for_each(|(o, b)| *o = *o * 0.7 + b * wash * 0.8);
            one_pole(&mut x, 300.0, true, sr);
            x
        }
        // Seeds in a shell: a dense burst of grains, swelling in and dying fast (a cabasa, maracas, a shaker).
        Piece::Shaker => noise(&mut rng, secs(0.14), 4800.0, 13000.0, |t| (1.0 - (-t / 0.006).exp()) * (-t / 0.028).exp(), sr),
        Piece::Bell => {
            let modes: Vec<Mode> = [(1.0, 1.0), (2.08, 0.6), (2.92, 0.5), (4.17, 0.35), (5.53, 0.2)].iter().map(|&(r, a)| Mode { freq: 640.0 * r, t60: 3.5 / r.sqrt(), amp: a }).collect();
            let mut x = super::modal::ring(&modes, &pulse(0.00015, sr), secs(4.0), None, 1.0, sr);
            let p2 = plate(23, 40, 2000.0, 15000.0, 1.2, 0.0002, x.len(), sr);
            x.iter_mut().zip(&p2).for_each(|(o, q)| *o += q * 0.3);
            x
        }
    };
    if let Some(c) = choke {
        // The closing hats grip the cymbals: gone in ~30 ms.
        out.iter_mut().enumerate().skip(c).for_each(|(i, s)| *s *= (-((i - c) as f64) / (0.006 * sr)).exp());
        out.truncate(c + secs(0.04));
    }
    // Each piece's level in a balanced kit (kick and snare lead, cymbals sit under them).
    let level = match p { Piece::Kick => 2.0, Piece::Rim => 0.6, Piece::Snare => 0.5, Piece::Clap => 1.8, Piece::ClosedHat => 0.35, Piece::PedalHat => 0.3, Piece::OpenHat => 0.3, Piece::Crash => 0.083, Piece::Ride => 0.056, Piece::Bell => 0.29, Piece::Tom(_) => 0.85, Piece::Shaker => 0.9 };
    let g = v.powf(1.3) * 0.5 * level;
    out.iter_mut().for_each(|s| *s *= g);
    out
}

pub fn render(notes: &[Note], left: &mut [f32], right: &mut [f32], sr: f64) {
    let key = |n: &Note| (69.0 + 12.0 * (n.freq / 440.0).log2()).round().clamp(0.0, 127.0) as u8;
    let jobs: Vec<(Piece, Note, Option<usize>)> = notes.iter().map(|n| {
        let p = piece(key(n));
        // An open hat rings until the next closed or pedal hat.
        let choke = (p == Piece::OpenHat).then(|| notes.iter().find(|m| m.start > n.start && matches!(piece(key(m)), Piece::ClosedHat | Piece::PedalHat)).map(|m| m.start - n.start)).flatten();
        (p, n.clone(), choke)
    }).collect();
    let hits = crate::mix::par::map(jobs, |(p, n, c)| (n.start, n.pan, hit(p, &n, c, sr)));
    for (start, pan, s) in hits {
        mix_in(&s, start, 1.0, pan, left, right);
    }
}
