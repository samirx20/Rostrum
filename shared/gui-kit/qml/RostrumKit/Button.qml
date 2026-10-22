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
    property string tip: ""              // the name in the hover help when the text alone doesn't say it
    property string help: ""             // one plain sentence of what it does
    property string job: ""              // its key map job: the key in the hover help (AppShell.keyFor)
    readonly property string keyName: job && Window.window && Window.window.keyFor ? Window.window.keyFor(job) : ""
    readonly property bool hovered: hoverHandler.hovered
    readonly property bool primary: kind === "primary" && !down
    signal clicked()
    implicitHeight: Theme.button
    implicitWidth: label.implicitWidth + (hint ? hintBox.width + Theme.gap : 0) + 2 * Theme.pad
    activeFocusOnTab: true
    Keys.onSpacePressed: clicked()
    Keys.onReturnPressed: clicked()

    HoverHandler { id: hoverHandler; cursorShape: Qt.PointingHandCursor }
    Rectangle {
        anchors.fill: parent; radius: Theme.radiusCtl
        color: b.primary ? (b.hovered || area.pressed ? Theme.accentHover : Theme.accent)
             : area.pressed || b.down ? Theme.active
             : b.hovered ? Theme.hover
             : b.kind === "ghost" ? "transparent" : Theme.raised
        border.width: b.activeFocus ? 1 : 0; border.color: b.primary ? "white" : Theme.accent
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
    Text {
        id: label
        x: b.hint ? Theme.pad : Math.max(Theme.pad, (b.width - width) / 2)
        anchors.verticalCenter: parent.verticalCenter
        text: b.text; font.pixelSize: Theme.body; font.family: uiFont
        font.weight: b.kind === "primary" ? Font.DemiBold : Font.Normal
        color: b.primary ? "white" : b.danger ? Theme.danger : Theme.fg
    }
    KeyHint { id: hintBox; visible: b.hint !== ""; text: b.hint
              anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter }
    MouseArea { id: area; anchors.fill: parent; onClicked: b.clicked() }
    HoverTip { text: b.help || b.keyName && !b.hint || b.tip ? (b.tip || b.text) : ""; help: b.help
               key: b.hint ? "" : b.keyName; hovered: b.hovered; pressed: area.pressed || b.down }
}
