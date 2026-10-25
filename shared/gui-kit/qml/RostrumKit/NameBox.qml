import QtQuick
import "."

// The one in-place name box (a track, a marker, a section renamed where it is). Open it by showing it: it takes the
// text from `current`, focuses and selects it. Enter -> done(text); Esc -> cancelled(); a click away -> cancelled(),
// or done(text) with `keepOnAway`. When it closes, the keys go back to the work (Ctrl+Z, Delete, Space ... answer at
// once): a hidden box must never keep the keyboard.
TextInput {
    id: box
    property string current: ""
    property bool keepOnAway: false
    signal done(string text)
    signal cancelled()
    selectByMouse: true; clip: true
    font.family: uiFont; font.pixelSize: Theme.body; color: Theme.fg; selectionColor: Theme.accent
    onVisibleChanged: {
        if (visible) { text = current; forceActiveFocus(); selectAll(); return }
        const w = Window.window
        if (w && (box.activeFocus || w.activeFocusItem === box || !w.activeFocusItem)) { box.focus = false; w.contentItem.forceActiveFocus() }
    }
    onAccepted: done(text)
    Keys.onEscapePressed: cancelled()
    onActiveFocusChanged: if (!activeFocus && visible) { if (keepOnAway) done(text); else cancelled() }
}
