import QtQuick
import RostrumKit

// 3D's tool rail (SPEC §2): the kit's ToolRail filled from today's add operations (backend.adder.rail, adding.py).
// Select, then Shapes (R), Lights (L), Camera (C). A pick adds the thing through the same operation agents use and
// selects it; the tool stays Select. The groups that aren't built yet (Type & logo, Edit mesh, Paint, Simulate,
// Import) are absent until they work (rule of individuality).
ToolRail {
    id: rail
    current: "select"
    iconKinds: ({ shape3d: icon3d })
    Component { id: icon3d; Icon3D { } }
    function entries(list) { return list.map(e => ({ name: e.name, icon: e.icon, kind: e.icon === "camera" ? "" : "shape3d", act: e.value })) }
    groups: [
        { id: "select", items: [{ name: "Select", icon: "select", tool: "select", help: "Click a thing in the viewport or the scene list." }] },
        { id: "shapes", name: "Shapes", items: rail.entries(backend.adder.rail.shapes) },
        { sep: true },
        { id: "lights", name: "Lights", items: rail.entries(backend.adder.rail.lights) },
        { id: "camera", name: "Camera", items: rail.entries(backend.adder.rail.camera) }
    ]
    onPicked: (e) => { if (e.act) backend.adder.add(e.act) }
}
