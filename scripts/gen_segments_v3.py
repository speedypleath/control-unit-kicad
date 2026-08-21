"""Regenerate the perfboard's jumper wiring with no visible wire overlaps.

Inputs (cwd):  taps_clean.json, board_model.json, reconstructed_segments.json.
Output:        segments_v3.json (place_wire.py 8-field schema), all on the back.

The wires are decorative footprints from ~/KiCad/jumper-wires-kicad -- no pads, no
nets, invisible to DRC. What they have to be is *legible*: two wires must never
merge into one another visually.

Two things make a wire pair merge, and they need different fixes:
  - collinear overlap: same row/column, overlapping span. No z-tier can hide this,
    so it must be prevented while routing. A span registry (row/col -> list of
    (net, lo, hi, tier)) is the single source of truth; emit() rejects a leg that
    would overlap another net at the same tier, so a clean run proves the output is
    overlap-free by construction.
  - mid-span crossing: unavoidable on a board this dense, and fine as long as the
    two wires sit at different heights. Handled after routing by colouring the
    net-conflict graph and using the colour as the z tier.

Routing
  - Buses (GND/+3V3/+5V/SCL/SDA): Manhattan MST over their taps -- same-row taps
    chain straight along the connector's pin row, giving the classic rail.
  - Everything else: A* over the hole grid, one straight leg per move, with a turn
    penalty (fewer jogs) and a crossing penalty (fewer conflict-graph edges, hence
    fewer tiers and a flatter stack).
  - Legs may run along pad rows/columns provided they don't pass strictly through a
    pad: only 4 of ~36 columns are pad-free, so a pad-free-lanes-only router has
    nowhere to turn and leaves most nets unroutable.

Verify the output with verify_v3.py (connectivity, tap coverage, bounds) and
analyze_conflicts.py (overlap/crossing census) before placing it on a board.
"""
import json
import math
import heapq
from collections import defaultdict, Counter

GRID = 2.54
EPS = 0.05

# taps_clean.json, not taps.json: the latter was derived from the OLD wire
# geometry and so includes elbow corner points as if they were taps -- some of
# which coincidentally sit on an unrelated component's pad. Routing to those
# invents connections that don't exist. taps_clean.json is rebuilt from each
# wire label's "REF.PIN->REF.PIN" text against real pad positions (157 taps,
# 50 nets), which is the actual ground truth.
taps = json.load(open("taps_clean.json"))
model = json.load(open("board_model.json"))
segs_old = json.load(open("reconstructed_segments.json"))

pads = {}
for p in model["pads"]:
    pads.setdefault((round(p["x"], 3), round(p["y"], 3)), (p["ref"], p["pin"]))
pad_by_refpin = {(r, p): (x, y) for (x, y), (r, p) in pads.items()}
pad_list = list(pads.keys())

def net_of(s): return s[5].split()[0]

net_color, net_label, net_endpoints = {}, {}, {}
for s in segs_old:
    n = net_of(s)
    net_color[n] = s[4]
    base = s[5].rsplit(" (", 1)[0]
    net_label[n] = base
    a, b = base.split("->")
    net_endpoints[n] = (a, b)

net_points = {}
for n in taps:
    src, dst = net_endpoints[n]
    # strip any leading net-name token, then split at '.'
    src_clean = src.split(None, 1)[1] if " " in src else src
    dst_clean = dst.split(None, 1)[1] if " " in dst else dst
    src_ref, src_pin = src_clean.rsplit(".", 1)
    dst_ref, dst_pin = dst_clean.rsplit(".", 1)
    net_points[n] = [pad_by_refpin[(src_ref, src_pin)], pad_by_refpin[(dst_ref, dst_pin)]]

BUS_NETS = ["GND", "+3V3", "+5V", "SCL", "SDA"]


def quant(v): return round(v * 10) / 10

# ---- pad-clearance predicates --------------------------------------------------
# Pads indexed by the grid line they sit on, so a clearance test scans only the
# handful of pads on that one row/column instead of all 157 every time. The
# router calls these tens of thousands of times per net, so the linear scan this
# replaces was the difference between seconds and minutes per run.
row_pads = defaultdict(list)
col_pads = defaultdict(list)
for (px, py) in pad_list:
    row_pads[quant(py)].append(px)
    col_pads[quant(px)].append(py)
for d in (row_pads, col_pads):
    for k in d:
        d[k].sort()


def clear_h(y, xa, xb):
    """No pad strictly between xa and xb on row y."""
    lo, hi = min(xa, xb), max(xa, xb)
    return not any(lo + EPS < px < hi - EPS for px in row_pads.get(quant(y), ()))


def clear_v(x, ya, yb):
    lo, hi = min(ya, yb), max(ya, yb)
    return not any(lo + EPS < py < hi - EPS for py in col_pads.get(quant(x), ()))

# ---- free lanes (no pads anywhere on the line) ---------------------------------
def all_grid(lo, hi):
    return [round(round(v / GRID) * GRID, 3)
            for v in range(int(math.floor(lo / GRID)), int(math.ceil(hi / GRID)) + 1)]

# Keep routing lanes a wire-radius clear of the board outline. A wire centred
# exactly on the edge column (x=0) is "in bounds" by its centreline but its ~0.4mm
# tube still overhangs the edge in a render, which reads as overflow.
EDGE_MARGIN = GRID
BB = model["bbox"]
free_rows = set(all_grid(BB[1] + EDGE_MARGIN, BB[3] - EDGE_MARGIN))
free_cols = set(all_grid(BB[0] + EDGE_MARGIN, BB[2] - EDGE_MARGIN))
for (px, py) in pad_list:
    free_rows.discard(round(round(py / GRID) * GRID, 3))
    free_cols.discard(round(round(px / GRID) * GRID, 3))
free_rows, free_cols = sorted(free_rows), sorted(free_cols)

# ---- span registry ----------------------------------------------------------------
row_spans = defaultdict(list)
col_spans = defaultdict(list)
violations = []

out = []


def orient_seg(seg):
    """(axis, lo, hi, line) for an emitted segment."""
    x1, y1, x2, y2 = seg[:4]
    if abs(y2 - y1) < EPS:
        return "H", min(x1, x2), max(x1, x2), y1
    return "V", min(y1, y2), max(y1, y2), x1


def emit(net, p1, p2, tier, allow_dup=False):
    x1, y1 = round(p1[0], 3), round(p1[1], 3)
    x2, y2 = round(p2[0], 3), round(p2[1], 3)
    if abs(x1-x2) < EPS and abs(y1-y2) < EPS:
        return False
    if abs(y1-y2) < EPS:
        spans, key, lo, hi = row_spans, quant(y1), min(x1, x2), max(x1, x2)
    else:
        spans, key, lo, hi = col_spans, quant(x1), min(y1, y2), max(y1, y2)
    # Check for same-tier conflicts only (different tiers can overlap)
    for (n2, l2, h2, t2) in spans[key]:
        if t2 == tier and min(hi, h2) - max(lo, l2) > EPS:
            if n2 != net:
                violations.append((net, "conflict", key, lo, hi, f"vs {n2}@tier{t2}"))
                return False
            elif not allow_dup:
                violations.append((net, "dup", key, lo, hi, f"vs self@tier{t2}"))
                return False
    spans[key].append((net, lo, hi, tier))
    out.append([x1, y1, x2, y2, net_color[net], net_label[net], "back", tier])
    return True


def leg_key(p1, p2):
    """(spans_dict, line_key, lo, hi) for a leg, or None if degenerate/diagonal."""
    x1, y1 = round(p1[0], 3), round(p1[1], 3)
    x2, y2 = round(p2[0], 3), round(p2[1], 3)
    if abs(x1 - x2) < EPS and abs(y1 - y2) < EPS:
        return None
    if abs(y1 - y2) < EPS:
        return (row_spans, quant(y1), min(x1, x2), max(x1, x2))
    return (col_spans, quant(x1), min(y1, y2), max(y1, y2))


def try_emit_path(net, legs, tier):
    """Validate EVERY leg of a route against the registry (plus the legs already
    pending in this same route) before committing any of it. Returns True only if
    the whole route lands; on failure nothing is written, so the caller can retry
    the same net on a different tier without leaving half a route behind."""
    pending = []
    for p1, p2 in legs:
        lk = leg_key(p1, p2)
        if lk is None:
            continue
        spans, key, lo, hi = lk
        for (n2, l2, h2, t2) in spans[key]:
            if t2 == tier and n2 != net and min(hi, h2) - max(lo, l2) > EPS:
                return False
        for (sd, k2, l2, h2) in pending:
            if sd is spans and k2 == key and min(hi, h2) - max(lo, l2) > EPS:
                return False
        pending.append((spans, key, lo, hi))
    if not pending:
        return False
    for (p1, p2) in legs:
        if leg_key(p1, p2) is not None:
            emit(net, p1, p2, tier, allow_dup=True)
    return True

# ---- 1. buses -----------------------------------------------------------------------
def bus_leg_cols(x_target, ya, yb, limit=12):
    """Candidate columns for a bus vertical leg: pad-clear over [ya,yb], ranked by
    distance from x_target. Span conflicts are left to try_emit_path so a rejected
    column simply falls through to the next candidate."""
    cands = sorted(set(free_cols) | {round(round(px / GRID) * GRID, 3) for (px, py) in pad_list},
                   key=lambda c: abs(c - x_target))
    return [c for c in cands if clear_v(c, ya, yb)][:limit]

bus_failed = []

def route_bus(net):
    ts = sorted(set((round(x, 3), round(y, 3)) for x, y in taps[net]))
    parent = list(range(len(ts)))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    edges = sorted((abs(ts[i][0]-ts[j][0]) + abs(ts[i][1]-ts[j][1]), i, j)
                   for i in range(len(ts)) for j in range(i+1, len(ts)))
    for d, i, j in edges:
        if find(i) == find(j):
            continue
        parent[find(i)] = find(j)
        a, b = ts[i], ts[j]
        ax, ay, bx, by = a[0], a[1], b[0], b[1]
        if abs(ay - by) < EPS or abs(ax - bx) < EPS:
            if try_emit_path(net, [(a, b)], 0):
                continue
            if abs(ax - bx) < EPS and abs(ay - by) < EPS:
                continue  # coincident taps (two pads on the same hole)
        # Straight run blocked (or the pair isn't axis-aligned): detour through a
        # pad-clear column. Try progressively further columns rather than trusting
        # the first geometric candidate -- the nearest clear column may already be
        # claimed by another bus on the same tier.
        placed = False
        for col in bus_leg_cols(bx, ay, by) + bus_leg_cols(ax, ay, by):
            legs = [(a, (col, ay)), ((col, ay), (col, by)), ((col, by), b)]
            if try_emit_path(net, legs, 0):
                placed = True
                break
        if not placed:
            path = dijkstra(a, b, net, 0)
            if path and try_emit_path(net, compress(path), 0):
                continue
            bus_failed.append((net, a, b))


# ---- 2. signals: Dijkstra over free lanes ---------------------------------------------
TURN = 25.0
CROSS_PENALTY = 40.0

def span_free(spans_dict, line_key, lo, hi, net, tier):
    """True if no OTHER net on the SAME tier has a span overlapping [lo, hi] on this line."""
    for (n2, l2, h2, t2) in spans_dict.get(line_key, []):
        if t2 == tier and n2 != net and min(hi, h2) - max(lo, l2) > EPS:
            return False
    return True

# Routable lines = the nominal 2.54mm hole grid PLUS every line a pad actually
# sits on. Not all pads land on the grid (JST rows sit at y=15.44 where the grid
# says 15.24), and routing only on grid lines forced a 0.2mm hop off each such pad
# -- a stub too short to be a real wire, which the cleanup then deleted, silently
# disconnecting the net from its own pad.
def in_margin(v, lo, hi):
    return lo + EDGE_MARGIN - EPS <= v <= hi - EDGE_MARGIN + EPS


ALL_ROWS = sorted(v for v in (set(free_rows)
                              | {round(round(py / GRID) * GRID, 3) for (px, py) in pad_list}
                              | {round(py, 3) for (px, py) in pad_list})
                  if in_margin(v, BB[1], BB[3]))
ALL_COLS = sorted(v for v in (set(free_cols)
                              | {round(round(px / GRID) * GRID, 3) for (px, py) in pad_list}
                              | {round(px, 3) for (px, py) in pad_list})
                  if in_margin(v, BB[0], BB[2]))

def crossings(kind, line, a, b, net):
    """How many already-committed segments of OTHER nets this leg would cross.
    Used as a routing cost so the router prefers detours over pile-ups: every
    crossing it avoids is one less edge in the tier-colouring conflict graph, and
    fewer graph colours means wires stack a millimetre or two above the board
    instead of seven."""
    lo, hi = (a, b) if a <= b else (b, a)
    n = 0
    for seg in out:
        if seg[5].split()[0] == net:
            continue
        o = orient_seg(seg)
        if o[0] == kind:
            continue
        if kind == "H":
            if lo + EPS < o[3] < hi - EPS and o[1] + EPS < line < o[2] - EPS:
                n += 1
        else:
            if lo + EPS < o[3] < hi - EPS and o[1] + EPS < line < o[2] - EPS:
                n += 1
    return n


def leg_ok(kind, line, a, b, net, tier):
    """A candidate leg is usable if it clears intermediate pads AND no other net
    already owns an overlapping span on this line at this tier."""
    lo, hi = (a, b) if a <= b else (b, a)
    if kind == "H":
        return clear_h(line, lo, hi) and span_free(row_spans, quant(line), lo, hi, net, tier)
    return clear_v(line, lo, hi) and span_free(col_spans, quant(line), lo, hi, net, tier)


def dijkstra(start, end, net, tier):
    """Shortest turn-penalised Manhattan route over the WHOLE 2.54mm hole grid.

    Nodes are (point, axis-just-travelled); every move is one straight leg that
    must pass leg_ok. Restricting intermediate hops to pad-free lanes (an earlier
    design) cannot work on this board -- only 4 of 36 columns and 14 of 54 rows
    are pad-free, and they all hug the edges, so most nets had no legal turn
    anywhere near them. Legs may run along pad rows/columns as long as they don't
    pass strictly through a pad.
    """
    sx, sy = round(start[0], 3), round(start[1], 3)
    ex, ey = round(end[0], 3), round(end[1], 3)
    if (abs(sx - ex) < EPS and leg_ok("V", sx, sy, ey, net, tier)) or \
       (abs(sy - ey) < EPS and leg_ok("H", sy, sx, ex, net, tier)):
        return [(sx, sy), (ex, ey)]

    def h(x, y):
        return abs(x - ex) + abs(y - ey)

    startk = ((sx, sy), "S")
    dist = {startk: 0.0}
    prev = {}
    pq = [(h(sx, sy), 0.0, startk)]
    goal = None
    while pq:
        _, d, key = heapq.heappop(pq)
        if d > dist.get(key, float("inf")):
            continue
        (x, y), axis = key
        if abs(x - ex) < EPS and abs(y - ey) < EPS:
            goal = key
            break
        for naxis in ("H", "V"):
            if naxis == axis:
                continue  # consecutive same-axis legs would just be one leg
            lines = ALL_COLS if naxis == "H" else ALL_ROWS
            for t in lines:
                if abs(t - (x if naxis == "H" else y)) < EPS:
                    continue
                if naxis == "H":
                    if not leg_ok("H", y, x, t, net, tier):
                        continue
                    nxt, step = ((t, y), "H"), abs(t - x)
                    xc = crossings("H", y, x, t, net)
                else:
                    if not leg_ok("V", x, y, t, net, tier):
                        continue
                    nxt, step = ((x, t), "V"), abs(t - y)
                    xc = crossings("V", x, y, t, net)
                nd = d + step + (0.0 if axis == "S" else TURN) + xc * CROSS_PENALTY
                if nd < dist.get(nxt, float("inf")):
                    dist[nxt] = nd
                    prev[nxt] = key
                    heapq.heappush(pq, (nd + h(*nxt[0]), nd, nxt))
    if goal is None:
        return None
    pts = []
    k = goal
    while k != startk:
        pts.append(k[0])
        k = prev[k]
    pts.append(startk[0])
    pts.reverse()
    return pts


def compress(path):
    merged = []
    for p, q in zip(path, path[1:]):
        if abs(p[0]-q[0]) < EPS and abs(p[1]-q[1]) < EPS:
            continue
        if merged and (
            (abs(merged[-1][1][0]-merged[-1][0][0]) < EPS and abs(q[0]-p[0]) < EPS
             and abs(merged[-1][1][1]-p[1]) < EPS) or
            (abs(merged[-1][1][1]-merged[-1][0][1]) < EPS and abs(q[1]-p[1]) < EPS
             and abs(merged[-1][1][0]-p[0]) < EPS)):
            merged[-1] = (merged[-1][0], q)
        else:
            merged.append((p, q))
    return merged

# Buses run first so they claim the straight rails; deferred to here because
# route_bus falls back to the A* router defined above.
for net in BUS_NETS:
    route_bus(net)

sig_nets = [n for n in taps if n not in BUS_NETS]
sig_nets.sort(key=lambda n: (min(p[1] for p in net_points[n]),
                             min(p[0] for p in net_points[n])))

MAX_SIGNAL_TIER = 6

unroutable = []
net_tier = {}
for net in sig_nets:
    a, b = net_points[net]
    # Try the lowest tier that fits. Routing and validation both depend on the
    # tier (the span registry only rejects same-tier overlaps), so a net that
    # can't fit at tier 1 often routes cleanly one tier up instead of failing.
    for tier in range(1, MAX_SIGNAL_TIER + 1):
        path = dijkstra(a, b, net, tier)
        if path is None:
            continue
        if try_emit_path(net, compress(path), tier):
            net_tier[net] = tier
            break
    else:
        unroutable.append(net)

# ---- 3. final tier assignment: colour the net-conflict graph -----------------------
# Routing tiers above were only a lane-allocation device. What actually matters
# visually is that two DIFFERENT nets never share a tier where their wires touch --
# whether by running along the same line (collinear overlap) or by crossing
# mid-span. Bumping one segment's tier after the fact could silently recreate a
# collinear overlap at the tier it moved to, so instead build the conflict graph
# over whole nets and greedily colour it; the colour is the tier.
def touches(a, b):
    oa, ob = orient_seg(a), orient_seg(b)
    if oa[0] == ob[0]:
        return abs(oa[3] - ob[3]) < EPS and min(oa[2], ob[2]) - max(oa[1], ob[1]) > EPS
    h, v = (oa, ob) if oa[0] == "H" else (ob, oa)
    return h[1] + EPS < v[3] < h[2] - EPS and v[1] + EPS < h[3] < v[2] - EPS


def assign_tiers():
    """Greedy colour of the net-conflict graph; the colour becomes the z tier."""
    nets = [seg[5].split()[0] for seg in out]
    conflict = defaultdict(set)
    for i in range(len(out)):
        for j in range(i + 1, len(out)):
            if nets[i] != nets[j] and touches(out[i], out[j]):
                conflict[nets[i]].add(nets[j])
                conflict[nets[j]].add(nets[i])
    # Buses first (most taps, longest runs) so they claim tier 0 and stay flat.
    order = BUS_NETS + sorted((n for n in taps if n not in BUS_NETS),
                              key=lambda n: -len(conflict[n]))
    tier_of = {}
    for net in order:
        used = {tier_of[o] for o in conflict[net] if o in tier_of}
        t = 0
        while t in used:
            t += 1
        tier_of[net] = t
    # place_wire.py lifts a wire by `z_tier * Z_TIER_STEP` (1.0mm) and only requires
    # z_tier >= 0 -- it needn't be an integer. Colouring needs ~7 tiers here, and a
    # whole-number top tier would sit 6mm off the board, well past the ~4mm that
    # already reads as floating rather than as one wire crossing another (CLAUDE.md,
    # session 7). Scale the step so the whole stack fits under MAX_LIFT while keeping
    # the strict per-tier ordering that makes crossings render as over/under.
    MAX_LIFT = 2.0
    span = max(tier_of.values()) or 1
    TIER_STEP = min(0.5, MAX_LIFT / span)
    for seg in out:
        seg[7] = tier_of[seg[5].split()[0]] * TIER_STEP
    return tier_of


tier_of = assign_tiers()

# ---- 4. merge same-net collinear runs, drop sub-hole stubs ------------------------
# emit() deliberately allows a net to overlap ITSELF (allow_dup) so a bus can chain
# through a tap it already passes. That leaves two wires of one colour stacked on the
# same line -- invisible electrically, but it renders as the same merged-wire artifact
# the different-net overlaps do. Union them into one segment per (net, tier, line).
def merge_and_clean(segments):
    groups = defaultdict(list)
    for seg in segments:
        axis, lo, hi, line = orient_seg(seg)
        # Group by the quantised line so near-identical runs merge, but carry the
        # EXACT line coordinate through: pads sit at real positions like y=17.94,
        # and rounding a merged run to 17.9 would slide the wire off its own pad.
        groups[(seg[5], seg[7], axis, quant(line))].append((lo, hi, line, seg))
    merged = []
    for (label, tier, axis, _q), items in groups.items():
        items.sort(key=lambda t: t[0])
        clo, chi, cline, proto = items[0]
        for lo, hi, line, seg in items[1:]:
            if lo <= chi + EPS:          # overlapping or touching end-to-end
                chi = max(chi, hi)
            else:
                merged.append((axis, clo, chi, cline, proto, tier))
                clo, chi, cline, proto = lo, hi, line, seg
        merged.append((axis, clo, chi, cline, proto, tier))
    out2 = []
    for axis, lo, hi, line, proto, tier in merged:
        # A run shorter than half a hole pitch is usually a routing artifact -- both
        # ends are effectively the same hole. But keep it when it terminates on a
        # real pad: pads are not all on the nominal grid, so a genuine last hop onto
        # one can be a fraction of a millimetre, and dropping it disconnects the net
        # from its own pin.
        ends = ((lo, line), (hi, line)) if axis == "H" else ((line, lo), (line, hi))
        if hi - lo < GRID / 2 and not any(e in pads for e in ends):
            continue
        if axis == "H":
            out2.append([lo, line, hi, line, proto[4], proto[5], "back", tier])
        else:
            out2.append([line, lo, line, hi, proto[4], proto[5], "back", tier])
    return out2


out[:] = merge_and_clean(out)
# Merging lengthens segments, which can create crossings the first colouring never
# saw, so colour again over the final geometry.
tier_of = assign_tiers()
out[:] = merge_and_clean(out)
tier_of = assign_tiers()
seg_net = [seg[5].split()[0] for seg in out]


def remaining_conflicts():
    return sum(1 for i in range(len(out)) for j in range(i + 1, len(out))
               if abs(out[i][7] - out[j][7]) < 1e-9 and seg_net[i] != seg_net[j]
               and touches(out[i], out[j]))


# ---- report ---------------------------------------------------------------------------
json.dump(out, open("segments_v3.json", "w"), indent=1)
print(f"emitted {len(out)} segments")
print("tiers:", dict(Counter(s[7] for s in out)))
print("colors:", dict(Counter(s[4] for s in out)))
print(f"unroutable: {unroutable}")
print(f"bus legs unplaced: {bus_failed}")
print(f"emit violations: {len(violations)}")
for v in violations[:20]:
    print("   ", v)
print(f"tiers used: {max(tier_of.values()) + 1}; remaining same-tier touches: {remaining_conflicts()}")
