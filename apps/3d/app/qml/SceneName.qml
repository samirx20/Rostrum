import QtQuick
import RostrumKit

// A scene list row's name side (SceneRows.qml), SPEC §1: fold arrow, kind icon, name, its material dim (click it: edit
// the material). Click selects the item (Ctrl+click adds or takes out, Shift+click the run from the primary);
// right-click picks it and opens its menu; a material dropped on it is given to it. A setting's row (or a second line
// of overlapping animations) is a dim name under its item, indented.
Rectangle {
    id: row
    objectName: field ? "" : "sceneRow:" + modelData.id      // a scripted hand finds a row by it
    required property var modelData
    property Item menu                  // the item menu (ContextMenu3D, SceneRows.qml)
    readonly property bool field: modelData.row === "field"
    readonly property bool selected: !field && (modelData.id === backend.selected || backend.selectedRows.length > 1 && backend.selectedRows.indexOf(modelData.id) >= 0)
    readonly property bool inSelected: !selected && modelData.owner === backend.selectedOwner && !field
    readonly property int indent: Theme.gap + modelData.depth * 16
    height: field ? Theme.rowDense - 2 : Theme.rowDense; radius: Theme.radiusCtl
    color: selected ? Theme.accentSoft : hover.containsMouse || inSelected ? Theme.hover : "transparent"
    MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
                onClicked: (m) => {   // Ctrl+click adds or takes out; Shift+click picks the run from the primary; right-click picks and opens the menu
                    if (m.button === Qt.RightButton) { backend.select(row.modelData.owner); row.menu.openAt(row, m.x, m.y, row.modelData.owner) }
                    else if (row.field) backend.select(row.modelData.owner)
                    else if (m.modifiers & Qt.ControlModifier) backend.toggleInSelection(row.modelData.id)
                    else if (m.modifiers & Qt.ShiftModifier) backend.selectRange(row.modelData.id)
                    else backend.select(row.modelData.owner)
                } }
    DropArea {  // a material dragged from the picker or the Materials list: this item gets it (the row lights while it hovers)
        anchors.fill: parent; keys: ["rostrum-material"]; enabled: !row.field
        onDropped: (d) => { backend.mats.dropOn(d.source.materialId, row.modelData.id); d.accept() }
        Rectangle { anchors.fill: parent; radius: Theme.radiusCtl; color: "transparent"; visible: parent.containsDrag
                    border.width: 1; border.color: Theme.accent }
    }
    Item {  // the fold arrow (absent when there is nothing to fold)
        x: row.indent - 2; width: 14; height: parent.height
        visible: row.modelData.fold !== ""
        Chevron { anchors.centerIn: parent; rotation: row.modelData.fold === "open" ? 0 : -90
                  color: foldArea.containsMouse ? Theme.fg : Theme.fg3 }
        MouseArea { id: foldArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: backend.toggleFold(row.modelData.id) }
    }
    KindIcon {
        id: icon
        visible: !row.field
        x: row.indent + 16; anchors.verticalCenter: parent.verticalCenter
        kind: row.modelData.kind
        ink: row.selected ? Theme.accentHover : row.modelData.row === "part" ? Theme.fg3 : Theme.fg2
    }
    Text {
        id: name
        anchors { left: icon.left; leftMargin: row.field ? 0 : icon.width + Theme.gap; verticalCenter: parent.verticalCenter
                  right: matName.visible ? matName.left : parent.right; rightMargin: Theme.gap }
        text: (row.modelData.cutter ? "− " : "") + row.modelData.label; elide: Text.ElideRight; font.family: uiFont
        font.pixelSize: row.field ? Theme.label + 1 : Theme.body
        color: row.field || row.modelData.row === "part" && !row.selected ? Theme.fg2 : Theme.fg
        HoverHandler { id: nameHover }
        HoverTip { text: name.truncated ? name.text : ""; hovered: nameHover.hovered }
    }
    Text {  // its material: click to edit it (only while the name has its whole room: the name comes first)
        id: matName
        readonly property real room: row.width - name.x - Theme.gap * 2
        visible: row.modelData.material !== "" && name.implicitWidth + Theme.gap + implicitWidth <= room
        anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
        text: row.modelData.material; font.family: uiFont; font.pixelSize: Theme.label
        color: matArea.containsMouse ? Theme.fg : Theme.fg3
        MouseArea { id: matArea; anchors.fill: parent; anchors.margins: -4; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { const m = backend.materials.find(x => x.label === row.modelData.material); if (m) backend.select(m.value) } }
    }
}
