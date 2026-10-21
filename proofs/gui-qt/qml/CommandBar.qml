import QtQuick
import QtQuick.Controls
import "."

// Ctrl+K: type to filter, ↑ ↓ to move, Enter to run, Esc to close.
Popup {
    id: bar
    property var app
    property var shown: []
    parent: Overlay.overlay
    x: Math.round((parent.width - width) / 2); y: 96
    width: 520; height: Math.min(search.height + list.contentHeight + 3 * Theme.gap, 420)
    padding: Theme.gap
    modal: true; focus: true
    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, 0.35) }
    background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Qt.rgba(1, 1, 1, 0.06) }

    function refilter() {
        var q = search.text.toLowerCase()
        shown = app.commands.filter(function(c) { return c.name.toLowerCase().indexOf(q) >= 0 })
        list.currentIndex = 0
    }
    function runCurrent() {
        var c = shown[list.currentIndex]
        if (!c) return
        close(); c.run()
    }
    onAboutToShow: { search.text = ""; refilter(); search.forceActiveFocus() }

    Column {
        anchors.fill: parent
        spacing: Theme.gap
        TextField {
            id: search
            width: parent.width; height: 36
            placeholderText: "Type a command"
            placeholderTextColor: Theme.fg3
            color: Theme.fg; font.pixelSize: Theme.title; leftPadding: Theme.pad
            background: Rectangle { color: Theme.panel; radius: Theme.radiusCtl }
            onTextChanged: bar.refilter()
            Keys.onDownPressed: list.currentIndex = Math.min(list.count - 1, list.currentIndex + 1)
            Keys.onUpPressed: list.currentIndex = Math.max(0, list.currentIndex - 1)
            Keys.onReturnPressed: bar.runCurrent()
            Keys.onEnterPressed: bar.runCurrent()
            Keys.onEscapePressed: bar.close()
        }
        ListView {
            id: list
            width: parent.width; height: contentHeight
            model: bar.shown
            interactive: false
            delegate: Rectangle {
                required property var modelData
                required property int index
                width: ListView.view.width; height: Theme.row + 4; radius: Theme.radiusCtl
                color: index === list.currentIndex ? Theme.accentSoft : "transparent"
                Text { anchors.left: parent.left; anchors.leftMargin: Theme.pad; anchors.verticalCenter: parent.verticalCenter
                       text: modelData.name; color: Theme.fg; font.pixelSize: Theme.body }
                Text { anchors.right: parent.right; anchors.rightMargin: Theme.pad; anchors.verticalCenter: parent.verticalCenter
                       text: modelData.hint; color: Theme.fg3; font.pixelSize: Theme.label }
                MouseArea { anchors.fill: parent; hoverEnabled: true
                            onEntered: list.currentIndex = index; onClicked: bar.runCurrent() }
            }
        }
        Text { visible: list.count === 0; text: "No matching command"; color: Theme.fg3; font.pixelSize: Theme.body; leftPadding: Theme.pad }
    }
}
