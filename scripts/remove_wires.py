"""Remove every decorative jumper-wire footprint from a board.

Identifies them the way prior sessions established: empty fpid, Reference matching
W<N>, and a 3D model path referencing JUMPER_WIRES_LIB. Goes through pcbnew's real
object model rather than text-editing the .kicad_pcb (CLAUDE.md Rule #1).
"""
import sys, re
KICAD = ("/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/"
         "Versions/3.9/lib/python3.9/site-packages")
if KICAD not in sys.path:
    sys.path.insert(0, KICAD)
import pcbnew  # noqa: E402

board = pcbnew.LoadBoard(sys.argv[1])
doomed = [fp for fp in board.Footprints()
          if re.fullmatch(r"W\d+", fp.GetReference() or "")
          and any("JUMPER_WIRES_LIB" in m.m_Filename for m in fp.Models())]
for fp in doomed:
    board.Remove(fp)
board.Save(sys.argv[1])
print(f"removed {len(doomed)} wire footprints from {sys.argv[1]}")
