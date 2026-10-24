"""The frame: what a scene exports, and its camera (design: apps/2d/FRAME.md). Every composition holds exactly one,
a layer of type `camera` (the word `frame` is a drawing's frame). `fields.py` its fields, `view.py` its maths,
`rules.py` what the document refuses, `make.py` a new one, `convert.py` an older file's cameras turned into it."""
TYPE = "camera"
