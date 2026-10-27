import QtQuick
import "."

// A small square button with a glyph (a short text such as "+", "×", "⋯"), a drawn `mark` ("loop": a font's ↻ draws
// thin and faint) or a kit `icon` (a ToolIcon name, 18 px), all in the one icon colour.
// Same hover and press as Button; `kind`: "normal" (raised) or "ghost" (no box until hovered); `danger` colours the
// glyph red. Click, Space or Enter: one clicked().
Item {
    id: b
    property string glyph: ""
    property string mark: ""             // a drawn mark instead of the glyph: "loop"
    property string icon: ""             // a ToolIcon instead of the glyph ("align-left")
    property string kind: "normal"
    property bool danger: false
    property bool down: false            // shown pressed (e.g. a toggled-on tool)
    property string tip: ""              // its name, in words: shown under it while the pointer rests on it
    property string help: ""             // hover help: one plain sentence of what it does (INTERACTION.md 1.17)
    property string job: ""              // its key map job: the key shown in the hover help (AppShell.keyFor)
    property bool working: false         // what its click started is still running (ack.py): it stays pressed
    readonly property bool hovered: hoverHandler.hovered
    signal clicked()
    implicitWidth: Theme.button; implicitHeight: Theme.button
    activeFocusOnTab: true
    Keys.onSpacePressed: { if (typeof ack !== "undefined" && ack) ack.by(b); clicked() }
    Keys.onReturnPressed: { if (typeof ack !== "undefined" && ack) ack.by(b); clicked() }

    HoverHandler { id: hoverHandler; cursorShape: Qt.PointingHandCursor }
    Rectangle {          // at rest and hovered: the hover fades in
        anchors.fill: parent; radius: Theme.radiusCtl
        color: b.hovered ? Theme.hover : b.kind === "ghost" ? "transparent" : Theme.raised
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
    Rectangle {          // pressed, on or working: in the frame of the press, never faded (INTERACTION principle 1)
        objectName: "pressLook"
        anchors.fill: parent; radius: Theme.radiusCtl
        visible: area.pressed || b.down || b.working; color: Theme.active
    }
    Rectangle { anchors.fill: parent; radius: Theme.radiusCtl; color: "transparent"; visible: b.activeFocus
                border.width: 1; border.color: Theme.accent }
    readonly property color ink: b.danger ? Theme.danger : b.hovered || b.down ? Theme.fg : Theme.fg2
    Text {
        anchors.centerIn: parent
        visible: b.mark === "" && b.icon === ""
        text: b.glyph; font.pixelSize: Theme.heading; font.family: uiFont
        color: b.ink
    }
    Canvas {   // "loop": an open circle with its arrowhead, 12 x 12
        anchors.centerIn: parent
        visible: b.mark === "loop"
        width: 12; height: 12
        property color ink: b.ink
        onInkChanged: requestPaint()
        onPaint: {
            var g = getContext("2d")
            g.reset()
            g.strokeStyle = ink; g.fillStyle = ink; g.lineWidth = 1.5; g.lineCap = "round"
            g.beginPath(); g.arc(6, 6, 4.5, -0.35 * Math.PI, 1.45 * Math.PI); g.stroke()
            g.beginPath(); g.moveTo(10.6, 0.6); g.lineTo(10.8, 4.6); g.lineTo(6.9, 3.6); g.closePath(); g.fill()
        }
    }
    ToolIcon { anchors.centerIn: parent; visible: b.icon !== ""; name: b.icon; ink: b.ink; width: 18; height: 18 }
    MouseArea { id: area; anchors.fill: parent; onClicked: { if (typeof ack !== "undefined" && ack) ack.by(b); b.clicked() } }
    HoverTip { text: b.tip; help: b.help; key: b.job && b.Window.window && b.Window.window.keyFor ? b.Window.window.keyFor(b.job) : ""
               hovered: b.hovered; pressed: area.pressed || b.down }
}
