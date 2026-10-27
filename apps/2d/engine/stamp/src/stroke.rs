//! A stroke's dabs laid in order (`brush.py` `dabs`): each pixel of a dab gets its coverage (tip.rs), the stroke's
//! coverage there grows to it, wet paint first takes up the brush's reservoir, then the paint is laid (paint.rs).
//! The reservoir (D×D RGBA, the paint the brush passed over) follows numpy's arrays: picked up before the dab
//! changes the layer, laid with the reservoir as it was, then taken up into it.
//!
//! Speed, with the same pixels (`skip`): a pixel a dab can't change is not worked out. Outside the tip's shape its
//! coverage is 0; where the stroke already covered a pixel at least as much as the dab can, a dry dab adds nothing
//! (dabs overlap many times over: a 260 px hard stroke lays 1,200 of them, each new one changing a thin crescent).
//! And a big stroke is laid on several threads, each owning every T-th band of rows (`Pool`): a pixel's result depends
//! only on itself, so dry dabs need no waiting; a wet dab's pick-up, laying and take-up wait for each other.

use crate::{paint, tip, Dab, Stroke};
use paint::Mode;
use std::sync::atomic::{AtomicUsize, Ordering};

/// Rows per band a thread owns; and how much work makes threads worth starting.
const BAND: usize = 4;
const PAR_PIXELS: usize = 64 * 1024;
const PAR_DAB: usize = 2048;

/// Lays `dabs` into `layer` (H×W×4) and fills `cov` (the stroke's bbox [x0, y0, x1, y1]). `carried`: the reservoir
/// (D×D×4) written back after the last dab, and whether it is also where it starts (a stroke laid in pieces).
#[allow(clippy::too_many_arguments)]
pub fn lay(st: &Stroke, dabs: &[Dab], (h, w): (usize, usize), bbox: [usize; 4], d: usize, layer: &mut [f32], cov: &mut [f32], under: Option<(&[f32], usize)>,
           carried: Option<(&mut [f32], bool)>) -> Result<(), String> {
    let wet = st.wet > 0.0;
    let mut first = None;
    for (i, dab) in dabs.iter().enumerate() {
        let [x0, x1, y0, y1] = dab.bx;
        if !wet || x1 <= x0 || y1 <= y0 {
            continue;
        }
        let [oy, ox] = dab.at;
        if y0 < oy || y1 > oy + d as i64 || x0 < ox || x1 > ox + d as i64 {
            return Err(format!("a dab ({x0}..{x1}, {y0}..{y1}) outside its reservoir ({ox}, {oy}, {d})"));
        }
        if first.is_none() && dab.again {
            return Err("a dab's other part came before the dab".into());
        }
        if first.is_none() {
            first = Some(i);
        }
    }
    if st.sample_all && first.is_some() && under.is_none() {
        return Err("sample_all needs the composite below".into());
    }
    let [bx0, _, bx1, _] = bbox;
    // What was under the stroke, for the modes that blend with it (its bbox, RGBA).
    let under0: Vec<f32> = if st.mode.reads_under() {
        (bbox[1]..bbox[3]).flat_map(|y| layer[(y * w + bx0) * 4..(y * w + bx1) * 4].iter().copied()).collect()
    } else {
        Vec::new()
    };
    let res_in = carried.as_ref().is_some_and(|c| c.1);
    let (mut res, mut pick) = if wet { (vec![0f32; d * d * 4], vec![0f32; d * d * 4]) } else { (Vec::new(), Vec::new()) };
    if let (true, Some((from, true))) = (wet, carried.as_ref()) {
        if from.len() != d * d * 4 {
            return Err("the carried reservoir is not D×D×4".into());
        }
        res.copy_from_slice(from);
    }
    let areas: Vec<usize> = dabs.iter().map(|b| ((b.bx[1] - b.bx[0]).max(0) * (b.bx[3] - b.bx[2]).max(0)) as usize).collect();
    let total: usize = areas.iter().sum();
    let lit = areas.iter().filter(|&&a| a > 0).count().max(1);
    let threads = if total < PAR_PIXELS || total / lit < PAR_DAB {
        1
    } else {
        std::thread::available_parallelism().map_or(1, |n| n.get()).clamp(1, 8)
    };
    let job = Job {
        st, dabs, h, w, d, bbox, under, under0: &under0, first, res_in, cap: cap(st, bbox, w), threads,
        bar: Bar { n: threads, came: AtomicUsize::new(0), round: AtomicUsize::new(0) },
        layer: Ptr(layer.as_mut_ptr()), cov: Ptr(cov.as_mut_ptr()), res: Ptr(res.as_mut_ptr()), pick: Ptr(pick.as_mut_ptr()),
    };
    if threads == 1 {
        job.run(0);
    } else {
        std::thread::scope(|s| {
            for t in 1..threads {
                let job = &job;
                s.spawn(move || job.run(t));
            }
            job.run(0);
        });
    }
    if let (Some(_), Some((to, _))) = (first, carried) {
        to.copy_from_slice(&res);
    }
    Ok(())
}

/// The threads wait for each other between a wet dab's steps (twice a dab): spinning briefly, as a dab takes well
/// under a millisecond and waking sleeping threads cost as much as the dab.
struct Bar {
    n: usize,
    came: AtomicUsize,
    round: AtomicUsize,
}

impl Bar {
    fn wait(&self) {
        let round = self.round.load(Ordering::Acquire);
        if self.came.fetch_add(1, Ordering::AcqRel) + 1 == self.n {
            self.came.store(0, Ordering::Relaxed);
            self.round.fetch_add(1, Ordering::Release);
            return;
        }
        let mut spins = 0u32;
        while self.round.load(Ordering::Acquire) == round {
            if spins < 4000 {
                spins += 1;
                std::hint::spin_loop();
            } else {
                std::thread::yield_now();
            }
        }
    }
}

#[derive(Clone, Copy)]
struct Ptr(*mut f32);
// The threads write disjoint rows (`Job::own`), and read others' only after a barrier.
unsafe impl Send for Ptr {}
unsafe impl Sync for Ptr {}

struct Job<'a> {
    st: &'a Stroke<'a>,
    dabs: &'a [Dab],
    h: usize,
    w: usize,
    d: usize,
    bbox: [usize; 4],
    under: Option<(&'a [f32], usize)>,
    under0: &'a [f32],
    /// The first dab that picks up (the reservoir starts as its pick-up, unless it goes on from a carried one).
    first: Option<usize>,
    res_in: bool,
    /// What bounds every dab's coverage (`cap`).
    cap: (f64, f64),
    threads: usize,
    bar: Bar,
    layer: Ptr,
    cov: Ptr,
    res: Ptr,
    pick: Ptr,
}

impl Job<'_> {
    fn own(&self, t: usize, row: usize) -> bool {
        (row / BAND) % self.threads == t
    }

    /// Thread `t`'s share of every dab, in order.
    fn run(&self, t: usize) {
        let (st, d) = (self.st, self.d);
        let mut across = Vec::with_capacity(st.kr);
        let wet = self.first.is_some();
        for (i, dab) in self.dabs.iter().enumerate() {
            let [x0, x1, y0, y1] = dab.bx;
            if x1 <= x0 || y1 <= y0 {
                continue;
            }
            let reservoir = wet && self.first.is_some_and(|f| i >= f);
            if reservoir {
                if !dab.again {
                    self.pick_up(t, dab.at, self.first == Some(i) && !self.res_in);
                }
                self.bar.wait();
            }
            tip::across(st, dab, &mut across);
            for y in (y0 as usize..y1 as usize).filter(|&y| self.own(t, y)) {
                self.lay_row(dab, &across, reservoir, y);
            }
            if reservoir {
                self.bar.wait();
                let (res, pick) = unsafe { (std::slice::from_raw_parts_mut(self.res.0, d * d * 4), std::slice::from_raw_parts(self.pick.0, d * d * 4)) };
                for j in (0..d).filter(|&j| self.own(t, j)) {
                    let (r, p) = (&mut res[j * d * 4..(j + 1) * d * 4], &pick[j * d * 4..(j + 1) * d * 4]);
                    if dab.take_weak {
                        let take = dab.take as f32;
                        r.iter_mut().zip(p).for_each(|(r, p)| *r += take * (*p - *r));
                    } else {
                        r.iter_mut().zip(p).for_each(|(r, p)| *r = (*r as f64 + dab.take * (*p - *r) as f64) as f32);
                    }
                }
            }
        }
    }

    /// One row of one dab.
    fn lay_row(&self, dab: &Dab, across: &[f64], reservoir: bool, y: usize) {
        let (st, w, d) = (self.st, self.w, self.d);
        let [bx0, by0, bx1, _] = self.bbox;
        let cw = bx1 - bx0;
        let [x0, x1, ..] = dab.bx;
        let [oy, ox] = dab.at;
        let row = unsafe { std::slice::from_raw_parts_mut(self.layer.0.add(y * w * 4), w * 4) };
        let crow = unsafe { std::slice::from_raw_parts_mut(self.cov.0.add((y - by0) * cw), cw) };
        let res = reservoir.then(|| unsafe { std::slice::from_raw_parts(self.res.0, d * d * 4) });
        let urow = (!self.under0.is_empty()).then(|| &self.under0[(y - by0) * cw * 4..(y - by0 + 1) * cw * 4]);
        let reach = tip::reach(st, dab, y);
        // a dry dab of a mode that steps by the coverage's growth leaves a pixel covered at least `most` as it is
        let grows = !reservoir && matches!(st.mode, Mode::Normal | Mode::Erase | Mode::Overlay | Mode::SoftLight | Mode::Color);
        let most = most_at(st, self.cap, dab, across);
        for x in x0 as usize..x1 as usize {
            let c0 = crow[x - bx0];
            if !reach.contains(&x) && untouched(st, c0, x, y) || grows && c0 as f64 >= most {
                continue;
            }
            let (a, idx) = tip::coverage(st, dab, across, x, y);
            if grows && a <= c0 as f64 {
                continue;
            }
            let c1 = f64::max(c0 as f64, a);
            crow[x - bx0] = c1 as f32;
            let tint = 1.0 + st.cj * 0.6 * st.streak[idx];
            let col = dab.col.map(|c| c as f64 * tint);
            let px = &mut row[x * 4..][..4];
            if let Some(res) = res {
                let r = &res[(((y as i64 - oy) as usize) * d + (x as i64 - ox) as usize) * 4..][..4];
                let la = a * dab.lay;
                for ch in 0..4 {
                    px[ch] = (px[ch] as f64 + la * (r[ch] - px[ch]) as f64) as f32;
                }
            }
            let base = urow.map_or(&[][..], |u| &u[(x - bx0) * 4..][..4]);
            paint::apply(px, c0, c1, col, st.mode, 1.0 - st.wet, base);
        }
    }

    /// Thread `t`'s rows of the reservoir's pick-up under a dab: the D×D pixels at `at` (oy, ox). The canvas edge
    /// repeats (numpy's clamped indices), or on a seamless canvas the paint across it shows (numpy's indices round the
    /// edge); with `sample_all` what the eye sees, this layer over the composite below. `start`: the reservoir starts
    /// as this pick-up.
    fn pick_up(&self, t: usize, [oy, ox]: [i64; 2], start: bool) {
        let (st, h, w, d) = (self.st, self.h, self.w, self.d);
        let layer = unsafe { std::slice::from_raw_parts(self.layer.0, h * w * 4) };
        let inside = ox >= 0 && ox + d as i64 <= w as i64;
        let at_y = |v: i64| if st.wrap { v.rem_euclid(h as i64) } else { v.clamp(0, h as i64 - 1) } as usize;
        let at_x = |v: i64| if st.wrap { v.rem_euclid(w as i64) } else { v.clamp(0, w as i64 - 1) } as usize;
        for j in (0..d).filter(|&j| self.own(t, j)) {
            let sy = at_y(oy + j as i64);
            let out = unsafe { std::slice::from_raw_parts_mut(self.pick.0.add(j * d * 4), d * 4) };
            if inside {
                let at = (sy * w + ox as usize) * 4;
                out.copy_from_slice(&layer[at..at + d * 4]);
            }
            for i in 0..d {
                let sx = at_x(ox + i as i64);
                let p = &mut out[i * 4..][..4];
                if !inside {
                    p.copy_from_slice(&layer[(sy * w + sx) * 4..][..4]);
                }
                if let (true, Some((u, row))) = (st.sample_all, self.under) {
                    let under = &u[sy * row + sx * 4..][..3];
                    for ch in 0..3 {
                        p[ch] += (1.0f32 - p[3]) * under[ch];
                    }
                    p[3] = 1.0;
                }
            }
            if start {
                unsafe { std::slice::from_raw_parts_mut(self.res.0.add(j * d * 4), d * 4) }.copy_from_slice(out);
            }
        }
    }
}

/// The most a dab's coverage can be, as (the factor before its strength and its profile across, the mask's most):
/// the tip's shape gives 0..1 (block: times its profile) and the tip picture scales it, then grain (`most_at`) and
/// the mask.
fn cap(st: &Stroke, [bx0, by0, bx1, by1]: [usize; 4], w: usize) -> (f64, f64) {
    let most = |v: &[f32]| v.iter().fold(0.0f64, |m, &v| m.max(v as f64));
    let shape = if st.tip == tip::Tip::Block { st.prof.iter().fold(0.0, |m: f64, &v| m.max(v)) } else { 1.0 };
    let tex = st.tex.map_or(1.0, most);
    let mask = st.mask.map_or(1.0, |m| (by0..by1).map(|y| most(&m[y * w + bx0..y * w + bx1])).fold(0.0, f64::max));
    (shape * tex, mask)
}

/// The most dab `d`'s coverage can be (`cap`; `across` its profile across). Grain clamps to 0..1 (and may raise a
/// coverage where the paper's values are outside 0..1), so with grain it is 1 before the mask.
fn most_at(st: &Stroke, (pre, mask): (f64, f64), d: &Dab, across: &[f64]) -> f64 {
    let across = if matches!(st.tip, tip::Tip::Bristle | tip::Tip::Flat) { across.iter().fold(0.0, |m, &v| f64::max(m, v)) } else { 1.0 };
    let m = if st.grain.is_some() { 1.0 } else { pre * across * d.a } * mask;
    if m.is_nan() { f64::INFINITY } else { m }
}

/// Whether laying a dab whose coverage at (x, y) is 0 leaves the pixel and the stroke's coverage there as they are
/// (`c0` the coverage so far). Coverage 0 adds nothing (c1 = c0, so the step is 0) for the modes that scale by the step;
/// multiply and screen also step by their own rounding when c0 > 0, and add clamps the pixel, so those lay it. The
/// tip's shape gives 0 before grain and chalk, which keep it 0 on paper of 0..1 (checked here, per pixel).
fn untouched(st: &Stroke, c0: f32, x: usize, y: usize) -> bool {
    let mode = match st.mode {
        Mode::Add => false,
        Mode::Multiply | Mode::Screen => c0 == 0.0,
        _ => true,
    };
    let paper = |f: Option<&[f32]>| f.is_none_or(|f| (0.0..=1.0).contains(&f[y * st.w + x]));
    mode && st.grain.is_none_or(|g| (0.0..=1.0).contains(&g) && paper(st.paper_g)) && (st.tip != tip::Tip::Chalk || paper(st.paper_f))
}
