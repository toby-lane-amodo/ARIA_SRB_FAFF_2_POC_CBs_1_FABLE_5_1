#!/usr/bin/env python3
"""Which of the still-open nets are *sealed*, and which are merely unrouted.

The distinction decides what to do next, and it is not visible in a router's
"UNROUTED" line.  A pad with no legal way out of its own pin ring cannot be
reached at any width on either layer, however wide the search window; the only
fix is to rip whatever is standing in its lane, route it first, and put the
sealer back (R3-1, and `tools/route_ripup.py` holds the plans).  A pad that can
get out but whose net still would not close is a different problem entirely --
that one wants a wider window or a different corridor.

So for every net that is still in more than one island, this walks each island
that holds pads and asks a concrete question of each pad: can a trace of the
net's own class width leave this pad, in any of eight directions, for a lane
length?  A pad that answers no to all eight is sealed, and the report names the
copper sitting in its best direction so the rip has something to aim at.

Reports only.  Nothing here touches the board.
"""
import argparse
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402

LANE = 0.90            # mm of clear lane a pad needs to count as escapable
DIRS = [(math.cos(math.radians(a)), math.sin(math.radians(a)))
        for a in range(0, 360, 45)]


def escapes(board, obst, pad, width):
    """Which of the eight directions a `width` trace can leave this pad by."""
    q = R.pt(pad.GetPosition())
    bb = R.pad_bbox(pad)
    half = max(bb[2] - bb[0], bb[3] - bb[1]) / 2.0
    nc = pad.GetNetCode()
    out = []
    for u in DIRS:
        a = (round(q[0] + u[0] * half, 3), round(q[1] + u[1] * half, 3))
        b = (round(q[0] + u[0] * (half + LANE), 3),
             round(q[1] + u[1] * (half + LANE), 3))
        for layer in (R.F, R.B):
            if layer not in R.pad_copper_layers(pad):
                continue
            if R.seg_ok(obst, a, b, width, nc, layer):
                out.append((u, board.GetLayerName(layer)))
                break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", help="only this net")
    a = ap.parse_args()

    board = R.load()
    obst = R.Obstacles(board)

    seen, split = set(), []
    for f in board.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if not n or n in seen or n == "GND" or n.startswith("unconnected-"):
                continue
            seen.add(n)
            if a.net and n != a.net:
                continue
            if len(R.pad_nodes(board, n)) < 2:
                continue
            if not R.net_is_whole(board, n):
                split.append(n)

    pads = {}
    for f in board.GetFootprints():
        for p in f.Pads():
            pads[f"{f.GetReference()}.{p.GetNumber()}"] = p

    sealed, open_ = [], []
    for net in sorted(split):
        w = R.net_width(net)
        isl = R.net_islands(board, net)
        for g in isl:
            for key in sorted({x[1] for x in g if x[0] == "pad"}):
                p = pads.get(key)
                if p is None or not R.pad_copper_layers(p):
                    continue
                e = escapes(board, obst, p, w)
                (open_ if e else sealed).append((net, key, e))

    print(f"{len(split)} nets still split, "
          f"{len(sealed) + len(open_)} pads in them")
    print(f"\n== SEALED -- no lane out at {LANE} mm, on either layer "
          f"({len(sealed)} pads)")
    for net, key, _e in sealed:
        print(f"   {net:<36} {key}")
    print(f"\n== escapable, so the net is a routing problem not a lane one "
          f"({len(open_)} pads)")
    for net, key, e in open_[:60]:
        dirs = ",".join(f"{d}" for d, _l in
                        [(f"{int(round(math.degrees(math.atan2(u[1], u[0]))))}",
                          l) for u, l in e])
        print(f"   {net:<36} {key:<14} out at {dirs} deg")
    if len(open_) > 60:
        print(f"   ... and {len(open_) - 60} more")
    return 1 if sealed else 0


if __name__ == "__main__":
    sys.exit(main())
