//! The short-time Fourier transform the spectral repairs share (dereverb, spectral repair, the
//! inspection's spectrogram): sqrt-Hann analysis and synthesis windows, the overlap normalised
//! sample by sample, so an unmodified spectrum gives the signal back exactly.

use std::f64::consts::PI;

use crate::fx::convolve::fft;

pub struct Spec {
    pub n: usize,
    pub hop: usize,
    /// frames × (n/2 + 1) bins.
    pub re: Vec<Vec<f64>>,
    pub im: Vec<Vec<f64>>,
}

fn window(n: usize) -> Vec<f64> {
    (0..n).map(|i| (0.5 - 0.5 * (2.0 * PI * i as f64 / n as f64).cos()).sqrt()).collect()
}

/// Where frame `f` starts in the signal (it may start before 0: the first frame ends one hop in).
pub fn frame_start(f: usize, n: usize, hop: usize) -> isize {
    (f * hop) as isize - (n - hop) as isize
}

/// The time (seconds) at the centre of frame `f`.
pub fn frame_time(f: usize, n: usize, hop: usize, sr: f64) -> f64 {
    (frame_start(f, n, hop) as f64 + n as f64 / 2.0) / sr
}

pub fn forward(x: &[f32], n: usize, hop: usize) -> Spec {
    let w = window(n);
    let frames = (x.len() + n - hop).div_ceil(hop);
    let bins = n / 2 + 1;
    let (mut re_out, mut im_out) = (Vec::with_capacity(frames), Vec::with_capacity(frames));
    let (mut re, mut im) = (vec![0.0; n], vec![0.0; n]);
    for f in 0..frames {
        let s = frame_start(f, n, hop);
        for i in 0..n {
            let j = s + i as isize;
            re[i] = if j >= 0 && (j as usize) < x.len() { x[j as usize] as f64 * w[i] } else { 0.0 };
            im[i] = 0.0;
        }
        fft(&mut re, &mut im, false);
        re_out.push(re[..bins].to_vec());
        im_out.push(im[..bins].to_vec());
    }
    Spec { n, hop, re: re_out, im: im_out }
}

/// The signal back, `len` samples, by weighted overlap-add.
pub fn inverse(s: &Spec, len: usize) -> Vec<f32> {
    let (n, hop) = (s.n, s.hop);
    let w = window(n);
    let mut out = vec![0.0f64; len];
    let mut norm = vec![0.0f64; len];
    let (mut re, mut im) = (vec![0.0; n], vec![0.0; n]);
    for f in 0..s.re.len() {
        for k in 0..=n / 2 {
            re[k] = s.re[f][k];
            im[k] = s.im[f][k];
        }
        for k in 1..n / 2 {
            re[n - k] = re[k];
            im[n - k] = -im[k];
        }
        fft(&mut re, &mut im, true);
        let st = frame_start(f, n, hop);
        for i in 0..n {
            let j = st + i as isize;
            if j >= 0 && (j as usize) < len {
                out[j as usize] += re[i] * w[i];
                norm[j as usize] += w[i] * w[i];
            }
        }
    }
    out.iter().zip(&norm).map(|(v, d)| if *d > 1e-9 { (v / d) as f32 } else { 0.0 }).collect()
}

impl Spec {
    pub fn power(&self, f: usize, k: usize) -> f64 {
        self.re[f][k] * self.re[f][k] + self.im[f][k] * self.im[f][k]
    }
    pub fn scale(&mut self, f: usize, k: usize, g: f64) {
        self.re[f][k] *= g;
        self.im[f][k] *= g;
    }
}

/// Both channels through one gain mask (frames × bins, from the mid signal), so the image holds.
pub fn apply_mask(l: &mut [f32], r: &mut [f32], n: usize, hop: usize, mask: &dyn Fn(&Spec) -> Vec<Vec<f64>>) {
    let mid: Vec<f32> = l.iter().zip(r.iter()).map(|(a, b)| (a + b) * 0.5).collect();
    let g = mask(&forward(&mid, n, hop));
    for ch in [l, r] {
        let mut s = forward(ch, n, hop);
        for (f, row) in g.iter().enumerate() {
            for (k, &v) in row.iter().enumerate() {
                if v != 1.0 {
                    s.scale(f, k, v);
                }
            }
        }
        let y = inverse(&s, ch.len());
        ch.copy_from_slice(&y);
    }
}
