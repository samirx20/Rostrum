import QtQuick
import RostrumKit

// Animate page, bottom, full width: one row per layer (a summary of all its keys), opened by its arrow into one
// row per animated field. Diamonds sit at key times. Click a diamond: the key is selected (the inspector shows
// its time, value and ease). Drag it: key.set t, one gesture = one undo step. The ruler scrubs the playhead.
Panel {
    id: panel
    title: "Timeline"
    property int labelWidth: 236
    readonly property real duration: backend.frameInfo.duration
    headerRight: [
        TimeReadout { anchors.verticalCenter: parent.verticalCenter },
        Item { width: Theme.gap; height: 1 },
        PlayButton { playing: backend.playing; onClicked: backend.togglePlay(); implicitHeight: 24; implicitWidth: 24 }
    ]

    TimeRuler {
        id: ruler
        x: panel.labelWidth + Theme.gap + 8; width: parent.width - x - Theme.gap - 8; height: 22   // 8: room for a key at 0
        duration: panel.duration; fps: backend.frameInfo.fps; time: backend.time
    }
    ListView {
        id: rows
        anchors { left: parent.left; right: parent.right; top: ruler.bottom; bottom: parent.bottom; topMargin: Theme.grid }
        model: backend.tracks
        spacing: 2
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        delegate: Item {
            id: row
            required property var modelData
            readonly property bool isField: modelData.row === "field"
            readonly property bool selected: modelData.owner === backend.selectedLayer
            width: ListView.view.width; height: isField ? Theme.rowDense - 2 : Theme.rowDense

            Rectangle {  // the label
                width: panel.labelWidth; height: parent.height; radius: Theme.radiusCtl
                color: row.selected && !row.isField ? Theme.accentSoft : "transparent"
                Item {
                    id: fold
                    x: Theme.gap - 2 + row.modelData.depth * 16; width: 14; height: parent.height
                    visible: row.modelData.fold !== ""
                    Chevron { anchors.centerIn: parent; rotation: row.modelData.fold === "open" ? 0 : -90
                              color: foldArea.containsMouse ? Theme.fg : Theme.fg3 }
                }
                Text {
                    x: Theme.gap + 16 + row.modelData.depth * 16; width: parent.width - x - Theme.gap
                    anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight
                    text: row.modelData.label; font.family: uiFont
                    font.pixelSize: row.isField ? Theme.label + 1 : Theme.body
                    color: row.isField ? Theme.fg2 : Theme.fg
                }
                MouseArea {
                    id: foldArea; anchors.fill: parent; hoverEnabled: true
                    onClicked: row.modelData.fold !== "" && mouseX < fold.x + fold.width + 4
                               ? backend.toggleTrack(row.modelData.id) : backend.select(row.modelData.owner)
                }
            }
            Rectangle {  // the track
                id: track
                x: ruler.x - 8; width: ruler.width + 16; height: parent.height; radius: Theme.radiusCtl
                color: row.isField ? Qt.darker(Theme.panel, 1.15) : Theme.sunken
                MouseArea { anchors.fill: parent; onPressed: (m) => backend.setTime(ruler.tOf(m.x - 8))
                            onPositionChanged: (m) => backend.setTime(ruler.tOf(m.x - 8)) }
                Repeater {
                    model: row.modelData.keys
                    delegate: Item {
                        id: key
                        required property var modelData
                        readonly property bool on: modelData.id === backend.selected
                        x: 8 + Math.round(ruler.xOf(modelData.t)) - width / 2; width: 16; height: track.height
                        KeyMark {
                            anchors.centerIn: parent; size: row.isField ? 8 : 7
                            color: key.on ? Theme.accent : keyArea.containsMouse ? Theme.fg
                                 : row.isField ? Theme.fg2 : Theme.fg3
                        }
                        MouseArea {
                            id: keyArea; anchors.fill: parent; hoverEnabled: true; preventStealing: true
                            cursorShape: Qt.SizeHorCursor
                            onPressed: backend.beginKeyDrag(key.modelData.id)
                            onPositionChanged: (m) => backend.keyDragTo(ruler.tOf(mapToItem(track, m.x, 0).x - 8))
                            onReleased: backend.endDrag()
                            onCanceled: backend.endDrag()
                        }
                    }
                }
            }
        }
    }
    Rectangle {  // the playhead line, across every row
        x: ruler.x + Math.round(ruler.xOf(backend.time)); y: ruler.y + ruler.height
        width: 1; height: parent.height - y; color: Theme.accent; opacity: 0.8
    }
}
