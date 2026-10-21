//! The per-hue tables ACES 2.0 precomputes once per target: the reach gamut's M at the limit J, the
//! limiting gamut's cusp (J, M) on a hue table that hits every gamut corner exactly, and the upper hull
//! gamma fitted per hue. Port of OCIO 2.5.2 ACES2 `make_reach_m_table`, `make_uniform_hue_gamut_table`,
//! `make_upper_hull_gamma` and `lookup_hue_interval`, step for step (360 nominal entries, 1 lower and
//! 2 upper wrap entries).
use super::cam::{Jmh, lerp};
use super::gamut::{self, FOCUS_GAIN_BLEND, Hull};

pub(crate) const N: usize = 363;
const SMOOTH_M: f32 = 0.27;
const SMOOTH_CUSPS: f32 = 0.12;

pub(crate) struct Gamut {
    pub mid_j: f32,
    pub focus_dist: f32,
    pub lower_gamma_inv: f32,
    range: [i32; 2],
    pub hues: [f32; N],
    /// (cusp J, cusp M, upper hull 1/gamma) per hue-table entry.
    pub cusp: [[f32; 3]; N],
}

fn wrap<T: Copy>(t: &mut [T; N]) {
    (t[0], t[361], t[362]) = (t[360], t[1], t[2]);
}

/// M of the reach gamut (AP1) at J = limit_j_max, per whole degree (`make_reach_m_table`).
pub(crate) fn reach_table(p: &Jmh, limit_j_max: f32) -> [f32; N] {
    let mut t = [0.0f32; N];
    let outside = |m: f32, h: f32| p.jmh_to_rgb([limit_j_max, m, h]).iter().any(|&c| c < 0.0);
    for i in 0..360 {
        let h = i as f32;
        let (mut lo, mut hi, mut out) = (0.0f32, 50.0f32, false);
        while !out && hi < 1300.0 {
            out = outside(hi, h);
            if !out {
                (lo, hi) = (hi, hi + 50.0);
            }
        }
        while hi - lo > 1e-2 {
            let m = (hi + lo) / 2.0;
            if outside(m, h) { hi = m } else { lo = m }
        }
        t[i + 1] = hi;
    }
    wrap(&mut t);
    t
}

pub(crate) fn reach_at(t: &[f32; N], h: f32) -> f32 {
    let base = h as u32;
    let i = base as usize + 1;
    lerp(t[i], t[i + 1], h - base as f32)
}

fn corner(c: usize) -> [f32; 3] {
    [((c + 1) % 6 < 3) as u32 as f32, ((c + 5) % 6 < 3) as u32 as f32, ((c + 3) % 6 < 3) as u32 as f32]
}

/// The six cube corners as a hue-sorted cycle, lowest hue at [1], wrapped at [0] and [7].
fn cycle(rgb: [[f32; 3]; 6], jmh: [[f32; 3]; 6]) -> ([[f32; 3]; 8], [[f32; 3]; 8]) {
    let k = (0..6).fold(0, |m, i| if jmh[i][2] < jmh[m][2] { i } else { m });
    let (mut r, mut j) = ([[0.0; 3]; 8], [[0.0; 3]; 8]);
    for i in 0..6 {
        (r[i + 1], j[i + 1]) = (rgb[(i + k) % 6], jmh[(i + k) % 6]);
    }
    (r[0], r[7], j[0], j[7]) = (r[6], r[1], j[6], j[1]);
    (j[0][2], j[7][2]) = (j[0][2] - 360.0, j[7][2] + 360.0);
    (r, j)
}

fn hue_table(sorted: &[f32]) -> [f32; N] {
    let n = sorted.len();
    let mut count = [0u32; 14];
    let (mut last, mut min_i) = (u32::MAX, if sorted[0] == 0.0 { 0 } else { 1 });
    for k in 0..n {
        let mut idx = (sorted[k].round() as u32).max(min_i).min(359);
        if last == idx {
            if k > 1 && count[k - 2] != count[k - 1].wrapping_sub(1) {
                count[k - 1] = count[k - 1].wrapping_sub(1);
            } else {
                idx += 1;
            }
        }
        count[k] = idx.min(359);
        (last, min_i) = (idx, idx);
    }
    let mut t = [0.0f32; N];
    let mut fill = |samples: u32, lo: f32, hi: f32, base: u32| {
        let d = (hi - lo) / samples as f32;
        (0..samples).for_each(|i| t[(base + i) as usize] = lo + i as f32 * d);
    };
    fill(count[0], 0.0, sorted[0], 1);
    let mut total = count[0];
    for k in 1..n {
        fill(count[k] - count[k - 1], sorted[k - 1], sorted[k], total + 1);
        total += count[k] - count[k - 1];
    }
    fill(360 - total, sorted[n - 1], 360.0, total + 1);
    (t[0], t[361], t[362]) = (t[360] - 360.0, t[1] + 360.0, t[2] + 360.0);
    t
}

/// Bisect along the cube edge between two corners for the display cusp at `hue`.
fn display_cusp(hue: f32, r: &[[f32; 3]; 8], j: &[[f32; 3]; 8], p: &Jmh, prev: &mut [f32; 2]) -> [f32; 2] {
    let up = (1..8).find(|&i| j[i][2] > hue).unwrap_or(1);
    let lo = up - 1;
    if j[lo][2] == hue {
        return [j[lo][0], j[lo][1]];
    }
    let at = |t: f32| p.rgb_to_jmh(std::array::from_fn(|k| lerp(r[lo][k], r[up][k], t)));
    let (mut lt, mut ut) = (if up as f32 == prev[0] { prev[1] } else { 0.0 }, 1.0f32);
    while ut - lt > 1e-7 {
        let t = (lt + ut) / 2.0;
        let h = at(t)[2];
        if h < j[lo][2] || (h < j[up][2] && h > hue) { ut = t } else { lt = t }
    }
    let t = (lt + ut) / 2.0;
    *prev = [up as f32, t];
    let jmh = at(t);
    [jmh[0], jmh[1]]
}

/// `make_uniform_hue_gamut_table` + `determine_hue_linearity_search_range` + `make_upper_hull_gamma`.
pub(crate) fn gamut(peak: f32, reach: &Jmh, limit: &Jmh, limit_j_max: f32, fwd_limit: f32, mid_j: f32, focus_dist: f32,
                    lower_gamma_inv: f32) -> Gamut {
    let reach_a = reach.j_to_a(limit_j_max);
    let reach_jmh: [[f32; 3]; 6] = std::array::from_fn(|i| {
        let (mut lo, mut hi) = (0.0f32, fwd_limit);
        while hi - lo > 1e-3 {
            let t = (lo + hi) / 2.0;
            let a = reach.rgb_to_aab(corner(i).map(|c| t * c))[0];
            if a < reach_a { lo = t } else { hi = t }
            if a == reach_a {
                break;
            }
        }
        reach.rgb_to_jmh(corner(i).map(|c| hi * c))
    });
    let (_, rj) = cycle([[0.0; 3]; 6], reach_jmh);
    let lim_rgb: [[f32; 3]; 6] = std::array::from_fn(|i| corner(i).map(|c| peak / 100.0 * c));
    let (lr, lj) = cycle(lim_rgb, lim_rgb.map(|c| limit.rgb_to_jmh(c)));
    let (mut sorted, mut a, mut b) = (Vec::new(), 1, 1);
    while a < 7 || b < 7 {
        let (x, y) = (rj[a][2], lj[b][2]);
        sorted.push(if x <= y { x } else { y });
        (a, b) = (a + (x <= y) as usize, b + (y <= x) as usize);
    }
    let hues = hue_table(&sorted);
    let (mut cusp, mut prev) = ([[0.0f32; 3]; N], [0.0f32; 2]);
    for i in 1..361 {
        let jm = display_cusp(hues[i], &lr, &lj, limit, &mut prev);
        cusp[i] = [jm[0], jm[1] * (1.0 + SMOOTH_M * SMOOTH_CUSPS), hues[i]];
    }
    wrap(&mut cusp);
    (cusp[0][2], cusp[361][2], cusp[362][2]) = (hues[0], hues[361], hues[362]);
    let mut range = [0i32, 1];
    for (i, c) in cusp.iter().enumerate().take(361).skip(1) {
        let delta = i as i32 - (1 + c[2] as u32) as i32;
        range = [range[0].min(delta), range[1].max(delta + 1)];
    }
    let mut g = Gamut { mid_j, focus_dist, lower_gamma_inv, range, hues, cusp };
    for i in 1..361 {
        g.cusp[i][2] = 1.0 / super::hull_gamma::fit(&g, i, peak, limit_j_max, limit);
    }
    (g.cusp[0][2], g.cusp[361][2], g.cusp[362][2]) = (g.cusp[360][2], g.cusp[1][2], g.cusp[2][2]);
    g
}

impl Gamut {
    /// The hull at hue `h` (`init_HueDependantGamutParams`).
    pub fn hull(&self, h: f32, limit_j_max: f32) -> Hull {
        let mut i = 1 + h as u32;
        let mut lo = (i as i32 + self.range[0]).max(0) as u32;
        let mut hi = (i as i32 + self.range[1]).min(361) as u32;
        while lo + 1 < hi {
            if h > self.hues[i as usize] { lo = i } else { hi = i }
            i = (lo + hi) / 2;
        }
        let hi = hi.max(1) as usize;
        let t = (h - self.hues[hi - 1]) / (self.hues[hi] - self.hues[hi - 1]);
        let c: [f32; 3] = std::array::from_fn(|k| lerp(self.cusp[hi - 1][k], self.cusp[hi][k], t));
        Hull {
            gamma_bottom_inv: self.lower_gamma_inv,
            cusp: [c[0], c[1]],
            gamma_top_inv: c[2],
            focus_j: gamut::focus_j(c[0], self.mid_j, limit_j_max),
            threshold: lerp(c[0], limit_j_max, FOCUS_GAIN_BLEND),
        }
    }
}
