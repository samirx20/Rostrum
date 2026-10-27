import QtQuick
import "."

// The value chip while dragging (INTERACTION.md 1.10, 1.22 canvas rule 8): the value, never a name for it ("X 120  Y 48",
// "120 × 48", "15°", "+6 f · drop", "1.20 s → 3.40 s", "−4.0 dB"), and under it what a held key does now (`hint`:
// "15° steps", "keep ratio · from centre"). It sits 16 px below-right of `at` (the pointer, in the parent's px), flips
// to the left / above near the parent's edge, and never covers `avoid` (the dragged thing's box, when given: it goes to
// the other side). `beside`: just right of `at`, centred on it (a timeline's dragged edge or key on its row). Tabular
// figures, so the chip doesn't wobble as digits change. It stays 600 ms after the drag ends (text ""), then goes.
// Bind it to a DragView (rostrum_gui/drag.py): text = view.text, hint = view.hint, at = Qt.point(view.x, view.y).
Rectangle {
    id: lbl
    property string text: ""
    property string hint: ""
    property point at: Qt.point(0, 0)
    property rect avoid: Qt.rect(0, 0, 0, 0)
    property bool beside: false
    readonly property int off: 16
    property string shownText: ""             // the words on screen: the last ones for 600 ms after the drag ends
    property string shownHint: ""
    property point pin: Qt.point(0, 0)        // where it is shown: held still while it lingers after the drag
    onAtChanged: if (text !== "") pin = at
    objectName: "dragChip"
    onTextChanged: if (text !== "") { shownText = text; shownHint = hint; pin = at; linger.stop() } else linger.restart()
    onHintChanged: if (text !== "") shownHint = hint
    Timer { id: linger; interval: 600; onTriggered: { lbl.shownText = ""; lbl.shownHint = "" } }
    visible: shownText !== ""
    enabled: false                            // only a sign: never takes the pointer the drag is using
    z: 1000

    function clampX(v) { return Math.max(0, Math.min(v, parent.width - width - 4)) }
    function clampY(v) { return Math.max(0, Math.min(v, parent.height - height - 4)) }
    function hits(px, py) {
        return avoid.width > 0 && px < avoid.x + avoid.width && px + width > avoid.x
            && py < avoid.y + avoid.height && py + height > avoid.y
    }
    readonly property bool flipX: pin.x + off + width > parent.width - 4
    readonly property bool flipY: pin.y + off + height > parent.height - 4
    readonly property real rightX: flipX ? pin.x - off - width : pin.x + off
    readonly property real downY: flipY ? pin.y - off - height : pin.y + off
    x: beside ? clampX(pin.x + 12) : clampX(hits(rightX, downY) && !hits(pin.x - off - width, downY) ? pin.x - off - width : rightX)
    y: beside ? clampY(pin.y - height / 2) : clampY(hits(x, downY) && !hits(x, pin.y - off - height) ? pin.y - off - height : downY)
    width: Math.max(words.implicitWidth, held.visible ? held.implicitWidth : 0) + 2 * Theme.grid + 4
    height: words.implicitHeight + (held.visible ? held.implicitHeight : 0) + Theme.grid
    radius: Theme.radiusCtl
    color: Theme.raised; border.color: Theme.popupEdge
    Column {
        anchors.centerIn: parent
        Text {
            id: words
            anchors.horizontalCenter: parent.horizontalCenter
            text: lbl.shownText
            color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 }
        }
        Text {
            id: held
            visible: lbl.shownHint !== ""
            anchors.horizontalCenter: parent.horizontalCenter
            text: lbl.shownHint
            color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
        }
    }
}
