#!/usr/bin/env python3
"""Routing step 4d -- undo step 4c's widening where it was not warranted.

Step 4c sizes a bridge segment from the rail's design current whenever a load
sits behind it, and its first cut counted any `U`-prefixed pad as a load.  On
`V24_MOT` that swept in `U1101` pin 5, which is **VDRAIN** -- the DRV8323's
high-impedance drain sense, drawing microamps -- and grew its stub and the
run behind it to the 1.0 mm Motor class width.  1.0 mm of copper through the
channel between the driver and the shunt row is not free: that channel is
also where leg U's gate run and its Kelvin tap have to go, and both failed.

So this stage narrows back every bridge segment that step 4c widened whose
far side holds **one** load pad, restoring the width it had before -- the
width the router chose as the widest that fitted, which is the right answer
for a branch.  Trunk segments, with the rail's real load behind them, keep
their new width.

`--before` is the pre-4c board; the widths come from there rather than from a
rule, so nothing is invented.  Reports what it changes and leaves the rest.
"""
import argparse
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402
from route4_power import VIA_BUDGET  # noqa: E402
from route4c_widen import bridges, is_load  # noqa: E402

# Pins that are a sense or reference input, never a current path.  A branch
# ending on one of these carries nothing and is sized for nothing.
SENSE_PINS = {("U1101", "5")}      # DRV8323 VDRAIN


def widths(path):
    b = pcbnew.LoadBoard(path)
    out = {}
    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            continue
        p, q = R.pt(t.GetStart()), R.pt(t.GetEnd())
        out[(t.GetNetname(), f"{p[0]:.2f},{p[1]:.2f}-{q[0]:.2f},{q[1]:.2f}")] \
            = R.tomm(t.GetWidth())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True,
                    help="board file as it was before step 4c")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    old = widths(a.before)
    board = R.load()
    by_key = {}
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            continue
        p, q = R.pt(t.GetStart()), R.pt(t.GetEnd())
        by_key.setdefault(
            (t.GetNetname(),
             f"{p[0]:.2f},{p[1]:.2f}-{q[0]:.2f},{q[1]:.2f}"), []).append(t)

    changed = 0
    for net in sorted(VIA_BUDGET):
        try:
            R.netcode(board, net)
        except KeyError:
            continue
        for key, pads in bridges(board, net):
            loads = [p for p in pads if is_load(p)]
            sense = all(tuple(p.split(".")) in SENSE_PINS for p in loads)
            if len(loads) > 1 and not sense:
                continue
            was = old.get((net, key))
            if was is None:
                continue
            for t in by_key.get((net, key), []):
                now = R.tomm(t.GetWidth())
                if now <= was + 1e-6:
                    continue
                print(f"   {net:<28} {key:<32} {now:.3f} -> {was:.3f}  "
                      f"branch, behind it: {loads[:3]}")
                if not a.check:
                    t.SetWidth(R.mm(was))
                changed += 1

    if changed and not a.check:
        R.refill(board)
        R.save(board)
    print(f"\n{changed} branch segments narrowed back to their routed width")
    return 0


if __name__ == "__main__":
    sys.exit(main())
