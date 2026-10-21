//! A VST3 class instantiated: its component and edit controller, and its saved state (`RVS3`, read
//! from the document or from a .vstpreset file).

use std::ffi::c_void;

use vst3::Steinberg::Vst::*;
use vst3::Steinberg::*;
use vst3::{ComPtr, ComWrapper, Interface};

use super::com::{HostApp, Stream};
use super::text16;
/// A class instantiated and initialized: its component, and its edit controller (the component itself, or a separate one).
pub(crate) struct Plugin {
    pub(crate) component: ComPtr<IComponent>,
    pub(crate) controller: Option<ComPtr<IEditController>>,
    _host: ComWrapper<HostApp>,
}

impl Plugin {
    pub(crate) fn new(f: &ComPtr<IPluginFactory>, cid: &TUID, who: &str) -> Result<Plugin, String> {
        unsafe {
            let host = ComWrapper::new(HostApp);
            let context = host.as_com_ref::<IHostApplication>().unwrap().as_ptr() as *mut FUnknown;
            let mut obj: *mut c_void = std::ptr::null_mut();
            if f.createInstance(cid.as_ptr(), IComponent::IID.as_ptr() as *const i8, &mut obj) != kResultOk {
                return Err(format!("{who}: the factory would not create it"));
            }
            let component = ComPtr::<IComponent>::from_raw(obj as *mut IComponent).ok_or(format!("{who}: no component"))?;
            if component.initialize(context) != kResultOk {
                return Err(format!("{who}: would not initialize"));
            }
            let controller = component.cast::<IEditController>().or_else(|| {
                let mut ccid: TUID = [0; 16];
                if component.getControllerClassId(&mut ccid) != kResultOk {
                    return None;
                }
                let mut c: *mut c_void = std::ptr::null_mut();
                if f.createInstance(ccid.as_ptr(), IEditController::IID.as_ptr() as *const i8, &mut c) != kResultOk {
                    return None;
                }
                let c = ComPtr::<IEditController>::from_raw(c as *mut IEditController)?;
                (c.initialize(context) == kResultOk).then_some(c)
            });
            // A separate controller learns about its component through their connection points (the spec's host duty;
            // JUCE plugins list no parameters until connected).
            if let (Some(ctl), None) = (&controller, component.cast::<IEditController>()) {
                if let (Some(a), Some(b)) = (component.cast::<IConnectionPoint>(), ctl.cast::<IConnectionPoint>()) {
                    a.connect(b.as_ptr());
                    b.connect(a.as_ptr());
                }
            }
            Ok(Plugin { component, controller, _host: host })
        }
    }

    /// Sets a saved state (`RVS3`: the component's bytes, then the controller's), the controller told the component's too.
    pub(crate) fn set_state(&self, blob: &[u8]) -> Result<(), String> {
        let (comp, ctrl) = unpack(blob)?;
        unsafe {
            let s = Stream::new(comp.to_vec());
            if self.component.setState(s.as_com_ref::<IBStream>().unwrap().as_ptr()) != kResultOk {
                return Err("it refused its saved state".into());
            }
            if let Some(c) = &self.controller {
                let s = Stream::new(comp.to_vec());
                c.setComponentState(s.as_com_ref::<IBStream>().unwrap().as_ptr());
                if !ctrl.is_empty() {
                    let s = Stream::new(ctrl.to_vec());
                    c.setState(s.as_com_ref::<IBStream>().unwrap().as_ptr());
                }
            }
        }
        Ok(())
    }

    /// Its state now, as `RVS3`.
    pub(crate) fn get_state(&self) -> Result<Vec<u8>, String> {
        unsafe {
            let comp = Stream::new(vec![]);
            if self.component.getState(comp.as_com_ref::<IBStream>().unwrap().as_ptr()) != kResultOk {
                return Err("it would not save its state".into());
            }
            let ctrl = Stream::new(vec![]);
            if let Some(c) = &self.controller {
                c.getState(ctrl.as_com_ref::<IBStream>().unwrap().as_ptr());
            }
            let (comp, ctrl) = (comp.0.borrow().0.clone(), ctrl.0.borrow().0.clone());
            Ok(pack(&comp, &ctrl))
        }
    }

    pub(super) fn params(&self) -> Vec<serde_json::Value> {
        let Some(c) = &self.controller else { return vec![] };
        unsafe {
            (0..c.getParameterCount())
                .filter_map(|i| {
                    let mut p: ParameterInfo = std::mem::zeroed();
                    (c.getParameterInfo(i, &mut p) == kResultOk).then(|| {
                        // Values stay normalized 0 … 1 (what the document stores and the engine sends); the plain
                        // range, unit and step count are what the plugin shows ("-60 … 6 dB", 4 steps).
                        let mut q = serde_json::json!({ "id": p.id, "name": text16(&p.title), "module": "", "min": 0.0, "max": 1.0, "default": p.defaultNormalizedValue });
                        let (lo, hi) = (c.normalizedParamToPlain(p.id, 0.0), c.normalizedParamToPlain(p.id, 1.0));
                        if lo.is_finite() && hi.is_finite() && (lo, hi) != (0.0, 1.0) {
                            q["plainMin"] = lo.into();
                            q["plainMax"] = hi.into();
                        }
                        let unit = text16(&p.units);
                        if !unit.trim().is_empty() {
                            q["unit"] = unit.trim().into();
                        }
                        if p.stepCount > 0 {
                            q["steps"] = p.stepCount.into();
                        }
                        q
                    })
                })
                .collect()
        }
    }
}

/// A VST3 plugin's saved state as the document carries it: "RVS3", the component's bytes, the controller's (each length-prefixed).
pub(crate) fn pack(comp: &[u8], ctrl: &[u8]) -> Vec<u8> {
    let mut out = b"RVS3".to_vec();
    for part in [comp, ctrl] {
        out.extend((part.len() as u32).to_le_bytes());
        out.extend(part);
    }
    out
}

pub(crate) fn unpack(blob: &[u8]) -> Result<(&[u8], &[u8]), String> {
    let bad = || "not a VST3 state (RVS3)".to_string();
    if blob.get(..4) != Some(b"RVS3") {
        return Err(bad());
    }
    let mut at = 4;
    let mut part = || -> Result<&[u8], String> {
        let n = u32::from_le_bytes(blob.get(at..at + 4).ok_or_else(bad)?.try_into().unwrap()) as usize;
        let p = blob.get(at + 4..at + 4 + n).ok_or_else(bad)?;
        at += 4 + n;
        Ok(p)
    };
    Ok((part()?, part()?))
}

/// A .vstpreset file: its component ("Comp") and controller ("Cont") chunks, as `RVS3`.
pub(crate) fn vstpreset(bytes: &[u8]) -> Result<Vec<u8>, String> {
    let bad = |why: &str| format!("not a .vstpreset ({why})");
    if bytes.get(..4) != Some(b"VST3") || bytes.len() < 48 {
        return Err(bad("no VST3 header"));
    }
    let list = i64::from_le_bytes(bytes[40..48].try_into().unwrap()) as usize;
    if bytes.get(list..list + 4) != Some(b"List") {
        return Err(bad("no chunk list"));
    }
    let count = i32::from_le_bytes(bytes.get(list + 4..list + 8).ok_or(bad("short"))?.try_into().unwrap()) as usize;
    let (mut comp, mut ctrl): (&[u8], &[u8]) = (&[], &[]);
    for k in 0..count {
        let e = list + 8 + k * 20;
        let entry = bytes.get(e..e + 20).ok_or(bad("short chunk list"))?;
        let (off, size) = (i64::from_le_bytes(entry[4..12].try_into().unwrap()) as usize, i64::from_le_bytes(entry[12..20].try_into().unwrap()) as usize);
        let data = bytes.get(off..off + size).ok_or(bad("a chunk past the end"))?;
        match &entry[..4] {
            b"Comp" => comp = data,
            b"Cont" => ctrl = data,
            _ => {}
        }
    }
    if comp.is_empty() {
        return Err(bad("no component state"));
    }
    Ok(pack(comp, ctrl))
}
