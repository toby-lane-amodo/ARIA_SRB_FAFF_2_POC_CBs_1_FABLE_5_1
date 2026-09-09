#!/usr/bin/env python3
"""Round 2, step 3c -- priority inversion, in batches.

`route24_pocket.py` established the doctrine and proved it works: a net that
will not close is usually not fighting congestion in general, it is a pad
walled in by a millimetre or two of somebody else's copper, and the fix is to
rip the wall, route the walled net *first*, and put the wall back somewhere
else.  What it could not do is scale -- one net per invocation, a fresh board
read per victim, and eighty nets left.

Two things had to be measured before this could be written, and both changed
the picture:

* **The wall is real and it is small.**  Flood-filling the free space out of
  `C1112.1` -- a plain 0402 pad, nothing fine-pitch about it -- reaches 388
  grid cells, about one square millimetre, on a board with half its window
  free.  No search at any margin, node budget or heuristic leaves that; the
  A* returns in ten milliseconds having exhausted its whole frontier.  So
  "UNROUTED" on these nets never meant "needs a wider window".
* **The fill only ever had two layers.**  `connect_net` defaults to
  `layers=(F, B)` and `route6_signals` never overrode it, so on the six-layer
  stack the signal fill kept routing into F.Cu -- 3064 segments against 1038
  on B.Cu and 16 on In3.Cu -- while two mixed inner layers sat empty.  That
  is fixed in `route6_signals` (`--layers`), and this stage inherits it.

The batch is the unit of the transaction, not the net: the walled pads cluster
round the same four packages, so their pockets overlap and ripping them
together costs barely more than ripping one.  The stage is accepted only if
the board comes out with strictly fewer unconnected items than it went in
with, and restored from the snapshot otherwise -- including on SIGTERM, which
does not raise and so never reaches `finally`.
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys

import numpy as np
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import route_lib as R  # noqa: E402
from route6_signals import open_nets, span, MAX_NODES, HW, LAYER_SETS  # noqa
from route26_escape_first import KEEP  # noqa: E402

RADIUS = 2.5            # mm of pocket opened around each walled pad
FLOOD = 4.0             # mm window the free-space flood is measured in


def free_area(obst, maze, nc, rects, centre, layers, width=R.W_SIGNAL):
    """Grid cells of free space reachable from one island of a net.

    This is the number that separates a walled island from a merely awkward
    one, and it has to be seeded exactly the way `Maze.route` seeds its open
    set: from the island's own copper, **on the layers that copper is actually
    on**.  Seeding every layer at the pad's coordinates instead -- which is
    what the first cut did -- hands the flood a free ride onto the empty
    In3.Cu and reports twenty thousand cells of room for a pad that cannot
    fit a via, which is precisely the pad that is stuck.
    """
    from collections import deque
    win = maze.window([centre], FLOOD)
    i0, j0, i1, j1 = win
    W, H = i1 - i0 + 1, j1 - j0 + 1
    r = width / 2.0 + R.CLEAR
    masks = {l: obst.track_mask(win, nc, l, r, ()) for l in layers}
    vmask = obst.via_mask(win, nc, ())
    smask = {l: np.zeros((W, H), dtype=bool) for l in layers}
    maze._mark(smask, win, rects, layers)
    seen, q = set(), deque()
    for l in layers:
        for ii, jj in np.argwhere(smask[l] & ~masks[l]):
            t = (int(ii), int(jj), l)
            seen.add(t)
            q.append(t)
    while q:
        i, j, l = q.popleft()
        for dx, dy in R.DIRS8:
            ni, nj = i + dx, j + dy
            if ni < 0 or nj < 0 or ni >= W or nj >= H:
                continue
            if masks[l][ni, nj]:
                continue
            if dx and dy and (masks[l][i + dx, j] or masks[l][i, j + dy]):
                continue
            t = (ni, nj, l)
            if t not in seen:
                seen.add(t)
                q.append(t)
        if not vmask[i, j]:
            for l2 in layers:
                if l2 != l and not masks[l2][i, j] and (i, j, l2) not in seen:
                    seen.add((i, j, l2))
                    q.append((i, j, l2))
    return len(seen)


def walled(board, nets, layers):
    """[(free cells, net, pad name, centre)] -- the tightest island of each net.

    Every island offers a pad, and the one that matters is the one with least
    room, not the one in the smallest island: a lone resistor land sitting in
    open board is not what is stopping the net (route24's `blocked_pads` note
    records the net that proved it).
    """
    obst = R.Obstacles(board)
    obst.reserve_pin_escapes(board)
    maze = R.Maze(obst)
    out = []
    for net in nets:
        nc = R.netcode(board, net)
        isl, pad_root = R.island_geoms(board, net)
        root_pad = {}
        for name, root in pad_root.items():
            root_pad.setdefault(root, name)
        best = None
        for root, d in isl.items():
            if root not in root_pad:
                continue
            rects = {l: d[l] for l in R.ROUTE_LAYERS}
            c = d["pts"][0]
            a = free_area(obst, maze, nc, rects, c, layers)
            if best is None or a < best[0]:
                best = (a, net, root_pad[root], c)
        if best:
            out.append(best)
    out.sort()
    return out


CHILD = '''
import json, sys
sys.path.insert(0, {here!r})
import pcbnew, route_lib as R
cs = json.loads({centres!r}); rad = {rad}; keep = set(json.loads({keep!r}))
b = pcbnew.LoadBoard(R.PCB)
def near(p):
    for c in cs:
        if (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 <= rad * rad:
            return True
    return False
doomed, nets = [], {{}}
for t in b.GetTracks():
    n = t.GetNetname()
    if n in keep or not n:
        continue
    if isinstance(t, pcbnew.PCB_VIA):
        hit = near(R.pt(t.GetPosition()))
    else:
        hit = near(R.pt(t.GetStart())) and near(R.pt(t.GetEnd()))
    if hit:
        doomed.append(t); nets[n] = nets.get(n, 0) + 1
for t in doomed:
    b.Remove(t)
print(json.dumps({{"removed": len(doomed), "nets": nets}}))
R.refill(b)
R.save(b)
'''


def rip(centres, rad, keep):
    src = CHILD.format(here=HERE, centres=json.dumps([list(c) for c in centres]),
                       rad=rad, keep=json.dumps(sorted(keep)))
    out = subprocess.run([sys.executable, "-c", src], capture_output=True,
                         text=True)
    if out.returncode != 0:
        print(out.stdout, out.stderr, file=sys.stderr)
        raise SystemExit("rip failed")
    for line in out.stdout.splitlines():
        if line.strip().startswith("{"):
            return json.loads(line.strip())
    return {"removed": 0, "nets": {}}


def fill(board, nets, layers, bias, **kw):
    obst = R.Obstacles(board)
    obst.reserve_pin_escapes(board)
    R.escape_pass(board, obst, verbose=False)
    maze = R.Maze(obst)
    a = dict(via_cost=15, margin=28, hw=HW, max_nodes=MAX_NODES,
             verbose=False, layers=layers, layer_bias=bias)
    a.update(kw)
    left = []
    for n in nets:
        if R.net_is_whole(board, n):
            continue
        if R.connect_net(board, obst, maze, n, width=R.net_width(n), **a):
            left.append(n)
    return left


def run(a, layers, bias, before):
    board = R.load()
    todo = open_nets(board)
    rank = walled(board, todo, layers)
    batch = rank[:a.limit]
    print(f"{len(todo)} open; the {len(batch)} most walled:", flush=True)
    for area, net, name, c in batch:
        print(f"   {area:6d} cells  {net:<36} {name:<12} "
              f"{c[0]:7.2f},{c[1]:7.2f}", flush=True)

    keep = set(KEEP) | {n for _a, n, _p, _c in batch}
    info = rip([c for _a, _n, _p, c in batch], a.radius, keep)
    victims = sorted(info["nets"])
    print(f"   ripped {info['removed']} items of {len(victims)} nets "
          f"within {a.radius} mm of {len(batch)} pads", flush=True)

    board = R.load()
    mine = [n for _a, n, _p, _c in batch]
    left = fill(board, sorted(mine, key=lambda n: span(board, n)), layers, bias)
    R.refill(board)
    R.save(board)
    print(f"   walled nets: {len(mine) - len(left)}/{len(mine)} closed",
          flush=True)

    board = R.load()
    still = fill(board, sorted(victims, key=lambda n: span(board, n)),
                 layers, bias)
    R.refill(board)
    R.save(board)
    print(f"   victims put back: {len(victims) - len(still)}/{len(victims)}",
          flush=True)
    if still:
        board = R.load()
        still = fill(board, sorted(still, key=lambda n: span(board, n)),
                     layers, bias, margin=40)
        R.refill(board)
        R.save(board)
        print(f"   second attempt leaves {len(still)}: {still[:8]}", flush=True)

    board = R.load()
    after = R.unconnected(board)
    print(f"   unconnected {before} -> {after}", flush=True)
    return after < before


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--radius", type=float, default=RADIUS)
    ap.add_argument("--layers", default="FBI")
    a = ap.parse_args()
    layers, bias = LAYER_SETS[a.layers]

    board = R.load()
    before = R.unconnected(board)
    snap = R.PCB + ".batch-snapshot"
    shutil.copyfile(R.PCB, snap)

    def _bail(signum, _frame):
        shutil.copyfile(snap, R.PCB)
        print(f"   signal {signum} -- board restored from the snapshot",
              flush=True)
        os._exit(2)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _bail)

    ok = False
    try:
        ok = run(a, layers, bias, before)
    except BaseException:
        shutil.copyfile(snap, R.PCB)
        print("   interrupted -- board restored from the snapshot", flush=True)
        raise
    finally:
        if not ok:
            shutil.copyfile(snap, R.PCB)
            print("   not better -- board restored from the snapshot",
                  flush=True)
        if os.path.exists(snap):
            os.remove(snap)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
