import QtQuick
import QtQuick.Controls as QQC
import "."
import "MenuPlace.js" as Place

// A small popup list of actions under whatever it sits in (a button's Add menu). `entries`: [{value, label, keys, checked}];
// choosing one closes it and sends picked(value). Up / Down move, Enter picks, Esc closes. When any entry has
// `checked`, a fixed left column shows ✓ on the chosen one; `keys` sit right-aligned.
SmallPopup {
    id: menu
    ownKeys: ["Up", "Down", "Enter"]          // the window's shortcuts for these wait while it is open (OpenPopups)
    property var entries: []
    property int highlighted: 0
    readonly property bool checks: entries.some(e => e.checked !== undefined)
    readonly property int checkW: checks ? 18 : 0
    signal picked(string value)
    y: parent ? parent.height + 2 : 0
    width: 168
    padding: Theme.grid
    margins: Theme.grid                 // never past the window's edge: it moves inside (a menu under a low tile)
    focus: true
    onAboutToShow: highlighted = 0
    // openFrom(button, "right"): by the kit's one placement rule (MenuPlace.js), clear of the rail, settings panel and names column
    property Item spotAnchor: null
    property string spotAlign: "left"
    function openFrom(anchor, align) { spotAnchor = anchor; spotAlign = align || "left"; reposition(); open() }
    function reposition() {
        const ov = QQC.Overlay.overlay
        if (!ov || !spotAnchor || !parent || !spotAnchor.Window.window) return
        const q = Place.near(spotAnchor, width, height, spotAnchor.Window.window.contentItem, ov, { align: spotAlign })
        const p = parent.mapFromItem(ov, q.x, q.y)
        x = p.x; y = p.y
    }
    onHeightChanged: if (visible && spotAnchor) reposition()
    onWidthChanged: if (visible && spotAnchor) reposition()
    onOpened: Qt.callLater(reposition)       // its size has settled by now
    onClosed: spotAnchor = null
    background: MenuBackground { }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }
    contentItem: Column {
        focus: true
        function pick(i) { const v = menu.entries[i].value; menu.close(); menu.picked(v) }
        Keys.onUpPressed: menu.highlighted = Math.max(0, menu.highlighted - 1)
        Keys.onDownPressed: menu.highlighted = Math.min(menu.entries.length - 1, menu.highlighted + 1)
        Keys.onReturnPressed: pick(menu.highlighted)
        Keys.onEnterPressed: pick(menu.highlighted)
        Repeater {
            model: menu.entries
            delegate: Rectangle {
                id: row
                required property int index
                required property var modelData
                objectName: "menu:" + modelData.value          // a walk clicks an entry by its value (clickobj)
                width: menu.availableWidth; height: Theme.popupRow; radius: 4
                color: index === menu.highlighted ? Theme.hover : "transparent"
                Text {
                    visible: menu.checks && !!row.modelData.checked
                    x: Theme.gap - menu.padding; anchors.verticalCenter: parent.verticalCenter
                    text: "✓"; color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont
                }
                Text {
                    anchors { left: parent.left; leftMargin: Theme.gap - menu.padding + menu.checkW; verticalCenter: parent.verticalCenter
                              right: keys.visible ? keys.left : parent.right; rightMargin: keys.visible ? Theme.gap : Theme.gap - menu.padding }
                    text: row.modelData.label; elide: Text.ElideRight
                    color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont
                }
                Text {
                    id: keys
                    visible: !!row.modelData.keys
                    anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                    text: row.modelData.keys || ""; color: Theme.fg2; font.pixelSize: Theme.label; font.family: uiFont
                }
                MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onEntered: menu.highlighted = row.index; onClicked: row.parent.pick(row.index) }
            }
        }
    }
}
