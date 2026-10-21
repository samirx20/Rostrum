//! The ACES 2.0 colour appearance model (a CAM16 variant, dim surround), RGB ↔ Aab ↔ JMh. A port of
//! OpenColorIO 2.5.2 `ops/fixedfunction/ACES2/Transform.cpp` (BSD-3-Clause), itself the C++ form of the
//! ACES 2.0 CTL (`aces-aswf/aces-output`, Apache-2.0). f32 throughout, in OCIO's operation order, so the
//! derived tables match OCIO's (the oracle) to the last bits.
use crate::matrix::{self, Primaries};
use crate::view::{M3, mul};

pub(crate) const PI: f32 = 3.14159265358979;
pub(crate) const REF_LUM: f32 = 100.0;
const L_A: f32 = 100.0;
const Y_B: f32 = 20.0;
const SURROUND: [f32; 3] = [0.9, 0.59, 0.9]; // dim
const J_SCALE: f32 = 100.0;
const NL_OFFSET: f32 = 0.2713 * 100.0;
const NL_SCALE: f32 = 4.0 * 100.0;

/// CAM16 primaries as ACES 2.0 defines them (white 0.333, 0.333, not 1/3).
pub(crate) const CAM16: Primaries =
    Primaries { r: [0.8336, 0.1735], g: [2.3854, -1.4659], b: [0.087, -0.125], w: [0.333, 0.333] };
pub(crate) const AP0: Primaries =
    Primaries { r: [0.7347, 0.2653], g: [0.0, 1.0], b: [0.0001, -0.077], w: [0.32168, 0.33767] };
pub(crate) const AP1: Primaries =
    Primaries { r: [0.713, 0.293], g: [0.165, 0.830], b: [0.128, 0.044], w: [0.32168, 0.33767] };

/// std::max / std::min (NaN handling as in C++, not Rust's NaN-ignoring `f32::max`).
pub(crate) fn smax(a: f32, b: f32) -> f32 {
    if a < b { b } else { a }
}
pub(crate) fn smin(a: f32, b: f32) -> f32 {
    if b < a { b } else { a }
}
pub(crate) fn lerp(a: f32, b: f32, t: f32) -> f32 {
    a + t * (b - a)
}

pub(crate) fn to_f32(m: &matrix::Mat3) -> M3 {
    m.map(|r| r.map(|v| v as f32))
}
pub(crate) fn invert(m: &M3) -> M3 {
    to_f32(&matrix::inverse(&m.map(|r| r.map(|v| v as f64))))
}
/// f32 matrix product in OCIO's `mult_f33_f33` order.
pub(crate) fn mm(a: &M3, b: &M3) -> M3 {
    std::array::from_fn(|i| std::array::from_fn(|j| a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j]))
}
fn diag(d: [f32; 3]) -> M3 {
    [[d[0], 0.0, 0.0], [0.0, d[1], 0.0], [0.0, 0.0, d[2]]]
}
pub(crate) fn rgb_to_xyz(p: &Primaries) -> M3 {
    to_f32(&matrix::rgb_to_xyz(p))
}
fn xyz_to_rgb(p: &Primaries) -> M3 {
    to_f32(&matrix::inverse(&matrix::rgb_to_xyz(p)))
}

pub(crate) fn model_gamma() -> f32 {
    SURROUND[1] * (1.48 + (Y_B / REF_LUM).sqrt())
}

fn cone_fwd_abs(rc: f32) -> f32 {
    let f = rc.powf(0.42);
    f / (NL_OFFSET + f)
}
fn cone_inv_abs(ra: f32) -> f32 {
    let r = smin(ra, 0.99);
    ((NL_OFFSET * r) / (1.0 - r)).powf(1.0 / 0.42)
}
fn cone_fwd(v: f32) -> f32 {
    cone_fwd_abs(v.abs()).copysign(v)
}
fn cone_inv(v: f32) -> f32 {
    cone_inv_abs(v.abs()).copysign(v)
}

/// The model for one set of RGB primaries (`JMhParams`).
#[derive(Clone, Debug)]
pub(crate) struct Jmh {
    pub rgb_cam: M3,
    pub cam_rgb: M3,
    pub cone_aab: M3,
    pub aab_cone: M3,
    pub f_l_n: f32,
    pub cz: f32,
    pub inv_cz: f32,
    pub a_w_j: f32,
    inv_a_w_j: f32,
}

impl Jmh {
    pub fn new(prims: &Primaries) -> Jmh {
        let base: M3 = [[2.0, 1.0, 1.0 / 20.0], [1.0, -12.0 / 11.0, 1.0 / 11.0], [1.0 / 9.0, 1.0 / 9.0, -2.0 / 9.0]];
        let m16 = xyz_to_rgb(&CAM16);
        let rgb_xyz = rgb_to_xyz(prims);
        let xyz_w = mul(&rgb_xyz, [REF_LUM; 3]);
        let rgb_w = mul(&m16, xyz_w);
        const K: f32 = 1.0 / (5.0 * L_A + 1.0);
        const K4: f32 = K * K * K * K;
        let f_l = 0.2 * K4 * (5.0 * L_A) + 0.1 * (1.0 - K4).powf(2.0) * (5.0 * L_A).powf(1.0 / 3.0);
        let f_l_n = f_l / REF_LUM;
        let cz = model_gamma();
        let d_rgb = rgb_w.map(|w| f_l_n * xyz_w[1] / w);
        let rgb_aw: [f32; 3] = std::array::from_fn(|i| cone_fwd(d_rgb[i] * rgb_w[i]));
        let c2a = mm(&diag([NL_SCALE; 3]), &base);
        let a_w = c2a[0][0] * rgb_aw[0] + c2a[0][1] * rgb_aw[1] + c2a[0][2] * rgb_aw[2];
        let a_w_j = cone_fwd_abs(f_l);
        let rgb_cam16 = mm(&mm(&m16, &rgb_xyz), &diag([REF_LUM; 3]));
        let rgb_cam = mm(&diag(d_rgb), &rgb_cam16);
        let cone_aab = [c2a[0].map(|v| v / a_w), c2a[1].map(|v| v * 43.0 * SURROUND[2]), c2a[2].map(|v| v * 43.0 * SURROUND[2])];
        Jmh {
            rgb_cam,
            cam_rgb: invert(&rgb_cam),
            cone_aab,
            aab_cone: invert(&cone_aab),
            f_l_n,
            cz,
            inv_cz: 1.0 / cz,
            a_w_j,
            inv_a_w_j: 1.0 / a_w_j,
        }
    }

    /// RGB → Aab with the model's own input matrix, or an equivalent one folded with a gamut change.
    pub fn rgb_to_aab_with(&self, m: &M3, rgb: [f32; 3]) -> [f32; 3] {
        mul(&self.cone_aab, mul(m, rgb).map(cone_fwd))
    }
    pub fn rgb_to_aab(&self, rgb: [f32; 3]) -> [f32; 3] {
        self.rgb_to_aab_with(&self.rgb_cam, rgb)
    }
    pub fn aab_to_rgb_with(&self, m: &M3, aab: [f32; 3]) -> [f32; 3] {
        mul(m, mul(&self.aab_cone, aab).map(cone_inv))
    }
    pub fn aab_to_rgb(&self, aab: [f32; 3]) -> [f32; 3] {
        self.aab_to_rgb_with(&self.cam_rgb, aab)
    }
    pub fn a_to_j(&self, a: f32) -> f32 {
        J_SCALE * a.powf(self.cz)
    }
    pub fn j_to_a(&self, j: f32) -> f32 {
        (j * (1.0 / J_SCALE)).powf(self.inv_cz)
    }
    pub fn a_to_y(&self, a: f32) -> f32 {
        cone_inv_abs(self.a_w_j * a) / self.f_l_n
    }
    pub fn j_to_y(&self, abs_j: f32) -> f32 {
        self.a_to_y(self.j_to_a(abs_j))
    }
    pub fn y_to_j_abs(&self, abs_y: f32) -> f32 {
        self.a_to_j(cone_fwd_abs(abs_y * self.f_l_n) * self.inv_a_w_j)
    }
    pub fn y_to_j(&self, y: f32) -> f32 {
        self.y_to_j_abs(y.abs()).copysign(y)
    }
    pub fn aab_to_jmh(&self, aab: [f32; 3]) -> [f32; 3] {
        if aab[0] <= 0.0 {
            return [0.0; 3];
        }
        let h = 180.0 * aab[2].atan2(aab[1]) / PI;
        [self.a_to_j(aab[0]), (aab[1] * aab[1] + aab[2] * aab[2]).sqrt(), if h < 0.0 { h + 360.0 } else { h }]
    }
    pub fn rgb_to_jmh(&self, rgb: [f32; 3]) -> [f32; 3] {
        self.aab_to_jmh(self.rgb_to_aab(rgb))
    }
    pub fn jmh_to_aab_cs(&self, jmh: [f32; 3], cos: f32, sin: f32) -> [f32; 3] {
        [self.j_to_a(jmh[0]), jmh[1] * cos, jmh[1] * sin]
    }
    pub fn jmh_to_rgb(&self, jmh: [f32; 3]) -> [f32; 3] {
        let h = PI * jmh[2] / 180.0;
        self.aab_to_rgb(self.jmh_to_aab_cs(jmh, h.cos(), h.sin()))
    }
}
