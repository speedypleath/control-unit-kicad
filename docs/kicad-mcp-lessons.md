# KiCad MCP — Hard-Won Lessons (2026-08-19)

## THE RULE (from Speedy, emphatic)

**NEVER modify KiCad schematic/PCB files with python or manual text edits. ALWAYS use the MCP tools** (`kicad-mcp__*` / `kicad-mcp-server__*`). Every file is MCP-owned. Hand-editing breaks the round-trip and wastes hours.

## What went wrong (Control Unit rebuild, 2026-08-19)

1. **Python-appended power symbols broke connectivity.** I appended `(symbol ... (lib_id "power:GND") ...)` instances by python. They parsed "fine" (paren balance 0) but showed `<NO NET>` in netlists and kicad-cli eventually refused to load the file ("Failed to load schematic").
2. **Root cause found:** KiCad 9/10 symbol instances need per-pin entries `(pin "1" (uuid "..."))` inside each instance, plus full property sets (Reference/Value/Footprint/Datasheet). My hand-written blocks lacked them; the MCP-written ones have them. The MCP writer is the only correct writer.
3. **MCP tools only round-trip their own writes.** Any python edit, even "correct", gets mangled by the next MCP call's full-file rewrite (annotate, delete, etc.).
4. **The native batch tool** `kicad-mcp__schematic_add_power_symbols` places power symbols in the correct format — use it, never hand-append.
5. **Annotate is the last step** for `#PWR?` refs — annotate assigns `#PWR1..N`. Run it once, after all placement, and don't touch the file afterwards except via MCP.

## Correct workflow for building a schematic with these MCPs

1. `kicad-mcp-server__create_kicad_project` (fresh template project).
2. Extract template junk UUIDs (read-only python is fine for READING/parsing — never writing) → delete via `kicad-mcp__schematic_delete_many` (one atomic call).
3. Add custom lib symbols via `kicad-mcp__schematic_add_lib_symbol` (pins as structured list).
4. Place everything via `kicad-mcp__schematic_place_symbol` / `schematic_place_footprint`.
5. Labels via `kicad-mcp__schematic_add_labels` (atomic batch).
6. Power symbols via `kicad-mcp__schematic_add_power_symbols` (atomic batch — correct format guaranteed).
7. No-connects via `kicad-mcp__schematic_add_no_connects`.
8. Annotate → ERC (`kicad-mcp__schematic_run_erc`) → export netlist via kicad-cli → validate.
9. `kicad-mcp__sync_schematic_to_pcb` for the PCB.

## References Speedy supplied (2026-08-19)

- JST headers on KiCad: https://www.reddit.com/r/KiCad/comments/1g5w09f/how_do_i_get_jst_headers_on_kicad/
- Teensy KiCad library (symbols + footprints): https://github.com/XenGi/teensy_library (+ https://github.com/XenGi/teensy.pretty for footprints) — covers Teensy 4.1.

## Tooling notes

- schemdraw-circuit-diagrams skill (proposal applied 2026-08-19) for circuit diagrams: `~/.openclaw/skill-workshop/proposals/schemdraw-circuit-diagrams-20260819-3e8bff1fc4/PROPOSAL.md`
- Project lives at `.openclaw/tmp/kicad/` (haptic-console-control-unit).
- kicad-cli: `/opt/homebrew/bin/kicad-cli`.
- Broken/partial builds archived in `.openclaw/tmp/kicad/broken/` and `broken2/`.

## 2026-08-19 UPDATE — MIRROR BUG SOLVED (the big one)

**THE MIRROR RULE (critical for this MCP toolchain):** KiCad resolves symbol pins at
`abs_y = inst_y - rel_y` (Y-mirrored) when symbols are embedded from the installed
KiCad 10 library into the KiCad-9-version template schematic. So EVERY label, power
symbol, and no-connect must be placed at the MIRRORED position:
`y_mirrored = 2 * inst_y - y_nominal` (equivalently `inst_y - rel_y`).

This is why build 1 "worked" (117/157) — its labels happened to be at mirrored coords.
The rebuild used nominal coords and failed until we mirrored them back.

**Verification pattern that caught it:** the netlist is ground truth. Test on a bare
Conn_01x05: label at nominal pin1 pos → netlist says pin5. That proves the mirror.

**FINAL SCHEMATIC STATE (haptic-console-control-unit, 2026-08-19 ~14:10):**
- 164/164 wiring matrix pins verified against netlist export (0 mismatches)
- Components: U1 (Teensy 4.1 XenGi symbol), B1-B8, J1/J2, CB1-CB5, NP, S1-S6, R1-R5, R12/R13
- 125 net labels, 40 power symbols, 19 no-connects, paren balance 0
- ERC: 2 expected "Input Power pin not driven" (no PSU symbol; power via Teensy VIN), 30 library-table warnings (cosmetic, GUI resolves)
- sym-lib-table + fp-lib-table now point at installed KiCad libs + XenGi teensy
- Path: .openclaw/tmp/kicad/haptic-console-control-unit.kicad_sch
- Render: .openclaw/tmp/kicad/render/cu_final.png

**LED chain correction:** U1 D8/D9/D36/D37/D38 pins carry D8..D38 labels (net U1→resistor),
while LED_ARM/EN/SFT/CONF/ALT nets are only between CB pin3 and R pin1. Matches perfboard
matrix: "LED anode via 220R (R1-R5) → D8/D9/D36/D37/D38".
