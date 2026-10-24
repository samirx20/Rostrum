"""Lip sync, shared by every app (2D keys a rig's mouth layers, 3D keys a mouth group's swapped shapes). No Qt.
`audio.py` reads the clip, `english.py` turns text into the aligner's phone labels (CMUdict, our own ARPAbet -> IPA
table), `model.py` runs the phone model on demand, `ctc.py` aligns or decodes, `phonemes.py` is the cached job,
`visemes.py` the nine mouth shapes and the timing tools, `keys.py` plans one-shape-at-a-time keys, `track.py` is the
whole job (phones -> cues -> keys), `voice.py` lists the project's voice lines from RostrumSound. Design: apps/2d/LIPSYNC.md.
"""
