//! The GPU programs the next frames will need, built while nothing is asked (serve.rs `run`). The GPU compiles a program
//! the first time a draw kind meets it (a turned shape, a tilted picture, a motion-blur sum, the export laid into a turned
//! frame): 10-100 ms each, all paid by the first frame that needs them (a frame's first turn took 86 ms, 444 ms under
//! load). After a page is loaded whole, once the host has asked nothing for IDLE, the page is painted through each of
//! VIEWS into a scratch surface (painter.rs `warm`), one view per quiet moment; a request that comes meanwhile waits for
//! at most that one paint. Programs built in earlier runs load from disk (program_cache.rs), so this mostly costs
//! the first run of a build. Nothing a frame shows or keeps is touched.

use std::time::{Duration, Instant};

use skia_safe::M44;

use crate::serve::Session;

/// How long the host must ask nothing before a warm-up paint.
const IDLE: Duration = Duration::from_millis(150);
/// The scale the page is painted at (the canvas shows it at about this size).
const SCALE: f32 = 0.5;
/// The views the page is painted through: turned (affine), then tilted (perspective).
const VIEWS: usize = 2;

#[derive(Default)]
pub struct Warm {
    view: usize,
    due: Option<Instant>,
}

impl Warm {
    /// A page was loaded whole: its draw kinds are built ahead again.
    pub fn page_loaded(&mut self) {
        (self.view, self.due) = (0, Some(Instant::now() + IDLE));
    }

    /// A request came: the next warm-up paint waits for the next quiet moment.
    pub fn asked(&mut self) {
        if let Some(d) = self.due.as_mut() {
            *d = Instant::now() + IDLE;
        }
    }

    /// How long to wait for a request before the next warm-up paint; None when nothing is left to build.
    pub fn wait(&self) -> Option<Duration> {
        self.due.map(|d| d.saturating_duration_since(Instant::now()))
    }

    /// One warm-up paint of the session's page. A paint that fails ends the warm-up: the frame that needs that draw
    /// reports it.
    pub fn step(&mut self, s: &mut Session) {
        let (w, h) = (s.width, s.height);
        let size = (((w as f32 * SCALE).round() as u32).max(1), ((h as f32 * SCALE).round() as u32).max(1));
        let (cx, cy) = (size.0 as f32 / 2.0, size.1 as f32 / 2.0);
        let base = match self.view {
            // Turned 17° about the picture's middle.
            0 => M44::concat(&M44::concat(&M44::translate(cx, cy, 0.0), &M44::rotate(skia_safe::V3::new(0.0, 0.0, 1.0), 17f32.to_radians())), &M44::translate(-cx, -cy, 0.0)),
            // Tilted: the far side smaller.
            _ => {
                #[rustfmt::skip]
                let m = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.3 / size.0 as f32, 0.0, 0.0, 1.0];
                M44::row_major(&m)
            }
        };
        let base = M44::concat(&base, &M44::scale(SCALE, SCALE, 1.0));
        let doc = &mut s.doc;
        let done = s.painter.warm(base, size, |scene| blitz_paint::paint_scene(scene, doc, 1.0, w, h, 0, 0));
        self.view += 1;
        self.due = (done.is_ok() && self.view < VIEWS && s.painter.is_gpu()).then(Instant::now);
    }
}
