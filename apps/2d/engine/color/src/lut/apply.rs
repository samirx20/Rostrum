//! LUT tables and their evaluation. Input outside the domain clamps to its edges, as OCIO's
//! `FileTransform` does. Tables are `.cube` order: red fastest, then green, then blue.
use crate::Rgb;

/// A per-channel 1D table on `[min, max]`.
#[derive(Clone, Debug, PartialEq)]
pub struct Lut1d {
    pub min: Rgb,
    pub max: Rgb,
    pub data: Vec<Rgb>,
}

/// An `N³` table on `[min, max]` per axis.
#[derive(Clone, Debug, PartialEq)]
pub struct Lut3d {
    pub size: usize,
    pub min: Rgb,
    pub max: Rgb,
    pub data: Vec<Rgb>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Interp {
    Trilinear,
    Tetrahedral,
}

/// Domain position → continuous grid coordinate in `[0, n − 1]` (NaN lands on 0).
fn coord(x: f32, min: f32, max: f32, n: usize) -> f32 {
    ((x - min) / (max - min)).max(0.0).min(1.0) * (n - 1) as f32
}

/// Grid coordinate → (lower index, fraction), keeping the upper index in range.
fn split(t: f32, n: usize) -> (usize, f32) {
    let i = (t.floor() as usize).min(n - 2);
    (i, t - i as f32)
}

fn lerp(a: Rgb, b: Rgb, t: f32) -> Rgb {
    [0, 1, 2].map(|c| a[c] + (b[c] - a[c]) * t)
}

impl Lut1d {
    /// Linear interpolation per channel.
    pub fn apply(&self, rgb: Rgb) -> Rgb {
        let n = self.data.len();
        [0, 1, 2].map(|c| {
            let (i, f) = split(coord(rgb[c], self.min[c], self.max[c], n), n);
            let (a, b) = (self.data[i][c], self.data[i + 1][c]);
            a + (b - a) * f
        })
    }
    /// Sample `f` per channel at `size` points over `[min, max]` (each channel independently).
    pub fn bake(size: usize, min: Rgb, max: Rgb, f: impl Fn(Rgb) -> Rgb) -> Lut1d {
        let at = |i: usize| [0, 1, 2].map(|c| min[c] + (max[c] - min[c]) * i as f32 / (size - 1) as f32);
        Lut1d { min, max, data: (0..size).map(|i| f(at(i))).collect() }
    }
}

impl Lut3d {
    fn at(&self, r: usize, g: usize, b: usize) -> Rgb {
        self.data[r + self.size * (g + self.size * b)]
    }
    pub fn apply(&self, rgb: Rgb, interp: Interp) -> Rgb {
        let n = self.size;
        let [(r, fr), (g, fg), (b, fb)] = [0, 1, 2].map(|c| split(coord(rgb[c], self.min[c], self.max[c], n), n));
        let c = |dr: usize, dg: usize, db: usize| self.at(r + dr, g + dg, b + db);
        match interp {
            Interp::Trilinear => {
                let x0 = lerp(lerp(c(0, 0, 0), c(1, 0, 0), fr), lerp(c(0, 1, 0), c(1, 1, 0), fr), fg);
                let x1 = lerp(lerp(c(0, 0, 1), c(1, 0, 1), fr), lerp(c(0, 1, 1), c(1, 1, 1), fr), fg);
                lerp(x0, x1, fb)
            }
            Interp::Tetrahedral => {
                // Pick the tetrahedron by the order of the fractions; weights walk 000 → … → 111.
                let (c000, c111) = (c(0, 0, 0), c(1, 1, 1));
                let (w, p, q) = if fr > fg {
                    if fg > fb {
                        ([1.0 - fr, fr - fg, fg - fb, fb], c(1, 0, 0), c(1, 1, 0))
                    } else if fr > fb {
                        ([1.0 - fr, fr - fb, fb - fg, fg], c(1, 0, 0), c(1, 0, 1))
                    } else {
                        ([1.0 - fb, fb - fr, fr - fg, fg], c(0, 0, 1), c(1, 0, 1))
                    }
                } else if fb > fg {
                    ([1.0 - fb, fb - fg, fg - fr, fr], c(0, 0, 1), c(0, 1, 1))
                } else if fb > fr {
                    ([1.0 - fg, fg - fb, fb - fr, fr], c(0, 1, 0), c(0, 1, 1))
                } else {
                    ([1.0 - fg, fg - fr, fr - fb, fb], c(0, 1, 0), c(1, 1, 0))
                };
                [0, 1, 2].map(|k| w[0] * c000[k] + w[1] * p[k] + w[2] * q[k] + w[3] * c111[k])
            }
        }
    }
    /// Sample `f` on an `size³` grid over `[min, max]`.
    pub fn bake(size: usize, min: Rgb, max: Rgb, f: impl Fn(Rgb) -> Rgb) -> Lut3d {
        let axis = |c: usize, i: usize| min[c] + (max[c] - min[c]) * i as f32 / (size - 1) as f32;
        let data = (0..size * size * size)
            .map(|i| f([axis(0, i % size), axis(1, i / size % size), axis(2, i / (size * size))]))
            .collect();
        Lut3d { size, min, max, data }
    }
}
