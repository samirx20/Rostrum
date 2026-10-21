//! The comp's spatial steps on the CPU, as the renderer runs them (Skia image filters behind the SVG primitives):
//! `blur` = feGaussianBlur `stdDeviation` σ px (outside the picture is transparent, so a blurred opaque matte fades at
//! the frame's border and is renormalised after: the `norm` program), `shrink` = the matte's erode / dilate over a disc
//! of radius r px (morph.rs, the `matteMorph` program's twin). Pictures are row-major `[r, g, b, a]`, premultiplied or
//! opaque grey mattes.
use super::morph::morph;

/// A 1D kernel: weights from offset `-left`.
struct Kernel {
    w: Vec<f32>,
    left: isize,
}

/// The sampled Gaussian for σ, 3σ each side (at least one tap), normalised.
fn gaussian(sigma: f32) -> Kernel {
    let r = (3.0 * sigma).ceil().max(1.0) as i32;
    let k: Vec<f32> = (-r..=r).map(|i| (-((i * i) as f32) / (2.0 * sigma * sigma)).exp()).collect();
    let sum: f32 = k.iter().sum();
    Kernel { w: k.into_iter().map(|v| v / sum).collect(), left: r as isize }
}

/// One pass along x or y: transparent beyond the picture.
fn pass(src: &[[f32; 4]], w: usize, h: usize, k: &Kernel, along_x: bool) -> Vec<[f32; 4]> {
    let mut out = vec![[0f32; 4]; w * h];
    for y in 0..h {
        for x in 0..w {
            let mut acc = [0f32; 4];
            for (j, kv) in k.w.iter().enumerate() {
                let o = j as isize - k.left;
                let (sx, sy) = if along_x { (x as isize + o, y as isize) } else { (x as isize, y as isize + o) };
                if sx < 0 || sy < 0 || sx >= w as isize || sy >= h as isize {
                    continue;
                }
                let p = src[sy as usize * w + sx as usize];
                for c in 0..4 {
                    acc[c] += kv * p[c];
                }
            }
            out[y * w + x] = acc;
        }
    }
    out
}

/// feGaussianBlur of σ px (σ ≤ 0: the picture as is): the sampled Gaussian at full rate. The renderer agrees within
/// 1e-3 up to σ 3; above σ 4 Skia (and anyrender_skia above σ 8) blurs a scaled-down picture, which stays within a
/// mean of 2–4e-3 (max 1–3e-2 at hard edges) of this (comp_tests.rs `blur_and_morphology_match_spatial`, measured).
pub fn blur(src: &[[f32; 4]], w: usize, h: usize, sigma: f32) -> Vec<[f32; 4]> {
    if sigma <= 0.0 {
        return src.to_vec();
    }
    let k = gaussian(sigma);
    pass(&pass(src, w, h, &k, true), w, h, &k, false)
}

/// A matte's erode by `r` px when r > 0, dilate by −r when r < 0 (the key's `erode` and `despot`, the matte's `grow`
/// with the sign flipped): the `matteMorph` program's twin (morph.rs), a **disc** of radius r with an antialiased rim,
/// not feMorphology's square. Outside the picture never counts (clamp to edge), so the frame's border is not eaten.
pub fn shrink(src: &[[f32; 4]], w: usize, h: usize, r: f32) -> Vec<[f32; 4]> {
    if r < 0.0 { morph(src, w, h, -r, false) } else { morph(src, w, h, r, true) }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blur_keeps_a_flat_interior_and_fades_at_the_border() {
        let (w, h) = (20, 12);
        let img = vec![[0.5, 0.5, 0.5, 1.0]; w * h];
        let b = blur(&img, w, h, 1.5);
        assert!((b[6 * w + 10][3] - 1.0).abs() < 1e-5);
        assert!(b[0][3] < 0.8 && b[0][3] > 0.2);
        // a ≤ 1: the ratio colour / alpha is the matte's value everywhere (what `norm` divides out).
        assert!((b[0][0] / b[0][3] - 0.5).abs() < 1e-5);
    }

    #[test]
    fn open_removes_a_speck_and_close_fills_a_hole() {
        let (w, h) = (9, 9);
        let mut img = vec![[0f32; 4]; w * h];
        img[4 * w + 4] = [1.0; 4];
        let open = shrink(&shrink(&img, w, h, 1.0), w, h, -1.0);
        assert!(open.iter().all(|p| p[0] == 0.0));
        let mut full = vec![[1f32; 4]; w * h];
        full[4 * w + 4] = [0.0; 4];
        let close = shrink(&shrink(&full, w, h, -1.0), w, h, 1.0);
        assert_eq!(close[4 * w + 4][0], 1.0);
        // Outside never counts: the border stays.
        assert_eq!(close[0][0], 1.0);
    }
}
