import QtQuick
import RostrumKit

// "› Main ▾" after the project's name: the scene this window shows. Its list switches to another scene or makes a new one
// (backend.sceneEntries / showScene, scenes.py). Always there: a project can always get a second scene.
Item {
    id: crumb
    objectName: "sceneCrumb"
    implicitWidth: crumbRow.implicitWidth + 2 * Theme.grid; implicitHeight: Theme.button
    function open() { sceneMenu.entries = backend.sceneEntries(); sceneMenu.openFrom(crumb, "left") }
    Rectangle { anchors.fill: parent; radius: Theme.radiusCtl; color: crumbArea.containsMouse ? Theme.hover : "transparent" }
    Row {
        id: crumbRow
        x: Theme.grid; anchors.verticalCenter: parent.verticalCenter; spacing: Theme.grid
        Text { text: "›"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body; anchors.verticalCenter: parent.verticalCenter }
        Text { objectName: "sceneCrumbName"; width: Math.min(implicitWidth, 220); elide: Text.ElideRight
               text: backend.frameInfo.label; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
               font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter
               HoverHandler { id: nameHover }
               HoverTip { text: parent.truncated ? parent.text : ""; hovered: nameHover.hovered } }
        Chevron { color: Theme.fg3; anchors.verticalCenter: parent.verticalCenter }
    }
    MouseArea { id: crumbArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: crumb.open() }
    Menu {
        id: sceneMenu
        objectName: "sceneMenu"
        width: 340
        onPicked: (v) => backend.showScene(v)
    }
}
