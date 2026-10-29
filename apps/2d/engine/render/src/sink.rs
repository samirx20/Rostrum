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
    pub fn for_encoder(self, nv12: bool) -> Pixels {
        let px = self.converted();
        if !nv12 || px.nv12 || px.repeat {
            return px;
        }
        let (w, h) = (px.width as usize, px.raw.len() / (px.width as usize * 4));
        let mut out = vec![0u8; w * h * 3 / 2];
        crate::nv12::from_rgba(&px.raw, w, h, &mut out);
        Pixels { raw: out, nv12: true, ..px }
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

struct Encoder {
    tx: Option<SyncSender<Pixels>>,
    writer: Option<JoinHandle<Result<(), String>>>,
    child: Child,
    /// The end of the encoder's stderr (what it says when it fails).
    said: Arc<Mutex<String>>,
    reader: Option<JoinHandle<()>>,
}

impl Sink {
    /// `repeats`: the encoder takes repeated frames as marks (encode_mp4.rs `--tagged`): each frame comes after a byte,
    /// 0 for a picture that follows, 1 for the picture before it again; else a repeat is written whole.
    /// `nv12`: it takes NV12 frames (encode_mp4.rs `--nv12`), converted by whoever pushes them (`Pixels::for_encoder`).
    pub fn start(program: &str, args: &[String], repeats: bool, nv12: bool) -> Result<Sink, String> {
        Ok(Sink { nv12, ..Sink::of(To::Encoder(Encoder::start(program, args, repeats)?)) })
    }

    /// Whether its encoder takes NV12 (a worker's turn converts each frame before its turn: sink_turn.rs).
    pub fn wants_nv12(&self) -> bool {
        self.nv12
    }

    /// A worker's sink: its frames go to `turn`'s encoder when their turn comes.
    pub fn turn(turn: Arc<Turn>) -> Sink {
        Sink::of(To::Turn(turn))
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
        let keep = said.clone();
        let reader = std::thread::spawn(move || {
            let mut buf = [0u8; 4096];
            while let Ok(n) = stderr.read(&mut buf) {
                if n == 0 {
                    break;
                }
                let mut s = keep.lock().unwrap();
                s.push_str(&String::from_utf8_lossy(&buf[..n]));
                if s.len() > 8000 {
                    let cut = s.len() - 4000;
                    let cut = (cut..s.len()).find(|&i| s.is_char_boundary(i)).unwrap_or(s.len());
                    s.drain(..cut);
                }
            }
        });
        let (tx, rx) = sync_channel::<Pixels>(2);
        let writer = std::thread::spawn(move || {
            let mut last: Vec<u8> = vec![];
            for frame in rx {
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
        Ok(Encoder { tx: Some(tx), writer: Some(writer), child, said, reader: Some(reader) })
    }

    fn stopped(&mut self) -> String {
        let code = self.child.try_wait().ok().flatten().map(|s| s.code().unwrap_or(-1));
        let said = self.said.lock().unwrap().trim().to_string();
        format!("the encoder stopped{}: {said}", code.map(|c| format!(" (code {c})")).unwrap_or_default())
    }

    fn push(&mut self, pixels: Pixels) -> Result<(), String> {
        let sent = self.tx.as_ref().ok_or("the encoder is finished")?.send(pixels);
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
    /// A render that ends without `finish` (an error, a closed host) stops its encoder.
    fn drop(&mut self) {
        if self.tx.is_some() {
            drop(self.tx.take());
            let _ = self.child.kill();
            let _ = self.child.wait();
        }
    }
}
