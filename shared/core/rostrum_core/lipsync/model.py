"""The phone model: wav2vec2-lv-60-espeak-cv-ft (Meta, Apache-2.0; onnx-community fp16 export), a CTC head over
espeak-style IPA labels. Loaded for one job and released before `emissions` returns; no session is kept.

Folder: ROSTRUM_PHONES_DIR, else ~/.rostrum/models/wav2vec2-lv60-espeak-fp16 (model_fp16.onnx, vocab.json,
device.json = the device picked before, e.g. {"device": "dml:1"}). ROSTRUM_AI_DEVICE ("cpu", "dml:0" …) forces one.
"""
from __future__ import annotations

import gc
import json
import os
from pathlib import Path

from rostrum_core import RostrumError, codes, memory

from .audio import RATE

ENGINE = "wav2vec2-lv60-espeak@1"     # our version of the whole job: bump when audio, alignment or timing changes
FRAME_S = 0.02                        # one output frame per 320 samples
CHUNK_S, CONTEXT_S = 20, 1            # long audio runs in pieces, each with context on both sides
MIN_FREE_GB = 2.5


def models_dir() -> Path:
    """The person's Rostrum models folder: ROSTRUM_DATA/models, else ~/.rostrum/models."""
    return Path(os.environ.get("ROSTRUM_DATA") or Path.home() / ".rostrum") / "models"


def folder() -> Path:
    return Path(os.environ.get("ROSTRUM_PHONES_DIR") or
                models_dir() / "wav2vec2-lv60-espeak-fp16")


def vocab(where="lipsync") -> dict:
    f = folder() / "vocab.json"
    if not f.is_file():
        raise RostrumError(codes.MODEL_MISSING, where, "the phone model", f"is not installed in {folder()}")
    return json.loads(f.read_text(encoding="utf-8"))


def _device() -> str:
    if os.environ.get("ROSTRUM_AI_DEVICE"):
        return os.environ["ROSTRUM_AI_DEVICE"]
    try:
        return json.loads((folder() / "device.json").read_text(encoding="utf-8"))["device"]
    except (OSError, ValueError, KeyError):
        return "cpu"


def _session(where):
    try:
        import onnxruntime as ort
    except ImportError as e:
        raise RostrumError(codes.MODEL_MISSING, where, "onnxruntime", "is not installed",
                           hint="pip install rostrum_core[lipsync] (onnxruntime-directml on Windows)") from e
    f, dev = folder() / "model_fp16.onnx", _device()
    if not f.is_file():
        raise RostrumError(codes.MODEL_MISSING, where, "the phone model", f"is not installed in {folder()}")
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    if dev.startswith("dml") and "DmlExecutionProvider" in ort.get_available_providers():
        try:
            prov = [("DmlExecutionProvider", {"device_id": int(dev.partition(":")[2] or 0)})]
            return ort.InferenceSession(str(f), opts, providers=prov), dev
        except Exception:
            if os.environ.get("ROSTRUM_AI_DEVICE"):
                raise
    # The CPU's full graph fusion breaks on this fp16 graph (SimplifiedLayerNormFusion, onnxruntime 1.24): basic only.
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    try:
        return ort.InferenceSession(str(f), opts, providers=["CPUExecutionProvider"]), "cpu"
    except Exception as e:
        raise RostrumError(codes.JOB_FAILED, where, "the phone model", f"could not be opened on the CPU: {e}") from e


def _normalized(x):
    import numpy as np
    return ((x - x.mean()) / np.sqrt(x.var() + 1e-7)).astype(np.float32)


def emissions(samples, where="lipsync", progress=None, waiting=None):
    """(log probabilities frames × labels, device). Loads the model, runs it, releases it. `progress(fraction)` is called
    when the model is open (0) and after each piece (a 20 s piece is the finest the model gives). Before it loads it
    waits its turn and for memory (rostrum_core.memory, bounded; `waiting(words)` told meanwhile)."""
    with memory.turn(where, "the phone model", MIN_FREE_GB, waiting=waiting):
        return _run(samples, where, progress)


def _run(samples, where, progress):
    import numpy as np
    from .ctc import log_softmax

    session, dev = _session(where)
    if progress:
        progress(0.0)
    try:
        inp = session.get_inputs()[0]
        dtype = np.float16 if "float16" in inp.type else np.float32
        frames = max(1, int(len(samples) / (RATE * FRAME_S)))
        step, ctx, ctx_f, out = CHUNK_S * RATE, CONTEXT_S * RATE, round(CONTEXT_S / FRAME_S), None
        for a in range(0, len(samples), step):
            lo = max(0, a - ctx)
            piece = _normalized(samples[lo:min(len(samples), a + step + ctx)])
            piece = np.pad(piece, (0, max(0, 800 - len(piece))))
            logits = session.run(None, {inp.name: piece[None, :].astype(dtype)})[0][0].astype(np.float32)
            if out is None:
                out = np.zeros((frames, logits.shape[1]), np.float32)
            first, skip = round(a / (RATE * FRAME_S)), (ctx_f if a > 0 else 0)
            n = min(frames - first, round(CHUNK_S / FRAME_S), logits.shape[0] - skip)
            out[first:first + n] = logits[skip:skip + n]
            if progress:
                progress(min(1.0, (a + step) / len(samples)))
        return log_softmax(out), dev
    except RostrumError:
        raise
    except Exception as e:
        raise RostrumError(codes.JOB_FAILED, where, "the phone model", f"failed on {dev}: {e}") from e
    finally:
        del session
        gc.collect()
