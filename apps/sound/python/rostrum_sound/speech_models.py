"""The speech model's files (Parakeet TDT v3, int8, through sherpa-onnx: voice_words.py) in the same download registry as
the clean-up and voice models (cleanup/fetch.py), so run_model_install can fetch them. Sizes and fingerprints are those
of the files the word timing was measured with (VOICE.md); the address is sherpa-onnx's own copy, pinned to one commit.
Weights CC-BY-4.0 (NVIDIA), code Apache-2.0 (k2-fsa).
"""
from __future__ import annotations

from .cleanup.models import Model

_ENGINE = "parakeet-tdt-0.6b-v3-int8@sherpa-onnx-1.13"          # voice_words.ENGINE
_AT = "https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/resolve/2bda32ec70b097a55adaa07d9a7173915b43cc78/"
_LICENCE = "CC-BY-4.0 weights (NVIDIA Parakeet TDT 0.6B v3), Apache-2.0 export (k2-fsa sherpa-onnx)"


def _file(name: str, size: int, sha: str, gb: float = 0.0) -> Model:
    return Model("parakeet-tdt-0.6b-v3", name, size, sha, _LICENCE, _ENGINE, gb, _AT + name)


FILES = (_file("encoder.int8.onnx", 652184281, "acfc2b4456377e15d04f0243af540b7fe7c992f8d898d751cf134c3a55fd2247", 2.0),
         _file("decoder.int8.onnx", 11845275, "179e50c43d1a9de79c8a24149a2f9bac6eb5981823f2a2ed88d655b24248db4e"),
         _file("joiner.int8.onnx", 6355277, "3164c13fc2821009440d20fcb5fdc78bff28b4db2f8d0f0b329101719c0948b3"),
         _file("tokens.txt", 93939, "d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d"))
