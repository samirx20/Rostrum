.pragma library
// The one way the canvas reads Ctrl / Shift / Alt: from the event itself (a MouseEvent, a WheelEvent, or a pointer
// handler's point / centroid), never from a global "is it held?" (Qt.application has none in this Qt: it reads as
// nothing, so a Ctrl+drag silently became a plain drag). tests/test_modifiers.py keeps the global read out.
function ctrl(e) { return !!e && (e.modifiers & Qt.ControlModifier) !== 0 }
function shift(e) { return !!e && (e.modifiers & Qt.ShiftModifier) !== 0 }
function alt(e) { return !!e && (e.modifiers & Qt.AltModifier) !== 0 }
