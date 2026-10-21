import QtQuick
import "."

// A keyboard shortcut chip ("Ctrl K", "Ctrl Z").
Rectangle {
    property alias text: t.text
    height: 20; width: t.implicitWidth + 2 * Theme.gap; radius: 4
    color: Theme.active
    Text { id: t; anchors.centerIn: parent; color: Theme.fg2; font.pixelSize: Theme.label; font.family: uiFont }
}
