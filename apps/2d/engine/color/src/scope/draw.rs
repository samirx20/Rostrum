//! The scope pictures (§5), drawn by our own code: waveform (RGB overlay and luma, 1024 columns), RGB parade,
//! vectorscope (Rec.709 targets, skin line), histogram, CIE chromaticity with the gamut triangles, false colour, and
//! a sheet of all of them. Graticules are in IRE (SDR display), nits (HDR display) or the space's own values.
use super::font;
use super::measure::{hue_deg, vector_of, SKIN_LINE_DEG};
use super::{Domain, Frame, Region};
use crate::spaces::Gamut;
use crate::Curve;

pub struct Image {
    pub width: usize,
    pub height: usize,
    /// RGBA8, top row first.
    pub rgba: Vec<u8>,
}

type C = [u8; 3];
const BG: C = [14, 15, 18];
const GRID: C = [56, 58, 66];
const GRID_STRONG: C = [96, 98, 108];
const TEXT: C = [190, 192, 200];

impl Image {
    pub fn new(width: usize, height: usize, bg: C) -> Image {
        let mut rgba = vec![255u8; width * height * 4];
        for p in rgba.chunks_exact_mut(4) {
            p[..3].copy_from_slice(&bg);
        }
        Image { width, height, rgba }
    }
    pub fn set(&mut self, x: i64, y: i64, c: C) {
        if x >= 0 && y >= 0 && (x as usize) < self.width && (y as usize) < self.height {
            let i = (y as usize * self.width + x as usize) * 4;
            self.rgba[i..i + 3].copy_from_slice(&c);
        }
    }
    /// Adds light (0..1 per channel) to a pixel.
    fn add(&mut self, x: i64, y: i64, c: [f32; 3]) {
        if x >= 0 && y >= 0 && (x as usize) < self.width && (y as usize) < self.height {
            let i = (y as usize * self.width + x as usize) * 4;
            for k in 0..3 {
                self.rgba[i + k] = (self.rgba[i + k] as f32 + c[k] * 255.0).min(255.0) as u8;
            }
        }
    }
    pub fn rect(&mut self, x0: i64, y0: i64, w: i64, h: i64, c: C) {
        for y in y0..y0 + h {
            for x in x0..x0 + w {
                self.set(x, y, c);
            }
        }
    }
    pub fn line(&mut self, a: (f32, f32), b: (f32, f32), c: C) {
        let n = (b.0 - a.0).abs().max((b.1 - a.1).abs()).ceil().max(1.0) as usize;
        for i in 0..=n {
            let t = i as f32 / n as f32;
            self.set((a.0 + (b.0 - a.0) * t).round() as i64, (a.1 + (b.1 - a.1) * t).round() as i64, c);
        }
    }
    fn frame_rect(&mut self, x0: i64, y0: i64, w: i64, h: i64, c: C) {
        self.line((x0 as f32, y0 as f32), ((x0 + w) as f32, y0 as f32), c);
        self.line((x0 as f32, (y0 + h) as f32), ((x0 + w) as f32, (y0 + h) as f32), c);
        self.line((x0 as f32, y0 as f32), (x0 as f32, (y0 + h) as f32), c);
        self.line(((x0 + w) as f32, y0 as f32), ((x0 + w) as f32, (y0 + h) as f32), c);
    }
    fn circle(&mut self, cx: f32, cy: f32, r: f32, c: C) {
        let n = (r * 6.3).ceil().max(8.0) as usize;
        for i in 0..n {
            let a = i as f32 / n as f32 * std::f32::consts::TAU;
            self.set((cx + r * a.cos()).round() as i64, (cy + r * a.sin()).round() as i64, c);
        }
    }
    pub fn text(&mut self, x: i64, y: i64, s: &str, scale: usize, c: C) {
        for (i, ch) in s.chars().enumerate() {
            let g = font::glyph(ch);
            for (row, bits) in g.iter().enumerate() {
                for col in 0..5 {
                    if bits >> (4 - col) & 1 == 1 {
                        self.rect(x + (i * 6 + col) as i64 * scale as i64, y + (row * scale) as i64, scale as i64, scale as i64, c);
                    }
                }
            }
        }
    }
    fn text_right(&mut self, right: i64, y: i64, s: &str, scale: usize, c: C) {
        self.text(right - font::width(s, scale) as i64, y, s, scale, c);
    }
    /// This image fitted inside `w` × `h` (area-averaged, aspect kept), centred on a `bg` canvas of that size.
    pub fn fit(&self, w: usize, h: usize, bg: C) -> Image {
        let s = (w as f32 / self.width as f32).min(h as f32 / self.height as f32);
        let (dw, dh) = (((self.width as f32 * s).round() as usize).max(1), ((self.height as f32 * s).round() as usize).max(1));
        let mut out = Image::new(w, h, bg);
        let (ox, oy) = ((w - dw) / 2, (h - dh) / 2);
        for y in 0..dh {
            let (sy0, sy1) = (y as f32 / s, ((y + 1) as f32 / s).min(self.height as f32));
            for x in 0..dw {
                let (sx0, sx1) = (x as f32 / s, ((x + 1) as f32 / s).min(self.width as f32));
                let (mut acc, mut n) = ([0f32; 3], 0f32);
                for yy in sy0 as usize..(sy1.ceil() as usize).max(sy0 as usize + 1).min(self.height) {
                    for xx in sx0 as usize..(sx1.ceil() as usize).max(sx0 as usize + 1).min(self.width) {
                        let i = (yy * self.width + xx) * 4;
                        for k in 0..3 {
                            acc[k] += self.rgba[i + k] as f32;
                        }
                        n += 1.0;
                    }
                }
                out.set((ox + x) as i64, (oy + y) as i64, acc.map(|a| (a / n).round() as u8));
            }
        }
        out
    }
}

fn fmt(v: f32) -> String {
    let s = format!("{v:.2}");
    s.trim_end_matches('0').trim_end_matches('.').to_string()
}

/// How a scope's value axis reads.
struct Axis {
    lo: f32,
    hi: f32,
    ticks: Vec<(f32, String)>,
    unit: String,
}

fn axis(frame: &Frame, region: &Region) -> Axis {
    match frame.domain {
        Domain::Display { hdr: false } => Axis { lo: -0.05, hi: 1.10, ticks: (0..=10).map(|i| (i as f32 / 10.0, (i * 10).to_string())).collect(), unit: "IRE".into() },
        Domain::Display { hdr: true } => Axis {
            lo: 0.0,
            hi: 1.0,
            ticks: [0.0, 1.0, 10.0, 100.0, 203.0, 400.0, 1000.0, 4000.0, 10000.0].iter().map(|&n: &f32| (Curve::Pq100.encode(n / 100.0), fmt(n))).collect(),
            unit: "NITS".into(),
        },
        Domain::AcesCg => {
            let (x0, y0, x1, y1) = region.bounds(frame.width, frame.height);
            let mut top = 1.0f32;
            for y in (y0..y1).step_by(((y1 - y0) / 128).max(1)) {
                for x in (x0..x1).step_by(((x1 - x0) / 128).max(1)) {
                    top = top.max(frame.px[y * frame.width + x].iter().cloned().fold(0.0, f32::max));
                }
            }
            let hi = (top.log2().ceil()).exp2().max(1.0);
            Axis { lo: -0.02 * hi, hi, ticks: (0..=4).map(|i| (hi * i as f32 / 4.0, fmt(hi * i as f32 / 4.0))).collect(), unit: "ACESCG".into() }
        }
        Domain::AcesCct => Axis { lo: -0.05, hi: 1.1, ticks: (0..=10).map(|i| (i as f32 / 10.0, fmt(i as f32 / 10.0))).collect(), unit: "ACESCCT".into() },
    }
}

fn for_px(frame: &Frame, region: &Region, mut f: impl FnMut(usize, usize, [f32; 3])) {
    let (x0, y0, x1, y1) = region.bounds(frame.width, frame.height);
    for y in y0..y1 {
        for x in x0..x1 {
            if region.contains(x, y) {
                f(x, y, frame.px[y * frame.width + x]);
            }
        }
    }
}

const ML: usize = 52;
const MT: usize = 22;
const PLOT_H: usize = 512;
const COLS: usize = 1024;
const RGB_COLOR: [[f32; 3]; 3] = [[1.0, 0.25, 0.25], [0.25, 1.0, 0.25], [0.35, 0.5, 1.0]];

fn row_of(ax: &Axis, v: f32) -> Option<usize> {
    let t = (v - ax.lo) / (ax.hi - ax.lo);
    (t >= 0.0 && t < 1.0).then(|| ((1.0 - t) * PLOT_H as f32) as usize)
}

/// The plot frame with its value graticule; the plot area starts at (ML, MT) and is `cols` × 512.
fn plot_base(ax: &Axis, cols: usize) -> Image {
    let mut img = Image::new(ML + cols + 10, MT + PLOT_H + 10, BG);
    for (v, label) in &ax.ticks {
        if let Some(r) = row_of(ax, *v) {
            let y = (MT + r) as i64;
            img.line((ML as f32, y as f32), ((ML + cols) as f32, y as f32), GRID);
            img.text_right(ML as i64 - 5, y - 3, label, 1, TEXT);
        }
    }
    img.text(4, 6, &ax.unit, 1, TEXT);
    img.frame_rect(ML as i64, MT as i64, cols as i64, PLOT_H as i64, GRID_STRONG);
    img
}

/// Brightness of a cell with `count` samples when `per_col` samples fall in each column.
fn glow(count: f32, per_col: f32) -> f32 {
    1.0 - (-0.35 * count * PLOT_H as f32 / per_col.max(1.0)).exp()
}

/// Waveform panels: `panels` lists, per panel, the channels it plots (a channel is 0..2 for R, G, B, 3 for luma).
fn waveform(frame: &Frame, region: &Region, ax: &Axis, panels: &[&[usize]], panel_w: usize, tint: &[[f32; 3]; 4]) -> Image {
    let gap = if panels.len() > 1 { 2 } else { 0 };
    let total = panels.len() * panel_w + (panels.len() - 1) * gap;
    let mut img = plot_base(ax, total);
    let (_, y0, _, y1) = region.bounds(frame.width, frame.height);
    let per_col = (y1 - y0) as f32 * (frame.width as f32 / panel_w as f32).max(1.0);
    let mut acc = vec![vec![0f32; panel_w * PLOT_H]; 4];
    let luma = |c: [f32; 3]| frame.domain.luma(c);
    for_px(frame, region, |x, _y, c| {
        let (c0, c1) = (x * panel_w / frame.width, ((x + 1) * panel_w / frame.width).max(x * panel_w / frame.width + 1));
        let vals = [c[0], c[1], c[2], luma(c)];
        for (k, v) in vals.iter().enumerate() {
            // A sample lands between two rows (shared by distance), so levels of an 8-bit picture fill the plot without a comb.
            let f = (1.0 - (*v - ax.lo) / (ax.hi - ax.lo)) * PLOT_H as f32 - 0.5;
            if f > -1.0 && f < PLOT_H as f32 {
                let (r0, w1) = (f.floor(), f - f.floor());
                for (r, w) in [(r0, 1.0 - w1), (r0 + 1.0, w1)] {
                    if r >= 0.0 && (r as usize) < PLOT_H {
                        for col in c0..c1.min(panel_w) {
                            acc[k][r as usize * panel_w + col] += w;
                        }
                    }
                }
            }
        }
    });
    for (p, chans) in panels.iter().enumerate() {
        let ox = ML + p * (panel_w + gap);
        for r in 0..PLOT_H {
            for col in 0..panel_w {
                let mut light = [0f32; 3];
                for &k in chans.iter() {
                    let g = glow(acc[k][r * panel_w + col], per_col);
                    for j in 0..3 {
                        light[j] += g * tint[k][j];
                    }
                }
                if light != [0.0; 3] {
                    img.add((ox + col) as i64, (MT + r) as i64, light);
                }
            }
        }
        if panels.len() > 1 {
            let name = ["R", "G", "B"][p.min(2)];
            img.text(ox as i64 + 4, MT as i64 + 4, name, 1, TEXT);
        }
    }
    img
}

fn histogram(frame: &Frame, region: &Region, ax: &Axis) -> Image {
    const BINS: usize = 256;
    const H: usize = 360;
    let mut img = Image::new(ML + COLS + 10, 22 + H + 24, BG);
    let mut bins = vec![[0f32; 4]; BINS];
    for_px(frame, region, |_, _, c| {
        let b = |v: f32| (((v - ax.lo) / (ax.hi - ax.lo) * BINS as f32).floor().clamp(0.0, BINS as f32 - 1.0)) as usize;
        for k in 0..3 {
            bins[b(c[k])][k] += 1.0;
        }
        bins[b(frame.domain.luma(c))][3] += 1.0;
    });
    let peak = bins[1..BINS - 1].iter().flat_map(|b| b.iter().cloned()).fold(1.0, f32::max);
    for (v, label) in &ax.ticks {
        let x = ML as f32 + (v - ax.lo) / (ax.hi - ax.lo) * COLS as f32;
        img.line((x, 22.0), (x, (22 + H) as f32), GRID);
        img.text(x as i64 - font::width(label, 1) as i64 / 2, (22 + H + 6) as i64, label, 1, TEXT);
    }
    img.text(4, 6, &format!("HISTOGRAM {}", ax.unit), 1, TEXT);
    for (i, b) in bins.iter().enumerate() {
        for x in 0..COLS / BINS {
            let col = (ML + i * COLS / BINS + x) as i64;
            for k in [3usize, 0, 1, 2] {
                let h = ((b[k] / peak).sqrt().min(1.0) * H as f32) as i64;
                let tint = if k == 3 { [0.30, 0.30, 0.32] } else { [RGB_COLOR[k][0] * 0.55, RGB_COLOR[k][1] * 0.55, RGB_COLOR[k][2] * 0.55] };
                for y in 0..h {
                    img.add(col, (22 + H) as i64 - 1 - y, tint.map(|t| t * if k == 3 { 1.0 } else { 0.7 }));
                }
            }
        }
    }
    img.frame_rect(ML as i64, 22, COLS as i64, H as i64, GRID_STRONG);
    img
}

const VEC: usize = 560;
const VR: f32 = 252.0;

fn vectorscope(frame: &Frame, region: &Region) -> Image {
    let mut img = Image::new(VEC, VEC, BG);
    let (cx, cy) = (VEC as f32 / 2.0, VEC as f32 / 2.0);
    for r in [0.25, 0.5, 0.75, 1.0] {
        img.circle(cx, cy, VR * r, if r == 1.0 { GRID_STRONG } else { GRID });
    }
    img.line((cx - VR, cy), (cx + VR, cy), GRID);
    img.line((cx, cy - VR), (cx, cy + VR), GRID);
    let d709 = frame.domain.d709_fn();
    let mut cells = vec![(0f32, [0f32; 3]); VEC * VEC];
    let mut n = 0usize;
    for_px(frame, region, |_, _, c| {
        let d = d709(c);
        let (u, v) = vector_of(d);
        let (px, py) = ((cx + u * VR).round() as i64, (cy - v * VR).round() as i64);
        n += 1;
        for (dx, dy) in [(0, 0), (1, 0), (0, 1), (1, 1)] {
            let (x, y) = (px + dx, py + dy);
            if x >= 0 && y >= 0 && (x as usize) < VEC && (y as usize) < VEC {
                let cell = &mut cells[y as usize * VEC + x as usize];
                cell.0 += 1.0;
                for k in 0..3 {
                    cell.1[k] += d[k].clamp(0.0, 1.0);
                }
            }
        }
    });
    let gain = 40_000.0 / n.max(1) as f32;
    for (i, (count, sum)) in cells.iter().enumerate() {
        if *count > 0.0 {
            let avg = sum.map(|s| s / count);
            let m = avg.iter().cloned().fold(0.05, f32::max);
            let g = 1.0 - (-count * gain).exp();
            img.add((i % VEC) as i64, (i / VEC) as i64, avg.map(|a| a / m * g * 0.55 + g * 0.35));
        }
    }
    // Rec.709 targets: 75 % colour bars (boxes), 100 % (ticks).
    let bars: [(&str, [f32; 3]); 6] = [("R", [1.0, 0.0, 0.0]), ("Y", [1.0, 1.0, 0.0]), ("G", [0.0, 1.0, 0.0]), ("C", [0.0, 1.0, 1.0]), ("B", [0.0, 0.0, 1.0]), ("M", [1.0, 0.0, 1.0])];
    for (name, rgb) in bars {
        for (amp, half) in [(0.75, 7i64), (1.0, 2i64)] {
            let (u, v) = vector_of(rgb.map(|c| c * amp));
            let (x, y) = ((cx + u * VR) as i64, (cy - v * VR) as i64);
            img.frame_rect(x - half, y - half, half * 2, half * 2, [230, 230, 120]);
            if amp == 0.75 {
                let ang = hue_deg(u, v).to_radians();
                img.text(x + (ang.cos() * 18.0) as i64 - 3, y - (ang.sin() * 18.0) as i64 - 3, name, 1, TEXT);
            }
        }
    }
    let a = SKIN_LINE_DEG.to_radians();
    img.line((cx, cy), (cx + a.cos() * VR, cy - a.sin() * VR), [255, 170, 90]);
    img.text((cx + a.cos() * VR) as i64 + 4, (cy - a.sin() * VR) as i64 - 4, "SKIN", 1, [255, 170, 90]);
    img.text(4, 4, "VECTORSCOPE 709", 1, TEXT);
    img
}

/// CIE 1931 spectral locus, xy, 380 .. 700 nm (CIE standard observer, 10–20 nm steps).
const LOCUS: [[f32; 2]; 27] = [
    [0.1741, 0.0050], [0.1733, 0.0048], [0.1714, 0.0051], [0.1644, 0.0109], [0.1440, 0.0297], [0.1241, 0.0578], [0.0913, 0.1327], [0.0454, 0.2950],
    [0.0082, 0.5384], [0.0139, 0.7502], [0.0743, 0.8338], [0.1547, 0.8059], [0.2296, 0.7543], [0.3016, 0.6923], [0.3731, 0.6245], [0.4441, 0.5547],
    [0.5125, 0.4866], [0.5752, 0.4242], [0.6270, 0.3725], [0.6658, 0.3340], [0.6915, 0.3083], [0.7079, 0.2920], [0.7190, 0.2809], [0.7260, 0.2740],
    [0.7300, 0.2700], [0.7347, 0.2653], [0.1741, 0.0050],
];

fn chromaticity(frame: &Frame, region: &Region) -> Image {
    const S: f32 = 640.0;
    let (w, h) = (560usize, 590usize);
    let mut img = Image::new(w, h, BG);
    let at = |x: f32, y: f32| (28.0 + x * S, h as f32 - 28.0 - y * S);
    for i in 0..=8 {
        let t = i as f32 * 0.1;
        let (px, _) = at(t, 0.0);
        img.line((px, at(0.0, 0.0).1), (px, at(0.0, 0.85).1), GRID);
        img.text(px as i64 - 6, h as i64 - 20, &fmt(t), 1, TEXT);
    }
    for i in 0..=8 {
        let t = i as f32 * 0.1;
        let (_, py) = at(0.0, t);
        img.line((at(0.0, 0.0).0, py), (at(0.8, 0.0).0, py), GRID);
        img.text(2, py as i64 - 3, &fmt(t), 1, TEXT);
    }
    let to_xyz = Gamut::get("lin_rec709").unwrap().to_xyz();
    let lin = frame.domain.to_lin709_fn();
    let mut cells = vec![(0f32, [0f32; 3]); w * h];
    let mut n = 0usize;
    let disp = frame.domain.d709_fn();
    for_px(frame, region, |_, _, c| {
        let l = lin(c).map(f64::from);
        let xyz = crate::matrix::apply(&to_xyz, l);
        let sum = xyz[0] + xyz[1] + xyz[2];
        if sum > 1e-6 {
            let (px, py) = at((xyz[0] / sum) as f32, (xyz[1] / sum) as f32);
            let (x, y) = (px.round() as i64, py.round() as i64);
            n += 1;
            if x >= 0 && y >= 0 && (x as usize) < w && (y as usize) < h {
                let cell = &mut cells[y as usize * w + x as usize];
                cell.0 += 1.0;
                let d = disp(c);
                for k in 0..3 {
                    cell.1[k] += d[k].clamp(0.0, 1.0);
                }
            }
        }
    });
    let gain = 40_000.0 / n.max(1) as f32;
    for (i, (count, sum)) in cells.iter().enumerate() {
        if *count > 0.0 {
            let avg = sum.map(|s| s / count);
            let m = avg.iter().cloned().fold(0.05, f32::max);
            let g = 1.0 - (-count * gain).exp();
            img.add((i % w) as i64, (i / w) as i64, avg.map(|a| a / m * g * 0.6 + g * 0.3));
        }
    }
    for pair in LOCUS.windows(2) {
        img.line(at(pair[0][0], pair[0][1]), at(pair[1][0], pair[1][1]), [150, 150, 160]);
    }
    for (id, label, col) in [("lin_rec709", "REC709", [235, 235, 235]), ("lin_p3d65", "P3", [240, 190, 70]), ("lin_rec2020", "REC2020", [80, 200, 230])] {
        let p = Gamut::get(id).unwrap().primaries.unwrap();
        let pts = [p.r, p.g, p.b, p.r].map(|q| at(q[0] as f32, q[1] as f32));
        for pair in pts.windows(2) {
            img.line(pair[0], pair[1], col);
        }
        let k = ["lin_rec709", "lin_p3d65", "lin_rec2020"].iter().position(|x| *x == id).unwrap() as i64;
        img.rect(w as i64 - 100, 10 + k * 12, 8, 8, col);
        img.text(w as i64 - 88, 10 + k * 12 + 1, label, 1, TEXT);
    }
    let (wx, wy) = at(0.3127, 0.3290);
    img.line((wx - 4.0, wy), (wx + 4.0, wy), [255, 255, 255]);
    img.line((wx, wy - 4.0), (wx, wy + 4.0), [255, 255, 255]);
    img.text(4, 4, "CIE 1931 XY (D65 WHITE)", 1, TEXT);
    img
}

/// False colour bands in units of the domain's white: (upper limit, colour, label).
const FALSE: [(f32, C, &str); 9] = [
    (0.0, [150, 40, 200], "<0"),
    (0.05, [30, 60, 220], "0-5"),
    (0.15, [0, 160, 190], "5-15"),
    (0.40, [70, 74, 80], "15-40"),
    (0.60, [60, 170, 70], "40-60"),
    (0.80, [170, 172, 178], "60-80"),
    (0.95, [235, 220, 60], "80-95"),
    (1.0, [255, 140, 0], "95-100"),
    (f32::INFINITY, [235, 30, 30], ">100"),
];

fn false_colour(frame: &Frame, region: &Region) -> Image {
    let s = (960.0 / frame.width as f32).min(1.0);
    let (w, h) = (((frame.width as f32 * s).round() as usize).max(1), ((frame.height as f32 * s).round() as usize).max(1));
    let mut img = Image::new(w, h + 26, BG);
    let white = frame.domain.white();
    for y in 0..h {
        for x in 0..w {
            let (sx, sy) = (((x as f32 / s) as usize).min(frame.width - 1), ((y as f32 / s) as usize).min(frame.height - 1));
            let c = frame.px[sy * frame.width + sx];
            let v = frame.domain.luma(c) / white;
            let band = if v < 0.0 { 0 } else if v > 1.0 + 0.5 / 255.0 { 8 } else { (1..8).find(|&i| v < FALSE[i].0).unwrap_or(7) };
            let inside = region.contains(sx, sy) && { let (x0, y0, x1, y1) = region.bounds(frame.width, frame.height); sx >= x0 && sx < x1 && sy >= y0 && sy < y1 };
            let col = FALSE[band].1;
            img.set(x as i64, y as i64, if inside { col } else { col.map(|k| k / 3) });
        }
    }
    let sw = w / FALSE.len();
    for (i, (_, col, label)) in FALSE.iter().enumerate() {
        img.rect((i * sw) as i64, h as i64 + 2, (sw - 2) as i64, 8, *col);
        img.text((i * sw) as i64, h as i64 + 14, label, 1, TEXT);
    }
    img
}

/// The picture itself as an 8-bit display image (scaled to at most `max_w` wide).
pub fn picture(frame: &Frame, max_w: usize) -> Image {
    let d = Domain::Display { hdr: false };
    let f = frame.domain.to_lin709_fn();
    let e = d.from_lin709_fn();
    let mut img = Image::new(frame.width, frame.height, BG);
    for (i, c) in frame.px.iter().enumerate() {
        let v = if frame.domain == d { *c } else { e(f(*c)) };
        for k in 0..3 {
            img.rgba[i * 4 + k] = (v[k].clamp(0.0, 1.0) * 255.0 + 0.5) as u8;
        }
    }
    if frame.width > max_w { img.fit(max_w, (frame.height * max_w).div_ceil(frame.width), BG) } else { img }
}

pub const NAMES: [&str; 8] = ["waveform", "luma", "parade", "vector", "histogram", "chroma", "false", "picture"];

/// The named scope pictures of the frame over `region` (`NAMES`).
pub fn draw(frame: &Frame, region: &Region, names: &[&str]) -> Result<Vec<(String, Image)>, String> {
    let ax = axis(frame, region);
    let tint = [RGB_COLOR[0], RGB_COLOR[1], RGB_COLOR[2], [0.55, 1.0, 0.65]];
    names
        .iter()
        .map(|&n| {
            let img = match n {
                "waveform" => waveform(frame, region, &ax, &[&[0, 1, 2]], COLS, &tint),
                "luma" => waveform(frame, region, &ax, &[&[3]], COLS, &tint),
                "parade" => waveform(frame, region, &ax, &[&[0], &[1], &[2]], 340, &tint),
                "vector" => vectorscope(frame, region),
                "histogram" => histogram(frame, region, &ax),
                "chroma" => chromaticity(frame, region),
                "false" => false_colour(frame, region),
                "picture" => picture(frame, 960),
                o => return Err(format!("unknown scope picture `{o}` (one of {})", NAMES.join(", "))),
            };
            Ok((n.to_string(), img))
        })
        .collect()
}

/// All the scopes on one sheet (two columns), with a title line.
pub fn sheet(frame: &Frame, region: &Region, title: &str) -> Image {
    let imgs = draw(frame, region, &["picture", "false", "luma", "waveform", "parade", "vector", "histogram", "chroma"]).expect("known names");
    let labels = ["PICTURE (DISPLAY)", "FALSE COLOUR", "LUMA WAVEFORM", "RGB WAVEFORM", "RGB PARADE", "VECTORSCOPE", "HISTOGRAM", "CIE CHROMATICITY"];
    let (cw, ch, gap, top) = (800usize, 440usize, 10usize, 34usize);
    let rows = imgs.len().div_ceil(2);
    let mut out = Image::new(2 * cw + 3 * gap, top + rows * (ch + gap) + gap, [6, 6, 8]);
    out.text(gap as i64, 10, title, 2, [225, 226, 232]);
    for (i, ((_, img), label)) in imgs.iter().zip(labels).enumerate() {
        let (x, y) = (gap + (i % 2) * (cw + gap), top + gap + (i / 2) * (ch + gap));
        let tile = img.fit(cw, ch, BG);
        for r in 0..ch {
            let o = ((y + r) * out.width + x) * 4;
            out.rgba[o..o + cw * 4].copy_from_slice(&tile.rgba[r * cw * 4..(r + 1) * cw * 4]);
        }
        out.text(x as i64 + 6, y as i64 + 6, label, 1, [200, 202, 210]);
    }
    out
}
