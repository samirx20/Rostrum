//! ACES 2.0 gamut compression: M is compressed along a line towards a focus point on the J axis, from
//! the reach gamut (AP1 at the limit J) into the limiting display gamut's hull (cusp + two gammas).
//! Port of OCIO 2.5.2 ACES2 `compressGamut`, `gamut_compress_fwd` / `_inv` and their helpers.
use super::cam::{lerp, smax, smin};
use super::tables::Gamut;
use super::tonescale::Shared;

const SMOOTH_CUSPS: f32 = 0.12;
const CUSP_MID_BLEND: f32 = 1.3;
pub(crate) const FOCUS_GAIN_BLEND: f32 = 0.3;
const COMPRESSION_THRESHOLD: f32 = 0.75;

/// The hull at one hue (`HueDependantGamutParams`).
pub(crate) struct Hull {
    pub gamma_bottom_inv: f32,
    pub cusp: [f32; 2],
    pub gamma_top_inv: f32,
    pub focus_j: f32,
    pub threshold: f32,
}

pub(crate) fn focus_j(cusp_j: f32, mid_j: f32, limit_j_max: f32) -> f32 {
    lerp(cusp_j, mid_j, smin(1.0, CUSP_MID_BLEND - (cusp_j / limit_j_max)))
}

pub(crate) fn focus_gain(j: f32, threshold: f32, limit_j_max: f32, focus_dist: f32) -> f32 {
    let mut gain = limit_j_max * focus_dist;
    if j > threshold {
        let adj = ((limit_j_max - threshold) / smax(0.0001, limit_j_max - j)).log10();
        gain *= adj * adj + 1.0;
    }
    gain
}

pub(crate) fn solve_j_intersect(j: f32, m: f32, focus_j: f32, max_j: f32, slope_gain: f32) -> f32 {
    let m_scaled = m / slope_gain;
    let a = m_scaled / focus_j;
    if j < focus_j {
        let b = 1.0 - m_scaled;
        let c = -j;
        let root = (b * b - 4.0 * a * c).sqrt();
        -2.0 * c / (b + root)
    } else {
        let b = -(1.0 + m_scaled + max_j * a);
        let c = max_j * m_scaled + j;
        let root = (b * b - 4.0 * a * c).sqrt();
        -2.0 * c / (b - root)
    }
}

pub(crate) fn slope(intersect_j: f32, focus_j: f32, limit_j_max: f32, slope_gain: f32) -> f32 {
    let dir = if intersect_j < focus_j { intersect_j } else { limit_j_max - intersect_j };
    dir * (intersect_j - focus_j) / (focus_j * slope_gain)
}

pub(crate) fn line_boundary_m(j_axis: f32, slope: f32, inv_gamma: f32, j_max: f32, m_max: f32, j_ref: f32) -> f32 {
    let shifted = j_ref * (j_axis / j_ref).powf(inv_gamma);
    shifted * m_max / (j_max - slope * m_max)
}

fn smin_scaled(a: f32, b: f32, reference: f32) -> f32 {
    let s = SMOOTH_CUSPS * reference;
    let h = smax(s - (a - b).abs(), 0.0) / s;
    smin(a, b) - h * h * h * s * (1.0 / 6.0)
}

pub(crate) fn boundary(cusp: [f32; 2], j_max: f32, g_top_inv: f32, g_bot_inv: f32, j_src: f32, slope: f32, j_cusp: f32) -> f32 {
    let lower = line_boundary_m(j_src, slope, g_bot_inv, cusp[0], cusp[1], j_cusp);
    let upper = line_boundary_m(j_max - j_src, -slope, g_top_inv, j_max - cusp[0], cusp[1], j_max - j_cusp);
    smin_scaled(lower, upper, cusp[1])
}

fn remap_m(m: f32, gamut_m: f32, reach_m: f32, invert: bool) -> f32 {
    let proportion = smax(gamut_m / reach_m, COMPRESSION_THRESHOLD);
    let threshold = proportion * gamut_m;
    if m <= threshold || proportion >= 1.0 {
        return m;
    }
    let (m_off, g_off, r_off) = (m - threshold, gamut_m - threshold, reach_m - threshold);
    let scale = r_off / ((r_off / g_off) - 1.0);
    let nd = m_off / scale;
    threshold
        + if !invert {
            scale * nd / (1.0 + nd)
        } else if nd >= 1.0 {
            scale
        } else {
            scale * -(nd / (nd - 1.0))
        }
}

fn compress(jmh: [f32; 3], jx: f32, s: &Shared, g: &Gamut, hd: &Hull, invert: bool) -> [f32; 3] {
    let [j, m, h] = jmh;
    let gain = focus_gain(jx, hd.threshold, s.limit_j_max, g.focus_dist);
    let j_src = solve_j_intersect(j, m, hd.focus_j, s.limit_j_max, gain);
    let sl = slope(j_src, hd.focus_j, s.limit_j_max, gain);
    let j_cusp = solve_j_intersect(hd.cusp[0], hd.cusp[1], hd.focus_j, s.limit_j_max, gain);
    let gamut_m = boundary(hd.cusp, s.limit_j_max, hd.gamma_top_inv, hd.gamma_bottom_inv, j_src, sl, j_cusp);
    if gamut_m <= 0.0 {
        return [j, 0.0, h];
    }
    let reach_m = line_boundary_m(j_src, sl, s.model_gamma_inv, s.limit_j_max, s.reach_max_m, s.limit_j_max);
    let mr = remap_m(m, gamut_m, reach_m, invert);
    [j_src + mr * sl, mr, h]
}

pub(crate) fn compress_fwd(jmh: [f32; 3], s: &Shared, g: &Gamut) -> [f32; 3] {
    let [j, m, h] = jmh;
    if j <= 0.0 {
        return [0.0, 0.0, h];
    }
    if m <= 0.0 || j > s.limit_j_max {
        return [j, 0.0, h];
    }
    compress(jmh, j, s, g, &g.hull(h, s.limit_j_max), false)
}

pub(crate) fn compress_inv(jmh: [f32; 3], s: &Shared, g: &Gamut) -> [f32; 3] {
    let [j, m, h] = jmh;
    if j <= 0.0 {
        return [0.0, 0.0, h];
    }
    if m <= 0.0 || j > s.limit_j_max {
        return [j, 0.0, h];
    }
    let hd = g.hull(h, s.limit_j_max);
    // Above the threshold the focus gain depends on the (unknown) source J: one approximation step.
    let jx = if j > hd.threshold { compress(jmh, j, s, g, &hd, true)[0] } else { j };
    compress(jmh, jx, s, g, &hd, true)
}
