#!/usr/bin/env python3
"""Escape a walled pin to open board with a search, not a straight stub.

`route25_fanout` takes each fine-pitch pin straight out of its ring on its own
lane and drops a via at a staggered depth.  That is the textbook fan-out and it
placed 124 of 291 pins; the other 167 found no legal row, ended their stub
*inside* the ring, and are exactly the pins the fill then cannot leave.

`U1001.54` is the type specimen and the arithmetic is the whole story.  Its
neighbours `U1001.53` and `U1001.55` both took row 1.65 mm, so their vias sit
1.00 mm apart in x with pin 54's lane between them.  Two 0.6 mm via pads leave
a 0.40 mm channel; a 0.15 mm trace at the 0.1524 mm clearance floor needs
0.4548 mm.  Pin 54 is walled out by **fifty-five microns**, and no row, margin,
node budget or heuristic changes that -- the flood out of its stub reaches 99
grid cells, a quarter of a square millimetre.

A straight lane is the wrong instrument for those pins.  This routes the
escape instead: pad -> *anywhere in the band of open board off this pin's own
side of the package*, on F.Cu, B.Cu or In3.Cu, with the maze free to turn, to
slip diagonally between two vias and to change layer wherever it fits.  The
band is 1.6-4.5 mm off the package edge, which is past every fan-out row, and
laterally bounded so a pin escapes on its own side rather than round the
corner into another edge's field.

Pins are taken tightest-first, measured by reachable free area rather than by
a straight-lane probe: a lane 0.34 mm long that dead-ends after a millimetre
grades "tight" on the probe and is as impassable as a lane of zero.  Each
escape joins the obstacle model as it lands, so the field packs rather than
races.
"""
import argparse
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import route_lib as R  # noqa: E402
from route6_signals import open_nets, LAYER_SETS, MAX_NODES, HW  # noqa: E402
from route25_fanout import PITCH_MAX, MIN_PADS, pkg_pitch, outward  # noqa
from route27_batch_pocket import free_area  # noqa: E402

BAND_IN = 1.6           # mm off the pad edge where open board starts
BAND_OUT = 4.5          # mm -- past every fan-out row
BAND_HALF = 3.0         # mm of lateral room the band spans
OUT_ENOUGH = 2000       # free cells that count as "already out of the ring"


def band(q, u, half):
    """The rectangle of open board this pin should reach, on its own side."""
    a = (q[0] + u[0] * (half + BAND_IN), q[1] + u[1] * (half + BAND_IN))
    b = (q[0] + u[0] * (half + BAND_OUT), q[1] + u[1] * (half + BAND_OUT))
    v = (-u[1], u[0])
    xs = [a[0] + v[0] * s * BAND_HALF for s in (-1, 1)] + \
         [b[0] + v[0] * s * BAND_HALF for s in (-1, 1)]
    ys = [a[1] + v[1] * s * BAND_HALF for s in (-1, 1)] + \
         [b[1] + v[1] * s * BAND_HALF for s in (-1, 1)]
    return (min(xs), min(ys), max(xs), max(ys)), b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layers", default="FBI")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    layers, bias = LAYER_SETS[a.layers]

    board = R.load()
    todo = set(open_nets(board))
    obst = R.Obstacles(board)
    maze = R.Maze(obst)

    cands = []
    for f in board.GetFootprints():
        pads = [p for p in f.Pads() if R.pad_copper_layers(p)]
        if len(pads) < MIN_PADS or pkg_pitch(f) > PITCH_MAX:
            continue
        pitch = pkg_pitch(f)
        for p in pads:
            net = p.GetNetname()
            if net not in todo:
                continue
            nc = p.GetNetCode()
            isl, pad_root = R.island_geoms(board, net)
            root = pad_root.get(f"{f.GetReference()}.{p.GetNumber()}")
            if root is None:
                continue
            d = isl[root]
            rects = {l: d[l] for l in R.ROUTE_LAYERS}
            c = R.pt(p.GetPosition())
            area = free_area(obst, maze, nc, rects, c, layers)
            if area >= OUT_ENOUGH:
                continue
            cands.append((area, f.GetReference(), p.GetNumber(), net, pitch))
    cands.sort()
    if a.limit:
        cands = cands[:a.limit]
    print(f"{len(cands)} walled pins on fine-pitch packages", flush=True)
    if a.check:
        for area, ref, num, net, _pitch in cands[:40]:
            print(f"   {area:6d} cells  {ref}.{num:<5} {net}")
        return 0

    made, held = 0, []
    for area, ref, num, net, pitch in cands:
        f = board.FindFootprintByReference(ref)
        p = next(x for x in f.Pads() if x.GetNumber() == num)
        nc = p.GetNetCode()
        q, u, half = outward(f, p)
        bb = R.pad_bbox(p)
        w = max(R.W_SIGNAL, min(R.net_width(net),
                                min(bb[2] - bb[0], bb[3] - bb[1]),
                                pitch - 2 * R.CLEAR))
        rect, goal = band(q, u, half)
        isl, pad_root = R.island_geoms(board, net)
        root = pad_root.get(f"{ref}.{num}")
        srect = {l: isl[root][l] for l in R.ROUTE_LAYERS} if root else \
            {R.F: [R.pad_target_rect(p)]}
        res = maze.route(nc, [R.pt(p.GetPosition())], [goal], w, layers=layers,
                         margin=3.0, via_cost=25, hw=HW, max_nodes=MAX_NODES,
                         layer_bias=bias, start_rects=srect,
                         goal_rects={l: [rect] for l in layers})
        if res is None:
            held.append(f"{ref}.{num}")
            continue
        R.emit_result(board, obst, res, w, nc)
        made += 1

    print(f"{made} pins escaped to open board; {len(held)} still walled",
          flush=True)
    if held:
        print(f"   {held[:16]}" + (" ..." if len(held) > 16 else ""))
    R.refill(board)
    R.save(board)
    board = R.load()
    print(f"unconnected now {R.unconnected(board)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
