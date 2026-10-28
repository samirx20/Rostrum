"""What a new 3D scene holds (3D simplicity SPEC §1, "Before the first click"), so the first Quick picture is lit and
framed with nothing done: a wide neutral ground, the "Studio" sky (a real photographed sky, skies/), and the shot
camera "Shot 1" looking at the middle of the ground, framed for things about a hand to an arm tall (a 30 cm figure
standing there fills about half the picture). The camera stands a little above (55 cm up, 1.6 m back) and looks down 15°, more than half the lens's
view (11.5°), so the first picture is the floor, with no horizon and no photographed room across its top (the Studio sky
still lights and reflects; a camera turned up sees it). New on the start
screen (app/screen3d/files_3d.py) and a new document an agent opens (mcp/server.py) both start from it. Not a look to
copy: every part of it is an ordinary item to change or delete. Two lights start it, so a thing put in the middle reads
at once (round 2 of the 3D gaps: the sky alone left it flat and dim): a "Key light" softbox (a rect, 0.45 m, Same
brightness at any size) on the camera's left, 1.1 m up and 1.75 m from the middle, casting the shadow on the floor, and a
"Rim light" strip standing on end behind on the right, drawing a bright edge (no shadow of its own); the Studio sky, one
stop down, is the fill. A plain floor, not a shadow catcher (there is none
yet): it shows the shadows and is seen as a floor. It is a backdrop (mesh_fields.py): a right-click on it is a
right-click on empty space, and it is never offered Turn into clay or Make copies; a click or the scene list selects it.
"""
from __future__ import annotations

from . import skies

SOURCE = f'''
material("ground_material", name="Ground", baseColor="#8f8e8a", roughness=0.9)
mesh("ground", name="Ground", shape="plane", width=200, depth=200, material="ground_material", backdrop=True)
light("sky", name="Sky", kind="dome", texture="{skies.START}", exposure=-1)
light("key_light", name="Key light", kind="rect", width=0.45, height=0.45, normalize=True, intensity=16,
      x=-1.4, y=1.1, z=0.3).aim((0, 0.1, 0))
light("rim_light", name="Rim light", kind="strip", length=1.0, width=0.2, normalize=True, intensity=20,
      shadows=False, x=0.6, y=0.9, z=-1.0).aim((0, 0.15, 0), roll=90)
cam = camera("shot_1_camera", name="Shot 1 camera", focalLength=50, y=0.55, z=1.6).aim((0, 0.12, 0))
shot("shot_1", name="Shot 1", camera=cam, fps=24, start=0, end=4)
'''
