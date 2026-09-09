#!/usr/bin/env python3
"""Round 2, step 4c -- drop each rail island into its plane, one via each.

`+3V3` came out of step 4b with a pour on In2.Cu and forty-one separate
islands of copper on the outer layers, and step 4's answer was to merge them
pairwise with a 3.15 mm trace.  That is the wrong construction and it showed:
each merge took a minute and the net grew slower as it went.

A power plane does not want traces between its consumers.  Every island needs
exactly one thing -- **a via into the pour** -- and the plane does the rest.
Forty-one vias instead of forty maze routes, and each is a slot search rather
than a path search.

The via has to be legal, which is the whole job: inside the zone outline, off
every pad (no via-in-pad, G9), clear of foreign copper, and clear of every
other via by the house 0.7524 mm.  The obstacle model's own via mask answers
all of that, so the search is: walk outward from the island's copper and take
the first free slot.

Islands already touching the pour are left alone -- they are connected.
"""
import argparse
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402
from route20_power_layers import INNER  # noqa: E402
from route22_power_zones import LAYER  # noqa: E402

STEP = 0.15             # mm, slot search step
REACH = 4.0             # mm, how far from the island a via may be planted


def zone_of(board, net, layer):
    for z in board.Zones():
        if z.GetNetname() == net and z.GetLayer() == layer:
            return z
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", default="+3V3")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    board = R.load()
    net = a.net
    layer = LAYER[net]
    z = zone_of(board, net, layer)
    if z is None:
        raise SystemExit(f"no {net} zone on {board.GetLayerName(layer)}")
    bb = z.GetBoundingBox()
    zx0, zy0 = R.tomm(bb.GetLeft()), R.tomm(bb.GetTop())
    zx1, zy1 = R.tomm(bb.GetRight()), R.tomm(bb.GetBottom())

    obst = R.Obstacles(board)
    nc = R.netcode(board, net)
    isl = R.net_islands(board, net)
    print(f"{net}: {len(isl)} islands, pour on "
          f"{board.GetLayerName(layer)}", flush=True)

    made, failed = 0, []
    for g in isl:
        if a.limit and made >= a.limit:
            break
        # already in the pour?  a via on this island lands in it already
        if any(k == "via" for k, *_ in g):
            continue
        # The stub must start on the island's own copper.  Starting it at the
        # island's *centroid* -- which is what this did first -- puts it in
        # empty space whenever the island is more than one pad, and the stub
        # then crosses whatever happens to be in between: 30 real DRC
        # violations, all of them self-inflicted.
        anchors = []
        for k, name, lay, boxes, tgt in g:
            for b0 in boxes:
                anchors.append(((b0[0] + b0[2]) / 2.0, (b0[1] + b0[3]) / 2.0))
        if not anchors:
            continue
        slot = start = None
        rings = int(REACH / STEP)
        for cx, cy in anchors:
            for ring in range(1, rings):
                r = ring * STEP
                n = max(8, int(2 * math.pi * r / STEP))
                for i in range(n):
                    th = 2 * math.pi * i / n
                    q = (round(cx + r * math.cos(th), 3),
                         round(cy + r * math.sin(th), 3))
                    if not (zx0 <= q[0] <= zx1 and zy0 <= q[1] <= zy1):
                        continue
                    win = obst.ij(q[0] - 1.5, q[1] - 1.5) + \
                        obst.ij(q[0] + 1.5, q[1] + 1.5)
                    m = obst.via_mask(win, nc)
                    ii, jj = obst.ij(*q)
                    if m[ii - win[0], jj - win[1]]:
                        continue
                    # and the stub from this anchor to it must be clear too
                    if not R.seg_ok(obst, (cx, cy), q, R.W_SIGNAL, nc, R.F):
                        continue
                    slot, start = q, (cx, cy)
                    break
                if slot:
                    break
            if slot:
                break
        if slot is None:
            failed.append(anchors[0])
            continue
        cx, cy = start
        R.add_track(board, (cx, cy), slot, R.W_SIGNAL, R.F, nc)
        R.add_via(board, slot, nc)
        obst.add_via_at(slot, nc)
        obst.add_seg((cx, cy), slot, R.W_SIGNAL / 2, R.F, nc)
        made += 1

    R.refill(board)
    R.save(board)
    board = R.load()
    print(f"   {made} vias dropped into the pour, {len(failed)} islands with "
          f"no legal slot", flush=True)
    print(f"   {net}: "
          f"{'whole' if R.net_is_whole(board, net) else 'still split'}"
          f"; unconnected {R.unconnected(board)}")


if __name__ == "__main__":
    main()
