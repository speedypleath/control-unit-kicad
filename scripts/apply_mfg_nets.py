"""Reassign every pad's net on the manufactured board from the schematic netlist,
and clear all routing so the board can be re-routed from scratch.

Input: scripts/mfg_pad_nets.json  ({ref: {pad: netname}}), dumped from
`kicad-cli sch export netlist --format kicadxml`.

Pads not listed keep no net (U1's genuinely-unconnected USB/VBAT/PROGRAM pins).
The board uses the codeless `(net "NAME")` pad style with no top-level net table;
pcbnew round-trips that faithfully -- don't "fix" it.
"""
import sys, json

SP = ("/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/"
      "Versions/3.9/lib/python3.9/site-packages")
if SP not in sys.path:
    sys.path.insert(0, SP)
import pcbnew  # noqa: E402

board_path = sys.argv[1]
pad_nets = json.load(open(sys.argv[2]))

board = pcbnew.LoadBoard(board_path)

# 1. make sure every net name exists on the board
wanted = {n for pads in pad_nets.values() for n in pads.values()}
existing = set(board.GetNetsByName().keys())
created = 0
for name in sorted(wanted):
    if name not in existing:
        board.Add(pcbnew.NETINFO_ITEM(board, name))
        created += 1

# 2. assign pad nets
assigned = cleared = missing = 0
for fp in board.Footprints():
    ref = fp.GetReference()
    pads = pad_nets.get(ref, {})
    for pad in fp.Pads():
        name = pads.get(pad.GetNumber())
        if name is None:
            if pad.GetNetname():
                pad.SetNet(board.FindNet(""))
                cleared += 1
            missing += 1
            continue
        net = board.FindNet(name)
        if net is None:
            raise SystemExit(f"net {name} not found after creation")
        pad.SetNet(net)
        assigned += 1

# 3. drop all routing
tracks = list(board.GetTracks())
for t in tracks:
    board.Remove(t)

pcbnew.SaveBoard(board_path, board)
print(f"nets created: {created}")
print(f"pads assigned: {assigned}  cleared: {cleared}  left netless: {missing}")
print(f"tracks/vias removed: {len(tracks)}")
