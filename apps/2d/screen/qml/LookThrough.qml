import QtQuick
import RostrumKit

// Look through the frame (camera spec 3.5, 4.7, 4.8): Shift+C, the view menu's check-marked item, or this label's ×.
// Screen state only: never the document, never an undo step. On: the view is saved and fitted to the frame's box (the
// fit of Ctrl+0, so it is the size and place of the playing picture: play and stop never jump), and fitted again
// whenever the box changes (scrubbing looks through, a frame move). Inside the outline the world picture already is
// the export (the engine fills the frame's quad with the export path), so picking, dragging, typing and painting work
// unchanged; WorldFrame.qml covers the outside in the well colour and drops the outline and tab, FrameHandles.qml and
// FrameChip.qml step aside. Off: the saved view comes back exactly. Playing shows the export fitted in the well either way.
// The item itself is the label at the canvas's bottom-left, shown only while on.
Rectangle {
    id: lt
    required property var view
    property bool on: false
    property var saved: null            // the world view to come back to: asked, cx, cy, fitted

    function fit() { view.fitAll(backend.frameView.fitRect()) }
    function set(v) {
        if (v === on) return
        if (v) {
            saved = { asked: view.asked, cx: view.cx, cy: view.cy, fitted: view.fitted }
            on = true
            fit()
        } else {
            on = false
            view.asked = saved.asked; view.cx = saved.cx; view.cy = saved.cy; view.fitted = saved.fitted
            saved = null
        }
    }
    function toggle() { set(!on) }
    // frameView sends news only when the box really differs (news.relay), so a pan or zoom of your own stays until the
    // frame itself moves
    readonly property var box: backend.frameView.box
    onBoxChanged: if (on) fit()

    visible: on
    anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.margins: Theme.gap
    width: words.width + close.width + Theme.gap + 2; height: Math.max(words.height + 4, close.height)
    radius: Theme.radiusCtl; color: Theme.raised
    Text { id: words; x: Theme.gap; anchors.verticalCenter: parent.verticalCenter; text: "Through the frame"
           color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
    IconButton { id: close; objectName: "lookThroughOff"; kind: "ghost"; glyph: "×"; width: 18; height: 18
                 anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; onClicked: lt.set(false) }
}
