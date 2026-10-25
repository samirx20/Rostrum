import QtQuick
import RostrumKit

// The settings panel as the picked animation (SPEC §9.3, mockup 04), shown over the layer's settings while a stretch
// is picked in the timeline (backend.stretch, screen2d/stretch_select.py). On the settings grid (Theme.labelColumnFor /
// fieldFor / halfFor / wideFor): ‹ back (Esc does the same) · Move · "title · Position"; one row per number (from | to);
// Start, Length; Ease (the kit's one EasePicker: the current ease's curve and name, the same list as the Key block's); its curve
// (handles to drag where the ease is a cubic) and the four numbers; Reverse | Delete. No headings over the groups: each
// field says what it is (a gap parts them). Every edit is one operation call (anim.ease, key.set, key.handles).
Rectangle {
    id: panel
    readonly property var s: backend.stretch
    readonly property var info: s.info
    property bool allowed: true                 // the app may hide it (2D: while drawing)
    visible: s.shown && allowed
    color: Theme.panel; z: 2
    readonly property real w: width - Theme.padLeft - Theme.padRight
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: (e) => e.accepted = true }   // the layer's settings under it stay untouched

    component Words: Text { color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; verticalAlignment: Text.AlignVCenter }
    component Gap: Item { width: 1; height: Theme.gap }
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
        Gap { }
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
        Gap { }
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
        Gap { }
        Line {   // the one ease control (EasePicker.qml): the same list and words as the Key block's; hover plays, a click sets
            Words { width: Theme.labelColumnFor(panel.w); height: parent.height; text: "Ease" }
            EasePicker {
                id: picker
                objectName: "animEase"
                x: Theme.labelColumnFor(panel.w); width: Theme.fieldFor(panel.w); anchors.verticalCenter: parent.verticalCenter
                eases: panel.s.easeList; current: panel.info.ease || ""
                onHovered: (v) => panel.s.preview(v)
                onPicked: (v) => panel.s.setEase(v)
            }
        }
        Repeater {   // a spring: Bounce and Speed (the same key fields as the key bar's, H41), one change per drag
            model: picker.shownEase === "spring" && (panel.info.feel || []).length === 2 ? ["Bounce", "Speed"] : []
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
            Words { x: Theme.labelColumnFor(panel.w); leftPadding: Theme.gap; height: parent.height   // on the fields' text
                    text: (panel.info.handles || []).map(v => v.toFixed(2)).join("  ") }
        }
        Item { width: 1; height: Theme.gap }
        Line {   // Reverse | Delete: the field column's two halves
            Button { x: Theme.labelColumnFor(panel.w); width: Theme.halfFor(panel.w); anchors.verticalCenter: parent.verticalCenter
                     text: "Reverse"; help: "From and to swap"; onClicked: panel.s.reverse() }
            Button { x: Theme.labelColumnFor(panel.w) + Theme.halfFor(panel.w) + Theme.pairGap; width: Theme.halfFor(panel.w)
                     anchors.verticalCenter: parent.verticalCenter
                     text: "Delete"; help: "Removes this animation (undo brings it back)"; onClicked: panel.s.remove() }
        }
    }
    }
}
