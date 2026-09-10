#!/usr/bin/env python3
"""Move an autorouter's vias out of the pads they were drilled into (G9).

Round 3's Experiment B is the best-connected board this project has produced --
33 unconnected against our 85 -- and it is not adoptable, because it puts 53
vias in pads.  G9 forbids that outright and the only standing exception is the
client-ruled QFN exposed-pad array, which `route_check` already exempts.  The
tool has no option to prevent it, so it has to be repaired afterwards.

A via in a pad is repaired by sliding it along the track it belongs to until
its barrel clears every foreign land, then dragging that track's endpoint with
it.  The direction is the track's own -- the via got there by being placed at
the end of a run, so backing it off along that run is the move that keeps the
route's shape.  A via that cannot be freed within `REACH` is removed together
with the stub that held it, which re-opens its net; that is reported rather
than hidden, because an open net is a smaller lie than a via in a pad.

Reads and writes whatever `--board` points at.  `route_lib.save` honours that
now; it did not always, which is how a scratch strip once landed on the
master.
"""
import argparse
import json
import math
import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import route_lib as R  # noqa: E402
import route_check as RC  # noqa: E402

REACH = 2.0             # mm the via may slide along its own track
STEP = 0.05


def offenders(board):
    """[(pos, net)] of every via G9 forbids, by route_check's own rule."""
    allowed = {(f.GetReference(), p.GetNumber())
               for f in board.GetFootprints() for p in f.Pads()
               if (f.GetReference(), p.GetNumber()) in RC.EP_PADS}
    pads = [(f.GetReference(), p.GetNumber(), R.pad_bbox(p), p)
            for f in board.GetFootprints() for p in f.Pads()
            if R.pad_copper_layers(p)]
    out = []
    for q, net in RC.vias(board):
        for ref, num, bb, p in pads:
            dx = max(bb[0] - q[0], 0.0, q[0] - bb[2])
            dy = max(bb[1] - q[1], 0.0, q[1] - bb[3])
            d = math.hypot(dx, dy)
            if d >= R.VIA_D / 2.0 or (ref, num) in allowed:
                continue
            if d < R.VIA_DRILL / 2.0 or p.GetNetname() != net:
                out.append((q, net))
                break
    return out


def clear_of_pads(board_pads, q, allowed):
    for ref, num, bb, _p in board_pads:
        if (ref, num) in allowed:
            continue
        dx = max(bb[0] - q[0], 0.0, q[0] - bb[2])
        dy = max(bb[1] - q[1], 0.0, q[1] - bb[3])
        if math.hypot(dx, dy) < R.VIA_D / 2.0:
            return False
    return True


CHILD = '''
import json, math, sys
sys.path.insert(0, {here!r})
import pcbnew, route_lib as R
R.PCB = {board!r}
plan = json.loads({plan!r})
b = pcbnew.LoadBoard(R.PCB)

# One pass over GetTracks, then act.  `Remove()` poisons SWIG type resolution
# for every wrapped return after it, so a loop that removes and then asks the
# board for its tracks again dies on the next iteration -- it did.  Gather
# first, move second, remove last.
by_pos = {{}}
for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA):
        key = (round(R.pt(t.GetPosition())[0], 3),
               round(R.pt(t.GetPosition())[1], 3))
        by_pos.setdefault(key, []).append(("via", t))
    else:
        for tag, pt_ in (("start", R.pt(t.GetStart())),
                         ("end", R.pt(t.GetEnd()))):
            by_pos.setdefault((round(pt_[0], 3), round(pt_[1], 3)),
                              []).append((tag, t))

moved = dropped = 0
doomed = []
for item in plan:
    key = (round(item["old"][0], 3), round(item["old"][1], 3))
    hits = by_pos.get(key, [])
    new_xy = item.get("new")
    if new_xy is None:
        doomed += [t for _tag, t in hits]
        dropped += 1
        continue
    p = pcbnew.VECTOR2I(R.mm(new_xy[0]), R.mm(new_xy[1]))
    for tag, t in hits:
        if tag == "via":
            t.SetPosition(p)
        elif tag == "start":
            t.SetStart(p)
        else:
            t.SetEnd(p)
    moved += 1

for t in doomed:
    b.Remove(t)
print(json.dumps({{"moved": moved, "dropped": dropped,
                  "removed_items": len(doomed)}}))
R.refill(b)
R.save(b)
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    R.PCB = a.board

    board = R.load()
    allowed = {(f.GetReference(), p.GetNumber())
               for f in board.GetFootprints() for p in f.Pads()
               if (f.GetReference(), p.GetNumber()) in RC.EP_PADS}
    pads = [(f.GetReference(), p.GetNumber(), R.pad_bbox(p), p)
            for f in board.GetFootprints() for p in f.Pads()
            if R.pad_copper_layers(p)]
    bad = offenders(board)
    print(f"{len(bad)} vias in a pad (G9)")

    # the track directions each via sits on
    ends = {}
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            continue
        for p, other in ((R.pt(t.GetStart()), R.pt(t.GetEnd())),
                         (R.pt(t.GetEnd()), R.pt(t.GetStart()))):
            ends.setdefault((round(p[0], 3), round(p[1], 3)), []).append(other)

    obst = R.Obstacles(board)
    plan, freed, lost = [], 0, 0
    for q, net in bad:
        dirs = []
        for o in ends.get((round(q[0], 3), round(q[1], 3)), []):
            L = R.dist(q, o)
            if L > 1e-6:
                dirs.append(((o[0] - q[0]) / L, (o[1] - q[1]) / L))
        best = None
        for u in dirs or [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            k = STEP
            while k <= REACH:
                c = (round(q[0] + u[0] * k, 3), round(q[1] + u[1] * k, 3))
                if clear_of_pads(pads, c, allowed):
                    win = obst.ij(c[0] - 1.0, c[1] - 1.0) + \
                        obst.ij(c[0] + 1.0, c[1] + 1.0)
                    m = obst.via_mask(win, R.netcode(board, net))
                    ii, jj = obst.ij(*c)
                    if not m[ii - win[0], jj - win[1]]:
                        best = c
                        break
                k += STEP
            if best:
                break
        plan.append({"old": list(q), "new": list(best) if best else None})
        if best:
            freed += 1
        else:
            lost += 1
    print(f"   {freed} can slide clear; {lost} must be removed (net re-opens)")
    if not a.yes:
        print("dry run -- pass --yes")
        return 0

    src = CHILD.format(here=HERE, board=a.board, plan=json.dumps(plan))
    out = subprocess.run([sys.executable, "-c", src], capture_output=True,
                         text=True)
    if out.returncode != 0:
        print(out.stdout, out.stderr, file=sys.stderr)
        raise SystemExit("unpad failed")
    for line in out.stdout.splitlines():
        if line.strip().startswith("{"):
            print("   ", line.strip())
    board = R.load()
    print(f"remaining G9 vias: {len(offenders(board))}")
    print(f"unconnected now {R.unconnected(board)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
