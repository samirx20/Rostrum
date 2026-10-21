//! A clip's spectrogram as a PNG an agent can look at: time across (pooled to at most 1200 columns),
//! a log-frequency axis up (40 Hz to Nyquist), level as colour over 90 dB below the loudest bin.
//! Grid lines at 100 Hz, 1 kHz and 10 kHz; time ticks at the top and bottom every second (every
//! 0.5 s under 3 s); each detected noise outlined in cyan.

use crate::analysis::stft::Spec;

pub const MIN_HZ: f64 = 40.0;
const HEIGHT: usize = 320;
const MAX_WIDTH: usize = 1200;

fn colour(v: f64) -> [u8; 3] {
    // Black → violet → red → orange → pale yellow.
    const STOPS: [(f64, [f64; 3]); 5] = [(0.0, [0.0, 0.0, 0.0]), (0.3, [80.0, 18.0, 123.0]), (0.55, [190.0, 45.0, 75.0]), (0.8, [250.0, 140.0, 20.0]), (1.0, [252.0, 252.0, 190.0])];
    let v = v.clamp(0.0, 1.0);
    for w in STOPS.windows(2) {
        if v <= w[1].0 {
            let t = (v - w[0].0) / (w[1].0 - w[0].0);
            return [0, 1, 2].map(|c| (w[0].1[c] + (w[1].1[c] - w[0].1[c]) * t) as u8);
        }
    }
    [252, 252, 190]
}

/// Writes the PNG; `boxes` are (from s, to s, low Hz, high Hz). Returns (width, height).
pub fn write(path: &str, s: &Spec, sr: f64, seconds: f64, boxes: &[(f64, f64, f64, f64)]) -> Result<(usize, usize), String> {
    let frames = s.re.len().max(1);
    let width = frames.min(MAX_WIDTH);
    let max_hz = sr / 2.0;
    let hz_per_bin = sr / s.n as f64;
    let row_hz = |y: usize| MIN_HZ * (max_hz / MIN_HZ).powf((HEIGHT - 1 - y) as f64 / (HEIGHT - 1) as f64);
    let y_of = |hz: f64| ((HEIGHT - 1) as f64 * (1.0 - (hz.max(MIN_HZ) / MIN_HZ).ln() / (max_hz / MIN_HZ).ln())).round().clamp(0.0, (HEIGHT - 1) as f64) as usize;
    let x_of = |t: f64| ((t / seconds.max(1e-9)) * width as f64).round().clamp(0.0, (width - 1) as f64) as usize;
    let mut db = vec![f64::MIN; width * HEIGHT];
    for x in 0..width {
        let (f0, f1) = (x * frames / width, ((x + 1) * frames / width).max(x * frames / width + 1));
        for y in 0..HEIGHT {
            let (lo, hi) = (row_hz(y.min(HEIGHT - 1) + 1).min(row_hz(y)), row_hz(y));
            let (k0, k1) = ((lo / hz_per_bin).floor() as usize, ((hi / hz_per_bin).ceil() as usize).min(s.n / 2));
            let mut m = 0.0f64;
            for f in f0..f1.min(frames) {
                for k in k0..=k1.max(k0) {
                    m = m.max(s.power(f, k.min(s.n / 2)));
                }
            }
            db[y * width + x] = 10.0 * m.max(1e-20).log10();
        }
    }
    let top = db.iter().fold(f64::MIN, |a, b| a.max(*b));
    let mut rgb = vec![0u8; width * HEIGHT * 3];
    for (i, v) in db.iter().enumerate() {
        rgb[i * 3..i * 3 + 3].copy_from_slice(&colour((v - top + 90.0) / 90.0));
    }
    let mut put = |x: usize, y: usize, c: [u8; 3]| {
        if x < width && y < HEIGHT {
            rgb[(y * width + x) * 3..(y * width + x) * 3 + 3].copy_from_slice(&c);
        }
    };
    for hz in [100.0, 1000.0, 10000.0] {
        if hz < max_hz {
            for x in (0..width).step_by(3) {
                put(x, y_of(hz), [110, 110, 110]);
            }
        }
    }
    let tick = if seconds < 3.0 { 0.5 } else { 1.0 };
    let mut t = tick;
    while t < seconds {
        for y in (0..6).chain(HEIGHT - 6..HEIGHT) {
            put(x_of(t), y, [230, 230, 230]);
        }
        t += tick;
    }
    for &(a, b, lo, hi) in boxes {
        let (x0, x1, y0, y1) = (x_of(a), x_of(b), y_of(hi), y_of(lo));
        for x in x0..=x1 {
            put(x, y0, [0, 230, 255]);
            put(x, y1, [0, 230, 255]);
        }
        for y in y0..=y1 {
            put(x0, y, [0, 230, 255]);
            put(x1, y, [0, 230, 255]);
        }
    }
    let file = std::fs::File::create(path).map_err(|e| format!("{path}: {e}"))?;
    let mut enc = png::Encoder::new(std::io::BufWriter::new(file), width as u32, HEIGHT as u32);
    enc.set_color(png::ColorType::Rgb);
    enc.set_depth(png::BitDepth::Eight);
    enc.write_header().and_then(|mut w| w.write_image_data(&rgb)).map_err(|e| format!("{path}: {e}"))?;
    Ok((width, HEIGHT))
}
