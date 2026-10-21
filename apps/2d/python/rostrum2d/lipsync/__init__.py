"""Lip sync from a voice recording (design: apps/2d/LIPSYNC.md). `audio.py` reads the clip, `english.py` turns text
into the aligner's phone labels (CMUdict, our own ARPAbet → IPA table), `model.py` runs the phone model on demand,
`ctc.py` aligns or decodes, `phonemes.py` is the cached job, `visemes.py` the mouth shapes and timing tools, `keys.py`
the plain opacity keys, `ops.py` the `lipsync.apply` operation, `script.py` the `lipsync(...)` script call."""
