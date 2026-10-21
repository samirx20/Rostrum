//! The hand-off picture for the Editor (shared/HANDOFFS.md § 2): one OpenEXR file per frame, the beauty as a part
//! named `rgba` (R G B A, half float, ZIP), ACEScg linear light, premultiplied alpha.
//!   rostrum2d-render encode-exr <pattern with {frame}> <w> <h> <first frame number> <fps> <view>
//! The frames arrive as 16-bit display codes (RGBA64LE, straight alpha), what every export gets. A 2D picture is
//! graphics, so each colour enters through the inverse of the project's view (HANDOFFS § 4, `Pipeline::display_to_scene`):
//! the Editor's forward view gives back exactly the colours typed. Header: AP1 chromaticities, framesPerSecond,
//! timeCode (01:00:00:00 at the first frame), `rostrum:engine`. Fails loudly as encode_cmd.rs does.

use exr::meta::attribute::{AttributeValue, Chromaticities, Text, TimeCode};
use exr::prelude::*;
use half::f16;
use rostrum_color::pipeline::{Pipeline, Working};
use rostrum_color::view::Target;

/// ACEScg (AP1 primaries, the ACES white), as OpenEXR's `chromaticities` attribute.
fn ap1() -> Chromaticities {
    Chromaticities {
        red: Vec2(0.713, 0.293),
        green: Vec2(0.165, 0.830),
        blue: Vec2(0.128, 0.044),
        white: Vec2(0.32168, 0.33767),
    }
}

/// Non-drop timecode of frame `n` after 01:00:00:00 at a whole-number rate (HANDOFFS § 6: a label, never timing).
fn timecode(n: u32, fps: u32) -> TimeCode {
    let f = 3600 * fps + n;
    TimeCode { hours: (f / (3600 * fps)) as u8 % 24, minutes: (f / (60 * fps) % 60) as u8, seconds: (f / fps % 60) as u8, frame: (f % fps) as u8, ..TimeCode::default() }
}

/// One frame's 16-bit straight display codes → premultiplied ACEScg halves, 4 per pixel.
fn convert(pipeline: &Pipeline, raw: &[u8], px: usize) -> Vec<f16> {
    let mut out = vec![0u8; px * 8];
    crate::pixels::bands(px, |range, dst: &mut [u8]| {
        for (i, o) in range.zip(dst.chunks_exact_mut(8)) {
            let c = |k: usize| u16::from_le_bytes([raw[i * 8 + k * 2], raw[i * 8 + k * 2 + 1]]) as f32 / 65535.0;
            let a = c(3);
            let rgb = if a > 0.0 { pipeline.display_to_scene([c(0), c(1), c(2)]).map(|v| v * a) } else { [0.0; 3] };
            for (k, v) in [rgb[0], rgb[1], rgb[2], a].into_iter().enumerate() {
                let v = if v.is_finite() { v } else { 0.0 };
                o[k * 2..k * 2 + 2].copy_from_slice(&f16::from_f32(v).to_le_bytes());
            }
        }
    }, &mut out, 8);
    out.chunks_exact(2).map(|b| f16::from_le_bytes([b[0], b[1]])).collect()
}

pub fn exr(args: &[String]) -> std::result::Result<u32, String> {
    let usage = "usage: encode-exr <pattern with {frame}> <w> <h> <first frame> <fps> <view>";
    let pattern = args.first().ok_or(usage)?;
    if !pattern.contains("{frame}") {
        return Err(format!("the path must hold {{frame}}: {pattern}"));
    }
    let num = |i: usize, what: &str| -> std::result::Result<u32, String> {
        args.get(i).ok_or(format!("missing {what}; {usage}"))?.parse().map_err(|_| format!("{what} is not a whole number: {}", args[i]))
    };
    let (w, h, first, fps) = (num(1, "width")?, num(2, "height")?, num(3, "first frame")?, num(4, "fps")?);
    let view = args.get(5).ok_or(format!("missing view; {usage}"))?;
    if fps == 0 || w == 0 || h == 0 {
        return Err(format!("size and fps must be above 0 (got {w}×{h} at {fps})"));
    }
    let pipeline = Pipeline::new(Working::Display, view, Target::Sdr)?;
    let px = (w * h) as usize;
    let (mut buf, mut input) = (vec![0u8; px * 8], std::io::stdin().lock());
    let mut n = 0u32;
    while crate::encode_cmd::frame(&mut input, &mut buf, n)? {
        let halves = convert(&pipeline, &buf, px);
        let mut attrs = LayerAttributes::named("rgba");
        attrs.frames_per_second = Some((fps as i32, 1));
        attrs.software_name = Some(Text::from(concat!("rostrum2d-render ", env!("CARGO_PKG_VERSION"))));
        attrs.other.insert(Text::from("rostrum:engine"), AttributeValue::Text(Text::from(concat!("rostrum-2d ", env!("CARGO_PKG_VERSION")))));
        let wu = w as usize;
        let layer = Layer::new(
            (wu, h as usize),
            attrs,
            Encoding { compression: Compression::ZIP16, blocks: Blocks::ScanLines, line_order: LineOrder::Increasing },
            SpecificChannels::rgba(|p: Vec2<usize>| {
                let i = (p.y() * wu + p.x()) * 4;
                (halves[i], halves[i + 1], halves[i + 2], halves[i + 3])
            }),
        );
        let mut image = Image::from_layer(layer);
        image.attributes.chromaticities = Some(ap1());
        image.attributes.time_code = Some(timecode(n, fps));
        let path = pattern.replace("{frame}", &format!("{:04}", first + n));
        image.write().to_file(&path).map_err(|e| format!("{path}: {e}"))?;
        n += 1;
    }
    if n == 0 {
        return Err("no frames arrived".into());
    }
    Ok(n)
}
