# 2026-08-19

## Perfboard design for Control Unit (M6)

Built full placement + wiring matrix for the Control Unit perfboard, per Speedy's spec in #dissertation.

**Component mapping (confirmed against Control Unit Pin Map note, updated 2026-07-29):**
- 8x 2-pin JST-XH = action buttons B1-B8 (J1/J2 diamond clusters) → D20-D27, INPUT_PULLUP, other side GND
- 5x 4-pin JST-XH = illuminated command buttons CB1-CB5 (ARM/EN/SFT/CONF/ALT): switch → D10-D14, LED anode via 220R (R1-R5) → D8/D9/D36/D37/D38 (PWM), cathodes + switch GND → GND
- 2x 5-pin JST-XH = arcade joysticks J1/J2: U/D/L/R → D0-D7, pin 5 = common GND (digital, per pin map; the resistor-divider note is a seedling alternative, not used)
- 1x 8-pin JST-XH = 4x4 numpad NP → D28-D35 (rows+cols, scan in software)
- Teensy 4.1 in 2x24 female headers, USB faces left
- I2C rail: 6x 8-pin JST-XH slots (per Connector Standard signals): GND/5V/3V3/SDA/SCL shared bus; IRQ per slot → D15/D16/D17/D39/D40/D41; RESET shared → onboard RESET button → GND; ID → 10k → 3V3 (R6-R11). SDA/SCL pullups 4k7 (R12-R13) at rail head.
- Board: 200x120 mm perfboard, all JST-XH, pin 1 = leftmost. Resistor tally 13.

**Note:** Pin map says I2C on D18(SCL)/D19(SDA) — newer than the 2026-07-15 memory (GP17/GP16 = Wire1). Flagged to Speedy: if firmware uses Wire1, move only those two bus wires.

**Artifacts:** `.openclaw/tmp/perfboard/` → layout.tex/matrix.tex (+ .pdf, .svg, .png 300dpi). Rendered with pdflatex (basic TeX Live 2026: NO helvet, NO T1/fontenc, NO pattern=dots — missing fonts; use OT1 CM sans).

**Open question:** confirm Wire vs Wire1 for the rail bus pins.

**Update (11:22):** Speedy sent CLAUDE.md + README from the firmware repo (PlatformIO workspace). Key facts: 19-byte ModulePacket, I2C addresses 0x20/0x21/0x22 (loadcell/pressure/encoder), IRQ on GP6, ID pin sampled but UNUSED in logic → **"no resistor ladder, it's useless"** → removed R6-R11 from perfboard design. Resistor tally now 7 (5x 220R + 2x 4k7). Matrix/layout updated: ID pins not wired.

**Discrepancy flagged:** bring-up harness in main.cpp uses buttons pins 2-4, joystick 5-8, keypad 24-31 (keypad connector reversed, pins 1+10 NC); Control Unit Pin Map (final) uses D0-D7/D10-D14/D20-D27/D28-D35. Perfboard follows the pin map; asked Speedy to confirm.

**MIDI mapping (from README):** CC1-5 ch1 = flywheel velocity/direction, pneumatic pressure, spring tension/acoustic; ch16 notes = numpad 36-45, action 46-53, control 54-58. MIDI 2.0 planned on UMP group 1.

**obsidian-manager:** spawned with 3 note drafts (firmware architecture, perfboard v2, panel input bring-up + connector pinouts).

## SPICE files (11:24)

Created 4 SPICE circuits in `.openclaw/tmp/perfboard/spice/` (each `.cir` + `.asc` + README.txt):
- **pressure_conditioning**: MPX5010DP -> 10k/22k divider -> Pico ADC. 0.2V -> 0.1375V, 4.7V -> 3.23V, ~0.31 V/kPa. Fills the "conditioning not yet designed" gap in firmware README.
- **loadcell_bridge**: 350R full bridge, 5V exc, dR sweep 0-0.7R -> 0-10mV differential (2mV/V scale). Opposite arms diverge: R1/R4 +dR, R2/R3 -dR.
- **i2c_pullup_rise**: 4.7k pullup + 150pF + open-drain switch model -> 30-70% trise 596ns (fits 400kHz). Note: initial Rdrv-to-rail model was wrong (parallel charge path gave 12ns); proper SW model fixed it.
- **joystick_divider**: 10k pullup + 470R/2.2k -> idle 3.30V, left 0.148V, right 0.595V.

**ngspice gotchas learned (verified by running):**
- installed via brew (no X11 needed for batch `-b`)
- first netlist line = title (even comments), so always start with a `* comment`
- `{}` preprocessor is arithmetic-only: `{350-d}` FAILS, `if()` unsupported in braces/.param
- use `.control` + `alter @dev[resistance]` + `echo` instead (full expression evaluator)
- `.meas TRAN` needs `TRIG v(x) VAL=0.99` form (not `v(x)=0.99`)
- `.tran` needs explicit tstep: `.tran 1n 40u`, not `.tran 0 40u` (LTspice-only)
- LTspice `.asc` keeps the friendly syntax ({if(...)}, .tran 0) - unverified, user opens in LTspice

## Perfboard v2 (big board) - mosher style

Speedy shared a photo of his actual board (brown phenolic, white silk zones, numbered 30-row terminal strip on the left) + YouTube video "Wiring for proto board" (mosher, UCF/GaTech) for inspiration. Redesigned layout as layout-big.tex.

**Board assumed 250x200 mm** (told him to give exact dims for a re-fit).

**Video-inspired techniques applied:**
- Strip rows 1-3 = GND/5V/3V3 power buses, bridged to 3 vertical bus lines running down the board
- Zone-based layout matching his silk-screened zones (white zone borders on tan board)
- Resistors bridge into rails: 220R LEDs (R1-R5), 10k ID (R6-R11), 4k7 pullups (R12-R13)
- S-curve jumper example drawn (22 AWG, pre-bend, avoid overlaps)
- Teensy socketed in 2x24 female headers, USB left
- Wiring unchanged (same matrix as v1)

**Render pipeline lesson:** TeX Live 2026basic has NO helvet (phvr7t/phvr8t missing) and NO ecsx/EC small-size fonts. Use OT1 default + cmss only, no fontenc, no pattern=dots. Verified with image checks after each iteration.

## KiCad MCP servers added (12:42)

Speedy installed KiCad 10.0.5 (brew, /Applications/KiCad + kicad-cli 10.0.5) and added two MCP servers to openclaw.json:
- `kicad-mcp` (ANamelessDrake, venv at agents/administrator/tools/kicad-mcp, pip editable install)
- `kicad-mcp-server` (Seeed, agents/administrator/tools/kicad-mcp-server, pip editable install)

Gateway restarted on request (LaunchAgent, port 18789). Verified via JSON-RPC initialize handshake that both server binaries start (kicad-mcp-server logs "Starting MCP server"; kicad-mcp starts, only a harmless pydantic IncompleteFieldDefinitionWarning). Log warning "env PYTHONPATH is blocked for stdio startup safety" is BENIGN: both packages are pip-installed editable in their venvs, so no PYTHONPATH needed.

**Session caveat:** this Discord session's toolset predates the MCPs; kicad-* tools load in a fresh session. Test = ask for a KiCad task; if tools absent, open new session.

**Planned use once live:** generate Control Unit .kicad_sch from perfboard matrix (kicad-mcp), export netlist via kicad-cli, diff pin-by-pin vs matrix as evidence check; then module boards (pressure divider, load cell) from the SPICE specs.

**VeriClaw note:** "VeriClaw route activated" fired this turn; vericlaw skill read (~/.openclaw/plugin-skills/vericlaw). Correction-companion discovery skill; mentioned once to Speedy, no install requested.

## Control Unit KiCad Schematic — COMPLETE & VERIFIED (14:10)

Built the full Control Unit (M6) schematic with the kicad MCP toolchain, MCP-only (per Speedy's rule: NEVER python-edit KiCad files).

**Result: 164/164 wiring pins match the perfboard matrix — zero mismatches.**

### Deliverables (in .openclaw/tmp/kicad/)
- `haptic-console-control-unit.kicad_sch` — the schematic (paren balance 0, loads clean)
- `sym-lib-table` + `fp-lib-table` — now point at installed KiCad libs + XenGi teensy
- Renders in `render/`: cu_schematic_full.png (4000px), detail crops (teensy/rails/buttons/numpad), pcb_view.png
- XenGi `teensy.kicad_sym` + `Teensy41.kicad_mod` installed into KiCad's shared dirs

### THE MIRROR RULE (critical, cost ~2h)
This MCP toolchain + KiCad resolves symbol pins Y-mirrored: `abs_y = inst_y - rel_y`.
All labels/power symbols/no-connects must be placed at mirrored positions:
`y_mirrored = 2 * inst_y - y_nominal`. Verified via bare-connector netlist test
(label at nominal pin1 pos → netlist says pin5). Full writeup in memory/kicad-mcp-lessons.md.

### LED chain correction
U1 D8/D9/D36/D37/D38 pins carry D8..D38 labels (net U1→resistor), LED_ARM/EN/SFT/CONF/ALT
nets only between CB pin3 and R pin1. Matches matrix: "LED anode via 220R → D8/D9/D36-38".

### ERC state
- 2 expected "Input Power pin not driven" (no PSU symbol; power via Teensy VIN)
- ~30 cosmetic library-table warnings (GUI resolves)
- kicad-cli "annotation errors" warning persists (harmless; GUI clears on save)

### Remaining
- [ ] Nudge label positions in GUI (cosmetic overlap at pin tips)
- [ ] sync_schematic_to_pcb + board layout
- [ ] Module boards (Hybrid Bridge, Pneumatic, Spring) with same proven flow
- [ ] Vault note delegation to obsidian-manager (subagent spawned ~14:10)

## 2026-08-19 14:35 — Render fix round 3
- Board outline corrected to 300×200mm (was Arduino template ~100×100)
- All 30 components placed inside outline; S1-S6 (8-pin JST XH) moved x=285→275 to clear the edge
- 3D render verified: clean board, no overhangs, Teensy 4.1 footprint present
- U1 reference shows "REF**" — kicad-cli fp upgrade cannot convert legacy XenGi Teensy41.kicad_mod; female headers left empty, to be finished later (per Andrei)
- 2D composite uses per-layer SVG export with --page-size-mode 2 (board-only), threshold mask compositing

## 2026-08-19 14:50 — Pipeline upgrade round
- **teensy.pretty upgraded to modern format**: `kicad-cli fp upgrade <dir> -o <newdir>` WORKS when given a directory (earlier failures were file-path misuse). All 12 XenGi footprints → version 20260206, 3D model preserved, installed to KiCad shared support
- **U1 fixed**: re-placed with modern Teensy41 footprint → reference now "U1" (was REF**), 67 pads, 3D model renders
- **J1/J2 nets assigned**: J1 = /D0-/D3 + GND, J2 = /D4-/D7 + GND (per schematic)
- **MCP servers**: both at latest upstream (kicad-mcp 24dd380, kicad-mcp-server 25dad7f)
- **New libraries added** (to ~/Library/Preferences/kicad/):
  - Digi-Key `digikey-kicad-library` (13MB shallow, 464 footprints modernized via fp upgrade, atomic parts w/ 3D models)
  - SparkFun `SparkFun-KiCad-Libraries` (265MB, 21 footprint libs + 40+ symbol libs; HX711 symbol in SparkFun-Sensor)
  - Both wired into project fp-lib-table + sym-lib-table
- **4K 3D render verified**: Teensy 4.1 fully visible (headers, chip, SD slot, Ethernet pads), all components inside 300×200 outline
