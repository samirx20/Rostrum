import QtQuick
import RostrumKit

// Bottom, full width: the shot's frames. One row per item that moves (all its keys on one line); the selected item
// opens into one row per animated field. Diamonds sit at key times. Click a diamond: the key is selected (the
// inspector shows its time, value and ease). Drag it: key.set t in whole frames, one gesture = one undo step.
// The ruler and the tracks scrub the playhead; the viewport draws that frame.
Panel {
    id: panel
    title: "Timeline"
    property int labelWidth: 236
    readonly property var shot: backend.shotInfo
    headerRight: [
        Text { anchors.verticalCenter: parent.verticalCenter; text: "frame " + backend.frame; color: Theme.fg
               font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 } },
        Item { width: Theme.grid; height: 1 },
        Text { anchors.verticalCenter: parent.verticalCenter; text: backend.time.toFixed(2) + " s"; color: Theme.fg3
               font.family: uiFont; font.pixelSize: Theme.label; font.features: { "tnum": 1 } },
        Item { width: Theme.gap; height: 1 },
        PlayButton { playing: backend.playing; onClicked: backend.togglePlay(); implicitHeight: 24; implicitWidth: 24 }
    ]

    FrameRuler {
        id: ruler
        x: panel.labelWidth + Theme.gap + 8; width: parent.width - x - Theme.gap - 8; height: 22   // 8: room for a key at the ends
        first: panel.shot.start; last: panel.shot.end; frame: backend.frame
    }
    ListView {
        anchors { left: parent.left; right: parent.right; top: ruler.bottom; bottom: parent.bottom; topMargin: Theme.grid }
        model: backend.tracks
        spacing: 2
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        delegate: Item {
            id: row
            required property var modelData
            readonly property bool isField: modelData.row === "field"
            readonly property bool selected: modelData.owner === backend.selectedOwner
            width: ListView.view.width; height: isField ? Theme.rowDense - 2 : Theme.rowDense

            Rectangle {  // the label
                width: panel.labelWidth; height: parent.height; radius: Theme.radiusCtl
                color: row.selected && !row.isField ? Theme.accentSoft : "transparent"
                Text {
                    x: Theme.gap + (row.isField ? 16 : 0); width: parent.width - x - Theme.gap
                    anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight
                    text: row.modelData.label; font.family: uiFont
                    font.pixelSize: row.isField ? Theme.label + 1 : Theme.body
                    color: row.isField ? Theme.fg2 : Theme.fg
                }
                MouseArea { anchors.fill: parent; onClicked: backend.select(row.modelData.owner) }
            }
            Rectangle {  // the track
                id: track
                x: ruler.x - 8; width: ruler.width + 16; height: parent.height; radius: Theme.radiusCtl
                color: row.isField ? Qt.darker(Theme.panel, 1.15) : Theme.sunken
                MouseArea { anchors.fill: parent; onPressed: (m) => backend.setFrame(Math.round(ruler.fOf(m.x - 8)))
                            onPositionChanged: (m) => backend.setFrame(Math.round(ruler.fOf(m.x - 8))) }
                Repeater {
                    model: row.modelData.keys
                    delegate: Item {
                        id: key
                        required property var modelData
                        readonly property bool on: modelData.id === backend.selected
                        property real dragF: -1            // while dragged: the frame under the pointer (rows refresh on release)
                        x: 8 + Math.round(ruler.xOf(dragF >= 0 ? dragF : modelData.t * panel.shot.fps)) - width / 2
                        width: 16; height: track.height
                        KeyMark {
                            anchors.centerIn: parent; size: row.isField ? 8 : 7
                            color: key.on ? Theme.accent : keyArea.containsMouse ? Theme.fg
                                 : row.isField ? Theme.fg2 : Theme.fg3
                        }
                        MouseArea {
                            id: keyArea; anchors.fill: parent; hoverEnabled: true; preventStealing: true
                            cursorShape: Qt.SizeHorCursor
                            onPressed: if (backend.beginKeyDrag(key.modelData.id)) key.dragF = key.modelData.t * panel.shot.fps
                            onPositionChanged: (m) => {
                                if (key.dragF < 0) return
                                var f = ruler.fOf(mapToItem(track, m.x, 0).x - 8)
                                key.dragF = Math.min(Math.max(Math.round(f), panel.shot.start), panel.shot.end + 1)
                                backend.keyDragTo(f)
                            }
                            onReleased: { key.dragF = -1; backend.endDrag() }
                            onCanceled: { key.dragF = -1; backend.endDrag() }
                        }
                    }
                }
            }
        }
    }
    Rectangle {  // the playhead line, across every row
        x: ruler.x + Math.round(ruler.xOf(backend.frame)); y: ruler.y + ruler.height
        width: 1; height: parent.height - y; color: Theme.accent; opacity: 0.8
    }
}
