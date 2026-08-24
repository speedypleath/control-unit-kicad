"""Rebuild the perfboard's wiring ground truth from scripts/pin_map.json.

Outputs (cwd = scripts/):
  taps_clean.json  {net: [[x, y], ...]}   every pad the net touches
  net_meta.json    {net: {color, label, endpoints}}  metadata gen_segments_v3 needs

The connector side of the board never moves -- what a remap changes is only which
Teensy header hole each signal lands in. So: keep every bus tap and every
CB->R LED tap exactly as they are, and re-point each signal net at the header pad
for its new GPIO. Net names follow the GPIO (IRQ nets keep their IRQ name).

The Teensy sits in two 24-pin sockets, J_TEENSY_A (board row 23) and J_TEENSY_B
(row 29), pin 1 leftmost in both; ROW_A/ROW_B below are those sockets read
left to right, and are the same lists gen_pin_map.py optimises against.
"""
import json
import hashlib
from collections import defaultdict

ROW_A = ["+5V", "GND", "+3V3", "D23", "D22", "D21", "D20", "D19", "D18", "D17",
         "D16", "D15", "D14", "D13", "GND", "D41", "D40", "D39", "D38", "D37",
         "D36", "D35", "D34", "D33"]
ROW_B = ["GND", "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9",
         "D10", "D11", "D12", "+3V3", "D24", "D25", "D26", "D27", "D28", "D29",
         "D30", "D31", "D32"]

# perfboard (ref, pin) -> the signal name gen_pin_map.py assigns a GPIO to
SIGNAL_OF_PAD = {}
for i in range(1, 7):
    SIGNAL_OF_PAD[(f"S{i}", "6")] = f"IRQ{i}"
for i in range(1, 9):
    SIGNAL_OF_PAD[(f"B{i}", "2")] = f"B{i}"
for i in range(1, 6):
    SIGNAL_OF_PAD[(f"CB{i}", "1")] = f"CB{i}"
    SIGNAL_OF_PAD[(f"R{i}", "2")] = f"LED{i}"
for i in range(1, 5):
    SIGNAL_OF_PAD[("J1", str(i))] = f"J1.{i}"
    SIGNAL_OF_PAD[("J2", str(i))] = f"J2.{i}"
for i in range(1, 9):
    SIGNAL_OF_PAD[("NP1", str(i))] = f"NP1.{i}"

BUS = ["GND", "+3V3", "+5V", "SCL", "SDA"]
SIGNAL_COLORS = ["green", "white", "orange"]


def color_of(net):
    if net in ("+3V3", "+5V"):
        return "red"
    if net == "GND":
        return "blue"
    if net in ("SDA", "SCL") or net.startswith("IRQ"):
        return "yellow"
    h = int(hashlib.md5(net.encode()).hexdigest(), 16)
    return SIGNAL_COLORS[h % len(SIGNAL_COLORS)]


model = json.load(open("board_model.json"))
pad_xy = {(p["ref"], p["pin"]): (round(p["x"], 3), round(p["y"], 3)) for p in model["pads"]}
xy_pad = {v: k for k, v in pad_xy.items()}

header_pad = {}
for row, ref in ((ROW_A, "J_TEENSY_A"), (ROW_B, "J_TEENSY_B")):
    for i, name in enumerate(row):
        header_pad.setdefault(name, (ref, str(i + 1)))

pin_map = json.load(open("pin_map.json"))
old_taps = json.load(open("taps_clean.json"))

new_taps = defaultdict(list)
new_meta = {}


def refpin(rp):
    return f"{rp[0]}.{rp[1]}"


for net, pts in old_taps.items():
    rps = [xy_pad[(round(x, 3), round(y, 3))] for x, y in pts]
    if net in BUS:
        new_net, new_rps = net, rps
    else:
        sig = next((SIGNAL_OF_PAD[rp] for rp in rps if rp in SIGNAL_OF_PAD), None)
        if sig is None:                       # LED_* : CB pin 3 -> resistor pin 1
            new_net, new_rps = net, rps
        else:
            gpio = pin_map[sig]
            new_net = sig if sig.startswith("IRQ") else gpio
            new_rps = [rp for rp in rps if rp[0] not in ("J_TEENSY_A", "J_TEENSY_B")]
            new_rps.append(header_pad[gpio])
    new_taps[new_net] = [list(pad_xy[rp]) for rp in new_rps]
    new_meta[new_net] = {
        "color": color_of(new_net),
        "label": f"{new_net} {refpin(new_rps[0])}->{refpin(new_rps[1])}",
        "endpoints": [refpin(new_rps[0]), refpin(new_rps[1])],
    }

json.dump(dict(sorted(new_taps.items())), open("taps_clean.json", "w"), indent=1)
json.dump(dict(sorted(new_meta.items())), open("net_meta.json", "w"), indent=1)

assert len(new_taps) == len(old_taps), (len(new_taps), len(old_taps))
print(f"nets {len(new_taps)}  taps {sum(len(v) for v in new_taps.values())}")
used = [rp for n in new_taps for rp in
        [xy_pad[(round(x, 3), round(y, 3))] for x, y in new_taps[n]]]
assert len(used) == len(set(used)), "a pad is claimed by two nets"
print("header pads used:", sum(1 for rp in used if rp[0].startswith("J_TEENSY")))
