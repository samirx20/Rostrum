import QtQuick
import RostrumKit

// The settings panel as the picked animation (SPEC §9.3, mockup 04), shown over the layer's settings while a stretch
// is picked in the timeline (backend.stretch, screen2d/stretch_select.py). On the settings grid (Theme.labelColumnFor /
// fieldFor / halfFor / wideFor): ‹ back (Esc does the same) · Move · "title · Position"; From → to, one row per number
// (from | → to); Start, Length; Easing presets four across, the chosen one lit; its curve (handles to drag where the ease
// is a cubic) and the four numbers; Reverse | Delete. Every edit is one operation call (anim.ease, key.set, key.handles).
Rectangle {
    id: panel
    readonly property var s: backend.stretch
    readonly property var info: s.info
    visible: s.shown && backend.tool !== "draw"
    color: Theme.panel; z: 2
    readonly property real w: width - Theme.padLeft - Theme.padRight
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: (e) => e.accepted = true }   // the layer's settings under it stay untouched

    component Words: Text { color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; verticalAlignment: Text.AlignVCenter }
    component Head: Words { height: Theme.row; color: Theme.fg3; font.pixelSize: Theme.label }
    component Line: Item { width: panel.w; height: Theme.row }

    SheetScroll {   // a short window (1280 × 720): the panel scrolls, never runs under the timeline
    Column {
        x: Theme.padLeft; y: Theme.gap; spacing: 0; bottomPadding: Theme.gap
        Line {   // ‹ · Move · title · Position
            IconButton { id: back; anchors.verticalCenter: parent.verticalCenter; x: -6; implicitWidth: 24; implicitHeight: 24
                         kind: "ghost"; glyph: "‹"; tip: "Back to the layer (Esc)"; onClicked: panel.s.clear() }
            Words { id: word; anchors { left: back.right; leftMargin: 4; verticalCenter: parent.verticalCenter }
                    text: panel.info.word || ""; color: Theme.fg; font.bold: true }
            Words { anchors { left: word.right; leftMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                    text: (panel.info.ownerLabel || "") + " · " + (panel.info.label || ""); color: Theme.fg3; font.pixelSize: Theme.label }
        }
        Head { text: "From → to" }
        Repeater {
            model: panel.info.rows || []
            delegate: Line {
                required property var modelData
                Words { width: Theme.labelColumnFor(panel.w); height: parent.height; text: modelData.label; elide: Text.ElideRight }
                NumberField {
                    x: Theme.labelColumnFor(panel.w); width: Theme.halfFor(panel.w); anchors.verticalCenter: parent.verticalCenter
                    visible: typeof modelData.from === "number"; value: modelData.from || 0
                    unit: modelData.unit || ""; display: modelData.display || ""; step: modelData.step || 0.01
                    onEdited: (v) => panel.s.setValue(modelData.prop, "from", v)
                }
                NumberField {
                    x: Theme.labelColumnFor(panel.w) + Theme.halfFor(panel.w) + Theme.pairGap; width: Theme.halfFor(panel.w)
                    anchors.verticalCenter: parent.verticalCenter
                    visible: typeof modelData.to === "number"; value: modelData.to || 0
                    unit: modelData.unit || ""; display: modelData.display || ""; step: modelData.step || 0.01
                    onEdited: (v) => panel.s.setValue(modelData.prop, "to", v)
                }
            }
        }
        Head { text: "Time" }
        Repeater {
            model: [{ label: "Start", key: "start" }, { label: "Length", key: "length" }]
            delegate: Line {
                required property var modelData
                Words { width: Theme.labelColumnFor(panel.w); height: parent.height; text: modelData.label }
                NumberField {
                    x: Theme.labelColumnFor(panel.w); width: Theme.fieldFor(panel.w); anchors.verticalCenter: parent.verticalCenter
                    value: panel.info[modelData.key] || 0; unit: "s"; step: 0.01; from: modelData.key === "length" ? 0.01 : 0
                    onEdited: (v) => modelData.key === "start" ? panel.s.setStart(v) : panel.s.setLength(v)
                }
            }
        }
        Head { text: "Easing" }
        Grid {   // the presets, four across
            objectName: "animPresets"
            columns: 4; spacing: 4
            readonly property real cell: (Theme.wideFor(panel.w) - 3 * spacing) / 4
            Repeater {
                model: panel.s.presets
                delegate: Rectangle {
                    required property var modelData
                    readonly property bool chosen: panel.info.preset === modelData.value
                    objectName: "preset:" + modelData.value
                    width: parent.cell; height: 40; radius: Theme.radiusCtl
                    color: chosen ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18) : presetArea.containsMouse ? Theme.raised : Theme.sunken
                    border.width: 1; border.color: chosen ? Theme.accent : Theme.border
                    Canvas {
                        width: 18; height: 10; anchors.horizontalCenter: parent.horizontalCenter; y: 7
                        property color ink: parent.chosen ? Theme.fg : Theme.fg2
                        onInkChanged: requestPaint()
                        onPaint: {
                            const c = getContext("2d"), w = width, h = height, v = parent.modelData.value
                            c.reset(); c.strokeStyle = ink; c.lineWidth = 1.3; c.beginPath(); c.moveTo(0, h)
                            if (v === "linear") c.lineTo(w, 0)
                            else if (v === "in") c.bezierCurveTo(w * 0.6, h, w, h * 0.4, w, 0)
                            else if (v === "out") c.bezierCurveTo(0, h * 0.4, w * 0.4, 0, w, 0)
                            else if (v === "smooth") c.bezierCurveTo(w * 0.5, h, w * 0.5, 0, w, 0)
                            else if (v === "spring") { c.bezierCurveTo(w * 0.2, -h * 0.6, w * 0.5, -h * 0.2, w * 0.7, h * 0.15); c.lineTo(w, 0) }
                            else if (v === "bounce") { c.lineTo(w * 0.4, 0); c.quadraticCurveTo(w * 0.55, h * 0.5, w * 0.7, 0); c.quadraticCurveTo(w * 0.85, h * 0.25, w, 0) }
                            else { c.lineTo(w * 0.7, h); c.lineTo(w * 0.7, 0); c.lineTo(w, 0) }
                            c.stroke()
                        }
                    }
                    Words { anchors.horizontalCenter: parent.horizontalCenter; y: 21; height: 14; text: modelData.label
                            font.pixelSize: Theme.label; color: parent.chosen ? Theme.fg : Theme.fg2 }
                    MouseArea { id: presetArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: panel.s.setEase(parent.modelData.value) }
                }
            }
        }
        Repeater {   // a spring: Bounce and Speed (the same key fields as the key bar's, H41), one change per drag
            model: panel.info.ease === "spring" && (panel.info.feel || []).length === 2 ? ["Bounce", "Speed"] : []
            delegate: Line {
                required property string modelData
                required property int index
                Words { width: Theme.labelColumnFor(panel.w); height: parent.height; text: modelData }
                Slider {
                    objectName: "spring" + modelData
                    x: Theme.labelColumnFor(panel.w); width: Theme.fieldFor(panel.w); anchors.verticalCenter: parent.verticalCenter
                    value: panel.info.feel[index]
                    function feelTo(v) { const f = panel.info.feel; panel.s.springTo(index === 0 ? v : f[0], index === 1 ? v : f[1]) }
                    onScrubStarted: panel.s.begin("spring")
                    onScrubbed: (v) => feelTo(v)
                    onScrubEnded: panel.s.end()
                    onEdited: (v) => { panel.s.begin("spring"); feelTo(v); panel.s.end() }
                }
            }
        }
        Item { width: 1; height: Theme.gap }
        EaseCurve {   // the curve: drag the two handles (a cubic); a spring or bounce shows its shape
            visible: panel.info.ease !== "hold"
            source: panel.s
            width: Theme.wideFor(panel.w); height: 136
        }
        Line {
            visible: (panel.info.handles || []).length === 4
            Words { width: Theme.labelColumnFor(panel.w); height: parent.height; text: "Curve" }
            Words { x: Theme.labelColumnFor(panel.w); height: parent.height; font.family: monoFont; font.pixelSize: Theme.label
                    text: (panel.info.handles || []).map(v => v.toFixed(2)).join(", ") }
        }
        Item { width: 1; height: Theme.gap }
        Line {   // Reverse | Delete: the field column's two halves
            Button { x: Theme.labelColumnFor(panel.w); width: Theme.halfFor(panel.w); anchors.verticalCenter: parent.verticalCenter
                     text: "⇄ Reverse"; help: "From and to swap"; onClicked: panel.s.reverse() }
            Button { x: Theme.labelColumnFor(panel.w) + Theme.halfFor(panel.w) + Theme.pairGap; width: Theme.halfFor(panel.w)
                     anchors.verticalCenter: parent.verticalCenter
                     text: "Delete"; help: "Removes this animation (undo brings it back)"; onClicked: panel.s.remove() }
        }
    }
    }
}
