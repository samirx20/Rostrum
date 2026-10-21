//! A vibrating string as a digital waveguide (Karplus–Strong, extended): one delay loop whose length is
//! the period, read at a fractional position (Lagrange, so the pitch is exact and can bend), a loss
//! filter that takes more from the high partials each trip (they die first, as on a real string), and
//! two all-passes that make high partials travel faster (a stiff steel string's sharp overtones). The
//! loop's total delay at the fundamental — read, loss filter and dispersion together — is the period,
//! so a note is in tune to a fraction of a cent.

use std::f64::consts::PI;

/// What the string is made of.
#[derive(Clone, Copy, Debug)]
pub struct Material {
    /// Seconds a low E (82 Hz) rings / a high E (330 Hz) rings (−60 dB), interpolated in log pitch.
    pub t60_low: f64,
    pub t60_high: f64,
    /// The loss filter's pole: more takes more from the high partials each period.
    pub loss: f64,
    /// The dispersion all-passes' coefficient (0: none; negative: stiff, overtones sharp).
    pub stiffness: f64,
}

/// First-order all-pass (a + z⁻¹)/(1 + a z⁻¹).
#[derive(Clone, Copy, Default)]
struct Allpass {
    a: f64,
    x1: f64,
    y1: f64,
}
impl Allpass {
    #[inline]
    fn tick(&mut self, x: f64) -> f64 {
        let y = self.a * x + self.x1 - self.a * self.y1;
        self.x1 = x;
        self.y1 = super::flush(y);
        y
    }
}

/// Phase delay (samples) at `w` rad/sample of a filter given its frequency response there.
fn phase_delay(re: f64, im: f64, w: f64) -> f64 {
    -im.atan2(re) / w
}

/// The one-pole loss filter (1−b)/(1−b z⁻¹): its phase delay and gain at `w`.
fn loss_at(b: f64, w: f64) -> (f64, f64) {
    let (dr, di) = (1.0 - b * w.cos(), b * w.sin());
    let d2 = dr * dr + di * di;
    let (re, im) = ((1.0 - b) * dr / d2, -(1.0 - b) * di / d2);
    (phase_delay(re, im, w), (re * re + im * im).sqrt())
}

/// A first-order all-pass's phase delay at `w`.
fn allpass_delay(a: f64, w: f64) -> f64 {
    let (c, s) = (w.cos(), -w.sin());
    let (nr, ni) = (a + c, s);
    let (dr, di) = (1.0 + a * c, a * s);
    let d2 = dr * dr + di * di;
    phase_delay((nr * dr + ni * di) / d2, (ni * dr - nr * di) / d2, w)
}

pub struct StringLoop {
    buf: Vec<f64>,
    w: usize,
    g: f64,
    b: f64,
    lp: f64,
    ap: [Allpass; 2],
    /// The filters' delay at the fundamental (samples): the read takes the rest of the period.
    filt_delay: f64,
    sr: f64,
}

impl StringLoop {
    /// A string tuned to `freq`, ringing `t60` seconds at its fundamental.
    pub fn new(freq: f64, t60: f64, m: &Material, sr: f64) -> StringLoop {
        let b = m.loss.clamp(0.0, 0.95);
        let mut s = StringLoop { buf: vec![0.0; (sr / 20.0) as usize + 8], w: 0, g: 1.0, b, lp: 0.0, ap: [Allpass { a: m.stiffness, ..Default::default() }; 2], filt_delay: 0.0, sr };
        s.tune(freq, t60);
        s
    }

    /// Sets the pitch and the decay (the loop gain per period that gives `t60` at the fundamental).
    pub fn tune(&mut self, freq: f64, t60: f64) {
        let w = 2.0 * PI * freq / self.sr;
        let (d_loss, mag) = loss_at(self.b, w);
        self.filt_delay = d_loss + self.ap.iter().map(|a| allpass_delay(a.a, w)).sum::<f64>();
        let per_period = 10f64.powf(-3.0 / (t60.max(0.005) * freq));
        self.g = (per_period / mag).min(0.99999);
    }

    /// Changes only the decay (a damper), keeping the pitch.
    pub fn damp(&mut self, freq: f64, t60: f64, extra_loss: f64) {
        self.b = (self.b + extra_loss).min(0.95);
        self.tune(freq, t60);
    }

    /// The next sample: the loop's output at fundamental `freq` (bent freely), plus `input` injected.
    #[inline]
    pub fn tick(&mut self, freq: f64, input: f64) -> f64 {
        let n = self.buf.len();
        let d = (self.sr / freq - self.filt_delay).clamp(2.0, (n - 4) as f64);
        let di = d.floor();
        let f = d - di + 1.0;
        let base = self.w + n - di as usize + 1;
        let x = |k: usize| self.buf[(base - k) % n];
        let h0 = -(f - 1.0) * (f - 2.0) * (f - 3.0) / 6.0;
        let h1 = f * (f - 2.0) * (f - 3.0) / 2.0;
        let h2 = -f * (f - 1.0) * (f - 3.0) / 2.0;
        let h3 = f * (f - 1.0) * (f - 2.0) / 6.0;
        let r = h0 * x(0) + h1 * x(1) + h2 * x(2) + h3 * x(3);
        self.lp = super::flush(self.g * ((1.0 - self.b) * r + self.b * self.lp));
        let mut y = self.lp;
        for a in self.ap.iter_mut() {
            y = a.tick(y);
        }
        let out = y + input;
        self.buf[self.w] = out;
        self.w = (self.w + 1) % n;
        out
    }
}

/// How long the material rings at `freq` (interpolated between its low and high E in log pitch).
pub fn t60_at(m: &Material, freq: f64) -> f64 {
    let u = ((freq / 82.41).log2() / 2.0).clamp(-0.5, 2.0);
    m.t60_low * (m.t60_high / m.t60_low).powf(u)
}
