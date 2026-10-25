import QtQuick
import RostrumKit

// The Editor's part of the dock's one header line (right of the Editor | Mixer tabs): the track's colour and name,
// then at the right Before / after (a cleaned take), the two tools (Select V, Draw B; INTERACTION 1.1) and Note ▾,
// the length a drawn or double-clicked note gets (backend.noteLength), and on drums + Drum ▾ (a row for another drum of the
// kit, drum_rows.py). Each shows only where it does something: the tools on notes and drums, Note ▾ on notes, + Drum ▾
// on drums while the kit has a drum the rows don't show.
Item {
    id: h
    readonly property var roll: backend.roll
    readonly property string kind: roll.kind
    function openNote() { note.openMenu() }       // (the scripted `note-open` step)
    function openInKey() { inKey.openMenu() }     // (the scripted `inkey-open` step)
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
        Item { width: Theme.gap; height: 1; visible: note.visible || drumAdd.visible }
        Rectangle {   // In key ▾: only on a notes track in a song with a key (backend.inKeyChip is empty otherwise); screen state, never saved
            id: inKey
            objectName: "inKeyChip"
            readonly property var chip: backend.inKeyChip
            readonly property bool keep: !!chip.entries && chip.entries[0].checked
            visible: h.kind === "notes" && !!chip.label
            anchors.verticalCenter: parent.verticalCenter
            width: kt.implicitWidth + 2 * Theme.gap; height: 24; radius: 4
            color: keep ? Theme.accentSoft : ka.containsMouse ? Theme.hover : Theme.raised; border.color: keep ? Theme.accent : Theme.popupEdge
            Text { id: kt; anchors.centerIn: parent; color: parent.keep ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
                   text: (parent.chip.label || "") + "  ▾" }
            MouseArea { id: ka; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: inKey.openMenu() }
            HoverTip { text: "Notes drawn and moved stay in the song's key, and which rows show"; hovered: ka.containsMouse; pressed: ka.pressed }
            function openMenu() { var q = inKey.mapToItem(null, 0, inKey.height + 2); keyMenu.openAt(q.x, q.y) }
            ActionMenu { id: keyMenu; objectName: "inKeyMenu"; entries: inKey.chip.entries || []; onPicked: (v) => backend.toggleKeyLock(v) }
        }
        Rectangle {   // + Drum ▾: a row for another drum of the kit (backend.drumRowChoices; absent when every drum shows)
            id: drumAdd
            objectName: "addDrumRow"
            visible: h.kind === "drums" && backend.drumRowChoices.length > 0
            anchors.verticalCenter: parent.verticalCenter
            width: dt.implicitWidth + 2 * Theme.gap; height: 24; radius: 4
            color: da.containsMouse ? Theme.hover : Theme.raised; border.color: Theme.popupEdge
            Text { id: dt; anchors.centerIn: parent; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label; text: "+ Drum  ▾" }
            MouseArea { id: da; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: { var q = drumAdd.mapToItem(null, 0, drumAdd.height + 2); drumMenu.openAt(q.x, q.y) } }
            HoverTip { text: "Add a row for another drum of this kit"; hovered: da.containsMouse; pressed: da.pressed }
            ActionMenu { id: drumMenu; objectName: "addDrumRowMenu"; entries: backend.drumRowChoices; onPicked: (v) => backend.addDrumRow(v) }
        }
        Rectangle {   // Note ▾
            id: note
            objectName: "noteMenu"
            visible: h.kind === "notes"
            anchors.verticalCenter: parent.verticalCenter
            width: nt.implicitWidth + 2 * Theme.gap; height: 24; radius: 4
            color: na.containsMouse ? Theme.hover : Theme.raised; border.color: Theme.popupEdge
            Text { id: nt; anchors.centerIn: parent; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
                   text: backend.noteLabel + "  ▾" }
            MouseArea { id: na; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: note.openMenu() }
            function openMenu() { var q = note.mapToItem(null, 0, note.height + 2); lenMenu.openAt(q.x, q.y) }
            HoverTip { text: "How long a note is when you draw it, and whether it is a single note or a chord"; hovered: na.containsMouse; pressed: na.pressed }
            ActionMenu { id: lenMenu; objectName: "noteMenuList"; entries: backend.noteLengthChoices
                         onPicked: (v) => v.indexOf("draw:") === 0 ? backend.setDrawChord(v.slice(5)) : backend.setNoteLength(v) }
        }
    }
}
