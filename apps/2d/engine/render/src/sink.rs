//! The encoder a render's frames go to (serve.rs `open.encode`): the renderer starts it (ffmpeg with the
//! host's arguments, raw frames on its stdin) and hands it each frame's pixels on a writer thread, so the
//! frames never pass through the host and painting the next frame overlaps writing this one. A bounded
//! queue of two frames holds memory and keeps the order; the pipe holds a whole frame (big_pipe.rs). `finish` closes its input and waits for it; an
//! encoder that stopped fails the next frame with what it said (AGENTS.md rule 6).
//!
//! A sink is either that encoder or a turn at one encoder shared by an export's drawing workers (sink_turn.rs):
//! each worker's frames wait there until every frame before them has gone in, so the encoder still gets every
//! frame once, in order.

use std::io::{Read, Write};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{sync_channel, SyncSender};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;

use crate::sink_turn::Turn;

/// A queued frame as the surface stores it (premultiplied half floats in the working space), put through the
/// output step (color.rs) on the writer thread, off the paint loop: 16-bit (`deep`) or 8-bit with dither.
pub struct Pixels {
    pub raw: Vec<u8>,
    pub spec: crate::color::Spec,
    pub width: u32,
    pub deep: bool,
    /// The document frame number (the dither's seed).
    pub index: u32,
    /// `raw` already went through the output step (`converted`): the encoder's bytes as they are.
    pub ready: bool,
    /// The same picture as the frame before it (serve.rs `repeat`): `raw` is empty and the encoder gets that frame's
    /// bytes again (or, one that takes repeats, a mark: `Sink::start`).
    pub repeat: bool,
    /// `raw` is the encoder's NV12 already (`for_encoder`): written as it is.
    pub nv12: bool,
}

impl Pixels {
    /// The frame put through the output step now, on this thread (an export's drawing workers do it side by side,
    /// sink_turn.rs, instead of the one writer thread): the same bytes the writer would make.
    pub fn converted(self) -> Pixels {
        let (spec, width, deep, index, repeat, nv12) = (self.spec, self.width, self.deep, self.index, self.repeat, self.nv12);
        Pixels { raw: self.bytes(), spec, width, deep, index, ready: true, repeat, nv12 }
    }

    /// The frame as the encoder takes it, made on this thread: converted, and into NV12 when it takes NV12 (`nv12`,
    /// encode_mp4.rs `--nv12`; nv12.rs, the same bytes the encoder made itself before). A repeat stays a mark.
    /// `ROSTRUM_NV12_DUMP=<folder>`: each NV12 frame is also written there as <index>.nv12 (nv12_check.py compares the
    /// GPU's with the CPU's).
    pub fn for_encoder(self, nv12: bool) -> Pixels {
        let px = self.converted();
        assert!(nv12 || !px.nv12, "an NV12 frame for an encoder taking RGBA");
        if !nv12 || px.repeat {
            return px;
        }
        if px.nv12 {
            return px.dumped();
        }
        let (w, h) = (px.width as usize, px.raw.len() / (px.width as usize * 4));
        let mut out = vec![0u8; w * h * 3 / 2];
        crate::nv12::from_rgba(&px.raw, w, h, &mut out);
        Pixels { raw: out, nv12: true, ..px }.dumped()
    }

    fn dumped(self) -> Pixels {
        if let Some(dir) = std::env::var_os("ROSTRUM_NV12_DUMP") {
            let path = std::path::Path::new(&dir).join(format!("{}.nv12", self.index));
            std::fs::write(&path, &self.raw).unwrap_or_else(|e| panic!("ROSTRUM_NV12_DUMP: writing {}: {e}", path.display()));
        }
        self
    }

    fn bytes(self) -> Vec<u8> {
        if self.ready {
            return self.raw;
        }
        let mut out = vec![];
        crate::color::output(&self.spec, &self.raw, self.width, self.deep, false, self.index, &mut out);
        out
    }
}

pub struct Sink {
    to: To,
    /// The encoder takes NV12 (`Sink::start`'s `nv12`): frames are converted before they reach it.
    nv12: bool,
    /// Frames queued so far, and whether each came right after the one before (an export checks both).
    pushed: u64,
    last: Option<u32>,
    in_order: bool,
}

enum To {
    Encoder(Encoder),
    /// A drawing worker's frames, through the export's one encoder in frame order.
    Turn(Arc<Turn>),
    /// Tests: every frame's encoder bytes, kept in the order they came (sink_turn.rs tests).
    #[cfg(test)]
    Kept(Arc<Mutex<Vec<(u32, Vec<u8>)>>>),
}

/// What the frame writer thread sends the encoder: a frame, or (a kept encoder: encode_mp4.rs `--keep`) "save the frames
/// so far as this file".
enum Out {
    Frame(Pixels),
    Save(String),
}

/// Tests (`Sink::kept`): a save mark among the kept frames, its path as the bytes.
#[cfg(test)]
pub const SAVE_MARK: u32 = u32::MAX;

struct Encoder {
    tx: Option<SyncSender<Out>>,
    writer: Option<JoinHandle<Result<(), String>>>,
    child: Child,
    /// Kept between exports (encode_mp4.rs `--keep=`): it saves each export's file and goes on (`Sink::save`).
    kept: bool,
    /// The end of the encoder's stderr (what it says when it fails).
    said: Arc<Mutex<String>>,
    /// Each file a kept encoder has saved since `begin_file`, with its frame count ("encode-mp4: saved <n> <path>"), kept
    /// apart from `said` (whose start is cut away on a long export: 33 files' lines are more than it holds).
    saved: Arc<Mutex<Vec<(u32, String)>>>,
    reader: Option<JoinHandle<()>>,
}

impl Sink {
    /// `repeats`: the encoder takes repeated frames as marks (encode_mp4.rs `--tagged`): each frame comes after a byte,
    /// 0 for a picture that follows, 1 for the picture before it again; else a repeat is written whole.
    /// `nv12`: it takes NV12 frames (encode_mp4.rs `--nv12`), converted by whoever pushes them (`Pixels::for_encoder`).
    pub fn start(program: &str, args: &[String], repeats: bool, nv12: bool) -> Result<Sink, String> {
        Ok(Sink { nv12, ..Sink::of(To::Encoder(Encoder::start(program, args, repeats)?)) })
    }

    /// Whether its encoder takes NV12 (a worker's turn converts each frame before its turn: sink_turn.rs; frames read
    /// back from the GPU come as NV12 already: painter.rs `start_read`).
    pub fn wants_nv12(&self) -> bool {
        self.nv12
    }

    /// A worker's sink: its frames go to `turn`'s encoder when their turn comes.
    pub fn turn(turn: Arc<Turn>) -> Sink {
        Sink { nv12: turn.nv12(), ..Sink::of(To::Turn(turn)) }
    }

    /// Tests: a sink keeping each frame's encoder bytes, in order, in `into`.
    #[cfg(test)]
    pub fn kept(into: Arc<Mutex<Vec<(u32, Vec<u8>)>>>) -> Sink {
        Sink::of(To::Kept(into))
    }

    fn of(to: To) -> Sink {
        Sink { to, nv12: false, pushed: 0, last: None, in_order: true }
    }

    /// Queues a frame's pixels (waits while two are queued; a worker's, until the frames before it are in).
    pub fn push(&mut self, pixels: Pixels) -> Result<(), String> {
        self.in_order &= self.last.map_or(true, |l| pixels.index == l + 1);
        (self.pushed, self.last) = (self.pushed + 1, Some(pixels.index));
        match &mut self.to {
            To::Encoder(e) => e.push(pixels.for_encoder(self.nv12)),
            To::Turn(t) => t.push(pixels),
            #[cfg(test)]
            To::Kept(k) => {
                let (index, repeat) = (pixels.index, pixels.repeat);
                let mut k = k.lock().unwrap();
                let bytes = if repeat { k.last().map(|l| l.1.clone()).ok_or("a repeat with no frame before it")? } else { pixels.bytes() };
                k.push((index, bytes));
                Ok(())
            }
        }
    }

    /// How many frames were queued.
    pub fn pushed(&self) -> u64 {
        self.pushed
    }

    /// Whether every frame's number was one more than the frame before.
    pub fn in_order(&self) -> bool {
        self.in_order
    }

    /// The encoder it used, as encode_mp4.rs names it on stderr ("encode-mp4: encoder <name> (graphics card)" or
    /// "(processor: …)"): {name, gpu, steps: where its time went, when it has finished}; None from an encoder that doesn't say (FFmpeg, pictures) and from a worker's turn.
    pub fn encoder(&self) -> Option<serde_json::Value> {
        let To::Encoder(e) = &self.to else { return None };
        let said = e.said.lock().unwrap();
        let line = said.lines().find_map(|l| l.strip_prefix("encode-mp4: encoder "))?;
        let gpu = line.ends_with("(graphics card)");
        let name = line.rsplit_once(" (").map_or(line, |(n, _)| n);
        // Where its time went, once it has finished ("2040 frames; waiting for frames … s, converting … s, encoder … s").
        let steps = said.lines().find_map(|l| l.strip_prefix("encode-mp4: ").filter(|l| l.contains(" frames; ")));
        Some(serde_json::json!({ "name": name, "gpu": gpu, "steps": steps }))
    }

    /// A kept encoder (`--keep`): the frames so far saved as `path`; it keeps running for the next export, its counts
    /// starting again (`pushed`, `in_order` are each file's).
    pub fn save(&mut self, path: &str) -> Result<(), String> {
        self.mark_save(path)?;
        let n = self.pushed as u32;
        self.wait_saved(&[(n, path.to_string())]).map(|_| ())
    }

    /// A kept encoder: "save the frames since the file before as `path`" queued after the frames so far, not waited for
    /// (an export's segment cuts, sink_turn.rs: the drawing goes on while the encoder finishes that file).
    pub fn mark_save(&mut self, path: &str) -> Result<(), String> {
        match &mut self.to {
            To::Encoder(e) if e.kept => e.send(Out::Save(path.to_string())),
            #[cfg(test)]
            To::Kept(k) => {
                k.lock().unwrap().push((SAVE_MARK, path.as_bytes().to_vec()));
                Ok(())
            }
            _ => Err("save: not a kept encoder (--keep)".into()),
        }
    }

    /// Waits until the kept encoder has saved each of `files` (frames, path): its own count must be each one's. Returns
    /// the seconds waited. An encoder that stopped first fails with what it said.
    pub fn wait_saved(&mut self, files: &[(u32, String)]) -> Result<f64, String> {
        let t0 = std::time::Instant::now();
        let To::Encoder(e) = &mut self.to else { return Ok(0.0) };
        for (want, path) in files {
            let n = e.wait_saved(path)?;
            if n != *want {
                return Err(format!("the encoder saved {n} frames as {path}, not {want}"));
            }
        }
        Ok(t0.elapsed().as_secs_f64())
    }

    /// The next export's frames start here (a kept encoder): its counts start again.
    pub fn begin_file(&mut self) {
        (self.pushed, self.last, self.in_order) = (0, None, true);
        if let To::Encoder(e) = &self.to {
            e.saved.lock().unwrap().clear();
            // what it said about earlier files goes; which encoder it is stays (`encoder`)
            let mut said = e.said.lock().unwrap();
            *said = said.lines().filter(|l| l.starts_with("encode-mp4: encoder ") || l.starts_with("encode-mp4: started in")).map(|l| format!("{l}
")).collect();
        }
    }

    /// Whether this is a kept encoder (encode_mp4.rs `--keep`).
    pub fn is_kept(&self) -> bool {
        matches!(&self.to, To::Encoder(e) if e.kept)
    }

    /// Closes the encoder's input and waits for it: its exit code, or an error with what it said.
    pub fn finish(&mut self) -> Result<i32, String> {
        match &mut self.to {
            To::Encoder(e) => e.finish(),
            To::Turn(_) => Err("a drawing worker's frames are finished by the export, not the worker".into()),
            #[cfg(test)]
            To::Kept(_) => Ok(0),
        }
    }
}

impl Encoder {
    fn start(program: &str, args: &[String], repeats: bool) -> Result<Encoder, String> {
        let mut cmd = Command::new(program);
        cmd.args(args).stdout(Stdio::null()).stderr(Stdio::piped());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
        }
        let (mut child, mut stdin) = crate::big_pipe::spawn(&mut cmd).map_err(|e| format!("the encoder ({program}) could not start: {e}"))?;
        drop(cmd); // it holds a copy of the pipe's reading end: with it gone, a stopped encoder shows as a failed write
        let mut stderr = child.stderr.take().expect("piped stderr");
        let said = Arc::new(Mutex::new(String::new()));
        let saved = Arc::new(Mutex::new(vec![]));
        let (keep, files) = (said.clone(), saved.clone());
        let reader = std::thread::spawn(move || {
            let mut buf = [0u8; 4096];
            let mut line = String::new();
            while let Ok(n) = stderr.read(&mut buf) {
                if n == 0 {
                    break;
                }
                let text = String::from_utf8_lossy(&buf[..n]);
                // whole lines only: a "saved" line may come in two reads
                line.push_str(&text);
                while let Some(end) = line.find('\n') {
                    let l: String = line.drain(..=end).collect();
                    if let Some((n, path)) = l.trim_end().strip_prefix("encode-mp4: saved ").and_then(|r| r.split_once(' ')) {
                        files.lock().unwrap().push((n.parse().unwrap_or(0), path.to_string()));
                    }
                }
                let mut s = keep.lock().unwrap();
                s.push_str(&text);
                if s.len() > 8000 {
                    let cut = s.len() - 4000;
                    let cut = (cut..s.len()).find(|&i| s.is_char_boundary(i)).unwrap_or(s.len());
                    s.drain(..cut);
                }
            }
        });
        let (tx, rx) = sync_channel::<Out>(2);
        let writer = std::thread::spawn(move || {
            let mut last: Vec<u8> = vec![];
            for out in rx {
                let frame = match out {
                    Out::Frame(f) => f,
                    Out::Save(path) => {
                        let mut mark = vec![2u8];
                        mark.extend((path.len() as u32).to_le_bytes());
                        mark.extend(path.as_bytes());
                        stdin.write_all(&mark).map_err(|e| e.to_string())?;
                        continue;
                    }
                };
                if frame.repeat {
                    if last.is_empty() {
                        return Err("a repeated frame with no frame before it".to_string());
                    }
                    let mark: &[u8] = if repeats { &[1] } else { &last };
                    stdin.write_all(mark).map_err(|e| e.to_string())?;
                    continue;
                }
                last = frame.bytes();
                if repeats {
                    stdin.write_all(&[0]).map_err(|e| e.to_string())?;
                }
                stdin.write_all(&last).map_err(|e| e.to_string())?;
            }
            Ok(())
        });
        let kept = args.iter().any(|a| a.starts_with("--keep="));
        Ok(Encoder { tx: Some(tx), writer: Some(writer), child, kept, said, saved, reader: Some(reader) })
    }

    fn stopped(&mut self) -> String {
        let code = self.child.try_wait().ok().flatten().map(|s| s.code().unwrap_or(-1));
        let said = self.said.lock().unwrap().trim().to_string();
        format!("the encoder stopped{}: {said}", code.map(|c| format!(" (code {c})")).unwrap_or_default())
    }

    fn push(&mut self, pixels: Pixels) -> Result<(), String> {
        self.send(Out::Frame(pixels))
    }

    fn send(&mut self, out: Out) -> Result<(), String> {
        let sent = self.tx.as_ref().ok_or("the encoder is finished")?.send(out);
        if sent.is_err() {
            // The writer quit: the encoder closed its input.
            if let Some(w) = self.writer.take() {
                let _ = w.join();
            }
            let _ = self.child.wait();
            if let Some(r) = self.reader.take() {
                let _ = r.join();
            }
            return Err(self.stopped());
        }
        Ok(())
    }

    /// A kept encoder (`--keep`): waits until it says it saved `path` (a save mark sent before); the frames in it.
    fn wait_saved(&mut self, path: &str) -> Result<u32, String> {
        loop {
            // its line for this file (the list since `begin_file` holds no other export's)
            if let Some((n, _)) = self.saved.lock().unwrap().iter().find(|(_, p)| p == path) {
                return Ok(*n);
            }
            if self.child.try_wait().ok().flatten().is_some() {
                if let Some(r) = self.reader.take() {
                    let _ = r.join();
                }
                return Err(self.stopped());
            }
            std::thread::sleep(std::time::Duration::from_millis(2));
        }
    }

    fn finish(&mut self) -> Result<i32, String> {
        drop(self.tx.take());
        let wrote = self.writer.take().map(|w| w.join().unwrap_or(Err("the frame writer panicked".into()))).unwrap_or(Ok(()));
        let status = self.child.wait().map_err(|e| e.to_string())?;
        if let Some(r) = self.reader.take() {
            let _ = r.join();
        }
        let code = status.code().unwrap_or(-1);
        if code != 0 || wrote.is_err() {
            return Err(self.stopped());
        }
        Ok(code)
    }
}

impl Drop for Encoder {
    /// A render that ends without `finish` (an error, a closed host) stops its encoder. A kept one that saved its last
    /// file is told the frames are over first, so it removes its hidden files itself (a second at most).
    fn drop(&mut self) {
        if self.tx.is_some() {
            drop(self.tx.take());
            if self.kept {
                if let Some(w) = self.writer.take() {
                    let _ = w.join();
                }
                for _ in 0..500 {
                    if self.child.try_wait().ok().flatten().is_some() {
                        return;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(2));
                }
            }
            let _ = self.child.kill();
            let _ = self.child.wait();
        }
    }
}
