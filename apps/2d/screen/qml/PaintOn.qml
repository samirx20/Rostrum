import QtQuick
import RostrumKit

// The settings panel's paint layers group, under "Painting on" (PaintTarget.qml; backend.paintLayers).
// The paint layers, top first: the eye, the name (click: strokes and fills go on it; drag: reorder; right-click ›
// Delete); under the list the highlighted layer's Opacity and Blend; then Onion skin while drawing each frame.
// Absent until what the pen paints on holds paint.
Column {
    id: po
    readonly property var pl: backend.paintLayers
    readonly property var cur: { for (const l of pl.layers) if (l.current) return l; return null }
    width: parent ? parent.width : 0
    readonly property int labelColumn: Theme.labelColumnFor(width)     // the settings rows' own column and field width
    visible: pl.title !== ""

    component Label: Text {
        width: po.labelColumn - Theme.gap; anchors.verticalCenter: parent.verticalCenter
        color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont; elide: Text.ElideRight
    }
    component Line: Item { width: po.width; height: Theme.row }

    Item { width: po.width; height: Theme.gap }     // no heading: the bar already says what the brush paints on
    Repeater {      // the paint layers, top first
        id: layerRows
        model: po.pl.layers
        delegate: Rectangle {
            id: lr
            required property var modelData
            required property int index
            width: po.width; height: Theme.rowDense; radius: Theme.radiusCtl
            color: modelData.current ? Theme.accentSoft : rowArea.containsMouse ? Theme.hover : "transparent"
            z: rowArea.moving ? 2 : 0
            Item {      // the eye (the layers panel's own; crossed out when hidden)
                id: eye
                x: Theme.grid; width: 18; height: parent.height
                LayerSwitchIcon { anchors.centerIn: parent; kind: "hidden"; on: !lr.modelData.visible; hot: eyeArea.containsMouse }
                MouseArea { id: eyeArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: po.pl.setLayer(lr.modelData.id, "visible", !lr.modelData.visible) }
                HoverTip { hovered: eyeArea.containsMouse; text: lr.modelData.visible ? "Hide" : "Show" }
            }
            Text {
                id: nameText
                anchors.left: eye.right; anchors.leftMargin: Theme.grid; anchors.right: parent.right; anchors.rightMargin: Theme.gap
                anchors.verticalCenter: parent.verticalCenter
                text: lr.modelData.name; color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont; elide: Text.ElideRight
            }
            MouseArea {     // click: strokes go on it; drag up or down: reorder (drop on another row's place)
                id: rowArea
                anchors.fill: nameText; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
                preventStealing: true
                property real y0: 0
                property real dy: 0
                property bool moving: false
                onPressed: (ev) => { y0 = mapToItem(po, ev.x, ev.y).y; dy = 0; moving = false }
                onPositionChanged: (ev) => {
                    if (!pressed || pressedButtons !== Qt.LeftButton) return
                    dy = mapToItem(po, ev.x, ev.y).y - y0
                    if (Math.abs(dy) > 4) moving = true
                }
                onReleased: (ev) => {
                    if (ev.button === Qt.RightButton) { rowMenu.open(); return }
                    if (!moving) { po.pl.pick(lr.modelData.id); return }
                    const to = Math.max(0, Math.min(layerRows.count - 1, lr.index + Math.round(dy / lr.height)))
                    moving = false; dy = 0
                    if (to !== lr.index) po.pl.moveTo(lr.modelData.id, to)
                }
                onCanceled: { moving = false; dy = 0 }
            }
            HoverTip { hovered: rowArea.containsMouse && !rowArea.moving && nameText.truncated; text: lr.modelData.name }
            transform: Translate { y: rowArea.moving ? rowArea.dy : 0 }
            Menu { id: rowMenu; y: lr.height; entries: [{ value: "delete", label: "Delete" }]
                   onPicked: (v) => po.pl.remove(lr.modelData.id) }
        }
    }
    Line {      // the highlighted layer's opacity and blend
        visible: po.cur !== null
        Label { text: "Opacity" }
        NumberField {
            x: po.labelColumn; width: parent.width - po.labelColumn - Theme.keyGutter; anchors.verticalCenter: parent.verticalCenter
            value: po.cur ? po.cur.opacity : 1; from: 0; to: 1; step: 0.01; display: "percent"
            onEdited: (v) => po.pl.setLayer(po.cur.id, "opacity", v)
            onScrubStarted: po.pl.beginScrub(po.cur.id); onScrubbed: (v) => po.pl.scrub(v); onScrubEnded: po.pl.endScrub()
        }
    }
    Line {
        visible: po.cur !== null
        Label { text: "Blend" }
        ChoiceField {
            x: po.labelColumn; width: parent.width - po.labelColumn - Theme.keyGutter; anchors.verticalCenter: parent.verticalCenter
            options: po.pl.modes; current: po.cur ? po.cur.mode : "normal"
            onPicked: (v) => po.pl.setLayer(po.cur.id, "mode", v)
        }
    }
    Line {
        visible: po.pl.onionApplies
        Label { text: "Onion skin" }
        Toggle { x: po.labelColumn; anchors.verticalCenter: parent.verticalCenter; checked: painter.onionOn
                 onToggled: (v) => painter.setOnion(v) }
    }
}
