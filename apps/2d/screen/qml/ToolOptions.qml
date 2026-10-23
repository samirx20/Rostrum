import QtQuick
import RostrumKit

// A tool's few options, shown by the kit's context bar in place of the selection's actions (UX_SPEC 4.3; Stage.qml
// gives it as ContextBar.toolOptions). `mode`:
//   pen    how to click (backend.pen; click the first point, Enter / Esc or another tool ends the path: no Done)
//   paint  PaintOptions.qml: the brush's bar settings (the painting kit's placement table), Eraser (E), Fill (G),
//          + Paint layer and Painting on: … ▸
//   text   while typing: Font, Weight, Size, Colour (backend.create.style / setStyle: in the typing's one change;
//          a click outside, Esc or Ctrl+Enter ends it: no Done)
// The settings panel holds everything else.
Row {
    id: opts
    property string mode: ""
    property real room: 10000           // the bar's width to fill (Stage.qml); too narrow: PaintOptions folds into its ⋯
    height: Theme.button; spacing: Theme.gap
    readonly property var look: backend.create.style
    readonly property var weights: [{ value: 300, label: "Light" }, { value: 400, label: "Regular" }, { value: 500, label: "Medium" },
                                    { value: 600, label: "Semibold" }, { value: 700, label: "Bold" }, { value: 800, label: "Heavy" }]

    component Words: Text { anchors.verticalCenter: parent.verticalCenter; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }

    // ---- Pen ----
    Words { visible: opts.mode === "pen"; text: backend.pen.draft.length === 0 ? "Click: corner  ·  Drag: curve" : "Click the first point to close  ·  Enter to finish" }

    // ---- Paint (PaintOptions.qml: the brush's bar settings, Eraser, Fill, + Paint layer, Painting on) ----
    PaintOptions { visible: opts.mode === "paint" && backend.strokeSelect.count === 0; room: opts.room; anchors.verticalCenter: parent.verticalCenter }
    StrokeBar { visible: opts.mode === "paint" && backend.strokeSelect.count > 0; anchors.verticalCenter: parent.verticalCenter }   // strokes picked: what applies to them

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
}
