//! A CLAP plugin opened for a person (plugins/session.rs): its saved state and a preset loaded (the
//! preset-load extension), the document's parameter values applied, its editor embedded in our
//! window (the gui extension, Win32), and it playing live on the audio thread.

use std::ffi::CString;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use clack_extensions::gui::{GuiApiType, GuiConfiguration, GuiSize, HostGui, HostGuiImpl, PluginGui, Window as ClapWindow};
use clack_extensions::params::PluginParams;
use clack_extensions::preset_discovery::prelude::{HostPresetLoad, Location, PluginPresetLoad};
use clack_extensions::preset_discovery::HostPresetLoadImpl;
use clack_host::events::event_types::{NoteOffEvent, NoteOnEvent, ParamValueEvent};
use clack_host::events::Match;
use clack_host::prelude::*;

use crate::plugins::session::{Note, Proc, Session, SessionSpec};
use crate::plugins::window::Window;

#[derive(Default)]
pub struct Shared {
    callback: AtomicBool,
    resize: AtomicU64,
    closed: AtomicBool,
}
impl<'a> SharedHandler<'a> for Shared {
    fn request_restart(&self) {}
    fn request_process(&self) {}
    fn request_callback(&self) {
        self.callback.store(true, Ordering::Relaxed);
    }
}
impl HostGuiImpl for Shared {
    fn resize_hints_changed(&self) {}
    fn request_resize(&self, size: GuiSize) -> Result<(), HostError> {
        self.resize.store(size.pack_to_u64(), Ordering::Relaxed);
        Ok(())
    }
    fn request_show(&self) -> Result<(), HostError> {
        Ok(())
    }
    fn request_hide(&self) -> Result<(), HostError> {
        Ok(())
    }
    fn closed(&self, _destroyed: bool) {
        self.closed.store(true, Ordering::Relaxed);
    }
}

/// The preset load's outcome, as the plugin reports it (on the main thread, maybe later).
#[derive(Default)]
pub struct Main(Mutex<Option<Result<(), String>>>);
impl<'a> MainThreadHandler<'a> for Main {}
impl HostPresetLoadImpl for Main {
    fn on_error(&self, _location: Location, _key: Option<&std::ffi::CStr>, os_error: i32, message: Option<&std::ffi::CStr>) {
        *self.0.lock().unwrap() = Some(Err(message.map(|m| m.to_string_lossy().into_owned()).unwrap_or_else(|| format!("error {os_error}"))));
    }
    fn loaded(&self, _location: Location, _key: Option<&std::ffi::CStr>) {
        *self.0.lock().unwrap() = Some(Ok(()));
    }
}

pub struct SessionHost;
impl HostHandlers for SessionHost {
    type Shared<'a> = Shared;
    type MainThread<'a> = Main;
    type AudioProcessor<'a> = ();
    fn declare_extensions(builder: &mut HostExtensions<Self>, _shared: &Shared) {
        builder.register::<HostGui>().register::<HostPresetLoad>();
    }
}

pub struct ClapSession {
    instance: PluginInstance<SessionHost>,
    _entry: PluginEntry,
    gui: Option<PluginGui>,
    params: Vec<u32>,
    who: String,
}

impl ClapSession {
    pub fn new(spec: &SessionSpec) -> Result<ClapSession, String> {
        let p = &spec.plugin;
        let who = format!("plugin {} ({})", p.id, p.path);
        let entry = unsafe { PluginEntry::load(&p.path) }.map_err(|e| format!("{who}: cannot load: {e:?}"))?;
        let id = CString::new(p.id.clone()).map_err(|_| format!("{who}: bad id"))?;
        let info = super::host_info()?;
        let mut instance = PluginInstance::<SessionHost>::new(|_| Shared::default(), |_| Main::default(), &entry, &id, &info).map_err(|e| format!("{who}: {e:?}"))?;
        if let Some(state) = &p.state {
            crate::plugins::clap::load_state(&mut instance.plugin_handle(), state).map_err(|e| format!("{who}: {e}"))?;
        }
        let mut s = ClapSession { instance, _entry: entry, gui: None, params: p.params.iter().map(|(id, _)| *id).collect(), who };
        if let Some(preset) = &spec.preset {
            s.load_preset(preset)?;
        }
        // The document's fixed values over the preset (an envelope plays in the render).
        let fixed: Vec<(u32, f64)> = p.params.iter().filter_map(|(id, v)| if let crate::mix::schedule::Param::Value(x) = v { Some((*id, *x)) } else { None }).collect();
        if !fixed.is_empty() {
            let mut events = EventBuffer::new();
            for (id, v) in fixed {
                if let Some(cid) = ClapId::from_raw(id) {
                    events.push(&ParamValueEvent::new(0, cid, Pckn::match_all(), v));
                }
            }
            let handle = s.instance.plugin_handle();
            if let Some(ext) = handle.get_extension::<PluginParams>() {
                if let Some(mut inactive) = s.instance.inactive_plugin_handle() {
                    ext.flush(&mut inactive, &InputEvents::from_buffer(&events), &mut OutputEvents::void());
                }
            }
        }
        Ok(s)
    }

    fn load_preset(&mut self, preset: &crate::plugins::session::Preset) -> Result<(), String> {
        let who = self.who.clone();
        let handle = self.instance.plugin_handle();
        let ext = handle.get_extension::<PluginPresetLoad>().ok_or(format!("{who}: it cannot load presets (no CLAP preset-load extension)"))?;
        let path = preset.file.as_deref().map(|f| CString::new(f).map_err(|_| format!("{who}: bad preset path"))).transpose()?;
        let key = preset.key.as_deref().map(|k| CString::new(k).map_err(|_| format!("{who}: bad preset key"))).transpose()?;
        let location = match &path {
            Some(p) => Location::File { path: p },
            None => Location::Plugin,
        };
        ext.load_from_location(&handle, location, key.as_deref()).map_err(|_| format!("{who}: it would not load the preset {preset:?}"))?;
        // The plugin may report the load later, on the main thread.
        let t0 = Instant::now();
        while t0.elapsed() < Duration::from_secs(3) {
            if let Some(r) = self.instance.access_handler(|m: &Main| m.0.lock().unwrap().take()) {
                return r.map_err(|e| format!("{who}: the preset did not load: {e}"));
            }
            self.idle(None);
            crate::plugins::window::pump_messages();
            std::thread::sleep(Duration::from_millis(5));
        }
        Ok(()) // a plugin that loads at once need not say so
    }
}

struct ClapProc {
    started: Option<StartedPluginAudioProcessor<SessionHost>>,
    stopped: Option<StoppedPluginAudioProcessor<SessionHost>>,
    events: EventBuffer,
    out_events: EventBuffer,
    ports: (AudioPorts, AudioPorts),
    steady: u64,
}

impl Proc for ClapProc {
    fn process(&mut self, input: (&[f32], &[f32]), out: (&mut [f32], &mut [f32]), notes: &[Note]) -> Result<(), String> {
        if self.started.is_none() {
            let stopped = self.stopped.take().ok_or("the plugin is not active")?;
            self.started = Some(stopped.start_processing().map_err(|e| format!("cannot start: {e:?}"))?);
        }
        let p = self.started.as_mut().unwrap();
        self.events.clear();
        for &(o, key, vel) in notes {
            let pckn = Pckn::new(0u16, 0u16, key as u16, Match::All);
            if vel > 0.0 {
                self.events.push(&NoteOnEvent::new(o, pckn, vel));
            } else {
                self.events.push(&NoteOffEvent::new(o, pckn, 0.0));
            }
        }
        let n = out.0.len();
        let (mut il, mut ir) = (input.0[..n].to_vec(), input.1[..n].to_vec());
        let (ol, or) = out;
        self.out_events.clear();
        let inp = self.ports.0.with_input_buffers([AudioPortBuffer { latency: 0, channels: AudioPortBufferType::f32_input_only([InputChannel::variable(&mut il[..]), InputChannel::variable(&mut ir[..])].into_iter()) }]);
        let mut outp = self.ports.1.with_output_buffers([AudioPortBuffer { latency: 0, channels: AudioPortBufferType::f32_output_only([&mut ol[..], &mut or[..]].into_iter()) }]);
        p.process(&inp, &mut outp, &InputEvents::from_buffer(&self.events), &mut OutputEvents::from_buffer(&mut self.out_events), Some(self.steady), None).map_err(|e| format!("process failed: {e:?}"))?;
        self.steady += n as u64;
        Ok(())
    }
    fn into_any(self: Box<Self>) -> Box<dyn std::any::Any> {
        self
    }
}

impl Session for ClapSession {
    fn activate(&mut self, rate: f64, max_frames: u32) -> Result<Box<dyn Proc>, String> {
        let config = PluginAudioConfiguration { sample_rate: rate, min_frames_count: 1, max_frames_count: max_frames };
        let stopped = self.instance.activate(|_, _| (), config).map_err(|e| format!("{}: cannot activate: {e:?}", self.who))?;
        Ok(Box::new(ClapProc { started: None, stopped: Some(stopped), events: EventBuffer::new(), out_events: EventBuffer::new(), ports: (AudioPorts::with_capacity(2, 1), AudioPorts::with_capacity(2, 1)), steady: 0 }))
    }

    fn open_editor(&mut self, title: &str) -> Result<Option<Window>, String> {
        let handle = self.instance.plugin_handle();
        let gui = handle.get_extension::<PluginGui>().ok_or(format!("{}: it has no editor (no CLAP gui extension)", self.who))?;
        let embedded = GuiConfiguration { api_type: GuiApiType::WIN32, is_floating: false };
        if !gui.is_api_supported(&handle, embedded) {
            // Its own floating window, then.
            let floating = GuiConfiguration { api_type: GuiApiType::WIN32, is_floating: true };
            gui.create(&handle, floating).map_err(|e| format!("{}: its editor would not open: {e:?}", self.who))?;
            gui.suggest_title(&handle, &CString::new(title).unwrap_or_default());
            gui.show(&handle).map_err(|e| format!("{}: its editor would not show: {e:?}", self.who))?;
            self.gui = Some(gui);
            return Ok(None);
        }
        gui.create(&handle, embedded).map_err(|e| format!("{}: its editor would not open: {e:?}", self.who))?;
        let size = gui.get_size(&handle).unwrap_or(GuiSize { width: 800, height: 600 });
        let window = Window::new(title, size.width, size.height, gui.can_resize(&handle))?;
        unsafe { gui.set_parent(&handle, ClapWindow::from_win32_hwnd(window.hwnd.0)) }.map_err(|e| format!("{}: its editor would not embed: {e:?}", self.who))?;
        gui.show(&handle).map_err(|e| format!("{}: its editor would not show: {e:?}", self.who))?;
        window.show();
        self.gui = Some(gui);
        Ok(Some(window))
    }

    fn idle(&mut self, window: Option<&Window>) -> bool {
        if self.instance.access_shared_handler(|s: &Shared| s.callback.swap(false, Ordering::Relaxed)) {
            self.instance.call_on_main_thread_callback();
        }
        let resize = self.instance.access_shared_handler(|s: &Shared| s.resize.swap(0, Ordering::Relaxed));
        if let (Some(w), true) = (window, resize != 0) {
            let size = GuiSize::unpack_from_u64(resize);
            w.resize(size.width, size.height);
        }
        !self.instance.access_shared_handler(|s: &Shared| s.closed.load(Ordering::Relaxed))
    }

    fn state(&mut self) -> Result<String, String> {
        crate::plugins::clap::save_state(&mut self.instance.plugin_handle())
    }

    fn values(&mut self) -> Vec<(u32, f64)> {
        let handle = self.instance.plugin_handle();
        let Some(ext) = handle.get_extension::<PluginParams>() else { return vec![] };
        self.params.iter().filter_map(|&id| ClapId::from_raw(id).and_then(|c| ext.get_value(&handle, c)).map(|v| (id, v))).collect()
    }

    fn close(&mut self, proc: Option<Box<dyn Proc>>) {
        if let Some(gui) = self.gui.take() {
            gui.destroy(&self.instance.plugin_handle());
        }
        if let Some(p) = proc.and_then(|p| p.into_any().downcast::<ClapProc>().ok()) {
            let ClapProc { started, stopped, .. } = *p;
            let stopped = started.map(|s| s.stop_processing()).or(stopped);
            if let Some(s) = stopped {
                self.instance.deactivate(s);
            }
        }
    }
}

#[cfg(test)]
#[path = "session_tests.rs"]
mod tests;
