#!/usr/bin/env python3
"""Trim the dead ends the escape-first order necessarily leaves behind.

Escape-first draws copper before it knows which way the net will leave: every
fine-pitch pin gets a stub out of its ring and, where a slot exists, a via at
the end of it.  That is the point -- the stub is real copper, so the next net
has to go round it rather than through the lane.  But when the fill then
routes the net the other way, or reaches the pad directly, the stub and its
via are left hanging: a branch with one free end, joined to the net at the
other.  KiCad calls those `track_dangling` / `via_dangling`, and round 2 ended
with 180 of them.

They are not merely cosmetic.  A via hanging off a signal is a quarter-wave
stub with a plane antipad round it, and an unterminated spur on a bus is the
classic source of a reflection nobody can find later.

So this prunes leaves: an item of a **whole** net whose endpoint touches
nothing else of that net is removed, and the pass repeats until nothing moves,
which peels a chain of segments back to the junction it grew from.  Three nets
are never touched:

* `GND` and anything else with a plane or a pour behind it -- a GND via joins
  the planes through its barrel, which is not an item in this graph, so every
  one of them looks like a leaf and none of them is;
* a net that is still **open** -- its stub is the escape the next fill pass
  will start from, and pruning it undoes the stage that placed it;
* a pad, ever.

`--check` reports without touching the board.  Deletion runs in a child
interpreter: `board.Remove()` mid-script poisons SWIG type resolution for
every wrapped return that follows it.
"""
import argparse
import json
import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import route_lib as R  # noqa: E402

# Nets whose connectivity does not live in the track graph at all.
POURED = {"GND", "+3V3"}


def _online(a, c, q, tol=2e-3):
    cross = (c[0] - a[0]) * (q[1] - a[1]) - (c[1] - a[1]) * (q[0] - a[0])
    L = max(R.dist(a, c), 1e-9)
    if abs(cross) / L > tol:
        return False
    t = ((q[0] - a[0]) * (c[0] - a[0]) + (q[1] - a[1]) * (c[1] - a[1])) / (L * L)
    return -1e-6 <= t <= 1 + 1e-6


def covered(board):
    """[(kind, key, layer)] of every track lying wholly inside another.

    A stage that redraws an area must rip what it is about to write, or the
    second run lays a second trace over the first -- AGENTS.md records the
    same trap for vias.  On this board it left 92 of them, three per motor
    half-bridge, and KiCad reports each as `track_dangling`: V24_MOT had
    collinear tracks of 1.45, 3.45 and 4.65 mm all sharing one endpoint.

    Removing a track whose whole extent lies inside another of the same net
    and layer cannot change connectivity -- the copper stays exactly where it
    was.  Ties are broken on index so that of two identical tracks exactly one
    goes.
    """
    segs = {}
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            continue
        a, c = R.pt(t.GetStart()), R.pt(t.GetEnd())
        segs.setdefault((t.GetNetname(), t.GetLayer()), []).append((a, c))
    dead = []
    for (net, lay), lst in segs.items():
        for i, (a, c) in enumerate(lst):
            for j, (p, q) in enumerate(lst):
                if i == j:
                    continue
                if R.dist(a, c) > R.dist(p, q) + 1e-6:
                    continue
                if R.dist(a, c) == R.dist(p, q) and j < i:
                    continue
                if _online(p, q, a) and _online(p, q, c):
                    dead.append(("track", f"{a[0]:.2f},{a[1]:.2f}-"
                                          f"{c[0]:.2f},{c[1]:.2f}", lay, net))
                    break
    return dead


def orphans(board, net):
    """[(kind, key, layer)] of every item in an island that reaches no pad.

    Leaf-pruning cannot see these.  An island left behind by a rip-and-reroute
    is internally connected -- a chain of track between two vias, or a loop --
    so every item in it touches two others and none of them is a leaf, while
    the island as a whole reaches no pad at all.  KiCad calls all of it
    dangling and it is right to: 48 of `/motor_drive/V24_MOT`'s copper was
    exactly this.
    """
    items = R.net_items(board, net)
    uf = R._touch_graph(items)
    groups = {}
    for i, it in enumerate(items):
        groups.setdefault(uf.find(i), []).append(i)
    dead = []
    for ids in groups.values():
        if any(items[i][0] == "pad" for i in ids):
            continue
        for i in ids:
            kind, key, lay = items[i][0], items[i][1], items[i][2]
            dead.append((kind, key, -1 if kind == "via" else min(lay)))
    return dead


def leaves(board, net):
    """[(kind, key, layer)] of every item of `net` that hangs by one end.

    The layer belongs in the key.  A rail routed on both outer layers between
    the same two vias gives two tracks with identical endpoints, and a kill
    list keyed on geometry alone takes the copy that was not a leaf with it.
    """
    items = R.net_items(board, net)
    alive = list(range(len(items)))
    dead = []
    while True:
        cut = None
        for i in alive:
            kind, key, lay, boxes, _t = items[i]
            if kind == "pad":
                continue
            touch = 0
            for j in alive:
                if j == i or not (items[j][2] & lay):
                    continue
                if R._boxes_touch(boxes, items[j][3]):
                    touch += 1
            if touch <= 1:
                cut = i
                break
        if cut is None:
            return dead
        kind, key, lay = items[cut][0], items[cut][1], items[cut][2]
        dead.append((kind, key, -1 if kind == "via" else min(lay)))
        alive.remove(cut)


CHILD = '''
import json, sys
sys.path.insert(0, {here!r})
import pcbnew, route_lib as R
kill = set(tuple(x) for x in json.loads({kill!r}))
b = pcbnew.LoadBoard(R.PCB)
doomed = []
for t in b.GetTracks():
    n = t.GetNetname()
    if isinstance(t, pcbnew.PCB_VIA):
        q = R.pt(t.GetPosition())
        key = ("via", n, f"{{q[0]:.3f}},{{q[1]:.3f}}", -1)
    else:
        a, c = R.pt(t.GetStart()), R.pt(t.GetEnd())
        key = ("track", n,
               f"{{a[0]:.2f}},{{a[1]:.2f}}-{{c[0]:.2f}},{{c[1]:.2f}}",
               t.GetLayer())
    if key in kill:
        doomed.append(t)
for t in doomed:
    b.Remove(t)
print(json.dumps({{"removed": len(doomed)}}))
R.refill(b)
R.save(b)
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    board = R.load()
    kill, per_net = [], {}
    seen = set()
    for f in board.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if not n or n in seen or n in POURED \
                    or n.startswith("unconnected-"):
                continue
            seen.add(n)
            if len(R.pad_nodes(board, n)) < 2:
                continue
            if not R.net_is_whole(board, n):
                # Its stub is the next pass's escape and must stay -- but a
                # padless island is dead on an open net too, and is what makes
                # an unfinished board's DRC unreadable.
                got = orphans(board, n)
                if got:
                    per_net[n] = len(got)
                    kill += [(k, n, key, lay) for k, key, lay in got]
                continue
            got = orphans(board, n) + leaves(board, n)
            if got:
                per_net[n] = len(got)
                kill += [(k, n, key, lay) for k, key, lay in got]

    cov = covered(board)
    for kind, key, lay, net in cov:
        per_net[net] = per_net.get(net, 0) + 1
        kill.append((kind, net, key, lay))
    print(f"{len(kill)} dead items on {len(per_net)} nets "
          f"({len(cov)} stacked, plus padless islands and leaves)")
    for n, c in sorted(per_net.items(), key=lambda kv: -kv[1])[:15]:
        print(f"   {c:3d}  {n}")
    if a.check or not kill:
        return 0

    src = CHILD.format(here=HERE, kill=json.dumps([list(x) for x in kill]))
    out = subprocess.run([sys.executable, "-c", src], capture_output=True,
                         text=True)
    if out.returncode != 0:
        print(out.stdout, out.stderr, file=sys.stderr)
        raise SystemExit("trim failed")
    for line in out.stdout.splitlines():
        if line.strip().startswith("{"):
            print("removed", json.loads(line.strip())["removed"])
    board = R.load()
    print("unconnected now", R.unconnected(board))
    return 0


if __name__ == "__main__":
    sys.exit(main())
