import QtQuick
import RostrumKit

// Beside a play button: how playing frames are drawn (screen2d/playback.py), each shown only where it matters.
// Blur while playing: only when the composition has motion blur (full blur is slower; off plays one blur step a frame).
// (Preview size lives in the canvas view menu: ViewControls.qml.) Paused frames and exports are always the full picture.
Row {
    readonly property bool hasBlur: backend.frameInfo.blur === true
    property bool roomy: true  // false: the header has no room (LayerTimeline gives way with these first)
    visible: hasBlur && roomy
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
}
