//! A VST3 plugin opened for a person (plugins/session.rs): its saved state or a .vstpreset set, the
//! document's parameter values applied, its editor (IPlugView) embedded in our window, and it
//! playing live. VST3 splits a plugin in two — the controller (the editor's side) and the processor
//! — and the host carries edits between them: what the person turns in the editor (performEdit,
//! IComponentHandler) reaches the processor as parameter changes on the next block, so what they
//! hear and the state saved afterwards agree.

#![allow(unsafe_op_in_unsafe_fn)]

use std::cell::Cell;
use std::ffi::c_void;
use std::path::Path;

use vst3::Steinberg::Vst::*;
use vst3::Steinberg::*;
use vst3::{ComPtr, ComWrapper};

use crate::plugins::session::{Note, Proc, Session, SessionSpec};
use crate::plugins::window::Window;
use super::com::{Changes, Edits, Events, Frame, Handler};
use super::plugin::Plugin;
use super::{cid_of, factory};

pub struct Vst3Session {
    _factory: ComPtr<IPluginFactory>,
    plugin: Plugin,
    handler: ComWrapper<Handler>,
    frame: ComWrapper<Frame>,
    view: Option<ComPtr<IPlugView>>,
    edits: Edits,
    params: Vec<u32>,
    effect: bool,
    active: bool,
    who: String,
}

/// The processor on the audio thread (its COM pointer is used from there only while it plays).
struct Vst3Proc {
    processor: ComPtr<IAudioProcessor>,
    edits: Edits,
    effect: bool,
    processing: bool,
    events: ComWrapper<Events>,
    changes: ComWrapper<Changes>,
}
unsafe impl Send for Vst3Proc {}

impl Vst3Session {
    pub fn new(spec: &SessionSpec) -> Result<Vst3Session, String> {
        let p = &spec.plugin;
        let who = format!("plugin {} ({})", p.id, p.path);
        let f = factory(Path::new(&p.path))?;
        let plugin = Plugin::new(&f, &cid_of(&p.id), &who)?;
        let edits: Edits = Default::default();
        let handler = ComWrapper::new(Handler(edits.clone()));
        if let Some(c) = &plugin.controller {
            unsafe { c.setComponentHandler(handler.as_com_ref::<IComponentHandler>().unwrap().as_ptr()) };
        }
        if let Some(state) = &p.state {
            plugin.set_state(&crate::plugins::params::unbase64(state)?).map_err(|e| format!("{who}: {e}"))?;
        }
        if let Some(preset) = &spec.preset {
            if preset.key.is_some() {
                return Err(format!("{who}: a VST3 preset is a .vstpreset file (no key)"));
            }
            let file = preset.file.as_deref().ok_or(format!("{who}: a VST3 preset is a .vstpreset file"))?;
            let bytes = std::fs::read(file).map_err(|e| format!("{file}: {e}"))?;
            plugin.set_state(&super::plugin::vstpreset(&bytes).map_err(|e| format!("{file}: {e}"))?).map_err(|e| format!("{who}: {e}"))?;
        }
        // The document's fixed values over the preset, on both sides.
        for (id, v) in &p.params {
            if let crate::mix::schedule::Param::Value(x) = v {
                if let Some(c) = &plugin.controller {
                    unsafe { c.setParamNormalized(*id, *x) };
                }
                edits.lock().unwrap().push((*id, *x));
            }
        }
        Ok(Vst3Session { _factory: f, plugin, handler, frame: ComWrapper::new(Frame(Cell::new(None))), view: None, edits, params: p.params.iter().map(|(id, _)| *id).collect(), effect: spec.effect, active: false, who })
    }
}

impl Proc for Vst3Proc {
    fn process(&mut self, input: (&[f32], &[f32]), out: (&mut [f32], &mut [f32]), notes: &[Note]) -> Result<(), String> {
        unsafe {
            if !self.processing {
                self.processor.setProcessing(1);
                self.processing = true;
            }
            self.events.0.borrow_mut().clear();
            self.changes.0.borrow_mut().clear();
            for &(o, key, vel) in notes {
                let mut e: Event = std::mem::zeroed();
                e.sampleOffset = o as int32;
                if vel > 0.0 {
                    e.r#type = Event_::EventTypes_::kNoteOnEvent as u16;
                    e.__field0.noteOn = NoteOnEvent { channel: 0, pitch: key as int16, tuning: 0.0, velocity: vel as f32, length: 0, noteId: -1 };
                } else {
                    e.r#type = Event_::EventTypes_::kNoteOffEvent as u16;
                    e.__field0.noteOff = NoteOffEvent { channel: 0, pitch: key as int16, velocity: 0.0, noteId: -1, tuning: 0.0 };
                }
                self.events.0.borrow_mut().push(e);
            }
            if let Ok(mut edits) = self.edits.try_lock() {
                for (id, v) in edits.drain(..) {
                    let mut i = 0;
                    if let Some(q) = vst3::ComRef::from_raw(self.changes.addParameterData(&id, &mut i)) {
                        q.addPoint(0, v, std::ptr::null_mut());
                    }
                }
            }
            let n = out.0.len();
            let (mut il, mut ir) = (input.0[..n].to_vec(), input.1[..n].to_vec());
            let (ol, or) = out;
            let mut in_ptrs = [il.as_mut_ptr(), ir.as_mut_ptr()];
            let mut out_ptrs = [ol.as_mut_ptr(), or.as_mut_ptr()];
            let mut inb = AudioBusBuffers { numChannels: 2, silenceFlags: 0, __field0: AudioBusBuffers__type0 { channelBuffers32: in_ptrs.as_mut_ptr() } };
            let mut outb = AudioBusBuffers { numChannels: 2, silenceFlags: 0, __field0: AudioBusBuffers__type0 { channelBuffers32: out_ptrs.as_mut_ptr() } };
            let mut data = ProcessData {
                processMode: ProcessModes_::kRealtime as int32,
                symbolicSampleSize: SymbolicSampleSizes_::kSample32 as int32,
                numSamples: n as int32,
                numInputs: if self.effect { 1 } else { 0 },
                numOutputs: 1,
                inputs: if self.effect { &mut inb } else { std::ptr::null_mut() },
                outputs: &mut outb,
                inputParameterChanges: self.changes.as_com_ref::<IParameterChanges>().unwrap().as_ptr(),
                outputParameterChanges: std::ptr::null_mut(),
                inputEvents: self.events.as_com_ref::<IEventList>().unwrap().as_ptr(),
                outputEvents: std::ptr::null_mut(),
                processContext: std::ptr::null_mut(),
            };
            if self.processor.process(&mut data) != kResultOk {
                return Err("process failed".into());
            }
        }
        Ok(())
    }
    fn into_any(self: Box<Self>) -> Box<dyn std::any::Any> {
        self
    }
}

impl Vst3Session {
    fn close_proc(&mut self, p: Box<dyn Proc>) {
        if let Ok(p) = p.into_any().downcast::<Vst3Proc>() {
            unsafe {
                if p.processing {
                    p.processor.setProcessing(0);
                }
                self.plugin.component.setActive(0);
            }
        }
        self.active = false;
    }
}

impl Session for Vst3Session {
    fn activate(&mut self, rate: f64, max_frames: u32) -> Result<Box<dyn Proc>, String> {
        let c = &self.plugin.component;
        let processor = c.cast::<IAudioProcessor>().ok_or(format!("{}: no audio processor", self.who))?;
        unsafe {
            let mut stereo: SpeakerArrangement = SpeakerArr::kStereo;
            let mut out_arr = [stereo];
            processor.setBusArrangements(&mut stereo, if self.effect { 1 } else { 0 }, out_arr.as_mut_ptr(), 1);
            if self.effect {
                c.activateBus(MediaTypes_::kAudio as MediaType, BusDirections_::kInput as BusDirection, 0, 1);
            }
            c.activateBus(MediaTypes_::kAudio as MediaType, BusDirections_::kOutput as BusDirection, 0, 1);
            if !self.effect && c.getBusCount(MediaTypes_::kEvent as MediaType, BusDirections_::kInput as BusDirection) > 0 {
                c.activateBus(MediaTypes_::kEvent as MediaType, BusDirections_::kInput as BusDirection, 0, 1);
            }
            let mut setup = ProcessSetup { processMode: ProcessModes_::kRealtime as int32, symbolicSampleSize: SymbolicSampleSizes_::kSample32 as int32, maxSamplesPerBlock: max_frames as int32, sampleRate: rate };
            if processor.setupProcessing(&mut setup) != kResultOk {
                return Err(format!("{}: refused real-time processing at {rate} Hz", self.who));
            }
            if c.setActive(1) != kResultOk {
                return Err(format!("{}: would not activate", self.who));
            }
        }
        self.active = true;
        Ok(Box::new(Vst3Proc { processor, edits: self.edits.clone(), effect: self.effect, processing: false, events: ComWrapper::new(Events(Default::default())), changes: ComWrapper::new(Changes(Default::default())) }))
    }

    fn open_editor(&mut self, title: &str) -> Result<Option<Window>, String> {
        let c = self.plugin.controller.as_ref().ok_or(format!("{}: it has no editor (no edit controller)", self.who))?;
        unsafe {
            let view = ComPtr::<IPlugView>::from_raw(c.createView(ViewType::kEditor)).ok_or(format!("{}: it has no editor", self.who))?;
            if view.isPlatformTypeSupported(kPlatformTypeHWND) != kResultTrue {
                return Err(format!("{}: its editor does not embed in a Windows window", self.who));
            }
            let mut r = ViewRect { left: 0, top: 0, right: 800, bottom: 600 };
            view.getSize(&mut r);
            let window = Window::new(title, (r.right - r.left).max(1) as u32, (r.bottom - r.top).max(1) as u32, view.canResize() == kResultTrue)?;
            view.setFrame(self.frame.as_com_ref::<IPlugFrame>().unwrap().as_ptr());
            if view.attached(window.hwnd.0 as *mut c_void, kPlatformTypeHWND) != kResultOk {
                return Err(format!("{}: its editor would not attach", self.who));
            }
            window.show();
            self.view = Some(view);
            Ok(Some(window))
        }
    }

    fn idle(&mut self, window: Option<&Window>) -> bool {
        if let (Some(w), Some((width, height))) = (window, self.frame.0.take()) {
            w.resize(width, height);
        }
        true
    }

    fn state(&mut self) -> Result<String, String> {
        // Edits not yet heard reach the processor first (a block of no samples: VST3's parameter flush).
        if !self.active && !self.edits.lock().unwrap().is_empty() {
            let mut p = self.activate(48000.0, 512)?;
            p.process((&[], &[]), (&mut [], &mut []), &[])?;
            self.close_proc(p);
        }
        Ok(crate::plugins::params::base64(&self.plugin.get_state()?))
    }

    fn values(&mut self) -> Vec<(u32, f64)> {
        let Some(c) = &self.plugin.controller else { return vec![] };
        self.params.iter().map(|&id| (id, unsafe { c.getParamNormalized(id) })).collect()
    }

    fn close(&mut self, proc: Option<Box<dyn Proc>>) {
        unsafe {
            if let Some(v) = self.view.take() {
                v.removed();
            }
            if let Some(p) = proc {
                self.close_proc(p);
            }
            if let Some(c) = &self.plugin.controller {
                c.setComponentHandler(std::ptr::null_mut());
                if self.plugin.component.cast::<IEditController>().is_none() {
                    c.terminate();
                }
            }
            self.plugin.component.terminate();
        }
        let _ = &self.handler;
    }
}

#[cfg(test)]
#[path = "session_tests.rs"]
mod tests;
