import QtQuick
import "."

// A button: "normal" (raised), "primary" (accent) or "ghost" (no box until hovered). `down` shows it pressed, a primary
// too (the top bar's Export while its sheet is open: one primary on screen). Wider than its words: they sit centred.
// Optional key hint at the right ("Ctrl K"). `danger` colours the text red (delete, discard). Click, Space or Enter: one clicked().
// Hover help (INTERACTION.md 1.17): with a `help` sentence or a key map `job`, resting on it shows its name (`tip`, else
// its text), the sentence and the key.
Item {
    id: b
    property string text: ""
    property string kind: "normal"
    property string hint: ""
    property bool danger: false
    property bool down: false            // shown pressed (e.g. a panel that is open)
    property bool chevron: false              // the thin dropdown arrow after the words (a button that opens a menu)
    property bool flushLeft: false            // the words at the left edge (in a column of list-like rows), not centred
    property string tip: ""              // the name in the hover help when the text alone doesn't say it
    property string help: ""             // one plain sentence of what it does
    property string job: ""              // its key map job: the key in the hover help (AppShell.keyFor)
    property bool working: false         // what its click started is still running (ack.py): it stays pressed
    readonly property string keyName: job && Window.window && Window.window.keyFor ? Window.window.keyFor(job) : ""
    readonly property bool hovered: hoverHandler.hovered
    readonly property bool primary: kind === "primary" && !down
    signal clicked()
    implicitHeight: Theme.button
    implicitWidth: label.implicitWidth + (chevron ? 16 : 0) + (hint ? hintBox.width + Theme.gap : 0) + 2 * Theme.pad
    activeFocusOnTab: true
    Keys.onSpacePressed: { if (typeof ack !== "undefined" && ack) ack.by(b); clicked() }
    Keys.onReturnPressed: { if (typeof ack !== "undefined" && ack) ack.by(b); clicked() }

    HoverHandler { id: hoverHandler; cursorShape: Qt.PointingHandCursor }
    Rectangle {          // at rest and hovered: the hover fades in
        anchors.fill: parent; radius: Theme.radiusCtl
        color: b.primary ? (b.hovered ? Theme.accentFillHover : Theme.accentFill)
             : b.hovered ? Theme.hover
             : b.kind === "ghost" ? "transparent" : Theme.raised
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
    Rectangle {          // pressed, open or working: drawn in the frame of the press, never faded (INTERACTION principle 1)
        objectName: "pressLook"
        anchors.fill: parent; radius: Theme.radiusCtl
        visible: area.pressed || b.down || b.working
        color: b.kind === "primary" && !b.down ? Qt.darker(Theme.accentFill, 1.18) : Theme.active
    }
    Rectangle { anchors.fill: parent; radius: Theme.radiusCtl; color: "transparent"; visible: b.activeFocus
                border.width: 1; border.color: b.primary ? "white" : Theme.accent }
    Text {
        id: label
        x: b.hint || b.flushLeft ? Theme.pad : Math.max(Theme.pad, (b.width - width - (b.chevron ? 16 : 0)) / 2)
        anchors.verticalCenter: parent.verticalCenter
        text: b.text; font.pixelSize: Theme.body; font.family: uiFont
        width: Math.min(implicitWidth, Math.max(0, b.width - 2 * Theme.pad - (b.hint ? hintBox.width + Theme.gap : 0)))
        elide: Text.ElideRight           // a button narrower than its words (a grid cell): the name whole on hover
        font.weight: b.kind === "primary" ? Font.DemiBold : Font.Normal
        color: b.primary ? "white" : b.danger ? Theme.danger : Theme.fg
    }
    Chevron { visible: b.chevron; x: label.x + label.width + 6; anchors.verticalCenter: parent.verticalCenter
              color: b.primary ? "white" : Theme.fg2 }
    KeyHint { id: hintBox; visible: b.hint !== ""; text: b.hint
              anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter }
    MouseArea { id: area; anchors.fill: parent; onClicked: { if (typeof ack !== "undefined" && ack) ack.by(b); b.clicked() } }
    HoverTip { text: b.help || b.keyName && !b.hint || b.tip ? (b.tip || b.text) : ""; help: b.help
               key: b.hint ? "" : b.keyName; hovered: b.hovered; pressed: area.pressed || b.down }
}
