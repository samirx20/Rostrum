//! Motion blur's time maths (MOTION.md § Motion blur). A shutter open `angle` degrees is open angle/360 of a frame;
//! the frame at t is the average of n stages spread evenly over that open time, centred on t (so a blurred frame is
//! centred where the still at t is). serve.rs `frame` paints each and averages them on the GPU.

use serde_json::Value;

use crate::scene::Node;

/// The shutter for a frame: (angle in degrees, sub-frames). The request's `shutter` / `shutterSamples` (a fast
/// preview with 1 sample, a timing test) override the comp's. No blur when the angle is 0 or there is 1 sample.
pub fn shutter(comp: &Node, req: &Value) -> Result<(f64, usize), String> {
    let pick = |f: &str| -> Result<f64, String> {
        match &req[f] {
            Value::Null => comp.props[f].as_f64().ok_or_else(|| format!("{}.{f}: not a number", comp.id)),
            v => v.as_f64().ok_or_else(|| format!("frame {f}: {v} is not a number")),
        }
    };
    let angle = pick("shutter")?;
    if !(0.0..=720.0).contains(&angle) {
        return Err(format!("{}.shutter: {angle}° is outside 0..720 (0 = no motion blur, 180 = film)", comp.id));
    }
    let n = pick("shutterSamples")?;
    if n.fract() != 0.0 || !(1.0..=64.0).contains(&n) {
        return Err(format!("{}.shutterSamples: {n} is not a whole number from 1 to 64", comp.id));
    }
    Ok((angle, n as usize))
}

/// The n sub-frame times of a shutter open `angle` degrees at `fps`, centred on `t`: the middle of each of n
/// equal slices of the open time [t − open/2, t + open/2].
pub fn sample_times(t: f64, fps: f64, angle: f64, n: usize) -> Vec<f64> {
    let open = angle / 360.0 / fps;
    (0..n).map(|j| t + open * ((j as f64 + 0.5) / n as f64 - 0.5)).collect()
}
