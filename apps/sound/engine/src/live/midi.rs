//! MIDI keyboards (S3), through Windows' own MIDI API (winmm): note-on / note-off from an input
//! device become the live instrument's events, stamped on arrival with the clock latency is measured on.

use std::sync::mpsc::Sender;

use windows::Win32::Media::Audio::{midiInClose, midiInGetDevCapsW, midiInGetNumDevs, midiInOpen, midiInStart, midiInStop, CALLBACK_FUNCTION, HMIDIIN, MIDIINCAPSW};

use crate::live::instrument::Event;

const MIM_DATA: u32 = 0x3C3;

/// The input devices' names, by index.
pub fn devices() -> Vec<String> {
    (0..unsafe { midiInGetNumDevs() })
        .map(|i| {
            let mut caps = MIDIINCAPSW::default();
            unsafe { midiInGetDevCapsW(i as usize, &mut caps, std::mem::size_of::<MIDIINCAPSW>() as u32) };
            let name = caps.szPname; // copied out of the packed struct
            String::from_utf16_lossy(&name).trim_end_matches('\0').to_string()
        })
        .collect()
}

unsafe extern "system" fn callback(_: HMIDIIN, msg: u32, instance: usize, param1: usize, _: usize) {
    if msg != MIM_DATA {
        return;
    }
    let events = unsafe { &*(instance as *const Sender<Event>) };
    let (status, key, velocity) = ((param1 & 0xF0) as u8, ((param1 >> 8) & 0x7F) as u8, ((param1 >> 16) & 0x7F) as u8);
    let at = crate::live::wasapi::now();
    let _ = match status {
        0x90 if velocity > 0 => events.send(Event::On { key, velocity: velocity as f64 / 127.0, at }),
        0x80 | 0x90 => events.send(Event::Off { key }),
        _ => Ok(()),
    };
}

/// An open input device; it stops and closes when dropped.
pub struct Input(HMIDIIN, *mut Sender<Event>);

pub fn open(index: u32, events: Sender<Event>) -> Result<Input, String> {
    let sender = Box::into_raw(Box::new(events));
    let mut h = HMIDIIN::default();
    let err = unsafe { midiInOpen(&mut h, index, Some(callback as *const () as usize), Some(sender as usize), CALLBACK_FUNCTION) };
    if err != 0 {
        drop(unsafe { Box::from_raw(sender) });
        return Err(format!("MIDI input {index}: midiInOpen failed ({err})"));
    }
    unsafe { midiInStart(h) };
    Ok(Input(h, sender))
}

impl Drop for Input {
    fn drop(&mut self) {
        unsafe {
            midiInStop(self.0);
            midiInClose(self.0);
            drop(Box::from_raw(self.1));
        }
    }
}

/// `rostrum-sound midi`: the MIDI input devices, the audio outputs and the audio inputs (microphones).
pub fn list_cmd() -> Result<(), String> {
    println!("{}", serde_json::json!({ "devices": devices(), "outputs": crate::live::wasapi::outputs(), "inputs": crate::live::wasapi::inputs() }));
    Ok(())
}
