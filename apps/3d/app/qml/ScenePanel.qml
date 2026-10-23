import QtQuick
import RostrumKit

// The settings panel with nothing selected: the Scene (SPEC §3.4). Its header is the shot's name and "Shot · nothing
// selected"; View holds the viewport's own settings (screen state: never the document, never in the history); Sky is the
// scene's dome light (a click selects it), or "Sky +" to add one; Shot lists the shot's values and a click opens the
// shot's own settings (where it is edited: one place). Same grid as the item settings (28 px rows, one label column).
// Rows that do nothing right now are absent. While the Final look is on, the Quick look's rows give way to one line.
Panel {
    id: panel
    readonly property var state: backend.sceneState
    readonly property bool final: viewport.look === "final"
    readonly property bool free: viewport.mode === "free"
    readonly property bool canAddSky: !state.sky.id

    component Title: Text {          // a group's name, as the item settings' group titles
        height: Theme.groupGap + Theme.rowDense
        verticalAlignment: Text.AlignBottom; bottomPadding: Theme.grid + 2
        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold
    }
    component Line: Item {           // label | field, on the kit grid; a click on the whole row when `clickable`
        id: line
        property string text: ""
        property string value: ""
        property bool clickable: false
        default property alias field: slot.data
        signal clicked()
        width: parent ? parent.width : 0; height: Theme.row
        Rectangle { anchors.fill: parent; anchors.leftMargin: -Theme.grid; radius: Theme.radiusCtl; color: Theme.hover
                    visible: line.clickable && area.containsMouse }
        Text { width: Theme.labelColumnFor(line.width) - Theme.gap; anchors.verticalCenter: parent.verticalCenter
               text: line.text; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; elide: Text.ElideRight }
        Text { visible: line.value !== ""; x: Theme.labelColumnFor(line.width); width: Theme.fieldFor(line.width)
               anchors.verticalCenter: parent.verticalCenter
               text: line.value; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; elide: Text.ElideRight }
        Item { id: slot; x: Theme.labelColumnFor(line.width); width: Theme.fieldFor(line.width); height: Theme.field
               anchors.verticalCenter: parent.verticalCenter }
        MouseArea { id: area; anchors.fill: parent; enabled: line.clickable; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor; onClicked: line.clicked() }
    }

    Item {
        anchors { fill: parent; rightMargin: Theme.padRight - panel.bodyPad }   // rows end where the item settings' rows end
        Text {
            id: head
            anchors { left: parent.left; right: parent.right }
            text: panel.state.shot.label; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.heading
            font.weight: Font.DemiBold; elide: Text.ElideRight
        }
        Text {
            id: sub
            anchors { left: parent.left; right: parent.right; top: head.bottom; topMargin: 2 }
            text: "Shot · nothing selected"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
        }
        Flickable {
            anchors { left: parent.left; right: parent.right; top: sub.bottom; bottom: parent.bottom; topMargin: Theme.gap }
            contentHeight: col.height; clip: true; boundsBehavior: Flickable.StopAtBounds
            Column {
                id: col
                width: parent.width

                Title { text: "View"; width: parent.width }
                Text {
                    visible: panel.final; width: parent.width; height: Theme.row; verticalAlignment: Text.AlignVCenter
                    text: "Final uses the Render settings"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
                }
                Line {
                    visible: !panel.final; text: "Exposure"
                    Slider { anchors.fill: parent; from: -4; to: 4; step: 0.1; value: viewport.exposure; defaultValue: 0
                             onScrubbed: (v) => viewport.setExposure(v); onEdited: (v) => viewport.setExposure(v) }
                }
                Line {
                    visible: !panel.final && viewport.studioInUse; text: "Studio light"   // a scene dome lights the view instead
                    Slider { anchors.fill: parent; from: 0; to: 2; step: 0.05; value: viewport.studio
                             onScrubbed: (v) => viewport.setStudio(v); onEdited: (v) => viewport.setStudio(v) }
                }
                Line {
                    visible: !panel.final; text: "Scene lights"
                    Toggle { anchors.verticalCenter: parent.verticalCenter; checked: viewport.sceneLights
                             onToggled: (v) => viewport.setSceneLights(v) }
                }
                Line {
                    visible: !panel.final; text: "Shadows"
                    Toggle { anchors.verticalCenter: parent.verticalCenter; checked: viewport.aoOn
                             onToggled: (v) => viewport.setAoOn(v) }
                }
                Line {
                    visible: !panel.final && viewport.aoOn; text: "Strength"
                    Slider { anchors.fill: parent; from: 0.05; to: 2; step: 0.05; value: viewport.aoStrength
                             onScrubbed: (v) => viewport.setAoStrength(v); onEdited: (v) => viewport.setAoStrength(v) }
                }
                Line {
                    visible: !panel.final && !panel.free && viewport.cameraDof; text: "Depth of field"   // only a camera with it on makes it matter
                    Toggle { anchors.verticalCenter: parent.verticalCenter; checked: viewport.dof
                             onToggled: (v) => viewport.setDof(v) }
                }
                Line {
                    visible: viewport.mode === "shot"; text: "Dim outside"
                    Toggle { anchors.verticalCenter: parent.verticalCenter; checked: !!viewport.dim
                             onToggled: (v) => viewport.setDim(v) }
                }
                Line {
                    visible: panel.free && viewport.hasShot; text: "Back to the shot"; value: "Home"
                    clickable: true; onClicked: viewport.home()
                }

                Title { text: "Sky"; width: parent.width; visible: !!panel.state.sky.id || panel.canAddSky }
                Line {
                    visible: !!panel.state.sky.id; text: "Light"; value: panel.state.sky.label || ""
                    clickable: true; onClicked: backend.select(panel.state.sky.id)
                }
                Line {
                    visible: !panel.state.sky.id && panel.canAddSky; text: "Sky +"
                    clickable: true; onClicked: backend.adder.add("light:dome")
                }

                Title { text: "Shot"; width: parent.width }
                Repeater {
                    model: panel.state.shot.rows
                    delegate: Line {
                        required property var modelData
                        text: modelData.label; value: modelData.value
                        clickable: true; onClicked: backend.select(panel.state.shot.id)
                    }
                }
            }
        }
    }
}
