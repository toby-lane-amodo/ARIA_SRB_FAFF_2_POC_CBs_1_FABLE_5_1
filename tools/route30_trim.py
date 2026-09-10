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
                continue        # its stub is the next pass's escape
            got = leaves(board, n)
            if got:
                per_net[n] = len(got)
                kill += [(k, n, key, lay) for k, key, lay in got]

    print(f"{len(kill)} dangling items on {len(per_net)} whole nets")
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
