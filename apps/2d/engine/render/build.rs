// Hybrid-GPU laptops (NVIDIA Optimus, AMD PowerXpress) give an .exe the discrete GPU only when it exports
// these two symbols (src/main.rs); Rust does not export a binary's statics, so the linker is told to.
// Media Foundation (MP4 export, encode_mp4.rs) is delay-loaded: its DLLs load only when an MP4 is written, so the
// engine still starts on a Windows without them ("N" editions without the Media Feature Pack). encode_mp4.rs reads
// the same list (ROSTRUM_DELAYED_DLLS) and checks each DLL is there before its first call.
const DELAYED: &[&str] = &["mfplat.dll", "mfreadwrite.dll"];

fn main() {
    println!("cargo:rustc-env=ROSTRUM_DELAYED_DLLS={}", DELAYED.join(";"));
    if std::env::var("CARGO_CFG_TARGET_ENV").as_deref() == Ok("msvc") {
        println!("cargo:rustc-link-arg-bins=/EXPORT:NvOptimusEnablement");
        println!("cargo:rustc-link-arg-bins=/EXPORT:AmdPowerXpressRequestHighPerformance");
        for dll in DELAYED {
            println!("cargo:rustc-link-arg-bins=/DELAYLOAD:{dll}");
        }
        println!("cargo:rustc-link-arg-bins=delayimp.lib");
    }
}
