import QtQuick
import RostrumKit

// A group's header in the arrangement (DESIGN.md §3.1d): a bus that tracks play into, drawn as a row above them with
// a fold arrow (click folds the tracks behind this one row, Alt+click folds or unfolds every group), its name (click
// selects the group: Ctrl+Shift+G ungroups it) and, folded, how many tracks it holds. Folding is the person's own
// screen state, not the song. A M S at the right: its automation lane, mute the group, solo its tracks. Its fader and effects are in the
// Mixer; a group inside a group is indented. Dropping a track header on it (Timeline) puts the track into the group.
Rectangle {
    id: h
    property var track
    property bool showAuto: true
    readonly property bool on: !!backend.picked[track.id]
    readonly property real indent: (track.depth || 0) * 14
    radius: Theme.radiusCtl
    color: on ? Theme.accentSoft : area.containsMouse ? Theme.raised : "transparent"
    Behavior on color { ColorAnimation { duration: Theme.fast } }

    MouseArea {
        id: area; anchors.fill: parent; hoverEnabled: true
        onClicked: (m) => { backend.focusArea("arrange")
                            backend.clickSelect(h.track.id, (m.modifiers & Qt.ControlModifier) !== 0, (m.modifiers & Qt.ShiftModifier) !== 0) }
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
        x: arrow.x + arrow.width + 2; width: (count.visible ? count.x : autoChip.visible ? autoChip.x : toggles.x) - x - Theme.gap; anchors.verticalCenter: parent.verticalCenter
        text: h.track.name; font.pixelSize: Theme.label; font.weight: Font.DemiBold
        color: h.track.mute ? Theme.fg3 : Theme.fg
    }
    Text {
        id: count
        visible: !!h.track.folded && h.width >= 200      // narrow: the name gets the room
        anchors { right: autoChip.visible ? autoChip.left : toggles.left; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
        text: h.track.count + (h.track.count === 1 ? " track" : " tracks")
        font.family: uiFont; font.pixelSize: Theme.label - 1; color: Theme.fg3
    }
    GroupToggles { id: toggles; track: h.track
                   anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter } }
    LaneToggle { id: autoChip; visible: h.showAuto; track: h.track
                 anchors { right: toggles.left; rightMargin: 2; verticalCenter: parent.verticalCenter } }
}
