"""Reconstruct the current wire segment set from the perfboard .kicad_pcb.

Every wire footprint (Reference W<N>, 3D model path containing JUMPER_WIRES_LIB)
encodes: position (segment midpoint), rotation (segment angle), m_Scale.x (length
span via the /2.54 convention), m_Offset.z (z tier), color (model filename), and
net label (Value field). Recover all of it as the place_wire.py 8-field schema.
"""
import sys
import json
import math

KICAD_PY_SITE_PACKAGES = (
    "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/"
    "Versions/3.9/lib/python3.9/site-packages"
)
if KICAD_PY_SITE_PACKAGES not in sys.path:
    sys.path.insert(0, KICAD_PY_SITE_PACKAGES)
import pcbnew  # noqa: E402

BOARD = sys.argv[1] if len(sys.argv) > 1 else \
    "/Users/speedypleath/KiCad/control-unit-kicad/project/haptic-console-control-unit-perfboard.kicad_pcb"
OUT = sys.argv[2] if len(sys.argv) > 2 else "reconstructed_segments.json"

COLORS = {"wire_red.wrl": "red", "wire_yellow.wrl": "yellow", "wire_white.wrl": "white",
          "wire_orange.wrl": "orange", "wire_green.wrl": "green", "wire_blue.wrl": "blue"}

board = pcbnew.LoadBoard(BOARD)
segs = []
for fp in board.Footprints():
    models = list(fp.Models())
    if not models:
        continue
    fname = models[0].m_Filename
    if "JUMPER_WIRES_LIB" not in fname:
        continue
    color = COLORS[fname.split("/")[-1]]
    pos = fp.GetPosition()
    mx, my = pos.x / 1e6, pos.y / 1e6  # nm -> mm
    # place_wire.py rotates the 3D MODEL, not the footprint (fp rot is always 0).
    # It set m_Rotation.z = -angle_deg, so angle_deg = -m_Rotation.z.
    angle_deg = -models[0].m_Rotation.z
    span = models[0].m_Scale.x * 2.54  # inverse of the place_wire /2.54 convention
    z_tier = round(models[0].m_Offset.z)
    th = math.radians(angle_deg)  # board-coords: x right, y down
    dx = math.cos(th) * span / 2.0
    dy = math.sin(th) * span / 2.0
    x1, y1 = round(mx - dx, 3), round(my - dy, 3)
    x2, y2 = round(mx + dx, 3), round(my + dy, 3)
    layer = "back" if fp.GetLayerName() == "B.Cu" else "front"
    segs.append([round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3),
                 color, fp.GetValue(), layer, z_tier])

json.dump(segs, open(OUT, "w"), indent=1)
from collections import Counter
print(f"recovered {len(segs)} segments -> {OUT}")
print("colors:", dict(Counter(s[4] for s in segs)))
print("tiers:", dict(Counter(s[7] for s in segs)))
print("layers:", dict(Counter(s[6] for s in segs)))
print("span range: %.2f .. %.2f mm" % (min(s for s in (math.hypot(s[2]-s[0], s[3]-s[1]) for s in segs)),
                                        max(s for s in (math.hypot(s[2]-s[0], s[3]-s[1]) for s in segs))))
