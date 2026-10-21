//! The score's instruments: the named instruments and drums (voices/), the synth voice (synth/,
//! analog.rs), drum-machine voices (drumsynth.rs), the SoundFont sampler (sampler.rs), procedural
//! instruments (model/), and the per-note expression they all read (expression.rs). SFZ instruments
//! are sfz.rs at the crate root.

pub mod analog;
pub mod drumsynth;
pub mod expression;
pub mod model;
pub mod sampler;
pub mod sfz;
pub mod synth;
pub mod voices;

/// Equal-power pan gains (the pan law every voice uses), scaled.
pub fn pan_gains(pan: f64, scale: f64) -> (f64, f64) {
    let a = (pan.clamp(-1.0, 1.0) + 1.0) * std::f64::consts::PI / 4.0;
    (a.cos() * scale, a.sin() * scale)
}
