//! RGBA8 (straight alpha) → NV12 for the MP4 encoder (encode_mp4.rs): BT.709, limited range (Y 16–235, Cb Cr 16–240).
//! Alpha is composited over black (an MP4 has no transparency); each 2×2 block shares one Cb Cr, the average of its
//! four pixels; rows of 2×2 blocks are split across the cores. The values stay as the comp's display picture encodes them (no transfer change), as the old ffmpeg path did.
//!
//! Integer maths only, so the GPU's NV12 pass (gpu_output.glsl LUMA / CHROMA, its constants from `glsl_defines`) gives
//! the same bytes bit for bit: each channel over black rounds to a code first (exact when opaque), then fixed point
//! with 24 fraction bits, rounded once. 32-bit wrapping sums: every result fits, so the order of the terms is free.

/// Fraction bits of the coefficients.
const S: u32 = 24;
/// Y = (Y0 + YR r + YG g + YB b) >> S: 219/255 × (Kr, Kg, Kb) in fixed point, YG making the three sum to 219/255 exactly
/// as rounded (white is 235). Kr 0.2126, Kb 0.0722.
const YR: u32 = 3063283;
const YG: u32 = 10305079;
const YB: u32 = 1040306;
const Y0: u32 = (16 << S) + (1 << (S - 1));
/// Cb, Cr from the sums of a block's four pixels: 224/255/4 × the BT.709 rows, the middle term making each row sum to
/// zero (grey is 128).
const CBR: u32 = 422130;
const CBG: u32 = 1420074;
const CBB: u32 = 1842204;
const CRR: u32 = 1842204;
const CRG: u32 = 1673285;
const CRB: u32 = 168919;
const C0: u32 = (128 << S) + (1 << (S - 1));

/// The constants for the GPU's NV12 pass, as GLSL defines.
pub fn glsl_defines() -> String {
    let all = [("FRAC", S), ("YR", YR), ("YG", YG), ("YB", YB), ("Y0", Y0), ("CBR", CBR), ("CBG", CBG), ("CBB", CBB), ("CRR", CRR), ("CRG", CRG), ("CRB", CRB), ("C0", C0)];
    all.iter().map(|(n, v)| format!("#define {n} {v}u\n")).collect()
}

/// `rgba` is w×h×4 bytes; `out` is w×h×3/2: the Y plane, then the Cb Cr pairs at half size (row stride w). w, h even.
/// Pairs of rows are split across the cores (each output byte depends only on its own 2×2 block, so the bytes are the same
/// whatever the split).
pub fn from_rgba(rgba: &[u8], w: usize, h: usize, out: &mut [u8]) {
    let (luma, chroma) = out.split_at_mut(w * h);
    let threads = std::thread::available_parallelism().map(|n| n.get()).unwrap_or(4).min(8);
    let pairs = (h / 2).div_ceil(threads).max(1); // row pairs per thread
    std::thread::scope(|s| {
        let parts = luma.chunks_mut(pairs * 2 * w).zip(chroma.chunks_mut(pairs * w)).zip(rgba.chunks(pairs * 2 * w * 4));
        for ((l, c), src) in parts {
            s.spawn(move || {
                for ((rows, ys), cs) in src.chunks_exact(w * 8).zip(l.chunks_exact_mut(w * 2)).zip(c.chunks_exact_mut(w)) {
                    let (top, bottom) = rows.split_at(w * 4);
                    let (y0, y1) = ys.split_at_mut(w);
                    pair(top, bottom, y0, y1, cs);
                }
            });
        }
    });
}

/// A rectangle's RGBA8 (`rgba`, rw × rh, at `at` in a frame `w` px wide) written into the frame's NV12 `out` over what is
/// there (painter.rs: the pixels the CPU redoes, over the GPU's planes). x, y, rw, rh even.
pub fn patch(rgba: &[u8], rw: usize, at: (usize, usize), w: usize, out: &mut [u8]) {
    let ((x0, y0), rh) = (at, rgba.len() / (rw * 4));
    assert!(x0 % 2 == 0 && y0 % 2 == 0 && rw % 2 == 0 && rh % 2 == 0, "an NV12 patch covers whole 2×2 blocks");
    let (luma, chroma) = out.split_at_mut(out.len() * 2 / 3);
    for (k, rows) in rgba.chunks_exact(rw * 8).enumerate() {
        let (top, bottom) = rows.split_at(rw * 4);
        let y = y0 + 2 * k;
        let (l0, l1) = luma[y * w..(y + 2) * w].split_at_mut(w);
        let c = &mut chroma[(y / 2) * w + x0..][..rw];
        pair(top, bottom, &mut l0[x0..x0 + rw], &mut l1[x0..x0 + rw], c);
    }
}

/// One pair of rows (`top`, `bottom`, RGBA8, even length): their Y into `y0`, `y1` and their Cb Cr pairs into `c`.
fn pair(top: &[u8], bottom: &[u8], y0: &mut [u8], y1: &mut [u8], c: &mut [u8]) {
    for (x, c) in c.chunks_exact_mut(2).enumerate() {
        let mut sum = [0u32; 3];
        for (row, ys) in [(top, &mut *y0), (bottom, &mut *y1)] {
            for dx in 0..2 {
                let q = over_black(&row[(x * 2 + dx) * 4..][..4]);
                ys[x * 2 + dx] = luma(q);
                for k in 0..3 {
                    sum[k] += q[k];
                }
            }
        }
        [c[0], c[1]] = chroma(sum);
    }
}

/// A pixel over black, each channel rounded to a code (unchanged when opaque).
fn over_black(p: &[u8]) -> [u32; 3] {
    let a = p[3] as u32;
    [0, 1, 2].map(|k| (p[k] as u32 * a + 127) / 255)
}

fn luma([r, g, b]: [u32; 3]) -> u8 {
    (Y0.wrapping_add(YR * r).wrapping_add(YG * g).wrapping_add(YB * b) >> S) as u8
}

/// Cb, Cr of a block from its four pixels' sums.
fn chroma([r, g, b]: [u32; 3]) -> [u8; 2] {
    let cb = C0.wrapping_add(CBB * b).wrapping_sub(CBR * r).wrapping_sub(CBG * g);
    let cr = C0.wrapping_add(CRR * r).wrapping_sub(CRG * g).wrapping_sub(CRB * b);
    [(cb >> S) as u8, (cr >> S) as u8]
}

#[cfg(test)]
mod tests {
    // A wrong matrix or range only shows as slightly-off colours in every MP4: the BT.709 limited-range codes, pinned.
    fn one(r: u8, g: u8, b: u8, a: u8) -> [u8; 3] {
        let mut out = [0u8; 6];
        super::from_rgba(&[r, g, b, a].repeat(4), 2, 2, &mut out);
        [out[0], out[4], out[5]]
    }

    #[test]
    fn bt709_limited_range() {
        assert_eq!(one(255, 255, 255, 255), [235, 128, 128]);
        assert_eq!(one(0, 0, 0, 255), [16, 128, 128]);
        assert_eq!(one(255, 0, 0, 255), [63, 102, 240]);
        assert_eq!(one(0, 0, 255, 255), [32, 240, 118]);
        assert_eq!(one(255, 255, 255, 0), [16, 128, 128]); // transparent is black
    }

    /// The coefficients are BT.709's, rounded: each within half a step of the exact value, every row summing as it should.
    #[test]
    fn coefficients_are_bt709() {
        let f = (1u64 << super::S) as f64;
        let (kr, kb) = (0.2126, 0.0722);
        let (ys, cs) = (219.0 / 255.0, 224.0 / 255.0 / 4.0);
        for (got, want) in [(super::YR, kr * ys), (super::YB, kb * ys), (super::CBR, kr * cs / (2.0 * (1.0 - kb))), (super::CBB, cs / 2.0), (super::CRR, cs / 2.0), (super::CRB, kb * cs / (2.0 * (1.0 - kr)))] {
            assert!((got as f64 - want * f).abs() <= 0.5, "{got} vs {}", want * f);
        }
        assert!((super::YG as f64 - (1.0 - kr - kb) * ys * f).abs() <= 1.5);
        assert_eq!((super::CBR + super::CBG, super::CRG + super::CRB), (super::CBB, super::CRR));
    }

    // A frame's random pixels: the split across cores, a patch, and the old float formula (kept here as the reference,
    // at most one code off, rarely).
    fn noise(w: usize, h: usize) -> Vec<u8> {
        let mut s = 12345u32;
        (0..w * h * 4).map(|i| { s ^= s << 13; s ^= s >> 17; s ^= s << 5; if i % 4 == 3 && s % 3 != 0 { 255 } else { (s >> 7) as u8 } }).collect()
    }

    #[test]
    fn a_patch_is_the_same_bytes_as_the_whole() {
        let (w, h) = (66usize, 38usize);
        let rgba = noise(w, h);
        let mut whole = vec![0u8; w * h * 3 / 2];
        super::from_rgba(&rgba, w, h, &mut whole);
        let (x0, y0, rw, rh) = (32, 8, 34, 30);
        let rect: Vec<u8> = (y0..y0 + rh).flat_map(|y| rgba[(y * w + x0) * 4..(y * w + x0 + rw) * 4].to_vec()).collect();
        let mut patched = whole.clone();
        let (l, c) = patched.split_at_mut(w * h);
        for y in y0..y0 + rh { l[y * w + x0..y * w + x0 + rw].fill(0); }
        for y in y0 / 2..(y0 + rh) / 2 { c[y * w + x0..y * w + x0 + rw].fill(0); }
        super::patch(&rect, rw, (x0, y0), w, &mut patched);
        assert!(patched == whole);
    }

    #[test]
    fn close_to_the_float_formula() {
        let (w, h) = (66usize, 38usize);
        let rgba = noise(w, h);
        let mut got = vec![0u8; w * h * 3 / 2];
        super::from_rgba(&rgba, w, h, &mut got);
        let float = float_version(&rgba, w, h);
        let off: Vec<i32> = got.iter().zip(&float).map(|(a, b)| *a as i32 - *b as i32).filter(|d| *d != 0).collect();
        // A part see-through pixel now rounds to a code over black first: one code at most, ~5 % of these bytes.
        assert!(off.iter().all(|d| d.abs() <= 1), "{off:?}");
        assert!(off.len() * 10 < got.len(), "{} of {} bytes differ", off.len(), got.len());
        // Opaque (an export with a background): the same bytes here (1 in 7 million on real frames, 2026-10-29).
        let opaque: Vec<u8> = rgba.chunks(4).flat_map(|p| [p[0], p[1], p[2], 255]).collect();
        super::from_rgba(&opaque, w, h, &mut got);
        assert!(got == float_version(&opaque, w, h));
    }

    /// The float formula nv12.rs had before the integer one (2026-10-29).
    pub fn float_version(rgba: &[u8], w: usize, h: usize) -> Vec<u8> {
        let (kr, kb) = (0.2126f32, 0.0722f32);
        let kg = 1.0 - kr - kb;
        let code = |v: f32| (v + 0.5).clamp(0.0, 255.0) as u8;
        let mut want = vec![0u8; w * h * 3 / 2];
        let (luma, chroma) = want.split_at_mut(w * h);
        let px = |x: usize, y: usize| { let p = &rgba[(y * w + x) * 4..][..4]; let a = p[3] as f32 / 255.0; [p[0] as f32 * a, p[1] as f32 * a, p[2] as f32 * a] };
        let l = |c: [f32; 3]| kr * c[0] + kg * c[1] + kb * c[2];
        for y in (0..h).step_by(2) {
            for x in (0..w).step_by(2) {
                let mut sum = [0f32; 3];
                for (dx, dy) in [(0, 0), (1, 0), (0, 1), (1, 1)] {
                    let c = px(x + dx, y + dy);
                    luma[(y + dy) * w + x + dx] = code(16.0 + 219.0 / 255.0 * l(c));
                    for k in 0..3 { sum[k] += c[k] * 0.25; }
                }
                let m = l(sum);
                chroma[(y / 2) * w + x] = code(128.0 + 224.0 / 255.0 * (sum[2] - m) / (2.0 * (1.0 - kb)));
                chroma[(y / 2) * w + x + 1] = code(128.0 + 224.0 / 255.0 * (sum[0] - m) / (2.0 * (1.0 - kr)));
            }
        }
        want
    }

    /// Real frames, integer vs float: `ROSTRUM_NV12_FRAMES` = a folder of PNGs (an export's frames, even size). Prints how
    /// many bytes move and by how much. `cargo test --profile agent nv12::tests::real_frames -- --ignored --nocapture`
    #[test]
    #[ignore]
    fn real_frames() {
        let dir = std::env::var("ROSTRUM_NV12_FRAMES").expect("ROSTRUM_NV12_FRAMES: a folder of PNG frames");
        let (mut bytes, mut moved, mut most) = (0usize, 0usize, 0i32);
        for e in std::fs::read_dir(&dir).unwrap() {
            let p = e.unwrap().path();
            if p.extension().is_none_or(|x| x != "png") { continue; }
            let img = image::open(&p).unwrap().to_rgba8();
            let (w, h) = (img.width() as usize & !1, img.height() as usize & !1);
            let rgba: Vec<u8> = (0..h).flat_map(|y| img.as_raw()[y * img.width() as usize * 4..][..w * 4].to_vec()).collect();
            let mut got = vec![0u8; w * h * 3 / 2];
            super::from_rgba(&rgba, w, h, &mut got);
            let float = float_version(&rgba, w, h);
            bytes += got.len();
            for (a, b) in got.iter().zip(&float) {
                let d = *a as i32 - *b as i32;
                moved += (d != 0) as usize;
                most = most.max(d.abs());
            }
        }
        println!("integer vs float NV12: {moved} of {bytes} bytes differ ({:.4} %), at most {most} code(s)", moved as f64 * 100.0 / bytes.max(1) as f64);
    }
}
