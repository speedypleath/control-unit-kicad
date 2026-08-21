"""Analyze wire-vs-wire conflicts in a segment JSON (place_wire 8-field schema).

Conflict = two segments whose tube geometries intersect/merge at the same Z tier:
  - perpendicular mid-span crossing (strictly interior, not a shared endpoint)
  - collinear overlap (same row/col with overlapping span, different nets or not
    merely touching end-to-end)
Reports every conflict, flagged SAME-TIER (= visible overlap/z-fight) or
different-tier (renders as clean over/under). Also sanity-checks that every
segment is exactly horizontal or vertical.
"""
import sys
import json
import math

EPS = 0.05  # mm tolerance; holes are 2.54mm apart, so anything tighter is noise


def load(path):
    segs = []
    for e in json.load(open(path)):
        x1, y1, x2, y2, color, label = e[:6]
        tier = e[7] if len(e) > 7 else 0
        segs.append(dict(x1=x1, y1=y1, x2=x2, y2=y2, color=color, label=label, tier=tier))
    return segs


def orient(s):
    if abs(s["y2"] - s["y1"]) < EPS:
        return "H", min(s["x1"], s["x2"]), max(s["x1"], s["x2"]), round(s["y1"], 2)
    if abs(s["x2"] - s["x1"]) < EPS:
        return "V", min(s["y1"], s["y2"]), max(s["y1"], s["y2"]), round(s["x1"], 2)
    return "D", None, None, None


def conflicts(segs):
    out = []
    for i in range(len(segs)):
        a = segs[i]
        oa, a1, a2, ac = orient(a)
        for j in range(i + 1, len(segs)):
            b = segs[j]
            ob, b1, b2, bc = orient(b)
            pt = None
            kind = None
            if oa == "D" or ob == "D":
                continue
            if oa == "H" and ob == "V":
                # horizontal a at row ac, x in [a1,a2]; vertical b at col bc, y in [b1,b2]
                if a1 + EPS < bc < a2 - EPS and b1 + EPS < ac < b2 - EPS:
                    pt, kind = (bc, ac), "cross"
            elif oa == "V" and ob == "H":
                if b1 + EPS < ac < b2 - EPS and a1 + EPS < bc < a2 - EPS:
                    pt, kind = (bc, ac), "cross"
            elif oa == ob and ac == bc:
                ov = min(a2, b2) - max(a1, b1)
                if ov > EPS:  # strictly overlapping span, not just end-to-end touch
                    kind = "collinear"
            if kind:
                out.append((i, j, kind, pt, a["tier"] == b["tier"]))
    return out


def main():
    path = sys.argv[1]
    segs = load(path)
    diag = [i for i, s in enumerate(segs) if orient(s)[0] == "D"]
    tiny = [i for i, s in enumerate(segs)
            if math.hypot(s["x2"] - s["x1"], s["y2"] - s["y1"]) < 1.0]
    print(f"{len(segs)} segments; diagonal: {diag}; sub-1mm: {tiny}")
    if diag:
        for i in diag:
            print("  diagonal seg", i, segs[i])

    cf = conflicts(segs)
    same = [c for c in cf if c[4]]
    print(f"\ntotal conflicts: {len(cf)}  |  SAME-TIER (visible overlaps): {len(same)}  |  diff-tier: {len(cf) - len(same)}")
    from collections import Counter
    print("same-tier by kind:", dict(Counter(c[2] for c in same)))
    print("\nsame-tier conflicts (i, j, kind, point):")
    for i, j, kind, pt, _ in same:
        a, b = segs[i], segs[j]
        print(f"  [{i:3d}] t{a['tier']} {a['label'][:44]:44s} X [{j:3d}] t{b['tier']} {b['label'][:44]:44s} {kind} @ {pt}")


if __name__ == "__main__":
    main()
