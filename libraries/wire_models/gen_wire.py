import math, sys

def make_wire_wrl(path, rgb, length=1.0, radius=0.4, sides=10):
    r, g, b = rgb
    # cylinder tube along local +X axis, x in [0, length], centered on Y=0, sitting on Z=radius
    # so its underside just touches the board surface (Z=0) when placed with no extra Z offset.
    half = length / 2.0
    verts = []
    for i in range(sides):
        ang = 2 * math.pi * i / sides
        y = radius * math.cos(ang)
        z = radius + radius * math.sin(ang)
        verts.append((-half, y, z))
        verts.append((half, y, z))
    # two end caps as centers -- geometry centered on local origin so any
    # pivot KiCad uses for non-uniform Scale (origin or bbox-center) gives
    # the same result: a shape symmetric about (0,0,radius).
    cap0 = len(verts); verts.append((-half, 0.0, radius))
    cap1 = len(verts); verts.append((half, 0.0, radius))

    faces = []
    for i in range(sides):
        a0 = 2 * i
        a1 = 2 * i + 1
        b0 = 2 * ((i + 1) % sides)
        b1 = 2 * ((i + 1) % sides) + 1
        # side quad (two triangles), CCW when viewed from outside
        faces.append((a0, b0, b1, a1))
    for i in range(sides):
        a0 = 2 * i
        b0 = 2 * ((i + 1) % sides)
        faces.append((cap0, b0, a0, -1))
    for i in range(sides):
        a1 = 2 * i + 1
        b1 = 2 * ((i + 1) % sides) + 1
        faces.append((cap1, a1, b1, -1))

    coord_str = ",\n            ".join(f"{x:.4f} {y:.4f} {z:.4f}" for (x, y, z) in verts)
    idx_lines = []
    for f in faces:
        idx_lines.append(" ".join(str(i) for i in f) + " -1")
    idx_str = ",\n            ".join(idx_lines)

    wrl = f"""#VRML V2.0 utf8
# Minimal single-color wire tube, generated for haptic-console-control-unit perfboard wiring diagram.
Shape {{
  appearance Appearance {{
    material Material {{
      diffuseColor {r:.4f} {g:.4f} {b:.4f}
      ambientIntensity 0.4
      specularColor 0.1 0.1 0.1
      shininess 0.05
    }}
  }}
  geometry IndexedFaceSet {{
    solid TRUE
    coord Coordinate {{
      point [
            {coord_str}
      ]
    }}
    coordIndex [
            {idx_str}
    ]
  }}
}}
"""
    open(path, "w").write(wrl)

def hex_to_rgb01(h):
    h = h.lstrip('#')
    return (int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255)

colors = {
    "power": "c23b2e",
    "gnd": "2f5fb0",
    "i2c": "c99a1e",
    "sig_white": "e0e0e0",
    "sig_orange": "e8912f",
    "sig_green": "3f9142",
}

for name, hexval in colors.items():
    make_wire_wrl(f"wire_{name}.wrl", hex_to_rgb01(hexval))
    print("wrote", f"wire_{name}.wrl")
