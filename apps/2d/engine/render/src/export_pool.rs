//! An export's extra drawing workers, kept alive between exports (export_crew.rs). Each is a thread that owns its session
//! (serve.rs `twin`: its page and, on the GPU, its own GL context, made and used on that thread only) for as long as
//! the export's session lives: a film exported in parts, or exported again after an edit, starts drawing at once
//! instead of making 2 workers' page, fonts and GL context per request (~1.2-1.7 s each time, 7 times a film).
//!
//! A worker's session is made once; a new page shell (other fonts) is put up on the session it has (serve.rs `page`). Between exports a worker frees the GPU
//! memory it kept (painter.rs `release`), so an idle worker holds its context and page, not a frame budget of card
//! memory. The pool goes with its session (a size change, the engine closing): its threads end and drop their
//! sessions on their own threads.
//!
//! `run` lends each worker a job that borrows the caller's data (the scene, the request, the encoder's turn) and waits
//! until every worker has finished it before returning, also when the caller panics, so the borrow never outlives
//! the job (the same contract as std::thread::scope).

use std::panic::{catch_unwind, AssertUnwindSafe};
use std::sync::mpsc::{channel, Receiver, Sender};
use std::thread::JoinHandle;

use crate::serve::{self, Like, Session};

/// A worker's job: its number (1..) and its session slot (None until the first job makes it).
type Job = dyn Fn(usize, &mut Option<Session>) + Sync;

struct Worker {
    tx: Option<Sender<&'static Job>>,
    done: Receiver<()>,
    thread: Option<JoinHandle<()>>,
}

#[derive(Default)]
pub(crate) struct Pool {
    workers: Vec<Worker>,
}

impl Pool {
    /// Runs `job` on workers 1..=`extra` (made the first time they are needed) while `here` runs on this thread; returns
    /// `here`'s result once every worker has finished the job.
    pub(crate) fn run<'a, R>(&mut self, extra: usize, job: &'a (dyn Fn(usize, &mut Option<Session>) + Sync + 'a), here: impl FnOnce() -> R) -> R {
        while self.workers.len() < extra {
            self.workers.push(spawn(self.workers.len() + 1));
        }
        // SAFETY: the reference is used only while the job runs, and `Wait` (below, also on unwinding) returns only
        // after each worker it was sent to has said it finished (or its thread is gone, so it no longer runs it).
        let job: &'static Job = unsafe { std::mem::transmute::<&'a (dyn Fn(usize, &mut Option<Session>) + Sync + 'a), &'static Job>(job) };
        let mut wait = Wait(Vec::with_capacity(extra));
        for w in &self.workers[..extra] {
            if w.tx.as_ref().is_some_and(|tx| tx.send(job).is_ok()) {
                wait.0.push(&w.done);
            }
        }
        here()
    }
}

/// Waits, when dropped, for every worker a job was sent to.
struct Wait<'a>(Vec<&'a Receiver<()>>);

impl Drop for Wait<'_> {
    fn drop(&mut self) {
        for done in &self.0 {
            let _ = done.recv(); // Err: the thread is gone, so it no longer runs the job
        }
    }
}

fn spawn(n: usize) -> Worker {
    let (tx, rx) = channel::<&'static Job>();
    let (done_tx, done) = channel();
    let thread = std::thread::Builder::new()
        .name(format!("export worker {n}"))
        .spawn(move || {
            let mut session: Option<Session> = None;
            for job in rx {
                // A panic is the job's to report (export_crew.rs catches its own); here it only must not end the worker
                // before it says it finished.
                if catch_unwind(AssertUnwindSafe(|| job(n, &mut session))).is_err() {
                    session = None;
                }
                if done_tx.send(()).is_err() {
                    break;
                }
            }
        })
        .expect("starting an export worker thread");
    Worker { tx: Some(tx), done, thread: Some(thread) }
}

impl Drop for Pool {
    fn drop(&mut self) {
        for w in &mut self.workers {
            w.tx = None; // its loop ends
        }
        for w in &mut self.workers {
            if let Some(t) = w.thread.take() {
                let _ = t.join();
            }
        }
    }
}

/// A worker's session for an export like `like` on the page shell `html`: the one it kept (a new shell put up on it
/// when the fonts changed), else a new one; whether it was made now. The pool lives in the export's session, whose size,
/// depth, colour and card never change (a new size opens a new session, and a new pool), so a kept one is always like it.
pub(crate) fn session<'s>(slot: &'s mut Option<Session>, like: &Like, html: &str) -> Result<(&'s mut Session, bool), String> {
    let made = slot.is_none();
    if made {
        *slot = Some(serve::twin(like, html)?);
    }
    let s = slot.as_mut().unwrap();
    if s.shell != html {
        serve::page(s, &serde_json::json!({ "html": html }))?;
    }
    Ok((s, made))
}
