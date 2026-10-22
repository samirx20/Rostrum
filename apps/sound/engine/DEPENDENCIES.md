# RostrumSound engine: every crate it builds with (Windows target)

Made with `python apps/sound/engine/deps.py` (`cargo metadata --filter-platform x86_64-pc-windows-msvc`) on 2026-10-22. No GPL / AGPL / LGPL crate (the script refuses one). MPL-2.0: Symphonia (file-level copyleft: changes to those files stay MPL; we ship them unmodified). Vendored C++: Signalsmith Stretch (MIT), compiled in by build.rs.

Our own and vendored (patched) crates: rostrum-sound 0.1.0 (MIT), rustysynth 1.3.7 (MIT).

| Crate | Version | Licence |
|---|---|---|
| adler2 | 2.0.1 | 0BSD OR MIT OR Apache-2.0 |
| arrayvec | 0.7.8 | MIT OR Apache-2.0 |
| assert_type_match | 0.1.1 | MIT OR Apache-2.0 |
| async-task | 4.7.1 | Apache-2.0 OR MIT |
| atomic-waker | 1.1.2 | Apache-2.0 OR MIT |
| audio-codec-algorithms | 0.8.1 | 0BSD OR Apache-2.0 |
| audioadapter | 5.0.0 | MIT OR Apache-2.0 |
| audioadapter-buffers | 5.2.0 | MIT OR Apache-2.0 |
| audioadapter-sample | 5.2.0 | MIT OR Apache-2.0 |
| autocfg | 1.5.1 | Apache-2.0 OR MIT |
| bevy_ecs | 0.19.1 | MIT OR Apache-2.0 |
| bevy_ecs_macro_logic | 0.19.1 | MIT OR Apache-2.0 |
| bevy_ecs_macros | 0.19.1 | MIT OR Apache-2.0 |
| bevy_macro_utils | 0.19.1 | MIT OR Apache-2.0 |
| bevy_platform | 0.19.1 | MIT OR Apache-2.0 |
| bevy_ptr | 0.19.1 | MIT OR Apache-2.0 |
| bevy_reflect | 0.19.1 | MIT OR Apache-2.0 |
| bevy_reflect_derive | 0.19.1 | MIT OR Apache-2.0 |
| bevy_tasks | 0.19.1 | MIT OR Apache-2.0 |
| bevy_utils | 0.19.1 | MIT OR Apache-2.0 |
| bitflags | 1.3.2 | MIT/Apache-2.0 |
| bitflags | 2.13.2 | MIT OR Apache-2.0 |
| blake3 | 1.8.7 | CC0-1.0 OR Apache-2.0 OR Apache-2.0 WITH LLVM-exception |
| bumpalo | 3.20.3 | MIT OR Apache-2.0 |
| bytemuck | 1.25.2 | Zlib OR Apache-2.0 OR MIT |
| bytemuck_derive | 1.12.1 | Zlib OR Apache-2.0 OR MIT |
| cc | 1.7.0 | MIT OR Apache-2.0 |
| cfg-if | 1.0.5 | MIT OR Apache-2.0 |
| clack-common | 0.2.0 | MIT OR Apache-2.0 |
| clack-extensions | 0.2.0 | MIT OR Apache-2.0 |
| clack-host | 0.2.0 | MIT OR Apache-2.0 |
| clap-sys | 0.5.0 | MIT/Apache-2.0 |
| claxon | 0.4.3 | Apache-2.0 |
| com-scrape-types | 0.1.1 | MIT OR Apache-2.0 |
| concurrent-queue | 2.5.0 | Apache-2.0 OR MIT |
| constant_time_eq | 0.4.2 | CC0-1.0 OR MIT-0 OR Apache-2.0 |
| convert_case | 0.10.0 | MIT |
| core_detect | 1.0.0 | MIT/Apache-2.0 |
| cpal | 0.18.2 | Apache-2.0 |
| cpufeatures | 0.3.1 | MIT OR Apache-2.0 |
| crc32fast | 1.5.2 | MIT OR Apache-2.0 |
| critical-section | 1.2.0 | MIT OR Apache-2.0 |
| crossbeam-queue | 0.3.14 | MIT OR Apache-2.0 |
| crossbeam-utils | 0.8.23 | MIT OR Apache-2.0 |
| dasp_frame | 0.11.0 | MIT OR Apache-2.0 |
| dasp_sample | 0.11.0 | MIT OR Apache-2.0 |
| derive_more | 2.1.1 | MIT |
| derive_more-impl | 2.1.1 | MIT |
| disqualified | 1.1.0 | MIT OR Apache-2.0 |
| downcast-rs | 2.0.2 | MIT OR Apache-2.0 |
| ebur128 | 0.1.10 | MIT |
| encoding_rs | 0.8.42 | (Apache-2.0 OR MIT) AND BSD-3-Clause |
| equivalent | 1.0.2 | Apache-2.0 OR MIT |
| erased-serde | 0.4.10 | MIT OR Apache-2.0 |
| extended | 0.1.0 | MIT |
| fdeflate | 0.3.7 | MIT OR Apache-2.0 |
| find-msvc-tools | 0.1.14 | MIT OR Apache-2.0 |
| firewheel | 0.14.0 | MIT OR Apache-2.0 |
| firewheel-core | 0.14.0 | MIT OR Apache-2.0 |
| firewheel-cpal | 0.14.0 | MIT OR Apache-2.0 |
| firewheel-graph | 0.14.0 | MIT OR Apache-2.0 |
| firewheel-macros | 0.14.0 | MIT OR Apache-2.0 |
| firewheel-nodes | 0.14.0 | MIT OR Apache-2.0 |
| fixed-resample | 0.13.0 | MIT |
| fixedbitset | 0.5.7 | MIT OR Apache-2.0 |
| flate2 | 1.1.10 | MIT OR Apache-2.0 |
| foldhash | 0.2.0 | Zlib |
| freeverb | 0.2.0 | MIT |
| futures-core | 0.3.34 | MIT OR Apache-2.0 |
| futures-lite | 2.6.1 | Apache-2.0 OR MIT |
| getrandom | 0.4.3 | MIT OR Apache-2.0 |
| glam | 0.29.3 | MIT OR Apache-2.0 |
| glam | 0.30.10 | MIT OR Apache-2.0 |
| glam | 0.31.1 | MIT OR Apache-2.0 |
| glam | 0.32.1 | MIT OR Apache-2.0 |
| hashbrown | 0.16.1 | MIT OR Apache-2.0 |
| hashbrown | 0.17.1 | MIT OR Apache-2.0 |
| indexmap | 2.14.2 | Apache-2.0 OR MIT |
| itoa | 1.0.18 | MIT OR Apache-2.0 |
| lazy_static | 1.5.1 | MIT OR Apache-2.0 |
| libloading | 0.8.9 | ISC |
| log | 0.4.34 | MIT OR Apache-2.0 |
| memchr | 2.8.3 | Unlicense OR MIT |
| miniz_oxide | 0.8.9 | MIT OR Zlib OR Apache-2.0 |
| miniz_oxide | 0.9.1 | MIT OR Zlib OR Apache-2.0 |
| multiversion_no_op | 1.0.0 | Apache-2.0 OR MIT |
| nonmax | 0.5.5 | MIT OR Apache-2.0 |
| num-complex | 0.4.6 | MIT OR Apache-2.0 |
| num-integer | 0.1.47 | MIT OR Apache-2.0 |
| num-traits | 0.2.19 | MIT OR Apache-2.0 |
| pin-project-lite | 0.2.17 | Apache-2.0 OR MIT |
| png | 0.18.1 | MIT OR Apache-2.0 |
| portable-atomic | 1.15.0 | Apache-2.0 OR MIT |
| portable-atomic-util | 0.2.8 | Apache-2.0 OR MIT |
| primal-check | 0.3.4 | MIT OR Apache-2.0 |
| proc-macro2 | 1.0.107 | MIT OR Apache-2.0 |
| quote | 1.0.47 | MIT OR Apache-2.0 |
| raw-window-handle | 0.6.2 | MIT OR Apache-2.0 OR Zlib |
| realfft | 3.5.0 | MIT |
| ringbuf | 0.5.3 | MIT OR Apache-2.0 |
| rubato | 5.0.1 | MIT OR Apache-2.0 |
| rustc_version | 0.4.1 | MIT OR Apache-2.0 |
| rustfft | 6.4.1 | MIT OR Apache-2.0 |
| rustversion | 1.0.23 | MIT OR Apache-2.0 |
| scopeguard | 1.2.0 | MIT OR Apache-2.0 |
| semver | 1.0.28 | MIT OR Apache-2.0 |
| serde | 1.0.229 | MIT OR Apache-2.0 |
| serde_core | 1.0.229 | MIT OR Apache-2.0 |
| serde_derive | 1.0.229 | MIT OR Apache-2.0 |
| serde_json | 1.0.152 | MIT OR Apache-2.0 |
| shlex | 2.0.1 | MIT OR Apache-2.0 |
| simd-adler32 | 0.3.10 | MIT |
| simdutf8 | 0.1.5 | MIT OR Apache-2.0 |
| slotmap | 1.1.1 | Zlib |
| smallvec | 1.16.3 | MIT OR Apache-2.0 |
| smol_str | 0.2.2 | MIT OR Apache-2.0 |
| spin | 0.10.1 | MIT |
| strength_reduce | 0.2.4 | MIT OR Apache-2.0 |
| symphonia | 0.5.5 | MPL-2.0 |
| symphonia-bundle-flac | 0.5.5 | MPL-2.0 |
| symphonia-bundle-mp3 | 0.5.5 | MPL-2.0 |
| symphonia-codec-aac | 0.5.5 | MPL-2.0 |
| symphonia-codec-pcm | 0.5.5 | MPL-2.0 |
| symphonia-codec-vorbis | 0.5.5 | MPL-2.0 |
| symphonia-core | 0.5.5 | MPL-2.0 |
| symphonia-format-isomp4 | 0.5.5 | MPL-2.0 |
| symphonia-format-ogg | 0.5.5 | MPL-2.0 |
| symphonia-format-riff | 0.5.5 | MPL-2.0 |
| symphonia-metadata | 0.5.5 | MPL-2.0 |
| symphonia-utils-xiph | 0.5.5 | MPL-2.0 |
| syn | 2.0.119 | MIT OR Apache-2.0 |
| syn | 3.0.7 | MIT OR Apache-2.0 |
| thiserror | 2.0.21 | MIT OR Apache-2.0 |
| thiserror-impl | 2.0.21 | MIT OR Apache-2.0 |
| thread_local | 1.1.10 | MIT OR Apache-2.0 |
| thunderdome | 0.6.1 | MIT OR Apache-2.0 |
| toml_datetime | 0.7.5+spec-1.1.0 | MIT OR Apache-2.0 |
| toml_datetime | 1.1.2+spec-1.1.0 | MIT OR Apache-2.0 |
| toml_edit | 0.23.10+spec-1.0.0 | MIT OR Apache-2.0 |
| toml_edit | 0.25.17+spec-1.1.0 | MIT OR Apache-2.0 |
| toml_parser | 1.1.5+spec-1.1.0 | MIT OR Apache-2.0 |
| transpose | 0.2.3 | MIT OR Apache-2.0 |
| triple_buffer | 9.0.0 | MPL-2.0 |
| typeid | 1.0.3 | MIT OR Apache-2.0 |
| unicode-ident | 1.0.26 | (MIT OR Apache-2.0) AND Unicode-3.0 |
| unicode-segmentation | 1.13.3 | MIT OR Apache-2.0 |
| unicode-xid | 0.2.6 | MIT OR Apache-2.0 |
| uuid | 1.28.0 | Apache-2.0 OR MIT |
| variadics_please | 1.1.0 | MIT OR Apache-2.0 |
| version_check | 0.9.5 | MIT/Apache-2.0 |
| visibility | 0.1.1 | Zlib OR MIT OR Apache-2.0 |
| vst3 | 0.3.0 | MIT OR Apache-2.0 |
| wgpu-types | 29.0.4 | MIT OR Apache-2.0 |
| windowfunctions | 0.1.1 | MIT |
| windows | 0.62.2 | MIT OR Apache-2.0 |
| windows-collections | 0.3.2 | MIT OR Apache-2.0 |
| windows-core | 0.62.2 | MIT OR Apache-2.0 |
| windows-future | 0.3.2 | MIT OR Apache-2.0 |
| windows-implement | 0.60.2 | MIT OR Apache-2.0 |
| windows-interface | 0.59.3 | MIT OR Apache-2.0 |
| windows-link | 0.2.1 | MIT OR Apache-2.0 |
| windows-numerics | 0.3.1 | MIT OR Apache-2.0 |
| windows-result | 0.4.1 | MIT OR Apache-2.0 |
| windows-strings | 0.5.1 | MIT OR Apache-2.0 |
| windows-sys | 0.61.2 | MIT OR Apache-2.0 |
| windows-threading | 0.2.1 | MIT OR Apache-2.0 |
| winnow | 0.7.15 | MIT |
| winnow | 1.0.4 | MIT |
| wmidi | 4.0.11 | MIT |
| zlib-rs | 0.6.8 | Zlib |
| zmij | 1.0.23 | MIT |
