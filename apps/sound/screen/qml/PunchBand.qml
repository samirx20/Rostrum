import QtQuick
import RostrumKit

// The punch range (the take panel's From / To) shaded across the rows: only that part of the next take is kept.
// Absent unless a track is armed with punch on.
Rectangle {
    property var ruler                     // the BarRuler the rows are drawn against
    readonly property var range: typeof takeSetup !== "undefined" ? takeSetup.punchRange : []
    visible: range.length === 2
    x: visible ? ruler.x + Math.round(ruler.xOf(range[0])) : 0
    width: visible ? Math.max(1, Math.round(ruler.xOf(range[1]) - ruler.xOf(range[0]))) : 0
    color: Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.1)
    border.width: 1; border.color: Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.6)
}
