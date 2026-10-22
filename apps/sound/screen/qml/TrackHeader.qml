import QtQuick
import RostrumKit

// A track's header in the arrangement: its colour, its name (click selects the track; Ctrl / Shift add; right-click
// its actions; double-click the name or F2 renames it in place, double-click elsewhere opens the Editor), a lock
// (track.lock / track.unlock: nobody, agents included, can change a locked track; shown on hover or when locked), and the two quick
// toggles, mute and solo (each a track.set operation; lit when on), and the "Rec" arm button for recording
// (red when armed; arming is screen state, not an edit).
Rectangle {
    id: h
    property var track
    property bool showAuto: true            // off while the arrangement is slim (its lanes cannot open there)
    readonly property bool on: !!backend.picked[track.id]
    signal menuWanted(real x, real y)       // right-click: the host opens the track's actions (backend.itemMenu)
    radius: Theme.radiusCtl
    color: on ? Theme.accentSoft : area.containsMouse ? Theme.raised : "transparent"
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    HoverHandler { id: hover }

    Repeater {   // an agent just changed this track: the 1-second outline
        model: backend.agent.flash.indexOf(h.track.id) >= 0 ? 1 : 0
        ChangeOutline { anchors.fill: parent }
    }
    MouseArea {   // click selects the track alone, Ctrl+click adds / removes, Shift+click the tracks between
        id: area; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: (m) => {
            backend.focusArea("arrange")
            if (m.button === Qt.RightButton) h.menuWanted(m.x, m.y)
            else backend.clickSelect(h.track.id, (m.modifiers & Qt.ControlModifier) !== 0, (m.modifiers & Qt.ShiftModifier) !== 0)
        }
        onDoubleClicked: (m) => {
            if (m.x >= nameText.x && m.x <= nameText.x + nameText.implicitWidth) backend.startRename(h.track.id)
            else { backend.select(h.track.id); workspace.setDock("editor") }
        }
    }
    Rectangle { x: Theme.gap; anchors.verticalCenter: parent.verticalCenter; width: 3; radius: 1.5
                height: Math.min(parent.height - 8, 18); color: h.track.hue }
    Text {
        x: Theme.gap + 11; width: toggles.x - x - Theme.gap; anchors.verticalCenter: parent.verticalCenter
        id: nameText
        text: h.track.name; elide: Text.ElideRight; font.family: uiFont; font.pixelSize: Theme.body
        HoverTip { text: nameText.truncated ? h.track.name : ""; hovered: hover.hovered }     // a cut name, whole
        color: h.track.mute ? Theme.fg3 : Theme.fg
        visible: !rename.visible
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
    Row {
        id: toggles
        anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter
        spacing: 2
        Item {   // the lock: a drawn padlock, lit when locked
            id: lock
            visible: hover.hovered || !!h.track.locked
            width: 18; height: 18
            Rectangle { x: 5; y: 3; width: 8; height: 8; radius: 4; color: "transparent"; border.width: 1.5
                        border.color: h.track.locked ? Theme.warn : lockArea.containsMouse ? Theme.fg : Theme.fg3 }
            Rectangle { x: 3; y: 8; width: 12; height: 8; radius: 2
                        color: h.track.locked ? Theme.warn : lockArea.containsMouse ? Theme.fg : Theme.fg3 }
            MouseArea { id: lockArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: backend.toggleLock(h.track.id) }
            HoverTip { text: h.track.locked ? "Locked: nobody can change this track, agents included. Click to unlock (Ctrl+Shift+L)"
                                            : "Lock this track: nobody can change it, agents included (Ctrl+Shift+L)"
                       hovered: lockArea.containsMouse; pressed: lockArea.pressed }
        }
        LaneToggle { visible: h.showAuto && (hover.hovered || h.track.autoUsed || !!h.track.auto); track: h.track }   // on hover or in use
        Rectangle {   // "Rec": arm this track for recording (lit red when armed)
            id: arm
            readonly property bool lit: recorder.armed === h.track.id
            width: armRow.width + Theme.gap; height: 18; radius: 4
            color: lit ? Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.18) : armArea.containsMouse ? Theme.hover : "transparent"
            border.width: 1; border.color: lit ? Theme.danger : Theme.line
            Row {
                id: armRow
                anchors.centerIn: parent; spacing: 4
                Rectangle { anchors.verticalCenter: parent.verticalCenter; width: 7; height: 7; radius: 3.5
                            color: arm.lit ? Theme.danger : "transparent"
                            border.width: 1.5; border.color: arm.lit ? Theme.danger : Theme.fg3 }
                Text { visible: h.width >= 170; anchors.verticalCenter: parent.verticalCenter; text: "Rec"; font.family: uiFont   // narrow: the dot alone
                       font.pixelSize: Theme.label; font.weight: Font.DemiBold
                       color: arm.lit ? Theme.danger : armArea.containsMouse ? Theme.fg : Theme.fg3 }
            }
            MouseArea { id: armArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: recorder.arm(h.track.id) }
            HoverTip { text: arm.lit ? "Armed: press Record (R) to record on this track. Click to disarm."
                                     : "Get this track ready to record: then press Record (R)"
                       hovered: armArea.containsMouse; pressed: armArea.pressed }
        }
        Repeater {
            model: [{ field: "mute", letter: "M", lit: Theme.warn }, { field: "solo", letter: "S", lit: Theme.ok }]
            delegate: Rectangle {
                id: t
                required property var modelData
                readonly property bool lit: h.track[modelData.field]
                width: 20; height: 18; radius: 4
                color: lit ? modelData.lit : tArea.containsMouse ? Theme.hover : "transparent"
                Behavior on color { ColorAnimation { duration: Theme.fast } }
                Text { anchors.centerIn: parent; text: t.modelData.letter; font.family: uiFont
                       font.pixelSize: Theme.label; font.weight: Font.DemiBold
                       color: t.lit ? Theme.app : tArea.containsMouse ? Theme.fg : Theme.fg3 }
                MouseArea { id: tArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: backend.toggleTrack(h.track.id, t.modelData.field) }
            }
        }
    }
}
