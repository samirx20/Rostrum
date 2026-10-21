//! The live output's device (mod.rs): the default output or the one $ROSTRUM_AUDIO_OUTPUT names,
//! the outputs by name, and how WASAPI describes one (its mix format and form factor). Opening a stream
//! on it is open.rs.

// The COM calls here are all unsafe; the functions that make them are unsafe as a whole.
#![allow(unsafe_op_in_unsafe_fn)]

use windows::core::GUID;
use windows::Win32::Media::Audio::*;
use windows::Win32::System::Com::{CoCreateInstance, CoInitializeEx, CoTaskMemFree, CLSCTX_ALL, COINIT_MULTITHREADED};

/// The output devices (their names, as Windows shows them).
pub fn outputs() -> Vec<String> {
    unsafe {
        let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
        endpoints().map(|v| v.into_iter().map(|(n, _)| n).collect()).unwrap_or_default()
    }
}

unsafe fn endpoints() -> Result<Vec<(String, IMMDevice)>, String> {
    let devices: IMMDeviceEnumerator = CoCreateInstance(&MMDeviceEnumerator, None, CLSCTX_ALL).map_err(|e| e.message())?;
    let all = devices.EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE).map_err(|e| e.message())?;
    let mut out = vec![];
    for i in 0..all.GetCount().map_err(|e| e.message())? {
        let d = all.Item(i).map_err(|e| e.message())?;
        out.push((name(&d), d));
    }
    Ok(out)
}

/// A device's name, as Windows shows it (PKEY_Device_FriendlyName).
pub unsafe fn name(d: &IMMDevice) -> String {
    let key = windows::Win32::Foundation::PROPERTYKEY { fmtid: GUID::from_u128(0xa45c254e_df1c_4efd_8020_67d146a850e0), pid: 14 };
    d.OpenPropertyStore(windows::Win32::System::Com::STGM_READ).and_then(|p| p.GetValue(&key)).map(|v| v.to_string()).unwrap_or_default()
}

/// The output to play on: the default, or the first whose name contains $ROSTRUM_AUDIO_OUTPUT
/// (any case), so a test or a person can pick the speakers without changing Windows' default.
pub unsafe fn output() -> Result<IMMDevice, String> {
    match std::env::var("ROSTRUM_AUDIO_OUTPUT").ok().filter(|s| !s.is_empty()) {
        Some(want) => {
            let all = endpoints()?;
            let names: Vec<String> = all.iter().map(|(n, _)| format!("\"{n}\"")).collect();
            all.into_iter().find(|(n, _)| n.to_lowercase().contains(&want.to_lowercase())).map(|(_, d)| d).ok_or(format!("no audio output named like \"{want}\" (ROSTRUM_AUDIO_OUTPUT); outputs: {}", names.join(", ")))
        }
        None => {
            let devices: IMMDeviceEnumerator = CoCreateInstance(&MMDeviceEnumerator, None, CLSCTX_ALL).map_err(|e| e.message())?;
            devices.GetDefaultAudioEndpoint(eRender, eConsole).map_err(|e| e.message())
        }
    }
}

/// The output as WASAPI describes it (monitor.rs Device): its mix format's rate, channels and
/// channel mask, and the endpoint's form factor (PKEY_AudioEndpoint_FormFactor; 10, unknown, when absent).
pub unsafe fn describe(device: &IMMDevice) -> Result<crate::live::monitor::Device, String> {
    let client: IAudioClient = device.Activate(CLSCTX_ALL, None).map_err(|e| e.message())?;
    let mix = client.GetMixFormat().map_err(|e| e.message())?;
    let (rate, channels, tag) = ((*mix).nSamplesPerSec, (*mix).nChannels, (*mix).wFormatTag);
    let mask = if tag == 0xFFFE { std::ptr::addr_of!((*(mix as *const WAVEFORMATEXTENSIBLE)).dwChannelMask).read_unaligned() } else { 0 };
    CoTaskMemFree(Some(mix as *const _ as *const _));
    let key = windows::Win32::Foundation::PROPERTYKEY { fmtid: GUID::from_u128(0x1da5d803_d492_4edd_8c23_e0c0ffee7f0e), pid: 0 };
    let form_factor = device.OpenPropertyStore(windows::Win32::System::Com::STGM_READ).and_then(|p| p.GetValue(&key)).ok().and_then(|v| u32::try_from(&v).ok()).unwrap_or(10);
    Ok(crate::live::monitor::Device { rate, channels: channels as usize, mask, form_factor, name: name(device) })
}
