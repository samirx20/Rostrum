//! Sound in real time: instruments played live (perform.rs, instrument/, layers.rs, midi.rs), the
//! transport playing a rendered mix with overdubs (play.rs, transport.rs), microphone takes (record.rs,
//! calib.rs), how a mix is monitored on the device (monitor.rs, frames.rs) and the WASAPI output (wasapi/).

pub mod calib;
pub mod frames;
#[cfg(not(windows))]
pub mod graph;
#[cfg(windows)]
pub mod hear;
#[cfg(windows)]
pub mod instrument;
#[cfg(windows)]
pub mod layers;
#[cfg(windows)]
pub mod midi;
pub mod monitor;
#[cfg(windows)]
pub mod perform;
#[cfg(windows)]
pub mod play;
#[cfg(windows)]
pub mod record;
#[cfg(windows)]
pub mod transport;
#[cfg(windows)]
pub mod wasapi;
