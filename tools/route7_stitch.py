#!/usr/bin/env python3
"""Routing step 7 -- a return via beside every signal via (house G5).

G5: *every signal via gets a neighbouring GND via -- the return changes layer
with the signal, vias always in pairs.*  The reason is the loop, not the
symmetry: a signal that hops from F.Cu to B.Cu changes which plane it is
referenced to, In1.Cu to In2.Cu, and its return current has to make the same
hop.  With no via nearby the return has to go the long way round to the
nearest plane-to-plane stitch, and that detour is the loop area.

So this stage sweeps every non-GND via, measures the distance to the nearest
GND via, and plants one where there is none within `WANT`.  The new via has to
be a *plane-to-plane* stitch and nothing more -- it needs no trace, because
both planes are GND and the barrel joins them.

Order matters: this runs after the signal fill, because a return via planted
early is just an obstacle in a corridor the signals had not claimed yet.

`tools/route_check.py --g5` is the proof.
"""
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402

WANT = 1.60             # mm -- a return via further than this is not "beside"
SEARCH = 2.20           # mm -- how far to look for a legal slot
SKIP_NETS = {"GND"}


def vias(board):
    out = []
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            out.append((R.pt(t.GetPosition()), t.GetNetname()))
    return out


def main():
    board = R.load()
    obst = R.Obstacles(board)
    gnd = R.netcode(board, "GND")

    allv = vias(board)
    g = [q for q, n in allv if n == "GND"]
    sig = [(q, n) for q, n in allv if n not in SKIP_NETS]
    print(f"{len(sig)} non-GND vias, {len(g)} GND vias")

    todo = []
    for q, n in sig:
        d = min((R.dist(q, p) for p in g), default=1e9)
        if d > WANT:
            todo.append((d, q, n))
    todo.sort(reverse=True)
    print(f"{len(todo)} without a GND via within {WANT} mm")

    made, left = 0, []
    for d, q, n in todo:
        # re-measure: a via planted for a neighbour may already serve this one
        if min((R.dist(q, p) for p in g), default=1e9) <= WANT:
            continue
        win = obst.ij(q[0] - SEARCH, q[1] - SEARCH) + obst.ij(q[0] + SEARCH,
                                                              q[1] + SEARCH)
        vm = obst.via_mask(win, gnd)
        best = None
        for i in range(win[0], win[2] + 1):
            for j in range(win[1], win[3] + 1):
                if vm[i - win[0], j - win[1]]:
                    continue
                x, y = obst.xy(i, j)
                dd = math.hypot(x - q[0], y - q[1])
                if dd > WANT:
                    continue
                if best is None or dd < best[0]:
                    best = (dd, x, y)
        if best is None:
            left.append((round(d, 2), q, n))
            continue
        R.add_via(board, (best[1], best[2]), gnd)
        obst.add_via_at((best[1], best[2]), gnd)
        g.append((best[1], best[2]))
        made += 1

    if made:
        R.refill(board)
        R.save(board)
    print(f"\n{made} GND return vias planted")
    if left:
        print(f"{len(left)} signal vias still without one -- no legal slot "
              f"within {WANT} mm:")
        for d, q, n in left[:40]:
            print(f"   {n:<34} at {q[0]:.2f},{q[1]:.2f}  nearest GND "
                  f"{d:.2f} mm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
