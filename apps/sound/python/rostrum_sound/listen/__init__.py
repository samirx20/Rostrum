"""The agent's ears: plain functions that turn a wav into facts (dict) and pictures (PNG path)."""
from .levels import levels
from .loudness import loudness
from .low_end import low_end
from .onsets import onsets
from .spectrogram import spectrogram
from .stereo import stereo

__all__ = ["loudness", "levels", "onsets", "spectrogram", "stereo", "low_end"]
