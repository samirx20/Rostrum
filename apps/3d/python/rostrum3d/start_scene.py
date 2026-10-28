"""What a new 3D scene holds (3D simplicity SPEC §1, "Before the first click"), so the first Quick picture is lit and
framed with nothing done: a wide neutral ground, the "Studio" sky (a real photographed sky, skies/), and the shot
camera "Shot 1" looking at the middle of the ground, framed for things about a hand to an arm tall (a 30 cm figure
standing there fills about half the picture). The camera stands a little above (55 cm up, 1.6 m back) and looks down 15°, more than half the lens's
view (11.5°), so the first picture is the floor, with no horizon. The Studio sky lights and reflects but is not seen by
the camera (`seenByCamera` off): a camera turned up or set low sees the ground run to a soft horizon against the shot's
plain background, the far floor's tone, never the photographed room's walls and lamps (round 5 of the 3D gaps, Drape:
its black band and grey panel along the top of every low shot; faults.py names it, backdrop_edge, when the photo is
turned back on). New on the start
screen (app/screen3d/files_3d.py) and a new document an agent opens (mcp/server.py) both start from it. Not a look to
copy: every part of it is an ordinary item to change or delete. Two lights start it, so a thing put in the middle reads
at once (round 2 of the 3D gaps: the sky alone left it flat and dim): a "Key light" softbox (a rect, 0.3 m, Same
brightness at any size) on the camera's left, 1.6 m up and 1.8 m from the middle (about 50° high), casting a contact
shadow close under what stands there that reads from any camera, and a
"Rim light" strip standing on end behind on the right, drawing a bright edge (no shadow of its own); the Studio sky, one and a
half stops down, is the fill (round 5, Hello: a lower, bigger key and a one-stop sky left a figure's shadow too faint to
read as a floor; both judges saw the figure hanging). A plain floor, not a shadow catcher (there is none
yet): it shows the shadows and is seen as a floor. It is a backdrop (mesh_fields.py): a right-click on it is a
right-click on empty space, and it is never offered Turn into clay or Make copies; a click or the scene list selects it.
"""
from __future__ import annotations

from . import skies

HORIZON = "#5c5957"     # the shot's background, past the ground's far edge: the far start floor's tone in Cycles (measured)
KEY_AT, KEY_AIM, KEY_INTENSITY = (-0.75, 1.6, 0.55), (0, 0.1, 0), 16   # the start key (script_shot.py's brightness= measures from it)
SKY_EXPOSURE = -1.5
SOURCE = f'''
material("ground_material", name="Ground", baseColor="#8f8e8a", roughness=0.9)
mesh("ground", name="Ground", shape="plane", width=200, depth=200, material="ground_material", backdrop=True)
light("sky", name="Sky", kind="dome", texture="{skies.START}", exposure={SKY_EXPOSURE}, seenByCamera=False)
light("key_light", name="Key light", kind="rect", width=0.3, height=0.3, normalize=True, intensity={KEY_INTENSITY},
      x={KEY_AT[0]}, y={KEY_AT[1]}, z={KEY_AT[2]}).aim({KEY_AIM})
light("rim_light", name="Rim light", kind="strip", length=1.0, width=0.2, normalize=True, intensity=20,
      shadows=False, x=0.6, y=0.9, z=-1.0).aim((0, 0.15, 0), roll=90)
cam = camera("shot_1_camera", name="Shot 1 camera", focalLength=50, y=0.55, z=1.6).aim((0, 0.12, 0))
shot("shot_1", name="Shot 1", camera=cam, fps=24, start=0, end=4, background="{HORIZON}")
'''
