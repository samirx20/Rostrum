//! The encoder a render's frames go to (serve.rs `open.encode`): the renderer starts it (ffmpeg with the
//! host's arguments, raw frames on its stdin) and hands it each frame's pixels on a writer thread, so the
//! frames never pass through the host and painting the next frame overlaps writing this one. A bounded
//! queue of two frames holds memory and keeps the order; the pipe holds a whole frame (big_pipe.rs). `finish` closes its input and waits for it; an
//! encoder that stopped fails the next frame with what it said (AGENTS.md rule 6).

use std::io::{Read, Write};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{sync_channel, SyncSender};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;

/// A queued frame as the surface stores it (premultiplied half floats in the working space), put through the
/// output step (color.rs) on the writer thread, off the paint loop: 16-bit (`deep`) or 8-bit with dither.
pub struct Pixels {
    pub raw: Vec<u8>,
    pub spec: crate::color::Spec,
    pub width: u32,
    pub deep: bool,
    /// The document frame number (the dither's seed).
    pub index: u32,
}

impl Pixels {
    fn bytes(self) -> Vec<u8> {
        let mut out = vec![];
        crate::color::output(&self.spec, &self.raw, self.width, self.deep, false, self.index, &mut out);
        out
    }
}

pub struct Sink {
    tx: Option<SyncSender<Pixels>>,
    writer: Option<JoinHandle<Result<(), String>>>,
    child: Child,
    /// The end of the encoder's stderr (what it says when it fails).
    said: Arc<Mutex<String>>,
    reader: Option<JoinHandle<()>>,
    /// Frames queued so far, and whether each came right after the one before (an export checks both).
    pushed: u64,
    last: Option<u32>,
    in_order: bool,
}

impl Sink {
    pub fn start(program: &str, args: &[String]) -> Result<Sink, String> {
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
            for frame in rx {
                stdin.write_all(&frame.bytes()).map_err(|e| e.to_string())?;
            }
            Ok(())
        });
        Ok(Sink { tx: Some(tx), writer: Some(writer), child, said, reader: Some(reader), pushed: 0, last: None, in_order: true })
    }

    fn stopped(&mut self) -> String {
        let code = self.child.try_wait().ok().flatten().map(|s| s.code().unwrap_or(-1));
        let said = self.said.lock().unwrap().trim().to_string();
        format!("the encoder stopped{}: {said}", code.map(|c| format!(" (code {c})")).unwrap_or_default())
    }

    /// Queues a frame's pixels (waits while two are queued).
    pub fn push(&mut self, pixels: Pixels) -> Result<(), String> {
        self.in_order &= self.last.map_or(true, |l| pixels.index == l + 1);
        (self.pushed, self.last) = (self.pushed + 1, Some(pixels.index));
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

    /// How many frames were queued.
    pub fn pushed(&self) -> u64 {
        self.pushed
    }

    /// Whether every frame's number was one more than the frame before.
    pub fn in_order(&self) -> bool {
        self.in_order
    }

    /// The encoder it used, as encode_mp4.rs names it on stderr ("encode-mp4: encoder <name> (graphics card)" or
    /// "(processor: …)"): {name, gpu}; None from an encoder that doesn't say (FFmpeg, pictures).
    pub fn encoder(&self) -> Option<serde_json::Value> {
        let said = self.said.lock().unwrap();
        let line = said.lines().find_map(|l| l.strip_prefix("encode-mp4: encoder "))?;
        let gpu = line.ends_with("(graphics card)");
        let name = line.rsplit_once(" (").map_or(line, |(n, _)| n);
        Some(serde_json::json!({ "name": name, "gpu": gpu }))
    }

    /// Closes the encoder's input and waits for it: its exit code, or an error with what it said.
    pub fn finish(&mut self) -> Result<i32, String> {
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

impl Drop for Sink {
    /// A render that ends without `finish` (an error, a closed host) stops its encoder.
    fn drop(&mut self) {
        if self.tx.is_some() {
            drop(self.tx.take());
            let _ = self.child.kill();
            let _ = self.child.wait();
        }
    }
}
