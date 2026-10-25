import QtQuick
import "."

// The one ease list (2D SPEC pro-workflows 3.7, mockup 3), opened by the EasePicker's button and by a key's right-click:
// the main eases, each a row with its small curve (28 x 18), its name and its key at the right (F9 …), the current one
// ticked; under them a fold "More" with the rest, open by itself when the current ease is one of them. The pointer on a
// row sends hovered(id) (the app plays that ease, nothing kept); leaving every row, or the list closing, sends
// hovered("") (put back) BEFORE a click's picked(id) (one change). Up / Down / Enter pick from the keyboard.
// `eases`: [{id, label, group: "main" | "more", curve, keys}] (rostrum_gui/eases.py rows).
SmallPopup {
    id: menu
    property var eases: []
    property string current: ""
    property bool moreOpen: false
    property int highlighted: -1
    signal picked(string id)
    signal hovered(string id)
    ownKeys: ["Up", "Down", "Enter"]
    width: 250
    padding: Theme.grid
    margins: Theme.grid
    focus: true
    readonly property var mains: eases.filter(e => e.group === "main")
    readonly property var mores: eases.filter(e => e.group !== "main")
    readonly property var shown: moreOpen ? mains.concat(mores) : mains          // the rows Up / Down walk
    onAboutToShow: {
        moreOpen = mores.some(e => e.id === current)
        highlighted = shown.findIndex(e => e.id === current)
    }
    // a hover changes at most once per pointer move: leaving row A and entering row B is one change, A → B
    property string sent: ""
    property string want: ""
    function hoverTo(id) { want = id; Qt.callLater(flush) }
    function flush() { if (want !== sent) { sent = want; hovered(want) } }
    property string chosen: ""
    onClosed: {
        want = ""; flush()                                          // put back first ...
        if (chosen !== "") { const v = chosen; chosen = ""; picked(v) }   // ... then the one change
    }
    function pick(id) { chosen = id === current ? "" : id; close() }
    background: MenuBackground { }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }

    component EaseRow: Rectangle {
        id: row
        property var ease
        objectName: "ease_" + ease.id
        width: menu.availableWidth; height: Theme.popupRow; radius: 4
        readonly property bool lit: menu.highlighted >= 0 && menu.shown[menu.highlighted] && menu.shown[menu.highlighted].id === ease.id
        color: lit ? Theme.hover : "transparent"
        Text {
            visible: row.ease.id === menu.current
            x: Theme.gap - menu.padding; anchors.verticalCenter: parent.verticalCenter
            text: "✓"; color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont
        }
        EaseIcon { id: icon; x: 22; anchors.verticalCenter: parent.verticalCenter; points: row.ease.curve; ink: row.lit ? Theme.fg : Theme.fg2 }
        Text {
            anchors { left: icon.right; leftMargin: Theme.gap; right: keys.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
            text: row.ease.label; elide: Text.ElideRight; color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont
        }
        Text {
            id: keys
            anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
            text: row.ease.keys || ""; color: Theme.fg2; font.pixelSize: Theme.label; font.family: uiFont
        }
        MouseArea {
            anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
            onEntered: { menu.highlighted = menu.shown.findIndex(e => e.id === row.ease.id); menu.hoverTo(row.ease.id) }
            onExited: menu.hoverTo("")
            onClicked: menu.pick(row.ease.id)
        }
    }

    contentItem: Column {
        focus: true
        Keys.onUpPressed: menu.highlighted = Math.max(0, menu.highlighted - 1)
        Keys.onDownPressed: menu.highlighted = Math.min(menu.shown.length - 1, menu.highlighted + 1)
        Keys.onReturnPressed: if (menu.highlighted >= 0) menu.pick(menu.shown[menu.highlighted].id)
        Keys.onEnterPressed: if (menu.highlighted >= 0) menu.pick(menu.shown[menu.highlighted].id)
        Repeater { model: menu.mains; delegate: EaseRow { required property var modelData; ease: modelData } }
        Rectangle { visible: menu.mores.length > 0; width: menu.availableWidth; height: 9; color: "transparent"
                    Rectangle { anchors.centerIn: parent; width: parent.width; height: 1; color: Theme.line } }
        Rectangle {   // the fold: More
            objectName: "easeMore"
            visible: menu.mores.length > 0
            width: menu.availableWidth; height: Theme.popupRow; radius: 4
            color: foldArea.containsMouse ? Theme.hover : "transparent"
            Chevron { id: fold; x: 8; anchors.verticalCenter: parent.verticalCenter; rotation: menu.moreOpen ? 0 : -90 }
            Text {
                anchors { left: fold.right; leftMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                text: "More"; color: Theme.fg2; font.pixelSize: Theme.label; font.family: uiFont
            }
            MouseArea { id: foldArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: menu.moreOpen = !menu.moreOpen }
        }
        Repeater { model: menu.moreOpen ? menu.mores : []; delegate: EaseRow { required property var modelData; ease: modelData } }
    }
}
