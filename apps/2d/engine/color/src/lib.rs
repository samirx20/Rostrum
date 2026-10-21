//! rostrum-color: Rostrum's one colour library (docs/phase0/COLOUR_PIPELINE.md §2.3). Pure Rust, CPU
//! reference for every colour path; OpenColorIO is only the offline oracle (ORACLE.md).
//!   tf       transfer functions (display curves, ACEScc/cct, camera logs), linear ↔ code
//!   matrix   3×3 maths, RGB ↔ XYZ from primaries, chromatic adaptation
//!   spaces   the gamut and colour-space registry (ids per ORACLE.md)
//!   convert  `convert(src, dst)`: decode → matrix → encode as one reusable transform
//!   lut      `.cube` read / write, 1D and 3D apply (trilinear, tetrahedral), bake
//!   view     the view transforms (Neutral, ACES 2.0, AgX, Standard, legacy ACES), forward and inverse
//!   comp     the comp's merge, matte and keyer programs (SkSL + CPU twins) and the key chain (COMP_CORE.md)
//!   grade    the one grade: operations in ACEScg / ACEScct, LUT nodes, CPU reference, SkSL, `.cube` bake
//!   matte_stats  matte numbers for `matte.read`: coverage, edge, holes, chatter, spill, screen, temporal, compare
pub mod comp;
pub mod convert;
pub mod grade;
pub mod lut;
pub mod matte_stats;
pub mod matrix;
pub mod spaces;
pub mod tf;
pub mod pipeline;
pub mod scope;
pub mod view;

pub use convert::{Transform, convert};
pub use lut::{Cube, CubeError, Interp, Lut, Lut1d, Lut3d};
pub use matrix::{Cat, Mat3};
pub use spaces::{Gamut, Space};
pub use tf::Curve;
pub use view::{Target, View};

/// One RGB triple, the unit every transform works on.
pub type Rgb = [f32; 3];
