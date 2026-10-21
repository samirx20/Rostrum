//! marks.py `apply_paint` for one pixel: the one place paint meets a layer, each step in numpy's precision (`k` is a
//! Python number, so `k · c0` is f32; `c1` is f64, so the step is f64 and the pixel is rounded back to f32 once).

#[derive(Clone, Copy, PartialEq)]
pub enum Mode {
    Normal,
    Multiply,
    Erase,
    Screen,
    Add,
}

impl Mode {
    /// The kit's `MODES` order.
    pub fn from_id(id: f64) -> Option<Mode> {
        [Mode::Normal, Mode::Multiply, Mode::Erase, Mode::Screen, Mode::Add].get(id as usize).copied()
    }
}

/// `px` premultiplied RGBA; the stroke's coverage here went c0 → c1; `col` the straight colour; `k` the share that
/// is paint (1 − wetness).
pub fn apply(px: &mut [f32], c0: f32, c1: f64, col: [f64; 3], mode: Mode, k: f64) {
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
    }
}
