#!/usr/bin/env python3
"""Round 2, step 4b -- the rails as zones on In2.Cu / In3.Cu.

Maze-routing a 3.15 mm trunk across a board is slow and it is also the wrong
shape.  `+3V3` needs 3.15 mm of 0.5 oz foil to carry its 1.5 A, and a trace
that wide threading between sixty pads is a worse conductor than the obvious
thing: a **pour**, on a layer that exists for nothing else.

**This is not the G3 waiver it looks like.**  G3 says power on the outer
layers is deliberate traces and never pours, *so that every current path is
explicit where signals share the copper*.  In2.Cu and In3.Cu share their
copper with nothing -- they were added by the captain for power alone -- and
on a dedicated power layer a pour is the standard construction and the lowest
impedance available.  The outer layers keep G3 exactly as before: what stayed
outside (the 24 V chain, the motor bus, the phases, the SW nodes) is still
drawn as explicit traces at sized widths.

Each rail gets a zone over the region its own consumers occupy, on the layer
that keeps it clear of the others.  Clearance and priority do the separation
KiCad is built to do; the two ground planes on In1/In4 are untouched.

Connectivity to a pad is unchanged from round 1's house pattern: the pad's
own feed via drops into the zone, and the zone is the distribution.
"""
import argparse
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402
from place_lib import save  # noqa: E402
from route20_power_layers import INNER, inner_width  # noqa: E402

# Only +3V3 pours, and only on In2.Cu.
#
# The first cut gave every rail a zone and that was wrong: a zone drawn round
# the bounding box of scattered pads covers everything between them, so +5VA
# came out 152 x 77 mm and +3V3A 121 x 27 mm, all overlapping on one layer and
# carving each other to pieces by priority.  A bounding box is not a consumer
# cluster.
#
# The other twelve rails do not need it.  They carry 0.1 to 0.6 A, they route
# as traces at 0.50-0.90 mm, and eight of them were already whole before this
# stage existed.  +3V3 is the one that needed 3.15 mm of 0.5 oz foil across
# the whole board, and it is the one that gets the pour -- on In2.Cu, which
# after this carries nothing else of consequence.
LAYER = {
    "+3V3": pcbnew.In2_Cu,
}
PAD_MARGIN = 3.0        # mm of pour around the outermost consumer pad
PRIORITY = {"+3V3": 0}  # everything else outranks the big one where they meet


def pads_of(board, net):
    out = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() == net and R.pad_copper_layers(p):
                out.append(R.pad_bbox(p))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nets")
    a = ap.parse_args()
    board = R.load()
    want = [n for n in LAYER if not a.nets or n in a.nets.split(",")]

    made = 0
    for net in want:
        boxes = pads_of(board, net)
        if len(boxes) < 2:
            continue
        x0 = min(b[0] for b in boxes) - PAD_MARGIN
        y0 = min(b[1] for b in boxes) - PAD_MARGIN
        x1 = max(b[2] for b in boxes) + PAD_MARGIN
        y1 = max(b[3] for b in boxes) + PAD_MARGIN
        # clip to the board, keeping the house edge clearance
        x0, y0 = max(x0, R.BX + R.EDGE_CLEAR), max(y0, R.BY + R.EDGE_CLEAR)
        x1 = min(x1, R.BX + R.BW - R.EDGE_CLEAR)
        y1 = min(y1, R.BY + R.BH - R.EDGE_CLEAR)

        z = pcbnew.ZONE(board)
        z.SetLayer(LAYER[net])
        z.SetNetCode(R.netcode(board, net))
        z.SetAssignedPriority(PRIORITY.get(net, 1))
        z.SetLocalClearance(R.mm(R.CLEAR))
        z.SetMinThickness(R.mm(0.15))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.SetIsFilled(False)
        o = z.Outline()
        o.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            o.Append(R.mm(x), R.mm(y))
        board.Add(z)
        made += 1
        print(f"   {net:<30} {board.GetLayerName(LAYER[net]):<14} "
              f"{x1 - x0:6.1f} x {y1 - y0:5.1f} mm  "
              f"(needs {inner_width(INNER[net]):.2f} mm of trace instead)",
              flush=True)

    R.refill(board)
    save(board)
    board = R.load()
    print(f"\n{made} rail zones added; unconnected now {R.unconnected(board)}")


if __name__ == "__main__":
    main()
