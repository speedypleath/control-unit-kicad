"""Build an occupancy model of the perfboard for wire rerouting.

Loads the board via pcbnew and dumps a JSON with:
  - every pad's world position and (ref, pin) for all footprints except the
    decorative wire footprints (models referencing JUMPER_WIRES_LIB)
  - the board Edge.Cuts bounding box
  - occupied grid lines: for the 2.54mm hole grid, every row-Y and col-X that
    contains a pad (rounded to grid) -- a wire line is "free" only if that grid
    line has no pads AND no (other) wire currently runs along it.
"""
import sys
import json

KICAD_PY_SITE_PACKAGES = (
    "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/"
    "Versions/3.9/lib/python3.9/site-packages"
)
if KICAD_PY_SITE_PACKAGES not in sys.path:
    sys.path.insert(0, KICAD_PY_SITE_PACKAGES)
import pcbnew  # noqa: E402

GRID = 2.54


def grid(v):
    return round(round(v / GRID) * GRID, 3)


def main():
    board_path = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "board_model.json"
    b = pcbnew.LoadBoard(board_path)

    pads = []
    for fp in b.Footprints():
        if any("JUMPER_WIRES_LIB" in m.m_Filename for m in fp.Models()):
            continue
        for pad in fp.Pads():
            pads.append(dict(ref=fp.GetReference(), pin=pad.GetPadName(),
                             x=round(pad.GetPosition().x / 1e6, 3),
                             y=round(pad.GetPosition().y / 1e6, 3)))

    # board outline bbox from Edge.Cuts items
    xs, ys = [], []
    for item in b.GetDrawings():
        if item.GetLayerName() == "Edge.Cuts":
            box = item.GetBoundingBox()
            xs += [box.GetX() / 1e6, (box.GetX() + box.GetWidth()) / 1e6]
            ys += [box.GetY() / 1e6, (box.GetY() + box.GetHeight()) / 1e6]
    bbox = [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)]

    # occupied grid lines (by pads)
    rows, cols = set(), set()
    for p in pads:
        rows.add(grid(p["y"]))
        cols.add(grid(p["x"]))

    json.dump(dict(pads=pads, bbox=bbox,
                   pad_rows=sorted(rows), pad_cols=sorted(cols)),
              open(out, "w"), indent=1)
    print(f"{len(pads)} pads, bbox={bbox}, {len(rows)} occupied pad rows, "
          f"{len(cols)} occupied pad cols -> {out}")


if __name__ == "__main__":
    main()
