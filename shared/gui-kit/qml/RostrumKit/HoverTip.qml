import QtQuick
import QtQuick.Controls as QQC
import "."

// The words under a control while the pointer rests on it (a glyph button says what it does). Shown after a short
// rest, gone as soon as the pointer leaves or the control is pressed; in the window's overlay, so nothing clips it.
// `text` empty: never shown.
QQC.Popup {
    id: tip
    property string text: ""
    property bool hovered: false
    property bool pressed: false
    y: parent ? parent.height + 4 : 0
    x: parent ? (parent.width - width) / 2 : 0
    padding: 0
    focus: false
    closePolicy: QQC.Popup.NoAutoClose
    background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
    contentItem: Text {
        text: tip.text; leftPadding: Theme.grid + 2; rightPadding: Theme.grid + 2; topPadding: 3; bottomPadding: 3
        color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label
    }
    Timer { id: rest; interval: 500; onTriggered: if (tip.text !== "") tip.open() }
    onHoveredChanged: hovered && !pressed ? rest.restart() : (rest.stop(), tip.close())
    onPressedChanged: if (pressed) { rest.stop(); tip.close() }
}
