//! The renderer's own encoders, for formats an LGPL FFmpeg can't or shouldn't make: a render's `encode` program
//! may be this program itself (sink.rs starts it and writes raw frames to its stdin, as to ffmpeg).
//!   rostrum2d-render encode-gif <out.gif> <w> <h> <fps>
//!       RGBA8 frames → a looping GIF: each frame its own 256-colour palette (NeuQuant, the `gif` and
//!       `color_quant` crates, MIT / Apache-2.0; gifski is AGPL and not used); alpha < 128 → transparent.
//!   rostrum2d-render encode-png <pattern with {frame}> <w> <h> <8|16> <first frame number>
//!       RGBA8 or RGBA64LE frames (straight alpha) → one PNG per frame, `{frame}` → the 4-digit frame number.
//! Both fail loudly (exit 1, the reason on stderr) on a short frame, a bad argument or a write error; a frame
//! that only partly arrived is an error, never a quietly shorter file.

use std::fs::File;
use std::io::{BufWriter, Read};

pub fn run(kind: &str, args: &[String]) {
    let done = match kind {
        "encode-gif" => gif(args),
        _ => png(args),
    };
    match done {
        Ok(n) => eprintln!("{kind}: {n} frames"),
        Err(e) => {
            eprintln!("{kind}: {e}");
            std::process::exit(1);
        }
    }
}

fn num(args: &[String], i: usize, what: &str) -> Result<u32, String> {
    args.get(i).ok_or(format!("missing {what}"))?.parse().map_err(|_| format!("{what} is not a number: {}", args[i]))
}

/// Reads one frame of exactly `buf.len()` bytes: Ok(false) at a clean end, an error for a partial frame.
fn frame(input: &mut impl Read, buf: &mut [u8], index: u32) -> Result<bool, String> {
    let mut got = 0;
    while got < buf.len() {
        match input.read(&mut buf[got..]).map_err(|e| e.to_string())? {
            0 if got == 0 => return Ok(false),
            0 => return Err(format!("frame {index} ended after {got} of {} bytes", buf.len())),
            n => got += n,
        }
    }
    Ok(true)
}

fn gif(args: &[String]) -> Result<u32, String> {
    let out = args.first().ok_or("usage: encode-gif <out.gif> <w> <h> <fps>")?;
    let (w, h, fps) = (num(args, 1, "width")?, num(args, 2, "height")?, num(args, 3, "fps")?);
    if w > u16::MAX as u32 || h > u16::MAX as u32 || fps == 0 {
        return Err(format!("a GIF is at most 65535 px a side and needs fps > 0 (got {w}×{h} at {fps})"));
    }
    let file = BufWriter::new(File::create(out).map_err(|e| format!("{out}: {e}"))?);
    let mut enc = gif::Encoder::new(file, w as u16, h as u16, &[]).map_err(|e| e.to_string())?;
    enc.set_repeat(gif::Repeat::Infinite).map_err(|e| e.to_string())?;
    let (mut buf, mut input) = (vec![0u8; (w * h * 4) as usize], std::io::stdin().lock());
    let (mut n, mut shown_cs) = (0u32, 0u64);
    while frame(&mut input, &mut buf, n)? {
        for px in buf.chunks_exact_mut(4) {
            // GIF has one transparent colour, no partial alpha: a pixel is in or out.
            if px[3] < 128 {
                px.fill(0);
            } else {
                px[3] = 255;
            }
        }
        let mut f = gif::Frame::from_rgba_speed(w as u16, h as u16, &mut buf, 10);
        // Delays are whole hundredths of a second: each frame ends where its exact time rounds to, so 30 fps
        // plays 3, 3, 4 … and the GIF's length matches the comp's.
        let end_cs = ((n as u64 + 1) * 100 + fps as u64 / 2) / fps as u64;
        f.delay = (end_cs - shown_cs).max(1) as u16;
        shown_cs = end_cs;
        f.dispose = gif::DisposalMethod::Background; // a transparent pixel shows nothing of the frame before
        enc.write_frame(&f).map_err(|e| format!("frame {n}: {e}"))?;
        n += 1;
    }
    if n == 0 {
        return Err("no frames arrived".into());
    }
    Ok(n)
}

fn png(args: &[String]) -> Result<u32, String> {
    let pattern = args.first().ok_or("usage: encode-png <pattern with {frame}> <w> <h> <8|16> <first frame>")?;
    if !pattern.contains("{frame}") {
        return Err(format!("the path must hold {{frame}}: {pattern}"));
    }
    let (w, h, depth, first) = (num(args, 1, "width")?, num(args, 2, "height")?, num(args, 3, "depth")?, num(args, 4, "first frame")?);
    let bytes = match depth {
        8 => 4,
        16 => 8,
        d => return Err(format!("depth is 8 or 16; got {d}")),
    };
    let (mut buf, mut input) = (vec![0u8; (w * h * bytes) as usize], std::io::stdin().lock());
    let mut n = 0u32;
    while frame(&mut input, &mut buf, n)? {
        if depth == 16 {
            // PNG stores 16-bit samples big-endian; the frames arrive little-endian.
            for s in buf.chunks_exact_mut(2) {
                s.swap(0, 1);
            }
        }
        let path = pattern.replace("{frame}", &format!("{:04}", first + n));
        let file = BufWriter::new(File::create(&path).map_err(|e| format!("{path}: {e}"))?);
        let mut enc = png::Encoder::new(file, w, h);
        enc.set_color(png::ColorType::Rgba);
        enc.set_depth(if depth == 16 { png::BitDepth::Sixteen } else { png::BitDepth::Eight });
        enc.set_source_srgb(png::SrgbRenderingIntent::Perceptual);
        let mut wr = enc.write_header().map_err(|e| format!("{path}: {e}"))?;
        wr.write_image_data(&buf).map_err(|e| format!("{path}: {e}"))?;
        wr.finish().map_err(|e| format!("{path}: {e}"))?;
        n += 1;
    }
    if n == 0 {
        return Err("no frames arrived".into());
    }
    Ok(n)
}
