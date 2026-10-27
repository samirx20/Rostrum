"""Rostrum3D's operation modules and agent tool modules, in registration order (the order agents see them): the lists the
document kind and the agent server read (rostrum_core.modules). A plugin adds its own module to the same lists."""
from rostrum_core.modules import ModuleList

OPS = ModuleList("rostrum3d", [      # they register on REGISTRY
    ".ops_bones", ".ops_clay", ".ops_clay_make", ".ops_combine", ".ops_copies", ".ops_follow", ".ops_graph", ".ops_import", ".ops_items", ".ops_keys", ".ops_lipsync", ".ops_lights", ".ops_materials", ".ops_mesh", ".ops_mesh2", ".ops_mirror", ".ops_paint",
    ".ops_pose", ".ops_poses", ".ops_rigs", ".ops_scene", ".ops_shot_camera", ".unfold",
    ".sim.ops",    # sim.body, sim.set, sim.run, sim.to_keys (brief 25)
    ".ops_anim",   # anim.ease, key.scale, key.paste, key.stagger: rostrum_core.keys.anim_ops; anims.py: inspect_animations
])

TOOLS = ModuleList("rostrum3d.mcp", [      # each has a `tools`; the order is the tools' order
    ".look", ".shots_look", ".material_look", ".paint_look", ".shape_look", ".render", ".facts", ".estimate", ".place", ".anims", ".motion_look", ".lipsync", ".send", ".assets_tools", ".simulate",
])
