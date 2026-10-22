import QtQuick
import RostrumKit

// "Type what she says" in the voice track's lane, at the time you double-clicked (or the playhead for Add line at
// playhead): Enter makes the line (its speech is made when typing finishes), Esc or clicking away cancels
// (DESIGN.md §3.11 step 2). `tl` is the Timeline, `bars` its ruler; the open box is editorSide.typing.
Item {
    id: box
    property var tl
    property var bars
    readonly property var at: editorSide.typing
    readonly property var span: at.track ? tl.rowSpan(at.track) : null
    visible: !!span
    x: bars.x + Math.round(bars.xOf(at.t || 0)); y: span ? span.top + 3 : 0
    width: Math.max(160, Math.min(320, bars.x + bars.width - x)); height: span ? span.bottom - span.top - 6 : 0
    onVisibleChanged: if (visible) { input.text = ""; input.forceActiveFocus() }
    Rectangle { anchors.fill: parent; radius: 3; color: Theme.raised; border.color: Theme.accent }
    TextInput {
        id: input
        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: Theme.gap }
        font.family: uiFont; font.pixelSize: Theme.body; color: Theme.fg; selectByMouse: true; clip: true
        onAccepted: editorSide.typeAt(box.at.track, text, box.at.t)
        Keys.onEscapePressed: editorSide.cancelTyping()
        onActiveFocusChanged: if (!activeFocus && box.visible) editorSide.cancelTyping()
        Text { visible: input.text === ""; text: "Type what she says, then Enter"; color: Theme.fg4
               font.family: uiFont; font.pixelSize: Theme.body }
    }
}
