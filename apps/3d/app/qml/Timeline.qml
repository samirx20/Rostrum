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

    Ruler {
        id: ruler
        unit: "frames"
        x: panel.labelWidth + Theme.gap + 8; width: parent.width - x - Theme.gap - 8; height: 22   // 8: room for a key at the ends
        first: panel.shot.start; last: panel.shot.end; value: backend.frame
        onScrubbed: (f) => backend.setFrame(Math.round(f))
    }
    KeyRows {
        anchors { left: parent.left; right: parent.right; top: ruler.bottom; bottom: parent.bottom; topMargin: Theme.grid }
        model: backend.tracks
        ruler: ruler; labelWidth: panel.labelWidth
        selectedOwner: backend.selectedOwner; selectedKey: backend.selected
        keyValue: (k) => k.t * panel.shot.fps
        dragClamp: (f) => Math.min(Math.max(Math.round(f), panel.shot.start), panel.shot.end + 1)
        onRowSelected: (owner) => backend.select(owner)
        onTrackScrubbed: (f) => backend.setFrame(Math.round(f))
        keyBegin: (id) => backend.beginKeyDrag(id)
        onKeyDragged: (f) => backend.keyDragTo(f)
        onKeyReleased: backend.endDrag()
    }
    Rectangle {  // the playhead line, across every row
        x: ruler.x + Math.round(ruler.xOf(backend.frame)); y: ruler.y + ruler.height
        width: 1; height: parent.height - y; color: Theme.accent; opacity: 0.8
    }
}
