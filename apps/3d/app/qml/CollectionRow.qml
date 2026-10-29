import QtQuick
import RostrumKit

// Collections (PR1, screen3d/bridge_shot_only.py): a row under the scene list's rows, there only once the scene has a
// collection (right-click items › New collection makes one). Left, in the names column: "Collections". Right: a chip
// per collection, "Props · 3". A click picks its items; a right-click opens what would change something now: Hide, Show,
// Hide / Show in the shown shot only (2+ shots), Add selected (picked items not in it), Delete. A double-click renames it.
Item {
    id: row
    objectName: "collectionRow"
    property int labelWidth: 240
    readonly property var list: backend.collections
    readonly property bool manyShots: backend.shots.length > 1
    height: list.length > 0 ? Theme.button + 4 : 0
    visible: list.length > 0
    Rectangle { anchors.fill: parent; color: Theme.panel }
    Rectangle { width: parent.width; height: 1; color: Theme.line }

    Text {
        x: Theme.gap + 16; width: row.labelWidth - x - Theme.gap
        anchors.verticalCenter: parent.verticalCenter
        text: "Collections"; elide: Text.ElideRight
        color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
    }
    Flickable {
        id: strip
        x: row.labelWidth; width: row.width - x - Theme.gap; height: parent.height
        contentWidth: chips.implicitWidth; clip: true; interactive: contentWidth > width
        WheelScroll { flick: strip }   // the first click after a wheel scroll lands (the kit's WheelScroll.qml)
        Row {
            id: chips
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.grid
            Repeater {
                model: row.list
                delegate: Rectangle {
                    id: chip
                    required property var modelData
                    objectName: "collection:" + modelData.id
                    width: words.implicitWidth + 2 * Theme.pad; height: Theme.button - 4
                    radius: Theme.radiusCtl
                    color: area.containsMouse ? Theme.raised : Theme.sunken
                    border.width: 1; border.color: Theme.line
                    Text { id: words; anchors.centerIn: parent; visible: !namer.visible
                           text: chip.modelData.label + " · " + chip.modelData.count
                           color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label }
                    MouseArea {
                        id: area; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
                        cursorShape: Qt.PointingHandCursor
                        onClicked: (e) => e.button === Qt.RightButton ? menu.openFor(chip) : backend.selectCollection(chip.modelData.id)
                        onDoubleClicked: { namer.text = chip.modelData.label; namer.visible = true; namer.forceActiveFocus(); namer.selectAll() }
                    }
                    TextInput {
                        id: namer
                        objectName: "collectionName:" + chip.modelData.id
                        visible: false; anchors.centerIn: parent; width: chip.width - Theme.pad
                        color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label; selectByMouse: true
                        onAccepted: { backend.renameCollection(chip.modelData.id, text); visible = false }
                        onActiveFocusChanged: if (!activeFocus) visible = false
                        Keys.onEscapePressed: visible = false
                    }
                }
            }
        }
    }
    Menu {
        id: menu
        objectName: "collectionMenu"
        width: 220
        property string target: ""
        function openFor(chip) {
            const c = chip.modelData, shot = backend.shotOnlyName
            target = c.id
            const e = []                                  // only what would change something now
            if (c.canHide) e.push({ value: "hide", label: "Hide" })
            if (c.canShow) e.push({ value: "show", label: "Show" })
            if (row.manyShots && c.canHideShot) e.push({ value: "hideShot", label: "Hide in " + shot + " only" })
            if (row.manyShots && c.canShowShot) e.push({ value: "showShot", label: "Show in " + shot + " only" })
            if (backend.selection.some(i => c.ids.indexOf(i) < 0)) e.push({ value: "add", label: "Add selected" })
            e.push({ value: "delete", label: "Delete collection" })
            entries = e
            openFrom(chip, "left")
        }
        onPicked: (v) => backend.collectionDo(target, v)
    }
}
