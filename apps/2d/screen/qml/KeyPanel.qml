import QtQuick
import RostrumKit

// The picked keys in the settings panel (UX_SPEC 3.18, SPEC §1 / §9.3; it was the timeline header's key bar), above the
// layer's settings while keys are picked. Laid on the settings rows' own columns (Theme.labelColumnFor / fieldFor /
// wideFor): "Key" / "3 keys" with ⋯ at the right; Ease; its curve; for a spring Bounce and Speed; for one key Time and
// Value (a colour key or several keys have no Value). Only what applies shows. Every picked key changes; each pick, field
// edit or whole drag is one change (backend.keyBar, screen2d/key_bar.py). ⋯: After the last key (only while a picked key
// is its setting's last: Stay, Repeat, Back and forth, Carry on; key.set {after}) and whether a picked ease plays once
// on the canvas (backend.easePlay, screen2d/ease_play.py).
Column {
    id: kp
    readonly property var kb: backend.keyBar
    readonly property real full: parent ? parent.width : 0
    readonly property real lab: Theme.labelColumnFor(full)
    visible: kb.shown
    width: full
    spacing: 2
    component Words: Text {
        height: Theme.row; verticalAlignment: Text.AlignVCenter
        color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
    }
    component Line: Item { width: Theme.wideFor(kp.full); height: Theme.row }

    Line {   // "Key" / "3 keys" · ⋯
        Words { text: kp.kb.count === 1 ? "Key" : kp.kb.count + " keys"; color: Theme.fg; font.weight: Font.DemiBold }
        IconButton {
            objectName: "keyMore"
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            glyph: "⋯"; tip: "More"
            onClicked: { const g = mapToItem(null, 0, height + 2); more.openAt(g.x, g.y) }
            ActionMenu {    // the kit's menu: one "After the last key" heading over its choices, then the ease option
                id: more
                entries: kp.kb.afters.map((a, i) => ({ value: "after:" + a.value, label: a.label, group: "after",
                                                       heading: i === 0 ? "After the last key" : "",
                                                       checked: kp.kb.after === a.value }))
                         .concat([{ value: "play", label: "Play the ease when picked", group: "play", checked: backend.easePlay.on }])
                onPicked: (v) => v === "play" ? backend.easePlay.setOn(!backend.easePlay.on) : kp.kb.setAfter(v.slice(6))
            }
        }
    }
    Line {
        Words { width: kp.lab; text: "Ease" }
        ChoiceField {
            objectName: "keyEase"
            x: kp.lab; width: Theme.fieldFor(kp.full); anchors.verticalCenter: parent.verticalCenter
            options: kp.kb.options; current: kp.kb.ease
            onPicked: (v) => kp.kb.setEase(v)
        }
    }
    EaseCurve { width: Theme.wideFor(kp.full); height: 96 }
    Repeater {   // a spring: Bounce and Speed, one change per drag
        model: kp.kb.ease === "spring" && kp.kb.feel.length === 2 ? ["Bounce", "Speed"] : []
        delegate: Line {
            required property string modelData
            required property int index
            Words { width: kp.lab; text: modelData }
            Slider {
                x: kp.lab; width: Theme.fieldFor(kp.full); anchors.verticalCenter: parent.verticalCenter
                value: kp.kb.feel[index]
                function feelTo(v) { const f = kp.kb.feel; kp.kb.springTo(index === 0 ? v : f[0], index === 1 ? v : f[1]) }
                onScrubStarted: kp.kb.begin("spring")
                onScrubbed: (v) => feelTo(v)
                onScrubEnded: kp.kb.end()
                onEdited: (v) => { kp.kb.begin("spring"); feelTo(v); kp.kb.end() }
            }
        }
    }
    Line {
        visible: kp.kb.one
        Words { width: kp.lab; text: "Time" }
        NumberField {
            x: kp.lab; width: Theme.fieldFor(kp.full); anchors.verticalCenter: parent.verticalCenter
            value: kp.kb.time; from: 0; to: backend.frameInfo.duration; step: 0.01; unit: " s"
            onEdited: (v) => kp.kb.setTime(v)
            onTypingStarted: kp.kb.hold("time")
            onTypingEnded: kp.kb.release("time")
        }
    }
    Line {   // on a beat of the music: "bar 5 beat 3"
        visible: kp.kb.one && kp.kb.beat !== ""
        Words { x: kp.lab; leftPadding: Theme.gap; text: kp.kb.beat }
    }
    Line {
        visible: kp.kb.hasValue
        Words { width: kp.lab; text: "Value" }
        NumberField {
            x: kp.lab; width: Theme.fieldFor(kp.full); anchors.verticalCenter: parent.verticalCenter
            value: kp.kb.value; step: 0.01
            onEdited: (v) => kp.kb.setValue(v)
            onTypingStarted: kp.kb.hold("value")
            onTypingEnded: kp.kb.release("value")
        }
    }
    Item {  // the end of the group: a line and a group's gap
        width: Theme.wideFor(kp.full); height: Theme.groupGap
        Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 1; color: Theme.line }
    }
}
