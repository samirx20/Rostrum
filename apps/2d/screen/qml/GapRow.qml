import QtQuick
import RostrumKit

// The Gap row (2d-pro-workflows SPEC 3.10), at the top of the settings with 3+ layers picked that already sit equally
// apart along an axis ("Gap ⟷ 48 px" across, "Gap ↕" down; backend.multi.gap); absent when their gaps differ (then
// the Distribute buttons even them). A number box like any other (a sum, +20, *2): a typed or scrubbed gap re-spaces
// them from the first (leftmost or topmost) one through layer.distribute {gap}, one change.
Column {
    id: row
    readonly property var g: backend.multi.gap
    readonly property real full: parent ? parent.width : 0
    visible: g.axis !== undefined
    width: full
    Item {
        width: Theme.wideFor(row.full); height: Theme.row
        Text {
            width: Theme.labelColumnFor(row.full); height: Theme.row; verticalAlignment: Text.AlignVCenter
            text: row.g.axis === "y" ? "Gap ↕" : "Gap ⟷"
            color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
        }
        NumberField {
            objectName: "gapBox"
            x: Theme.labelColumnFor(row.full); width: Theme.fieldFor(row.full); anchors.verticalCenter: parent.verticalCenter
            value: row.g.gap || 0; unit: " px"; label: "Gap"; relative: true
            onEdited: (v) => backend.multi.setGap(v)
            onEditedRelative: (by, factor) => backend.multi.setGap(value * factor + by)
            onScrubStarted: backend.multi.beginGap()
            onScrubbed: (v) => backend.multi.gapTo(v)
            onScrubEnded: backend.multi.endGap()
        }
    }
    Item {  // the end of the group: a line and a group's gap
        width: Theme.wideFor(row.full); height: Theme.groupGap
        Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 1; color: Theme.line }
    }
}
