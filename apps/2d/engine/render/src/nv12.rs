//! RGBA8 (straight alpha) → NV12 for the MP4 encoder (encode_mp4.rs): BT.709, limited range (Y 16–235, Cb Cr 16–240).
//! Alpha is composited over black (an MP4 has no transparency); each 2×2 block shares one Cb Cr, the average of its
//! four pixels. The values stay as the comp's display picture encodes them (no transfer change), as the old ffmpeg path did.

const KR: f32 = 0.2126;
const KB: f32 = 0.0722;
const KG: f32 = 1.0 - KR - KB;
const Y_SCALE: f32 = 219.0 / 255.0;
const C_SCALE: f32 = 224.0 / 255.0;

/// `rgba` is w×h×4 bytes; `out` is w×h×3/2: the Y plane, then the Cb Cr pairs at half size (row stride w). w, h even.
pub fn from_rgba(rgba: &[u8], w: usize, h: usize, out: &mut [u8]) {
    let (luma, chroma) = out.split_at_mut(w * h);
    let px = |x: usize, y: usize| -> [f32; 3] {
        let p = &rgba[(y * w + x) * 4..][..4];
        let a = p[3] as f32 / 255.0; // over black: the colour times its coverage
        [p[0] as f32 * a, p[1] as f32 * a, p[2] as f32 * a]
    };
    let luma_of = |c: [f32; 3]| KR * c[0] + KG * c[1] + KB * c[2];
    for y in (0..h).step_by(2) {
        for x in (0..w).step_by(2) {
            let mut sum = [0f32; 3];
            for (dx, dy) in [(0, 0), (1, 0), (0, 1), (1, 1)] {
                let c = px(x + dx, y + dy);
                luma[(y + dy) * w + x + dx] = code(16.0 + Y_SCALE * luma_of(c));
                for k in 0..3 {
                    sum[k] += c[k] * 0.25;
                }
            }
            let l = luma_of(sum);
            let i = (y / 2) * w + x;
            chroma[i] = code(128.0 + C_SCALE * (sum[2] - l) / (2.0 * (1.0 - KB)));
            chroma[i + 1] = code(128.0 + C_SCALE * (sum[0] - l) / (2.0 * (1.0 - KR)));
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
}
