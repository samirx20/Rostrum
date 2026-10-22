import QtQuick
import "."

// The body of a sheet that may be taller than its window (Lip sync, Add blinks at 1280×720): fills the panel's body,
// scrolls by wheel or touch with the thin bar in the margin; a short one never moves. Children go into one column.
Item {
    id: scroll
    default property alias content: column.data
    property alias spacing: column.spacing
    anchors.fill: parent
    Flickable {
        id: flick
        anchors.fill: parent
        contentHeight: column.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        Column { id: column; width: flick.width }
    }
    EdgeFade { flick: flick; anchors.fill: flick }
    VScrollBar { flick: flick }
}
