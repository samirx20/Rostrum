//! ACES 2.0 tonescale (the Daniele Siragusano curve, applied in Y and expressed in J) and chroma
//! compression. Port of OCIO 2.5.2 ACES2 `init_ToneScaleParams`, `aces_tonescale`, `chroma_compress_*`.
use super::cam::{Jmh, REF_LUM, smax, smin};

#[derive(Clone, Copy, Debug)]
pub(crate) struct Tonescale {
    pub n: f32,
    pub n_r: f32,
    pub g: f32,
    pub t_1: f32,
    pub c_t: f32,
    pub s_2: f32,
    pub m_2: f32,
    pub forward_limit: f32,
    pub inverse_limit: f32,
    pub log_peak: f32,
}

impl Tonescale {
    pub fn new(peak: f32) -> Tonescale {
        let (n, n_r, g, c, c_d, w_g, t_1) = (peak, 100.0f32, 1.15f32, 0.18f32, 10.013f32, 0.14f32, 0.04f32);
        let (r_hit_min, r_hit_max) = (128.0f32, 896.0f32);
        let r_hit = r_hit_min + (r_hit_max - r_hit_min) * ((n / n_r).ln() / (10000.0f32 / 100.0).ln());
        let m_0 = n / n_r;
        let m_1 = 0.5 * (m_0 + (m_0 * (m_0 + 4.0 * t_1)).sqrt());
        let u = ((r_hit / m_1) / ((r_hit / m_1) + 1.0)).powf(g);
        let m = m_1 / u;
        let w_i = (n / 100.0).ln() / 2.0f32.ln();
        let c_t = c_d / n_r * (1.0 + w_i * w_g);
        let g_ip = 0.5 * (c_t + (c_t * (c_t + 4.0 * t_1)).sqrt());
        let g_ipp2 = -(m_1 * (g_ip / m).powf(1.0 / g)) / ((g_ip / m).powf(1.0 / g) - 1.0);
        let w_2 = c / g_ipp2;
        let s_2 = w_2 * m_1 * REF_LUM;
        let u_2 = ((r_hit / m_1) / ((r_hit / m_1) + w_2)).powf(g);
        let m_2 = m_1 / u_2;
        Tonescale {
            n,
            n_r,
            g,
            t_1,
            c_t,
            s_2,
            m_2,
            forward_limit: 8.0 * r_hit,
            inverse_limit: n / (u_2 * n_r),
            log_peak: (n / n_r).log10(),
        }
    }
    fn fwd_y(&self, y: f32) -> f32 {
        let f = self.m_2 * (y / (y + self.s_2)).powf(self.g);
        smax(0.0, f * f / (f + self.t_1)) * self.n_r
    }
    fn inv_y(&self, y: f32) -> f32 {
        let z = smax(0.0, smin(self.inverse_limit, y / REF_LUM));
        let f = (z + (z * (4.0 * self.t_1 + z)).sqrt()) / 2.0;
        self.s_2 / ((self.m_2 / f).powf(1.0 / self.g) - 1.0)
    }
    /// Achromatic A → tonescaled J (the forward path's `tonescale_A_to_J_fwd`).
    pub fn a_to_j(&self, a: f32, p: &Jmh) -> f32 {
        p.y_to_j_abs(self.fwd_y(p.a_to_y(a))).copysign(a)
    }
    /// Tonescaled J → scene J.
    pub fn inv_j(&self, j: f32, p: &Jmh) -> f32 {
        p.y_to_j_abs(self.inv_y(p.j_to_y(j.abs()))).copysign(j)
    }
}

#[derive(Clone, Copy, Debug)]
pub(crate) struct Chroma {
    pub sat: f32,
    pub sat_thr: f32,
    pub compr: f32,
    pub scale: f32,
}

impl Chroma {
    pub fn new(peak: f32, ts: &Tonescale) -> Chroma {
        let (cc, cc_fact, ce, ce_fact, ce_thr) = (2.4f32, 3.3f32, 1.3f32, 0.69f32, 0.5f32);
        Chroma {
            sat: smax(0.2, ce - (ce * ce_fact) * ts.log_peak),
            sat_thr: ce_thr / ts.n,
            compr: cc + (cc * cc_fact) * ts.log_peak,
            scale: (0.03379 * peak).powf(0.30596) - 0.45135,
        }
    }
}

/// The hue-dependent M normalisation (a 3-harmonic Fourier fit).
pub(crate) fn norm(c1: f32, s1: f32, scale: f32) -> f32 {
    let (c2, s2) = (2.0 * c1 * c1 - 1.0, 2.0 * c1 * s1);
    let (c3, s3) = (4.0 * c1 * c1 * c1 - 3.0 * c1, 3.0 * s1 - 4.0 * s1 * s1 * s1);
    let m = 11.34072 * c1 + 16.46899 * c2 + 7.88380 * c3 + 14.66441 * s1 + -6.37224 * s2 + 9.19364 * s3 + 77.12896;
    m * scale
}

fn toe(x: f32, limit: f32, k1_in: f32, k2_in: f32, inverse: bool) -> f32 {
    if x > limit {
        return x;
    }
    let k2 = smax(k2_in, 0.001);
    let k1 = (k1_in * k1_in + k2 * k2).sqrt();
    let k3 = (limit + k1) / (limit + k2);
    if inverse {
        return (x * x + k1 * x) / (k3 * (x + k2));
    }
    let minus_b = k3 * x - k1;
    let minus_ac = k2 * k3 * x;
    0.5 * (minus_b + (minus_b * minus_b + 4.0 * minus_ac).sqrt())
}

/// (limit J max, 1 / model gamma, reach M at this hue): `ResolvedSharedCompressionParameters`.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Shared {
    pub limit_j_max: f32,
    pub model_gamma_inv: f32,
    pub reach_max_m: f32,
}

/// `chroma_compress_fwd`: JMh (scene) → (J_ts, compressed M, h).
pub(crate) fn compress_fwd(jmh: [f32; 3], j_ts: f32, mnorm: f32, s: &Shared, c: &Chroma) -> [f32; 3] {
    let [j, m, h] = jmh;
    if m == 0.0 {
        return [j_ts, m, h];
    }
    let nj = j_ts / s.limit_j_max;
    let snj = smax(0.0, 1.0 - nj);
    let limit = nj.powf(s.model_gamma_inv) * s.reach_max_m / mnorm;
    let mut mc = m * (j_ts / j).powf(s.model_gamma_inv) / mnorm;
    mc = limit - toe(limit - mc, limit - 0.001, snj * c.sat, (nj * nj + c.sat_thr).sqrt(), false);
    mc = toe(mc, limit, nj * c.compr, snj, false);
    [j_ts, mc * mnorm, h]
}

/// `chroma_compress_inv`: (J_ts, compressed M, h) with the scene J → JMh (scene).
pub(crate) fn compress_inv(jmh: [f32; 3], j: f32, mnorm: f32, s: &Shared, c: &Chroma) -> [f32; 3] {
    let [j_ts, mc, h] = jmh;
    if mc == 0.0 {
        return [j, mc, h];
    }
    let nj = j_ts / s.limit_j_max;
    let snj = smax(0.0, 1.0 - nj);
    let limit = nj.powf(s.model_gamma_inv) * s.reach_max_m / mnorm;
    let mut m = toe(mc / mnorm, limit, nj * c.compr, snj, true);
    m = limit - toe(limit - m, limit - 0.001, snj * c.sat, (nj * nj + c.sat_thr).sqrt(), true);
    [j, m * mnorm * (j_ts / j).powf(-s.model_gamma_inv), h]
}
