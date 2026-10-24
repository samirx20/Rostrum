mod avar; // Rostrum patch (H5): undo `avar` before Skia sees variation coords
mod image_renderer;
pub mod layer_census; // Rostrum patch (export speed): which code opens each layer, when profiling
mod plane; // Rostrum patch (round 14, H5): what part of a tilted plane is on screen / in front
mod scene;
mod window_renderer;
pub mod working_space;

// Backends
mod cache;
#[cfg(any(target_os = "macos", target_os = "ios"))]
mod metal;
#[cfg(not(any(target_os = "macos", target_os = "ios")))]
mod opengl;
#[cfg(feature = "vulkan")]
mod vulkan;

pub use image_renderer::SkiaImageRenderer;
pub use scene::{SkiaSceneCache, SkiaScenePainter};
pub use window_renderer::*;
