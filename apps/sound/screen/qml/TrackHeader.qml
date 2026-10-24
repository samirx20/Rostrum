import QtQuick
import RostrumKit

// A track's header in the arrangement, laid out like a desk channel's head (Logic, Ableton, Bitwig):
// line 1 its colour, a small picture of what it holds (TrackIcon), its name (click selects the track; Ctrl / Shift
// add; right-click its actions; double-click the name or F2 renames it in place, double-click elsewhere opens the
// Editor) and a small padlock when the track is locked; line 2 its buttons in fixed places whatever the selection
// (TrackButtons: R M S A); line 3 a thin level bar, live while the song plays (TrackMeter). A short row folds to one
// line: the name and the buttons, the bar left out. Selection only tints the row; nothing moves.
Rectangle {
    id: h
    property var track
    property bool showAuto: true            // off while the arrangement is slim (its lanes cannot open there)
    readonly property bool on: !!backend.picked[track.id]
    signal menuWanted(real x, real y)       // right-click: the host opens the track's actions (backend.itemMenu)
    signal dragMoved(real x, real y)        // the header is being dragged (pointer in this header's coordinates): into / out of a group
    signal dragEnded(real x, real y, bool dropped)
    property bool dragging: false           // set by the host while its drop marks show; the header dims
    readonly property bool tall: height >= 45                 // room for the buttons on a line of their own
    readonly property bool metered: height >= 51              // and for the level bar under them
    // too narrow for the buttons beside a name of 80 px on one line: the picture goes, the name keeps its room
    readonly property bool cramped: width - Theme.gap - 11 - Theme.grid < buttons.fullWidth + (tall ? 0 : 100)
    readonly property real lineTop: tall ? Math.round((height - (metered ? 47 : 39)) / 2) : 0
    radius: Theme.radiusCtl
    color: on ? Theme.accentSoft : area.containsMouse ? Theme.raised : "transparent"
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    opacity: dragging ? 0.55 : 1

    Repeater {   // an agent just changed this track: the 1-second outline
        model: backend.agent.flash.indexOf(h.track.id) >= 0 ? 1 : 0
        ChangeOutline { anchors.fill: parent }
    }
    MouseArea {   // click selects the track alone, Ctrl+click adds / removes, Shift+click the tracks between
        id: area; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
        property real x0: 0
        property real y0: 0
        property bool moved: false
        onPressed: (m) => { x0 = m.x; y0 = m.y; moved = false }
        onPositionChanged: (m) => {
            if (!pressed || !(pressedButtons & Qt.LeftButton)) return
            if (!moved && Math.abs(m.y - y0) + Math.abs(m.x - x0) < 8) return       // a click is not a drag
            moved = true; h.dragMoved(m.x, m.y)
        }
        onReleased: (m) => { if (moved) h.dragEnded(m.x, m.y, true) }
        onCanceled: { if (moved) h.dragEnded(0, 0, false); moved = false }
        onClicked: (m) => {
            if (moved) { moved = false; return }
            backend.focusArea("arrange")
            if (m.button === Qt.RightButton) h.menuWanted(m.x, m.y)
            else backend.clickSelect(h.track.id, (m.modifiers & Qt.ControlModifier) !== 0, (m.modifiers & Qt.ShiftModifier) !== 0)
        }
        onDoubleClicked: (m) => {
            var nx = nameText.mapToItem(h, 0, 0).x
            if (m.x >= nx && m.x <= nx + nameText.width && m.y >= line1.y && m.y <= line1.y + line1.height) backend.startRename(h.track.id)
            else { backend.select(h.track.id); workspace.setDock("editor") }
        }
    }
    Rectangle { x: Theme.gap; anchors.verticalCenter: parent.verticalCenter; width: 3; radius: 1.5
                height: h.tall ? parent.height - 10 : Math.min(parent.height - 8, 18); color: h.track.hue }
    Item {   // line 1: picture, name, volume (one line high; centred in a short row)
        id: line1
        x: Theme.gap + 11; y: h.tall ? h.lineTop : (h.height - height) / 2
        width: (h.tall ? h.width - Theme.grid : buttons.x - Theme.gap) - x; height: 16
        TrackIcon { id: icon; anchors.verticalCenter: parent.verticalCenter; icon: h.track.icon || "empty"
                    visible: !(h.cramped && !h.tall)   // a short, narrow row: the name keeps the room, R M S stay
                    ink: h.track.mute ? Theme.fg4 : Theme.fg2 }
        NameLabel {
            id: nameText
            x: icon.visible ? icon.width + 6 : 0; width: (padlock.visible ? padlock.x - Theme.gap : parent.width) - x
            anchors.verticalCenter: parent.verticalCenter
            text: h.track.name
            color: h.track.mute ? Theme.fg3 : Theme.fg
            visible: !rename.visible
        }
        Item {   // a locked track shows a small padlock (lock / unlock: right-click menu, Ctrl+Shift+L)
            id: padlock
            visible: !!h.track.locked
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            width: 10; height: 12
            Rectangle { x: 2; y: 0; width: 6; height: 7; radius: 3; color: "transparent"; border.width: 1.2; border.color: Theme.warn }
            Rectangle { x: 0; y: 5; width: 10; height: 7; radius: 1.5; color: Theme.warn }
        }
        TextInput {   // F2 / double-click the name: rename in place (Enter keeps it, Esc or clicking away cancels)
            id: rename
            visible: backend.renaming === h.track.id
            x: nameText.x - 3; width: nameText.width + 3; anchors.verticalCenter: parent.verticalCenter
            font.family: uiFont; font.pixelSize: Theme.body; color: Theme.fg; selectByMouse: true; clip: true
            selectionColor: Theme.accent
            onVisibleChanged: if (visible) { text = h.track.name; forceActiveFocus(); selectAll() }
            onAccepted: backend.finishRename(h.track.id, text)
            Keys.onEscapePressed: backend.finishRename(h.track.id, "")
            onActiveFocusChanged: if (!activeFocus && visible) backend.finishRename(h.track.id, "")
            Rectangle { z: -1; anchors.fill: parent; anchors.margins: -2; radius: 3; color: Theme.sunken; border.color: Theme.accent }
        }
    }
    TrackButtons {   // line 2 (a short row: at the right of line 1)
        id: buttons
        x: h.tall ? line1.x : h.width - buttons.fullWidth - Theme.grid
        y: h.tall ? line1.y + line1.height + 3 : (h.height - height) / 2
        track: h.track; showAuto: h.showAuto
    }
    TrackMeter { visible: h.metered; x: line1.x; y: buttons.y + buttons.height + 5; width: h.width - Theme.grid - x
                 trackId: h.track.id }
}
