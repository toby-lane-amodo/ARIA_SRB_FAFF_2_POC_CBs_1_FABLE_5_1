#!/usr/bin/env python3
"""Round 2, step 3b -- open the pocket around a blocked pad, automatically.

The residue is not congestion in general and not a layer count.  It is dozens
of instances of one shape: a pad whose escape lane is fine but whose corridor
closes a millimetre or two out, so no search at any width, margin, heuristic or
node budget can leave.  `U501.12` is the type specimen -- the free region round
it is a slot 0.3 mm tall that dead-ends after 1.5 mm.

Round 1 solved these one at a time by hand, writing a plan per pin: rip what
seals it, route the sealed net first, put the sealer back.  That doctrine is
right and there are far too many of them to keep writing plans.  So this does
it generically:

  1. take a net that will not close, and the pad that will not be reached;
  2. rip every *foreign* net's copper inside a small disc round that pad --
     never GND, never a plane, never a via that belongs to the ground stitch;
  3. route the blocked net first, while the pocket is open;
  4. put every ripped net back, in the order they were ripped.

Step 4 is the part that makes it safe: the nets that were in the way get the
whole board to detour through, and the pad that had one lane gets it.  If a
ripped net cannot be put back, the stage says so rather than leaving the board
quietly worse.

Deletion runs in a child interpreter, as everywhere else -- `board.Remove()`
mid-script poisons SWIG type resolution for every later wrapped return.

**The whole thing is transactional**, and it has to be: the first run was
interrupted between the rip and the restore and left the board seven
unconnected items worse than it started, with thirty-one items of nine nets
deleted and nothing put back.  A stage that improves the board on success and
damages it on interruption is not a stage worth having.  The board file is
snapshotted before the rip and restored on any outcome that is not a clean
win, so the worst case is that nothing happened.
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import route_lib as R  # noqa: E402

RADIUS = 3.5            # mm of pocket to open around the blocked pad
KEEP = {"GND"}          # never ripped: the ground stitch is structural

CHILD = '''
import json, sys
sys.path.insert(0, {here!r})
import pcbnew, route_lib as R
c = {centre}; rad = {rad}; keep = set({keep})
b = pcbnew.LoadBoard(R.PCB)
def near(p):
    return (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 <= rad * rad
doomed, nets = [], {{}}
for t in b.GetTracks():
    n = t.GetNetname()
    if n in keep or not n:
        continue
    if isinstance(t, pcbnew.PCB_VIA):
        if near(R.pt(t.GetPosition())):
            doomed.append(t); nets[n] = nets.get(n, 0) + 1
    elif near(R.pt(t.GetStart())) and near(R.pt(t.GetEnd())):
        doomed.append(t); nets[n] = nets.get(n, 0) + 1
for t in doomed:
    b.Remove(t)
print(json.dumps({{"removed": len(doomed), "nets": nets}}))
R.refill(b)
R.save(b)
'''


def rip(centre, rad):
    src = CHILD.format(here=HERE, centre=json.dumps(list(centre)), rad=rad,
                       keep=json.dumps(sorted(KEEP)))
    out = subprocess.run([sys.executable, "-c", src], capture_output=True,
                         text=True)
    if out.returncode != 0:
        print(out.stdout, out.stderr, file=sys.stderr)
        raise SystemExit("rip failed")
    for line in out.stdout.splitlines():
        if line.strip().startswith("{"):
            return json.loads(line.strip())
    return {"removed": 0, "nets": {}}


def blocked_pads(board, net):
    """A pad from every island, hardest first.

    The first cut took the pad in the *smallest* island, on the reasoning that
    nothing had reached it.  That is the wrong end: the smallest island is
    usually a lone resistor pad sitting in open board, and the pocket that
    actually needs opening is round the fine-pitch package pin at the other
    end.  Net-(U501A-DIN) proved it -- the rip freed 3.5 mm round R515.2, an
    0603 land with room on every side, and changed nothing.

    So every island offers a pad and they are tried in order of how little
    free space surrounds them, which is the order of how likely each is to be
    the one in the pocket.
    """
    isl = R.net_islands(board, net)
    if len(isl) < 2:
        return []
    obst = R.Obstacles(board)
    nc = R.netcode(board, net)
    out = []
    for g in isl:
        for k, name, lay, boxes, tgt in g:
            if k != "pad":
                continue
            b0 = boxes[0]
            c = ((b0[0] + b0[2]) / 2.0, (b0[1] + b0[3]) / 2.0)
            win = obst.ij(c[0] - 1.0, c[1] - 1.0) + \
                obst.ij(c[0] + 1.0, c[1] + 1.0)
            m = obst.track_mask(win, nc, R.F, R.W_SIGNAL / 2 + R.CLEAR)
            out.append((int((~m).sum()), name, c))
            break
    out.sort()
    return [(n, c) for _f, n, c in out]


def route(board, obst, maze, net, width=None, **kw):
    a = dict(via_cost=15, margin=28, hw=2.0, max_nodes=400_000, verbose=False)
    a.update(kw)
    return R.connect_net(board, obst, maze, net,
                         width=width or R.net_width(net), **a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", required=True)
    ap.add_argument("--radius", type=float, default=RADIUS)
    a = ap.parse_args()

    board = R.load()
    if R.net_is_whole(board, a.net):
        print(f"{a.net} already whole")
        return 0
    cands = blocked_pads(board, a.net)
    if not cands:
        print(f"{a.net}: no isolated pad found")
        return 1
    name, centre = cands[0]
    print(f"{a.net}: pocket round {name} at "
          f"{centre[0]:.2f},{centre[1]:.2f} "
          f"(tightest of {len(cands)} island pads)", flush=True)

    snap = R.PCB + ".pocket-snapshot"
    shutil.copyfile(R.PCB, snap)

    # SIGTERM does not raise, so `finally` never runs and the snapshot never
    # gets restored -- which is exactly how `timeout 110` left the board seven
    # items worse the first time.  The handler is the whole point of the
    # snapshot: without it this is a stage that damages the board whenever it
    # runs long, which on this board is often.
    def _bail(signum, _frame):
        shutil.copyfile(snap, R.PCB)
        print(f"   signal {signum} -- board restored from the snapshot",
              flush=True)
        # `finally` never runs on SIGTERM, so this is the only place the
        # snapshot gets deleted on that path -- one was left behind.
        try:
            os.remove(snap)
        except OSError:
            pass
        os._exit(2)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, _bail)

    try:
        return run(a, name, centre, snap)
    except BaseException:
        shutil.copyfile(snap, R.PCB)
        print("   interrupted -- board restored from the snapshot")
        raise
    finally:
        if os.path.exists(snap):
            os.remove(snap)


def run(a, name, centre, snap):
    import shutil as _sh
    info = rip(centre, a.radius)
    victims = [n for n in info["nets"] if n != a.net]
    print(f"   ripped {info['removed']} items of {len(info['nets'])} nets "
          f"within {a.radius} mm", flush=True)

    board = R.load()
    obst = R.Obstacles(board)
    maze = R.Maze(obst)
    f = route(board, obst, maze, a.net)
    ok = R.net_is_whole(board, a.net)
    print(f"   {a.net:<30} {'whole' if ok else 'STILL SPLIT'}", flush=True)
    R.refill(board)
    R.save(board)

    back, lost = 0, []
    for n in victims:
        board = R.load()
        obst = R.Obstacles(board)
        obst.reserve_pin_escapes(board)
        maze = R.Maze(obst)
        route(board, obst, maze, n)
        R.refill(board)
        R.save(board)
        board = R.load()
        if R.net_is_whole(board, n):
            back += 1
        else:
            lost.append(n)
    print(f"   {back} of {len(victims)} displaced nets put back"
          + (f"; still open {lost}" if lost else ""), flush=True)
    board = R.load()
    now = R.unconnected(board)
    if not ok or lost:
        _sh.copyfile(snap, R.PCB)
        print(f"   not a clean win ({'net still split' if not ok else ''}"
              f"{' and ' if not ok and lost else ''}"
              f"{f'{len(lost)} displaced nets lost' if lost else ''})"
              f" -- board rolled back")
        return 1
    print(f"   unconnected now {now}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
