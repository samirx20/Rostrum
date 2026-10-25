import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Layouts
import RostrumKit
import "MixFormat.js" as F

// One track's, bus' or the master's strip, top to bottom: a cap in the track's colour and its name, its effects (one
// line each, "+ Effect" pinned under them), its sends and ducks, where it plays to, pan, the level block (dB scale, fader, meter with its
// peak), M S R and the volume. Editing works on the strip at once (one change on it) and selects it; the inspector follows the release.
// The Master's output line holds "+ Group" (a new group plays into it). The parts under the head (pan, the fader at its
// least, M S R, the volume) always fit: a low dock gives the effect lines less room (they scroll), never the volume box.
Rectangle {
    id: s
    required property var model          // roles: mixer.py ROLES (id, name, hue, volume, pan, effects, meter, canSolo, canArm, output, sends, …)
    readonly property bool selected: backend.selected === model.id
    readonly property bool low: height < 460          // a low dock (most laptops): sends and ducks fold into "Sends ▾", the fader keeps the height
    readonly property bool routed: model.output !== ""
    property real head: 0                 // the tallest strip's parts above the fader (set by the Mixer)
    readonly property real naturalHead: headCol.implicitHeight
    readonly property bool isMaster: model.id === "master"
    // the head's room: the strip less its margins and the parts under it at their least (pan 20, fader 72, M S R 24, volume 24, 4 gaps)
    readonly property real headRoom: height - (Theme.gap + 4) - (Theme.gap + 2) - (20 + 72 + 24 + 24 + 4 * Theme.gap)
    // what the effect lines may take: the head's room less the name, the output line and their gaps (one line and "+ Effect" at the least)
    readonly property real chainRoom: Math.max(46, headRoom - 20 - 20 - 2 * Theme.grid)
    width: 148
    color: Theme.app
    radius: Theme.radiusPanel
    border.width: selected ? 1 : 0; border.color: Theme.accent

    function pick() { if (backend.selected !== model.id) backend.select(model.id) }

    Rectangle {   // the colour cap: the track's arrangement colour, grey for a bus and the master
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: s.selected ? 1 : 0 }
        height: 4; radius: 2; color: s.model.hue
    }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: Theme.gap + 2; anchors.topMargin: Theme.gap + 4
        spacing: Theme.gap
        Item {   // the parts above the fader, padded to the tallest strip's (s.head): every fader starts on one line
            Layout.fillWidth: true; Layout.preferredHeight: Math.min(Math.max(headCol.implicitHeight, s.head), Math.max(s.headRoom, headCol.implicitHeight))
        ColumnLayout {   // name, effects, sends and ducks, output, pan
            id: headCol
            width: parent.width; spacing: Theme.grid
            NameLabel {
                Layout.fillWidth: true; Layout.preferredHeight: 20
                text: s.model.name; verticalAlignment: Text.AlignVCenter
                font.pixelSize: Theme.title; font.weight: Font.DemiBold
                MouseArea { anchors.fill: parent; onPressed: s.pick() }
            }
            MixChain {   // one line per effect (scrolls past three), "+ Effect" pinned under them
                Layout.fillWidth: true; Layout.preferredHeight: Math.min(contentHeight, 22 + rowStep * Math.max(1, Math.floor((Math.min(s.low ? 72 : 94, s.chainRoom) - 22) / rowStep)))   // whole lines and "+ Effect"
                chips: s.model.effects; ownerId: s.model.id
            }
            Loader {   // sends and ducks (a low dock: they open from "Sends" on the output line); scrolls only when the dock has no room for all
                active: !s.low && s.routed; visible: active      // made only where shown: most laptops' docks are low
                Layout.fillWidth: true; Layout.preferredHeight: item ? Math.min(item.contentHeight, Math.max(80, s.height - 340)) : 0   // the content's own height; only a very full strip scrolls (340 = the strip's other parts at their least)
                sourceComponent: Flickable {
                    contentHeight: routes.height; clip: true; boundsBehavior: Flickable.StopAtBounds; interactive: contentHeight > height
                    MixRoutes { id: routes; width: parent.width; strip: s }
                }
            }
            Item {   // the Master: "+ Group", level with the other strips' output line
                visible: s.isMaster
                Layout.fillWidth: true; Layout.preferredHeight: 20
                MixChip { objectName: "addGroup"; text: "+ Group"; row: true; flat: true; width: parent.width; anchors.verticalCenter: parent.verticalCenter
                          tip: "New group: a shared channel several tracks play into"; onClicked: mixer.addBus() }
            }
            Item {   // where it plays to: a pick when there is a bus to choose, plain words when the master is the only place
                visible: s.routed
                Layout.fillWidth: true; Layout.preferredHeight: 20
                MixPick {
                    visible: s.routed && s.model.outputs.length > 1
                    anchors { left: parent.left; top: parent.top; bottom: parent.bottom; right: sendsBtn.visible ? sendsBtn.left : parent.right
                              rightMargin: sendsBtn.visible ? Theme.grid : 0 }
                    row: true
                    text: s.model.output; choices: s.model.outputs
                    tip: "Plays to " + s.model.output.replace(/^→\s*/, "") + ". Click to pick the master or a group"
                    onPicked: (id) => mixer.setOutput(s.model.id, id)
                }
                Text {
                    visible: s.routed && s.model.outputs.length <= 1
                    anchors { left: parent.left; top: parent.top; bottom: parent.bottom; right: sendsBtn.visible ? sendsBtn.left : parent.right }
                    leftPadding: Theme.gap; verticalAlignment: Text.AlignVCenter
                    text: s.model.output; color: Theme.fg2; elide: Text.ElideRight
                    font.family: uiFont; font.pixelSize: Theme.label
                }
                MixChip {   // a low dock: the sends and ducks open from here, so they stay one click away
                    id: sendsBtn
                    visible: s.low && s.model.reverb !== null && s.model.reverb !== undefined
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    readonly property bool open: !!sendsPop.item && sendsPop.item.opened
                    height: 20; selected: open
                    text: "…"   // the same on every strip: the output's name keeps the room
                    tip: open ? "" : "Reverb send, sends to groups and dips"
                    onClicked: { sendsPop.active = true; open ? sendsPop.item.close() : sendsPop.item.open() }
                    Loader {   // made on the first click: every strip has one, and a closed one made its sends and picks anyway
                        id: sendsPop
                        active: false
                        sourceComponent: SmallPopup {
                            parent: sendsBtn
                            // above the button (the Mixer sits at the bottom of the window), inside the window
                            y: Math.max(8 - sendsBtn.mapToItem(null, 0, 0).y, -implicitHeight - 2)
                            x: Math.max(8 - sendsBtn.mapToItem(null, 0, 0).x, sendsBtn.width - width)
                            width: 150; padding: Theme.gap
                            background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
                            contentItem: MixRoutes { strip: s }
                        }
                    }
                }
            }
        }
        }
        RowLayout {  // pan: its value and the slider on one line, under the padded head so every strip's pan sits on one line
            opacity: s.model.canPan ? 1 : 0; enabled: s.model.canPan       // the master has none: its room stays, faders level
            Layout.fillWidth: true; Layout.preferredHeight: 20; spacing: Theme.grid
            Text { text: "Pan " + F.panText(s.model.pan); color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
                   font.features: { "tnum": 1 }; Layout.minimumWidth: 42 }
            Slider {
                objectName: "mixPan:" + s.model.id
                Layout.fillWidth: true; implicitWidth: 10
                from: -1; to: 1; step: 0.01; value: s.model.pan; origin: 0; defaultValue: 0
                onScrubStarted: backend.beginScrubOn(s.model.id, "pan")      // the strip at once, the panel after the release
                onScrubbed: (v) => backend.scrub("pan", v)
                onScrubEnded: backend.endScrubOn()
                onEdited: (v) => { s.pick(); backend.beginScrub("pan"); backend.scrub("pan", v); backend.endScrub() }   // wheel, ← / →: one change
            }
        }
        MixLevel {
            ownerId: s.model.id
            Layout.alignment: Qt.AlignHCenter; Layout.fillHeight: true; Layout.minimumHeight: 72; Layout.preferredHeight: 1000
            gain: s.model.volume; meter: s.model.meter; peak: mixer.peaks[s.model.id] !== undefined ? mixer.peaks[s.model.id] : null; live: s.visible ? mixer.live[s.model.id] || null : null   // hidden (the Editor shows): the meter rests
            onScrubStarted: backend.beginScrubOn(s.model.id, "volume")
            onScrubbed: (g) => backend.scrub("volume", g)
            onScrubEnded: backend.endScrubOn()
            onReset: { s.pick(); backend.setValue("volume", 1) }
            onNudged: (g) => { s.pick(); backend.setValue("volume", g) }
            onTypeIt: { level.forceActiveFocus(); level.input.forceActiveFocus(); level.input.selectAll() }
        }
        MixMS { strip: s; Layout.fillWidth: true; Layout.preferredHeight: 24; Layout.minimumHeight: 24; Layout.maximumHeight: 24; opacity: s.model.canMute || s.model.canSolo || s.model.canArm ? 1 : 0 }   // the master: its room stays, faders level
        NumberField {   // the level in dB: click to type (a value outside −60 … +12 is refused with the range), wheel and arrows nudge
            id: level
            objectName: "mixVolume:" + s.model.id
            Layout.fillWidth: true; Layout.preferredHeight: 24; Layout.minimumHeight: 24
            from: 0; to: 4; step: 0.1; display: "db"; label: "Volume"; value: s.model.volume; defaultValue: 1
            onScrubStarted: backend.beginScrubOn(s.model.id, "volume")
            onScrubbed: (v) => backend.scrub("volume", v)
            onScrubEnded: backend.endScrubOn()
            onEdited: (v) => { s.pick(); backend.setValue("volume", v) }
        }
    }
}
