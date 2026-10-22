import QtQuick
import RostrumKit

// Beside a play button: how playing frames are drawn (screen2d/playback.py), each shown only where it matters.
// Blur while playing: only when the composition has motion blur (full blur is slower; off plays one blur step a frame).
// Preview size: only for a large composition (playback.py SIZE_FROM), where a full frame can take longer than a frame.
// Paused frames and exports are always the full picture.
Row {
    readonly property bool hasBlur: backend.frameInfo.blur === true
    readonly property bool hasSize: backend.frameInfo.previewSize === true
    property bool roomy: true  // false: the header has no room (LayerTimeline gives way with these first)
    visible: (hasBlur || hasSize) && roomy
    spacing: Theme.gap         // a label to its control; groups get Theme.pad more (below)
    // its width when laid out (kept while hidden, which may measure 0), so the header can ask whether it fits
    property real shownWidth: 0
    onWidthChanged: if (width > 0) shownWidth = width

    Text {
        visible: hasBlur; anchors.verticalCenter: parent.verticalCenter
        text: "Blur while playing"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
    }
    Toggle {
        id: sw
        visible: hasBlur; anchors.verticalCenter: parent.verticalCenter
        checked: backend.playback.blur
        onToggled: (v) => backend.playback.setBlur(v)
        HoverTip {
            hovered: sw.hovered
            text: sw.checked ? "Plays with full motion blur: true to the export, but slower"
                             : "Plays with one blur step per frame so it keeps up; paused frames and exports have full blur"
        }
    }
    Item { visible: hasBlur && hasSize; width: Theme.pad; height: 1 }
    Text {
        visible: hasSize; anchors.verticalCenter: parent.verticalCenter
        text: "Preview size"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
    }
    Segmented {
        id: size
        visible: hasSize; anchors.verticalCenter: parent.verticalCenter; implicitHeight: 26
        options: [{ value: "full", label: "Full" }, { value: "half", label: "Half" }, { value: "quarter", label: "Quarter" }]
        current: backend.playback.size
        onPicked: (v) => backend.playback.setSize(v)
        HoverHandler { id: sizeHover }
        HoverTip {
            hovered: sizeHover.hovered
            text: "How big frames are drawn while playing: smaller plays smoother. Paused frames and exports are always full size"
        }
    }
}
