import QtQuick
import RostrumKit

// The Editor's part of the dock's one header line (right of the Editor | Mixer tabs): the track's colour and name,
// then at the right Before / after (a cleaned take), the two tools (Select V, Draw B; INTERACTION 1.1) and Note ▾,
// the length a drawn or double-clicked note gets (backend.noteLength). Each shows only
// where it does something: the tools on notes and drums, Note ▾ on notes.
Item {
    id: h
    readonly property var roll: backend.roll
    readonly property string kind: roll.kind
    function toolHint(tool) {   // what the Select / Draw tool does here, said on hover (not as a line on the screen)
        var free = "Ctrl drags freely"
        return kind === "notes" ? "  ·  " + (tool === "draw" ? "Click to add a note" : "Double-click to add a note") + "  ·  " + free
             : kind === "drums" || kind === "audio" ? "  ·  " + free : ""
    }
    Row {   // the track: its colour, its name
        visible: h.roll.name !== ""
        anchors { left: parent.left; verticalCenter: parent.verticalCenter }
        width: Math.max(0, tools.x - Theme.gap); spacing: Theme.grid; clip: true
        Rectangle { width: 3; height: 16; radius: 1.5; color: h.roll.hue; anchors.verticalCenter: parent.verticalCenter }
        Text { text: h.roll.name; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold
               elide: Text.ElideRight; width: Math.min(implicitWidth, parent.width - 3 - Theme.grid) }
    }
    Row {
        id: tools
        anchors { right: parent.right; verticalCenter: parent.verticalCenter }
        spacing: 2
        BeforeAfter { anchors.verticalCenter: parent.verticalCenter; rightPadding: Theme.gap }
        Repeater {
            model: h.kind === "notes" || h.kind === "drums" ? [{ v: "select", label: "Select", key: "V" }, { v: "draw", label: "Draw", key: "B" }] : []
            delegate: Rectangle {
                required property var modelData
                readonly property bool on: backend.tool === modelData.v
                anchors.verticalCenter: parent.verticalCenter
                width: t.implicitWidth + 2 * Theme.gap; height: 24; radius: 4
                color: on ? Theme.accentSoft : ta.containsMouse ? Theme.hover : Theme.raised
                border.color: on ? Theme.accent : Theme.popupEdge
                Text { id: t; anchors.centerIn: parent; text: parent.modelData.label; color: parent.on ? Theme.fg : Theme.fg2
                       font.family: uiFont; font.pixelSize: Theme.label }
                MouseArea { id: ta; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: backend.setTool(parent.modelData.v) }
                HoverTip { text: parent.modelData.label + "  " + parent.modelData.key + h.toolHint(parent.modelData.v); hovered: ta.containsMouse; pressed: ta.pressed }
            }
        }
        Item { width: Theme.gap; height: 1; visible: note.visible }
        Rectangle {   // Note ▾
            id: note
            visible: h.kind === "notes"
            anchors.verticalCenter: parent.verticalCenter
            width: nt.implicitWidth + 2 * Theme.gap; height: 24; radius: 4
            color: na.containsMouse ? Theme.hover : Theme.raised; border.color: Theme.popupEdge
            Text { id: nt; anchors.centerIn: parent; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
                   text: "Note " + (backend.noteLength === "grid" ? "= grid" : backend.noteLength === "beat" ? "1/4" : backend.noteLength === "bar" ? "1 bar" : backend.noteLength) + "  ▾" }
            MouseArea { id: na; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: { var q = note.mapToItem(null, 0, note.height + 2); lenMenu.openAt(q.x, q.y) } }
            HoverTip { text: "How long a note is when you draw it (Draw, or a double-click)"; hovered: na.containsMouse; pressed: na.pressed }
            ActionMenu { id: lenMenu; entries: backend.noteLengthChoices; onPicked: (v) => backend.setNoteLength(v) }
        }
    }
}
