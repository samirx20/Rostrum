import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Draw's part of the context bar (UX_SPEC 3.8, 4.3): the few brush settings changed while painting, then Eraser (E),
// Fill (G), + Paint layer and Painting on ▸. Which settings: `painter.brushNow.bar`, from the painting kit's own
// placement table (rostrum_paint.fields.BAR), the one the settings panel reads to leave them out: nothing shows twice.
// With Fill on: the settings a fill has (Colour, Opacity), Close gaps, and the clicks fill (backend.fill).
// Too narrow (`room`): Opacity, then Eraser, then Fill fold into the bar's own ⋯ (never into the panel; Size and
// Colour never fold; the bar never wraps).
Row {
    id: po
    property real room: 10000
    spacing: Theme.gap
    readonly property var brush: painter.brushNow
    readonly property bool filling: backend.fill.on
    readonly property var fields: (filling ? brush.fillBar : brush.bar) || []
    readonly property bool erasing: brush.mode === "erase"
    function set(name, v) { painter.setValue(name, v) }
    function toggleErase() { set("mode", erasing ? "normal" : "erase") }

    // ---- folding: how many of Opacity, Eraser, Fill go under ⋯ ----
    function fieldW(f) { return f.type === "choice" ? 92 : f.type === "color" ? 96 : 72 + 7 * f.label.length + Theme.gap }
    readonly property real opacityW: fieldW({ type: "number", label: "Opacity" })
    readonly property real fullW: {
        let w = 0
        for (const f of fields) w += fieldW(f) + spacing
        if (!filling) w += eraser.implicitWidth + spacing
        if (fillBtn.can) w += fillBtn.implicitWidth + spacing
        if (filling) w += gaps.implicitWidth + spacing
        if (painter.canNewLayer) w += newLayer.implicitWidth + spacing
        if (!filling) w += selectBtn.implicitWidth + spacing
        return w + paintingOn.implicitWidth
    }
    readonly property int fold: {
        const more = Theme.button + spacing
        const cuts = [opacityW + spacing, filling ? 0 : eraser.implicitWidth + spacing, fillBtn.implicitWidth + spacing,
                      filling ? 0 : selectBtn.implicitWidth + spacing]
        let w = fullW, k = 0
        while (k < cuts.length && w > room) { w -= cuts[k]; if (k === 0) w += more; k++ }
        return k
    }
    function folded(id) { return id === "opacity" ? fold >= 1 : id === "eraser" ? fold >= 2 : id === "fill" ? fold >= 3 : id === "select" ? fold >= 4 : false }

    Shortcut { sequence: "E"; enabled: po.visible && !po.filling; onActivated: po.toggleErase() }
    Shortcut { sequence: "G"; enabled: po.visible && fillBtn.can; onActivated: backend.fill.setOn(!po.filling) }
    Shortcut { sequence: "["; enabled: po.visible && !po.filling; onActivated: po.set("size", Math.max(0.5, Math.round(po.brush.size / 1.25 * 2) / 2)) }
    Shortcut { sequence: "]"; enabled: po.visible && !po.filling; onActivated: po.set("size", Math.min(2000, Math.round(po.brush.size * 1.25 * 2) / 2)) }

    component Words: Text { anchors.verticalCenter: parent.verticalCenter; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
    component Act: Button { anchors.verticalCenter: parent.verticalCenter }
    component Field: Row {      // one brush setting by its type (the bar's list and the ⋯ popup use the same)
        id: fld
        required property var modelData
        spacing: Theme.gap
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        Words { visible: fld.modelData.type === "number"; text: fld.modelData.label }
        Loader {
            anchors.verticalCenter: parent.verticalCenter
            sourceComponent: ({ choice: choiceW, number: numberW, color: colourW })[fld.modelData.type] || null
            Component { id: choiceW; ChoiceField {
                width: 92; options: fld.modelData.options || []; current: fld.modelData.value
                onPicked: (v) => po.set(fld.modelData.id, v) } }
            Component { id: numberW; NumberField {
                width: 72; value: fld.modelData.value; from: fld.modelData.min; to: fld.modelData.max; step: fld.modelData.step
                unit: fld.modelData.unit || ""
                onEdited: (v) => po.set(fld.modelData.id, v); onScrubbed: (v) => po.set(fld.modelData.id, v) } }
            Component { id: colourW; ColorField {
                width: 96; hex: fld.modelData.value; onEdited: (v) => po.set(fld.modelData.id, v) } }
        }
    }

    Repeater { model: po.fields.filter(f => !po.folded(f.id)); delegate: Field { } }
    Act { id: eraser; visible: !po.filling && !po.folded("eraser"); down: po.erasing; text: "Eraser  E"; onClicked: po.toggleErase() }
    Act {   // Fill: only on something already painted (it fills between lines)
        id: fillBtn
        readonly property bool can: painter.canNewLayer
        visible: can && !po.folded("fill"); down: po.filling; text: "Fill  G"; onClicked: backend.fill.setOn(!po.filling)
    }
    Segmented {
        id: gaps
        visible: po.filling; anchors.verticalCenter: parent.verticalCenter
        options: backend.fill.gaps; current: backend.fill.gap; onPicked: (v) => backend.fill.setGap(v)
        HoverHandler { id: gapHover }
        HoverTip { hovered: gapHover.hovered; text: "Close gaps: lines this far apart still close the area" }
    }
    Act {   // the next stroke or fill starts a new paint layer (painter.newPaintLayer); only once the target has paint
        id: newLayer
        visible: painter.canNewLayer; down: painter.newLayerNext
        text: "+ Paint layer"; onClicked: painter.newPaintLayer()
    }
    Act {   // the next drag is a lasso round strokes (Ctrl+drag does the same): backend.strokeSelect
        id: selectBtn
        visible: !po.filling && !po.folded("select"); down: backend.strokeSelect.armed
        text: "Select strokes"; onClicked: backend.strokeSelect.arm(!backend.strokeSelect.armed)
    }
    Act {   // what the strokes go on: the selected layer or a new drawing (painter.targetName / paintOn)
        id: paintingOn
        down: onMenu.visible
        // a long name is shortened here (the whole name shows on hover): the bar never wraps or cuts (UX_SPEC 4.3)
        readonly property string name: painter.targetName
        readonly property int most: po.room >= 800 ? 24 : 10
        text: "Painting on: " + (name.length > most ? name.slice(0, most - 1) + "…" : name) + "  ▸"
        onClicked: onMenu.visible ? onMenu.close() : onMenu.open()
        HoverHandler { id: onHover }
        HoverTip { hovered: onHover.hovered && paintingOn.name.length > paintingOn.most; text: "Painting on " + paintingOn.name }
        Menu { id: onMenu; entries: painter.targetChoices; onPicked: (v) => painter.paintOn(v) }
    }
    IconButton {    // the bar's own ⋯: what folded away, in the same order
        visible: po.fold > 0; glyph: "⋯"; tip: "More"; anchors.verticalCenter: parent.verticalCenter
        down: more.visible; onClicked: more.visible ? more.close() : more.open()
        QQC.Popup {
            id: more
            y: parent.height + 4; x: parent.width - width
            padding: Theme.gap
            background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
            contentItem: Row {
                spacing: Theme.gap
                Repeater { model: po.fields.filter(f => po.folded(f.id)); delegate: Field { } }
                Act { visible: !po.filling && po.folded("eraser"); down: po.erasing; text: "Eraser  E"; onClicked: po.toggleErase() }
                Act { visible: fillBtn.can && po.folded("fill"); down: po.filling; text: "Fill  G"; onClicked: backend.fill.setOn(!po.filling) }
                Act { visible: !po.filling && po.folded("select"); down: backend.strokeSelect.armed; text: "Select strokes"; onClicked: backend.strokeSelect.arm(!backend.strokeSelect.armed) }
            }
        }
    }
}
