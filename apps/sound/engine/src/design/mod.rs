//! Designed sounds: motion-design effects built from layers, each layer a control, so one sound fits
//! one move (a slow heavy slide and a quick flick get different whooshes, a snap stop gets its own
//! click). Whoosh (whoosh.rs), click / tick / tap / pop (click.rs), riser, hit and sub drop (big.rs).
//! The field table below is the one source of truth: the contract reads through it (contract/designed.rs),
//! `describe` answers it, and the Python side builds its document fields from that answer.
//! Deterministic: the noise is seeded by the sound's `seed`.

mod big;
mod click;
mod whoosh;

use serde_json::{Map, Value};

/// A field: name, lowest, highest, default (NaN = required), what it does.
pub struct F(pub &'static str, pub f64, pub f64, pub f64, pub &'static str);

const REQUIRED: f64 = f64::NAN;

/// Fields every design has.
pub const COMMON: &[F] = &[
    F("volume", 0.0, 4.0, 1.0, "Level (1 = the design's own peak level)"),
    F("pan", -1.0, 1.0, 0.0, "Left … right (a whoosh's panPath overrides it)"),
    F("width", 0.0, 1.0, 0.5, "Mono … wide stereo"),
    F("seed", 1.0, 999_999.0, 1.0, "Another whole number: another take of the same design"),
];

pub const DESIGNS: &[(&str, &[F])] = &[
    ("whoosh", &[
        F("dur", 0.04, 10.0, REQUIRED, "Length (s): the move's start to its stop"),
        F("brightness", 0.0, 1.0, 0.5, "Dark … bright (where the noise sits)"),
        F("size", 0.0, 1.0, 0.5, "Small and light … big and heavy (adds low body, lowers the sweep)"),
        F("doppler", 0.0, 1.0, 0.3, "How far the pitch falls as it passes its fastest point"),
        F("tone", 0.0, 1.0, 0.25, "A tuned whistle layer riding the sweep"),
        F("air", 0.0, 1.0, 0.4, "High air at the fastest moment"),
        F("texture", 0.0, 1.0, 0.2, "Smooth … rough (fabric / fan flutter)"),
    ]),
    ("click", &[
        F("pitch", 100.0, 12000.0, 1800.0, "The body's pitch (Hz)"),
        F("material", 0.0, 1.0, 0.3, "Soft plastic (0) … glass (0.5) … metal (1)"),
        F("tight", 0.0, 1.0, 0.6, "Ringing … tight and short"),
        F("body", 0.0, 1.0, 0.6, "The tuned body's level"),
        F("transient", 0.0, 1.0, 0.7, "The first-millisecond snap's level"),
        F("air", 0.0, 1.0, 0.3, "A high tick of air"),
        F("bend", -1.0, 1.0, 0.0, "Pitch sweep: above 0 falls into the note (a knock), below 0 rises (a pop)"),
    ]),
    ("riser", &[
        F("dur", 0.1, 20.0, REQUIRED, "Length (s); it peaks at its end"),
        F("pitch", 40.0, 2000.0, 220.0, "The tonal layer's starting pitch (Hz); it climbs two octaves"),
        F("brightness", 0.0, 1.0, 0.5, "How high the noise sweep climbs"),
        F("curve", 0.0, 1.0, 0.5, "Even climb … holds back and surges at the end"),
        F("tone", 0.0, 1.0, 0.4, "The tonal layer's level"),
        F("air", 0.0, 1.0, 0.4, "Hiss near the peak"),
        F("texture", 0.0, 1.0, 0.5, "An accelerating flutter"),
    ]),
    ("hit", &[
        F("pitch", 25.0, 200.0, 50.0, "The sub thump's pitch (Hz)"),
        F("size", 0.0, 1.0, 0.6, "Small knock … huge"),
        F("brightness", 0.0, 1.0, 0.5, "The crack's level and the tail's brightness"),
        F("tail", 0.05, 6.0, 1.2, "How long the tail rings (s)"),
        F("drive", 0.0, 1.0, 0.3, "Saturation (weight on small speakers)"),
    ]),
    ("subDrop", &[
        F("dur", 0.1, 8.0, 1.2, "Length (s)"),
        F("pitch", 25.0, 200.0, 40.0, "Where it lands (Hz)"),
        F("drop", 0.0, 4.0, 1.5, "How far it falls (octaves)"),
        F("drive", 0.0, 1.0, 0.2, "Saturation"),
    ]),
];

/// The design's own fields, or None for an unknown design.
pub fn fields(design: &str) -> Option<&'static [F]> {
    DESIGNS.iter().find(|(n, _)| *n == design).map(|(_, f)| *f)
}

pub fn names() -> Vec<&'static str> {
    DESIGNS.iter().map(|(n, _)| *n).collect()
}

/// A resolved sound (every field present), read by the designs.
pub struct P<'a>(pub &'a Map<String, Value>);

impl P<'_> {
    pub fn f(&self, k: &str) -> f64 {
        self.0.get(k).and_then(Value::as_f64).unwrap_or(0.0)
    }
    /// A lane `[[fraction 0 … 1, value], …]`, if given.
    pub fn lane(&self, k: &str) -> Option<Vec<[f64; 2]>> {
        serde_json::from_value(self.0.get(k)?.clone()).ok()
    }
}

/// Straight lines between points, held before the first and after the last.
pub fn at(lane: &[[f64; 2]], u: f64) -> f64 {
    match lane.iter().position(|p| p[0] > u) {
        None => lane.last().map_or(0.0, |p| p[1]),
        Some(0) => lane[0][1],
        Some(k) => {
            let ([u0, v0], [u1, v1]) = (lane[k - 1], lane[k]);
            v0 + (v1 - v0) * ((u - u0) / (u1 - u0).max(1e-9))
        }
    }
}

/// How long the rendered sound is (its ring-out included), seconds.
pub fn seconds(spec: &Map<String, Value>) -> f64 {
    let p = P(spec);
    match spec.get("design").and_then(Value::as_str).unwrap_or("") {
        "whoosh" => p.f("dur") + 0.12,
        "click" => 0.6,
        "riser" => p.f("dur") + 0.05,
        "hit" => p.f("tail") + 0.4,
        _ => p.f("dur") + 0.1,
    }
}

/// Renders the sound into `l` / `r` from sample 0, peak-normalized to the design's level × volume, panned.
pub fn render(spec: &Map<String, Value>, l: &mut [f32], r: &mut [f32], sr: f64) -> Result<(), String> {
    let p = P(spec);
    let design = spec.get("design").and_then(Value::as_str).unwrap_or("");
    let mut rng = crate::sfx::Rng(0x9E37_79B9_7F4A_7C15 ^ (p.f("seed") as u64).wrapping_mul(0x2545_F491_4F6C_DD1D));
    let (mut bl, mut br) = (vec![0.0f64; l.len()], vec![0.0f64; r.len()]);
    // Each design writes a mid / side pair and (whoosh) its own pan per sample.
    let mut pan: Option<Vec<f64>> = None;
    match design {
        "whoosh" => pan = whoosh::render(&p, &mut bl, &mut br, &mut rng, sr),
        "click" => click::render(&p, &mut bl, &mut br, &mut rng, sr),
        "riser" => big::riser(&p, &mut bl, &mut br, &mut rng, sr),
        "hit" => big::hit(&p, &mut bl, &mut br, &mut rng, sr),
        "subDrop" => big::sub_drop(&p, &mut bl, &mut br, sr),
        other => return Err(format!("designed sound \"{other}\": not one of {}", names().join(", "))),
    }
    let peak = bl.iter().chain(br.iter()).fold(0.0f64, |m, x| m.max(x.abs()));
    if peak <= 0.0 {
        return Ok(());
    }
    let gain = 0.5 * p.f("volume") / peak;
    let (w, fixed) = (p.f("width"), p.f("pan"));
    let n = l.len().min(r.len()).min(bl.len());
    for i in 0..n {
        let (m, s) = (bl[i] * gain, br[i] * gain * w);
        let pn = pan.as_ref().map_or(fixed, |v| v[i]).clamp(-1.0, 1.0);
        let ang = (pn + 1.0) * std::f64::consts::FRAC_PI_4;
        l[i] = ((m + s) * ang.cos() * std::f64::consts::SQRT_2) as f32;
        r[i] = ((m - s) * ang.sin() * std::f64::consts::SQRT_2) as f32;
    }
    Ok(())
}

/// A short fade at a buffer's end so nothing clicks off.
fn end_fade(buf: &mut [f64], sr: f64) {
    let n = ((0.004 * sr) as usize).min(buf.len());
    let len = buf.len();
    for k in 0..n {
        buf[len - 1 - k] *= k as f64 / n as f64;
    }
}
