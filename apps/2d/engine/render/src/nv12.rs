//! RGBA8 (straight alpha) → NV12 for the MP4 encoder (encode_mp4.rs): BT.709, limited range (Y 16–235, Cb Cr 16–240).
//! Alpha is composited over black (an MP4 has no transparency); each 2×2 block shares one Cb Cr, the average of its
//! four pixels; rows of 2×2 blocks are split across the cores. The values stay as the comp's display picture encodes them (no transfer change), as the old ffmpeg path did.

const KR: f32 = 0.2126;
const KB: f32 = 0.0722;
const KG: f32 = 1.0 - KR - KB;
const Y_SCALE: f32 = 219.0 / 255.0;
const C_SCALE: f32 = 224.0 / 255.0;

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
            s.spawn(move || rows(src, w, l, c));
        }
    });
}

/// The rows `src` holds (an even number): their Y rows into `luma`, their Cb Cr rows into `chroma`.
fn rows(src: &[u8], w: usize, luma: &mut [u8], chroma: &mut [u8]) {
    let px = |p: &[u8]| -> [f32; 3] {
        if p[3] == 255 {
            return [p[0] as f32, p[1] as f32, p[2] as f32]; // fully covered: the colour times 1.0, unchanged
        }
        let a = p[3] as f32 / 255.0; // over black: the colour times its coverage
        [p[0] as f32 * a, p[1] as f32 * a, p[2] as f32 * a]
    };
    let luma_of = |c: [f32; 3]| KR * c[0] + KG * c[1] + KB * c[2];
    for ((top, bottom), (yt, cr)) in src.chunks_exact(w * 8).map(|r| r.split_at(w * 4)).zip(luma.chunks_exact_mut(w * 2).zip(chroma.chunks_exact_mut(w))) {
        let (y0, y1) = yt.split_at_mut(w);
        for (x, c) in cr.chunks_exact_mut(2).enumerate() {
            let mut sum = [0f32; 3];
            for (rowp, ys) in [(top, &mut *y0), (bottom, &mut *y1)] {
                for dx in 0..2 {
                    let c = px(&rowp[(x * 2 + dx) * 4..][..4]);
                    ys[x * 2 + dx] = code(16.0 + Y_SCALE * luma_of(c));
                    for k in 0..3 {
                        sum[k] += c[k] * 0.25;
                    }
                }
            }
            let l = luma_of(sum);
            c[0] = code(128.0 + C_SCALE * (sum[2] - l) / (2.0 * (1.0 - KB)));
            c[1] = code(128.0 + C_SCALE * (sum[0] - l) / (2.0 * (1.0 - KR)));
        }
    }
}

fn code(v: f32) -> u8 {
    (v + 0.5).clamp(0.0, 255.0) as u8
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
        assert_eq!(one(255, 255, 255, 0), [16, 128, 128]); // transparent is black
    }

    // The split across cores and the opaque shortcut change no byte: the first one-thread, per-pixel version, kept as the reference.
    #[test]
    fn same_bytes_as_the_plain_version() {
        let (w, h) = (66usize, 38usize);
        let mut s = 12345u32;
        let rgba: Vec<u8> = (0..w * h * 4).map(|i| { s ^= s << 13; s ^= s >> 17; s ^= s << 5; if i % 4 == 3 && s % 3 != 0 { 255 } else { (s >> 7) as u8 } }).collect();
        let (mut got, mut want) = (vec![0u8; w * h * 3 / 2], vec![0u8; w * h * 3 / 2]);
        super::from_rgba(&rgba, w, h, &mut got);
        let (luma, chroma) = want.split_at_mut(w * h);
        let px = |x: usize, y: usize| { let p = &rgba[(y * w + x) * 4..][..4]; let a = p[3] as f32 / 255.0; [p[0] as f32 * a, p[1] as f32 * a, p[2] as f32 * a] };
        let l = |c: [f32; 3]| super::KR * c[0] + super::KG * c[1] + super::KB * c[2];
        for y in (0..h).step_by(2) {
            for x in (0..w).step_by(2) {
                let mut sum = [0f32; 3];
                for (dx, dy) in [(0, 0), (1, 0), (0, 1), (1, 1)] {
                    let c = px(x + dx, y + dy);
                    luma[(y + dy) * w + x + dx] = super::code(16.0 + super::Y_SCALE * l(c));
                    for k in 0..3 { sum[k] += c[k] * 0.25; }
                }
                let m = l(sum);
                chroma[(y / 2) * w + x] = super::code(128.0 + super::C_SCALE * (sum[2] - m) / (2.0 * (1.0 - super::KB)));
                chroma[(y / 2) * w + x + 1] = super::code(128.0 + super::C_SCALE * (sum[0] - m) / (2.0 * (1.0 - super::KR)));
            }
        }
        assert!(got == want);
    }
}
