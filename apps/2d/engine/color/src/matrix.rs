//! 3×3 maths in f64: RGB ↔ XYZ from primaries (SMPTE RP 177-1993 §3.3) and chromatic adaptation.

pub type Mat3 = [[f64; 3]; 3];

pub const IDENTITY: Mat3 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]];

pub fn mul(a: &Mat3, b: &Mat3) -> Mat3 {
    let mut m = [[0.0; 3]; 3];
    for (i, row) in m.iter_mut().enumerate() {
        for (j, v) in row.iter_mut().enumerate() {
            *v = (0..3).map(|k| a[i][k] * b[k][j]).sum();
        }
    }
    m
}

pub fn apply(m: &Mat3, v: [f64; 3]) -> [f64; 3] {
    m.map(|r| r[0] * v[0] + r[1] * v[1] + r[2] * v[2])
}

/// Inverse by cofactors; panics on a singular matrix (never the case for real primaries).
pub fn inverse(m: &Mat3) -> Mat3 {
    let c = |i: usize, j: usize| {
        let (r0, r1) = ((i + 1) % 3, (i + 2) % 3);
        let (c0, c1) = ((j + 1) % 3, (j + 2) % 3);
        m[r0][c0] * m[r1][c1] - m[r0][c1] * m[r1][c0]
    };
    let det = m[0][0] * c(0, 0) + m[0][1] * c(0, 1) + m[0][2] * c(0, 2);
    assert!(det.abs() > 1e-12, "singular matrix");
    let mut inv = [[0.0; 3]; 3];
    for (i, row) in inv.iter_mut().enumerate() {
        for (j, v) in row.iter_mut().enumerate() {
            *v = c(j, i) / det;
        }
    }
    inv
}

/// Chromaticity xy → XYZ with Y = 1.
pub fn xy_to_xyz([x, y]: [f64; 2]) -> [f64; 3] {
    [x / y, 1.0, (1.0 - x - y) / y]
}

/// Red, green, blue and white chromaticities.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Primaries {
    pub r: [f64; 2],
    pub g: [f64; 2],
    pub b: [f64; 2],
    pub w: [f64; 2],
}

/// RGB → XYZ, white mapping to Y = 1.
pub fn rgb_to_xyz(p: &Primaries) -> Mat3 {
    let cols = [xy_to_xyz(p.r), xy_to_xyz(p.g), xy_to_xyz(p.b)];
    let m: Mat3 = [0, 1, 2].map(|i| cols.map(|c| c[i]));
    let s = apply(&inverse(&m), xy_to_xyz(p.w));
    m.map(|r| [r[0] * s[0], r[1] * s[1], r[2] * s[2]])
}

/// Chromatic adaptation transforms (cone-response matrices).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Cat {
    /// Lam 1985, as in ICC v4 and OCIO's `_BFD` utility matrices.
    Bradford,
    /// CIECAM02 (CIE 159:2004).
    Cat02,
    /// Von Kries with the Hunt-Pointer-Estévez cone fundamentals (colour-science's "Von Kries").
    VonKries,
}

impl Cat {
    pub fn cone(self) -> Mat3 {
        match self {
            Cat::Bradford => [[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]],
            Cat::Cat02 => [[0.7328, 0.4296, -0.1624], [-0.7036, 1.6975, 0.0061], [0.0030, 0.0136, 0.9834]],
            Cat::VonKries => [[0.40024, 0.70760, -0.08081], [-0.22630, 1.16532, 0.04570], [0.0, 0.0, 0.91822]],
        }
    }
    /// XYZ under white `src` → XYZ under white `dst` (von Kries-type scaling in this cone space).
    pub fn adapt(self, src: [f64; 2], dst: [f64; 2]) -> Mat3 {
        let m = self.cone();
        let (s, d) = (apply(&m, xy_to_xyz(src)), apply(&m, xy_to_xyz(dst)));
        let scale = [[d[0] / s[0], 0.0, 0.0], [0.0, d[1] / s[1], 0.0], [0.0, 0.0, d[2] / s[2]]];
        mul(&inverse(&m), &mul(&scale, &m))
    }
    pub fn from_id(id: &str) -> Option<Cat> {
        match id {
            "bradford" => Some(Cat::Bradford),
            "cat02" => Some(Cat::Cat02),
            "vonkries" => Some(Cat::VonKries),
            _ => None,
        }
    }
}
