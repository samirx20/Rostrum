import QtQuick
import "."

// One marker on a Ruler (INTERACTION.md 1.6 › Markers): a line down the ruler and a flag with its name in the
// marker band, above the time labels. Shared markers (the project's, seen in every app; `shared` missing = shared)
// are solid with a small chain; this scene's or song's own are hollow. With the ruler's editMarkers: drag = one
// markerMoved on release, double-click = rename in place (Enter keeps, Esc cancels), × on hover = markerRemoved.
// Right-click: the Ruler's marker menu (Rename, Move to playhead, Colour, Shared / Only here, Delete) when the ruler has
// a `markerSource`; Rename there starts the same name field (`startRename()`).
Item {
    id: mk
    required property var modelData
    property Item ruler
    readonly property var ru: ruler ? ruler : stub    // (the ruler arrives after the first bindings run)
    QtObject { id: stub; property real width; property real height; property int flagTop; property bool editMarkers
               function xOfSec(s) { return -1 } function nextX(at) { return 0 }
               function openMarkerMenu(flag, marker, x, y) { } }
    readonly property bool shared: modelData.shared !== false
    readonly property color tint: modelData.colour ? modelData.colour : Theme.warn
    property real dx: 0                      // while dragging (one move on release)
    property bool naming: false
    function startRename() { naming = true; editor.text = modelData.name; editor.selectAll(); editor.forceActiveFocus() }
    x: Math.round(ru.xOfSec(modelData.at) + dx); width: 1; height: ru.height
    visible: x >= 0 && x <= ru.width
    z: hit.containsMouse || crossHit.containsMouse || naming ? 2 : 1
    Rectangle { y: ru.flagTop; width: 1; height: parent.height - y; color: mk.tint; opacity: mk.shared ? 1 : 0.7 }
    Rectangle {
        id: flag
        objectName: "markerFlag:" + modelData.id        // the flag itself (not its 1 px line): what a scripted hand hovers and drags
        x: 1; y: ru.flagTop; height: 16; radius: 2
        color: mk.shared ? mk.tint : hit.containsMouse || crossHit.containsMouse ? Theme.raised : Theme.panel
        border.color: mk.tint
        readonly property int lead: mk.shared ? 15 : 4                  // room for the chain
        readonly property int room: Math.max(16, Math.min(ru.width, ru.nextX(modelData.at) - 3) - mk.x - 1)  // to the next flag
        width: mk.naming ? Math.max(editor.contentWidth + 12, 60)
                         : Math.max(16, Math.min(lead + name.implicitWidth + 4 + (cross.visible ? 14 : 0), room))
        Item {      // the chain: two small links
            visible: mk.shared
            x: 3; anchors.verticalCenter: parent.verticalCenter; width: 10; height: 6
            Rectangle { width: 6; height: 4; radius: 2; y: 1; color: "transparent"; border.color: Theme.app; border.width: 1 }
            Rectangle { x: 4; width: 6; height: 4; radius: 2; y: 1; color: "transparent"; border.color: Theme.app; border.width: 1 }
        }
        Text { id: name; x: flag.lead; anchors.verticalCenter: parent.verticalCenter; text: modelData.name
               width: Math.max(0, flag.width - flag.lead - 4 - (cross.visible ? 14 : 0)); elide: Text.ElideRight
               visible: !mk.naming; color: mk.shared ? Theme.app : mk.tint; font.family: uiFont; font.pixelSize: Theme.label - 1 }
        MouseArea {
            id: hit
            anchors.fill: parent
            enabled: ru.editMarkers && !mk.naming
            hoverEnabled: true
            preventStealing: true
            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            property real x0: 0
            onPressed: (m) => { x0 = hit.mapToItem(null, m.x, 0).x; mk.dx = 0 }     // window x: the flag moves under the pointer
            onPositionChanged: (m) => { if (pressed) mk.dx = hit.mapToItem(null, m.x, 0).x - x0 }
            onReleased: {
                if (Math.abs(mk.dx) >= 2)
                    ru.markerMoved(modelData.id, ru.secOf(ru.xOfSec(modelData.at) + mk.dx))
                mk.dx = 0
            }
            onDoubleClicked: mk.startRename()
        }
        TapHandler {      // right-click: the marker menu (built from the marker operations, rostrum_gui/marker_menu.py)
            acceptedButtons: Qt.RightButton
            enabled: ru.editMarkers && !mk.naming
            onTapped: (pt) => { const p = flag.mapToItem(null, pt.position.x, pt.position.y); ru.openMarkerMenu(mk, modelData, p.x, p.y) }
        }
        HoverTip { text: modelData.name + (mk.shared ? " · shared with the project" : " · only here")
                   help: ru.editMarkers ? "Drag to move it, double-click to rename." : ""
                   hovered: hit.containsMouse; pressed: hit.pressed || mk.naming }
        Text {      // delete, on hover
            id: cross
            objectName: "markerCross:" + modelData.id
            visible: ru.editMarkers && (hit.containsMouse || crossHit.containsMouse) && !mk.naming
            anchors.right: parent.right; anchors.rightMargin: 4; anchors.verticalCenter: parent.verticalCenter
            text: "×"; color: crossHit.containsMouse ? Theme.danger : mk.shared ? Theme.app : Theme.fg3
            font.family: uiFont; font.pixelSize: Theme.label + 1
            MouseArea { id: crossHit; anchors.fill: parent; anchors.margins: -5; hoverEnabled: true
                        onClicked: ru.markerRemoved(modelData.id) }
        }
        TextInput {
            id: editor
            visible: mk.naming
            x: 4; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 8
            color: mk.shared ? Theme.app : Theme.fg; selectionColor: Theme.accentSoft; selectByMouse: true
            font.family: uiFont; font.pixelSize: Theme.label - 1
            onAccepted: { mk.naming = false; if (text.trim() && text !== modelData.name) ru.markerRenamed(modelData.id, text.trim()) }
            onActiveFocusChanged: if (!activeFocus) mk.naming = false
            Keys.onEscapePressed: mk.naming = false
        }
    }
}
