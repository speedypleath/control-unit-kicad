"""Verify a generated segment set: connectivity per net, pad coverage, bounds.

A wire set can be overlap-free and still wrong -- a net whose segments don't
form one connected graph touching every one of its taps would be an open
circuit if anyone soldered it. Checks, per net:
  1. every tap pad lies ON some segment of that net,
  2. the net's segments + taps form a single connected component,
  3. no segment leaves the board outline.
Segments of DIFFERENT nets that merely cross are not connections (they're at
different z tiers), so connectivity is computed strictly within a net.
"""
import json, sys
from collections import defaultdict

EPS = 0.05
segs = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "segments_v3.json"))
taps = json.load(open("taps_clean.json"))
bbox = json.load(open("board_model.json"))["bbox"]

def on_seg(p, s):
    x, y = p; x1, y1, x2, y2 = s[:4]
    if abs(y1 - y2) < EPS:
        return abs(y - y1) < EPS and min(x1, x2) - EPS <= x <= max(x1, x2) + EPS
    return abs(x - x1) < EPS and min(y1, y2) - EPS <= y <= max(y1, y2) + EPS

by_net = defaultdict(list)
for s in segs:
    by_net[s[5].split()[0]].append(s)

bad_cover, bad_conn, oob = [], [], []
for net, ss in by_net.items():
    pts = set()
    for s in ss:
        pts.add((round(s[0], 3), round(s[1], 3)))
        pts.add((round(s[2], 3), round(s[3], 3)))
        for c in (s[0], s[2]):
            if not bbox[0] - EPS <= c <= bbox[2] + EPS:
                oob.append((net, s))
        for c in (s[1], s[3]):
            if not bbox[1] - EPS <= c <= bbox[3] + EPS:
                oob.append((net, s))
    tp = [(round(x, 3), round(y, 3)) for x, y in taps[net]]
    for p in tp:
        if not any(on_seg(p, s) for s in ss):
            bad_cover.append((net, p))
        pts.add(p)
    # union-find over points joined by a shared segment
    parent = {p: p for p in pts}
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[ra] = rb
    for s in ss:
        anchors = [p for p in pts if on_seg(p, s)]
        for p in anchors[1:]:
            union(anchors[0], p)
    if len({find(p) for p in pts}) != 1:
        bad_conn.append((net, len({find(p) for p in pts})))

print(f"{len(segs)} segments across {len(by_net)} nets")
print(f"taps not on any wire: {len(bad_cover)}", bad_cover[:10])
print(f"nets not fully connected: {len(bad_conn)}", bad_conn[:10])
print(f"segments out of board bounds: {len(oob)}", oob[:5])
