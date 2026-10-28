"""What a new 3D scene holds (3D simplicity SPEC §1, "Before the first click"), so the first Quick picture is lit and
framed with nothing done: a wide neutral ground, the "Studio" sky (a real photographed sky, skies/), and the shot
camera "Shot 1" looking at the middle of the ground, framed for things about a hand to an arm tall (a 30 cm figure
standing there fills about half the picture). The camera stands a little above (55 cm up, 1.6 m back) and looks down 15°, more than half the lens's
view (11.5°), so the first picture is the floor, with no horizon and no photographed room across its top (the Studio sky
still lights and reflects; a camera turned up sees it). New on the start
screen (app/screen3d/files_3d.py) and a new document an agent opens (mcp/server.py) both start from it. Not a look to
copy: every part of it is an ordinary item to change or delete. A plain floor, not a shadow catcher (there is none
yet): it shows the shadows and is seen as a floor. It is a backdrop (mesh_fields.py): a right-click on it is a
right-click on empty space, and it is never offered Turn into clay or Make copies; a click or the scene list selects it.
"""
from __future__ import annotations

from . import skies

SOURCE = f'''
material("ground_material", name="Ground", baseColor="#8f8e8a", roughness=0.9)
mesh("ground", name="Ground", shape="plane", width=200, depth=200, material="ground_material", backdrop=True)
light("sky", name="Sky", kind="dome", texture="{skies.START}")
cam = camera("shot_1_camera", name="Shot 1 camera", focalLength=50, y=0.55, z=1.6).aim((0, 0.12, 0))
shot("shot_1", name="Shot 1", camera=cam, fps=24, start=0, end=4)
'''
