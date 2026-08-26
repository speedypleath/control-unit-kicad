"""Assign every connector signal to its nearest free Teensy GPIO.

The old map was sequential-by-function (B1-B8 -> D20-D27, NP1 -> D28-D35, ...),
which ignores where anything physically sits on the perfboard: CB5's button ran
86mm across the board to reach D14. There are exactly 40 signals and exactly 40
free GPIOs on the two header rows, so this is a perfect bipartite matching --
solved optimally (Hungarian) against Manhattan distance, which on this board *is*
the wire length, because every jumper routes as an elbow on the hole grid.

Three things constrain the raw optimum:

  * B1-B8, J1/J2, LED4 and LED5 are **frozen** to the pins they are physically
    wired to on the built board. For the sixteen button/joystick wires the
    firmware's `kActionButtonPins` / `kJoystickPins` in
    `~/Projects/haptic-console-firmware/lib/TeensyPanelCore/src/TeensyPanelCore.h`
    are the authority; the two lamps are frozen by their holes (R4 L41 -> O29 =
    D13, R5 E41 -> H23 = D29). They are an
    input, not a result: change `FIXED` only when the board is rewired. Both
    firmware arrays are correct exactly as written, including the order of
    `kJoystickPins`' two sub-arrays -- an earlier revision swapped them here to
    stop the joystick wires crossing the board, but that crossing was an artifact
    of having the Teensy's orientation backwards (see SOCKET_A/SOCKET_B) and
    disappeared when the orientation was fixed.

  * D13 drives the Teensy's onboard LED through a resistor to GND. As an
    INPUT_PULLUP it reads unreliably (the LED clamps the pin near its forward
    voltage), so D13 is only offered to the nine driven outputs -- NP1's four
    matrix rows and the five LED drives.
  * The optimum is massively degenerate (many assignments hit the same total),
    so a bottleneck sweep picks the min-sum solution with the smallest longest
    wire, and a per-group tidy pass then permutes each connector's own pins --
    at zero cost, since same-column pads are equidistant from a given header
    hole -- so pin order runs with GPIO order instead of scrambled.

With those 18 frozen this is a plain 22x22 assignment over the leftover GPIOs --
the IRQ, CB, numpad and remaining LED lines -- not the combinatorial
button-subset sweep an earlier revision needed.

Output: scripts/pin_map.json  {signal: gpio}, plus a human-readable table.
"""
import json
import os
from itertools import permutations

HERE = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(os.path.join(HERE, "board_model.json")))
pad = {(p["ref"], p["pin"]): (p["x"], p["y"]) for p in M["pads"]}

SEQ = "F E D C B A Z Y X W V U T S R Q P O N M L K J I H G F E D C B A".split()
def gref(x, y):
    return f"{SEQ[round(x / 2.54) - 1]}{round(y / 2.54):02d}"

# Teensy 4.1's two pin rows, read from the module itself (USB end first).
ROW_A = ["+5V", "GND", "+3V3", "D23", "D22", "D21", "D20", "D19", "D18", "D17",
         "D16", "D15", "D14", "D13", "GND", "D41", "D40", "D39", "D38", "D37",
         "D36", "D35", "D34", "D33"]
ROW_B = ["GND", "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9",
         "D10", "D11", "D12", "+3V3", "D24", "D25", "D26", "D27", "D28", "D29",
         "D30", "D31", "D32"]

# ...and how those rows land in the board's two sockets, socket pin 1 in hole
# B23/B29. Ground truth, read straight off the board (owner, 2026-08-26): the
# Vin/GND/3.3V trio -- the three pins at the module's USB end -- sits in
# B29 A29 Z29. So row 29 (J_TEENSY_B, the owner's rail "B") carries ROW_A in its
# own order, and row 23 (J_TEENSY_A) carries ROW_B in its own order; neither is
# reversed. D32 stays on row 23, now at its far end (E23).
# Two earlier revisions got this wrong in different ways -- the rows swapped,
# then both rows reversed. Only ever change it from a direct reading of the
# physical board, never from "the resulting map looks sensible": every artifact
# downstream is generated from this, so any orientation looks self-consistent.
SOCKET_A = list(ROW_B)                       # board row 23
SOCKET_B = list(ROW_A)                       # board row 29

teensy = {}
for i, s in enumerate(SOCKET_A):
    teensy.setdefault(s, pad[("J_TEENSY_A", str(i + 1))])
for i, s in enumerate(SOCKET_B):
    teensy.setdefault(s, pad[("J_TEENSY_B", str(i + 1))])

# (label, group, connector ref, connector pin, direction)
signals = []
for i in range(1, 7):
    signals.append((f"IRQ{i}", "IRQ", f"S{i}", "6", "in"))
for i in range(1, 9):
    signals.append((f"B{i}", "B", f"B{i}", "2", "in"))
for i in range(1, 6):
    signals.append((f"CB{i}", "CB", f"CB{i}", "1", "in"))
for i in range(1, 5):
    signals.append((f"J1.{i}", "J1", "J1", str(i), "in"))
for i in range(1, 5):
    signals.append((f"J2.{i}", "J2", "J2", str(i), "in"))
for i in range(1, 5):
    signals.append((f"NP1.{i}", "NP1c", "NP1", str(i), "in"))
for i in range(5, 9):
    signals.append((f"NP1.{i}", "NP1r", "NP1", str(i), "out"))
for i in range(1, 6):
    signals.append((f"LED{i}", "LED", f"R{i}", "2", "out"))

gpios = [g for g in sorted((s for s in teensy if s[0] == "D"),
                           key=lambda s: int(s[1:])) if g not in ("D18", "D19")]
assert len(signals) == len(gpios) == 40

def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

BIG = 1e6

# As-built wiring -- soldered, not up for optimisation. Action buttons on the
# D0-D12/D24-D32 row, joysticks on the owner's "B" rail (D13-D23/D33-D41).
# B1/B2 spot-checked against the physical board (owner, 2026-08-26): B1 in hole
# A23, B2 in Z23, which under the corrected socket mapping above read D0/D1 --
# exactly what the firmware says. That is the check to repeat if this is ever
# doubted again: read a hole off the board, not the resulting map.
FIXED = {"B1": "D0", "B2": "D1", "B3": "D4", "B4": "D8",
         "B5": "D32", "B6": "D30", "B7": "D26", "B8": "D9",
         # kJoystickPins' order is taken literally, and it is the uncrossed one:
         # the D22/D21/D20/D16 stick lands in X29 W29 V29 R29, right under J1
         # (board col 9), 109.5mm against 216.1mm for the other pairing. An
         # earlier revision swapped the two sticks here; that was compensating
         # for the backwards socket model, not for anything on the board, and it
         # came back out once the orientation was fixed. The firmware is correct
         # as written -- do not "fix" it to match a swapped map.
         "J1.1": "D22", "J1.2": "D21", "J1.3": "D20", "J1.4": "D16",
         "J2.1": "D37", "J2.2": "D39", "J2.3": "D40", "J2.4": "D41",
         # The two soldered lamp jumpers. R5 went in E41 -> H23 (H23 = D29).
         # R4 first went into R29, which is D16 = J1.4 and already taken; the
         # owner moved it five holes along to O29 = D13 (2026-08-26), which is
         # where the solver had put LED4 anyway, so freezing it costs nothing.
         # D13 drives the onboard LED -- legal here precisely because LED4 is a
         # driven output, see `forbidden` below.
         "LED4": "D13", "LED5": "D29"}
JOY_RAIL = {g for g in ROW_A if g[0] == "D"}   # D13-D23 + D33-D41, owner's "B"
assert {g for s, g in FIXED.items() if s[0] == "B"} <= set(ROW_B)
assert {g for s, g in FIXED.items() if s[0] == "J"} <= JOY_RAIL


def forbidden(lab, grp, io, g):
    """True if signal `lab` may not use GPIO `g` (see the docstring's three)."""
    if g == "D13" and io == "in":
        return True                       # onboard LED clamps the pull-up
    return False


base = [[man(pad[(r, p)], teensy[g]) + (BIG if forbidden(lab, grp, io, g) else 0)
         for g in gpios] for (lab, grp, r, p, io) in signals]


def hungarian(a):
    n, m = len(a), len(a[0])
    INF = float("inf")
    u = [0.0] * (n + 1); v = [0.0] * (m + 1); p = [0] * (m + 1); way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i; j0 = 0
        minv = [INF] * (m + 1); used = [False] * (m + 1)
        while True:
            used[j0] = True; i0 = p[j0]; delta = INF; j1 = -1
            for j in range(1, m + 1):
                if not used[j]:
                    cur = a[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur; way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]; j1 = j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta; v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]; p[j0] = p[j1]; j0 = j1
            if j0 == 0:
                break
    res = [0] * n
    for j in range(1, m + 1):
        if p[j]:
            res[p[j] - 1] = j - 1
    return res


# --- buttons and joysticks frozen, the rest matched over what is left ------
gpos = {g: j for j, g in enumerate(gpios)}
bidx = {i for i, s in enumerate(signals) if s[0] in FIXED}
oidx = [i for i in range(40) if i not in bidx]
taken = {gpos[FIXED[signals[i][0]]] for i in bidx}
assert len(taken) == len(FIXED)
free = [j for j in range(40) if j not in taken]


def hung_rest(cap=None):
    """Optimal matching of the 24 unfrozen signals over the leftover GPIOs.

    With `cap`, any pairing longer than cap is penalised out, so the sweep below
    can find the min-max solution among the min-sum ones.
    """
    sub = [[base[i][j] + (BIG * 10 if cap is not None
                          and base[i][j] % BIG > cap + 1e-9 else 0)
            for j in free] for i in oidx]
    a = hungarian(sub)
    real = [man(pad[(signals[oidx[k]][2], signals[oidx[k]][3])],
                teensy[gpios[free[a[k]]]]) for k in range(len(oidx))]
    ok = all(base[oidx[k]][free[a[k]]] < BIG for k in range(len(oidx)))
    return {oidx[k]: free[a[k]] for k in range(len(oidx))}, sum(real), max(real), ok


def full(rest):
    a = [0] * 40
    for i in bidx:
        a[i] = gpos[FIXED[signals[i][0]]]
    for i, j in rest.items():
        a[i] = j
    return a, [man(pad[(signals[i][2], signals[i][3])], teensy[gpios[a[i]]])
               for i in range(40)]


# pass 1: the minimum achievable total over the free signals
rest0, best_total, _, ok0 = hung_rest()
assert ok0, "no feasible assignment -- a forbidden pin was forced"

# pass 2: among the min-sum solutions, the one with the shortest longest wire
assign, real = None, None
for cap in sorted({round(man(pad[(r, p)], teensy[g]), 3)
                   for (_, _, r, p, _) in signals for g in gpios}):
    rest, rsum, rmax, ok = hung_rest(cap)
    if ok and rmax <= cap + 1e-9 and abs(rsum - best_total) < 1e-6:
        assign, real = full(rest)
        break
assert assign is not None

# per-group tidy: within one connector, permute its own GPIOs to run with pin
# order. Free whenever the group's pads share a column (they all do here).
#
# "Run with pin order" has to be judged by the header hole's *physical* x
# position, not its GPIO number -- neither socket's GPIO numbering runs with
# its holes (see SOCKET_A/SOCKET_B above: row 23 runs D0..D12 then D24..D32,
# row 29 counts *down* D23..D13 then D41..D33), so an inversion count keyed on
# int(gpio) silently prefers a physically-crossing layout. And
# either monotonic direction (ascending or descending physical x) avoids a
# crossing equally well, so score against whichever direction is cheaper
# instead of only rewarding ascending order.
opt = {signals[i][0]: gpios[assign[i]] for i in range(40)}
for grp in {s[1] for s in signals}:
    if any(s[0] in FIXED for s in signals if s[1] == grp):
        continue              # frozen groups: permuting would unfreeze them
    idx = [i for i, s in enumerate(signals) if s[1] == grp]
    if len(idx) > 8:
        continue
    have = [opt[signals[i][0]] for i in idx]
    cur = sum(man(pad[(signals[i][2], signals[i][3])], teensy[opt[signals[i][0]]])
              for i in idx)
    best = None
    for perm in permutations(have):
        cost = sum(man(pad[(signals[i][2], signals[i][3])], teensy[g])
                   for i, g in zip(idx, perm))
        if cost > cur + 1e-9:
            continue
        xs = [teensy[g][0] for g in perm]
        asc = sum(1 for a in range(len(xs)) for b in range(a + 1, len(xs)) if xs[a] > xs[b])
        desc = sum(1 for a in range(len(xs)) for b in range(a + 1, len(xs)) if xs[a] < xs[b])
        inv = min(asc, desc)
        key = (round(cost, 6), inv)
        if best is None or key < best[0]:
            best = (key, perm)
    for i, g in zip(idx, best[1]):
        opt[signals[i][0]] = g

final = {s[0]: opt[s[0]] for s in signals}
json.dump(final, open(os.path.join(HERE, "pin_map.json"), "w"), indent=1)

# The map the firmware currently ships (TeensyPanelCore.h) -- the baseline the
# delta column below is measured against. Its B/J entries are FIXED above.
OLD = {"IRQ1": "D23", "IRQ2": "D2", "IRQ3": "D17", "IRQ4": "D14", "IRQ5": "D38",
       "IRQ6": "D33", "B1": "D0", "B2": "D1", "B3": "D4", "B4": "D8",
       "B5": "D32", "B6": "D30", "B7": "D26", "B8": "D9", "CB1": "D3",
       "CB2": "D6", "CB3": "D11", "CB4": "D25", "CB5": "D28", "J1.1": "D22",
       "J1.2": "D21", "J1.3": "D20", "J1.4": "D16", "J2.1": "D37", "J2.2": "D39",
       "J2.3": "D40", "J2.4": "D41", "NP1.1": "D29", "NP1.2": "D24",
       "NP1.3": "D7", "NP1.4": "D15", "NP1.5": "D13", "NP1.6": "D36",
       "NP1.7": "D35", "NP1.8": "D34", "LED1": "D5", "LED2": "D10",
       "LED3": "D12", "LED4": "D27", "LED5": "D31"}

print(f"{'signal':7} {'pad':7} {'hole':5} | {'old':4} {'hole':5} {'mm':>6} | "
      f"{'new':4} {'hole':5} {'mm':>6}   delta")
told = tnew = 0.0
for (lab, _, r, p, _) in signals:
    xy = pad[(r, p)]
    do = man(xy, teensy[OLD[lab]]); dn = man(xy, teensy[final[lab]])
    told += do; tnew += dn
    print(f"{lab:7} {r + '.' + p:7} {gref(*xy):5} | {OLD[lab]:4} "
          f"{gref(*teensy[OLD[lab]]):5} {do:6.1f} | {final[lab]:4} "
          f"{gref(*teensy[final[lab]]):5} {dn:6.1f} {do - dn:+7.1f}")
print(f"\ntotal {told:.1f} -> {tnew:.1f} mm  ({100 * (told - tnew) / told:.0f}% shorter), "
      f"longest {max(man(pad[(r, p)], teensy[OLD[lab]]) for lab, _, r, p, _ in signals):.1f}"
      f" -> {max(man(pad[(r, p)], teensy[final[lab]]) for lab, _, r, p, _ in signals):.1f} mm")
print("wrote scripts/pin_map.json")
