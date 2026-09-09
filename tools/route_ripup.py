#!/usr/bin/env python3
"""Windowed rip-up and reroute.

Three pins came out of step 4 unreachable, and all three for the same reason:
another net's copper had taken the pin's only escape lane.  `U1101` pin 5's
lane ends 0.475 mm short of `VM_DRV`'s wall -- too narrow for a trace to pass
and far too narrow for a via -- and `U302`/`U303` pin 7 sit under the `+6V0`
tie that loops from pin 8 over the package to pin 5.  That is the hazard R3-1
names: *an IC's pin ring is escape lanes wall to wall*, and a router with no
memory of it will wall a pin in and then be unable to reach it from anywhere.

No amount of retrying reaches a sealed pin, so the answer is the standard one:
rip the copper that sealed it, route the sealed net **first**, and put the
ripped net back afterwards -- it has the whole board to detour through and the
sealed pin has one lane.

Ripping is windowed: only tracks and vias with **both** ends inside the box
go, so a board-spanning rail loses its local detail and keeps its trunk.
Deletion runs in a **child interpreter** that saves and exits, because
`board.Remove()` mid-script poisons SWIG type resolution for every later
wrapped return in the same process (pcb-layout-style, KiCad 9 quirks).

    python3 tools/route_ripup.py --plan u1101-vm
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

# A plan is: a window, the nets to rip inside it, then passes of nets to
# route in order.  A pass may drop `reserve` -- the pin-escape reservation
# `Obstacles.reserve_pin_escapes` lays down.  That reservation is what keeps a
# stray trace out of an IC's pin ring, and it is right almost everywhere; for
# a pin that is *already* sealed it is the last straw, because leaving the
# package means crossing a neighbour's held lane at right angles a millimetre
# out.  U302 pin 7 routes in 13.98 mm with the reservations off and not at all
# with them on.  So the sealed net runs first with them off -- by this stage
# every pin it could cap already carries real fan-out copper, which is a real
# obstacle -- and the ripped net goes back with them on.  `fanout` is the same
# argument one step further: the fan-out pass re-stubs whatever the rip left
# split, and for U302 those stubs are the two +6V0 pins either side of the
# sealed one, so it must not run until the sealed net has its lane.
PLANS = {
    # U1101 pins 4 (VM) and 5 (VDRAIN) are adjacent on a 0.5 mm pitch and both
    # have to leave east.  Step 4 gave the corridor to VM_DRV and V24_MOT
    # could not reach pin 5; ripping VM_DRV alone just swapped which one lost.
    # Both are ripped, VM_DRV takes the F.Cu lane it needs to reach its own
    # decoupling, and V24_MOT is biased onto B.Cu so the two cross layers
    # rather than corridors.
    "u1101-pair": dict(
        box=(212.5, 137.5, 227.0, 149.0),
        rip=["/motor_drive/VM_DRV", "/motor_drive/V24_MOT"],
        passes=[
            dict(reserve=False, nets=[("/motor_drive/VM_DRV", 0.25, {})]),
            dict(reserve=False, nets=[("/motor_drive/V24_MOT", 0.25,
                                       dict(layer_bias={R.F: 0.5}))]),
        ],
    ),
    # U302/U303 pin 7 (PGOOD) sits between pin 8 and pin 6 on a 0.5 mm pitch
    # with the exposed pad to its south, so north is its only way out -- and
    # step 4's "tie VIN's two pins at the package" link loops from pin 8 north
    # over the row to pin 5, straight across it.  The tie is a convenience;
    # the PGOOD pin has nowhere else to go, so it is drawn first and the tie
    # routes around it.
    # ...and each of those plans, having run, sealed the pin it had just been
    # let past.  PGOOD left pin 7 and elbowed west across pin 8's lane at
    # y = 65.80, 0.20 mm above the pad's north edge, which leaves +6V0's own
    # supply pin 0.048 mm of travel.  Trading one sealed pin for another is
    # not a fix.
    #
    # Ordering and reservations both just pick a winner, and so, on its own,
    # does the fan-out: run with +6V0 first and PGOOD came out sealed instead,
    # which is the same trade in the other direction.
    #
    # What actually breaks the tie is the asymmetry between the two nets.
    # +6V0 has *two* pins on this package -- 5 and 8, at opposite ends of the
    # row -- so it needs a tie across the row, and that tie is the thing that
    # crosses PGOOD's lane.  PGOOD has one pin and a long run west.  So +6V0
    # is biased onto B.Cu and takes its tie *under* the ring, which leaves the
    # F.Cu lane in front of pin 7 to the net that has nowhere else to be.  The
    # fan-out stays, because it is what stops either one sealing the other
    # while they are drawn.
    "u302-pg": dict(
        box=(172.0, 62.5, 179.5, 69.5),
        rip=["/power_rails/+6V0", "Net-(U302-PG)"],
        passes=[
            dict(reserve=False, fanout=True, nets=[
                ("/power_rails/+6V0", 0.30,
                 dict(layer_bias={R.F: 2.0}, via_cost=8)),
                ("Net-(U302-PG)", 0.20, {})]),
        ],
    ),
    # J601 is a 10-way 0.5 mm FPC and all ten pins fan north.  Step 4 took
    # +5V_ENC to pin 9 across that fan -- a wall on F.Cu at y = 149.55 from
    # x = 126.15 to 130.5, 1.4 mm above the pad tops, plus two vias parked in
    # pins 6-9's lanes -- and sealed nine pins in.  Every RS-422 pair came out
    # of step 5 split with its J601 end alone in its own island, and no amount
    # of retrying reaches a sealed pin.
    #
    # So the fan goes first, all eight signals, and the supply goes back
    # afterwards: it has the whole board to detour through and the pins have
    # one lane each.  R3-1, and the same shape as the two PGOOD plans above.
    "j601-fan": dict(
        box=(122.0, 142.0, 134.0, 152.5),
        rip=["/linear_encoder/+5V_ENC"],
        passes=[
            dict(reserve=True, nets=[
                (n, 0.20, {}) for n in (
                    "/linear_encoder/ENC_A_P", "/linear_encoder/ENC_A_N",
                    "/linear_encoder/ENC_B_P", "/linear_encoder/ENC_B_N",
                    "/linear_encoder/ENC_Z_P", "/linear_encoder/ENC_Z_N",
                    "/linear_encoder/ENC_nPROG", "/linear_encoder/ENC_SDO")]),
            dict(reserve=True, nets=[("/linear_encoder/+5V_ENC", 0.50,
                                      dict(layer_bias={R.B: 0.4}))]),
        ],
    ),
    # The DRV8323's east row, again.  route8_drv drew the block in priority
    # order and got the Kelvin taps in first, which was right -- but it built
    # its obstacle model *without* `reserve_pin_escapes`, so nothing held the
    # neighbouring pins' lanes while it worked.  Leg A's tap left pin 9 and
    # elbowed 0.15 mm north to y = 139.40; pin 8 is 0.5 mm above it at 139.75
    # and pin 7's own run sits at 140.25, which leaves pin 8 a 0.60 mm slot
    # for a trace that needs 0.4572 of copper and 0.3048 of clearance.  Five
    # microns short, and the low-side gate was sealed.  The same happened on
    # legs B and C, and on VM_DRV at pin 4.
    #
    # The priority stands -- accuracy before length, taps before gates -- but
    # the reservations go on, so neither can take the other's lane.
    "u1101-gates": dict(
        box=(207.5, 134.0, 220.5, 144.5),
        # Ripping the *whole* east row was tried and is not kept.  It did
        # prove the point -- with MOTOR_U and Q1101-G out of the way,
        # Q1102-G reached U1101.8 and only its FET end stayed open -- but it
        # cost MOTOR_U, which had been whole, so the count went from four
        # open to five.  The row cannot carry its nets; ripping more of it
        # only changes which one loses.  That is the placement finding in
        # docs/decisions/actuator-pcb-route1.md S12, not something to keep
        # re-deciding here.
        rip=["Net-(Q1102-G)", "Net-(Q1104-G)", "Net-(Q1106-G)",
             "Net-(Q1102-S_3)", "Net-(Q1104-S_3)", "Net-(Q1106-S_3)",
             "/motor_drive/VM_DRV"],
        passes=[
            dict(reserve=True, nets=[
                ("Net-(Q1102-S_3)", 0.25, {}),
                ("Net-(Q1104-S_3)", 0.25, {}),
                ("Net-(Q1106-S_3)", 0.25, {})]),
            # Reservations OFF for the gates, and this is the trade-off this
            # file already names: a held lane is right almost everywhere, but
            # a gate run is 25 mm from the FET to the driver and every
            # package it passes has its own ring held.  With 320 lanes held
            # board-wide there is no path at all.  Pass 1 above fanned six
            # pins into real copper stubs, and copper is what protects the
            # local lanes now -- so the long runs are free to cross elsewhere
            # and the pins they must reach are still not seal-able.
            dict(reserve=False, fanout=False, nets=[
                ("Net-(Q1102-G)", 0.25, {}),
                ("Net-(Q1104-G)", 0.25, {}),
                ("Net-(Q1106-G)", 0.25, {})]),
            dict(reserve=False, fanout=False,
                 nets=[("/motor_drive/VM_DRV", 0.25, {})]),
        ],
    ),
    "u303-pg": dict(
        box=(172.0, 76.5, 179.5, 83.5),
        rip=["/power_rails/+6V0", "Net-(U303-PG)"],
        passes=[
            dict(reserve=False, fanout=True, nets=[
                ("/power_rails/+6V0", 0.30,
                 dict(layer_bias={R.F: 2.0}, via_cost=8)),
                ("Net-(U303-PG)", 0.20, {})]),
        ],
    ),
}

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
    else:
        if inside(R.pt(t.GetStart())) and inside(R.pt(t.GetEnd())):
            doomed.append(t)
for t in doomed:
    b.Remove(t)
print(json.dumps({{"removed": len(doomed)}}))
R.refill(b)
R.save(b)
'''


def rip(box, nets):
    """Delete matching copper in a child interpreter that saves and exits."""
    src = CHILD.format(here=HERE, box=json.dumps(list(box)),
                       nets=json.dumps(list(nets)))
    out = subprocess.run([sys.executable, "-c", src], capture_output=True,
                         text=True)
    if out.returncode != 0:
        print(out.stdout)
        print(out.stderr, file=sys.stderr)
        raise SystemExit("rip failed")
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)["removed"]
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, choices=sorted(PLANS))
    a = ap.parse_args()
    p = PLANS[a.plan]

    n = rip(p["box"], p["rip"])
    print(f"ripped {n} items of {p['rip']} inside {p['box']}")

    board = R.load()
    routed = []
    for k, ps in enumerate(p["passes"]):
        obst = R.Obstacles(board)
        if ps["reserve"]:
            print(f"== pass {k + 1}: "
                  f"{obst.reserve_pin_escapes(board)} escape lanes held")
        else:
            print(f"== pass {k + 1}: escape reservations OFF "
                  f"(the sealed pin cannot cross a held lane to get out)")
        maze = R.Maze(obst)
        if ps.get("fanout", True):
            R.escape_pass(board, obst)
        for net, w, kw in ps["nets"]:
            # A plan may override the search parameters, not just add to them.
            # Biasing a net onto B.Cu is useless while the via cost is pinned
            # at 45: the two vias the layer change needs outprice the detour
            # the bias was meant to avoid, and the router stays on F.Cu.
            args = dict(via_cost=45, margin=24)
            args.update(kw)
            f = R.connect_net(board, obst, maze, net, width=w, **args)
            whole = R.net_is_whole(board, net)
            routed.append(net)
            print(f"   {net:<30} @ {w:4.2f}  "
                  f"{'whole' if whole else 'STILL SPLIT'}"
                  + (f"  unrouted {sorted(set(f))}" if f else ""))

    R.refill(board)
    R.save(board)
    bad = [net for net in routed if not R.net_is_whole(board, net)]
    print("\nstill split:", bad or "none")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
