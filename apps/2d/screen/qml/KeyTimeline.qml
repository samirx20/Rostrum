import QtQuick
import RostrumKit

// Animate page, bottom, full width: one row per layer (a summary of all its keys), opened by its arrow into one
// row per animated field. Diamonds sit at key times. Click a diamond: the key is selected (the inspector shows
// its time, value and ease). Drag it: key.set t, one gesture = one undo step; near a shared marker it lands on it.
// The ruler scrubs the playhead.
// A drawing layer's row also shows its frames (a mark per drawing, a bar for its hold); its buttons are in the header.
Panel {
    id: panel
    title: "Timeline"
    property int labelWidth: 236
    readonly property real duration: backend.frameInfo.duration
    headerRight: [
        Segmented {   // Keys: a row per layer / field; Curves: the value curves inside this same area
            anchors.verticalCenter: parent.verticalCenter; implicitHeight: 26
            options: [{ value: "keys", label: "Keys" }, { value: "curves", label: "Curves" }]
            current: backend.curves.on ? "curves" : "keys"
            onPicked: (v) => backend.curves.setOn(v === "curves")
        },
        Item { width: Theme.gap; height: 1 },
        FrameTools { anchors.verticalCenter: parent.verticalCenter },
        Item { width: Theme.gap; height: 1 },
        TimeReadout { anchors.verticalCenter: parent.verticalCenter },
        Item { width: Theme.gap; height: 1 },
        PlayButton { playing: backend.playing; onClicked: backend.togglePlay(); implicitHeight: 24; implicitWidth: 24 }
    ]

    TimeRuler {
        id: ruler
        x: panel.labelWidth + Theme.gap + 8; width: parent.width - x - Theme.gap - 8; height: 22   // 8: room for a key at 0
        duration: panel.duration; fps: backend.frameInfo.fps; time: backend.time
    }
    CurveEditor {
        visible: backend.curves.on
        ruler: ruler; labelWidth: panel.labelWidth
        anchors { left: parent.left; right: parent.right; top: ruler.bottom; bottom: parent.bottom; topMargin: Theme.grid }
    }
    KeyRows {
        visible: !backend.curves.on
        anchors { left: parent.left; right: parent.right; top: ruler.bottom; bottom: parent.bottom; topMargin: Theme.grid }
        model: backend.tracks
        ruler: ruler; labelWidth: panel.labelWidth; foldable: true
        selectedOwner: backend.selectedLayer; selectedKey: backend.selected
        trackExtras: Component { FrameMarks { frames: parent.rowData.frames; timeRuler: ruler } }   // a drawing's frames
        onRowSelected: (owner) => backend.select(owner)
        onFolded: (id) => backend.toggleTrack(id)
        onTrackScrubbed: (t) => backend.setTime(t)
        keyBegin: (id) => backend.beginKeyDrag(id)
        onKeyDragged: (t) => backend.keyDragTo(t, 6 / ruler.perSec)   // lands on a marker within 6 px
        onKeyReleased: backend.endDrag()
    }
    Repeater {   // the project's shared markers, a faint line across every row (their flags are on the ruler)
        model: backend.markers
        delegate: Rectangle {
            required property var modelData
            x: ruler.x + Math.round(ruler.xOf(modelData.at)); y: ruler.y + ruler.height
            width: 1; height: panel.height - y; color: Theme.warn; opacity: 0.35
        }
    }
    Rectangle {  // the playhead line, across every row
        x: ruler.x + Math.round(ruler.xOf(backend.time)); y: ruler.y + ruler.height
        width: 1; height: parent.height - y; color: Theme.accent; opacity: 0.8
    }
}
