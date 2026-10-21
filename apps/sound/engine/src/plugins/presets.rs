//! `rostrum-sound plugin-presets <format> <path> <id>`: a plugin's presets by name, so a document can
//! name one ({ plugin: { name, preset: "Leads/Acid" } }) and the host resolve it to its file (and
//! key) once, when the preset is loaded into the document's state (session.rs). CLAP plugins say
//! where their presets are through the preset-discovery factory (its locations walked for the file
//! types it declares); VST3 presets are .vstpreset files in the standard folders.

use std::ffi::{CStr, CString};
use std::path::{Path, PathBuf};

use clack_extensions::preset_discovery::indexer::IndexerImpl;
use clack_extensions::preset_discovery::metadata_receiver::MetadataReceiverImpl;
use clack_extensions::preset_discovery::prelude::*;
use clack_extensions::preset_discovery::provider::Provider;
use clack_host::prelude::*;

#[derive(Default)]
struct Indexer {
    extensions: Vec<String>,
    locations: Vec<Option<PathBuf>>,
}
impl IndexerImpl for Indexer {
    fn declare_filetype(&mut self, t: FileType) -> Result<(), HostError> {
        self.extensions.push(t.file_extension.map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default());
        Ok(())
    }
    fn declare_location(&mut self, l: LocationInfo) -> Result<(), HostError> {
        self.locations.push(match l.location {
            Location::Plugin => None,
            Location::File { path } => Some(PathBuf::from(path.to_string_lossy().into_owned())),
        });
        Ok(())
    }
    fn declare_soundpack(&mut self, _: Soundpack) -> Result<(), HostError> {
        Ok(())
    }
}

/// The presets read from one location: (name, key, the plugin ids it is for).
#[derive(Default)]
struct Receiver {
    file: Option<String>,
    found: Vec<(String, Option<String>, Option<String>, Vec<String>)>,
}
impl MetadataReceiverImpl for Receiver {
    fn on_error(&mut self, _code: i32, _message: Option<&CStr>) {}
    fn begin_preset(&mut self, name: Option<&CStr>, key: Option<&CStr>) -> Result<(), HostError> {
        self.found.push((name.map(|n| n.to_string_lossy().into_owned()).unwrap_or_default(), self.file.clone(), key.map(|k| k.to_string_lossy().into_owned()), vec![]));
        Ok(())
    }
    fn add_plugin_id(&mut self, id: UniversalPluginId) {
        if let Some(p) = self.found.last_mut() {
            p.3.push(id.id.to_string_lossy().into_owned());
        }
    }
    fn set_soundpack_id(&mut self, _: &CStr) {}
    fn set_flags(&mut self, _: Flags) {}
    fn add_creator(&mut self, _: &CStr) {}
    fn set_description(&mut self, _: &CStr) {}
    fn set_timestamps(&mut self, _: Option<Timestamp>, _: Option<Timestamp>) {}
    fn add_feature(&mut self, _: &CStr) {}
    fn add_extra_info(&mut self, _: &CStr, _: &CStr) {}
}

fn walk(dir: &Path, exts: &[String], out: &mut Vec<PathBuf>) {
    let Ok(items) = std::fs::read_dir(dir) else { return };
    for p in items.flatten().map(|e| e.path()) {
        if p.is_dir() {
            walk(&p, exts, out);
        } else if exts.is_empty() || exts.iter().any(|e| e.is_empty() || p.extension().is_some_and(|x| x.to_string_lossy().eq_ignore_ascii_case(e))) {
            out.push(p);
        }
    }
}

fn clap(path: &str, id: &str) -> Result<Vec<serde_json::Value>, String> {
    let entry = unsafe { PluginEntry::load(path) }.map_err(|e| format!("{path}: cannot load: {e:?}"))?;
    let Some(factory) = entry.get_factory::<PresetDiscoveryFactory>() else { return Ok(vec![]) };
    let info = HostInfo::new("Rostrum", "Rostrum", "https://rostrum.studio", env!("CARGO_PKG_VERSION")).map_err(|e| format!("{e:?}"))?;
    let mut out = vec![];
    for d in factory.provider_descriptors() {
        let Some(pid) = d.id() else { continue };
        let Ok(mut provider) = Provider::instantiate(Indexer::default(), &entry, pid, &info) else { continue };
        let (exts, locations) = (provider.indexer().extensions.clone(), provider.indexer().locations.clone());
        let mut rx = Receiver::default();
        for loc in locations {
            match loc {
                None => {
                    rx.file = None;
                    provider.get_metadata(Location::Plugin, &mut rx);
                }
                Some(dir) => {
                    let mut files = vec![];
                    if dir.is_dir() { walk(&dir, &exts, &mut files) } else { files.push(dir) }
                    for f in files {
                        let Ok(c) = CString::new(f.to_string_lossy().into_owned()) else { continue };
                        rx.file = Some(f.to_string_lossy().into_owned());
                        provider.get_metadata(Location::File { path: &c }, &mut rx);
                    }
                }
            }
        }
        out.extend(rx.found.into_iter().filter(|p| p.3.is_empty() || p.3.iter().any(|i| i == id)).map(|(name, file, key, _)| serde_json::json!({ "name": name, "file": file, "key": key })));
    }
    Ok(out)
}

/// .vstpreset files for a plugin: <Documents>\VST3 Presets\<vendor>\<plugin> and the machine's.
fn vst3(name: &str, vendor: &str) -> Vec<serde_json::Value> {
    let mut roots = vec![];
    if let Some(home) = std::env::var_os("USERPROFILE") {
        roots.push(Path::new(&home).join("Documents").join("VST3 Presets"));
    }
    if let Some(data) = std::env::var_os("PROGRAMDATA") {
        roots.push(Path::new(&data).join("VST3 Presets"));
    }
    let mut files = vec![];
    for r in roots {
        walk(&r.join(vendor).join(name), &["vstpreset".into()], &mut files);
    }
    files.into_iter().map(|f| serde_json::json!({ "name": f.file_stem().map(|s| s.to_string_lossy().into_owned()), "file": f.to_string_lossy(), "key": null })).collect()
}

pub fn main(args: &[String]) -> Result<(), String> {
    let get = |i: usize| args.get(i).cloned().ok_or("usage: plugin-presets <clap|vst3> <path> <id> [<name> <vendor>]");
    let presets = match get(1)?.as_str() {
        "clap" => clap(&get(2)?, &get(3)?)?,
        "vst3" => vst3(&get(4).unwrap_or_default(), &get(5).unwrap_or_default()),
        f => return Err(format!("plugin format \"{f}\": clap or vst3")),
    };
    println!("{}", serde_json::json!({ "presets": presets }));
    Ok(())
}
