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


# Pass 1 is the longest single stretch of routing on the board -- 150-odd
# nets -- and a refill can segfault (route5's first run did, exit 139, and
# took ten minutes of work with it because nothing had been written).  So it
# banks in chunks: route CHUNK nets, refill, save, reload, carry on.  The
# reload is not a cost either, it is what the repair pass does on purpose.
# Twelve rather than twenty-five: a wide A* search holds its whole visited
# set in memory and this box runs several sessions at once, so two runs were
# killed under memory pressure mid-chunk.  Smaller chunks bank more often and
# put less at risk each time.
#
# The spike itself is the search, not the chunk.  `Maze.route` keeps `gscore`
# and `came` for every node it expands, and the default ceiling of 1.2 M
# nodes is roughly 400 MB of Python dict before it gives up -- affordable on
# an empty board, not on this one, where a net with no path explores
# everything reachable before returning None.  Capping the ceiling bounds the
# memory *and* costs nothing real: a route that needs more than 300 k nodes
# on a 210 x 130 board is not finding a sensible path anyway.
MAX_NODES = 300_000
CHUNK = 12


def main():
    board = R.load()
    todo = open_nets(board)
    todo.sort(key=lambda n: span(board, n))
    print(f"{len(todo)} nets still open", flush=True)

    left = []
    done = 0
    for i in range(0, len(todo), CHUNK):
        batch = todo[i:i + CHUNK]
        board = R.load()
        obst = R.Obstacles(board)
        print(f"   [{i}..{i + len(batch)}] "
              f"{obst.reserve_pin_escapes(board)} escape lanes held",
              flush=True)
        R.escape_pass(board, obst, verbose=False)
        maze = R.Maze(obst)
        for net in batch:
            w = R.net_width(net)
            f = R.connect_net(board, obst, maze, net, width=w, via_cost=55,
                              margin=16, verbose=False, max_nodes=MAX_NODES)
            if f:
                left.append(net)
            else:
                done += 1
        R.refill(board)
        R.save(board)
        print(f"   banked: {done} routed so far, {len(left)} left, "
              f"unconnected {R.unconnected(board)}", flush=True)
    print(f"pass 1: {done} routed, {len(left)} left", flush=True)

    # Reload before the repair pass: a board object that has taken many
    # hundreds of Add()s behaves differently from the same board read back.
    board = R.load()

    # Pass 2 is pass 1 again with a wider window, not `R.repair`.  repair
    # rebuilds the whole obstacle model for every net and tries three
    # progressively wider searches, which on this board is roughly fifty
    # minutes per chunk of twenty-five -- three hours for the remainder, and
    # it cannot help a sealed pin at any margin.  Building the model once per
    # chunk and giving each net one wider attempt costs a fraction of that and
    # closes the same nets; what is genuinely sealed is a job for
    # `tools/route_sealed.py` and a rip plan, not for a wider search.
    still = open_nets(board)
    still.sort(key=lambda n: span(board, n))
    print(f"pass 2 (fresh read, wider window): retrying {len(still)}",
          flush=True)
    left2 = []
    for i in range(0, len(still), CHUNK):
        batch = still[i:i + CHUNK]
        board = R.load()
        obst = R.Obstacles(board)
        obst.reserve_pin_escapes(board)
        R.escape_pass(board, obst, verbose=False)
        maze = R.Maze(obst)
        for net in batch:
            f = R.connect_net(board, obst, maze, net, width=R.net_width(net),
                              via_cost=35, margin=32, verbose=False,
                              max_nodes=MAX_NODES)
            if f:
                left2.append(net)
        R.refill(board)
        R.save(board)
        print(f"   banked: {i + len(batch)} tried, {len(left2)} still open, "
              f"unconnected {R.unconnected(board)}", flush=True)
    for net in left2:
        print(f"   UNROUTED {net}")

    board = R.load()
    print("\nunconnected now:", R.unconnected(board), flush=True)


if __name__ == "__main__":
    main()
