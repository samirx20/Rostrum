//! Dialogue repair and dynamics, the inserts a recording is cleaned with (fx/chain.rs runs them):
//! declick, declip (lsar.rs: AR interpolation), dehum, dereverb (plus spectral repair regions) and
//! the de-esser, gate and leveller (dynamics.rs).

pub mod declick;
pub mod dehum;
pub mod dereverb;
pub mod dynamics;
pub mod lsar;
#[cfg(test)]
mod tests;
