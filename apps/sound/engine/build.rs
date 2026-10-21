// Compiles the vendored Signalsmith Stretch (MIT, header-only C++) and Rostrum's C shim over it (src/stretch.rs).
fn main() {
    let dir = std::path::Path::new("vendor/signalsmith-stretch");
    println!("cargo::rerun-if-changed=vendor/signalsmith-stretch");
    cc::Build::new()
        .cpp(true)
        .std("c++14")
        .opt_level(3)
        .define("NDEBUG", None)
        .include(dir)
        .file(dir.join("rostrum_stretch.cpp"))
        .compile("rostrum_stretch");
}
