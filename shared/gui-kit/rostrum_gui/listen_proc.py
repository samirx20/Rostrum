"""Listening to a voice line for Lip sync…, in a process of its own (the same reason as 2D's problems_proc.py). On a
thread of the screen's own interpreter it got Python's lock so rarely that a busy screen left the sheet at "Step 1 of
3 · Opening the voice…" for minutes with no error (2D final critic, row 4: 30 s in, it was still importing scipy;
the same job in a plain Python took 15 s). Here the screen's worker thread only waits on a pipe; the phones land in the
shared cache (phonemes.analyse), which the sheet then reads.

Fails loudly: a process that says nothing for `stall_s` seconds (ROSTRUM_LISTEN_STALL_S, default 120; every step and
every "waiting for memory" note counts as saying something) is ended and the wait raises, naming the last step; a
process that dies raises with its exit code.
"""
from __future__ import annotations

import multiprocessing
import os


def stall_s() -> float:
    return float(os.environ.get("ROSTRUM_LISTEN_STALL_S") or 120)


def _child(conn, wav, text):
    try:
        from rostrum_core.lipsync import phonemes
        phonemes.analyse(wav, 0.0, None, text, "english",
                         progress=lambda step, of, words, f: conn.send(("step", step, words, f)))
        conn.send(("ok",))
    except Exception as e:  # noqa: BLE001  handed back through the pipe, raised on the screen's side
        conn.send(("error", str(e) or type(e).__name__))
    finally:
        conn.close()


def listen(wav: str, text: str | None, on_step, stall: float | None = None) -> None:
    """Listen to `wav` (with its `text` for alignment, else free decoding) in a new process; blocks the calling
    (worker) thread until the phones are in the cache. `on_step(step, words, fraction)` as the job goes. Raises
    RuntimeError with plain words on a failure, a stall or a dead process."""
    limit = stall_s() if stall is None else stall
    ctx = multiprocessing.get_context("spawn")
    reader, writer = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child, args=(writer, str(wav), text), name="lipsync-listen", daemon=True)
    proc.start()
    writer.close()
    last = "starting"
    try:
        while True:
            if not reader.poll(limit):
                raise RuntimeError(f"listening to the line stopped answering for {limit:.0f} s (last step: {last}); "
                                   "it was stopped. Try Apply again; on a busy computer close other work first.")
            try:
                msg = reader.recv()
            except (EOFError, OSError):
                proc.join(5)
                raise RuntimeError(f"the listening process ended without an answer (exit code {proc.exitcode}, "
                                   f"last step: {last})") from None
            if msg[0] == "ok":
                return
            if msg[0] == "error":
                raise RuntimeError(msg[1])
            _, step, words, f = msg
            last = f"{step} of 3, {words}"
            on_step(step, words, f)
    finally:
        reader.close()
        proc.join(2)
        if proc.is_alive():
            proc.terminate()                  # our own child, by its handle
            proc.join(5)
