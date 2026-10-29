//!   rostrum2d-render encode-mp4 [--tagged] [--nv12] [--keep=<folder>] <out.mp4> <w> <h> <fps> <bitrate kbps> [quality 1-100]
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
//! `--keep=<folder>` (with `--tagged`; files wait in that folder while written): an export's held encoder (sink.rs): it stays running across an export's parts and
//! exports, a 2 mark followed by a path saves the frames so far as that file, and the next file's writer is made ahead
//! (its 2-4 s start, the graphics card's encoder, taken while the file before encodes); the saved file is finished
//! (Finalize) and renamed into place on a thread of its own, so an export cut into many files (scene_export.rs `saves`)
//! never waits on one. See `mf::write`.
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
    let flags = args.iter().take_while(|a| a.starts_with("--")).count();
    let flag = |f: &str| args[..flags].iter().any(|a| a == f);
    let (tagged, nv12) = (flag("--tagged"), flag("--nv12"));
    // --keep=<folder>: where the files being written wait (Rostrum's cache, never the person's export folder)
    let keep: Option<String> = args[..flags].iter().find_map(|a| a.strip_prefix("--keep=").map(String::from));
    if keep.is_some() && !tagged {
        return Err("--keep needs --tagged (its save marks are tagged)".into());
    }
    let args = &args[flags..];
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
    let kept = keep.is_some();
    let done = mf::write(out, w, h, fps, kbps, quality, tagged, nv12, keep); // the writer is released here, so the file can be removed
    if done.is_err() && !kept {   // a kept encoder's files were saved whole, or are its own hidden ones (removed)
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
            // The encoder's quality-vs-speed: 0, its fastest. On the RTX 3050 it encodes 232 frames a second at 1080p (62
            // at 4K) against 147 (41) at 100, and a clean Rostrum render came out 0.02-0.43 dB from 100 against the
            // source, with no difference seen side by side at full size (2026-10-29, results\2d-export-fast-r2\encoder\clean).
            // ROSTRUM2D_MP4_SPEED (0-100) sets another, to measure.
            let qvs = std::env::var("ROSTRUM2D_MP4_SPEED").ok().and_then(|v| v.trim().parse::<u32>().ok()).unwrap_or(0).min(100);
            p.SetUINT32(&CODECAPI_AVEncCommonQualityVsSpeed, qvs)?;
            // To measure too: ROSTRUM2D_MP4_LOW_LATENCY=1 (no frames held back to look ahead), ROSTRUM2D_MP4_BFRAMES=<n>
            // (pictures predicted from both sides); left to the encoder unless set.
            let knob = |k: &str| std::env::var(k).ok().and_then(|v| v.trim().parse::<u32>().ok());
            if let Some(v) = knob("ROSTRUM2D_MP4_LOW_LATENCY") {
                p.SetUINT32(&CODECAPI_AVLowLatencyMode, v)?;
            }
            if let Some(v) = knob("ROSTRUM2D_MP4_BFRAMES") {
                p.SetUINT32(&CODECAPI_AVEncMPVDefaultBPictureCount, v)?;
            }
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

    /// What the writer is made with (a file's settings; `open` makes one writer from them).
    #[derive(Clone, Copy)]
    pub struct Spec {
        pub w: u32,
        pub h: u32,
        pub fps: u32,
        pub kbps: u32,
        pub quality: Option<u32>,
    }

    /// One MP4 being written: the writer, its stream, the file it writes.
    struct Open {
        writer: IMFSinkWriter,
        stream: u32,
        path: String,
    }
    // Media Foundation's writer is free-threaded in this process's multithreaded COM: a spare is made on another thread.
    unsafe impl Send for Open {}

    /// A writer for `path`, started (BeginWriting): the costly step, 2-4 s with the graphics card's encoder.
    fn open(path: &str, sp: Spec) -> Result<Open, String> {
        unsafe {
            let attrs = step("making the writer's settings", attributes(2))?;
            step("allowing the GPU's encoder", attrs.SetUINT32(&MF_READWRITE_ENABLE_HARDWARE_TRANSFORMS, 1))?;
            step("choosing the MP4 container", attrs.SetGUID(&MF_TRANSCODE_CONTAINERTYPE, &MFTranscodeContainerType_MPEG4))?;
            let wide: Vec<u16> = path.encode_utf16().chain(Some(0)).collect();
            let writer = step(format!("creating {path} (MFCreateSinkWriterFromURL)"),
                MFCreateSinkWriterFromURL(PCWSTR(wide.as_ptr()), None::<&IMFByteStream>, &attrs))?;
            let output = step("describing the H.264 output", output_type(sp.w, sp.h, sp.fps, sp.kbps))?;
            let input = step("describing the NV12 input", input_type(sp.w, sp.h, sp.fps))?;
            let params = step("making the encoder's settings", encoder_settings(sp.fps, sp.quality))?;
            let stream = step("adding the H.264 stream (AddStream)", writer.AddStream(&output))?;
            step("connecting the encoder to NV12 frames (SetInputMediaType)", writer.SetInputMediaType(stream, &input, &params))?;
            step("starting to write (BeginWriting)", writer.BeginWriting())?;
            Ok(Open { writer, stream, path: path.to_string() })
        }
    }

    /// What the reading thread hands on: a picture, the one before again (`--tagged` 1), or "save the frames so far as
    /// this file" (`--keep` 2).
    enum Got {
        Pic(Vec<u8>),
        Again,
        Save(String),
    }

    /// How many next writers are made ahead (`--keep`). One: an export saves a file per part of up to 10 s
    /// (export_cache.py `_parts`), and one writer starts well within that. With two, a file every 2 s ended the encoder
    /// process with no word on the RTX 3050 (bench, 2026-10-29); kept at one until that is understood. To measure:
    /// ROSTRUM2D_MP4_AHEAD (1-4).
    const AHEAD: usize = 1;

    /// The next writers, being made (`--keep`): the next file starts at once, the writer's start taken while the files
    /// before encode.
    struct Spare {
        dir: std::path::PathBuf,
        k: u32,
        making: std::collections::VecDeque<std::thread::JoinHandle<Result<Open, String>>>,
    }

    impl Spare {
        /// Starts making writers until AHEAD are on their way.
        fn arm(&mut self, sp: Spec) {
            let ahead = std::env::var("ROSTRUM2D_MP4_AHEAD").ok().and_then(|v| v.trim().parse::<usize>().ok()).unwrap_or(AHEAD).clamp(1, 4);
            while self.making.len() < ahead {
                self.k += 1;
                let path = self.dir.join(format!(".encoding-{}-{}.mp4.partial", std::process::id(), self.k)).to_string_lossy().into_owned();
                self.making.push_back(std::thread::spawn(move || {
                    unsafe { CoInitializeEx(None, COINIT_MULTITHREADED).ok().map_err(|e| e.to_string())? };
                    open(&path, sp)
                }));
            }
        }

        /// The oldest writer on its way, waited for if it is not made yet.
        fn take(&mut self) -> Result<Open, String> {
            self.making.pop_front().ok_or("no next writer was being made")?.join().map_err(|_| "making the next writer panicked".to_string())?
        }
    }

    impl Drop for Spare {
        /// Spares never used: their writers released, their hidden files removed.
        fn drop(&mut self) {
            for t in self.making.drain(..) {
                if let Ok(Ok(o)) = t.join() {
                    let path = o.path.clone();
                    drop(o);
                    let _ = std::fs::remove_file(path);
                }
            }
        }
    }

    /// `done` finished as `path` (its `n` frames), then "encode-mp4: saved <n> <path>" on stderr. Renamed from its hidden
    /// name only once whole: a crash before leaves nothing under `path`. On a thread in this process's multithreaded COM.
    fn finish(done: Open, path: String, n: u32) -> Result<(), String> {
        let t = std::time::Instant::now();
        let r = unsafe { step(format!("finishing {path} (Finalize)"), done.writer.Finalize()) };
        let tmp = done.path.clone();
        drop(done);
        if let Err(e) = r {
            let _ = std::fs::remove_file(&tmp);
            return Err(e);
        }
        if std::fs::rename(&tmp, &path).is_err() {
            // another drive (or the name is taken): copied over, then the hidden one removed
            std::fs::copy(&tmp, &path).map_err(|e| format!("saving {path}: {e}"))?;
            let _ = std::fs::remove_file(&tmp);
        }
        eprintln!("encode-mp4: finished {path} in {:.2} s", t.elapsed().as_secs_f64());
        eprintln!("encode-mp4: saved {n} {path}");
        Ok(())
    }

    #[path = "../../encode_lanes.rs"]
    mod lanes;

    /// Files at most being encoded side by side by a kept encoder (encode_lanes.rs): the one taking frames and the one
    /// before, finishing. To measure: ROSTRUM2D_MP4_LANES (1-3; 1: one file at a time, as before round 5).
    const LANES: usize = 2;

    /// Files saved by a kept encoder, each being finished on a thread of its own (`--keep`'s 2 marks).
    struct Finishing(Vec<std::thread::JoinHandle<Result<(), String>>>);

    impl Finishing {
        /// `done` finished as `path` (its `n` frames), then "encode-mp4: saved <n> <path>" on stderr. Renamed from its
        /// hidden name only once whole: a crash before leaves nothing under `path`.
        fn add(&mut self, done: Open, path: String, n: u32) {
            self.0.push(std::thread::spawn(move || {
                unsafe { CoInitializeEx(None, COINIT_MULTITHREADED).ok().map_err(|e| e.to_string())? };
                finish(done, path, n)
            }));
        }

        /// Waits until at most `most` of the files are still being written or finished (the oldest first).
        fn limit(&mut self, most: usize) -> Result<(), String> {
            while self.0.iter().filter(|h| !h.is_finished()).count() > most {
                let k = self.0.iter().position(|h| !h.is_finished()).unwrap();
                self.0.remove(k).join().map_err(|_| "finishing a file panicked".to_string())??;
            }
            self.check()
        }

        /// The first failure of a file already finished (the ones still going are left to go on).
        fn check(&mut self) -> Result<(), String> {
            let (ended, going): (Vec<_>, Vec<_>) = std::mem::take(&mut self.0).into_iter().partition(|h| h.is_finished());
            self.0 = going;
            ended.into_iter().try_for_each(|h| h.join().map_err(|_| "finishing a file panicked".to_string())?)
        }

        /// Every file finished, or the first failure.
        fn wait(&mut self) -> Result<(), String> {
            std::mem::take(&mut self.0).into_iter().try_for_each(|h| h.join().map_err(|_| "finishing a file panicked".to_string())?)
        }
    }

    impl Drop for Finishing {
        /// A failed export still finishes the files it saved before failing (declared after the Session, so this runs
        /// before Media Foundation shuts down): the next export draws only the rest.
        fn drop(&mut self) {
            let _ = self.wait();
        }
    }

    /// `out`, written from the frames on stdin. `keep` (`--keep`, an export's held encoder): files are written under a
    /// hidden name in `out`'s folder, and each 2 mark followed by a path (u32 length, little-endian, then UTF-8) saves the
    /// frames since the one before as that file ("encode-mp4: saved <n> <path>" on stderr) while the next writer, made
    /// ahead, takes the frames after it; frames never saved are dropped at the end. Returns the frames written (saved).
    #[allow(clippy::too_many_arguments)]
    pub fn write(out: &str, w: u32, h: u32, fps: u32, kbps: u32, quality: Option<u32>, tagged: bool, nv12_in: bool, keep_in: Option<String>) -> Result<u32, String> {
        unsafe {
            let t_start = std::time::Instant::now();
            step("starting COM (CoInitializeEx)", CoInitializeEx(None, COINIT_MULTITHREADED).ok())?;
            let mut session = Session { mf: false };
            step("starting Media Foundation (MFStartup)", MFStartup(MF_VERSION, MFSTARTUP_LITE))?;
            session.mf = true;
            let t_mf = t_start.elapsed().as_secs_f64();
            let sp = Spec { w, h, fps, kbps, quality };
            let keep = keep_in.is_some();
            let dir = std::path::PathBuf::from(keep_in.unwrap_or_default());
            if keep {
                std::fs::create_dir_all(&dir).map_err(|e| format!("the encoder's folder {}: {e}", dir.display()))?;
            }
            let mut spare = Spare { dir, k: 0, making: Default::default() };
            let mut finishing = Finishing(vec![]);
            let first = if keep {
                spare.arm(sp);
                let first = spare.take()?;
                spare.arm(sp);
                first
            } else {
                open(out, sp)?
            };
            eprintln!("encode-mp4: encoder {}", encoder_name(&first.writer, first.stream));
            eprintln!("encode-mp4: started in {:.2} s (Media Foundation {t_mf:.2} s, the writer and its encoder {:.2} s)",
                      t_start.elapsed().as_secs_f64(), t_start.elapsed().as_secs_f64() - t_mf);

            let (wu, hu) = (w as usize, h as usize);
            let size = wu * hu * 3 / 2;
            // A thread reads the frames (three buffers going round) while this one converts and encodes the one before,
            // so the pipe's time and the encoder's overlap.
            let (full_tx, full) = std::sync::mpsc::sync_channel::<Result<Got, String>>(3);
            let (free, free_rx) = std::sync::mpsc::channel::<Vec<u8>>();
            // `--nv12`: the frames come as NV12 already (the export's drawing workers convert them side by side, sink.rs).
            let frame_bytes = if nv12_in { size } else { wu * hu * 4 };
            // A kept encoder's files each on a lane of their own (encode_lanes.rs), else one writer on this thread.
            let lanes_n = std::env::var("ROSTRUM2D_MP4_LANES").ok().and_then(|v| v.trim().parse::<usize>().ok()).unwrap_or(LANES).clamp(1, 3);
            let room = lanes::Room::new(size);
            let (mut file, mut lane) = if keep && lanes_n > 1 { (None, Some(lanes::Lane::start(first, fps, room.clone()))) } else { (Some(first), None) };
            for _ in 0..3 {
                let _ = free.send(vec![0u8; frame_bytes]);
            }
            std::thread::spawn(move || {
                let mut stdin = std::io::stdin().lock();
                let mut i = 0u32;
                let send = |g: Result<Got, String>| full_tx.send(g).is_ok();
                loop {
                    if tagged {
                        let mut tag = [0u8];
                        match frame(&mut stdin, &mut tag, i) {
                            Ok(true) if tag[0] == 1 => {
                                if !send(Ok(Got::Again)) {
                                    break;
                                }
                                i += 1;
                                continue;
                            }
                            Ok(true) if tag[0] == 2 && keep => {
                                let mut len = [0u8; 4];
                                let path = frame(&mut stdin, &mut len, i).and_then(|_| {
                                    let mut b = vec![0u8; u32::from_le_bytes(len) as usize];
                                    frame(&mut stdin, &mut b, i)?;
                                    String::from_utf8(b).map_err(|e| format!("a file name that is not UTF-8: {e}"))
                                });
                                let bad = path.is_err();
                                if !send(path.map(Got::Save)) || bad {
                                    break;
                                }
                                continue;
                            }
                            Ok(true) if tag[0] == 0 => {}
                            Ok(true) => {
                                let _ = send(Err(format!("frame {i}: its mark is {} (0: a picture, 1: the one before again, 2 with --keep: save)", tag[0])));
                                break;
                            }
                            Ok(false) => break,
                            Err(e) => {
                                let _ = send(Err(e));
                                break;
                            }
                        }
                    }
                    let Ok(mut buf) = free_rx.recv() else { break };
                    match frame(&mut stdin, &mut buf, i) {
                        Ok(true) => drop(send(Ok(Got::Pic(buf)))),
                        Ok(false) if tagged => {
                            let _ = send(Err(format!("frame {i} ended after its mark, before its picture")));
                            break;
                        }
                        Ok(false) => break,
                        Err(e) => {
                            let _ = send(Err(e));
                            break;
                        }
                    }
                    i += 1;
                }
            });
            let (mut n, mut saved) = (0u32, 0u32);
            // The last picture's buffer: never written again once sent, so a repeat is a new sample of the same buffer
            // (no new 3-12 MB buffer, no copy: a still stretch costs the encoder only its own work).
            let mut last: Option<IMFMediaBuffer> = None;
            let (mut waited, mut converted, mut encoded) = (0f64, 0f64, 0f64); // seconds, for the log
            let mut lap = std::time::Instant::now();
            let mut took = |into: &mut f64| {
                *into += lap.elapsed().as_secs_f64();
                lap = std::time::Instant::now();
            };
            while let Ok(read) = full.recv() {
                took(&mut waited);
                // A new picture straight into a new buffer, as NV12 (a repeat: the buffer before again).
                let got = read?;
                let fresh = matches!(got, Got::Pic(_));
                match got {
                    Got::Pic(pic) => {
                        let buf = step(format!("frame {n}: MFCreateMemoryBuffer"), MFCreateMemoryBuffer(size as u32))?;
                        let mut p = std::ptr::null_mut();
                        step(format!("frame {n}: locking its buffer"), buf.Lock(&mut p, None, None))?;
                        let into = std::slice::from_raw_parts_mut(p, size);
                        if nv12_in {
                            into.copy_from_slice(&pic);
                        } else {
                            crate::nv12::from_rgba(&pic, wu, hu, into);
                        }
                        step(format!("frame {n}: unlocking its buffer"), buf.Unlock())?;
                        step(format!("frame {n}: SetCurrentLength"), buf.SetCurrentLength(size as u32))?;
                        let _ = free.send(pic);
                        last = Some(buf);
                    }
                    Got::Again if last.is_none() => return Err("frame 0 is marked as the picture before it again; there is none".into()),
                    Got::Again => {}
                    Got::Save(path) => {
                        if n == 0 {
                            return Err(format!("save as {path}: no frames since the file before"));
                        }
                        // The next writer (made ahead) takes the frames after this at once; this file is finished
                        // (Finalize: its last pictures out of the card's encoder, 0.2-0.3 s) and renamed on a thread of
                        // its own meanwhile, so an export cut into 33 files never waits for one.
                        let taken = spare.take()?;
                        let mut next = 0.0;
                        took(&mut next);
                        spare.arm(sp);
                        eprintln!("encode-mp4: {n} frames; waiting for frames {waited:.2} s, converting {converted:.2} s, encoder {encoded:.2} s, waiting for the next writer {next:.3} s");
                        match lane.as_mut() {
                            Some(l) => {
                                let done = std::mem::replace(l, lanes::Lane::start(taken, fps, room.clone()));
                                finishing.0.push(done.save(path));
                                // At most lanes_n files at once: this one and those still encoding or finishing.
                                finishing.limit(lanes_n - 1)?;
                            }
                            None => {
                                let done = std::mem::replace(file.as_mut().expect("a writer"), taken);
                                finishing.check()?;
                                finishing.add(done, path, n);
                            }
                        }
                        (saved, n, waited, converted, encoded) = (saved + n, 0, 0.0, 0.0, 0.0);
                        continue;
                    }
                }
                took(&mut converted);
                let buf = last.as_ref().expect("a picture before (checked above)");
                if let Some(l) = lane.as_mut() {
                    l.push(buf, fresh, &room)?;
                    took(&mut encoded);
                    n += 1;
                    continue;
                }
                let file = file.as_ref().expect("a writer");
                let sample = step(format!("frame {n}: MFCreateSample"), MFCreateSample())?;
                step(format!("frame {n}: AddBuffer"), sample.AddBuffer(buf))?;
                // 100 ns units from the frame number, exact: no drift over a long film.
                let at = |i: u32| i as i64 * 10_000_000 / fps as i64;
                step(format!("frame {n}: SetSampleTime"), sample.SetSampleTime(at(n)))?;
                step(format!("frame {n}: SetSampleDuration"), sample.SetSampleDuration(at(n + 1) - at(n)))?;
                step(format!("frame {n}: encoding (WriteSample)"), file.writer.WriteSample(file.stream, &sample))?;
                took(&mut encoded);
                n += 1;
            }
            if keep {
                // Frames never saved have no file to go to: the hidden one goes with its writer. The files being
                // finished are waited for (each is saved whole or fails loudly).
                if let Some(f) = file.take() {
                    let tmp = f.path.clone();
                    drop(f);
                    let _ = std::fs::remove_file(tmp);
                }
                drop(lane);
                finishing.wait()?;
                return Ok(saved);
            }
            if n == 0 {
                return Err("no frames arrived".into());
            }
            step("finishing the MP4 (Finalize)", file.as_ref().expect("a writer").writer.Finalize())?;
            let mut finished = 0.0;
            took(&mut finished);
            eprintln!("encode-mp4: {n} frames; waiting for frames {waited:.2} s, converting {converted:.2} s, encoder {encoded:.2} s, finishing {finished:.2} s");
            Ok(n)
        }
    }
}
