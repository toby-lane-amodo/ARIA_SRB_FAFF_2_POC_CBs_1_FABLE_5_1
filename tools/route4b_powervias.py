#!/usr/bin/env python3
"""Routing step 4b -- bring every power layer change up to the via budget.

Step 4 routes each rail until its pads are in one island.  That is a
connectivity test, and connectivity is happy with one via; current is not.
At 1.0 A per via (`docs/decisions/actuator-pcb-setup.md` S3 -- JLC plates
~18 um, so a 0.20 mm barrel is worth a 0.32 mm 1 oz trace) a rail that
crosses layers through a single via puts its whole current through that
barrel.

So the test that matters is not "how many vias does this net have" but
"how many does it *depend* on": a via whose removal splits the net is
carrying everything that crosses there.  This stage finds those bridge vias
net by net and parallels each one up to `ceil(I / 1.0 A)`, minimum 2 -- the
extra vias placed in legal slots beside it and tied to it on **both** outer
layers, because two vias joined on one layer only are in series through the
other, not in parallel.

Design currents come from `route4_power.VIA_BUDGET`; `tools/route_check.py
--power` is the proof and must come back with no min-cut smaller than the
budget.  The board file is the master -- this mutates it, create-only.
"""
import itertools
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402
from route4_power import VIA_BUDGET  # noqa: E402

CLUSTER = 2.2           # mm -- vias this close count as one parallel cluster
SEARCH = 3.0            # mm -- how far a partner via may be planted


def net_vias(board, net):
    return [R.pt(t.GetPosition()) for t in board.GetTracks()
            if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == net]


def islands_without(items, drop):
    keep = [it for i, it in enumerate(items) if i not in drop]
    uf = R._touch_graph(keep)
    groups = {}
    for i, it in enumerate(keep):
        groups.setdefault(uf.find(i), []).append(it)
    return [g for g in groups.values() if any(k == "pad" for k, *_ in g)]


def bridges(board, net, need):
    """Via sets smaller than `need` whose removal splits the net.

    A single bridge via is the obvious case, but a rail can also cross on two
    vias that are in parallel with each other and with nothing else -- pull
    both and the net falls apart, so between them they carry the lot.  At
    3 A and a 1.0 A budget that pair is still 50 % over.  So the cut is
    searched at every size below the budget, smallest first, and the vias it
    names are the ones that get a partner.
    """
    items = R.net_items(board, net)
    base = len(islands_without(items, set()))
    vidx = [i for i, it in enumerate(items) if it[0] == "via"]

    def xy(i):
        x, y = items[i][1].split(",")
        return (float(x), float(y))

    single = [xy(i) for i in vidx
              if len(islands_without(items, {i})) > base]
    if single or need <= 2:
        return single, 1
    for k in range(2, need):
        for combo in itertools.combinations(vidx, k):
            if len(islands_without(items, set(combo))) > base:
                return [xy(i) for i in combo], k
    return [], 0


def cluster_of(vs, q):
    """Vias already parallel with q -- one hop of CLUSTER, transitively."""
    grp = [q]
    again = True
    while again:
        again = False
        for v in vs:
            if v in grp:
                continue
            if any(R.dist(v, g) <= CLUSTER for g in grp):
                grp.append(v)
                again = True
    return grp


def plant(board, obst, q, nc, width, want):
    """Add `want` vias beside q, each tied to q on both outer layers."""
    made = []
    win = obst.ij(q[0] - SEARCH, q[1] - SEARCH) + obst.ij(q[0] + SEARCH,
                                                          q[1] + SEARCH)
    for _ in range(want):
        vm = obst.via_mask(win, nc)
        cands = []
        for i in range(win[0], win[2] + 1):
            for j in range(win[1], win[3] + 1):
                if vm[i - win[0], j - win[1]]:
                    continue
                x, y = obst.xy(i, j)
                d = math.hypot(x - q[0], y - q[1])
                if d < R.VIA_D + R.CLEAR or d > SEARCH:
                    continue
                cands.append((d, x, y))
        cands.sort()
        placed = None
        for _d, x, y in cands:
            w = min(width, R.VIA_D)
            if not (R.seg_ok(obst, q, (x, y), w, nc, R.F)
                    and R.seg_ok(obst, q, (x, y), w, nc, R.B)):
                continue
            R.add_via(board, (x, y), nc)
            obst.add_via_at((x, y), nc)
            for lay in (R.F, R.B):
                R.add_track(board, q, (x, y), w, lay, nc)
                obst.add_seg(q, (x, y), w / 2.0, lay, nc)
            placed = (x, y)
            break
        if placed is None:
            break
        made.append(placed)
    return made


def main():
    board = R.load()
    obst = R.Obstacles(board)
    print(f"{'net':<32} {'I':>5} {'need':>5} {'near':>5}  action")
    added = 0
    short = []
    for net, amps in sorted(VIA_BUDGET.items(), key=lambda kv: -kv[1]):
        try:
            nc = R.netcode(board, net)
        except KeyError:
            continue
        vs = net_vias(board, net)
        need = max(2, math.ceil(amps / R.VIA_A))
        br, k = bridges(board, net, need)
        if not br:
            print(f"{net:<32} {amps:5.2f} {need:5d} {len(vs):5d}  "
                  f"no cut below {need} vias -- nothing depends on too few")
            continue
        width = max(0.30, min(R.net_width(net), 0.60))
        for q in br:
            # A bridge via is by definition not paralleled -- proximity is
            # not parallelism, so the cluster is only reported, never used
            # to excuse a bridge.
            grp = cluster_of(vs, q)
            want = need - k
            made = plant(board, obst, q, nc, width, want)
            added += len(made)
            vs = net_vias(board, net)
            state = ("+" + str(len(made)) if made else "NONE")
            print(f"{net:<32} {amps:5.2f} {need:5d} {len(grp):5d}  "
                  f"{k}-via cut at {q[0]:.2f},{q[1]:.2f} -> {state}")
            if len(made) < want:
                short.append((net, q, len(grp) + len(made), need))

    if added:
        R.refill(board)
        R.save(board)
    print(f"\n{added} parallel vias added")
    if short:
        print("STILL SHORT OF BUDGET -- needs the engineer:")
        for net, q, have, need in short:
            print(f"   {net} at {q[0]:.2f},{q[1]:.2f}: {have} of {need}")
    return 1 if short else 0


if __name__ == "__main__":
    sys.exit(main())
