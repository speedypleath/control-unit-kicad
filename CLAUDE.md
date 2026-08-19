# CLAUDE.md — Haptic Console Control Unit

Guidance for working on this KiCad project. See also `README.md` (project overview)
and `docs/kicad-mcp-lessons.md` (detailed history of a prior schematic rebuild).

## Rule #1: don't hand-edit .kicad_sch / .kicad_pcb

The project owner has said this emphatically before (see `docs/kicad-mcp-lessons.md`):
**never modify the schematic or PCB S-expression files with Python scripts or manual
text edits. Use the KiCad MCP tools, or `kicad-cli`/the GUI, instead.**

Why: KiCad 9/10 symbol instances need exact per-pin `(pin "N" (uuid ...))` entries and
full property sets. Hand-written or scripted edits that look structurally valid (balanced
parens) can still desync from what KiCad's own writer produces — pins silently drop out
of the netlist (`<NO NET>`), or the file fails to load entirely.

**2026-08-19 session note:** an earlier ERC-fixing pass in this same session (before the
MCP servers below were installed) *did* hand-edit the schematic directly — adding wires,
deleting stale no-connect flags, and resyncing the cached `Conn_01x06` symbol geometry to
the current `Connector_Generic` library. Every change was verified against `kicad-cli sch
erc` (0 errors/0 warnings) and a rendered PDF before being called done, so the file is in
a known-good state — but it was done the way this project's rules say not to. Going
forward, prefer the MCP tools below for any further schematic/PCB edits.

## MCP servers (installed 2026-08-19, project-local scope)

Two servers are registered for this project (`claude mcp list` to confirm they're up):

- **`kicad-seeed`** (Seeed-Studio/kicad-mcp-server) — analysis-first: schematic/PCB
  read, netlist tracing, ERC/DRC via `kicad-cli`, pin/power/bus extraction, device-tree
  generation, parts registry search. Installed in its own venv at
  `~/mcp-servers/kicad-mcp-server/.venv` (system Python 3.13, not KiCad's bundled 3.9 —
  see caveat below). Good default for "what does this schematic/PCB contain" questions
  and for ERC/DRC checks.
- **`kicad-namelessdrake`** (ANamelessDrake/kicad-mcp) — read *and write*: place symbols/
  footprints, add wires/labels/power symbols, route traces, run ERC/DRC, sync schematic→
  PCB, JLCPCB parts search, Freerouting autoroute integration. Installed in its own venv
  at `~/mcp-servers/kicad-mcp/.venv`. This is the one to reach for when *editing* the
  schematic or PCB — it uses a lossless S-expression parser built for exactly this.

Both were smoke-tested against `project/haptic-console-control-unit.kicad_sch` and agree
with `kicad-cli sch erc` output.

**Caveat:** KiCad's own bundled Python on this Mac is 3.9
(`/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9`), but
both MCP servers require Python ≥3.10. They're installed against system Python (miniconda,
3.13.9) instead. Practical effect: `kicad-seeed`'s PCB analysis runs in text-parsing
fallback mode rather than via the real `pcbnew` API (no precise track-length/DRC-rule
introspection) — fine for schematic work and ERC, worth knowing if PCB analysis results
look approximate. To get full `pcbnew`-backed analysis, `kicad-mcp-server` would need to
be reinstalled into a KiCad Python ≥3.10 build if one ever ships for this platform.

## Library setup

- `libraries/teensy.kicad_sym` + `libraries/teensy.pretty` — custom Teensy 4.1 symbol +
  footprints (from XenGi's teensy_library/teensy.pretty), **not** part of stock KiCad.
  `project/sym-lib-table` and `project/fp-lib-table` must reference them via
  `${KIPRJMOD}/../libraries/...` (project-relative), **not**
  `${KICAD_SYMBOL_DIR}`/`${KICAD_FOOTPRINT_DIR}` — those resolve to KiCad's own stock
  install directory and won't find a custom library placed in the project tree. This was
  the root cause of the "Symbol 'Teensy4.1' not found" / "does not include the footprint
  library 'teensy'" errors fixed 2026-08-19.
- `Connector_JST`, `Resistor_THT`, `Device`, `Connector_Generic`, `power` — all stock
  KiCad 10 libraries, resolved fine via `${KICAD_SYMBOL_DIR}`/`${KICAD_FOOTPRINT_DIR}`.
  No need to vendor these into the project (checked: the current stock
  `Connector_JST.pretty` already has 558 footprints including the JST-XH-6 used by
  S1–S6, `JST_XH_B6B-XH-A_1x06_P2.50mm_Vertical` — it's built from the same
  `gitlab.com/kicad/libraries/kicad-footprints` repo the project owner pointed at).

## Verification workflow

`kicad-cli` is on PATH at `/opt/homebrew/bin/kicad-cli` (KiCad 10.0.4). Useful for
independent verification alongside/instead of the MCP tools:

```bash
kicad-cli sch erc --format report project/haptic-console-control-unit.kicad_sch -o /tmp/erc.rpt
kicad-cli sch export pdf project/haptic-console-control-unit.kicad_sch -o /tmp/sch.pdf
pdftoppm -png -r 200 /tmp/sch.pdf /tmp/sch_page   # poppler; no SVG→PNG tool installed
```

No `rsvg-convert`/`imagemagick`/`inkscape` on this machine for SVG→PNG conversion — go
through PDF export + `pdftoppm` (poppler, already installed via miniconda) instead when a
visual check is needed.

## lib_symbol_mismatch gotcha (if it recurs elsewhere)

KiCad's stock `Connector_Generic` symbols occasionally get their internal pin/body
geometry revised between library versions, which desyncs any schematic's *cached* copy of
that symbol (embedded in `lib_symbols` inside the `.kicad_sch`) from what's currently
installed — shows up as `lib_symbol_mismatch` in ERC. Blindly "update from library" shifts
every pin's absolute position and can silently break existing wiring.

If the geometry diff between old and new is a uniform shift (check by diffing the two
symbol S-expressions), you can update to the new geometry *and* counter-shift the
instance's anchor position by the same amount, so every pin's absolute position on the
sheet stays exactly where it was — no rewiring needed. This is what was done for S1–S6's
`Conn_01x06` on 2026-08-19 (uniform −1.27mm local-Y shift in the library, compensated
with a −1.27mm shift of each instance's `(at ...)` anchor and property positions). Verify
with `kicad-cli sch erc` (should show 0 violations) and a rendered PDF before trusting it.
