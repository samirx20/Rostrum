//! VST3 plugins (S4) through the `vst3` bindings (MIT / Apache-2.0; the VST 3 SDK is MIT since 3.8):
//! the same contract as plugins/clap/ — the user's installed plugins listed with their parameters (VST3
//! parameters are normalized, 0 … 1), and rendered offline in fixed 256-sample blocks with notes and
//! parameter changes timed to the sample. We implement the host side (host application, event list,
//! parameter changes, a memory stream) as COM objects and drive the component, its processor and
//! its controller. A saved state (the component's and the controller's, `RVS3` below) is set before
//! it plays; automated parameters follow their envelopes (plugins/params.rs `Automation`).

#![allow(unsafe_op_in_unsafe_fn)]

mod com;
mod plugin;
pub mod render;
pub mod session;
#[cfg(test)]
mod tests;

use std::path::{Path, PathBuf};

use vst3::Steinberg::*;
use vst3::ComPtr;
use windows::core::{s, HSTRING};
use windows::Win32::Foundation::HMODULE;
use windows::Win32::System::LibraryLoader::{GetProcAddress, LoadLibraryW};

use plugin::Plugin;

/// The folders VST3 plugins are installed in (VST3_PATH first, then per user and per machine).
pub fn folders() -> Vec<PathBuf> {
    let mut out: Vec<PathBuf> = std::env::var_os("VST3_PATH").map(|p| std::env::split_paths(&p).collect()).unwrap_or_default();
    if let Some(local) = std::env::var_os("LOCALAPPDATA") {
        out.push(Path::new(&local).join("Programs").join("Common").join("VST3"));
    }
    if let Some(common) = std::env::var_os("COMMONPROGRAMFILES") {
        out.push(Path::new(&common).join("VST3"));
    }
    out
}

/// The DLL in a .vst3 bundle (or the file itself, the older single-file layout).
fn binary(bundle: &Path) -> PathBuf {
    if bundle.is_dir() {
        let stem = bundle.file_stem().map(|s| s.to_os_string()).unwrap_or_default();
        bundle.join("Contents").join("x86_64-win").join(Path::new(&stem).with_extension("vst3"))
    } else {
        bundle.to_path_buf()
    }
}

fn text(chars: &[i8]) -> String {
    let bytes: Vec<u8> = chars.iter().take_while(|&&c| c != 0).map(|&c| c as u8).collect();
    String::from_utf8_lossy(&bytes).into_owned()
}

fn text16(chars: &[u16]) -> String {
    String::from_utf16_lossy(&chars[..chars.iter().position(|&c| c == 0).unwrap_or(chars.len())])
}

/// A loaded plugin module: its factory (the DLL stays loaded for the process: plugins rarely unload cleanly).
pub(crate) fn factory(path: &Path) -> Result<ComPtr<IPluginFactory>, String> {
    let dll = binary(path);
    unsafe {
        let module: HMODULE = LoadLibraryW(&HSTRING::from(dll.as_os_str())).map_err(|e| format!("{}: cannot load ({})", dll.display(), e.message()))?;
        if let Some(init) = GetProcAddress(module, s!("InitDll")) {
            let init: extern "system" fn() -> bool = std::mem::transmute(init);
            init();
        }
        let get = GetProcAddress(module, s!("GetPluginFactory")).ok_or(format!("{}: not a VST3 module (no GetPluginFactory)", dll.display()))?;
        let get: extern "system" fn() -> *mut IPluginFactory = std::mem::transmute(get);
        ComPtr::from_raw(get()).ok_or(format!("{}: no plugin factory", dll.display()))
    }
}

/// An audio class of the factory: its id, name, and whether it is an instrument.
struct ClassEntry {
    cid: TUID,
    name: String,
    instrument: bool,
    vendor: String,
}

fn classes(f: &ComPtr<IPluginFactory>) -> Vec<ClassEntry> {
    let f2 = f.cast::<IPluginFactory2>();
    let mut out = vec![];
    unsafe {
        for i in 0..f.countClasses() {
            let mut info: PClassInfo = std::mem::zeroed();
            if f.getClassInfo(i, &mut info) != kResultOk || text(&info.category) != "Audio Module Class" {
                continue;
            }
            let (mut sub, mut vendor) = (String::new(), String::new());
            if let Some(f2) = &f2 {
                let mut i2: PClassInfo2 = std::mem::zeroed();
                if f2.getClassInfo2(i, &mut i2) == kResultOk {
                    sub = text(&i2.subCategories);
                    vendor = text(&i2.vendor);
                }
            }
            out.push(ClassEntry { cid: info.cid, name: text(&info.name), instrument: sub.split('|').any(|s| s == "Instrument"), vendor });
        }
    }
    out
}

/// A class id from its hex form (as `scan` lists it).
pub(crate) fn cid_of(id: &str) -> TUID {
    std::array::from_fn(|i| u8::from_str_radix(id.get(2 * i..2 * i + 2).unwrap_or("00"), 16).unwrap_or(0) as i8)
}

/// Every plugin in the VST3 bundles there: what it is and its parameters.
pub fn scan() -> Vec<serde_json::Value> {
    let mut out = vec![];
    for dir in folders() {
        let Ok(items) = std::fs::read_dir(&dir) else { continue };
        for bundle in items.flatten().map(|e| e.path()).filter(|p| p.extension().is_some_and(|x| x.eq_ignore_ascii_case("vst3"))) {
            match describe(&bundle) {
                Ok(list) => out.extend(list),
                Err(e) => out.push(serde_json::json!({ "format": "vst3", "path": bundle.to_string_lossy(), "error": e })),
            }
        }
    }
    out
}

/// The plugins in one VST3 bundle (what `scan` lists for each; the contract's `plugins` request).
pub fn describe(bundle: &Path) -> Result<Vec<serde_json::Value>, String> {
    let path = bundle.to_string_lossy().into_owned();
    let f = factory(bundle)?;
    Ok(classes(&f).into_iter().map(|c| {
        let plugin = Plugin::new(&f, &c.cid, &c.name).ok();
        let params = plugin.as_ref().map(|p| p.params()).unwrap_or_default();
        let has_window = plugin.as_ref().is_some_and(|p| p.has_editor());
        let id: String = c.cid.iter().map(|b| format!("{:02X}", *b as u8)).collect();
        serde_json::json!({ "format": "vst3", "path": path, "id": id, "name": c.name, "vendor": c.vendor, "kind": if c.instrument { "instrument" } else { "effect" }, "features": [], "params": params, "hasWindow": has_window })
    }).collect())
}
