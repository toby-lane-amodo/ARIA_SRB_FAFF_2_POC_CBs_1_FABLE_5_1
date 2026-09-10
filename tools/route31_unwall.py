#!/usr/bin/env python3
"""Let the flood name the sealer, then rip it whole.

Round 1's doctrine for a sealed pin is right and is recorded in `AGENTS.md`:
rip the net that seals it, route the sealed pins first, put the sealer back --
because the sealer usually has the whole board to detour through and the
sealed pin has one lane.  What it never had was a way to *find* the sealer, so
it was one hand-written plan per pin and there were far too many of them.

`route27_batch_pocket` guessed with a disc of a fixed radius, and that is why
it kept failing: a wall sitting 5 mm out is missed by a 2 mm disc, and a 2.5 mm
disc round a wall that is 1.5 mm out rips a great deal of innocent copper as
well -- 162 items of 34 nets in one run, of which only 18 could be put back.

The flood already knows.  Flooding the free space out of a blocked island
stops *somewhere*, and the copper it stops against is the wall by definition.
So: flood, collect the nets whose copper the frontier touches, rip those nets
**entirely**, route the blocked net while they are gone, and put them back.
Ripping a whole net rather than a boxful is the point -- a net with a hole cut
in the middle has to find its way back through the same congestion, while a
net ripped whole is free to take a different route altogether.

One correction to the measure came out of this and is worth keeping: **free
area is not reachability.**  `/linear_encoder/ENC_SDO` has 2446 free cells
round every island, a 12 mm span, and fails at four million nodes with a 50 mm
window -- a 2446-cell pocket is still a pocket.  So the flood here is run to a
*goal*, not to a size: it asks whether island A can reach island B, which is
the only question that decides anything.

Transactional, like `route27_batch_pocket`: snapshot, and restore unless the
board comes out with strictly fewer unconnected items -- including on SIGTERM,
which does not raise and so never reaches `finally`.
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
from collections import deque

import numpy as np
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import route_lib as R  # noqa: E402
from route6_signals import open_nets, span, LAYER_SETS, MAX_NODES, HW  # noqa
from route26_escape_first import KEEP  # noqa: E402

WINDOW = 14.0           # mm of board the flood is allowed to explore


def wall_nets(obst, maze, board, net, layers, width=R.W_SIGNAL,
              full=False):
    """Nets whose copper the flood out of this net's islands stops against.

    Returned in frontier-contact order, most contact first: the net that walls
    the most of the frontier is the one worth ripping.
    """
    nc = R.netcode(board, net)
    isl, pad_root = R.island_geoms(board, net)
    roots = [r for r in isl if r in set(pad_root.values())]
    if len(roots) < 2:
        return [], False
    a, b = roots[0], roots[1]
    pts = isl[a]["pts"] + isl[b]["pts"]
    win = maze.window(pts, WINDOW)
    i0, j0, i1, j1 = win
    W, H = i1 - i0 + 1, j1 - j0 + 1
    r = width / 2.0 + R.CLEAR
    masks = {l: obst.track_mask(win, nc, l, r, ()) for l in layers}
    vmask = obst.via_mask(win, nc, ())
    smask = {l: np.zeros((W, H), dtype=bool) for l in layers}
    gmask = {l: np.zeros((W, H), dtype=bool) for l in layers}
    maze._mark(smask, win, {l: isl[a][l] for l in R.ROUTE_LAYERS}, layers)
    maze._mark(gmask, win, {l: isl[b][l] for l in R.ROUTE_LAYERS}, layers)

    seen, q = set(), deque()
    for l in layers:
        for ii, jj in np.argwhere(smask[l] & ~masks[l]):
            t = (int(ii), int(jj), l)
            seen.add(t)
            q.append(t)
    reached = False
    frontier = []
    while q:
        i, j, l = q.popleft()
        if gmask[l][i, j]:
            reached = True
            break
        for dx, dy in R.DIRS8:
            ni, nj = i + dx, j + dy
            if ni < 0 or nj < 0 or ni >= W or nj >= H:
                continue
            if masks[l][ni, nj]:
                frontier.append((ni + i0, nj + j0, l))
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
    if reached:
        return [], True

    # Which net owns each frontier cell?
    code = {}
    for f in board.GetFootprints():
        for p in f.Pads():
            code[p.GetNetCode()] = p.GetNetname()
    for t in board.GetTracks():
        code[t.GetNetCode()] = t.GetNetname()
    hits = {}
    for gi, gj, l in frontier:
        x, y = obst.xy(gi, gj)
        for k in obst._near((gi, gj, gi, gj), r + 0.1):
            n, lay, box, kind = obst.items[k]
            if n == nc or n == 0 or l not in lay:
                continue
            if box[0] - r <= x <= box[2] + r and box[1] - r <= y <= box[3] + r:
                key = n if kind != "pad" else -n
                hits[key] = hits.get(key, 0) + 1
    out = [(c, (code.get(n, "") if n > 0
                else code.get(-n, "") + " [pad]")) for n, c in hits.items()]
    out.sort(reverse=True)
    if full:
        # --why: the whole boundary, KEEP and pads included.  Ripping the two
        # signal nets that touch the frontier most closed 0 of 6 blocked nets,
        # which only makes sense if most of the boundary is copper no rip may
        # touch -- so the honest report has to show all of it.
        return out, False
    out = [(c, nm) for c, nm in out if nm and nm not in KEEP]
    return [nm for _c, nm in out], False


CHILD = '''
import json, sys
sys.path.insert(0, {here!r})
import pcbnew, route_lib as R
nets = set(json.loads({nets!r}))
b = pcbnew.LoadBoard(R.PCB)
doomed = [t for t in b.GetTracks() if t.GetNetname() in nets]
for t in doomed:
    b.Remove(t)
print(json.dumps({{"removed": len(doomed)}}))
R.refill(b)
R.save(b)
'''


def rip(nets):
    src = CHILD.format(here=HERE, nets=json.dumps(sorted(nets)))
    out = subprocess.run([sys.executable, "-c", src], capture_output=True,
                         text=True)
    if out.returncode != 0:
        print(out.stdout, out.stderr, file=sys.stderr)
        raise SystemExit("rip failed")
    for line in out.stdout.splitlines():
        if line.strip().startswith("{"):
            return json.loads(line.strip())["removed"]
    return 0


def fill(board, nets, layers, bias, **kw):
    obst = R.Obstacles(board)
    obst.reserve_pin_escapes(board)
    R.escape_pass(board, obst, verbose=False)
    maze = R.Maze(obst)
    a = dict(via_cost=15, margin=32, hw=HW, max_nodes=MAX_NODES,
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
    obst = R.Obstacles(board)
    obst.reserve_pin_escapes(board)
    maze = R.Maze(obst)
    todo = open_nets(board)
    todo.sort(key=lambda n: span(board, n))

    if a.why:
        for net in todo[:a.limit]:
            walls, ok = wall_nets(obst, maze, board, net, layers, full=True)
            if ok:
                print(f"{net}: reachable", flush=True)
                continue
            tot = sum(c for c, _ in walls) or 1
            keepish = sum(c for c, nm in walls
                          if nm.replace(" [pad]", "") in KEEP
                          or nm.endswith("[pad]"))
            print(f"{net}: {100.0 * keepish / tot:5.1f}% of the boundary is "
                  f"copper no rip may touch", flush=True)
            for c, nm in walls[:7]:
                print(f"      {100.0 * c / tot:5.1f}%  {nm}")
        return False

    # Spend the rip where a rip can help.  Ordering by span put the two
    # shortest nets first, and those were `Net-(U1101-CPH)`, whose pocket is
    # 100% bounded by its own capacitor's other pad, and the `U30x-PG` pair at
    # 75-86% GND vias and kept rails -- the three the boundary report had just
    # named as unrippable.  Ten sealers ripped for each closed nothing,
    # because none of the ten was what was in the way.
    #
    # So the boundary is measured first and the nets are taken in order of how
    # much of it a rip may actually touch.
    plan, reachable, hopeless = {}, 0, []
    graded = []
    for net in todo:
        walls, ok = wall_nets(obst, maze, board, net, layers, full=True)
        if ok:
            reachable += 1
            continue
        tot = sum(c for c, _ in walls) or 1
        fixed = sum(c for c, nm in walls
                    if nm.endswith("[pad]") or nm.replace(" [pad]", "") in KEEP)
        rippable = [nm for _c, nm in walls
                    if nm and not nm.endswith("[pad]") and nm not in KEEP]
        frac = fixed / float(tot)
        if not walls:
            # No frontier at all: the flood never started, because the pad has
            # no legal cell to start from.  That is a different thing from a
            # pocket with a wall round it and it must not be reported as
            # "0.0% fixed" -- there is no boundary to take a percentage of.
            hopeless.append((None, net))
            continue
        if frac > a.maxfixed or not rippable:
            hopeless.append((frac, net))
            continue
        graded.append((frac, net, rippable[:a.walls]))
    graded.sort()
    for frac, net, walls in graded[:a.limit]:
        plan[net] = walls
    noroom = [n for f, n in hopeless if f is None]
    bounded = sorted((f, n) for f, n in hopeless if f is not None)
    print(f"{len(todo)} open; {reachable} reachable; {len(noroom)} with no "
          f"legal cell to leave the pad at all; {len(bounded)} bounded mostly "
          f"by copper no rip may touch; {len(graded)} worth a rip", flush=True)
    for n in noroom[:6]:
        print(f"   NO ROOM AT THE PAD  {n}")
    for frac, net in bounded[:6]:
        print(f"   BOUNDED {100 * frac:5.1f}% fixed  {net}")
    if not plan:
        return False
    victims = sorted({w for ws in plan.values() for w in ws} - set(plan))
    for net, ws in list(plan.items())[:a.limit]:
        print(f"   {net:<36} sealed by {ws}", flush=True)
    if a.check:
        return False

    n = rip(victims)
    print(f"   ripped {n} items of {len(victims)} whole nets", flush=True)

    board = R.load()
    mine = sorted(plan, key=lambda x: span(board, x))
    left = fill(board, mine, layers, bias)
    R.refill(board)
    R.save(board)
    print(f"   walled nets: {len(mine) - len(left)}/{len(mine)} closed",
          flush=True)

    # Put the sealers back by refilling *everything* that is open, not just
    # them.  Ripping five sealers to close three blocked nets came out at
    # 93 -> 93 with one sealer back in place: the region is at capacity, so
    # the gap a sealer used to occupy is gone by the time it is asked to
    # return, and asking only the sealers to re-route forces each one back
    # into a board that has changed everywhere.  A general fill lets the
    # whole neighbourhood re-solve, which is the only version of this trade
    # that can come out ahead.
    board = R.load()
    wanted = set(victims)
    everything = sorted(set(open_nets(board)) | wanted,
                        key=lambda x: span(board, x))
    still = fill(board, everything, layers, bias)
    R.refill(board)
    R.save(board)
    back = len(wanted) - len([n for n in still if n in wanted])
    print(f"   sealers put back: {back}/{len(victims)}; "
          f"{len(everything) - len(still)} of {len(everything)} open nets "
          f"closed in the refill", flush=True)
    if still:
        board = R.load()
        still = fill(board, sorted(still, key=lambda x: span(board, x)),
                     layers, bias, margin=45, via_cost=10)
        R.refill(board)
        R.save(board)
        print(f"   second attempt leaves {len(still)} open", flush=True)

    after = R.unconnected(R.load())
    print(f"   unconnected {before} -> {after}", flush=True)
    return after < before


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=4,
                    help="blocked nets to unwall in one transaction")
    ap.add_argument("--walls", type=int, default=2,
                    help="sealing nets to rip per blocked net")
    ap.add_argument("--layers", default="FBI")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--maxfixed", type=float, default=0.55,
                    help="skip a net when more than this fraction of its "
                         "pocket boundary is pads, GND or kept copper")
    ap.add_argument("--why", action="store_true",
                    help="report the full boundary of each blocked net -- "
                         "GND, pads and all -- and change nothing")
    a = ap.parse_args()
    layers, bias = LAYER_SETS[a.layers]

    before = R.unconnected(R.load())
    snap = R.PCB + ".unwall-snapshot"
    shutil.copyfile(R.PCB, snap)

    def _bail(signum, _frame):
        shutil.copyfile(snap, R.PCB)
        print(f"   signal {signum} -- board restored", flush=True)
        # `finally` never runs on SIGTERM, so this is the only place the
        # snapshot gets deleted on that path -- one was left behind.
        try:
            os.remove(snap)
        except OSError:
            pass
        os._exit(2)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _bail)

    ok = False
    try:
        ok = run(a, layers, bias, before)
    except BaseException:
        shutil.copyfile(snap, R.PCB)
        print("   interrupted -- board restored", flush=True)
        raise
    finally:
        if not ok and not a.check:
            shutil.copyfile(snap, R.PCB)
            print("   not better -- board restored", flush=True)
        if os.path.exists(snap):
            os.remove(snap)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
