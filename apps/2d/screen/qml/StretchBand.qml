import QtQuick
import RostrumKit

// One stretch on a layer's line (SPEC §9.2; LayerTrack.qml): the time between two keys of one setting, from
// screen2d/outline.py (anims.py, anim.list's one source). It carries no mark (the ease shows in the panel). Hover:
// it lights up key to key (faint blue band, blue edge, pointing hand; after a moment "Position · 1.00 → 2.00 s · Out").
// Click: the stretch is picked (solid band; its two keys blue) and its layer selected; the settings panel shows the
// animation (backend.stretch, AnimPanel.qml). Clicking the band never moves keys; the keys above it keep their own clicks.
Item {
    id: band
    objectName: "stretch:" + modelData.ids[0]       // (the scripted steps click it: stretch_steps.py)
    required property var modelData
    property Item row                                   // the LayerTrack
    property real shift: 0                              // the x of what it lies in (a layer's bar), as KeyDot's
    property real room: -1                              // the bar's width (as KeyDot's: keys at its ends stay inside)
    readonly property real x0: row.xOf(modelData.t0)
    readonly property real x1: row.xOf(modelData.t1)
    readonly property bool picked: backend.stretch.shown && backend.stretch.ids.indexOf(modelData.ids[0]) >= 0
    x: x0 - shift; width: Math.max(0, x1 - x0)
    height: Math.min(row.height - 8, parent.height - 2); y: Math.round((parent.height - height) / 2)   // inside what it lies in (a layer's slim bar)
    Rectangle {
        anchors.fill: parent; radius: 3
        visible: band.picked || area.containsMouse
        color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, band.picked ? 0.45 : 0.14)
        border.width: 1; border.color: Theme.accent
    }
    MouseArea {
        id: area
        // between its two keys' click areas (KeyDot: 16 wide, kept inside the bar at its ends), 2 px clear of each
        anchors.fill: parent
        anchors.topMargin: -Math.max(0, (18 - band.height) / 2); anchors.bottomMargin: anchors.topMargin   // a slim bar: still 18 px to click
        anchors.leftMargin: Math.max(0, band.x0 - band.shift - 8) + 18 - band.x
        anchors.rightMargin: band.x + band.width - (band.room < 0 ? band.x1 - band.shift - 8 : Math.min(band.room - 16, band.x1 - band.shift - 8)) + 2
        visible: width >= 6                       // a stretch too short to click between its keys: the keys only
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: backend.stretch.pick(band.modelData.owner, band.modelData.ids)
    }
    HoverTip { hovered: area.containsMouse; text: band.modelData.tip }
}
