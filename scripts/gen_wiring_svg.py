#!/usr/bin/env python3
"""Regenerate the "Back-side wiring diagram" SVG in docs/wiring-guide.html.

Reads the *real* routed wire segments (scripts/segments_v3.json, the same file
that gets applied to the board by jumper-wires-kicad's place_wire.py) plus real
pad world positions (scripts/board_model.json), and emits the three content
lines of the inline SVG: pad dots, wire lines, and component ref labels.

Notes on fidelity:
  * This is the BACK (solder) side, so X is mirrored.
  * Segments are drawn in z_tier order, lowest first, so a signal wire that
    physically passes over a bus rail also renders on top of it here.
  * The Teensy header sockets' 48 pins get pad dots but no ref label (they'd
    crowd the top of the diagram); every net still terminates at its real pin.

Run from the repo root:  python3 scripts/gen_wiring_svg.py
It rewrites docs/wiring-guide.html in place.
"""
import json
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = ROOT / "docs" / "wiring-guide.html"

SCALE = 6.2          # px per mm - matches the previous diagram's visual weight
MARGIN_X = 14.0      # px; wide enough that an edge-column ref label isn't clipped
MARGIN_Y = 3.0       # px of breathing room top and bottom
LABEL_DY = 6.0       # px a ref label sits above its topmost pad
LABEL_H = 11.0       # px of headroom a ref label needs in the content bbox

# Physical jumper colour -> (stroke hex, css class). power/gnd/i2c get a class
# so the page's light/dark theme variables can override them; the three signal
# colours are literal, matching the legend swatches.
COLOURS = {
    "red":    ("#c23b2e", "wire wire-power"),
    "blue":   ("#2f5fb0", "wire wire-gnd"),
    "yellow": ("#c99a1e", "wire wire-i2c"),
    "white":  ("#e0e0e0", "wire wire-signal"),
    "orange": ("#e8912f", "wire wire-signal"),
    "green":  ("#3f9142", "wire wire-signal"),
}

model = json.loads((ROOT / "scripts" / "board_model.json").read_text())
segs = json.loads((ROOT / "scripts" / "segments_v3.json").read_text())
pads = model["pads"]

# --- content bbox in mm, then the mirrored mm -> px transform ----------------
xs = [p["x"] for p in pads] + [s[0] for s in segs] + [s[2] for s in segs]
ys = [p["y"] for p in pads] + [s[1] for s in segs] + [s[3] for s in segs]
x0, x1 = min(xs), max(xs)
y0, y1 = min(ys), max(ys)

W = round((x1 - x0) * SCALE + 2 * MARGIN_X, 1)
H = round((y1 - y0) * SCALE + 2 * MARGIN_Y + LABEL_H, 1)


def sx(x):
    return round((x1 - x) * SCALE + MARGIN_X, 1)    # mirrored: solder-side view


def sy(y):
    return round((y - y0) * SCALE + MARGIN_Y + LABEL_H, 1)


# --- pad dots ---------------------------------------------------------------
dots = "".join(
    f'<circle cx="{sx(p["x"])}" cy="{sy(p["y"])}" r="1.1" class="pad-dot"/>'
    for p in pads
)

# --- wires, lowest z tier first so the physical over/under reads correctly ---
lines = []
for x1s, y1s, x2s, y2s, colour, label, _side, tier in sorted(segs, key=lambda s: s[7]):
    stroke, cls = COLOURS[colour]
    net = label.split()[0]
    geom = f'x1="{sx(x1s)}" y1="{sy(y1s)}" x2="{sx(x2s)}" y2="{sy(y2s)}"'
    if colour == "white":
        # A white jumper on the light-theme board colour is almost invisible;
        # give it a theme-aware casing so it reads in both themes.
        lines.append(
            f'<line {geom} stroke-width="4.0" stroke-linecap="round"'
            f' class="wire-casing"/>'
        )
    lines.append(
        f'<line {geom} stroke="{stroke}" stroke-width="2.6" stroke-linecap="round"'
        f' class="{cls}" data-net="{net}"/>'
    )
wires = "".join(lines)

# --- ref labels above each component's topmost pad --------------------------
tops = {}
for p in pads:
    if p["ref"].startswith("J_TEENSY"):
        continue
    cur = tops.get(p["ref"])
    if cur is None or p["y"] < cur["y"]:
        tops[p["ref"]] = p
labels = "".join(
    f'<text x="{sx(p["x"])}" y="{round(sy(p["y"]) - LABEL_DY, 1)}"'
    f' text-anchor="middle" class="ref-label">{ref}</text>'
    for ref, p in sorted(tops.items())
)

# --- splice into the HTML ---------------------------------------------------
html = HTML.read_text()
new_svg = (
    f'      <svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img"'
    ' aria-label="Back-side wiring diagram of the perfboard, mirrored for soldering,'
    ' wires color-coded by net type">\n'
    f'  <rect x="0" y="0" width="{W}" height="{H}" class="board-bg"/>\n'
    f'  {dots}\n  {wires}\n  {labels}\n</svg>'
)
html, n = re.subn(r'      <svg viewBox=.*?\n</svg>', lambda _m: new_svg, html,
                  count=1, flags=re.S)
assert n == 1, "could not locate the inline diagram <svg> block"
HTML.write_text(html)

print(f"viewBox 0 0 {W} {H}  ({len(pads)} pads, {len(segs)} wires, {len(tops)} labels)")
