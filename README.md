# Haptic Console — Control Unit (M6) KiCad Project

KiCad project for the Control Unit module of the Haptic Console v1.0.

## Layout (300×200mm)
- U1 Teensy 4.1 — center-left (60,100), footprint `teensy:Teensy41` (XenGi, modern format)
- J1, J2 — 5-pin JST XH (joysticks): J1=/D0-/D3+GND, J2=/D4-/D7+GND
- B1-B8 — tactile buttons, lower right
- S1-S6 — 8-pin JST XH rail connectors, right edge (x=275)
- R1-R5, R12, R13 — resistors; CB1-CB5 — caps; NP — mounting point

## Status
- Placement complete, all components inside 300×200 outline
- U1 reference fixed (was REF**), Teensy 4.1 3D model renders
- J1/J2 nets assigned
- No routing yet, no zones

## Libraries
- `teensy.pretty` — XenGi Teensy footprints, UPGRADED to modern format (v20260206), 3D model `${KICAD_USER_DIR}/teensy.pretty/Teensy_4.1_Assembly.STEP`
- `digikey-kicad-library` (~/Library/Preferences/kicad/) — 464 atomic footprints, modernized, 3D models
- `SparkFun-KiCad-Libraries` (~/Library/Preferences/kicad/) — 21 footprint + 40 symbol libs (HX711 in SparkFun-Sensor)
- Project fp-lib-table + sym-lib-table wired for all of the above

## Files
- `project/` — schematic, board, project file, lib tables
- `libraries/` — XenGi `teensy.pretty` (modernized footprints)
- `renders/` — schematic + PCB renders (2D composite, 3D top 4K)
- `docs/` — build log, kicad-mcp lessons

## Sources
- Teensy 4.1 footprints + 3D: https://github.com/XenGi/teensy.pretty
- Digi-Key atomic parts: https://github.com/Digi-Key/digikey-kicad-library
- SparkFun: https://github.com/sparkfun/SparkFun-KiCad-Libraries
