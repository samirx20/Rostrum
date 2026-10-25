import QtQuick
import "."

// Hover help (INTERACTION.md 1.17): after 500 ms over a control, one line under it: its name, one plain sentence of
// what it does (`help`, from the operation's or setting's own help) and its key (`key`, from the key map). Gone as
// soon as the pointer leaves or the control is pressed (the tip watches the press itself, on its parent, so a caller
// never has to pass `pressed`; the pointer stays on the control after the click, and the tip stays away until it
// has left and come back); in the window's overlay, so nothing clips it, and kept inside
// the window (a line too long ends in "…"). `text` empty: never shown.
// Nearly every control carries one, so a tip costs nothing until it is needed: this is an invisible, sizeless item (a
// Row or Column leaves it out); the layer that watches the pointer is made at the first hover, the line itself
// (HoverTipLine.qml, a popup) at the first rest. A popup per control made every panel slower to build (a settings
// row's fields, the context bar's buttons): ~40 % of a new selection's rows.
Item {
    id: tip
    property string text: ""             // the name ("Export")
    property string help: ""             // one sentence ("Make a file to share or hand on.")
    property string key: ""              // "Ctrl+E"
    property bool hovered: false
    property bool pressed: false
    property real atX: NaN               // where the line stands on its control, when the caller places it (else under it)
    property real atY: NaN
    readonly property bool shown: line.item !== null && line.item.visible
    visible: false; width: 0; height: 0
    property var spot: null              // the layer over the parent, which hears a press on it
    property bool held: false            // the screen moved under a still pointer: no tip until the pointer moves
    property bool clicked: false         // this control was pressed: no tip until the pointer has left and come back
    function open() { line.active = true; if (line.item) line.item.open() }
    function close() { if (line.item) line.item.close() }
    function pressedNow(at) { TipGate.pressAt = at; clicked = true; rest.stop(); tip.close() }
    function waited() {
        if (text === "" || !parent || !parent.visible) return
        if (spot && TipGate.near(TipGate.at)) { held = true; return }   // the screen moved under a still pointer
        held = false; open()
    }
    Loader { id: line; active: false; sourceComponent: HoverTipLine { owner: tip; parent: tip.parent } }
    // an invisible layer over the control, above whatever takes its clicks (a MouseArea inside it would eat the press
    // before a handler on the control itself heard it); its handlers only look: the click goes on underneath
    Component { id: layer
        Item {
            z: 10000; anchors.fill: parent
            PointHandler { acceptedButtons: Qt.AllButtons; onActiveChanged: if (active) tip.pressedNow(point.scenePosition) }
        } }                  // no hover handler in here: an item that takes hover hides the control's own MouseArea from it (TipGate tracks the pointer)
    Connections { target: tip.spot ? TipGate : null
        function onAtChanged() { if (tip.held && !tip.clicked && tip.hovered && !TipGate.near(TipGate.at)) rest.restart() } }
    Timer { id: rest; interval: 500; onTriggered: tip.waited() }
    function watch() { if (!spot && parent) { TipGate.track(tip.Window.window); spot = layer.createObject(parent) } }   // a press anywhere on the control ends the tip, whoever wired `pressed`
    onHoveredChanged: {
        if (hovered) watch()
        if (hovered && !pressed && !clicked) rest.restart()
        else { rest.stop(); tip.close(); if (!hovered) { clicked = false; held = false } }
    }
    // a panel that closes or goes away under a tip takes the tip with it (the tip lives in the window's overlay)
    Connections {
        target: tip.spot ? tip.parent : null
        ignoreUnknownSignals: true
        function onVisibleChanged() { if (tip.parent && !tip.parent.visible) { rest.stop(); tip.close(); tip.clicked = false; tip.held = false } }
    }
    Component.onDestruction: tip.close()
    onPressedChanged: if (pressed) { rest.stop(); tip.close() }
    Component.onCompleted: if (hovered) { watch(); if (!pressed) rest.restart() }     // made already hovered (a tip loaded on hover)
}
