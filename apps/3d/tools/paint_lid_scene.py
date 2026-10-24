# The brief 20 walk's scene (a script for `main.py --script`): a dark glossy round lid on a grey plinth, a softbox and a
# dim sky, the camera looking down at it, so a roughness scuff reads as a dull patch in the gloss.
gloss = material("gloss", baseColor="#141517", roughness=0.08)
grey = material("grey", baseColor="#5a5d62", roughness=0.7)
mesh("plinth", shape="box", width=0.3, height=0.02, depth=0.3, y=-0.01, material=grey)
mesh("lid", shape="cylinder", radius=0.03, height=0.012, bevel=0.003, segments=64, y=0.006, material=gloss)
light("key", kind="rect", width=0.3, height=0.2, intensity=25, x=-0.2, y=0.3, z=0.15).aim((0, 0, 0))
light("sky", kind="dome", color="#b8c4d6", intensity=0.3)
cam = camera("cam", focalLength=85, y=0.12, z=0.16).aim((0, 0.006, 0))
shot("hero", camera=cam, fps=24, start=0, end=1)
