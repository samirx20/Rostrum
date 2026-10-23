import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Look harness for the kit's ToolRail: filled with a small 3D-style list (what Rostrum3D's Build page will give it), to
// show that any app can fill the rail from a list. See rail_preview.py. Nothing here is an app.
QQC.ApplicationWindow {
    id: win
    visible: true; width: 1280; height: 720
    color: Theme.app
    property string tool: "select"
    property string lastAct: ""
    property bool painting: false
    function keyFor(job) { return ({ select_tool: "V", box_tool: "B", orbit_tool: "O" })[job] || "" }

    ToolRail {
        id: rail
        x: Theme.gap; y: Theme.gap; height: parent.height - 2 * Theme.gap
        current: win.tool
        panelOpen: win.painting
        onPicked: (e) => { if (e.tool) win.tool = e.tool; else win.lastAct = e.act }
        onPanelRequested: win.painting = true
        onPanelCloseRequested: win.painting = false
        groups: [
            { id: "select", items: [{ name: "Select", icon: "select", job: "select_tool", tool: "select", help: "Pick objects and drag their handles." }] },
            { id: "add", name: "Add", items: [
                { name: "Box", icon: "rect", job: "box_tool", tool: "box" },
                { name: "Sphere", icon: "ellipse", tool: "sphere" },
                { name: "Plane", icon: "union", tool: "plane" },
                { name: "A very long shape name", icon: "pen", tool: "long" }] },
            { id: "paint", panel: true, items: [{ name: "Paint", icon: "brush", tool: "paint", help: "Paint on the model." }] },
            { sep: true },
            { id: "camera", items: [{ name: "Camera", icon: "camera", tool: "camera", help: "Place the shot's camera." }] },
            { id: "light", items: [] },                     // nothing to list: left out of the rail
            { id: "render", name: "Render", items: [
                { name: "Quick look", icon: "render3d", act: "quick" },
                { name: "Final", icon: "render3d", act: "final" }] },
            { sep: true },
            { id: "view", items: [
                { name: "Orbit", icon: "hand", job: "orbit_tool", tool: "orbit", help: "Drag to turn the view round." },
                { name: "Zoom", icon: "zoom", tool: "zoom" }] }
        ]
    }
    Text {
        x: 120; y: 40; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
        text: "tool: " + win.tool + (win.lastAct ? "   last act: " + win.lastAct : "") + (win.painting ? "   (paint panel open)" : "")
    }
}
