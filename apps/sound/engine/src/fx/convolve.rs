//! The convolution insert (src/core/soundDsl/soundtrack/effects.ts decides it): a signal through an impulse
//! response — a recorded one (a file the host decoded to PCM) or a built-in one, generated here
//! (nothing shipped or downloaded): short resonant bodies (an instrument's wood: decaying modes
//! with a direct click) and a scoring hall (early reflections, then diffuse noise whose highs die
//! first). FFT overlap-add, so a 2-second hall costs little; the same every render.

use std::f64::consts::PI;

use serde::Deserialize;

use crate::mix::schedule::{Param, Pcm};

/// A built-in IR by name, or a decoded file.
#[derive(Deserialize, Clone, Debug)]
#[serde(untagged)]
pub enum Ir {
    Builtin(String),
    File(Pcm),
}

pub const BUILTINS: [&str; 3] = ["body.wood_hollow", "body.cello", "stage.scoring_hall"];

/// Deterministic noise in -1..1 (splitmix64).
struct Noise(u64);
impl Noise {
    fn next(&mut self) -> f64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        ((z ^ (z >> 31)) as f64 / u64::MAX as f64) * 2.0 - 1.0
    }
}

/// A resonant body: a direct click plus decaying modes (Hz, level, decay seconds), `len` seconds.
fn body(modes: &[(f64, f64, f64)], direct: f64, len: f64, seed: u64, sr: f64) -> Vec<f64> {
    let n = (len * sr) as usize;
    let mut rng = Noise(seed);
    let phases: Vec<f64> = modes.iter().map(|_| rng.next() * PI).collect();
    let mut ir = vec![0.0; n];
    ir[0] = direct;
    for (i, v) in ir.iter_mut().enumerate() {
        let t = i as f64 / sr;
        for ((f, a, d), p) in modes.iter().zip(&phases) {
            *v += a * (-t / d).exp() * (2.0 * PI * f * t + p).sin();
        }
        // A little wood grain: noise in the first few milliseconds.
        *v += rng.next() * 0.08 * (-t / 0.004).exp();
    }
    ir
}

/// A scoring hall: pre-delay, early reflections, then a diffuse tail (RT60 ≈ 2 s; highs ≈ 0.8 s).
fn hall(seed: u64, sr: f64) -> Vec<f64> {
    let n = (2.6 * sr) as usize;
    let mut rng = Noise(seed);
    let mut ir = vec![0.0; n];
    ir[0] = 1.0;
    for k in 0..14 {
        let at = 0.011 + 0.006 * k as f64 + 0.004 * rng.next().abs();
        ir[(at * sr) as usize] += 0.55 * (-at / 0.09).exp() * rng.next().signum();
    }
    let (rt_low, rt_high) = (2.0, 0.8);
    let lp_a = 1.0 - (-2.0 * PI * 2500.0 / sr).exp();
    let mut lp = 0.0;
    for (i, v) in ir.iter_mut().enumerate() {
        let t = i as f64 / sr;
        let x = rng.next();
        lp += lp_a * (x - lp);
        let onset = ((t - 0.02) / 0.06).clamp(0.0, 1.0); // the tail builds up behind the reflections
        // −60 dB over RT60: amplitude e^(−6.91 t / RT60).
        *v += onset * 0.35 * (lp * 1.6 * (-6.91 * t / rt_low).exp() + (x - lp) * (-6.91 * t / rt_high).exp());
    }
    ir
}

/// A built-in IR, left and right (the channels differ slightly: a body's two sides, a hall's walls).
pub fn builtin(name: &str, sr: f64) -> Result<[Vec<f64>; 2], String> {
    let side = |seed: u64| -> Result<Vec<f64>, String> {
        Ok(match name {
            "body.wood_hollow" => body(&[(110.0, 0.5, 0.05), (205.0, 0.9, 0.04), (290.0, 1.0, 0.035), (340.0, 0.8, 0.03), (470.0, 0.5, 0.025), (680.0, 0.45, 0.02), (930.0, 0.3, 0.015), (1300.0, 0.22, 0.01), (2100.0, 0.12, 0.007)], 1.0, 0.06, seed, sr),
            "body.cello" => body(&[(98.0, 0.9, 0.09), (185.0, 1.0, 0.08), (280.0, 0.8, 0.07), (410.0, 0.6, 0.05), (560.0, 0.5, 0.04), (720.0, 0.35, 0.03), (1050.0, 0.25, 0.02), (1500.0, 0.18, 0.012), (2400.0, 0.1, 0.008)], 1.0, 0.12, seed, sr),
            "stage.scoring_hall" => hall(seed, sr),
            _ => return Err(format!("convolution: no built-in impulse response \"{name}\" ({})", BUILTINS.join(", "))),
        })
    };
    let (mut l, mut r) = (side(1)?, side(2)?);
    // Unit energy: as loud as the dry signal on broadband material.
    for ch in [&mut l, &mut r] {
        let e = ch.iter().map(|v| v * v).sum::<f64>().sqrt().max(1e-12);
        ch.iter_mut().for_each(|v| *v /= e);
    }
    Ok([l, r])
}

/// An in-place complex FFT of (re, im) (rustfft: any length, split-radix / Bluestein, planned once per
/// size per thread); `inverse` scales by 1/n. The one FFT every analysis and repair calls.
pub(crate) fn fft(re: &mut [f64], im: &mut [f64], inverse: bool) {
    use rustfft::{num_complex::Complex, FftPlanner};
    thread_local! { static PLANNER: std::cell::RefCell<FftPlanner<f64>> = std::cell::RefCell::new(FftPlanner::new()); }
    let n = re.len();
    if n == 0 {
        return;
    }
    let plan = PLANNER.with(|p| {
        let mut p = p.borrow_mut();
        if inverse { p.plan_fft_inverse(n) } else { p.plan_fft_forward(n) }
    });
    let mut buf: Vec<Complex<f64>> = re.iter().zip(im.iter()).map(|(&r, &i)| Complex::new(r, i)).collect();
    plan.process(&mut buf);
    let s = if inverse { 1.0 / n as f64 } else { 1.0 };
    for (k, c) in buf.iter().enumerate() {
        re[k] = c.re * s;
        im[k] = c.im * s;
    }
}

/// `x` convolved with `ir`, cut to x's length (overlap-add; real FFTs, realfft).
pub fn convolve(x: &[f32], ir: &[f64]) -> Vec<f64> {
    use realfft::RealFftPlanner;
    let mut out = vec![0.0; x.len()];
    if ir.is_empty() || x.is_empty() {
        return out;
    }
    let n = (2 * ir.len()).next_power_of_two().max(256);
    let block = n - ir.len() + 1;
    let mut planner = RealFftPlanner::<f64>::new();
    let (fwd, inv) = (planner.plan_fft_forward(n), planner.plan_fft_inverse(n));
    let mut h = vec![0.0; n];
    h[..ir.len()].copy_from_slice(ir);
    let mut hs = fwd.make_output_vec();
    fwd.process(&mut h, &mut hs).expect("fft size");
    let (mut buf, mut spec) = (vec![0.0; n], fwd.make_output_vec());
    let scale = 1.0 / n as f64;
    for start in (0..x.len()).step_by(block) {
        let end = (start + block).min(x.len());
        if x[start..end].iter().all(|v| *v == 0.0) {
            continue;
        }
        buf.iter_mut().for_each(|v| *v = 0.0);
        for (k, v) in x[start..end].iter().enumerate() {
            buf[k] = *v as f64;
        }
        fwd.process(&mut buf, &mut spec).expect("fft size");
        for (s, h) in spec.iter_mut().zip(&hs) {
            *s *= *h;
        }
        spec[0].im = 0.0;
        spec[n / 2].im = 0.0;
        inv.process(&mut spec, &mut buf).expect("fft size");
        for (k, v) in buf.iter().enumerate().take(x.len() - start) {
            out[start + k] += v * scale;
        }
    }
    out
}

/// The insert: each channel through its side of the IR, blended with the dry signal by `mix`.
pub fn run(ir: &Ir, mix: &Param, l: &mut [f32], r: &mut [f32], sr: f64) -> Result<(), String> {
    let [il, irr] = match ir {
        Ir::Builtin(name) => builtin(name, sr)?,
        Ir::File(pcm) => {
            let d = pcm.read()?;
            let ch = |c: usize| d.iter().skip(c.min(pcm.channels - 1)).step_by(pcm.channels).map(|v| *v as f64).collect::<Vec<_>>();
            [ch(0), ch(1)]
        }
    };
    let (wl, wr) = (convolve(l, &il), convolve(r, &irr));
    for i in 0..l.len() {
        let m = mix.at(i as f64 / sr);
        l[i] = (l[i] as f64 * (1.0 - m) + wl[i] * m) as f32;
        r[i] = (r[i] as f64 * (1.0 - m) + wr[i] * m) as f32;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The hand-written radix-2 FFT this replaced, kept as the reference the swap is proved against.
    fn fft_reference(re: &mut [f64], im: &mut [f64], inverse: bool) {
        let n = re.len();
        let mut j = 0;
        for i in 1..n {
            let mut bit = n >> 1;
            while j & bit != 0 {
                j ^= bit;
                bit >>= 1;
            }
            j |= bit;
            if i < j {
                re.swap(i, j);
                im.swap(i, j);
            }
        }
        let mut len = 2;
        while len <= n {
            let ang = 2.0 * PI / len as f64 * if inverse { 1.0 } else { -1.0 };
            let (wr, wi) = (ang.cos(), ang.sin());
            for start in (0..n).step_by(len) {
                let (mut cr, mut ci) = (1.0, 0.0);
                for k in 0..len / 2 {
                    let (a, b) = (start + k, start + k + len / 2);
                    let (xr, xi) = (re[b] * cr - im[b] * ci, re[b] * ci + im[b] * cr);
                    (re[b], im[b]) = (re[a] - xr, im[a] - xi);
                    re[a] += xr;
                    im[a] += xi;
                    (cr, ci) = (cr * wr - ci * wi, cr * wi + ci * wr);
                }
            }
            len <<= 1;
        }
        if inverse {
            let s = 1.0 / n as f64;
            re.iter_mut().chain(im.iter_mut()).for_each(|v| *v *= s);
        }
    }

    fn noise(n: usize, seed: u64) -> Vec<f64> {
        let mut r = Noise(seed);
        (0..n).map(|_| r.next()).collect()
    }

    /// The swap is lossless: rustfft against the old radix-2 on noise at every size we use, both directions,
    /// and the realfft convolution against the old complex-FFT overlap-add. Prints the max abs differences (README).
    #[test]
    fn rustfft_matches_the_hand_written_fft_and_the_convolution_is_unchanged() {
        let mut worst = 0.0f64;
        for &n in &[256usize, 2048, 4096, 8192, 16384, 65536] {
            for inverse in [false, true] {
                let (r0, i0) = (noise(n, n as u64), noise(n, n as u64 + 7));
                let (mut ar, mut ai, mut br, mut bi) = (r0.clone(), i0.clone(), r0, i0);
                fft_reference(&mut ar, &mut ai, inverse);
                fft(&mut br, &mut bi, inverse);
                let d = ar.iter().zip(&br).chain(ai.iter().zip(&bi)).map(|(a, b)| (a - b).abs()).fold(0.0, f64::max);
                worst = worst.max(d);
                assert!(d < 1e-9, "n={n} inverse={inverse}: {d:e}");
            }
        }
        println!("FFT max abs diff (f64, sizes 256..65536, fwd+inv): {worst:e}");
        let x: Vec<f32> = noise(30000, 3).iter().map(|v| *v as f32 * 0.5).collect();
        let [hall, _] = builtin("stage.scoring_hall", 44100.0).unwrap();
        let new = convolve(&x, &hall);
        let old = convolve_reference(&x, &hall);
        let d = new.iter().zip(&old).map(|(a, b)| (a - b).abs()).fold(0.0, f64::max);
        let d32 = new.iter().zip(&old).map(|(a, b)| ((*a as f32) - (*b as f32)).abs()).fold(0.0, f32::max);
        println!("CONVOLVE hall (30000 samples x {} taps) max abs diff f64 {d:e}, after the f32 cast {d32:e}", hall.len());
        assert!(d < 1e-9);
    }

    fn convolve_reference(x: &[f32], ir: &[f64]) -> Vec<f64> {
        let mut out = vec![0.0; x.len()];
        let n = (2 * ir.len()).next_power_of_two().max(256);
        let block = n - ir.len() + 1;
        let (mut hr, mut hi) = (vec![0.0; n], vec![0.0; n]);
        hr[..ir.len()].copy_from_slice(ir);
        fft_reference(&mut hr, &mut hi, false);
        let (mut re, mut im) = (vec![0.0; n], vec![0.0; n]);
        for start in (0..x.len()).step_by(block) {
            let end = (start + block).min(x.len());
            re.iter_mut().chain(im.iter_mut()).for_each(|v| *v = 0.0);
            for (k, v) in x[start..end].iter().enumerate() {
                re[k] = *v as f64;
            }
            fft_reference(&mut re, &mut im, false);
            for k in 0..n {
                (re[k], im[k]) = (re[k] * hr[k] - im[k] * hi[k], re[k] * hi[k] + im[k] * hr[k]);
            }
            fft_reference(&mut re, &mut im, true);
            for (k, v) in re.iter().enumerate().take(x.len() - start) {
                out[start + k] += v;
            }
        }
        out
    }

    #[test]
    fn convolution_matches_the_direct_sum() {
        let x: Vec<f32> = (0..3000).map(|i| ((i * 7919) % 101) as f32 / 50.0 - 1.0).collect();
        let h: Vec<f64> = (0..300).map(|i| ((i as f64) * 0.37).sin() * (-(i as f64) / 80.0).exp()).collect();
        let y = convolve(&x, &h);
        for &i in &[0usize, 17, 299, 1500, 2999] {
            let direct: f64 = (0..=i.min(h.len() - 1)).map(|k| x[i - k] as f64 * h[k]).sum();
            assert!((y[i] - direct).abs() < 1e-9, "sample {i}: {} vs {direct}", y[i]);
        }
    }

    /// The level of `hz` in a signal (one DFT bin).
    fn level(x: &[f64], hz: f64, sr: f64) -> f64 {
        let (mut c, mut s) = (0.0, 0.0);
        for (i, v) in x.iter().enumerate() {
            let p = 2.0 * PI * hz * i as f64 / sr;
            (c, s) = (c + v * p.cos(), s + v * p.sin());
        }
        (c * c + s * s).sqrt()
    }

    #[test]
    fn a_body_resonates_at_its_modes_and_dies_fast() {
        let sr = 44100.0;
        let [l, _] = builtin("body.wood_hollow", sr).unwrap();
        assert!(l.len() < (0.07 * sr) as usize, "a short body: {} samples", l.len());
        assert!(level(&l, 290.0, sr) > 3.0 * level(&l, 3800.0, sr), "wood rings in its low mids");
        let [c, _] = builtin("body.cello", sr).unwrap();
        assert!(level(&c, 185.0, sr) > level(&c, 1500.0, sr));
    }

    #[test]
    fn the_hall_tail_decays_and_its_highs_die_first() {
        let sr = 44100.0;
        let [h, r] = builtin("stage.scoring_hall", sr).unwrap();
        let energy = |a: f64, b: f64| h[(a * sr) as usize..(b * sr) as usize].iter().map(|v| v * v).sum::<f64>();
        let (early, late) = (energy(0.1, 0.3), energy(1.5, 1.7));
        let db = 10.0 * (early / late).log10();
        assert!((35.0..65.0).contains(&db), "about 2 s RT60: {db:.1} dB down over 1.4 s");
        assert_ne!(h[5000], r[5000], "left and right walls differ");
        let late_tail = &h[(1.2 * sr) as usize..(1.6 * sr) as usize];
        assert!(level(late_tail, 300.0, sr) > 2.0 * level(late_tail, 8000.0, sr), "the highs have died first");
        assert!(builtin("body.nothing", sr).is_err());
    }

    #[test]
    fn the_mix_blends_dry_and_wet() {
        let sr = 1000.0;
        let mut l = vec![0.0f32; 100];
        l[0] = 1.0;
        let mut r = l.clone();
        let file = std::env::temp_dir().join("rostrum-ir-test.f32");
        let ir: Vec<u8> = [0.0f32, 0.0, 0.0, 0.0, 0.5, 0.5].iter().flat_map(|v| v.to_le_bytes()).collect(); // 3 stereo frames: silent, silent, half
        std::fs::write(&file, ir).unwrap();
        let pcm = Pcm { file: file.to_string_lossy().into(), channels: 2, frames: 3 };
        run(&Ir::File(pcm), &Param::Value(0.5), &mut l, &mut r, sr).unwrap();
        assert!((l[0] - 0.5).abs() < 1e-6 && (l[2] - 0.25).abs() < 1e-6 && l[1].abs() < 1e-6, "{:?}", &l[..3]);
    }
}
