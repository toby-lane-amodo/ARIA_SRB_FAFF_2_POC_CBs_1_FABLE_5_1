#!/usr/bin/env python3
"""Escape-first re-route: rip the signals, fan every pin out, then route.

Stage A's measurement is the whole justification and it is worth restating
because it inverts the obvious reading.  With copper stripped, all 201 pads of
the fine-pitch packages have open escape room; with the routing in place, 59
are starved.  The board is not short of room -- the routing takes it, because
ordinary signals routed early, took the shortest path they could see, and
walled in the pins they passed.

So the order changes.  Signals come out, every fine-pitch pin gets its own
escape to a via in open board, and only then does anything long get drawn.
After the fan-out no net *can* wall another in: the copper that would have
done the walling is already there, and it is the escape.

What survives the rip, and why:

* **GND** -- the planes and the one-via-per-pad stitch are structural and
  proved (`route_check --gnd`); nothing about them is the problem.
* **The inner rails** on In2/In3 and the `+3V3` pour -- round 2's work, on
  layers the signals do not use.
* **The outer power** that had to stay outside: the 24 V chain, `V24_MOT`, the
  three phases, the three leg returns, both buck SW nodes.  Tight, current-
  sized and proved against the via budget.
* **The USB pair and the sync chain** -- hand-drawn to a geometry spec, 90.6 Ω
  and 0.414 mm skew, and the ESD ordering.  Re-routing those would throw away
  work no router will reproduce.

Everything else -- 201 nets, 5563 mm -- comes out and goes back properly.
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
from route20_power_layers import INNER, OUTER  # noqa: E402

KEEP = set(INNER) | set(OUTER) | {
    "GND",
    "/mcu/USB_DM", "/mcu/USB_DP", "/mcu/USB_CC1", "/mcu/USB_CC2",
    "/mcu/USB_VBUS",
    "Net-(D903-K)", "Net-(R907-Pad1)",
    "Net-(Q1102-S_3)", "Net-(Q1104-S_3)", "Net-(Q1106-S_3)",
}

CHILD = '''
import json, sys
sys.path.insert(0, {here!r})
import pcbnew, route_lib as R
keep = set({keep})
b = pcbnew.LoadBoard(R.PCB)
doomed = [t for t in b.GetTracks() if t.GetNetname() not in keep]
for t in doomed:
    b.Remove(t)
print(json.dumps({{"removed": len(doomed)}}))
R.refill(b)
R.save(b)
'''


def rip():
    src = CHILD.format(here=HERE, keep=json.dumps(sorted(KEEP)))
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="actually do the rip")
    a = ap.parse_args()
    board = R.load()
    before = R.unconnected(board)
    print(f"unconnected before {before}; keeping {len(KEEP)} nets")
    if not a.yes:
        print("dry run -- pass --yes")
        return
    n = rip()
    board = R.load()
    print(f"ripped {n} items; unconnected now {R.unconnected(board)}")


if __name__ == "__main__":
    main()
