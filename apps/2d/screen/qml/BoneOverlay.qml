import QtQuick
import QtQuick.Shapes
import RostrumKit
import RostrumCursors 1.0

// The rig in hand's bones over the canvas (UX_SPEC 3.23; backend.rig: screen2d/rig_view.py, rig_drag.py). Thin tapered
// bones from joint to tip, a circle at each joint. Drag a bone: it turns about its joint, or, in an IK chain (an arm, a
// leg), the chain bends to reach the pointer; a click picks the bone (Ctrl+click: with the part picked, for Attach to
// bone). Drag a circle: the joint moves (at rest).
// Right-click the end of a chain (a wrist, an ankle) › Pin / Unpin. Each drag is one undo step. Positions are
// composition px; `fit` is canvas px per composition px; `space` is the item the pointer is read in (Stage's marks).
// Pointers (CURSORS.md): a bone `rotate` towards its tip (it turns about its joint), a joint `pick` + point.
Item {
    id: ov
    property real fit: 1
    property Item space
    readonly property var rig: backend.rig
    readonly property bool posing: backend.tool === "move"    // with the Bone tool the bones show, its own overlay takes the pointer
    visible: rig.rig !== ""
    function at(item, m) { const q = item.mapToItem(ov.space, m.x, m.y); return Qt.point(q.x / ov.fit, q.y / ov.fit) }

    Repeater {      // the bones: a long thin wedge, wide at the joint
        model: ov.rig.bones
        delegate: Item {
            id: bone
            required property var modelData
            readonly property real len: Math.hypot(modelData.tipX - modelData.x, modelData.tipY - modelData.y) * ov.fit
            readonly property real wide: Math.max(3, Math.min(9, len * 0.14))
            readonly property color tint: modelData.picked ? Theme.accent : modelData.chain !== "" ? "#ffb340" : "#f5f5f7"
            x: modelData.x * ov.fit; y: modelData.y * ov.fit
            rotation: Math.atan2(modelData.tipY - modelData.y, modelData.tipX - modelData.x) * 180 / Math.PI
            transformOrigin: Item.TopLeft
            Shape {
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeWidth: 1; strokeColor: Qt.rgba(0, 0, 0, 0.55)
                    fillColor: Qt.rgba(bone.tint.r, bone.tint.g, bone.tint.b, area.containsMouse || area.pressed ? 0.95 : 0.7)
                    startX: 0; startY: -bone.wide
                    PathLine { x: bone.len; y: 0 }
                    PathLine { x: 0; y: bone.wide }
                    PathLine { x: 0; y: -bone.wide }
                }
            }
            MouseArea {         // the wedge's middle: pose it
                id: area
                x: bone.wide; y: -bone.wide; width: Math.max(4, bone.len - bone.wide * 1.5); height: 2 * bone.wide
                enabled: ov.posing
                hoverEnabled: true; preventStealing: true
                CanvasCursor { kind: "rotate"; angle: bone.rotation }
                property bool on: false
                property point p0
                property bool ctrl: false       // Ctrl at the press or the release: a window that was not active at the press may only report it later
                onPressed: (m) => { p0 = Qt.point(m.x, m.y); ctrl = (m.modifiers & Qt.ControlModifier) !== 0; const p = ov.at(area, m); on = ov.rig.dragger.beginPose(bone.modelData.id, p.x, p.y) }
                onPositionChanged: (m) => { if (on) { const p = ov.at(area, m); ov.rig.dragger.moveTo(p.x, p.y) } }
                onReleased: (m) => {
                    const still = Math.abs(m.x - p0.x) + Math.abs(m.y - p0.y) < 3
                    if (on) { if (still) ov.rig.dragger.cancel(); else ov.rig.dragger.end() }
                    if (still) ov.rig.pickBone(bone.modelData.id, ctrl || (m.modifiers & Qt.ControlModifier) !== 0)   // a click picks the bone; Ctrl+click adds it to the part picked
                    on = false
                }
                onCanceled: { if (on) ov.rig.dragger.cancel(); on = false }
            }
            HoverTip { hovered: area.containsMouse && !area.pressed   // the colour is the kind: orange bends as a chain, blue is picked, white turns alone
                       text: bone.modelData.name + (bone.modelData.chain !== "" ? " · bends as a chain" : "") }
        }
    }
    Repeater {      // the joints: drag to fix one; a chain's end has Pin on right-click
        model: ov.rig.joints
        delegate: Rectangle {
            id: joint
            required property var modelData
            width: 11; height: 11; radius: 5.5
            x: modelData.x * ov.fit - 5.5; y: modelData.y * ov.fit - 5.5
            color: modelData.pinned ? "#30d158" : jarea.containsMouse ? Theme.accent : "white"
            border.width: 1.5; border.color: modelData.ik !== "" ? "#ff9f0a" : Qt.rgba(0, 0, 0, 0.6)
            MouseArea {
                id: jarea
                anchors.fill: parent; anchors.margins: -4
                enabled: ov.posing
                hoverEnabled: true; preventStealing: true
                acceptedButtons: Qt.LeftButton | (joint.modelData.ik !== "" ? Qt.RightButton : 0)
                CanvasCursor { kind: "pick"; badge: "point" }
                property bool on: false
                onPressed: (m) => {
                    if (m.button === Qt.RightButton) { const g = jarea.mapToItem(null, m.x, m.y); pinMenu.ik = joint.modelData.ik
                        pinMenu.entries = [{ value: joint.modelData.pinned ? "unpin" : "pin", label: joint.modelData.pinned ? "Unpin" : "Pin" }]
                        pinMenu.openAt(g.x, g.y); return }
                    on = ov.rig.dragger.beginJoint(joint.modelData.bone, joint.modelData.end)
                }
                onPositionChanged: (m) => { if (on) { const p = ov.at(jarea, m); ov.rig.dragger.moveTo(p.x, p.y) } }
                onReleased: { if (on) ov.rig.dragger.end(); on = false }
                onCanceled: { if (on) ov.rig.dragger.cancel(); on = false }
            }
            HoverTip { hovered: jarea.containsMouse && !jarea.pressed
                       text: joint.modelData.ik !== "" ? "Drag to fix the joint · right-click to pin" : "Drag to fix the joint" }
        }
    }
    ActionMenu {
        id: pinMenu
        property string ik: ""
        onPicked: (v) => ov.rig.dragger.pin(ik, v === "pin")
    }
}
