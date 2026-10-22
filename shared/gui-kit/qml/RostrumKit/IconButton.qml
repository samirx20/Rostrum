import QtQuick
import "."

// A small square button with a glyph (a short text such as "+", "×", "⋯") or a drawn `mark` ("loop": a font's ↻ draws
// thin and faint), both in the one icon colour.
// Same hover and press as Button; `kind`: "normal" (raised) or "ghost" (no box until hovered); `danger` colours the
// glyph red. Click, Space or Enter: one clicked().
Item {
    id: b
    property string glyph: ""
    property string mark: ""             // a drawn mark instead of the glyph: "loop"
    property string kind: "normal"
    property bool danger: false
    property bool down: false            // shown pressed (e.g. a toggled-on tool)
    property string tip: ""              // its name, in words: shown under it while the pointer rests on it
    property string help: ""             // hover help: one plain sentence of what it does (INTERACTION.md 1.17)
    property string job: ""              // its key map job: the key shown in the hover help (AppShell.keyFor)
    readonly property bool hovered: hoverHandler.hovered
    signal clicked()
    implicitWidth: Theme.button; implicitHeight: Theme.button
    activeFocusOnTab: true
    Keys.onSpacePressed: clicked()
    Keys.onReturnPressed: clicked()

    HoverHandler { id: hoverHandler; cursorShape: Qt.PointingHandCursor }
    Rectangle {
        anchors.fill: parent; radius: Theme.radiusCtl
        color: area.pressed || b.down ? Theme.active : b.hovered ? Theme.hover : b.kind === "ghost" ? "transparent" : Theme.raised
        border.width: b.activeFocus ? 1 : 0; border.color: Theme.accent
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
    readonly property color ink: b.danger ? Theme.danger : b.hovered || b.down ? Theme.fg : Theme.fg2
    Text {
        anchors.centerIn: parent
        visible: b.mark === ""
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
    MouseArea { id: area; anchors.fill: parent; onClicked: b.clicked() }
    HoverTip { text: b.tip; help: b.help; key: b.job && b.Window.window && b.Window.window.keyFor ? b.Window.window.keyFor(b.job) : ""
               hovered: b.hovered; pressed: area.pressed || b.down }
}
