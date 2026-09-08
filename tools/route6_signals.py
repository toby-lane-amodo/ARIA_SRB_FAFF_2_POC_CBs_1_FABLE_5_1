#!/usr/bin/env python3
"""Routing step 6 -- the general signal fill.

Everything the earlier stages left: whatever net still has more than one
connectivity island, routed at its net-class width on both outer layers.

Order is shortest-span first.  A short net has the fewest alternative paths,
so it gets its corridor before a long haul that has the whole board to detour
through; the long ones are then re-tried with a wider search window if the
first pass could not place them.  Failures are listed, never silently left.
"""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402

SKIP_PREFIX = ("unconnected-",)


def span(board, net):
    pts = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() == net and R.pad_copper_layers(p):
                pts.append(R.pt(p.GetPosition()))
    if len(pts) < 2:
        return 0.0
    return (max(q[0] for q in pts) - min(q[0] for q in pts)
            + max(q[1] for q in pts) - min(q[1] for q in pts))


def open_nets(board):
    """Nets whose pads are not yet all in one island."""
    todo = []
    seen = set()
    for f in board.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if not n or n in seen or n == "GND" or n.startswith(SKIP_PREFIX):
                continue
            seen.add(n)
            if len(R.pad_nodes(board, n)) < 2:
                continue
            if not R.net_is_whole(board, n):
                todo.append(n)
    return todo


def main():
    board = R.load()
    obst = R.Obstacles(board)
    print(f"   {obst.reserve_pin_escapes(board)} fine-pitch pin escape lanes held")
    R.escape_pass(board, obst)
    maze = R.Maze(obst)

    todo = open_nets(board)
    todo.sort(key=lambda n: span(board, n))
    print(f"{len(todo)} nets still open")

    left = []
    for net in todo:
        w = R.net_width(net)
        f = R.connect_net(board, obst, maze, net, width=w, via_cost=55,
                          margin=16, verbose=False)
        if f:
            left.append(net)
    print(f"pass 1: {len(todo) - len(left)} routed, {len(left)} left")

    # Reload before the repair pass: a board object that has taken many
    # hundreds of Add()s behaves differently from the same board read back.
    R.refill(board)
    R.save(board)
    board = R.load()

    still = open_nets(board)
    if still:
        print(f"pass 2 (fresh read, wide window): retrying {len(still)}")
        left2 = R.repair(board, still,
                         tries=(dict(via_cost=40, margin=30),
                                dict(via_cost=25, margin=60),
                                dict(via_cost=25, margin=90, hw=1.0)))
        for net in left2:
            print(f"   UNROUTED {net}")
    else:
        print("pass 2: nothing left to repair")

    R.refill(board)
    R.save(board)
    print("\nunconnected now:", R.unconnected(board))


if __name__ == "__main__":
    main()
