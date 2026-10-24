import QtQuick
import QtQuick.Controls as QQC
import "."

// Hover help (INTERACTION.md 1.17): after 500 ms over a control, one line under it: its name, one plain sentence of
// what it does (`help`, from the operation's or setting's own help) and its key (`key`, from the key map). Gone as
// soon as the pointer leaves or the control is pressed (the tip watches the press itself, on its parent, so a caller
// never has to pass `pressed`; the pointer stays on the control after the click, and the tip stays away until it
// has left and come back); in the window's overlay, so nothing clips it, and kept inside
// the window (a line too long ends in "…"). `text` empty: never shown.
QQC.Popup {
    id: tip
    property string text: ""             // the name ("Export")
    property string help: ""             // one sentence ("Make a file to share or hand on.")
    property string key: ""              // "Ctrl+E"
    property bool hovered: false
    property bool pressed: false
    readonly property var win: parent ? parent.Window.window : null
    readonly property int most: win ? Math.min(560, win.width - 16) : 560
    readonly property int oneLine: 420        // a tip longer than this wraps and stands beside its control
    readonly property int wrapW: 300
    readonly property bool wraps: whole.advanceWidth > oneLine
    TextMetrics { id: whole; font.family: uiFont; font.pixelSize: Theme.label; text: tip.help ? tip.text + "  " + tip.help : tip.text }
    readonly property int side: {      // -1 left of the control, 1 right of it, 0 under it
        if (!wraps || !parent || !win || !visible) return 0
        const at = parent.mapToItem(null, 0, 0).x
        return at - width - 8 >= 8 ? -1 : at + parent.width + 8 + width <= win.width - 8 ? 1 : 0
    }
    y: {
        if (!parent) return 0
        if (side === 0) return parent.height + 4
        const top = parent.mapToItem(null, 0, 0).y + (parent.height - height) / 2      // centred on the control, inside the window
        return Math.max(8, Math.min(win.height - 8 - height, top)) - parent.mapToItem(null, 0, 0).y
    }
    x: {
        if (!parent) return 0
        if (side !== 0) return side < 0 ? -width - 8 : parent.width + 8
        const want = (parent.width - width) / 2
        if (!win || !visible) return want
        const at = parent.mapToItem(null, want, 0).x                  // keep the whole line inside the window
        return want + Math.max(8 - at, Math.min(0, win.width - 8 - (at + width)))
    }
    padding: 0
    focus: false
    closePolicy: QQC.Popup.NoAutoClose
    background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
    contentItem: Row {
        spacing: Theme.grid
        leftPadding: Theme.grid + 2; rightPadding: Theme.grid + 2; topPadding: 3; bottomPadding: 3
        Text {
            anchors.verticalCenter: parent.verticalCenter
            width: tip.wraps ? tip.wrapW : Math.min(implicitWidth, tip.most - (keyHint.visible ? keyHint.width + Theme.grid : 0) - 2 * Theme.grid - 4)
            wrapMode: tip.wraps ? Text.WordWrap : Text.NoWrap
            elide: tip.wraps ? Text.ElideNone : Text.ElideRight; textFormat: Text.StyledText
            text: tip.help ? "<b>" + tip.esc(tip.text) + "</b>  " + tip.esc(tip.help) : tip.esc(tip.text)
            color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label
        }
        KeyHint { id: keyHint; visible: tip.key !== ""; text: tip.key.replace(/\+/g, " ")
                  anchors.verticalCenter: parent.verticalCenter }
    }
    function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;") }
    property var spot: null              // the layer over the parent, which knows where the pointer is on it
    property bool held: false            // the screen moved under a still pointer: no tip until the pointer moves
    property bool clicked: false         // this control was pressed: no tip until the pointer has left and come back
    function pressedNow(at) { TipGate.pressAt = at; clicked = true; rest.stop(); tip.close() }
    function waited() {
        if (text === "") return
        if (spot && TipGate.near(spot.point.scenePosition)) { held = true; return }   // the screen moved under a still pointer
        held = false; open()
    }
    // an invisible layer over the control, above whatever takes its clicks (a MouseArea inside it would eat the press
    // before a handler on the control itself heard it); its handlers only look: the click goes on underneath
    Component { id: layer
        Item {
            z: 10000; anchors.fill: parent
            property alias point: where.point
            PointHandler { acceptedButtons: Qt.AllButtons; onActiveChanged: if (active) tip.pressedNow(point.scenePosition) }
            HoverHandler { id: where; onPointChanged: if (tip.held && !tip.clicked && tip.hovered && !TipGate.near(point.scenePosition)) rest.restart() }
        } }
    Timer { id: rest; interval: 500; onTriggered: tip.waited() }
    onHoveredChanged: {
        if (hovered && !pressed && !clicked) rest.restart()
        else { rest.stop(); tip.close(); if (!hovered) { clicked = false; held = false } }
    }
    onPressedChanged: if (pressed) { rest.stop(); tip.close() }
    Component.onCompleted: {
        if (parent) spot = layer.createObject(parent)      // a press anywhere on the control ends the tip, whoever wired `pressed`
        if (hovered && !pressed) rest.restart()      // made already hovered (a tip loaded on hover)
    }
}
