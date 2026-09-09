#!/usr/bin/env python3
"""Routing step 12 -- put the sync clamp back in the line.

House rule: *ESD nets are routed without stubs -- track from the ESD source pin
through the ESD device pin and on to the next component pin, in that order.
The protection is in the line, never hanging off it.*

`Net-(D903-K)` came out of step 5c connected but not in that order.  The run
leaves `J902` pin 1 heading south-west toward `D903`, and `R907` taps it at
(88.70, 41.35) -- 5.6 mm along, with the clamp still 4.5 mm further on.  A
strike therefore reaches the branch and divides, and part of it is on its way
to `U901` before it has met the clamp at all.

The fix is the ordering, not the copper: source pad, clamp pad, then the series
resistor, in series.  It costs `R907` a longer approach and buys the clamp its
place at the head of the line.

Both segments are drawn at the `RF50` class width, 0.37 mm -- the 50 ohm
microstrip for this stackup (setup S2).  The chain is 50 ohm from the SMA to
the source termination, and the clamp's own stub to ground is `D903` pin 2's
own via, which step 3 already placed.
"""
import json
import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import route_lib as R  # noqa: E402

NET = "Net-(D903-K)"
RIP_BOX = (83.0, 34.0, 98.0, 49.0)
W = 0.37

# J902.1 (90.00, 36.25) -> D903.1 (85.05, 44.20) -> R907.2 (90.00, 42.675).
# The first leg is the one that matters and it is drawn straight; the second
# leaves the clamp pad eastward and comes up under R907 from the south.
TO_CLAMP = [(90.00, 36.25), (89.25, 37.50), (89.25, 40.30),
            (85.75, 43.80), (85.00, 44.20)]
# R907 stands vertically with pin 1 north of pin 2, so the second leg has to
# reach pin 2 from the *west*: an approach from the north walks straight
# through pin 1, which is the other side of the series resistor and a
# different net.
TO_R907 = [(85.00, 44.20), (86.00, 45.20), (87.60, 45.20),
           (88.60, 44.20), (88.60, 42.675), (90.00, 42.675)]

CHILD = '''
import json, sys
sys.path.insert(0, {here!r})
import pcbnew, route_lib as R
box = {box}; nets = set({nets})
b = pcbnew.LoadBoard(R.PCB)
def ins(p):
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]
doomed = []
for t in b.GetTracks():
    if t.GetNetname() not in nets:
        continue
    if isinstance(t, pcbnew.PCB_VIA):
        if ins(R.pt(t.GetPosition())):
            doomed.append(t)
    elif ins(R.pt(t.GetStart())) and ins(R.pt(t.GetEnd())):
        doomed.append(t)
for t in doomed:
    b.Remove(t)
print(json.dumps({{"removed": len(doomed)}}))
R.refill(b)
R.save(b)
'''


def rip():
    src = CHILD.format(here=HERE, box=json.dumps(list(RIP_BOX)),
                       nets=json.dumps([NET]))
    out = subprocess.run([sys.executable, "-c", src], capture_output=True,
                         text=True)
    if out.returncode != 0:
        print(out.stdout, out.stderr, file=sys.stderr)
        raise SystemExit("rip failed")
    for line in out.stdout.splitlines():
        if line.strip().startswith("{"):
            return json.loads(line.strip())["removed"]
    return 0


def plen(pts):
    return sum(R.dist(a, b) for a, b in zip(pts, pts[1:]))


def main():
    print(f"ripped {rip()} items of {NET}")
    board = R.load()
    nc = R.netcode(board, NET)
    R.polyline(board, TO_CLAMP, W, R.F, nc)
    R.polyline(board, TO_R907, W, R.F, nc)
    R.refill(board)
    R.save(board)
    board = R.load()
    print(f"   J902.1 -> D903.1  {plen(TO_CLAMP):5.2f} mm @ {W}")
    print(f"   D903.1 -> R907.2  {plen(TO_R907):5.2f} mm @ {W}")
    print(f"   {NET}: "
          f"{'whole' if R.net_is_whole(board, NET) else 'SPLIT'}")
    print("unconnected now:", R.unconnected(board))


if __name__ == "__main__":
    main()
