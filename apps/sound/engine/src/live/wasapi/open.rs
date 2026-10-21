//! Opening the live output (mod.rs) on its device (device.rs): exclusive mode at the
//! shortest period the device keeps real time at (each tried with 300 ms of silence and doubled up to
//! 25 ms), else low-latency shared mode (IAudioClient3); and writing f32 blocks in the device's sample
//! format. The stream itself, and stepping up when it falls behind, is mod.rs and stream.rs.

// The COM calls here are all unsafe; the functions that make them are unsafe as a whole.
#![allow(unsafe_op_in_unsafe_fn)]

use windows::core::{w, Interface, GUID};
use windows::Win32::Foundation::{CloseHandle, S_OK, WAIT_OBJECT_0};
use windows::Win32::Media::Audio::*;
use windows::Win32::System::Com::{CoTaskMemFree, CLSCTX_ALL};
use windows::Win32::System::Threading::{AvRevertMmThreadCharacteristics, AvSetMmThreadCharacteristicsW, CreateEventW, WaitForSingleObject};

use crate::live::wasapi::now;

/// The longest exclusive period tried (100 ns units): 25 ms.
pub const MAX_PERIOD: i64 = 250_000;

#[derive(Clone, Copy)]
pub enum Sample {
    F32,
    I32,
    I24,
    I16,
}

const SUBTYPE_PCM: GUID = GUID::from_u128(0x00000001_0000_0010_8000_00aa00389b71);
const SUBTYPE_FLOAT: GUID = GUID::from_u128(0x00000003_0000_0010_8000_00aa00389b71);

fn extensible(rate: u32, channels: u16, mask: u32, s: Sample) -> WAVEFORMATEXTENSIBLE {
    let (bits, valid, sub) = match s {
        Sample::F32 => (32u16, 32u16, SUBTYPE_FLOAT),
        Sample::I32 => (32, 24, SUBTYPE_PCM),
        Sample::I24 => (24, 24, SUBTYPE_PCM),
        Sample::I16 => (16, 16, SUBTYPE_PCM),
    };
    let block = channels * bits / 8;
    WAVEFORMATEXTENSIBLE {
        Format: WAVEFORMATEX { wFormatTag: 0xFFFE, nChannels: channels, nSamplesPerSec: rate, nAvgBytesPerSec: rate * block as u32, nBlockAlign: block, wBitsPerSample: bits, cbSize: 22 },
        Samples: WAVEFORMATEXTENSIBLE_0 { wValidBitsPerSample: valid },
        // The device's own speakers (its mix format's mask); stereo as before when it gives none.
        dwChannelMask: if mask != 0 { mask } else if channels == 2 { 3 } else { 0 },
        SubFormat: sub,
    }
}

/// A block of `src` channels → the device's frames, each device channel playing the source channel
/// `map` gives it (monitor.rs channel_map; None: silent).
pub fn write(block: &[f32], frames: usize, src: usize, map: &[Option<usize>], channels: usize, s: Sample, dst: *mut u8) {
    let bytes = match s {
        Sample::F32 | Sample::I32 => 4,
        Sample::I24 => 3,
        Sample::I16 => 2,
    };
    let out = unsafe { std::slice::from_raw_parts_mut(dst, frames * channels * bytes) };
    for i in 0..frames {
        for ch in 0..channels {
            let v = crate::live::monitor::placed(block, i, src, map, ch);
            let at = (i * channels + ch) * bytes;
            match s {
                Sample::F32 => out[at..at + 4].copy_from_slice(&v.to_le_bytes()),
                Sample::I32 => out[at..at + 4].copy_from_slice(&((v as f64 * 2147483647.0) as i32).to_le_bytes()),
                Sample::I24 => out[at..at + 3].copy_from_slice(&((v as f64 * 8388607.0) as i32).to_le_bytes()[..3]),
                Sample::I16 => out[at..at + 2].copy_from_slice(&((v * 32767.0) as i16).to_le_bytes()),
            }
        }
    }
}

/// An initialized client, its sample format and that format's name, its channels, and its period (100 ns units).
pub type Open = (IAudioClient, Sample, &'static str, u16, i64);

/// Exclusive mode at `rate`, from the device's shortest period (or `from`, when stepping up after the stream fell behind).
pub unsafe fn exclusive(device: &IMMDevice, rate: u32, channels: u16, mask: u32, from: Option<i64>) -> Result<Open, String> {
    let probe: IAudioClient = device.Activate(CLSCTX_ALL, None).map_err(|e| e.message())?;
    let (mut default, mut min) = (0i64, 0i64);
    probe.GetDevicePeriod(Some(&mut default), Some(&mut min)).map_err(|e| e.message())?;
    let names = [(Sample::F32, "f32"), (Sample::I32, "i32 (24-bit)"), (Sample::I24, "i24"), (Sample::I16, "i16")];
    // ROSTRUM_AUDIO_FORMAT (f32, i32, i24, i16) and ROSTRUM_AUDIO_PERIOD_MS pin them, for a driver that misbehaves with its first choice.
    let only = std::env::var("ROSTRUM_AUDIO_FORMAT").ok();
    let (sample, name, fmt) = names
        .iter()
        .filter(|(_, n)| only.as_deref().is_none_or(|o| n.starts_with(o)))
        .map(|&(s, n)| (s, n, extensible(rate, channels, mask, s)))
        .find(|(_, _, f)| probe.IsFormatSupported(AUDCLNT_SHAREMODE_EXCLUSIVE, &f.Format, None) == S_OK)
        .ok_or(format!("the device takes none of f32 / i32 / i24 / i16 at {rate} Hz, {channels} channels ({}) in exclusive mode", crate::live::monitor::speakers(mask)))?;
    let pinned = std::env::var("ROSTRUM_AUDIO_PERIOD_MS").ok().and_then(|v| v.parse::<f64>().ok());
    if from.is_some_and(|f| f > MAX_PERIOD) {
        return Err(format!("no exclusive period up to {} ms keeps real time", MAX_PERIOD / 10_000));
    }
    let mut period = pinned.map_or(from.unwrap_or(min).max(min), |ms| ((ms * 1e4) as i64).max(min));
    // The device's shortest period is not always one it keeps up with (a driver, a busy machine):
    // each period is tried for a moment with silence, and doubled (up to 25 ms) until the device
    // plays in real time. A pinned period is taken as it is.
    loop {
        let (client, aligned) = init(device, &fmt, period, rate)?;
        let ok = pinned.is_some() || aligned >= MAX_PERIOD || keeps_time(&client, &fmt, sample)?;
        drop(client); // exclusive: one client at a time
        if ok {
            return Ok((init(device, &fmt, aligned, rate)?.0, sample, name, channels, aligned));
        }
        period = aligned * 2;
    }
}

/// An exclusive client at `period` (100 ns units), aligned to the device's buffer size; the period it took.
unsafe fn init(device: &IMMDevice, fmt: &WAVEFORMATEXTENSIBLE, mut period: i64, rate: u32) -> Result<(IAudioClient, i64), String> {
    for attempt in 0..2 {
        let client: IAudioClient = device.Activate(CLSCTX_ALL, None).map_err(|e| e.message())?;
        match client.Initialize(AUDCLNT_SHAREMODE_EXCLUSIVE, AUDCLNT_STREAMFLAGS_EVENTCALLBACK, period, period, &fmt.Format, None) {
            Ok(()) => return Ok((client, period)),
            // The period must be a whole number of the device's buffer frames: take the size it offers.
            Err(e) if e.code() == AUDCLNT_E_BUFFER_SIZE_NOT_ALIGNED && attempt == 0 => {
                let frames = client.GetBufferSize().map_err(|e| e.message())?;
                period = (1e7 * frames as f64 / rate as f64 + 0.5) as i64;
            }
            Err(e) => return Err(format!("exclusive mode: {}", e.message())),
        }
    }
    Err("exclusive mode: the device refused its own aligned period".into())
}

/// Plays 300 ms of silence on the client and says whether the device's clock kept up with real time.
unsafe fn keeps_time(client: &IAudioClient, fmt: &WAVEFORMATEXTENSIBLE, sample: Sample) -> Result<bool, String> {
    let event = CreateEventW(None, false, false, None).map_err(|e| e.message())?;
    client.SetEventHandle(event).map_err(|e| e.message())?;
    let render: IAudioRenderClient = client.GetService().map_err(|e| e.message())?;
    let clock: IAudioClock = client.GetService().map_err(|e| e.message())?;
    let freq = clock.GetFrequency().map_err(|e| e.message())? as f64;
    let buffer = client.GetBufferSize().map_err(|e| e.message())?;
    let silence = vec![0f32; buffer as usize * 2];
    let channels = fmt.Format.nChannels as usize;
    let fill = || -> Result<(), String> {
        let p = render.GetBuffer(buffer).map_err(|e| e.message())?;
        write(&silence, buffer as usize, 2, &[], channels, sample, p);
        render.ReleaseBuffer(buffer, 0).map_err(|e| e.message())
    };
    fill()?;
    let mut task = 0u32;
    let mmcss = AvSetMmThreadCharacteristicsW(w!("Pro Audio"), &mut task).ok();
    client.Start().map_err(|e| e.message())?;
    let t0 = now();
    let mut ok = true;
    while now() - t0 < 0.3 {
        if WaitForSingleObject(event, 500) != WAIT_OBJECT_0 || fill().is_err() {
            ok = false;
            break;
        }
    }
    let mut pos = 0u64;
    let played = clock.GetPosition(&mut pos, None).map(|_| pos as f64 / freq).unwrap_or(0.0);
    let elapsed = now() - t0;
    let _ = client.Stop();
    let _ = CloseHandle(event);
    if let Some(h) = mmcss {
        let _ = AvRevertMmThreadCharacteristics(h);
    }
    // Real time within 2 % (the clock starts a period late at most).
    let period = buffer as f64 / fmt.Format.nSamplesPerSec as f64;
    Ok(ok && played >= elapsed * 0.98 - period)
}

pub unsafe fn shared(device: &IMMDevice) -> Result<(Open, u32), String> {
    let client: IAudioClient3 = device.Activate(CLSCTX_ALL, None).map_err(|e| e.message())?;
    let mix = client.GetMixFormat().map_err(|e| e.message())?;
    let (rate, channels, bits, tag) = ((*mix).nSamplesPerSec, (*mix).nChannels, (*mix).wBitsPerSample, (*mix).wFormatTag);
    let float = tag == 3 || (tag == 0xFFFE && std::ptr::addr_of!((*(mix as *const WAVEFORMATEXTENSIBLE)).SubFormat).read_unaligned() == SUBTYPE_FLOAT);
    let (mut default, mut fundamental, mut min, mut max) = (0u32, 0u32, 0u32, 0u32);
    let r = client.GetSharedModeEnginePeriod(mix, &mut default, &mut fundamental, &mut min, &mut max).and_then(|_| client.InitializeSharedAudioStream(AUDCLNT_STREAMFLAGS_EVENTCALLBACK, min, mix, None));
    CoTaskMemFree(Some(mix as *const _ as *const _));
    r.map_err(|e| format!("shared mode: {}", e.message()))?;
    if !(float && bits == 32) {
        return Err(format!("shared mode: the mix format is {bits}-bit {} (expected 32-bit float)", if float { "float" } else { "integer" }));
    }
    Ok(((client.cast().map_err(|e| e.message())?, Sample::F32, "f32", channels, 0), rate))
}
