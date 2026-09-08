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
    """Nets whose pads are not all in one connectivity island yet."""
    board.BuildConnectivity()
    conn = board.GetConnectivity()
    out = []
    for f in board.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if not n or n == "GND" or n.startswith(SKIP_PREFIX):
                continue
            if n not in out and conn.GetUnconnectedCount(True):
                out.append(n)
    # keep only the ones that really still have islands
    todo = []
    for n in out:
        nodes = R.pad_nodes(board, n)
        if len(nodes) < 2:
            continue
        if not R.net_is_whole(board, n):
            todo.append(n)
    return todo


def main():
    board = R.load()
    obst = R.Obstacles(board)
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

    if left:
        again = []
        for net in left:
            f = R.connect_net(board, obst, maze, net, width=R.net_width(net),
                              via_cost=45, margin=40, verbose=False)
            if f:
                again.append((net, sorted(set(f))))
        print(f"pass 2 (wide window): {len(left) - len(again)} routed, "
              f"{len(again)} left")
        for net, refs in again:
            print(f"   UNROUTED {net:<36} {refs}")

    R.refill(board)
    R.save(board)
    print("\nunconnected now:", R.unconnected(board))


if __name__ == "__main__":
    main()
