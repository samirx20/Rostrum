//! rostrum2d-render: Rostrum2D's renderer (apps/2d/engine/README.md). The stage page is laid out by Blitz
//! (Stylo + Taffy + Parley; our patched copies in ../vendor/) and painted by Skia on the GPU.
//!   rostrum2d-render serve                         the renderer process the host drives (serve.rs)
//!   rostrum2d-render glyphs                        text laid out as outlines for the host (glyphs.rs)
//!   rostrum2d-render styles                        the computed CSS each class set declares (styles.rs)
//!   rostrum2d-render cube | sksl | scope           colour helpers: a .cube as a table, view / grade programs, scopes

mod asset_cache;
mod assets;
mod boxes;
mod color;
mod cube;
mod glyphs;
mod grade_cmd;
mod keep;
mod painter;
mod pixels;
mod readback;
mod scene;
mod scene_serve;
mod scopes;
mod serve;
mod sink;
mod sksl;
mod styles;
#[cfg(test)]
mod cliptext_tests;
#[cfg(test)]
mod cold_warm_tests;
#[cfg(test)]
mod depth_tests;
#[cfg(test)]
mod incremental_tests;
#[cfg(test)]
mod opsz_tests;
#[cfg(test)]
mod seam_tests;
#[cfg(test)]
mod shader_tests;
#[cfg(test)]
mod tilt_tests;

/// Hybrid-GPU laptops: paint on the discrete GPU (read by the NVIDIA / AMD drivers; exported by build.rs).
/// On Sam's laptop (AMD Radeon integrated + RTX 3050) GL otherwise opens on the integrated GPU.
#[no_mangle]
#[used]
pub static NvOptimusEnablement: u32 = 1;
#[no_mangle]
#[used]
pub static AmdPowerXpressRequestHighPerformance: u32 = 1;

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        Some("serve") => serve::run(),
        Some("glyphs") => glyphs::run(),
        Some("styles") => styles::run(),
        Some("cube") => cube::run(&args[1..]),
        Some("sksl") => sksl::run(&args[1..]),
        Some("scope") => scopes::run_cli(&args[1..]),
        _ => {
            eprintln!("usage: rostrum2d-render serve | glyphs | styles | cube <file.cube> <table.f32> | sksl display-in <view> <target> | scope <spec.json>");
            std::process::exit(2);
        }
    }
}
