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
    readonly property var none: ({ id: "", name: "", x: 0, y: 0, tipX: 0, tipY: 0, picked: false, chain: "", bone: "", end: "", ik: "", pinned: false })
    function boneOf(id) { return rig.bones.find(b => b.id === id) || none }
    function jointOf(key) { return rig.joints.find(j => j.bone + "|" + j.end === key) || none }
    function at(item, m) { const q = item.mapToItem(ov.space, m.x, m.y); return Qt.point(q.x / ov.fit, q.y / ov.fit) }

    Repeater {      // the bones: a long thin wedge, wide at the joint
        model: ov.rig.boneIds       // one delegate per bone that stays while the pose changes: a dragged bone's area must live until the release
        delegate: Item {
            id: bone
            required property string modelData      // the bone's id
            readonly property var d: ov.boneOf(modelData)
            readonly property real len: Math.hypot(d.tipX - d.x, d.tipY - d.y) * ov.fit
            readonly property real wide: Math.max(3, Math.min(9, len * 0.14))
            readonly property color tint: d.picked ? Theme.accent : d.chain !== "" ? "#ffb340" : "#f5f5f7"
            x: d.x * ov.fit; y: d.y * ov.fit
            rotation: Math.atan2(d.tipY - d.y, d.tipX - d.x) * 180 / Math.PI
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
                property point p0           // where the press was, in composition px (the bone turns under the pointer: its own coordinates would say "still")
                property bool ctrl: false       // Ctrl at the press or the release: a window that was not active at the press may only report it later
                onPressed: (m) => { const p = ov.at(area, m); p0 = p; ctrl = (m.modifiers & Qt.ControlModifier) !== 0; on = ov.rig.dragger.beginPose(bone.modelData, p.x, p.y) }
                onPositionChanged: (m) => { if (on) { const p = ov.at(area, m); ov.rig.dragger.moveTo(p.x, p.y) } }
                onReleased: (m) => {
                    const q = ov.at(area, m)
                    const still = (Math.abs(q.x - p0.x) + Math.abs(q.y - p0.y)) * ov.fit < 3
                    if (on) { if (still) ov.rig.dragger.cancel(); else ov.rig.dragger.end() }
                    if (still) ov.rig.pickBone(bone.modelData, ctrl || (m.modifiers & Qt.ControlModifier) !== 0)   // a click picks the bone; Ctrl+click adds it to the part picked
                    on = false
                }
                onCanceled: { if (on) ov.rig.dragger.cancel(); on = false }
            }
            HoverTip { hovered: area.containsMouse && !area.pressed   // the colour is the kind: orange bends as a chain, blue is picked, white turns alone
                       text: bone.d.name + (bone.d.chain !== "" ? " · bends as a chain" : "") }
        }
    }
    Repeater {      // the joints: drag to fix one; a chain's end has Pin on right-click
        model: ov.rig.jointKeys     // stable like the bones: a dragged joint's area lives until the release
        delegate: Rectangle {
            id: joint
            required property string modelData      // "bone|end"
            readonly property var d: ov.jointOf(modelData)
            width: 11; height: 11; radius: 5.5
            x: d.x * ov.fit - 5.5; y: d.y * ov.fit - 5.5
            color: d.pinned ? "#30d158" : jarea.containsMouse ? Theme.accent : "white"
            border.width: 1.5; border.color: d.ik !== "" ? "#ff9f0a" : Qt.rgba(0, 0, 0, 0.6)
            MouseArea {
                id: jarea
                anchors.fill: parent; anchors.margins: -4
                enabled: ov.posing
                hoverEnabled: true; preventStealing: true
                acceptedButtons: Qt.LeftButton | (joint.d.ik !== "" ? Qt.RightButton : 0)
                CanvasCursor { kind: "pick"; badge: "point" }
                property bool on: false
                onPressed: (m) => {
                    if (m.button === Qt.RightButton) { const g = jarea.mapToItem(null, m.x, m.y); pinMenu.ik = joint.d.ik
                        pinMenu.entries = [{ value: joint.d.pinned ? "unpin" : "pin", label: joint.d.pinned ? "Unpin" : "Pin" }]
                        pinMenu.openAt(g.x, g.y); return }
                    on = ov.rig.dragger.beginJoint(joint.d.bone, joint.d.end)
                }
                onPositionChanged: (m) => { if (on) { const p = ov.at(jarea, m); ov.rig.dragger.moveTo(p.x, p.y) } }
                onReleased: { if (on) ov.rig.dragger.end(); on = false }
                onCanceled: { if (on) ov.rig.dragger.cancel(); on = false }
            }
            HoverTip { hovered: jarea.containsMouse && !jarea.pressed
                       text: joint.d.ik !== "" ? "Drag to fix the joint · right-click to pin" : "Drag to fix the joint" }
        }
    }
    ActionMenu {
        id: pinMenu
        property string ik: ""
        onPicked: (v) => ov.rig.dragger.pin(ik, v === "pin")
    }
}
