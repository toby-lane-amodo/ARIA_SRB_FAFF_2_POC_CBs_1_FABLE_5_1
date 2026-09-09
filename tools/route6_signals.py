#!/usr/bin/env python3
"""Routing step 6 -- the general signal fill.

Everything the earlier stages left: whatever net still has more than one
connectivity island, routed at its net-class width on both outer layers.

Order is shortest-span first.  A short net has the fewest alternative paths,
so it gets its corridor before a long haul that has the whole board to detour
through; the long ones are then re-tried with a wider search window if the
first pass could not place them.  Failures are listed, never silently left.
"""
import argparse
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402

SKIP_PREFIX = ("unconnected-",)

# Round 2: the rails that now live on In2.Cu / In3.Cu are not the signal
# fill's business.  Without this it would cheerfully put +3V3 back on F.Cu,
# which is exactly the copper step 2 just cleared.
from route20_power_layers import INNER as _INNER  # noqa: E402
SKIP_NETS = set(_INNER)


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
            if not n or n in seen or n == "GND" or n in SKIP_NETS \
                    or n.startswith(SKIP_PREFIX):
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
MAX_NODES = 600_000
# The heuristic weight is the whole reason this stage stalled at 66 nets.
# A* with hw = 1.3 is nearly admissible, so on a congested board it expands an
# enormous frontier before committing: /mcu/SWCLK, a 34 mm run from the MCU to
# the debug header, needs *three million* nodes at 1.3 and fails at the stock
# ceiling of 1.2 M -- which is why almost every net left open had a bare
# U1001 pin as one of its islands.  At hw = 2.0 the same route lands inside
# 600 k nodes and comes out 39.5 mm, sixteen per cent over the direct
# distance.  That is the right trade for a signal: a slightly longer path
# routed beats an optimal one that never lands.
HW = 2.0
CHUNK = 12


def main():
    # `--chunks` bounds how much one invocation does before exiting.  Python
    # does not hand freed arenas back to the OS reliably, so a long-lived
    # process keeps the high-water mark of its worst search for the rest of
    # the run; three runs of this stage were killed under memory pressure for
    # exactly that.  Exiting between chunks releases it properly, and the
    # stage is resumable by construction -- `open_nets` recomputes what is
    # still split from the board every time.
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=0,
                    help="stop after this many chunks (0 = all)")
    ap.add_argument("--skip", type=int, default=0,
                    help="skip this many open nets before starting")
    ap.add_argument("--pass2", action="store_true",
                    help="run the wider second pass instead of the first")
    a = ap.parse_args()

    board = R.load()
    todo = open_nets(board)
    todo.sort(key=lambda n: span(board, n))
    print(f"{len(todo)} nets still open", flush=True)

    left = []
    done = 0
    if a.pass2:
        todo = []
    todo = todo[a.skip:]
    for k, i in enumerate(range(0, len(todo), CHUNK)):
        if a.chunks and k >= a.chunks:
            print(f"stopping after {a.chunks} chunk(s); "
                  f"{len(todo) - i} nets not yet tried", flush=True)
            break
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
                              margin=16, verbose=False,
                              max_nodes=MAX_NODES, hw=HW)
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
    if not a.pass2:
        board = R.load()
        print("\nunconnected now:", R.unconnected(board), flush=True)
        return
    still = open_nets(board)
    still.sort(key=lambda n: span(board, n))
    still = still[a.skip:]
    print(f"pass 2 (fresh read, wider window): retrying {len(still)}",
          flush=True)
    left2 = []
    for k, i in enumerate(range(0, len(still), CHUNK)):
        if a.chunks and k >= a.chunks:
            print(f"stopping after {a.chunks} chunk(s); "
                  f"{len(still) - i} nets not yet tried", flush=True)
            break
        batch = still[i:i + CHUNK]
        board = R.load()
        obst = R.Obstacles(board)
        obst.reserve_pin_escapes(board)
        R.escape_pass(board, obst, verbose=False)
        maze = R.Maze(obst)
        for net in batch:
            f = R.connect_net(board, obst, maze, net, width=R.net_width(net),
                              via_cost=35, margin=32, verbose=False,
                              max_nodes=MAX_NODES, hw=HW)
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
