import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// The File button in the top bar: New, Open, Open sample, Save (only while there is something to save), Save as, and the projects
// opened last. Each is also a Ctrl+K command and a shortcut (files.commands); `act(key)` is what a click does.
Button {
    id: fileButton
    property alias menuOpen: menu.visible
    signal act(string key)
    text: "File"
    down: menu.visible
    onClicked: menu.visible ? menu.close() : menu.open()

    QQC.Popup {
        id: menu
        y: parent.height + 2
        width: 264
        padding: Theme.grid
        background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
        contentItem: Column {
            Repeater {
                model: files.menu
                delegate: Rectangle {
                    id: row
                    required property var modelData
                    readonly property bool first: modelData.hint === "Recent" && (index === 0 || files.menu[index - 1].hint !== "Recent")
                    required property int index
                    width: menu.availableWidth; height: Theme.popupRow + (first ? heading.height : 0)
                    color: "transparent"
                    Text {   // "Recent", once, over the projects opened last
                        id: heading
                        visible: row.first; height: visible ? Theme.popupRow : 0
                        leftPadding: Theme.gap - menu.padding; verticalAlignment: Text.AlignBottom; bottomPadding: Theme.grid
                        text: "Recent"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
                    }
                    Rectangle {
                        y: heading.height; width: parent.width; height: Theme.popupRow; radius: 4
                        color: hover.hovered ? Theme.hover : "transparent"
                        Text {
                            anchors { left: parent.left; leftMargin: Theme.gap - menu.padding; right: chip.left; rightMargin: Theme.gap
                                      verticalCenter: parent.verticalCenter }
                            text: row.modelData.label
                            elide: Text.ElideRight; color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont
                        }
                        KeyHint { id: chip; visible: row.modelData.hint !== "Recent" && row.modelData.hint !== ""; text: row.modelData.hint
                                  anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter }
                        HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: { menu.close(); fileButton.act(row.modelData.key) } }
                    }
                }
            }
        }
    }
}
