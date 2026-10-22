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
    Rectangle {   // "Full ▾": the size's menu, its name on hover
        id: size
        visible: hasSize; anchors.verticalCenter: parent.verticalCenter
        readonly property var sizes: [{ value: "full", label: "Full" }, { value: "half", label: "Half" }, { value: "quarter", label: "Quarter" }]
        implicitWidth: sizeText.implicitWidth + 2 * Theme.gap; implicitHeight: 26
        radius: Theme.radiusCtl; color: sizeHover.hovered ? Theme.hover : "transparent"
        Text { id: sizeText; anchors.centerIn: parent; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
               text: (size.sizes.find(o => o.value === backend.playback.size) || size.sizes[0]).label + " ▾" }
        HoverHandler { id: sizeHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: sizeMenu.open() }
        HoverTip {
            hovered: sizeHover.hovered && !sizeMenu.opened
            text: "Preview size: how big frames are drawn while playing. Paused frames and exports are always full size"
        }
        Menu {
            id: sizeMenu
            y: size.height + 2; width: 110
            entries: size.sizes
            onPicked: (v) => backend.playback.setSize(v)
        }
    }
}
