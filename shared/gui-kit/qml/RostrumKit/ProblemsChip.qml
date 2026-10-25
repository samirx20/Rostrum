import QtQuick
import QtQuick.Controls as QQC
import "."

// The Problems chip in the top bar (INTERACTION.md 1.14, 1.15): "2 problems", only while something is wrong. Click:
// the list, each in words with what to do; click one to select the thing and jump to its moment (the app's
// `source.jump(row)`). `narrow`: the dot and the count.
// `source`: an object with `rows` [{label, message, fix, item, kind?, danger?, action?, options?}] and a `jump(row)` slot;
// a row with `action` (a word) and `options` shows a picker saying it, and a pick calls `source.act(row, value)`.
Rectangle {
    id: chip
    property var source
    property bool narrow: false
    readonly property var rows: source ? source.rows : []
    readonly property int n: rows ? rows.length : 0
    readonly property bool danger: n > 0 && rows.some(r => !!r.danger)
    readonly property string words: n + (n === 1 ? " problem" : " problems")
    readonly property real fullWidth: n > 0 ? full.implicitWidth + 2 * Theme.gap : 0
    readonly property real narrowWidth: n > 0 ? small.implicitWidth + 2 * Theme.gap : 0
    function openList() { pop.open() }
    function closeList() { pop.close() }
    objectName: "problemsChip"
    visible: n > 0
    implicitWidth: n > 0 ? (narrow ? narrowWidth : fullWidth) : 0
    implicitHeight: Theme.button
    radius: Theme.radiusCtl
    color: hover.hovered || pop.opened ? Theme.hover : Theme.raised
    clip: true

    component Dot: Rectangle {
        width: 8; height: 8; radius: 4; color: chip.danger ? Theme.danger : Theme.warn
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
    }
    Row {
        id: full
        x: Theme.gap; height: parent.height; spacing: Theme.gap
        opacity: chip.narrow ? 0 : 1
        Dot { }
        Text { anchors.verticalCenter: parent.verticalCenter; text: chip.words
               color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label }
    }
    Row {
        id: small
        x: Theme.gap; height: parent.height; spacing: Theme.grid + 2
        opacity: chip.narrow ? 1 : 0
        Dot { }
        Text { anchors.verticalCenter: parent.verticalCenter; text: String(chip.n)
               color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label }
    }
    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { onTapped: pop.opened ? pop.close() : pop.open() }
    HoverTip { text: chip.narrow ? chip.words : ""; hovered: hover.hovered && !pop.opened }

    SmallPopup {
        id: pop
        objectName: "problemsPopup"
        y: chip.height + Theme.grid
        x: Math.min(0, chip.width - width)          // under the chip, its right edge on the chip's
        width: 360
        padding: Theme.gap
        background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
        contentItem: ListView {
            id: list
            implicitHeight: Math.min(contentHeight, 420)
            clip: true; spacing: Theme.grid
            boundsBehavior: Flickable.StopAtBounds
            model: chip.rows
            delegate: Rectangle {
                id: row
                required property var modelData
                width: list.width
                height: body.implicitHeight + 2 * Theme.gap
                radius: Theme.radiusCtl
                color: rowHover.hovered ? Theme.hover : "transparent"
                Column {
                    id: body
                    x: Theme.gap; y: Theme.gap; width: parent.width - 2 * Theme.gap
                    spacing: 2
                    Text { width: parent.width; text: row.modelData.label || ""; elide: Text.ElideRight
                           color: row.modelData.danger ? Theme.danger : Theme.warn
                           font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
                    Text { width: parent.width; text: row.modelData.message || ""; wrapMode: Text.Wrap
                           color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
                    Text { width: parent.width; visible: !!row.modelData.fix; text: row.modelData.fix || ""; wrapMode: Text.Wrap
                           color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                    ChoiceField {   // a problem with its own picker (a missing font: "Use another font"): one pick fixes them all
                        id: pick
                        objectName: "problemPick"
                        visible: !!row.modelData.action; width: parent.width
                        height: visible ? implicitHeight : 0
                        options: row.modelData.options || []; current: row.modelData.action || ""
                        onPicked: v => { pop.close(); chip.source.act(row.modelData, String(v)) }
                    }
                }
                HoverHandler { id: rowHover; cursorShape: Qt.PointingHandCursor }
                TapHandler {
                    onTapped: {
                        if (pick.visible && pick.contains(pick.mapFromItem(row, point.position.x, point.position.y))) return   // the picker's own click
                        pop.close(); chip.source.jump(row.modelData)
                    }
                }
            }
        }
    }
}
