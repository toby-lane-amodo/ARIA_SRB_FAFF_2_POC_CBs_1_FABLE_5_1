#!/usr/bin/env python3
"""Routing step 8 -- redo the DRV8323 interface in priority order.

Step 5 draws the bridge leg by leg and then net by net, and in the motor block
that is not enough.  Fourteen nets have to reach one 6 mm package from three
legs spread over 30 mm, through a channel that also carries the motor bus and
the driver's own supply, and the first net to ask for the channel gets it.
Step 5 came out with leg U's high gate, leg W's low gate, all three Kelvin
taps and leg W's phase sense unrouted.

Two things about the pinout make this harder than it looks, and both are worth
the captain's eye:

* **The north edge is planar; the east edge is not.**  Pins 19..12 take leg W
  then leg V in the same order their sources sit in, west to east, so they
  nest -- routed west pin first, each run hugs the last.  The east row does
  not: its sources run north to south as Q1101 gate, phase node, Q1102 gate,
  R1125, R1114, and their pins run 6, 7, 8, 9, 5/4 -- the high-side gate comes
  from the furthest north and lands on the *southmost* of the four.  Those
  four must cross, so on one layer they cannot all be drawn.  Vias on the two
  that cross is the cheapest answer and it is what this stage takes; place1
  open point 1 wanted all six gates F.Cu and via-free, and five of six are.

* **Priority is accuracy, not length.**  The Kelvin taps go first.  They are
  short, they have exactly one useful path each -- from the shunt's own pad,
  not from the power path -- and the CSA's gain error is whatever IR drop the
  tap picks up.  A gate run that detours 4 mm costs nanoseconds of edge; a
  Kelvin tap that detours costs percent of current-sense accuracy.

Everything in the window is ripped first (child interpreter -- Remove()
poisons SWIG), so no net is routed around a competitor that will itself be
redrawn.  The bus and the phase outputs are put back last, at motor width.
"""
import json
import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import route_lib as R  # noqa: E402

BOX = (193.0, 111.0, 235.0, 153.0)

W_GATE = 0.40
W_KELVIN = 0.25
W_SENSE = 0.30
W_PHASE = 1.00

# Ripped wholesale inside BOX.  MOTOR_U/V/W are NOT here: their phase nodes
# and the B.Cu runs to J1103 are correct and are the tightest copper on the
# board.  V24_MOT and VM_DRV are, because between them they own the channel.
RIP = ["/motor_drive/VM_DRV", "/motor_drive/V24_MOT",
       "Net-(Q1101-G)", "Net-(Q1102-G)", "Net-(Q1103-G)",
       "Net-(Q1104-G)", "Net-(Q1105-G)", "Net-(Q1106-G)"]

# (label, net, from, to, width, layers, kwargs)
F = R.F
FB = (R.F, R.B)

KELVIN = [
    ("SPC Kelvin", "Net-(Q1106-S_3)", ("R1127", "1"), ("U1101", "19"),
     W_KELVIN, FB, dict(via_cost=60, margin=22)),
    ("SPB Kelvin", "Net-(Q1104-S_3)", ("R1126", "1"), ("U1101", "12"),
     W_KELVIN, FB, dict(via_cost=60, margin=22)),
    ("SPA Kelvin", "Net-(Q1102-S_3)", ("R1125", "1"), ("U1101", "9"),
     W_KELVIN, FB, dict(via_cost=60, margin=22)),
]

# North edge, west pin first -- source order and pin order agree, so they nest.
GATES_N = [
    ("GLC", "Net-(Q1106-G)", ("Q1106", "4"), ("U1101", "18")),
    ("GHC", "Net-(Q1105-G)", ("Q1105", "4"), ("U1101", "16")),
    ("GHB", "Net-(Q1103-G)", ("Q1103", "4"), ("U1101", "15")),
    ("GLB", "Net-(Q1104-G)", ("Q1104", "4"), ("U1101", "13")),
]
# East row -- these are the two that have to cross the others.
GATES_E = [
    ("GHA", "Net-(Q1101-G)", ("Q1101", "4"), ("U1101", "6")),
    ("GLA", "Net-(Q1102-G)", ("Q1102", "4"), ("U1101", "8")),
]

SENSE = [
    ("SHC", "/motor_drive/MOTOR_W", ("Q1106", "5_6_7_8"), ("U1101", "17")),
    ("SHB", "/motor_drive/MOTOR_V", ("Q1104", "5_6_7_8"), ("U1101", "14")),
    ("SHA", "/motor_drive/MOTOR_U", ("Q1102", "5_6_7_8"), ("U1101", "7")),
]

CHILD = r'''
import sys, json
sys.path.insert(0, {here!r})
import pcbnew, route_lib as R
box = json.loads({box!r})
nets = set(json.loads({nets!r}))
b = pcbnew.LoadBoard(R.PCB)
def inside(p):
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]
doomed = []
for t in b.GetTracks():
    if t.GetNetname() not in nets:
        continue
    if isinstance(t, pcbnew.PCB_VIA):
        if inside(R.pt(t.GetPosition())):
            doomed.append(t)
    elif inside(R.pt(t.GetStart())) and inside(R.pt(t.GetEnd())):
        doomed.append(t)
for t in doomed:
    b.Remove(t)
print(json.dumps({{"removed": len(doomed)}}))
R.refill(b)
R.save(b)
'''


def rip():
    src = CHILD.format(here=HERE, box=json.dumps(list(BOX)),
                       nets=json.dumps(RIP))
    out = subprocess.run([sys.executable, "-c", src], capture_output=True,
                         text=True)
    if out.returncode != 0:
        print(out.stdout, out.stderr, file=sys.stderr)
        raise SystemExit("rip failed")
    for line in out.stdout.splitlines():
        if line.strip().startswith("{"):
            return json.loads(line.strip())["removed"]
    return 0


def draw(board, obst, maze, rows, width, layers, **base):
    bad = []
    for row in rows:
        label, net, a, bpad = row[0], row[1], row[2], row[3]
        w = row[4] if len(row) > 4 else width
        lay = row[5] if len(row) > 5 else layers
        kw = dict(base)
        if len(row) > 6:
            kw.update(row[6])
        ln, ww, nv, direct = R.link(board, obst, maze, net, a, bpad, w,
                                    layers=lay, **kw)
        if ln is None:
            bad.append(label)
            print(f"   {label:<12} {net:<24} FAILED")
            continue
        print(f"   {label:<12} {net:<24} {ln:6.2f} mm @ {ww:.2f}  "
              f"vias {nv}  (direct {direct:.2f})")
    return bad


def main():
    n = rip()
    print(f"ripped {n} items inside {BOX}\n")

    board = R.load()
    obst = R.Obstacles(board)
    maze = R.Maze(obst)

    print("== 1. Kelvin taps first -- the CSA's accuracy is the tightest "
          "constraint in the block")
    bad = draw(board, obst, maze, KELVIN, W_KELVIN, FB)

    print("\n== 2. north-edge gates, west pin first (source order == pin "
          "order, so they nest)")
    bad += draw(board, obst, maze, GATES_N, W_GATE, (F,),
                margin=24, allow_layer_change=False)

    print("\n== 3. east-row gates -- these two cross the row and take vias")
    bad += draw(board, obst, maze, GATES_E, W_GATE, FB,
                margin=26, via_cost=90)

    print("\n== 4. phase sense")
    bad += draw(board, obst, maze, SENSE, W_SENSE, FB,
                margin=24, via_cost=70)

    print("\n== 5. the bus and the driver supply back, at motor width")
    for net, w, bias in (("/motor_drive/V24_MOT", W_PHASE, 0.0),
                         ("/motor_drive/VM_DRV", 0.25, 0.3)):
        f = R.connect_net(board, obst, maze, net, width=w, via_cost=45,
                          margin=24, layer_bias={R.F: bias})
        print(f"   {net:<28} @ {w:4.2f}  "
              + ("whole" if R.net_is_whole(board, net) else f"SPLIT {f}"))
        if not R.net_is_whole(board, net):
            bad.append(net)

    print("\n== 6. anything the passes above left, on a fresh model")
    todo = [r[1] for r in KELVIN + GATES_N + GATES_E + SENSE]
    todo = [n for n in dict.fromkeys(todo) if not R.net_is_whole(board, n)]
    if todo:
        R.refill(board)
        R.save(board)
        board = R.load()
        left = R.repair(board, todo,
                        tries=(dict(via_cost=40, margin=30),
                               dict(via_cost=25, margin=55)))
        print(f"   retried {todo} -> still open: {left or 'none'}")
        bad = [x for x in bad if x in left or x in todo] if left else []

    R.refill(board)
    R.save(board)
    print(f"\nunrouted: {sorted(set(bad)) or 'none'}")
    print("unconnected now:", R.unconnected(board))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
