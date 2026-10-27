import QtQuick
import "."

// The app's mark and ▾, first in the top bar: it says which app this is and opens the app's menu (the File menu: the
// `menu` slot's FilesMenu, which sits invisible under it and does the opening, so its keys, dialogs and the menu's
// place stay its own). `appIcon`: a picture's address, or a kit mark's name ("app-2d", "app-sound", "app-3d":
// marks/<name>.svg, stand-ins until the real app icons are drawn). With no icon: the kit's ≡.
// Another window in front (`active` false): the mark loses most of its colour; its place and size never change.
Item {
    id: m
    property string appIcon: ""
    property var target: null                 // the menu button (FilesMenu): openMenu(), closeMenu(), menuOpen
    property bool active: true
    readonly property bool open: !!target && !!target.menuOpen
    readonly property url source: appIcon === "" ? "" : appIcon.indexOf(":") >= 0 ? appIcon : Qt.resolvedUrl("marks/" + appIcon + ".svg")
    readonly property bool hovered: area.containsMouse
    implicitWidth: Theme.grid + 20 + Theme.grid + 8 + Theme.grid + 2; implicitHeight: Theme.button
    width: implicitWidth; height: implicitHeight
    objectName: "appMark"

    Rectangle {      // hover and press, as every top-bar button
        anchors.fill: parent; radius: Theme.radiusCtl
        color: area.pressed || m.open ? Theme.active : m.hovered ? Theme.hover : "transparent"
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
    Image {
        id: mark
        visible: m.appIcon !== ""
        x: Theme.grid; anchors.verticalCenter: parent.verticalCenter
        width: 20; height: 20; sourceSize: Qt.size(40, 40); smooth: true
        source: m.source
    }
    Rectangle {      // inactive: a grey veil over the mark (most of its colour goes, its shape stays)
        visible: mark.visible && !m.active
        anchors.fill: mark; radius: 5; color: Theme.app; opacity: 0.6
    }
    ToolIcon { visible: m.appIcon === ""; x: Theme.grid + 1; anchors.verticalCenter: parent.verticalCenter
               name: "menu"; width: 18; height: 18; ink: m.hovered || m.open ? Theme.fg : Theme.fg2 }
    Chevron { x: Theme.grid + 20 + Theme.grid; anchors.verticalCenter: parent.verticalCenter; width: 8; open: m.open
              color: m.active ? Theme.fg2 : Theme.fg4 }
    MouseArea {
        id: area
        anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
        onClicked: if (m.target) m.open ? m.target.closeMenu() : m.target.openMenu()
    }
    HoverTip { text: "Menu"; help: "New, open, duplicate, versions and the start screen"; hovered: area.containsMouse && !m.open
               pressed: area.pressed }
}
