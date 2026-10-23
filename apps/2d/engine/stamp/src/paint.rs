//! marks.py `apply_paint` for one pixel: the one place paint meets a layer, each step in numpy's precision (`k` is a
//! Python number, so `k · c0` is f32; `c1` is f64, so the step is f64 and the pixel is rounded back to f32 once).

#[derive(Clone, Copy, PartialEq)]
pub enum Mode {
    Normal,
    Multiply,
    Erase,
    Screen,
    Add,
    Overlay,
    SoftLight,
    Color,
}

impl Mode {
    /// The kit's `MODES` order.
    pub fn from_id(id: f64) -> Option<Mode> {
        [Mode::Normal, Mode::Multiply, Mode::Erase, Mode::Screen, Mode::Add, Mode::Overlay, Mode::SoftLight, Mode::Color]
            .get(id as usize)
            .copied()
    }

    /// Reads a copy of what was under the stroke (the kit's `UNDER`).
    pub fn reads_under(self) -> bool {
        matches!(self, Mode::Overlay | Mode::SoftLight | Mode::Color)
    }
}

/// `px` premultiplied RGBA; the stroke's coverage here went c0 → c1; `col` the straight colour; `k` the share that
/// is paint (1 − wetness); `base` what was under the stroke here (the modes that read it).
pub fn apply(px: &mut [f32], c0: f32, c1: f64, col: [f64; 3], mode: Mode, k: f64, base: &[f32]) {
    let inc = k * (c1 - c0 as f64) / (1.0001f32 - c0) as f64;
    let lo = (k as f32 * c0) as f64;
    let hi = k * c1;
    let alpha = |px: &mut [f32]| px[3] = (px[3] as f64 + inc * (1.0f32 - px[3]) as f64) as f32;
    match mode {
        Mode::Normal => {
            for ch in 0..3 {
                px[ch] = (px[ch] as f64 + inc * (col[ch] - px[ch] as f64)) as f32;
            }
            alpha(px);
        }
        Mode::Multiply => {
            for ch in 0..3 {
                px[ch] = (px[ch] as f64 * ((1.0 - hi * (1.0 - col[ch])) / (1.0 - lo * (1.0 - col[ch])))) as f32;
            }
        }
        Mode::Erase => {
            for v in px.iter_mut() {
                *v = (*v as f64 * (1.0 - inc)) as f32;
            }
        }
        Mode::Screen => {
            alpha(px);
            for ch in 0..3 {
                let s = (hi - lo) * col[ch] / (1.0 - lo * col[ch]);
                let v = px[ch] as f64;
                px[ch] = (v + s - v * s) as f32;
            }
        }
        Mode::Add => {
            alpha(px);
            for ch in 0..3 {
                px[ch] = f64::min(px[ch] as f64 + (hi - lo) * col[ch], 1.0) as f32;
            }
            px[3] = px[3].max(px[0].max(px[1]).max(px[2]));
        }
        Mode::Overlay | Mode::SoftLight | Mode::Color => {
            let t = blend_under(base, col, mode);
            for ch in 0..3 {
                px[ch] = (px[ch] as f64 + inc * (t[ch] - px[ch] as f64)) as f32;
            }
        }
    }
}

fn lum(c: [f64; 3]) -> f64 {
    0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
}

/// marks.py `blend_under`: the paint blended over `base` (premultiplied RGBA), premultiplied, in f64.
fn blend_under(base: &[f32], col: [f64; 3], mode: Mode) -> [f64; 3] {
    let a = base[3] as f64;
    let b = [0, 1, 2].map(|ch| if a > 0.0 { base[ch] as f64 / a } else { 0.0 }.clamp(0.0, 1.0));
    let s = col.map(|v| v.clamp(0.0, 1.0));
    let out = match mode {
        Mode::Overlay => [0, 1, 2].map(|i| if b[i] <= 0.5 { 2.0 * b[i] * s[i] } else { 1.0 - 2.0 * (1.0 - b[i]) * (1.0 - s[i]) }),
        Mode::SoftLight => [0, 1, 2].map(|i| {
            let (b, s) = (b[i], s[i]);
            if s <= 0.5 {
                b - (1.0 - 2.0 * s) * b * (1.0 - b)
            } else {
                let d = if b <= 0.25 { ((16.0 * b - 12.0) * b + 4.0) * b } else { b.sqrt() };
                b + (2.0 * s - 1.0) * (d - b)
            }
        }),
        _ => {
            let d = lum(b) - lum(s);
            let c = s.map(|v| v + d);
            let (l, n, x) = (lum(c), c[0].min(c[1]).min(c[2]), c[0].max(c[1]).max(c[2]));
            let c = if n < 0.0 { c.map(|v| l + (v - l) * l / (l - n)) } else { c };
            if x > 1.0 { c.map(|v| l + (v - l) * (1.0 - l) / (x - l)) } else { c }
        }
    };
    out.map(|v| v * a)
}
