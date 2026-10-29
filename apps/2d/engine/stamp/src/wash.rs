//! A wash's drying, the per-pixel parts (the kit's `marks._noise`, `wash._blur`, `wash._upsample`), in numpy's
//! precision and order: f32 where numpy keeps f32, f64 where it mixes f32 with int64 (the upsample's weights). Each
//! output pixel is worked out alone, so rows are split over threads without changing a number.

/// Rows worked out per thread at least (smaller jobs stay on the calling thread).
const BAND: usize = 64;

/// Splits `out` (rows of `w`) over up to 8 threads; `f(y, row)` fills row y.
fn rows<F: Fn(usize, &mut [f32]) + Sync>(out: &mut [f32], w: usize, f: F) {
    let h = if w == 0 { 0 } else { out.len() / w };
    let n = (h * w / (BAND * 1024)).clamp(1, 8).min(h.max(1));
    if n <= 1 {
        for (y, row) in out.chunks_exact_mut(w.max(1)).enumerate() {
            f(y, row);
        }
        return;
    }
    let per = h.div_ceil(n);
    std::thread::scope(|s| {
        for (k, part) in out.chunks_mut(per * w).enumerate() {
            let f = &f;
            s.spawn(move || {
                for (i, row) in part.chunks_exact_mut(w).enumerate() {
                    f(k * per + i, row);
                }
            });
        }
    });
}

/// marks._knots: the value-noise knot at lattice point (ky, kx); `seedsalt` = seed * 0x9E3779B1 + salt * 0x85EBCA6B
/// (only its low 32 bits count). numpy's int64 products wrap; their low 32 bits are these.
fn knot(seedsalt: u64, ky: i64, kx: i64) -> f32 {
    let mut h = (kx.wrapping_mul(0x27D4EB2D).wrapping_add(ky.wrapping_mul(0x165667B1)) as u64).wrapping_add(seedsalt) & 0xFFFF_FFFF;
    for (mul, shift) in [(0x2C1B3C6Du64, 12), (0x297A2D39, 15)] {
        h ^= h >> 15;
        h = h.wrapping_mul(mul) & 0xFFFF_FFFF;
        h ^= h >> shift;
    }
    (h as f64 / 4294967296.0) as f32
}

/// marks._cubic for one sample: its lattice cell and Catmull-Rom weights (f32, numpy's steps).
fn cubic(u: f64) -> (i64, [f32; 4]) {
    let i = u.floor();
    let t = (u - i) as f32;
    let (t2, t3) = (t * t, t * t * t);
    let w = [
        (-t3 + 2.0 * t2 - t) / 2.0,
        (3.0 * t3 - 5.0 * t2 + 2.0) / 2.0,
        (-3.0 * t3 + 4.0 * t2 + t) / 2.0,
        (t3 - t2) / 2.0,
    ];
    (i as i64, w)
}

/// marks._noise into `out` (h×w): sample x at u = (x - ox) / div_x (f64), y likewise; `nk` the knots across and down
/// on a seamless canvas (they repeat), 0 0 otherwise.
#[allow(clippy::too_many_arguments)]
pub fn noise(out: &mut [f32], h: usize, w: usize, o: [f64; 2], div: [f64; 2], seedsalt: u64, nk: [i64; 2]) {
    if h == 0 || w == 0 {
        return;
    }
    let xs: Vec<(i64, [f32; 4])> = (0..w).map(|x| cubic((x as f64 - o[0]) / div[0])).collect();
    let ys: Vec<(i64, [f32; 4])> = (0..h).map(|y| cubic((y as f64 - o[1]) / div[1])).collect();
    let span = |c: &[(i64, [f32; 4])]| (c.iter().map(|v| v.0).min().unwrap() - 1, c.iter().map(|v| v.0).max().unwrap());
    let ((kx0, kx_max), (ky0, ky_max)) = (span(&xs), span(&ys));
    let (nx, ny) = ((kx_max - kx0 + 3) as usize, (ky_max - ky0 + 3) as usize);
    let wrap = |k: i64, n: i64| if n > 0 { k.rem_euclid(n) } else { k };
    let mut g = vec![0f32; nx * ny];
    for r in 0..ny {
        let ky = wrap(ky0 + r as i64, nk[1]);
        for c in 0..nx {
            g[r * nx + c] = knot(seedsalt, ky, wrap(kx0 + c as i64, nk[0]));
        }
    }
    // the knot rows across first (numpy's `rows`, every knot row), then down
    let mut across = vec![0f32; ny * w];
    rows(&mut across, w, |r, row| {
        let gr = &g[r * nx..(r + 1) * nx];
        for (x, v) in row.iter_mut().enumerate() {
            let (i, wx) = xs[x];
            let c = (i - kx0 - 1) as usize;
            let mut s = 0.0f32;
            for j in 0..4 {
                s += gr[c + j] * wx[j];
            }
            *v = s;
        }
    });
    rows(out, w, |y, row| {
        let (i, wy) = ys[y];
        let r = (i - ky0 - 1) as usize;
        row.fill(0.0);
        for j in 0..4 {
            let src = &across[(r + j) * w..(r + j + 1) * w];
            for (v, &a) in row.iter_mut().zip(src) {
                *v += a * wy[j];
            }
        }
        for v in row.iter_mut() {
            *v = v.max(0.0).min(1.0);
        }
    });
}

/// wash._blur: a box 2r+1 wide down then across, zero outside, each pixel's sum in the window's order from its top /
/// left, then / (2r+1) (f32). The zeros outside are not added: a sum that starts at +0 is the same with or without
/// adding +0.
pub fn blur(a: &[f32], out: &mut [f32], h: usize, w: usize, r: usize) {
    if h == 0 || w == 0 {
        return;
    }
    let n = (2 * r + 1) as f32;
    let mut down = vec![0f32; h * w];
    rows(&mut down, w, |y, row| {
        row.fill(0.0);
        for k in 0..2 * r + 1 {
            if let Some(s) = (y + k).checked_sub(r).filter(|&s| s < h) {
                for (v, &q) in row.iter_mut().zip(&a[s * w..(s + 1) * w]) {
                    *v += q;
                }
            }
        }
        for v in row.iter_mut() {
            *v /= n;
        }
    });
    rows(out, w, |y, row| {
        let src = &down[y * w..(y + 1) * w];
        row.fill(0.0);
        for k in 0..2 * r + 1 {
            // row[x] += src[x + k - r] where that is inside
            let (x0, s0) = if k >= r { (0, k - r) } else { (r - k, 0) };
            if x0 >= w || s0 >= w {
                continue;
            }
            let m = (w - x0).min(w - s0);
            for (v, &q) in row[x0..x0 + m].iter_mut().zip(&src[s0..s0 + m]) {
                *v += q;
            }
        }
        for v in row.iter_mut() {
            *v /= n;
        }
    });
}

/// wash._upsample: a coarse grid (`hc`×`wc`, one sample per f px, sample k at px (k + at) * f) up to h×w, bilinear:
/// the places in f32, the weights and the blend in f64 (numpy mixes f32 with int64 there), cast back to f32.
#[allow(clippy::too_many_arguments)]
pub fn upsample(small: &[f32], hc: usize, wc: usize, f: usize, at: f64, out: &mut [f32], h: usize, w: usize) {
    if h == 0 || w == 0 || hc == 0 || wc == 0 {
        return;
    }
    let (ff, at) = (f as f32, at as f32);
    let place = |i: usize, n: usize| -> (usize, usize, f64) {
        let s = (i as f32 + 0.5f32) / ff - at;
        let i0 = (s.floor() as i64).clamp(0, n as i64 - 1);
        let i1 = (i0 + 1).min(n as i64 - 1);
        (i0 as usize, i1 as usize, (s as f64 - i0 as f64).clamp(0.0, 1.0))
    };
    let xs: Vec<(usize, usize, f64)> = (0..w).map(|x| place(x, wc)).collect();
    rows(out, w, |y, row| {
        let (y0, y1, wy) = place(y, hc);
        let (a, b) = (&small[y0 * wc..(y0 + 1) * wc], &small[y1 * wc..(y1 + 1) * wc]);
        let across: Vec<f64> = a.iter().zip(b).map(|(&p, &q)| p as f64 * (1.0 - wy) + q as f64 * wy).collect();
        for (v, &(x0, x1, wx)) in row.iter_mut().zip(&xs) {
            *v = (across[x0] * (1.0 - wx) + across[x1] * wx) as f32;
        }
    });
}

/// Splits `n` pixels into runs for up to 8 threads; `f(start, end)` works out pixels start..end.
fn spans<F: Fn(usize, usize) + Sync>(n: usize, f: F) {
    let t = (n / (BAND * 1024)).clamp(1, 8);
    if t <= 1 {
        f(0, n);
        return;
    }
    let per = n.div_ceil(t);
    std::thread::scope(|s| {
        for k in 0..t {
            let f = &f;
            s.spawn(move || f(k * per, ((k + 1) * per).min(n)));
        }
    });
}

/// A pointer shared by the threads of `spans`, each writing its own pixels.
#[derive(Clone, Copy)]
struct Out(*mut f32);
unsafe impl Send for Out {}
unsafe impl Sync for Out {}

/// np.clip(x, lo, hi) on f32: the maximum, then the minimum.
fn clip(x: f32, lo: f32, hi: f32) -> f32 {
    x.max(lo).min(hi)
}

/// marks._ss: a smooth step of x clipped to 0..1, x * x * (3 - 2 * x) in f32.
fn ss(x: f32) -> f32 {
    let x = clip(x, 0.0, 1.0);
    x * x * (3.0 - 2.0 * x)
}

/// The per-pixel steps of wash.dry, one effect a call, in its numpy expression's order (f32; the strengths `k` are
/// the NumPy f32 scalars the Python makes). `f` the fields read, `out` the ones added to or written (n pixels each):
/// 0 edge: f a, blur(a, thin), blur(a, edge), along noise; k strength; out deep (+=)
/// 1 granulation: f a, grain, clump noise; k strength; out deep (+=)
/// 2 pooling: f a, noise; k strength; out deep (+=)
/// 3 bloom's wet: f a, wide blur of a, noise; out wet (=)
/// 4 bloom: f wet, blur(wet), noise, strong noise; k amount; out light (+=), deep (+=)
///
/// # Safety
/// Every pointer of `f` and `out` the call reads points at `n` f32; `out`'s arrays are not among `f`'s.
pub unsafe fn mix(kind: u32, n: usize, k: f32, f: &[*const f32], out: &[*mut f32]) -> bool {
    let need = [(4, 1), (3, 1), (2, 1), (3, 1), (4, 2)];
    let Some(&(nf, no)) = need.get(kind as usize) else { return false };
    if f.len() < nf || out.len() < no || f[..nf].iter().any(|p| p.is_null()) || out[..no].iter().any(|p| p.is_null()) {
        return false;
    }
    let fs: Vec<&[f32]> = f[..nf].iter().map(|&p| std::slice::from_raw_parts(p, n)).collect();
    let os: Vec<Out> = out[..no].iter().map(|&p| Out(p)).collect();
    spans(n, |s, e| {
        let o0 = std::slice::from_raw_parts_mut(os[0].0.add(s), e - s);
        let fd = |j: usize| &fs[j][s..e];
        match kind {
            0 => {
                let (a, b1, b2, nz) = (fd(0), fd(1), fd(2), fd(3));
                for i in 0..e - s {
                    let thin = clip(a[i] - b1[i], 0.0, 1.0);
                    let e = 1.6f32 * thin + 0.7f32 * clip(a[i] - b2[i], 0.0, 1.0);
                    let along = clip(0.25f32 + 1.3f32 * (nz[i] - 0.25f32), 0.15, 1.25);
                    o0[i] += k * e * along;
                }
            }
            1 => {
                let (a, g, clump) = (fd(0), fd(1), fd(2));
                for i in 0..e - s {
                    let gr = clip((0.62f32 - g[i]) / 0.62f32 * 2.0f32, 0.0, 1.0) * ss((clump[i] - 0.3f32) / 0.5f32);
                    o0[i] += k * a[i] * gr;
                }
            }
            2 => {
                let (a, nz) = (fd(0), fd(1));
                for i in 0..e - s {
                    o0[i] += k * a[i] * ss((nz[i] - 0.42f32) / 0.3f32);
                }
            }
            3 => {
                let (a, wide, nz) = (fd(0), fd(1), fd(2));
                for i in 0..e - s {
                    let spread = clip(wide[i] * 2.0f32, 0.0, 1.0);
                    let front = clip(0.05f32 + 1.1f32 * (1.0f32 - nz[i]) - 0.2f32, 0.04, 0.95);
                    o0[i] = ss((spread - front) / 0.08f32) * (1.0f32 - a[i]);
                }
            }
            _ => {
                let o1 = std::slice::from_raw_parts_mut(os[1].0.add(s), e - s);
                let (wet, bw, nz, n7) = (fd(0), fd(1), fd(2), fd(3));
                let (kl, kd) = (k * 0.45f32, k * 1.8f32);
                for i in 0..e - s {
                    let rim = clip(wet[i] - bw[i], 0.0, 1.0);
                    let strong = ss((n7[i] - 0.3f32) / 0.4f32);
                    o0[i] += kl * wet[i] * (0.6f32 + 0.4f32 * nz[i]);
                    o1[i] += kd * rim * strong;
                }
            }
        }
    });
    true
}
