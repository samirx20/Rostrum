import QtQuick
import RostrumKit

// The key bar (UX_SPEC 3.18, INTERACTION 1.5 point 6), in the timeline header only while keys are picked: Ease ▾, the
// small curve, for one key its Time and Value, for a spring Bounce and Speed. Every picked key changes; each pick,
// field edit or whole drag is one change (backend.keyBar, screen2d/key_bar.py). Only what applies shows: no Value for
// a colour key or several keys, no Bounce / Speed unless the ease is Spring. ⋯: After the last key (only while a picked
// key is its setting's last: Stay, Repeat, Back and forth, Carry on; key.set {after}) and whether a picked ease plays
// once on the canvas (backend.easePlay, screen2d/ease_play.py).
Row {
    id: bar
    readonly property var kb: backend.keyBar
    visible: kb.shown
    spacing: Theme.grid
    component Words: Text {
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
    }
    Words { text: bar.kb.count === 1 ? "Key" : bar.kb.count + " keys"; color: Theme.fg3 }
    ChoiceField {
        objectName: "keyEase"
        anchors.verticalCenter: parent.verticalCenter; width: 104
        options: bar.kb.options; current: bar.kb.ease
        onPicked: (v) => bar.kb.setEase(v)
    }
    EaseCurve { anchors.verticalCenter: parent.verticalCenter }
    Words { visible: bar.kb.ease === "spring"; text: "Bounce" }
    Slider {
        visible: bar.kb.ease === "spring"; anchors.verticalCenter: parent.verticalCenter; width: 72
        value: bar.kb.feel.length ? bar.kb.feel[0] : 0
        onScrubStarted: bar.kb.begin("spring")
        onScrubbed: (v) => bar.kb.springTo(v, bar.kb.feel[1])
        onScrubEnded: bar.kb.end()
        onEdited: (v) => { bar.kb.begin("spring"); bar.kb.springTo(v, bar.kb.feel[1]); bar.kb.end() }
    }
    Words { visible: bar.kb.ease === "spring"; text: "Speed" }
    Slider {
        visible: bar.kb.ease === "spring"; anchors.verticalCenter: parent.verticalCenter; width: 72
        value: bar.kb.feel.length ? bar.kb.feel[1] : 0
        onScrubStarted: bar.kb.begin("spring")
        onScrubbed: (v) => bar.kb.springTo(bar.kb.feel[0], v)
        onScrubEnded: bar.kb.end()
        onEdited: (v) => { bar.kb.begin("spring"); bar.kb.springTo(bar.kb.feel[0], v); bar.kb.end() }
    }
    Words { visible: bar.kb.one; text: "Time" }
    NumberField {
        visible: bar.kb.one; anchors.verticalCenter: parent.verticalCenter; width: 72
        value: bar.kb.time; from: 0; to: backend.frameInfo.duration; step: 0.01; unit: " s"
        onEdited: (v) => bar.kb.setTime(v)
    }
    Words { visible: bar.kb.hasValue; text: "Value" }
    NumberField {
        visible: bar.kb.hasValue; anchors.verticalCenter: parent.verticalCenter; width: 72
        value: bar.kb.value; step: 0.01
        onEdited: (v) => bar.kb.setValue(v)
    }
    IconButton {
        objectName: "keyMore"
        anchors.verticalCenter: parent.verticalCenter
        glyph: "⋯"; tip: "More"
        onClicked: more.open()
        Menu {
            id: more
            width: 236
            readonly property string tick: "  ✓"
            entries: bar.kb.afters.map(a => ({ value: "after:" + a.value,
                                               label: "After the last key: " + a.label + (bar.kb.after === a.value ? more.tick : "") }))
                     .concat([{ value: "play", label: "Play the ease when picked" + (backend.easePlay.on ? more.tick : "") }])
            onPicked: (v) => v === "play" ? backend.easePlay.setOn(!backend.easePlay.on) : bar.kb.setAfter(v.slice(6))
        }
    }
}
