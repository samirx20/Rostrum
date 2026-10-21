//! LUTs: the 1D / 3D tables and their interpolation (`apply`), the ONE `.cube` reader and writer
//! (`cube`).
mod apply;
mod cube;

pub use apply::{Interp, Lut1d, Lut3d};
pub use cube::{Cube, CubeError, Lut};
