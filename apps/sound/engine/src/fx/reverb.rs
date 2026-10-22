//! The reverb of the clips, track sends and master bus (a port of masteringDsp.ts): parallel feedback
//! combs per channel, cross-mixed, over stereo or a bed's mains. Delay lines hold f32 like the TS buffers did.

use std::f64::consts::PI;

use super::dsp::each;

/// Four parallel feedback combs per channel, cross-mixed; "shimmer" adds an octave tap and wobble.
/// Stereo is the original two sides; a surround bed's mains (the LFE stays dry: `BedReverb`) each
/// get comb lengths of their own and are fed half their own signal, half the mains' sum (÷√n), so a
/// source in one speaker still fills the room.
pub struct Reverb {
    /// The Freeverb form (`freeverb.<space>`): it replaces the combs below.
    fv: Option<FreeverbBed>,
    on: bool,
    shimmer: bool,
    feedback: f64,
    wet: f64,
    dry: f64,
    sr: f64,
    bufs: Vec<Vec<Vec<f32>>>,
    idx: Vec<[usize; 4]>,
    n: usize,
    sums: Vec<f64>,
}

/// Comb lengths (s) of the first two sides; further channels stretch side 0's by these factors.
const SIDES: [[f64; 4]; 2] = [[0.0297, 0.0371, 0.0411, 0.0437], [0.0313, 0.0389, 0.0429, 0.0461]];
const STRETCH: [f64; 6] = [1.071, 1.113, 1.157, 1.203, 1.249, 1.297];

impl Reverb {
    pub fn new(space: &str, wet_amount: f64, sr: f64) -> Self {
        Self::with_channels(space, wet_amount, sr, 2)
    }

    pub fn with_channels(space: &str, wet_amount: f64, sr: f64, channels: usize) -> Self {
        Self::shaped(space, wet_amount, sr, channels, Shape::default())
    }

    /// `freeverb.<space>` is the Freeverb form (any channel count; `shape` tunes it); any other name the comb reverb.
    pub fn shaped(space: &str, wet_amount: f64, sr: f64, channels: usize, shape: Shape) -> Self {
        let fv = space.strip_prefix("freeverb.").and_then(|name| FreeverbBed::new(name, wet_amount, sr, channels, shape));
        let space = if fv.is_some() { "dry" } else { space.strip_prefix("freeverb.").unwrap_or(space) };
        let on = space != "dry" && wet_amount > 0.005;
        let scale = match space { "cathedral" | "shimmer" => 1.48, "hall" => 1.0, _ => 0.6 };
        let feedback = match space { "shimmer" | "cathedral" => 0.74, "hall" => 0.66, _ => 0.48 };
        let lines = |ds: [f64; 4]| -> Vec<Vec<f32>> {
            if !on {
                return vec![];
            }
            ds.iter().map(|d| vec![0.0f32; ((d * scale * sr).floor() as usize).max(16)]).collect()
        };
        let set = |c: usize| if c < 2 { SIDES[c] } else { SIDES[0].map(|d| d * STRETCH[(c - 2) % STRETCH.len()]) };
        Reverb {
            fv,
            on,
            shimmer: space == "shimmer",
            feedback,
            wet: wet_amount.min(0.85) * 0.26,
            dry: 1.0 - (wet_amount * 0.35).min(0.45),
            sr,
            bufs: (0..channels).map(|c| lines(set(c))).collect(),
            idx: vec![[0; 4]; channels],
            n: 0,
            sums: vec![0.0; channels],
        }
    }

    pub fn process(&mut self, x: [f64; 2]) -> [f64; 2] {
        let mut y = x;
        self.process_n(&mut y);
        y
    }

    /// One frame of every channel, in place.
    pub fn process_n(&mut self, x: &mut [f64]) {
        if let Some(fv) = &mut self.fv {
            return fv.process_n(x);
        }
        if !self.on {
            return;
        }
        let ch = x.len();
        let m = if self.shimmer { (2.0 * PI * 1.8 * self.n as f64 / self.sr).sin() * 0.14 } else { 0.0 };
        self.n += 1;
        let diffuse = if ch > 2 { x.iter().sum::<f64>() / (ch as f64).sqrt() } else { 0.0 };
        for side in 0..ch {
            let mod_sign = if side % 2 == 0 { m } else { -m };
            let input = if ch > 2 { 0.5 * x[side] + 0.5 * diffuse } else { x[side] };
            self.sums[side] = 0.0;
            for c in 0..4 {
                let b = &mut self.bufs[side][c];
                let p = self.idx[side][c];
                let out = b[p] as f64;
                let oct = if self.shimmer { b[(p * 2) % b.len()] as f64 * 0.16 } else { 0.0 };
                b[p] = (input + out * self.feedback + (oct + out * mod_sign) * 0.45) as f32;
                self.idx[side][c] = (p + 1) % b.len();
                self.sums[side] += out + oct;
            }
        }
        let total: f64 = self.sums.iter().sum();
        for side in 0..ch {
            let others = if ch == 2 { self.sums[1 - side] } else { (total - self.sums[side]) / (ch - 1) as f64 };
            x[side] = x[side] * self.dry + (self.sums[side] * 0.8 + others * 0.2) * self.wet;
        }
    }
}

/// A track's reverb send over a bed of `channels` (stereo: both sides; a bed: its mains), its tail kept
/// between blocks; nothing when the space is dry or the send under 0.005.
pub struct BedReverb {
    r: Option<Reverb>,
    mains: Vec<usize>,
    x: Vec<f64>,
}

impl BedReverb {
    pub fn new(channels: usize, layout: crate::bed::Layout, space: &str, wet: f64, sr: f64) -> Self {
        let mains: Vec<usize> = (0..channels).filter(|&c| channels == 2 || Some(c) != layout.lfe()).collect();
        let on = space != "dry" && wet > 0.005 && channels > 0;
        BedReverb { r: on.then(|| Reverb::with_channels(space, wet, sr, mains.len())), x: vec![0.0; mains.len()], mains }
    }

    pub fn block(&mut self, bed: &mut [Vec<f32>]) {
        let Some(r) = &mut self.r else { return };
        for i in 0..bed.first().map_or(0, Vec::len) {
            for (k, &c) in self.mains.iter().enumerate() {
                self.x[k] = bed[c][i] as f64;
            }
            r.process_n(&mut self.x);
            for (k, &c) in self.mains.iter().enumerate() {
                bed[c][i] = self.x[k] as f32;
            }
        }
    }
}

/// The spaces of the Freeverb form (`freeverb.room` / `.hall` / `.cathedral`): room size, damping, and the wet gain
/// that levels it with the comb reverb's space (the wet-only level, averaged over a voice-like, a percussive and a pad
/// clip at wet 0.5: README of the reverb A/B, results/sound/hem-r7/reverb).
const FREEVERB: [(&str, f64, f64, f64); 3] = [("room", 0.1, 0.55, 0.88), ("hall", 0.55, 0.45, 0.80), ("cathedral", 0.9, 0.3, 0.50)];

/// A Freeverb's own settings over its space's (the reverb insert's `decay` / `damping` / `size`; none: the space's).
#[derive(Clone, Copy, Debug, Default)]
pub struct Shape {
    /// Seconds the tail takes to fall 60 dB (RT60), 0.2 … 20: sets the combs' feedback.
    pub decay: Option<f64>,
    /// 0 … 1: how fast the highs die in the tail.
    pub damping: Option<f64>,
    /// 0 … 1: the room's size, heard as the gap before the tail (up to 60 ms) and its width.
    pub size: Option<f64>,
}

/// Freeverb's room size (0 … 1) for a decay in seconds: its combs' feedback is 0.7 + 0.28 · size, and a comb of
/// mean length L (Jezar's tuning: 1356 samples at 44.1 kHz) falls 60 dB in RT60 = −3 L / log10(feedback).
fn room_for_decay(rt60: f64) -> f64 {
    let l = 1356.0 / 44100.0;
    let g = 10f64.powf(-3.0 * l / rt60.max(0.05));
    ((g - 0.7) / 0.28).clamp(0.0, 1.0)
}

/// The Freeverb form over any number of channels (the `freeverb` crate, MIT: Jezar's eight combs and four
/// all-passes per side). Channels go in pairs, one Freeverb each (an odd last one is fed to both sides and reads
/// the left); a bed's mains get half their own signal, half the mains' sum (÷√n), as the comb reverb does.
/// The dry part is added here, after the pre-delay that `size` sets, so the dry signal is never delayed.
struct FreeverbBed {
    pairs: Vec<freeverb::Freeverb<f64>>,
    dry: f64,
    pre: Vec<Vec<f64>>,
    at: usize,
}

impl FreeverbBed {
    fn new(space: &str, wet: f64, sr: f64, channels: usize, shape: Shape) -> Option<Self> {
        let &(_, size, damp, level) = FREEVERB.iter().find(|s| s.0 == space)?;
        let room = shape.decay.map_or(size, room_for_decay);
        let damp = shape.damping.map_or(damp, |d| d.clamp(0.0, 1.0));
        let width = shape.size.map_or(1.0, |s| 0.6 + 0.4 * s.clamp(0.0, 1.0));
        let pre = shape.size.map_or(0, |s| (s.clamp(0.0, 1.0) * 0.06 * sr) as usize);
        let pairs = (0..channels.div_ceil(2).max(1))
            .map(|_| {
                let mut f = freeverb::Freeverb::<f64>::new(sr.round() as usize);
                f.set_room_size(room);
                f.set_dampening(damp);
                f.set_width(width);
                f.set_wet(wet.min(0.85) * 0.26 * level);
                f.set_dry(0.0);
                f
            })
            .collect();
        Some(FreeverbBed { pairs, dry: 1.0 - (wet * 0.35).min(0.45), pre: if pre > 0 { vec![vec![0.0; pre]; channels] } else { vec![] }, at: 0 })
    }

    fn process_n(&mut self, x: &mut [f64]) {
        let ch = x.len();
        let diffuse = if ch > 2 { x.iter().sum::<f64>() / (ch as f64).sqrt() } else { 0.0 };
        let mut input: Vec<f64> = x.iter().map(|&v| if ch > 2 { 0.5 * v + 0.5 * diffuse } else { v }).collect();
        if !self.pre.is_empty() {
            for (c, v) in input.iter_mut().enumerate() {
                std::mem::swap(v, &mut self.pre[c][self.at]);
            }
            self.at = (self.at + 1) % self.pre[0].len();
        }
        for (k, f) in self.pairs.iter_mut().enumerate() {
            let (a, b) = (2 * k, 2 * k + 1);
            if a >= ch {
                break;
            }
            let pair = (input[a], if b < ch { input[b] } else { input[a] });
            let y = f.tick(pair);
            x[a] = x[a] * self.dry + y.0;
            if b < ch {
                x[b] = x[b] * self.dry + y.1;
            }
        }
    }
}

pub fn reverb(left: &mut [f32], right: &mut [f32], space: &str, wet: f64, sr: f64) {
    if space == "dry" || wet <= 0.005 || left.is_empty() {
        return;
    }
    let mut r = Reverb::new(space, wet, sr);
    each(left, right, |_, x| r.process(x));
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A mono sound, three kinds: a voice-like buzz with formants and syllables, percussion (kick, snare, hat)
    /// and a detuned pad chord; 3 s each, dry.
    fn dry(kind: &str, sr: f64) -> Vec<f32> {
        let n = (3.0 * sr) as usize;
        let mut seed = 12345u64;
        let mut noise = move || {
            seed = seed.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let mut z = seed;
            z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
            z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
            ((z ^ (z >> 31)) as f64 / u64::MAX as f64) * 2.0 - 1.0
        };
        let tau = 2.0 * PI;
        (0..n)
            .map(|i| {
                let t = i as f64 / sr;
                let v = match kind {
                    "voice" => {
                        // Syllables at ~3 Hz on a gliding 140 Hz pitch; formants at 700 / 1200 / 2600 Hz by harmonics.
                        let f0 = 140.0 + 12.0 * (tau * 0.7 * t).sin();
                        let env = (0.5 + 0.5 * (tau * 3.0 * t - 1.5).sin()).powi(2) * if t < 2.2 { 1.0 } else { 0.0 };
                        let s: f64 = (1..=30).map(|h| { let f = f0 * h as f64; let g = [700.0, 1200.0, 2600.0].iter().map(|c| (-((f - c) / 250.0).powi(2)).exp()).sum::<f64>(); g * (tau * f * t).sin() / h as f64 }).sum();
                        s * env * 0.5
                    }
                    "percussive" => {
                        let beat = (t * 2.0).fract() / 2.0; // 120 bpm: time since the last beat
                        let k = (tau * (50.0 + 90.0 * (-beat * 40.0).exp()) * beat).sin() * (-beat * 9.0).exp();
                        let sn = if ((t * 2.0) as usize) % 2 == 1 { noise() * (-beat * 14.0).exp() * 0.6 } else { 0.0 };
                        let h = noise() * (-((t * 4.0).fract() / 4.0) * 60.0).exp() * 0.25;
                        k * 0.8 + sn + h
                    }
                    _ => {
                        let env = (t / 0.8).min(1.0) * (-(t - 2.2).max(0.0) * 4.0).exp();
                        [220.0, 277.18, 329.63, 440.0].iter().flat_map(|f| [0.997, 1.003].map(|d| f * d)).map(|f| (0..6).map(|h| (tau * f * (h + 1) as f64 * t).sin() / (h + 1) as f64 / 2.0).sum::<f64>()).sum::<f64>() * env * 0.12
                    }
                };
                v as f32
            })
            .collect()
    }

    fn rms(x: &[f32]) -> f64 {
        (x.iter().map(|v| (*v as f64).powi(2)).sum::<f64>() / x.len().max(1) as f64).sqrt()
    }

    /// The A/B (README of results/sound/hem-r7/reverb): `ROSTRUM_REVERB_AB=<dir> cargo test reverb_ab -- --ignored --nocapture`.
    #[test]
    #[ignore]
    fn reverb_ab() {
        let dir = std::path::PathBuf::from(std::env::var("ROSTRUM_REVERB_AB").expect("ROSTRUM_REVERB_AB=<dir>"));
        std::fs::create_dir_all(&dir).unwrap();
        let sr = 48000.0;
        for kind in ["voice", "percussive", "pad"] {
            let d = dry(kind, sr);
            let write = |name: &str, l: &[f32], r: &[f32]| {
                let b = crate::mix::wavio::write(&[l.to_vec(), r.to_vec()], crate::bed::Layout::Stereo, sr as u32);
                std::fs::write(dir.join(name), b).unwrap();
            };
            write(&format!("{kind}_dry.wav"), &d, &d);
            for space in ["room", "hall", "cathedral"] {
                let wet = 0.5;
                let (mut al, mut ar) = (d.clone(), d.clone());
                reverb(&mut al, &mut ar, space, wet, sr);
                let (mut bl, mut br) = (d.clone(), d.clone());
                reverb(&mut bl, &mut br, &format!("freeverb.{space}"), wet, sr);
                write(&format!("{kind}_{space}_A-comb.wav"), &al, &ar);
                write(&format!("{kind}_{space}_B-freeverb.wav"), &bl, &br);
                // Wet-only level (output minus the dry part) and tail energy (last second, after the source stops).
                let tail = |x: &[f32]| 20.0 * rms(&x[x.len() - sr as usize..]).max(1e-9).log10();
                let wetlevel = |x: &[f32], dry_gain: f64| 20.0 * rms(&x.iter().zip(&d).map(|(y, s)| *y - *s * dry_gain as f32).collect::<Vec<_>>()).max(1e-9).log10();
                let g = 1.0 - (wet * 0.35).min(0.45);
                println!("AB {kind} {space}: wet-only level comb {:.1} dB, freeverb {:.1} dB; last-second level comb {:.1} dB, freeverb {:.1} dB; peak comb {:.2}, freeverb {:.2}", wetlevel(&al, g), wetlevel(&bl, g), tail(&al), tail(&bl), al.iter().fold(0.0f32, |m, v| m.max(v.abs())), bl.iter().fold(0.0f32, |m, v| m.max(v.abs())));
            }
        }
    }
}
