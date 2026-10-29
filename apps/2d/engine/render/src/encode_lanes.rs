//! An export's held encoder (encode_mp4.rs `--keep`) writes each saved file on a thread of its own, a "lane": the
//! frames go to the current file's lane as they come, and when a file is saved its lane goes on encoding the frames it
//! still has (then finishes and renames it) while the next file's lane already takes the frames after it. Two files
//! encode side by side on the graphics card's encoder, each through its own writer: one writer took 232 frames a second
//! at 1080p on the RTX 3050, the whole export's limit (a still film's repeated frames cost it as much as new ones).
//!
//! Memory stays bounded: new pictures waiting in lanes take `Room` (a repeat is the buffer before again, free). A lane
//! that fails keeps giving room back for what it is sent, so the frames' reader never waits on it; its failure is the
//! export's, at the next save or the end.

use std::sync::mpsc::{channel, Sender};
use std::sync::{Arc, Condvar, Mutex};
use std::thread::JoinHandle;

use super::{step, Open};
use windows::Win32::Media::MediaFoundation::*;
use windows::Win32::System::Com::{CoInitializeEx, COINIT_MULTITHREADED};

/// How many new pictures' bytes may wait in lanes at most.
const ROOM_BYTES: usize = 192 << 20;

/// A picture buffer handed to a lane (Media Foundation's buffers are free-threaded in this process's multithreaded COM).
struct Buf(IMFMediaBuffer);
unsafe impl Send for Buf {}

enum Msg {
    /// A frame: its picture's buffer, and whether it is a new picture (it holds room until written).
    Frame(Buf, bool),
    /// The frames so far are this file: finish and rename it.
    Save(String),
}

/// Room for new pictures waiting in lanes.
pub struct Room {
    left: Mutex<usize>,
    cv: Condvar,
}

impl Room {
    pub fn new(picture_bytes: usize) -> Arc<Room> {
        Arc::new(Room { left: Mutex::new((ROOM_BYTES / picture_bytes.max(1)).max(4)), cv: Condvar::new() })
    }

    fn take(&self) {
        let mut left = self.left.lock().unwrap();
        while *left == 0 {
            left = self.cv.wait(left).unwrap();
        }
        *left -= 1;
    }

    fn give(&self) {
        *self.left.lock().unwrap() += 1;
        self.cv.notify_all();
    }
}

/// One file's lane: its thread, and the frames sent to it.
pub struct Lane {
    tx: Option<Sender<Msg>>,
    thread: Option<JoinHandle<Result<(), String>>>,
}

impl Lane {
    /// A lane writing `file`: frame k of it at k / fps.
    pub fn start(file: Open, fps: u32, room: Arc<Room>) -> Lane {
        struct Sent(Open);
        unsafe impl Send for Sent {}
        let file = Sent(file);
        let (tx, rx) = channel::<Msg>();
        let thread = std::thread::spawn(move || {
            let file = file;
            let file = file.0;
            let mut failed: Option<String> = None;
            let (mut n, mut encoded) = (0u32, 0f64);
            if let Err(e) = unsafe { CoInitializeEx(None, COINIT_MULTITHREADED).ok() } {
                failed = Some(format!("an encoding lane could not start COM: {e}"));
            }
            for m in rx {
                match m {
                    Msg::Frame(buf, new) => {
                        if failed.is_none() {
                            let t = std::time::Instant::now();
                            if let Err(e) = unsafe { write(&file, &buf.0, n, fps) } {
                                failed = Some(e);
                            }
                            encoded += t.elapsed().as_secs_f64();
                        }
                        drop(buf);
                        if new {
                            room.give();
                        }
                        n += 1;
                    }
                    Msg::Save(path) => {
                        if let Some(e) = failed {
                            let tmp = file.path.clone();
                            drop(file);
                            let _ = std::fs::remove_file(tmp);
                            return Err(e);
                        }
                        eprintln!("encode-mp4: {n} frames; encoder {encoded:.2} s");
                        return super::finish(file, path, n);
                    }
                }
            }
            // Ended without a save: frames no file takes (the export's end), dropped with the hidden file.
            let tmp = file.path.clone();
            drop(file);
            let _ = std::fs::remove_file(tmp);
            failed.map_or(Ok(()), Err)
        });
        Lane { tx: Some(tx), thread: Some(thread) }
    }

    /// Frame `buf` next in this lane's file (`new`: a new picture, waiting for room first).
    pub fn push(&mut self, buf: &IMFMediaBuffer, new: bool, room: &Room) -> Result<(), String> {
        if new {
            room.take();
        }
        let sent = self.tx.as_ref().map(|tx| tx.send(Msg::Frame(Buf(buf.clone()), new)));
        if sent.is_some_and(|s| s.is_ok()) {
            return Ok(());
        }
        if new {
            room.give();
        }
        Err("an encoding lane stopped".into())
    }

    /// Saves this lane's frames as `path` once written: its thread, which ends when the file is saved (or failed).
    pub fn save(mut self, path: String) -> JoinHandle<Result<(), String>> {
        if let Some(tx) = self.tx.take() {
            let _ = tx.send(Msg::Save(path));
        }
        self.thread.take().expect("a lane's thread")
    }
}

impl Drop for Lane {
    /// A lane never saved: its frames dropped, its hidden file removed, its thread waited for.
    fn drop(&mut self) {
        self.tx = None;
        if let Some(t) = self.thread.take() {
            let _ = t.join();
        }
    }
}

/// Frame `n` of `file` from `buf`: a sample at n / fps lasting one frame, encoded.
unsafe fn write(file: &Open, buf: &IMFMediaBuffer, n: u32, fps: u32) -> Result<(), String> {
    unsafe {
        let sample = step(format!("frame {n}: MFCreateSample"), MFCreateSample())?;
        step(format!("frame {n}: AddBuffer"), sample.AddBuffer(buf))?;
        // 100 ns units from the frame number, exact: no drift over a long film.
        let at = |i: u32| i as i64 * 10_000_000 / fps as i64;
        step(format!("frame {n}: SetSampleTime"), sample.SetSampleTime(at(n)))?;
        step(format!("frame {n}: SetSampleDuration"), sample.SetSampleDuration(at(n + 1) - at(n)))?;
        step(format!("frame {n}: encoding (WriteSample)"), file.writer.WriteSample(file.stream, &sample))
    }
}
