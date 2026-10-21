//! What the default output device allows in low-latency shared mode (IAudioClient3, Windows 10+):
//! the engine periods it offers and the stream latency at the smallest one. cpal opens WASAPI
//! streams the classic way (a 10 ms period), so this is what a backend of our own could reach;
//! exclusive mode (the device to ourselves) can run at the device's minimum period.

use windows::Win32::Media::Audio::{eConsole, eRender, IAudioClient3, IMMDeviceEnumerator, MMDeviceEnumerator, AUDCLNT_STREAMFLAGS_EVENTCALLBACK};
use windows::Win32::System::Com::{CoCreateInstance, CoInitializeEx, CoTaskMemFree, CLSCTX_ALL, COINIT_MULTITHREADED};

pub fn probe() -> Result<String, String> {
    let e = |x: windows::core::Error| x.to_string();
    unsafe {
        let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
        let devices: IMMDeviceEnumerator = CoCreateInstance(&MMDeviceEnumerator, None, CLSCTX_ALL).map_err(e)?;
        let device = devices.GetDefaultAudioEndpoint(eRender, eConsole).map_err(e)?;
        let client: IAudioClient3 = device.Activate(CLSCTX_ALL, None).map_err(e)?;
        let (mut dev_default, mut dev_min) = (0i64, 0i64);
        client.GetDevicePeriod(Some(&mut dev_default), Some(&mut dev_min)).map_err(e)?;
        let format = client.GetMixFormat().map_err(e)?;
        let rate = (*format).nSamplesPerSec;
        let (mut default, mut fundamental, mut min, mut max) = (0u32, 0u32, 0u32, 0u32);
        client.GetSharedModeEnginePeriod(format, &mut default, &mut fundamental, &mut min, &mut max).map_err(e)?;
        client.InitializeSharedAudioStream(AUDCLNT_STREAMFLAGS_EVENTCALLBACK, min, format, None).map_err(e)?;
        let latency_100ns = client.GetStreamLatency().map_err(e)?;
        let buffer = client.GetBufferSize().map_err(e)?;
        CoTaskMemFree(Some(format as *const _ as *const _));
        let ms = |frames: u32| frames as f64 * 1000.0 / rate as f64;
        Ok(format!(
            "{{\"rate\":{rate},\"defaultPeriodMs\":{:.2},\"minPeriodMs\":{:.2},\"maxPeriodMs\":{:.2},\"bufferAtMinMs\":{:.2},\"streamLatencyAtMinMs\":{:.2},\"exclusiveMinPeriodMs\":{:.2}}}",
            ms(default), ms(min), ms(max), ms(buffer), latency_100ns as f64 / 1e4, dev_min as f64 / 1e4
        ))
    }
}
