mod avar; // Rostrum patch (H5): undo `avar` before Skia sees variation coords
mod image_renderer;
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
