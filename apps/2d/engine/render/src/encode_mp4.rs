//!   rostrum2d-render encode-mp4 [--tagged] [--nv12] <out.mp4> <w> <h> <fps> <bitrate kbps> [quality 1-100]
//!   rostrum2d-render encode-mp4 --check     exit 0 when this computer can write MP4, else the reason on stderr
//! RGBA8 frames (straight alpha, the framing of encode_cmd.rs) → an H.264 MP4 through the operating system's own
//! encoder, never libx264 (GPL). Windows: Media Foundation's sink writer, the GPU's encoder when there is one, else
//! Microsoft's software H.264 encoder. High profile; with a quality, each frame gets the bits that picture quality needs
//! (constant quality: a still or simple shot is small, a busy one keeps its detail; the bitrate is then only the
//! file's nominal rate), else the bitrate given (variable). BT.709 limited range tagged on input
//! and output; frames turn into NV12 here (nv12.rs). The Mac (AVFoundation) is not built yet and says so.
//! Fails loudly: odd sizes are refused before anything is written; any failed step is named; a frame that only partly
//! arrived is an error; on any failure the unfinished file is deleted.
//! `--nv12`: frames come as NV12 (w×h×3/2 bytes, nv12.rs's own conversion, made by the sender) instead of RGBA8.
//! `--tagged`: each frame comes after a byte, 0 for a picture that follows, 1 for the picture before it again (sink.rs:
//! a still stretch of an export costs no bytes in the pipe and no conversion; the encoder gets the same frame again).
//! A thread reads the next frame while this one converts and writes the one before (three buffers going round); at the end
//! stderr says how long each step took. Media Foundation's DLLs are delay-loaded (build.rs): nothing loads them until `available` has found each one in
//! System32, so a Windows without them still runs the engine and gets a plain reason here instead of a crash.

#[cfg(not(windows))]
pub fn mp4(_args: &[String]) -> Result<u32, String> {
    Err("MP4 export on this system is not built yet (Windows only for now; the Mac's own encoder comes later)".into())
}

#[cfg(windows)]
const NO_MF: &str = "MP4 export needs Windows Media Foundation, which this Windows doesn't have (Windows N editions: \
install the Media Feature Pack from Settings › Apps › Optional features). WebM, PNG and GIF still work.";

/// Loads each delay-loaded Media Foundation DLL from System32 only, and keeps it loaded: the delay-load helper then
/// finds that copy (never one planted beside the program), and a missing one is reported before any call needs it.
#[cfg(windows)]
fn available() -> Result<(), String> {
    use windows_sys::Win32::System::LibraryLoader::{LoadLibraryExW, LOAD_LIBRARY_SEARCH_SYSTEM32};
    for dll in env!("ROSTRUM_DELAYED_DLLS").split(';') {
        let wide: Vec<u16> = dll.encode_utf16().chain(Some(0)).collect();
        if unsafe { LoadLibraryExW(wide.as_ptr(), std::ptr::null_mut(), LOAD_LIBRARY_SEARCH_SYSTEM32) }.is_null() {
            return Err(NO_MF.into());
        }
    }
    Ok(())
}

#[cfg(windows)]
pub fn mp4(args: &[String]) -> Result<u32, String> {
    use crate::encode_cmd::num;
    available()?;
    if args.first().map(String::as_str) == Some("--check") {
        return Ok(0);
    }
    let flag = |f: &str, args: &[String]| args.iter().take(2).any(|a| a == f);
    let (tagged, nv12) = (flag("--tagged", args), flag("--nv12", args));
    let args = &args[tagged as usize + nv12 as usize..];
    let out = args.first().ok_or("usage: encode-mp4 <out.mp4> <w> <h> <fps> <bitrate kbps> [quality 1-100]")?;
    let (w, h) = (num(args, 1, "width")?, num(args, 2, "height")?);
    let (fps, kbps) = (num(args, 3, "fps")?, num(args, 4, "bitrate (kbps)")?);
    if w == 0 || h == 0 || w % 2 == 1 || h % 2 == 1 {
        return Err(format!("H.264 (4:2:0) needs an even width and height; got {w}×{h}. Make the composition one pixel wider or taller"));
    }
    if fps == 0 || kbps == 0 || kbps > 4_000_000 {
        return Err(format!("fps and bitrate must be above 0 (bitrate at most 4 000 000 kbps); got {fps} fps, {kbps} kbps"));
    }
    let quality = if args.len() > 5 { Some(num(args, 5, "quality (1-100)")?) } else { None };
    if quality.is_some_and(|q| !(1..=100).contains(&q)) {
        return Err(format!("quality is 1 to 100; got {}", quality.unwrap()));
    }
    let done = mf::write(out, w, h, fps, kbps, quality, tagged, nv12); // the writer is released here, so the file can be removed
    if done.is_err() {
        let _ = std::fs::remove_file(out);
    }
    done
}

#[cfg(windows)]
mod mf {
    use crate::encode_cmd::frame;
    use windows::core::{GUID, PCWSTR};
    use windows::Win32::Media::MediaFoundation::*;
    use windows::Win32::System::Com::{CoInitializeEx, CoUninitialize, COINIT_MULTITHREADED};

    /// COM and Media Foundation for this process; shut down after the writer is released (declared before it).
    struct Session {
        mf: bool,
    }

    impl Drop for Session {
        fn drop(&mut self) {
            unsafe {
                if self.mf {
                    let _ = MFShutdown();
                }
                CoUninitialize();
            }
        }
    }

    fn step<T>(what: impl std::fmt::Display, r: windows::core::Result<T>) -> Result<T, String> {
        r.map_err(|e| format!("{what} failed: {e}"))
    }

    fn pair(hi: u32, lo: u32) -> u64 {
        ((hi as u64) << 32) | lo as u64
    }

    /// A video type with what input and output share: size, rate, square pixels, progressive, BT.709 limited range.
    unsafe fn video_type(sub: &GUID, w: u32, h: u32, fps: u32) -> windows::core::Result<IMFMediaType> {
        unsafe {
            let t = MFCreateMediaType()?;
            t.SetGUID(&MF_MT_MAJOR_TYPE, &MFMediaType_Video)?;
            t.SetGUID(&MF_MT_SUBTYPE, sub)?;
            t.SetUINT64(&MF_MT_FRAME_SIZE, pair(w, h))?;
            t.SetUINT64(&MF_MT_FRAME_RATE, pair(fps, 1))?;
            t.SetUINT64(&MF_MT_PIXEL_ASPECT_RATIO, pair(1, 1))?;
            t.SetUINT32(&MF_MT_INTERLACE_MODE, MFVideoInterlace_Progressive.0 as u32)?;
            t.SetUINT32(&MF_MT_YUV_MATRIX, MFVideoTransferMatrix_BT709.0 as u32)?;
            t.SetUINT32(&MF_MT_VIDEO_PRIMARIES, MFVideoPrimaries_BT709.0 as u32)?;
            t.SetUINT32(&MF_MT_TRANSFER_FUNCTION, MFVideoTransFunc_709.0 as u32)?;
            t.SetUINT32(&MF_MT_VIDEO_NOMINAL_RANGE, MFNominalRange_16_235.0 as u32)?;
            Ok(t)
        }
    }

    unsafe fn attributes(n: u32) -> windows::core::Result<IMFAttributes> {
        unsafe {
            let mut a = None;
            MFCreateAttributes(&mut a, n)?;
            Ok(a.expect("MFCreateAttributes succeeded"))
        }
    }

    unsafe fn output_type(w: u32, h: u32, fps: u32, kbps: u32) -> windows::core::Result<IMFMediaType> {
        unsafe {
            let t = video_type(&MFVideoFormat_H264, w, h, fps)?;
            t.SetUINT32(&MF_MT_AVG_BITRATE, kbps.saturating_mul(1000))?;
            t.SetUINT32(&MF_MT_MPEG2_PROFILE, eAVEncH264VProfile_High.0 as u32)?;
            Ok(t)
        }
    }

    unsafe fn input_type(w: u32, h: u32, fps: u32) -> windows::core::Result<IMFMediaType> {
        unsafe {
            let t = video_type(&MFVideoFormat_NV12, w, h, fps)?;
            t.SetUINT32(&MF_MT_DEFAULT_STRIDE, w)?;
            Ok(t)
        }
    }

    /// The encoder's own settings: constant quality (`quality`) or variable bitrate around the average, best quality
    /// over speed, a key frame every 2 s.
    unsafe fn encoder_settings(fps: u32, quality: Option<u32>) -> windows::core::Result<IMFAttributes> {
        unsafe {
            let p = attributes(4)?;
            match quality {
                Some(q) => {
                    p.SetUINT32(&CODECAPI_AVEncCommonRateControlMode, eAVEncCommonRateControlMode_Quality.0 as u32)?;
                    p.SetUINT32(&CODECAPI_AVEncCommonQuality, q)?;
                }
                None => p.SetUINT32(&CODECAPI_AVEncCommonRateControlMode, eAVEncCommonRateControlMode_UnconstrainedVBR.0 as u32)?,
            }
            // ROSTRUM2D_MP4_SPEED (0-100, to measure): the encoder's quality-vs-speed; 100, its best, unless set.
            let qvs = std::env::var("ROSTRUM2D_MP4_SPEED").ok().and_then(|v| v.trim().parse::<u32>().ok()).unwrap_or(100).min(100);
            p.SetUINT32(&CODECAPI_AVEncCommonQualityVsSpeed, qvs)?;
            p.SetUINT32(&CODECAPI_AVEncMPVGOPSize, fps * 2)?;
            Ok(p)
        }
    }

    /// Which encoder Media Foundation picked, said on stderr for the export's log (Sam: "is it using the GPU?"):
    /// its own name, and whether it is the graphics card's (a hardware transform) or the processor's.
    unsafe fn encoder_name(writer: &IMFSinkWriter, stream: u32) -> String {
        use windows::core::Interface;
        unsafe {
            let found = (|| -> windows::core::Result<String> {
                let ex: IMFSinkWriterEx = writer.cast()?;
                for i in 0.. {
                    let (mut cat, mut t) = (GUID::zeroed(), None);
                    ex.GetTransformForStream(stream, i, Some(&mut cat), &mut t)?;
                    if cat != MFT_CATEGORY_VIDEO_ENCODER {
                        continue;
                    }
                    let a = t.expect("GetTransformForStream gave a transform").GetAttributes()?;
                    let mut name = [0u16; 256];
                    let mut len = 0u32;
                    let named = a.GetString(&MFT_FRIENDLY_NAME_Attribute, &mut name, Some(&mut len)).is_ok();
                    let hw = a.GetStringLength(&MFT_ENUM_HARDWARE_URL_Attribute).is_ok();
                    let name = if named { String::from_utf16_lossy(&name[..len as usize]) } else { "unnamed".into() };
                    return Ok(format!("{name} ({})", if hw { "graphics card" } else { "processor: no graphics card encoder" }));
                }
                unreachable!()
            })();
            found.unwrap_or_else(|e| format!("unknown ({e})"))
        }
    }

    #[allow(clippy::too_many_arguments)]
    pub fn write(out: &str, w: u32, h: u32, fps: u32, kbps: u32, quality: Option<u32>, tagged: bool, nv12_in: bool) -> Result<u32, String> {
        unsafe {
            let t_start = std::time::Instant::now();
            step("starting COM (CoInitializeEx)", CoInitializeEx(None, COINIT_MULTITHREADED).ok())?;
            let mut session = Session { mf: false };
            step("starting Media Foundation (MFStartup)", MFStartup(MF_VERSION, MFSTARTUP_LITE))?;
            session.mf = true;

            let attrs = step("making the writer's settings", attributes(2))?;
            step("allowing the GPU's encoder", attrs.SetUINT32(&MF_READWRITE_ENABLE_HARDWARE_TRANSFORMS, 1))?;
            step("choosing the MP4 container", attrs.SetGUID(&MF_TRANSCODE_CONTAINERTYPE, &MFTranscodeContainerType_MPEG4))?;
            let t_mf = t_start.elapsed().as_secs_f64();
            let wide: Vec<u16> = out.encode_utf16().chain(Some(0)).collect();
            let writer = step(format!("creating {out} (MFCreateSinkWriterFromURL)"),
                MFCreateSinkWriterFromURL(PCWSTR(wide.as_ptr()), None::<&IMFByteStream>, &attrs))?;

            let output = step("describing the H.264 output", output_type(w, h, fps, kbps))?;
            let input = step("describing the NV12 input", input_type(w, h, fps))?;
            let params = step("making the encoder's settings", encoder_settings(fps, quality))?;
            let stream = step("adding the H.264 stream (AddStream)", writer.AddStream(&output))?;
            step("connecting the encoder to NV12 frames (SetInputMediaType)", writer.SetInputMediaType(stream, &input, &params))?;
            step("starting to write (BeginWriting)", writer.BeginWriting())?;
            eprintln!("encode-mp4: encoder {}", encoder_name(&writer, stream));
            eprintln!("encode-mp4: started in {:.2} s (Media Foundation {t_mf:.2} s, the writer and its encoder {:.2} s)",
                      t_start.elapsed().as_secs_f64(), t_start.elapsed().as_secs_f64() - t_mf);

            let (wu, hu) = (w as usize, h as usize);
            let size = wu * hu * 3 / 2;
            // A thread reads the frames (three buffers going round) while this one converts and encodes the one before,
            // so the pipe's time and the encoder's overlap.
            // None: the picture before again (`--tagged`).
            let (full_tx, full) = std::sync::mpsc::sync_channel::<Result<Option<Vec<u8>>, String>>(3);
            let (free, free_rx) = std::sync::mpsc::channel::<Vec<u8>>();
            // `--nv12`: the frames come as NV12 already (the export's drawing workers convert them side by side, sink.rs).
            let frame_bytes = if nv12_in { size } else { wu * hu * 4 };
            for _ in 0..3 {
                let _ = free.send(vec![0u8; frame_bytes]);
            }
            std::thread::spawn(move || {
                let mut stdin = std::io::stdin().lock();
                let mut i = 0u32;
                loop {
                    if tagged {
                        let mut tag = [0u8];
                        match frame(&mut stdin, &mut tag, i) {
                            Ok(true) if tag[0] == 1 => {
                                if full_tx.send(Ok(None)).is_err() {
                                    break;
                                }
                                i += 1;
                                continue;
                            }
                            Ok(true) if tag[0] == 0 => {}
                            Ok(true) => {
                                let _ = full_tx.send(Err(format!("frame {i}: its mark is {} (0: a picture, 1: the one before again)", tag[0])));
                                break;
                            }
                            Ok(false) => break,
                            Err(e) => {
                                let _ = full_tx.send(Err(e));
                                break;
                            }
                        }
                    }
                    let Ok(mut buf) = free_rx.recv() else { break };
                    match frame(&mut stdin, &mut buf, i) {
                        Ok(true) => drop(full_tx.send(Ok(Some(buf)))),
                        Ok(false) if tagged => {
                            let _ = full_tx.send(Err(format!("frame {i} ended after its mark, before its picture")));
                            break;
                        }
                        Ok(false) => break,
                        Err(e) => {
                            let _ = full_tx.send(Err(e));
                            break;
                        }
                    }
                    i += 1;
                }
            });
            let mut n = 0u32;
            let mut nv12 = vec![0u8; size];
            let (mut waited, mut converted, mut encoded) = (0f64, 0f64, 0f64); // seconds, for the log
            let mut lap = std::time::Instant::now();
            let mut took = |into: &mut f64| {
                *into += lap.elapsed().as_secs_f64();
                lap = std::time::Instant::now();
            };
            while let Ok(read) = full.recv() {
                took(&mut waited);
                // A new picture into NV12 (kept: a repeat is the same NV12 again).
                if let Some(pic) = read? {
                    if nv12_in {
                        nv12.copy_from_slice(&pic);
                    } else {
                        crate::nv12::from_rgba(&pic, wu, hu, &mut nv12);
                    }
                    let _ = free.send(pic);
                } else if n == 0 {
                    return Err("frame 0 is marked as the picture before it again; there is none".into());
                }
                let buf = step(format!("frame {n}: MFCreateMemoryBuffer"), MFCreateMemoryBuffer(size as u32))?;
                let mut p = std::ptr::null_mut();
                step(format!("frame {n}: locking its buffer"), buf.Lock(&mut p, None, None))?;
                std::slice::from_raw_parts_mut(p, size).copy_from_slice(&nv12);
                step(format!("frame {n}: unlocking its buffer"), buf.Unlock())?;
                took(&mut converted);
                step(format!("frame {n}: SetCurrentLength"), buf.SetCurrentLength(size as u32))?;
                let sample = step(format!("frame {n}: MFCreateSample"), MFCreateSample())?;
                step(format!("frame {n}: AddBuffer"), sample.AddBuffer(&buf))?;
                // 100 ns units from the frame number, exact: no drift over a long film.
                let at = |i: u32| i as i64 * 10_000_000 / fps as i64;
                step(format!("frame {n}: SetSampleTime"), sample.SetSampleTime(at(n)))?;
                step(format!("frame {n}: SetSampleDuration"), sample.SetSampleDuration(at(n + 1) - at(n)))?;
                step(format!("frame {n}: encoding (WriteSample)"), writer.WriteSample(stream, &sample))?;
                took(&mut encoded);
                n += 1;
            }
            if n == 0 {
                return Err("no frames arrived".into());
            }
            step("finishing the MP4 (Finalize)", writer.Finalize())?;
            let mut finished = 0.0;
            took(&mut finished);
            eprintln!("encode-mp4: {n} frames; waiting for frames {waited:.2} s, converting {converted:.2} s, encoder {encoded:.2} s, finishing {finished:.2} s");
            Ok(n)
        }
    }
}
