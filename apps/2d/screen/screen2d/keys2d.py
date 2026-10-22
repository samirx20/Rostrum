"""Rostrum2D's own keys, as data on top of the shared key map (rostrum_gui/keymap.py; INTERACTION.md Part 2, the
[2D] rows that 2D uses today). The kit refuses at start-up any of these that would take a shared key. The actions
(actions.py) take their keys from here through `job`; tools and frame-by-frame keys are listed so Ctrl+/ shows them
(Main.qml still runs those itself).
"""
from __future__ import annotations

from rostrum_gui.keymap import KeyMap

OWN = [
    {"job": "pen_tool", "keys": ["P"], "label": "Pen"},
    {"job": "new_drawing", "keys": ["Alt+N"], "label": "New drawing"},
    {"job": "copy_drawing", "keys": ["Alt+Shift+N"], "label": "Copy of this drawing"},
    {"job": "onion", "keys": ["Alt+O"], "label": "Onion skin"},
    {"job": "hold_longer", "keys": ["="], "label": "Hold this drawing longer"},
    {"job": "hold_shorter", "keys": ["-"], "label": "Hold this drawing shorter"},
    {"job": "rect_tool", "keys": ["R"], "label": "Rectangle"},
    {"job": "ellipse_tool", "keys": ["O"], "label": "Ellipse"},
    {"job": "text_tool", "keys": ["T"], "label": "Text"},
    {"job": "camera_tool", "keys": ["C"], "label": "Camera"},
    {"job": "auto_layout", "keys": ["Shift+A"], "label": "Auto layout"},
    {"job": "align_left", "keys": ["Alt+A"], "label": "Align left"},
    {"job": "align_right", "keys": ["Alt+D"], "label": "Align right"},
    {"job": "align_top", "keys": ["Alt+W"], "label": "Align top"},
    {"job": "align_bottom", "keys": ["Alt+S"], "label": "Align bottom"},
    {"job": "centre_across", "keys": ["Alt+H"], "label": "Centre across"},
    {"job": "centre_down", "keys": ["Alt+V"], "label": "Centre up and down"},
    {"job": "mask", "keys": ["Ctrl+Alt+M"], "label": "Mask"},
    {"job": "union", "keys": ["Ctrl+Alt+U"], "label": "Combine: union"},
    {"job": "subtract", "keys": ["Ctrl+Alt+S"], "label": "Combine: subtract"},
    {"job": "intersect", "keys": ["Ctrl+Alt+I"], "label": "Combine: intersect"},
    {"job": "exclude", "keys": ["Ctrl+Alt+X"], "label": "Combine: exclude"},
]

KEYS2D = KeyMap("Rostrum2D", OWN)
