//! CLAP and VST3 plugins: listed and rendered offline (clap/, vst3/), their state and parameters as
//! the document stores them (params.rs), their presets (presets.rs), opened for a person with their
//! own editor (session.rs, window.rs) and played live (live.rs).

pub mod clap;
#[cfg(windows)]
pub mod live;
pub mod params;
pub mod presets;
#[cfg(windows)]
pub mod session;
#[cfg(windows)]
pub mod vst3;
#[cfg(windows)]
pub mod window;

/// `rostrum-sound plugins`: the installed CLAP / VST3 plugins and their parameters (JSON).
pub fn list_cmd() -> Result<(), String> {
    let mut folders = clap::folders();
    let mut plugins = clap::scan();
    #[cfg(windows)]
    {
        folders.extend(vst3::folders());
        plugins.extend(vst3::scan());
    }
    println!("{}", serde_json::json!({ "folders": folders, "plugins": plugins }));
    Ok(())
}
