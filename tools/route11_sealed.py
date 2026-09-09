#!/usr/bin/env python3
"""Routing step 11 -- free the two pins an earlier step sealed in.

`C1020` is the PHY's 1V8 decoupler and its ground pad's in-line escape is due
south (R3-1: a stitch via sits in its pin's own lane, straight out).  Due south
of that pad is also the only corridor `U1002` pins 25 and 26 have -- the USB
crystal pair, on a 0.5 mm pitch with the package's south row below them -- and
the stub plus its via sits straight across both.  Neither net could be routed
around it, and no amount of retrying reaches a sealed pin.

R3-1 says exactly what to do when a pin's in-line lane is genuinely taken:
swing the via, check the deviation against every neighbour's *real* escape
direction, and log it.  Here the neighbour that needs the lane is a pair of
crystal pins with no alternative at all, and `C1020`'s ground has open board to
its north-west, so the ground via swings and the crystal pair gets the lane.

The swing costs the decoupler's return loop about 0.9 mm of stub against 0.7 mm
before -- the loop is still the cap's own pad to its own via, and the plane is
0.2 mm below it.  That is the cheaper of the two.
"""
import json
import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import route_lib as R  # noqa: E402

# The stub and via as drawn: (143.75, 56.27) -> via (143.632, 55.601).
RIP_BOX = (143.0, 54.9, 144.5, 56.4)
RIP_NETS = ["GND"]

PAD = (143.75, 56.27)          # C1020 pad 2 centre
STUB = [(143.75, 56.27), (142.90, 56.60)]
VIA = (142.90, 56.60)
W_STUB = 0.56                  # unchanged: the widest that fits the pad

XTAL = ["/mcu/USB_XO_24M", "/mcu/USB_REFCLK_24M"]

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
                       nets=json.dumps(RIP_NETS))
    out = subprocess.run([sys.executable, "-c", src], capture_output=True,
                         text=True)
    if out.returncode != 0:
        print(out.stdout, out.stderr, file=sys.stderr)
        raise SystemExit("rip failed")
    for line in out.stdout.splitlines():
        if line.strip().startswith("{"):
            return json.loads(line.strip())["removed"]
    return 0


def main():
    print(f"ripped {rip()} GND items inside {RIP_BOX}")

    # 1. The crystal pair first, into the lane the ground via has vacated.
    board = R.load()
    obst = R.Obstacles(board)
    obst.reserve_pin_escapes(board)
    maze = R.Maze(obst)
    for net in XTAL:
        f = R.connect_net(board, obst, maze, net, width=0.20, via_cost=60,
                          margin=26, verbose=False)
        print(f"   {net:<24} "
              + ("whole" if R.net_is_whole(board, net) else f"SPLIT {f}"))
    R.refill(board)
    R.save(board)

    # 2. Then the ground stitch back, swung north-west out of that lane.
    board = R.load()
    nc = R.netcode(board, "GND")
    R.polyline(board, STUB, W_STUB, R.F, nc)
    R.add_via(board, VIA, nc)
    R.refill(board)
    R.save(board)
    print(f"   C1020.2 stitch re-laid: {PAD} -> via {VIA}")
    print("unconnected now:", R.unconnected(board))


if __name__ == "__main__":
    main()
