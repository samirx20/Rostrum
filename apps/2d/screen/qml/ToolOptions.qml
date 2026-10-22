import QtQuick
import RostrumKit

// A tool's few options, shown by the kit's context bar in place of the selection's actions (UX_SPEC 4.3; Stage.qml
// gives it as ContextBar.toolOptions). `mode`:
//   pen    how to click, Close path, Done (backend.pen)
//   paint  the tip, Size, Colour, Opacity, Eraser (E); [ and ] size (painter.brushNow / setValue: the next stroke);
//          + Paint layer and Painting on: … ▸ (painter: what the next stroke goes on)
//   text   while typing: Font, Weight, Size, Colour, Done (backend.create.style / setStyle / done: in the typing's one change)
// The brush panel and the settings panel hold everything else.
Row {
    id: opts
    property string mode: ""
    property real room: 10000           // the bar's width to fill (Stage.qml); too narrow: Opacity gives way first (UX_SPEC
                                        // 4.3: never wraps; Size and Colour never fold), it stays in the Brush panel
    readonly property bool roomy: room >= 800
    height: Theme.button; spacing: Theme.gap
    readonly property var brush: painter.brushNow
    readonly property var look: backend.create.style
    function setBrush(name, v) { painter.setValue(name, v) }
    readonly property var weights: [{ value: 300, label: "Light" }, { value: 400, label: "Regular" }, { value: 500, label: "Medium" },
                                    { value: 600, label: "Semibold" }, { value: 700, label: "Bold" }, { value: 800, label: "Heavy" }]

    Shortcut { sequence: "E"; enabled: opts.mode === "paint"; onActivated: opts.setBrush("mode", opts.brush.mode === "erase" ? "normal" : "erase") }
    Shortcut { sequence: "["; enabled: opts.mode === "paint"; onActivated: opts.setBrush("size", Math.max(0.5, Math.round(opts.brush.size / 1.25 * 2) / 2)) }
    Shortcut { sequence: "]"; enabled: opts.mode === "paint"; onActivated: opts.setBrush("size", Math.min(2000, Math.round(opts.brush.size * 1.25 * 2) / 2)) }

    component Words: Text { anchors.verticalCenter: parent.verticalCenter; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
    component Act: Button { anchors.verticalCenter: parent.verticalCenter }

    // ---- Pen ----
    Words { visible: opts.mode === "pen"; text: backend.pen.draft.length === 0 ? "Click: corner  ·  Drag: curve" : "Click the first point to close" }
    Act { visible: opts.mode === "pen" && backend.pen.draft.length > 2; text: "Close path"; onClicked: { backend.pen.close(); backend.setTool("move") } }
    Act { visible: opts.mode === "pen"; text: "Done"; onClicked: { backend.pen.finish(); backend.setTool("move") } }

    // ---- Paint ----
    ChoiceField {
        visible: opts.mode === "paint"; anchors.verticalCenter: parent.verticalCenter; width: 92
        options: (opts.brush.tips || []).map(t => ({ value: t, label: t.charAt(0).toUpperCase() + t.slice(1) }))
        current: opts.brush.brush; onPicked: (v) => opts.setBrush("brush", v)
    }
    Words { visible: opts.mode === "paint"; text: "Size" }
    NumberField {
        visible: opts.mode === "paint"; anchors.verticalCenter: parent.verticalCenter; width: 72
        value: opts.brush.size || 0; from: 0.5; to: 2000; step: 0.5; unit: "px"
        onEdited: (v) => opts.setBrush("size", v); onScrubbed: (v) => opts.setBrush("size", v)
    }
    ColorField {
        visible: opts.mode === "paint"; anchors.verticalCenter: parent.verticalCenter; width: 96
        hex: opts.brush.color || "#ffffff"; onEdited: (v) => opts.setBrush("color", v)
    }
    Words { visible: opts.mode === "paint" && opts.roomy; text: "Opacity" }
    NumberField {
        visible: opts.mode === "paint" && opts.roomy; anchors.verticalCenter: parent.verticalCenter; width: 64
        value: opts.brush.opacity === undefined ? 1 : opts.brush.opacity; from: 0; to: 1; step: 0.01
        onEdited: (v) => opts.setBrush("opacity", v); onScrubbed: (v) => opts.setBrush("opacity", v)
    }
    Act {
        visible: opts.mode === "paint"; down: opts.brush.mode === "erase"
        text: "Eraser  E"; onClicked: opts.setBrush("mode", opts.brush.mode === "erase" ? "normal" : "erase")
    }
    Act {   // the next stroke starts a new paint layer (painter.newPaintLayer); only once the target has paint
        visible: opts.mode === "paint" && painter.canNewLayer; down: painter.newLayerNext
        text: "+ Paint layer"; onClicked: painter.newPaintLayer()
    }
    Act {   // what the strokes go on: the selected layer or a new drawing (painter.targetName / paintOn)
        id: paintingOn
        visible: opts.mode === "paint"; down: onMenu.visible
        text: "Painting on: " + painter.targetName + "  ▸"; onClicked: onMenu.visible ? onMenu.close() : onMenu.open()
        Menu { id: onMenu; entries: painter.targetChoices; onPicked: (v) => painter.paintOn(v) }
    }

    // ---- Text, while typing ----
    TextField {
        visible: opts.mode === "text"; anchors.verticalCenter: parent.verticalCenter; width: 120
        value: opts.look.font || ""; onEdited: (v) => backend.create.setStyle("font", v)
    }
    ChoiceField {
        visible: opts.mode === "text"; anchors.verticalCenter: parent.verticalCenter; width: 100
        options: opts.weights; current: opts.look.weight; onPicked: (v) => backend.create.setStyle("weight", v)
    }
    Words { visible: opts.mode === "text"; text: "Size" }
    NumberField {
        visible: opts.mode === "text"; anchors.verticalCenter: parent.verticalCenter; width: 72
        value: opts.look.size || 0; from: 1; to: 2000; step: 1; unit: "px"
        onEdited: (v) => backend.create.setStyle("size", v)
    }
    ColorField {
        visible: opts.mode === "text"; anchors.verticalCenter: parent.verticalCenter; width: 96
        hex: opts.look.color || "#ffffff"; onEdited: (v) => backend.create.setStyle("color", v)
    }
    Act { visible: opts.mode === "text"; text: "Done"; onClicked: backend.create.done() }
}
