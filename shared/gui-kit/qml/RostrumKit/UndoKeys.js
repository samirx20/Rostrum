// Ctrl+Z / redo in a text box with nothing typed in it (the box still holds its value, or the name it opened with):
// the box lets go and the window's undo runs. A focused text box takes the key before any shortcut, so without this a
// box that opened by itself (a new section's or marker's name) would swallow the person's Ctrl+Z. The one rule for
// every kit box (FieldFrame, NameBox, MarkerFlag): `typed` = the person typed something (then Ctrl+Z undoes the typing);
// `letGo()` closes or unfocuses the box first. True when the key was taken.
function passOn(e, typed, backend, letGo) {
    const mods = e.modifiers & (Qt.ControlModifier | Qt.ShiftModifier | Qt.AltModifier)    // (Ctrl is Cmd on a Mac)
    const undo = e.key === Qt.Key_Z && mods === Qt.ControlModifier
    const redo = (e.key === Qt.Key_Z && mods === (Qt.ControlModifier | Qt.ShiftModifier)) || (e.key === Qt.Key_Y && mods === Qt.ControlModifier)
    if ((!undo && !redo) || typed || !backend || !backend.undo) return false
    e.accepted = true
    letGo()
    if (undo) backend.undo(); else backend.redo()
    return true
}
