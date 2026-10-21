"""A small document to open the screen on while developing: a few meshes with materials (one glass), a floor, three
lights, a camera with a 2 s move, one shot. Not a template: it only exercises the screen's panels."""
SOURCE = '''
clay = material("clay", baseColor="#d9d4cc", roughness=0.6)
alu = material("alu", baseColor="#c4c8ce", metallic=1, roughness=0.3)
glass = material("glass", baseColor="#ffffff", roughness=0.02, transmission=1, ior=1.5)
floor = material("floor", baseColor="#3a3d42", roughness=0.8)

mesh("ground", shape="plane", width=6, depth=6, material=floor)
with group("set", ry=-10):
    mesh("block", shape="box", width=0.5, height=0.3, depth=0.5, bevel=0.02, y=0.15, material=clay)
    mesh("vase", shape="cylinder", radius=0.11, height=0.42, bevel=0.01, x=0.05, y=0.51, material=glass)
    mesh("ball", shape="sphere", radius=0.12, x=0.48, y=0.12, z=0.18, material=alu)

key = light("key", kind="rect", width=1.2, height=0.8, intensity=6, temperature=5200, x=1.4, y=1.6, z=1.2)
key.aim((0, 0.3, 0))
light("rim", kind="rect", width=0.4, height=1.4, intensity=9, x=-1.2, y=1.0, z=-1.4).aim((0, 0.4, 0))
light("sky", kind="dome", color="#9fb2cc", intensity=0.25)

cam = camera("cam", focalLength=70, y=0.7, z=3.0).aim((0.1, 0.35, 0))
cam.key("x", {0: -0.6, 2: 0.6}, ease="smooth")
cam.key("y", {0: 0.55, 2: 0.8}, ease="smooth")
shot("hero", camera=cam, fps=24, start=0, end=2)
'''
