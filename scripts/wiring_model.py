"""The perfboard's wiring, derived from pin_map.json + board_model.json.

One place that knows what connects to what. `gen_wiring_guide.py` renders it as
HTML; anything else that needs the connection list should import it rather than
re-deriving the same tables a fourth time.

Nothing here is hand-maintained per-pin: connector pinouts are fixed by the
hardware (the XH2.54 v1.1 standard for S1-S6, the board's own layout for the
rest), and every GPIO destination comes from pin_map.json.

Two names exist for the same wire and both matter. The *signal* name is what the
panel calls it (B3, J1.2, NP1.5, LED2); the *board net* is what the schematic and
the placed jumper footprints call it, which for plain signals is the GPIO itself
(D5, D4, D13, D16). IRQ, LED_* and bus nets use one name for both. Colour hashes
the board net, matching gen_taps.py, so this page and the board agree.
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# --- board grid -------------------------------------------------------------
# The board prints its own column letters and the sequence wraps, so "B" appears
# at both ends and a label alone does not identify a hole -- position does.
SEQ = "F E D C B A Z Y X W V U T S R Q P O N M L K J I H G F E D C B A".split()


def col_letter(x):
    return SEQ[min(max(round(x / 2.54), 1), 32) - 1]


def gref(x, y):
    return f"{col_letter(x)}{round(y / 2.54):02d}"


# --- Teensy sockets ---------------------------------------------------------
# Two 24-pin sockets, pin 1 leftmost in both: row A is the board's row 23, row B
# its row 29. Row B reads GND, D0..D12, 3V3, D24..D32 -- strictly ascending left
# to right; row A's numbering runs *down* in two blocks, which is why "further
# right means a higher pin number" only holds on row B.
ROW_A = ["+5V", "GND", "+3V3", "D23", "D22", "D21", "D20", "D19", "D18", "D17",
         "D16", "D15", "D14", "D13", "GND", "D41", "D40", "D39", "D38", "D37",
         "D36", "D35", "D34", "D33"]
ROW_B = ["GND", "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9",
         "D10", "D11", "D12", "+3V3", "D24", "D25", "D26", "D27", "D28", "D29",
         "D30", "D31", "D32"]

BUS = ("GND", "+3V3", "+5V", "SDA", "SCL")
CB_NAMES = ["ARM", "EN", "SFT", "CONF", "ALT"]
SIGNAL_COLORS = ["green", "white", "orange"]

model = json.load(open(os.path.join(HERE, "board_model.json")))
pad_xy = {(p["ref"], p["pin"]): (round(p["x"], 3), round(p["y"], 3))
          for p in model["pads"]}
pin_map = json.load(open(os.path.join(HERE, "pin_map.json")))

header_pad, header_all = {}, {}
for _row, _ref in ((ROW_A, "J_TEENSY_A"), (ROW_B, "J_TEENSY_B")):
    for _i, _name in enumerate(_row):
        header_pad.setdefault(_name, (_ref, str(_i + 1)))   # first hole on the net
        header_all.setdefault(_name, []).append((_ref, str(_i + 1)))

# The Teensy's I2C bus lives on D18/D19; the schematic calls those nets SDA/SCL
# and gen_pin_map.py keeps them out of the assignable pool for that reason.
for _bus, _gpio in (("SDA", "D18"), ("SCL", "D19")):
    header_pad[_bus] = header_pad[_gpio]
    header_all[_bus] = header_all[_gpio]


def hole(rp):
    return gref(*pad_xy[rp])


def refpin(rp):
    return f"{rp[0]}.{rp[1]}"


# --- connector pinouts ------------------------------------------------------
def _pinouts():
    p = {}
    for i in range(1, 7):
        for pin, net in zip("123456", ["GND", "+3V3", "+5V", "SDA", "SCL", f"IRQ{i}"]):
            p[(f"S{i}", pin)] = net
    for i in range(1, 9):
        p[(f"B{i}", "1")] = "GND"
        p[(f"B{i}", "2")] = f"B{i}"
    for i, name in enumerate(CB_NAMES, 1):
        p[(f"CB{i}", "1")] = f"CB{i}"
        p[(f"CB{i}", "2")] = "GND"
        p[(f"CB{i}", "3")] = f"LED_{name}"
        p[(f"CB{i}", "4")] = "GND"
        p[(f"R{i}", "1")] = f"LED_{name}"
        p[(f"R{i}", "2")] = f"LED{i}"
    for j in ("J1", "J2"):
        for k in range(1, 5):
            p[(j, str(k))] = f"{j}.{k}"
        p[(j, "5")] = "GND"
    for k in range(1, 9):
        p[("NP1", str(k))] = f"NP1.{k}"
    p[("R12", "1")], p[("R12", "2")] = "SDA", "+3V3"
    p[("R13", "1")], p[("R13", "2")] = "SCL", "+3V3"
    for i, net in enumerate(["SDA", "SCL", "GND", "+3V3", "+5V"], 1):
        p[(f"TP{i}", "1")] = net
    return p


PINOUT = _pinouts()


def kind_of(net):
    if net in ("+3V3", "+5V"):
        return "power"
    if net == "GND":
        return "gnd"
    if net in ("SDA", "SCL") or net.startswith("IRQ"):
        return "i2c"
    return "signal"


def board_net(net):
    """What the schematic and the placed jumpers call this net."""
    if net in BUS or net.startswith(("LED_", "IRQ")):
        return net
    return pin_map[net]


def color_of(net):
    """Kit wire colour for a *board* net -- same rule as gen_taps.py."""
    if net in ("+3V3", "+5V"):
        return "red"
    if net == "GND":
        return "blue"
    if net in ("SDA", "SCL") or net.startswith("IRQ"):
        return "yellow"
    h = int(hashlib.md5(net.encode()).hexdigest(), 16)
    return SIGNAL_COLORS[h % len(SIGNAL_COLORS)]


# --- connections ------------------------------------------------------------
def bus_taps(net):
    """Every hole on a bus net, ordered the way a daisy-chain would run."""
    pts = [rp for rp, n in PINOUT.items() if n == net]
    pts += header_all[net]
    return sorted(pts, key=lambda rp: (pad_xy[rp][1], pad_xy[rp][0]))


def connections():
    """Every wire to solder: dicts with net, signal, kind, colour, ends, length.

    Bus nets daisy-chain hole to hole in board order -- bare perfboard has no
    copper between holes, so a shared rail really is one wire per hop.
    Everything else is a single point-to-point run.
    """
    out = []

    def add(signal, a, b):
        net = board_net(signal)
        (ax, ay), (bx, by) = pad_xy[a], pad_xy[b]
        out.append({
            "net": net, "signal": signal, "kind": kind_of(signal),
            "color": color_of(net), "a": a, "b": b,
            "mm": round(abs(ax - bx) + abs(ay - by), 1),
        })

    for net in BUS:
        taps = bus_taps(net)
        for a, b in zip(taps, taps[1:]):
            add(net, a, b)
    seen = set()
    for rp, net in sorted(PINOUT.items()):
        if net in BUS or net in seen:
            continue
        seen.add(net)
        if net.startswith("LED_"):                       # CBn.3 -> Rn.1
            a, b = sorted(r for r, n in PINOUT.items() if n == net)
            add(net, a, b)
        else:
            add(net, rp, header_pad[pin_map[net]])
    return out
