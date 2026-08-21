# Regenerating the perfboard's jumper wiring

The perfboard's back-side wiring is a set of **decorative** footprints from
`~/KiCad/jumper-wires-kicad` — no pads, no nets, no copper. DRC never sees them
(409 violations before and after, byte-identical violation set). Their whole job
is to be *readable*, so the quality bar is visual: no two wires may merge.

Everything needed to regenerate them lives in `scripts/`.

## Why wires merged, and the two different fixes

| Failure | Fix |
| --- | --- |
| **Collinear overlap** — two wires on the same row/column with overlapping spans | Cannot be hidden by height. Prevented during routing by a span registry. |
| **Mid-span crossing** — a horizontal wire and a vertical wire meet at a point | Unavoidable on a board this dense, and fine if the two sit at different heights. Fixed after routing by graph-colouring the nets and using the colour as the z tier. |

The previous 163-segment set had **55 same-tier collinear overlaps**. The current
268-segment set has **zero**.

## Pipeline

```bash
cd scripts
python3 gen_segments_v3.py                 # -> segments_v3.json
python3 verify_v3.py segments_v3.json      # connectivity / tap coverage / bounds
python3 analyze_conflicts.py segments_v3.json   # overlap + crossing census
```

Then apply, always to a **copy of the board first**:

```bash
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
$KPY scripts/remove_wires.py <board.kicad_pcb>          # 304 -> 36 footprints
$KPY ~/KiCad/jumper-wires-kicad/scripts/place_wire.py \
     <board.kicad_pcb> scripts/segments_v3.json          # 36 -> 304
kicad-cli pcb drc --severity-all --format report <board.kicad_pcb> -o /tmp/drc.rpt
```

The DRC violation *set* (not just the count) must come back identical to the
pre-wiring baseline. `place_wire.py`'s success message is not evidence of
anything on this file — check `grep -c '(footprint'` yourself, per the standing
rule in `CLAUDE.md`.

Regenerating the board also re-creates the stray
`haptic-console-control-unit-perfboard.kicad_pro` / `.kicad_prl`. Delete them.

## Routing, in brief

- **Buses** (`GND`, `+3V3`, `+5V`, `SCL`, `SDA`) route as a Manhattan MST over
  their taps, so same-row taps chain straight along a connector's pin row.
- **Everything else** routes by A* over the hole grid, one straight leg per move,
  with a turn penalty (`TURN`, fewer jogs) and a crossing penalty
  (`CROSS_PENALTY`, fewer conflict-graph edges → fewer tiers → a flatter stack).
  The 25/40 pair currently in the file was picked by sweeping both.

Three constraints in the generator each exist because violating them produced a
specific, real bug — don't "simplify" them away:

- **Legs may run along pad rows/columns**, as long as they don't pass strictly
  *through* a pad. Only 4 of ~36 columns and 14 of ~54 rows are pad-free, and
  they all hug the board edge, so restricting turns to pad-free lanes left 19 of
  37 signal nets unroutable.
- **Routable lines include each pad's exact coordinate**, not just the nominal
  2.54mm grid. JST pad rows sit at y=15.44 where the grid says 15.24; grid-only
  routing forced a 0.2mm hop off every such pad, which the stub filter then
  deleted, silently disconnecting nets from their own pins.
- **Merging preserves the exact line coordinate.** Runs are *grouped* by a
  0.1mm-quantised key, but the merged segment keeps the real coordinate —
  rounding a run at y=17.94 to 17.90 slides the wire off its pad.

`verify_v3.py` is what catches all three: it checks that every one of the 157
taps lies on a wire and that each net's segments form one connected component.
A wire set can be perfectly overlap-free and still be an open circuit.

## Tier heights

`place_wire.py` lifts a wire by `z_tier * 1.0mm` and accepts fractional tiers.
Colouring needs 7 tiers here; at whole-number steps the top wire would float 6mm
off the board. `assign_tiers()` scales the step so the whole stack fits under
`MAX_LIFT = 2.0mm` while keeping the strict per-tier ordering that makes a
crossing render as over/under.

## Ground truth

`taps_clean.json` (157 taps, 50 nets) is rebuilt by `reconstruct_segments.py`
from each wire label's `REF.PIN->REF.PIN` text resolved against real pad
positions. An earlier `taps.json` was derived from the old wire *geometry* and
so included elbow corner points as if they were taps — several of which happen
to land on an unrelated component's pad, inventing connections that don't exist.
