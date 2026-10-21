// Hybrid-GPU laptops (NVIDIA Optimus, AMD PowerXpress) give an .exe the discrete GPU only when it exports
// these two symbols (src/main.rs); Rust does not export a binary's statics, so the linker is told to.
fn main() {
    if std::env::var("CARGO_CFG_TARGET_ENV").as_deref() == Ok("msvc") {
        println!("cargo:rustc-link-arg-bins=/EXPORT:NvOptimusEnablement");
        println!("cargo:rustc-link-arg-bins=/EXPORT:AmdPowerXpressRequestHighPerformance");
    }
}
