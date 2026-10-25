import QtQuick
import RostrumKit

// "› Main ▾" after the project's name: the scene this window shows. Its menu switches to another scene, makes a new one,
// renames, duplicates, moves or deletes the one shown (backend.sceneEntries / sceneMenuPicked, scenes.py). Double-click
// the name (or Rename scene) to type a new one. Always there: a project can always get a second scene.
Item {
    id: crumb
    objectName: "sceneCrumb"
    implicitWidth: crumbRow.implicitWidth + 2 * Theme.grid; implicitHeight: Theme.button
    property bool renaming: false
    function beginRename() {       // (the menu gives the keyboard back to where it was as it closes: the box takes it after that)
        renaming = true; nameBox.text = backend.frameInfo.label; nameBox.had = false
        if (sceneMenu.visible) sceneMenu.close(); else focusBox()
    }
    function focusBox() { nameBox.forceActiveFocus(); nameBox.selectAll() }
    function endRename(keep) { if (!renaming) return; renaming = false; if (keep) backend.renameScene(nameBox.text) }
    function open() { sceneMenu.entries = backend.sceneEntries(); sceneMenu.openFrom(crumb, "left") }
    Rectangle { anchors.fill: parent; radius: Theme.radiusCtl; color: crumbArea.containsMouse ? Theme.hover : "transparent" }
    Row {
        id: crumbRow
        x: Theme.grid; anchors.verticalCenter: parent.verticalCenter; spacing: Theme.grid
        Text { text: "›"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body; anchors.verticalCenter: parent.verticalCenter }
        Text { objectName: "sceneCrumbName"; visible: !crumb.renaming; width: Math.min(implicitWidth, 220); elide: Text.ElideRight
               text: backend.frameInfo.label; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
               font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter
               HoverHandler { id: nameHover }
               HoverTip { text: parent.truncated ? parent.text : ""; hovered: nameHover.hovered } }
        Chevron { color: Theme.fg3; anchors.verticalCenter: parent.verticalCenter }
    }
    TextInput {  // the name box while renaming: Enter or leaving the box keeps, Esc drops
        id: nameBox
        objectName: "sceneNameBox"
        visible: crumb.renaming
        x: Theme.grid + 14; width: Math.max(120, crumbRow.implicitWidth - 14 - Theme.grid); anchors.verticalCenter: parent.verticalCenter
        font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold; color: Theme.fg; selectByMouse: true; clip: true
        onAccepted: crumb.endRename(true)
        property bool had: false
        onActiveFocusChanged: { if (activeFocus) had = true; else if (had) crumb.endRename(true) }
        Keys.onEscapePressed: crumb.endRename(false)
    }
    MouseArea { id: crumbArea; objectName: "sceneCrumbArea"; anchors.fill: parent; hoverEnabled: true; enabled: !crumb.renaming
                cursorShape: Qt.PointingHandCursor
                property double lastClick: 0      // (the first click opens the menu, whose close eats the second press's double-click: two clicks close together are one)
                onClicked: { const now = Date.now(); if (now - lastClick < Qt.styleHints.mouseDoubleClickInterval) { lastClick = 0; crumb.beginRename() } else { lastClick = now; crumb.open() } }
                onDoubleClicked: { lastClick = 0; crumb.beginRename() } }
    Connections { target: sceneMenu; function onClosed() { if (crumb.renaming) Qt.callLater(crumb.focusBox) } }
    Menu {
        id: sceneMenu
        objectName: "sceneMenu"
        width: 340
        onPicked: (v) => { crumbArea.lastClick = 0; v === "scene:rename" ? crumb.beginRename() : backend.sceneMenuPicked(v) }
    }
}
