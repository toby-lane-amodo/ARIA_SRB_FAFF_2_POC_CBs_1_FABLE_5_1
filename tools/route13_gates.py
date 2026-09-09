#!/usr/bin/env python3
"""Routing step 13 -- the four DRV8323 nets the window plans could not close.

`u1101-gates` frees the pins and redraws the block, and after it the three
low-side gates and `VM_DRV` still would not close.  `route_sealed` says the
pins are no longer sealed, so this is not a lane problem any more -- it is a
25 mm run from a FET gate to the driver across a board that the general fill
has since filled.  Step 5b closed the same net in 20.62 mm when the board was
half empty; the corridor is simply not there now.

So: a wide, cheap-via search, on a model rebuilt for each net, and the layer
change taken rather than the run left open.  `place1` open point 1 asked for
all six gates on F.Cu and via-free; the east row of the package is not planar
and this is where that wish runs out.  What each one actually cost is printed,
and the decisions file carries the count.
"""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402

NETS = ["Net-(Q1102-G)", "Net-(Q1104-G)", "Net-(Q1106-G)",
        "/motor_drive/VM_DRV"]
TRIES = (dict(via_cost=45, margin=30),
         dict(via_cost=25, margin=55),
         dict(via_cost=12, margin=90, hw=1.0))


def stats(board, net):
    ln = sum(R.dist(R.pt(t.GetStart()), R.pt(t.GetEnd()))
             for t in board.GetTracks()
             if t.GetNetname() == net and not isinstance(t, pcbnew.PCB_VIA))
    nv = sum(1 for t in board.GetTracks()
             if t.GetNetname() == net and isinstance(t, pcbnew.PCB_VIA))
    return ln, nv


def main():
    board = R.load()
    todo = [n for n in NETS if not R.net_is_whole(board, n)]
    print(f"{len(todo)} of {len(NETS)} still open: {todo}", flush=True)
    left = []
    for net in todo:
        done = False
        for k, kw in enumerate(TRIES, 1):
            board = R.load()
            obst = R.Obstacles(board)
            maze = R.Maze(obst)
            f = R.connect_net(board, obst, maze, net, width=0.25,
                              verbose=False, **kw)
            if not f:
                R.refill(board)
                R.save(board)
                ln, nv = stats(board, net)
                print(f"   {net:<22} try {k}: {ln:6.2f} mm, {nv} vias",
                      flush=True)
                done = True
                break
            print(f"   {net:<22} try {k}: no path", flush=True)
        if not done:
            left.append(net)
    board = R.load()
    print(f"\nstill open: {left or 'none'}")
    print("unconnected now:", R.unconnected(board))
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
