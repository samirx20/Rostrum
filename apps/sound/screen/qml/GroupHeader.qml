import QtQuick
import RostrumKit

// A group's header in the arrangement (DESIGN.md §3.1d): a bus that tracks play into, drawn as a row above them with
// a fold arrow (click folds the tracks behind this one row, Alt+click folds or unfolds every group), its name (click
// selects the group: Ctrl+Shift+G ungroups it; double-click the name or F2 renames it in place, right-click its actions)
// and, folded, how many tracks it holds. Folding is the person's own
// screen state, not the song. A M S at the right: its automation lane, mute the group, solo its tracks. Its fader and effects are in the
// Mixer; a group inside a group is indented. Dropping a track header on it (Timeline) puts the track into the group.
Rectangle {
    id: h
    property var track
    property bool showAuto: true
    signal menuWanted(real x, real y)       // right-click: the host opens the group's actions (backend.itemMenu)
    readonly property bool on: !!backend.picked[track.id]
    readonly property real indent: (track.depth || 0) * 14
    // The name comes first: the track count, then the automation button, give way when the name would be cut (an open
    // automation lane keeps its button, so it can be closed). The name's own hover tip shows it whole when still too long.
    readonly property real nameRoom: width - (arrow.x + arrow.width + 2) - toggles.width - Theme.grid * 3 - Theme.grid
    readonly property bool autoFits: nameRoom - autoChip.width - 2 >= nameText.implicitWidth
    readonly property bool countFits: nameRoom - (autoChip.visible ? autoChip.width + 2 : 0) - count.implicitWidth - Theme.grid >= nameText.implicitWidth
    radius: Theme.radiusCtl
    color: on ? Theme.accentSoft : area.containsMouse ? Theme.raised : "transparent"
    Behavior on color { ColorAnimation { duration: Theme.fast } }

    MouseArea {
        id: area; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: (m) => { backend.focusArea("arrange")
                            if (m.button === Qt.RightButton) h.menuWanted(m.x, m.y)
                            else backend.clickSelect(h.track.id, (m.modifiers & Qt.ControlModifier) !== 0, (m.modifiers & Qt.ShiftModifier) !== 0) }
        onDoubleClicked: (m) => { if (m.button === Qt.LeftButton && m.x >= nameText.x && m.x <= nameText.x + nameText.width) backend.startRename(h.track.id) }
    }
    Item {   // the fold arrow, drawn: points right when folded, down when open
        id: arrow
        x: h.indent + Theme.grid; anchors.verticalCenter: parent.verticalCenter; width: 18; height: 18
        Canvas {
            anchors.centerIn: parent; width: 10; height: 10
            property color ink: arrowArea.containsMouse ? Theme.fg : Theme.fg2
            property bool folded: !!h.track.folded
            onInkChanged: requestPaint()
            onFoldedChanged: requestPaint()
            onPaint: { var c = getContext("2d"); c.reset(); c.fillStyle = ink; c.beginPath()
                       if (folded) { c.moveTo(2, 0); c.lineTo(9, 5); c.lineTo(2, 10) } else { c.moveTo(0, 2); c.lineTo(10, 2); c.lineTo(5, 9) }
                       c.closePath(); c.fill() }
        }
        MouseArea { id: arrowArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: (m) => backend.toggleFold(h.track.id, (m.modifiers & Qt.AltModifier) !== 0) }
        HoverTip { text: (h.track.folded ? "Show the tracks" : "Fold the tracks away") + ". Alt+click: all groups"
                   hovered: arrowArea.containsMouse; pressed: arrowArea.pressed }
    }
    NameLabel {
        id: nameText
        x: arrow.x + arrow.width + 2; width: (count.visible ? count.x : autoChip.visible ? autoChip.x : toggles.x) - x - Theme.grid; anchors.verticalCenter: parent.verticalCenter
        text: h.track.name; elide: Text.ElideMiddle; font.pixelSize: Theme.label; font.weight: Font.DemiBold
        color: h.track.mute ? Theme.fg3 : Theme.fg
        visible: !rename.visible
    }
    NameBox {   // F2 / double-click the name: rename in place, the same box a track's name uses
        id: rename
        objectName: "groupNameBox"
        visible: backend.renaming === h.track.id
        current: h.track.name
        x: nameText.x - 3; width: nameText.width + 3; anchors.verticalCenter: parent.verticalCenter
        font.pixelSize: Theme.label
        onDone: (t) => backend.finishRename(h.track.id, t)
        onCancelled: backend.finishRename(h.track.id, "")
        Rectangle { z: -1; anchors.fill: parent; anchors.margins: -2; radius: 3; color: Theme.sunken; border.color: Theme.accent }
    }
    Text {
        id: count
        visible: !!h.track.folded && h.countFits
        anchors { right: autoChip.visible ? autoChip.left : toggles.left; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
        text: h.track.count + (h.track.count === 1 ? " track" : " tracks")
        font.family: uiFont; font.pixelSize: Theme.label - 1; color: Theme.fg3
    }
    GroupToggles { id: toggles; track: h.track
                   anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter } }
    LaneToggle { id: autoChip; visible: h.showAuto && (h.autoFits || !!h.track.auto); track: h.track
                 anchors { right: toggles.left; rightMargin: 2; verticalCenter: parent.verticalCenter } }
}
