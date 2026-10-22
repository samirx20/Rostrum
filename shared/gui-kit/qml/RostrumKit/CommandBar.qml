import QtQuick
import QtQuick.Controls as QQC
import "."

// Ctrl+K: every command that can run right now, from the operation registry (bridge.commands).
// Type to filter (all words, any order), Up / Down to move, Enter or click to run, Esc to close.
QQC.Popup {
    id: bar
    property var bridge
    property var shown: []
    parent: QQC.Overlay.overlay
    x: Math.round((parent.width - width) / 2); y: 88
    width: 560
    height: Math.min(search.height + list.contentHeight + 3 * Theme.gap + (list.count ? 0 : empty.height), 460)
    padding: Theme.gap
    modal: true; focus: true
    QQC.Overlay.modal: Rectangle { color: Theme.scrim }
    background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }

    function query(q) { search.input.text = q; refilter() }
    function refilter() { shown = bridge.commands(search.input.text); list.currentIndex = 0 }
    function runCurrent() {
        var c = shown[list.currentIndex]
        if (!c) return
        close(); bridge.run(c.key)
    }
    onAboutToShow: { search.input.text = ""; refilter(); search.input.forceActiveFocus() }

    Column {
        anchors.fill: parent
        spacing: Theme.gap
        FieldFrame {
            id: search
            width: parent.width; height: 32
            editable: true
            placeholder: "Type a command"
            onEntered: bar.runCurrent()
            onArrow: (d) => list.currentIndex = Math.max(0, Math.min(list.count - 1, list.currentIndex - d))
            Connections { target: search.input; function onTextEdited() { bar.refilter() } }
        }
        ListView {
            id: list
            width: parent.width; height: Math.min(contentHeight, 460 - search.height - 3 * Theme.gap)
            model: bar.shown
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            highlightMoveDuration: 0
            delegate: Rectangle {
                id: cmd
                required property var modelData
                required property int index
                width: ListView.view.width; height: Theme.row + 2; radius: Theme.radiusCtl
                color: index === list.currentIndex ? Theme.accentSoft : "transparent"
                Text { anchors.left: parent.left; anchors.leftMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                       anchors.right: tail.left; anchors.rightMargin: Theme.gap; elide: Text.ElideRight
                       text: cmd.modelData.label; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
                Row {
                    id: tail
                    anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                    spacing: Theme.gap
                    Text { text: cmd.modelData.hint || ""; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
                           visible: text !== ""; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: cmd.modelData.keys || ""; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
                           visible: text !== ""; anchors.verticalCenter: parent.verticalCenter }
                }
                MouseArea { anchors.fill: parent; hoverEnabled: true
                            onEntered: list.currentIndex = cmd.index; onClicked: bar.runCurrent() }
            }
        }
        Text { id: empty; visible: list.count === 0; text: "Nothing matches"; leftPadding: Theme.gap
               color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body }
    }
}
