//! A room's decay time (RT60) from reverberant speech alone, blind: maximum-likelihood decay rates of
//! the clip's decaying stretches (Ratnam et al. 2003; with Löllmann et al. 2010's pre-selection), the
//! most frequent one taken. Each 0.3 s frame of 2.5 ms block energies (the noise floor's power taken
//! out) whose three thirds fall, from 20 dB over the floor to at least 6 dB over it, and whose 10 ms
//! levels lie within 1.5 dB of a line (a room's tail is smooth; a dry phrase ending wobbles with its
//! syllables), is fitted as exponentially decaying noise: block energies e_j with mean
//! σ²ρ^j, so for each ρ the likelihood's σ² is mean(e_j ρ^−j) and ρ maximises
//! −J ln σ²(ρ) − ln ρ · J(J − 1)/2. A frame that is still speech decays slower than the room, a frame on
//! an offset faster; the free decays of the room agree with each other, so the histogram's peak is the
//! room. Measured on a dry synthesized voice through 0.4 / 0.7 / 1.2 s rooms: 0.4 / 0.7 / 1.2 s with no
//! noise and with a −60 dB floor; the 0.4 s room under floors up to −40 dB (RMS under the peak) through
//! half-length frames (see `blind`); the dry voice: None, with or without a floor.

const BLOCK: f64 = 0.0025;
const FRAME: f64 = 0.3;
const HOP: f64 = 0.02;
const THIRDS: usize = 3;
/// Decaying frames needed for an answer.
const MIN_FRAMES: usize = 8;
const RT_MIN: f64 = 0.1;
const RT_MAX: f64 = 3.0;
const GRID: usize = 160;
const BINS: usize = 40;
/// Blocks per 10 ms level in the smoothness check, and the most a decay's levels may stray (dB RMS).
const GROUP: usize = 4;
const MAX_RESIDUAL: f64 = 1.5;

/// The decay time (s), or None: too few free decays (a dry take, a clip without pauses, or silence).
/// Frames of FRAME first; when they find too few, frames half as long. A 0.3 s frame of a 0.4 s room
/// spans 45 dB of its decay, more than speech stands over a −45 dB floor, so the frame cannot both start
/// 20 dB over the floor and end 6 dB over it; a half frame spans 22 dB and can. A longer room still fits
/// the long frames (which see its decay best), so its answer stays theirs.
pub fn blind(l: &[f32], r: &[f32], sr: f64) -> Option<f64> {
    let m = ((sr * BLOCK) as usize).max(1);
    let n = l.len().min(r.len()) / m;
    let raw: Vec<f64> = (0..n).map(|b| (b * m..(b + 1) * m).map(|i| ((l[i] as f64 + r[i] as f64) * 0.5).powi(2)).sum::<f64>() / m as f64 + 1e-14).collect();
    let mut sorted = raw.clone();
    sorted.sort_by(|a, b| a.total_cmp(b));
    let noise = *sorted.get(sorted.len() / 10)?;
    // The noise floor's power taken out, so a tail sinking into it does not read as a longer room.
    let e: Vec<f64> = raw.iter().map(|v| (v - noise).max(1e-3 * noise + 1e-16)).collect();
    let found = [FRAME, FRAME / 2.0].iter().map(|&frame| decays(&e, noise, frame, m, sr)).find(|f| f.len() >= MIN_FRAMES)?;
    // The histogram's peak (log-spaced bins), refined to the median of the estimates in it and its neighbours.
    let bin = |rt: f64| (((rt / RT_MIN).ln() / (RT_MAX / RT_MIN).ln() * BINS as f64) as usize).min(BINS - 1);
    let mut hist = [0usize; BINS];
    found.iter().for_each(|&rt| hist[bin(rt)] += 1);
    let peak = (0..BINS).max_by_key(|&b| (hist[b], std::cmp::Reverse(b)))?;
    let mut near: Vec<f64> = found.into_iter().filter(|&rt| bin(rt).abs_diff(peak) <= 1).collect();
    near.sort_by(|a, b| a.total_cmp(b));
    Some(near[near.len() / 2])
}

/// The decay time of each `frame`-second stretch of block energies `e` (blocks of `m` samples) that falls
/// freely from 20 dB over the floor to 6 dB over it.
fn decays(e: &[f64], noise: f64, frame: f64, m: usize, sr: f64) -> Vec<f64> {
    let n = e.len();
    let third = ((frame / BLOCK) as usize / THIRDS).max(GROUP);
    let j = third * THIRDS;
    let hop = ((HOP / BLOCK) as usize).max(1);
    // ln ρ per block for each candidate decay time (energy falls 60 dB over rt), and ρ^−i.
    let rts: Vec<f64> = (0..GRID).map(|k| RT_MIN * (RT_MAX / RT_MIN).powf(k as f64 / (GRID - 1) as f64)).collect();
    let ln_rho: Vec<f64> = rts.iter().map(|rt| -6.0 * std::f64::consts::LN_10 * m as f64 / (sr * rt)).collect();
    let weights: Vec<Vec<f64>> = ln_rho.iter().map(|lr| (0..j).map(|i| (-lr * i as f64).exp()).collect()).collect();
    let pairs = (j * (j - 1)) as f64 / 2.0;
    let mut found = vec![];
    let mut s = 0;
    while s + j < n {
        let f = &e[s..s + j];
        s += hop;
        let thirds: Vec<f64> = f.chunks(third).map(|c| c.iter().sum::<f64>() / c.len() as f64).collect();
        if !thirds.windows(2).all(|w| w[1] < w[0]) || thirds[0] < noise * 100.0 || thirds[THIRDS - 1] < noise * 4.0 || !smooth(f) {
            continue;
        }
        let cost = |k: usize| j as f64 * (f.iter().zip(&weights[k]).map(|(v, w)| v * w).sum::<f64>() / j as f64).ln() + ln_rho[k] * pairs;
        let Some(best) = (0..GRID).map(|k| (k, cost(k))).min_by(|a, b| a.1.total_cmp(&b.1)).map(|b| b.0) else { continue };
        // At either end of the range: not a decay this range can tell.
        if best > 0 && best < GRID - 1 {
            found.push(rts[best]);
        }
    }
    found
}

/// A room's decay is smooth: the 10 ms levels stay within MAX_RESIDUAL dB (RMS) of a straight line.
/// Speech that merely gets quieter (a dry take's phrase endings) wobbles with its syllables.
fn smooth(f: &[f64]) -> bool {
    let lv: Vec<f64> = f.chunks_exact(GROUP).map(|c| 10.0 * (c.iter().sum::<f64>() / GROUP as f64).log10()).collect();
    let n = lv.len() as f64;
    let (mx, my) = ((n - 1.0) / 2.0, lv.iter().sum::<f64>() / n);
    let slope = lv.iter().enumerate().map(|(i, y)| (i as f64 - mx) * (y - my)).sum::<f64>() / lv.iter().enumerate().map(|(i, _)| (i as f64 - mx).powi(2)).sum::<f64>();
    let var = lv.iter().enumerate().map(|(i, y)| (y - my - slope * (i as f64 - mx)).powi(2)).sum::<f64>() / n;
    var.sqrt() <= MAX_RESIDUAL
}

#[cfg(test)]
mod tests {
    /// Speech-like syllables (noise shaped by short bursts and pauses of uneven length) through a room
    /// of decay time `rt` (an exponential noise tail, direct-to-reverberant 0 dB).
    fn talk_in_room(rt: f64, sr: f64) -> Vec<f32> {
        let mut seed = 0x2545f4914f6cdd1du64;
        let mut rnd = move || {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            (seed >> 11) as f64 / (1u64 << 53) as f64
        };
        let mut dry = vec![0.0f32; (sr * 12.0) as usize];
        let mut t = 0.2;
        while t < 10.5 {
            let (len, gap) = (0.08 + 0.17 * rnd(), 0.03 + 0.4 * rnd() * rnd());
            let (a, b) = ((t * sr) as usize, ((t + len) * sr) as usize);
            for i in a..b {
                let env = (std::f64::consts::PI * (i - a) as f64 / (b - a) as f64).sin().powf(0.3);
                dry[i] = (0.3 * env * (2.0 * rnd() - 1.0)) as f32;
            }
            t += len + gap;
        }
        let n = (sr * rt * 1.5) as usize;
        let tail: Vec<f64> = (0..n).map(|i| if i < (0.004 * sr) as usize { 0.0 } else { (2.0 * rnd() - 1.0) * (-6.908 * i as f64 / (sr * rt)).exp() }).collect();
        let norm = tail.iter().map(|v| v * v).sum::<f64>().sqrt();
        let ir: Vec<f64> = tail.iter().enumerate().map(|(i, v)| v / norm + if i == 0 { 1.0 } else { 0.0 }).collect();
        crate::fx::convolve::convolve(&dry, &ir).iter().map(|v| *v as f32).collect()
    }

    #[test]
    fn finds_the_room_from_speech_alone() {
        let sr = 16000.0;
        for rt in [0.4, 0.7, 1.2] {
            let x = talk_in_room(rt, sr);
            let peak = x.iter().fold(0.0f32, |a, v| a.max(v.abs()));
            // And over a noise floor 60 dB under the peak (a real recording's).
            let mut k = 1u32;
            let noisy: Vec<f32> = x.iter().map(|v| {
                k = k.wrapping_mul(1664525).wrapping_add(1013904223);
                v + peak * 1e-3 * ((k >> 8) as f32 / (1u32 << 24) as f32 * 2.0 - 1.0) * 1.7
            }).collect();
            for (what, y) in [("clean", &x), ("noisy", &noisy)] {
                let got = super::blind(y, y, sr).expect("free decays");
                assert!((got / rt - 1.0).abs() < 0.15, "{what} room {rt} s: estimated {got} s");
            }
        }
    }

    /// `x` plus uniform noise whose RMS is `db` under the clip's peak.
    fn with_floor(x: &[f32], db: f32) -> Vec<f32> {
        let peak = x.iter().fold(0.0f32, |a, v| a.max(v.abs()));
        let g = peak * 10f32.powf(db / 20.0) * 3f32.sqrt();
        let mut k = 1u32;
        x.iter().map(|v| {
            k = k.wrapping_mul(1664525).wrapping_add(1013904223);
            v + g * ((k >> 8) as f32 / (1u32 << 24) as f32 * 2.0 - 1.0)
        }).collect()
    }

    /// A short room under a high floor: 0.3 s frames span more of its decay than the speech stands over
    /// the noise (read None at −45 dB before the half frames); the dry take stays dry under the same floors.
    #[test]
    fn a_short_room_reads_under_a_high_noise_floor() {
        let sr = 16000.0;
        let (room, dry) = (talk_in_room(0.4, sr), talk_in_room(0.05, sr));
        for db in [-50.0, -45.0, -40.0] {
            let got = super::blind(&with_floor(&room, db), &with_floor(&room, db), sr).unwrap_or_else(|| panic!("0.4 s room under {db} dB: None"));
            assert!((got / 0.4 - 1.0).abs() < 0.15, "0.4 s room under {db} dB: estimated {got} s");
            let d = with_floor(&dry, db);
            assert_eq!(super::blind(&d, &d, sr), None, "the dry take under {db} dB");
        }
    }

    #[test]
    fn a_dry_take_reads_as_dry_and_silence_as_nothing() {
        let sr = 16000.0;
        let dry = talk_in_room(0.05, sr);
        assert_eq!(super::blind(&dry, &dry, sr), None, "a dry take has no room to take out");
        let quiet = vec![0.0f32; 48000];
        assert_eq!(super::blind(&quiet, &quiet, sr), None);
    }
}
