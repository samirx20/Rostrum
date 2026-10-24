"""The vetted cleanup models (apps/sound/MODELS.md: licences of code and weights, training data, measurements).
A model is loaded for one job and released when the job ends; nothing stays in memory between jobs.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from rostrum_core import RostrumError, codes

from .. import memory, settings


@dataclass(frozen=True)
class Model:
    id: str            # folder under the models folder
    file: str
    size: int          # bytes, checked before loading
    sha256: str
    licence: str
    engine: str        # the cache key's engine: bump when anything that decides the output changes
    need_gb: float     # free memory the job needs (measured, MODELS.md)
    url: str = ""      # where `fetch.install` downloads it (a pinned address: the file's hash is checked after)


DFN3 = Model("deepfilternet3", "denoiser_model.onnx", 16104687,
             "fe5eb64fa2e4154c83f8e4935e82871c850c154387ee892e0ab65fe179e7d8c9",
             "MIT OR Apache-2.0 (DeepFilterNet 3, Schröter et al.; torchDF single-graph export)",
             "deepfilternet3-torchdf-fe5eb64f@2", 1.0,
             "https://huggingface.co/kimtos-labs/denoiser-dfn3/resolve/888f33c41851d7168ae31c3637c323b9e2f3c2a4/denoiser_model.onnx")
UMXHQ = Model("umxhq", "umxhq.onnx", 142496426,
              "b26b5f5a4ff0e919825d28b355bac648908a271f00990bf8ca2f238c87863ec9",
              "MIT (Open-Unmix UMX-HQ, sigsep, Zenodo 3370489; trained on MUSDB18-HQ); our ONNX export",
              "umxhq-onnx-b26b5f5a@1", 2.0,
              # TO DO BEFORE RELEASE: this is our own export and is not hosted yet. Upload umxhq.onnx (142496426 bytes) as an
              # asset of the GitHub release "models-v1" (needs Sam's OK to publish); until then the download says "not available".
              "https://github.com/samirx20/Rostrum/releases/download/models-v1/umxhq.onnx")


def models_dir() -> Path:
    return settings.models_dir()


def path(m: Model) -> Path:
    """The model's file, checked to be there and whole (loud error naming the folder otherwise)."""
    from .fetch import bundle_of, next_step
    f = models_dir() / m.id / m.file
    if not f.is_file():
        raise RostrumError(codes.MODEL_MISSING, "cleanup", m.id, f"is not installed (missing {f})",
                           hint=next_step(bundle_of(m)))
    if f.stat().st_size != m.size:
        raise RostrumError(codes.MODEL_MISSING, "cleanup", m.id, f"{f} is {f.stat().st_size} bytes, expected {m.size} "
                           "(a broken or different download)", hint=f"Delete it, then: {next_step(bundle_of(m))}")
    return f


def session(m: Model, device: str = "cpu"):
    """An ONNX Runtime session for one job (release it by dropping it: `del s`). `device`: "cpu" or "gpu"
    (DirectML on Windows). ROSTRUM_CLEANUP_DEVICE overrides."""
    import onnxruntime as ort
    memory.gate("cleanup", m.id, m.need_gb)
    device = os.environ.get("ROSTRUM_CLEANUP_DEVICE", device)
    providers = ["DmlExecutionProvider", "CPUExecutionProvider"] if device == "gpu" else ["CPUExecutionProvider"]
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 3          # RULES: at most 3 workers per agent
    opts.log_severity_level = 3
    return ort.InferenceSession(str(path(m)), opts, providers=providers)
