import QtQuick
import RostrumKit

// "Paint layers +", under "Painting on" (painting design §2.3, mockup paint-02; backend.paintLayers). One paint layer:
// only the heading line with its +. Two or more: the list, top first, each row eye · thumbnail · name, in grey its blend
// and opacity when not Normal · 100 %, a lock when locked. Click a row: strokes and fills go on it (blue); drag:
// reorder; double-click: rename; right-click: Hide, Lock, Rename, Duplicate, Delete. Under the list the highlighted layer's
// Blend, Opacity and Lock. Absent until what the pen paints on holds paint.
Column {
    id: po
    readonly property var pl: backend.paintLayers
    readonly property var cur: { for (const l of pl.layers) if (l.current) return l; return null }
    width: parent ? parent.width : 0
    readonly property int labelColumn: Theme.labelColumnFor(width)     // the settings rows' own column and field width
    readonly property real wide: Theme.wideFor(width)
    visible: pl.canAdd

    component Label: Text {
        width: po.labelColumn - Theme.gap; anchors.verticalCenter: parent.verticalCenter
        color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont; elide: Text.ElideRight
    }
    component Line: Item { width: po.width; height: Theme.row }

    Item {      // the heading: "Paint layers" and its + at the row's end
        width: po.width; height: Theme.groupGap + Theme.rowDense
        Text { anchors.left: parent.left; anchors.verticalCenter: plus.verticalCenter
               text: "Paint layers"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
        IconButton { id: plus; objectName: "paintLayerAdd"; x: po.wide - width; anchors.bottom: parent.bottom
                     width: Theme.field; height: Theme.field; kind: "ghost"; glyph: "+"
                     tip: "Add paint layer"; help: "A new paint layer on top; the next stroke goes into it"
                     onClicked: po.pl.add() }
    }
    Repeater {      // the paint layers, top first
        id: layerRows
        model: po.pl.layers
        delegate: Rectangle {
            id: lr
            required property var modelData
            required property int index
            objectName: "paintLayer:" + modelData.name.replace(/ /g, "_")     // (a walk's clickobj: _ for spaces)
            property bool renaming: false
            width: po.wide; height: Theme.row; radius: Theme.radiusCtl
            color: modelData.current ? Theme.accentSoft : rowArea.containsMouse ? Theme.hover : "transparent"
            border.width: modelData.current ? 1 : 0; border.color: Theme.accent
            z: rowArea.moving ? 2 : 0
            Item {      // the eye (the layers panel's own; crossed out when hidden)
                id: eye
                objectName: "paintEye:" + lr.modelData.name.replace(/ /g, "_")     // (a walk's clickname: _ for spaces)
                x: Theme.grid; width: 18; height: parent.height
                LayerSwitchIcon { anchors.centerIn: parent; kind: "hidden"; on: !lr.modelData.visible; hot: eyeArea.containsMouse }
                MouseArea { id: eyeArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: po.pl.setLayer(lr.modelData.id, "visible", !lr.modelData.visible) }
                HoverTip { hovered: eyeArea.containsMouse; text: lr.modelData.visible ? "Hide" : "Show" }
            }
            Item {          // the thumbnail: the layer's own paint on a mid-grey checker, so ink of any colour reads
                id: thumb
                anchors.left: eye.right; anchors.leftMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter
                width: Theme.field - 2; height: width
                opacity: lr.modelData.visible ? 1 : 0.4
                Checker { anchors.fill: parent; radius: 3; cell: 4; light: "#7a7a7a"; dark: "#5a5a5a" }
                Image { anchors.fill: parent; source: lr.modelData.thumb; fillMode: Image.PreserveAspectFit
                        smooth: true; cache: false }
            }
            Text {
                id: nameText
                visible: !lr.renaming
                anchors.left: thumb.right; anchors.leftMargin: Theme.grid + 2
                anchors.right: note.left; anchors.rightMargin: Theme.gap
                anchors.verticalCenter: parent.verticalCenter
                text: lr.modelData.name; color: lr.modelData.visible ? Theme.fg : Theme.fg3
                font.pixelSize: Theme.body; font.family: uiFont; elide: Text.ElideRight
            }
            Text {      // its blend and opacity, only when not Normal · 100 % and the whole name fits beside it (a name is
                        // never cut for a note: the highlighted layer's Blend and Opacity rows say it anyway)
                id: note
                readonly property real room: lock.x - thumb.x - thumb.width - 2 * Theme.grid - 2 - 2 * Theme.gap
                anchors.right: lock.left; anchors.rightMargin: lock.visible ? Theme.grid : Theme.gap
                anchors.verticalCenter: parent.verticalCenter
                width: visible ? implicitWidth : 0
                visible: lr.modelData.note !== "" && nameText.implicitWidth + implicitWidth <= room
                text: lr.modelData.note; color: Theme.fg3; font.pixelSize: Theme.label; font.family: uiFont
            }
            Item {      // a lock when locked (click: unlock)
                id: lock
                visible: lr.modelData.locked
                anchors.right: parent.right; anchors.rightMargin: Theme.grid
                width: visible ? 18 : 0; height: parent.height
                LayerSwitchIcon { anchors.centerIn: parent; kind: "locked"; on: true; hot: lockArea.containsMouse }
                MouseArea { id: lockArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: po.pl.setLayer(lr.modelData.id, "locked", false) }
                HoverTip { hovered: lockArea.containsMouse; text: "Unlock" }
            }
            MouseArea {     // click: strokes go on it; drag up or down: reorder (drop on another row's place)
                id: rowArea
                anchors.left: thumb.left; anchors.right: note.right; anchors.top: parent.top; anchors.bottom: parent.bottom
                hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
                preventStealing: true; enabled: !lr.renaming
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
                onDoubleClicked: (ev) => { if (ev.button === Qt.LeftButton) lr.startRename() }
                onCanceled: { moving = false; dy = 0 }
            }
            HoverTip { hovered: rowArea.containsMouse && !rowArea.moving && nameText.truncated; text: lr.modelData.name }
            TextInput {     // rename in place: Enter keeps it, Esc or a click elsewhere leaves the name as it was
                id: nameEdit
                visible: lr.renaming
                anchors.left: nameText.left; anchors.right: nameText.right; anchors.verticalCenter: parent.verticalCenter
                color: Theme.fg; selectionColor: Theme.accent; font.pixelSize: Theme.body; font.family: uiFont
                onAccepted: { lr.renaming = false; if (text.trim() && text !== lr.modelData.name) po.pl.setLayer(lr.modelData.id, "name", text.trim()) }
                Keys.onEscapePressed: lr.renaming = false
                onActiveFocusChanged: if (!activeFocus) lr.renaming = false
            }
            function startRename() { nameEdit.text = modelData.name; renaming = true; nameEdit.forceActiveFocus(); nameEdit.selectAll() }
            transform: Translate { y: rowArea.moving ? rowArea.dy : 0 }
            Menu { id: rowMenu; y: lr.height
                   entries: [{ value: "visible", label: lr.modelData.visible ? "Hide" : "Show" },
                             { value: "locked", label: lr.modelData.locked ? "Unlock" : "Lock" },
                             { value: "rename", label: "Rename" }, { value: "duplicate", label: "Duplicate" },
                             { value: "delete", label: "Delete" }]
                   onPicked: (v) => v === "delete" ? po.pl.remove(lr.modelData.id)
                                  : v === "duplicate" ? po.pl.duplicate(lr.modelData.id)
                                  : v === "rename" ? lr.startRename()
                                  : po.pl.setLayer(lr.modelData.id, v, !lr.modelData[v]) }
        }
    }
    Line {      // the highlighted layer's own rows
        visible: po.cur !== null
        Label { text: "Blend" }
        ChoiceField {
            objectName: "paintLayerBlend"
            x: po.labelColumn; width: parent.width - po.labelColumn - Theme.keyGutter; anchors.verticalCenter: parent.verticalCenter
            options: po.pl.modes; current: po.cur ? po.cur.mode : "normal"
            onPicked: (v) => po.pl.setLayer(po.cur.id, "mode", v)
        }
    }
    Line {
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
        Label { text: "Lock" }
        Toggle { x: po.labelColumn; anchors.verticalCenter: parent.verticalCenter; checked: po.cur ? po.cur.locked : false
                 onToggled: (v) => po.pl.setLayer(po.cur.id, "locked", v) }
        HoverHandler { id: lockHover }
        HoverTip { hovered: lockHover.hovered; text: "A locked layer refuses paint and fill" }
    }
}
