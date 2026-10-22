import QtQuick
import "."

// The timeline's header (INTERACTION.md 1.6 › Header), left to right: the transport slot (▶ / ■, the time, ⟳ Loop),
// the timeline's own context (the key bar, frame tools), and on the right the view slot (◇ Marker, snap, zoom − +
// and fit) and ⊟, which folds the timeline between full and compact (foldClicked; the app keeps the height).
// The app fills the slots with its own controls; the header lays them out:
//   TimelineHeader { transport: [PlayButton {…}, …]; context: [...]; view: [...]; compact: … }
// When the window is too narrow for all three, the context slot gives way first (contextFolded true: the app shows
// those actions in its ⋯ menu instead); transport, view and ⊟ always stay. Nothing is greyed out: a control the
// app can't use now is left out of its slot.
Item {
    id: h
    property alias transport: transportRow.data
    property alias context: contextRow.data
    property alias view: viewRow.data
    property bool compact: false          // the timeline is folded (⊟ shows "Full timeline")
    property bool foldable: true
    readonly property bool contextFolded: !contextRow.visible && contextRow.implicitWidth > 0
    signal foldClicked()
    implicitHeight: Theme.header

    Row {
        id: transportRow
        x: Theme.pad; anchors.verticalCenter: parent.verticalCenter; spacing: Theme.gap
    }
    Row {
        id: contextRow
        x: transportRow.x + transportRow.width + Theme.groupGap; anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.gap
        visible: x + implicitWidth + Theme.groupGap <= rightSide.x
    }
    Row {
        id: rightSide
        anchors.right: parent.right; anchors.rightMargin: Theme.pad; anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.gap
        Row { id: viewRow; anchors.verticalCenter: parent.verticalCenter; spacing: Theme.gap }
        IconButton {
            visible: h.foldable; anchors.verticalCenter: parent.verticalCenter
            kind: "ghost"; glyph: "⊟"; implicitWidth: 24; implicitHeight: 24
            tip: h.compact ? "Full timeline" : "Compact timeline"
            help: h.compact ? "Show every row again." : "Keep only the header, the ruler, the sound row and the selected row."
            onClicked: h.foldClicked()
        }
    }
}
