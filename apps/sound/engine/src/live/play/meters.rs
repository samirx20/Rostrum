//! The strips' live meters in `rostrum-sound play` (play.rs): the render's own levels (mix/render/levels.rs), one
//! `levels` line about every 33 ms while the mix rolls, at the speaker's mix time, and `{"levels": null}` when it stops.

use std::time::{Duration, Instant};

use crate::mix::render::levels::Levels;

/// The strips' live meters (the render's levels, levels.rs) printed at the speaker's time while it rolls.
pub struct Meters {
    levels: Option<Levels>,
    last: Option<f64>,
    shown: Instant,
}

impl Meters {
    pub fn new(levels: Result<Levels, String>) -> Meters {
        let levels = levels.map_err(|e| println!("{}", serde_json::json!({ "error": format!("meters: no levels for this mix, the Mixer's meters stay still ({e})") }))).ok();
        Meters { levels, last: None, shown: Instant::now() }
    }

    /// `t`: the mix time at the speaker, None when stopped.
    pub fn show(&mut self, t: Option<f64>) {
        let Some(l) = &self.levels else { return };
        match (t, self.last) {
            (None, Some(_)) => {
                println!("{}", serde_json::json!({ "levels": null }));
                self.last = None;
            }
            (Some(b), last) if self.shown.elapsed() >= Duration::from_millis(33) => {
                self.shown = Instant::now();
                // A seek or a loop's wrap: from here, not across the jump.
                let a = last.filter(|a| *a <= b && b - *a < 0.25).unwrap_or(b);
                println!("{}", l.line(a, b));
                self.last = Some(b);
            }
            _ => {}
        }
    }
}

