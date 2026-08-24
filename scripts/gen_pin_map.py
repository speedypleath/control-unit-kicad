"""Assign every connector signal to its nearest free Teensy GPIO.

The old map was sequential-by-function (B1-B8 -> D20-D27, NP1 -> D28-D35, ...),
which ignores where anything physically sits on the perfboard: CB5's button ran
86mm across the board to reach D14. There are exactly 40 signals and exactly 40
free GPIOs on the two header rows, so this is a perfect bipartite matching --
solved optimally (Hungarian) against Manhattan distance, which on this board *is*
the wire length, because every jumper routes as an elbow on the hole grid.

Three things constrain the raw optimum:

  * B1-B8 are pinned to header B (the row the owner works from: GND, D0-D12,
    3V3, D24-D32) and assigned *monotonically* along their physical x order,
    which on this mirrored button row is B1 B2 B3 B4 B8 B7 B6 B5 -- so no two
    button wires cross. Header B is the far row from the buttons, so this costs
    wire; it is a deliberate layout choice, not an optimisation result.

  * D13 drives the Teensy's onboard LED through a resistor to GND. As an
    INPUT_PULLUP it reads unreliably (the LED clamps the pin near its forward
    voltage), so D13 is only offered to the nine driven outputs -- NP1's four
    matrix rows and the five LED drives.
  * The optimum is massively degenerate (many assignments hit the same total),
    so a bottleneck sweep picks the min-sum solution with the smallest longest
    wire, and a per-group tidy pass then permutes each connector's own pins --
    at zero cost, since same-column pads are equidistant from a given header
    hole -- so pin order runs with GPIO order instead of scrambled.

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

# Teensy 4.1, socket pin 1 = leftmost (col B). Row A is the perfboard's row 23,
# row B its row 29 -- confirmed against Teensy41.kicad_mod pad geometry and U1's
# pad->net map on the manufactured board.
ROW_A = ["+5V", "GND", "+3V3", "D23", "D22", "D21", "D20", "D19", "D18", "D17",
         "D16", "D15", "D14", "D13", "GND", "D41", "D40", "D39", "D38", "D37",
         "D36", "D35", "D34", "D33"]
ROW_B = ["GND", "D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9",
         "D10", "D11", "D12", "+3V3", "D24", "D25", "D26", "D27", "D28", "D29",
         "D30", "D31", "D32"]

teensy = {}
for i, s in enumerate(ROW_A):
    teensy.setdefault(s, pad[("J_TEENSY_A", str(i + 1))])
for i, s in enumerate(ROW_B):
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
base = [[man(pad[(r, p)], teensy[g]) + (BIG if g == "D13" and io == "in" else 0)
         for g in gpios] for (_, _, r, p, io) in signals]


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


def solve(cap=None):
    c = base if cap is None else [
        [base[i][j] + (BIG * 10 if base[i][j] % BIG > cap + 1e-9 else 0)
         for j in range(40)] for i in range(40)]
    a = hungarian(c)
    real = [man(pad[(signals[i][2], signals[i][3])], teensy[gpios[a[i]]])
            for i in range(40)]
    ok = all(base[i][a[i]] < BIG for i in range(40))
    return a, real, ok


# --- B1-B8: header B, monotonic in x (see docstring) ----------------------
from itertools import combinations

ROWB_GPIOS = [g for g in ROW_B if g[0] == "D"]          # already in x order
bidx = sorted((i for i, s in enumerate(signals) if s[1] == "B"),
              key=lambda i: pad[(signals[i][2], signals[i][3])][0])
oidx = [i for i in range(40) if i not in bidx]
gpos = {g: j for j, g in enumerate(gpios)}


def hung_rest(taken, cap=None):
    """Optimal matching of the 32 non-button signals over the leftover GPIOs.

    With `cap`, any pairing longer than cap is penalised out, so the sweep below
    can find the min-max solution among the min-sum ones (same bottleneck
    tie-break the unconstrained version used).
    """
    free = [j for j in range(40) if j not in taken]
    sub = [[base[i][j] + (BIG * 10 if cap is not None
                          and base[i][j] % BIG > cap + 1e-9 else 0)
            for j in free] for i in oidx]
    a = hungarian(sub)
    real = [man(pad[(signals[oidx[k]][2], signals[oidx[k]][3])],
                teensy[gpios[free[a[k]]]]) for k in range(len(oidx))]
    ok = all(base[oidx[k]][free[a[k]]] < BIG for k in range(len(oidx)))
    return {oidx[k]: free[a[k]] for k in range(len(oidx))}, sum(real), max(real), ok


def full(sub, rest):
    a = [0] * 40
    for i, j in zip(bidx, sub):
        a[i] = gpos[ROWB_GPIOS[j]]
    a.__setitem__  # noqa -- keep flake quiet about the loop below
    for i, j in rest.items():
        a[i] = j
    return a, [man(pad[(signals[i][2], signals[i][3])], teensy[gpios[a[i]]])
               for i in range(40)]


# every strictly-increasing choice of 8 header-B pins, cheapest button cost first
cands = []
for sub in combinations(range(len(ROWB_GPIOS)), 8):
    cands.append((sum(man(pad[(signals[i][2], signals[i][3])],
                          teensy[ROWB_GPIOS[j]]) for i, j in zip(bidx, sub)), sub))
cands.sort()

# pass 1: the minimum achievable total, and every button subset that reaches it
best_total, optimal_subs = None, []
for bcost, sub in cands[:400]:
    taken = {gpos[ROWB_GPIOS[j]] for j in sub}
    rest, rsum, _, ok = hung_rest(taken)
    if not ok:                             # D13 forced onto an input
        continue
    tot = round(bcost + rsum, 6)
    if best_total is None or tot < best_total:
        best_total, optimal_subs = tot, [(bcost, sub)]
    elif tot == best_total:
        optimal_subs.append((bcost, sub))
assert optimal_subs

# pass 2: among those, the one with the shortest longest wire
assign, real = None, None
for cap in sorted({round(man(pad[(r, p)], teensy[g]), 3)
                   for (_, _, r, p, _) in signals for g in gpios}):
    for bcost, sub in optimal_subs:
        bmax = max(man(pad[(signals[i][2], signals[i][3])], teensy[ROWB_GPIOS[j]])
                   for i, j in zip(bidx, sub))
        if bmax > cap + 1e-9:
            continue
        taken = {gpos[ROWB_GPIOS[j]] for j in sub}
        rest, rsum, rmax, ok = hung_rest(taken, cap)
        if ok and rmax <= cap + 1e-9 and abs(bcost + rsum - best_total) < 1e-6:
            assign, real = full(sub, rest)
            break
    if assign:
        break
assert assign is not None

# per-group tidy: within one connector, permute its own GPIOs to run with pin
# order. Free whenever the group's pads share a column (they all do here).
opt = {signals[i][0]: gpios[assign[i]] for i in range(40)}
for grp in {s[1] for s in signals}:
    if grp == "B":            # order is fixed by the monotonic constraint
        continue
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
        inv = sum(1 for a in range(len(perm)) for b in range(a + 1, len(perm))
                  if int(perm[a][1:]) > int(perm[b][1:]))
        key = (round(cost, 6), inv)
        if best is None or key < best[0]:
            best = (key, perm)
    for i, g in zip(idx, best[1]):
        opt[signals[i][0]] = g

final = {s[0]: opt[s[0]] for s in signals}
json.dump(final, open(os.path.join(HERE, "pin_map.json"), "w"), indent=1)

OLD = {"IRQ1": "D15", "IRQ2": "D16", "IRQ3": "D17", "IRQ4": "D39", "IRQ5": "D40",
       "IRQ6": "D41", "B1": "D20", "B2": "D21", "B3": "D22", "B4": "D23",
       "B5": "D24", "B6": "D25", "B7": "D26", "B8": "D27", "CB1": "D10",
       "CB2": "D11", "CB3": "D12", "CB4": "D13", "CB5": "D14", "J1.1": "D0",
       "J1.2": "D1", "J1.3": "D2", "J1.4": "D3", "J2.1": "D4", "J2.2": "D5",
       "J2.3": "D6", "J2.4": "D7", "NP1.1": "D28", "NP1.2": "D29",
       "NP1.3": "D30", "NP1.4": "D31", "NP1.5": "D32", "NP1.6": "D33",
       "NP1.7": "D34", "NP1.8": "D35", "LED1": "D8", "LED2": "D9",
       "LED3": "D36", "LED4": "D37", "LED5": "D38"}

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
