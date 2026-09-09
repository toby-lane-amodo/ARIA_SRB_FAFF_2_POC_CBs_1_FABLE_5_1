#!/usr/bin/env python3
"""Escape-first fan-out: take every fine-pitch pin out of its ring, first.

Stage A proved the board has the escape room and the routing takes it: with
copper stripped all 201 pads of the fine-pitch packages grade open, and with
the current routing 59 are starved.  Ordinary signals routed early, took the
shortest path they could see and walled in the pins they passed.

The fix is the order.  `escape_pass` already stubs a pin 0.9 mm, which clears
the *pad* and stops inside the ring -- so the stub ends in the corridor the
next net then takes, and the pin is walled in anyway.  This takes each pin
**out of the ring entirely** and parks it on the far layer, before any long
haul is drawn:

    pin -> in-line stub -> via at a staggered depth -> B.Cu

Staggering is what makes it fit.  At 0.5 mm pitch a 0.6 mm via wants 0.7524 mm
of separation and cannot sit one-per-pin in a single row.  Assigning pins to
three rows 0.6 mm apart in depth puts adjacent pins' vias at
sqrt(0.5^2 + 0.6^2) = 0.78 mm -- clear -- while same-row neighbours are 1.5 mm
apart.  That is the standard BGA/QFN fan-out and it is what the board has been
missing.

After this every long route starts from a via in open board instead of from a
pin in a ring, so no net can wall another in: the copper that would do the
walling is already there and is the escape itself.
"""
import argparse
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402

PITCH_MAX = 0.85        # only packages this fine need a fan-out field
MIN_PADS = 8
# Depths past the pad edge.  Three staggered rows is the textbook fan-out and
# it placed 124 of 291 pins; the rest sit where a neighbour's stitch via or a
# kept power run already occupies the obvious row, so the list is longer than
# three and every pin tries all of them from its own row onward.  Staggering
# is preserved -- a pin starts at its assigned row and walks outward -- but a
# pin that cannot use any row is reported rather than forced.
ROWS = (1.05, 1.65, 2.25, 2.85, 3.45, 4.05, 4.65, 5.25)
SKIP = {"GND"}


def pkg_pitch(f):
    cs = [R.pt(p.GetPosition()) for p in f.Pads() if R.pad_copper_layers(p)]
    return min((R.dist(a, b) for i, a in enumerate(cs) for b in cs[i + 1:]),
               default=99.0)


def outward(f, p):
    """Unit vector from the package centre through this pad -- its own lane."""
    c = R.pt(f.GetPosition())
    q = R.pt(p.GetPosition())
    bb = R.pad_bbox(p)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    # a pad's lane runs along its long axis, away from the body
    if w > h:
        u = (math.copysign(1.0, (q[0] - c[0]) or 1.0), 0.0)
        half = w / 2.0
    else:
        u = (0.0, math.copysign(1.0, (q[1] - c[1]) or 1.0))
        half = h / 2.0
    return q, u, half


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", help="only these packages")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    board = R.load()
    obst = R.Obstacles(board)
    want = set(a.refs.split(",")) if a.refs else None

    made, held, skipped = 0, [], 0
    for f in board.GetFootprints():
        ref = f.GetReference()
        if want and ref not in want:
            continue
        pads = [p for p in f.Pads() if R.pad_copper_layers(p)]
        if len(pads) < MIN_PADS or pkg_pitch(f) > PITCH_MAX:
            continue
        # order pins along the ring so the row assignment alternates round it
        pads.sort(key=lambda p: (R.pt(p.GetPosition())[1],
                                 R.pt(p.GetPosition())[0]))
        for idx, p in enumerate(pads):
            net = p.GetNetname()
            if not net or net in SKIP or net.startswith("unconnected-"):
                continue
            nc = p.GetNetCode()
            q, u, half = outward(f, p)
            bb = R.pad_bbox(p)
            w = max(R.W_SIGNAL, min(R.net_width(net),
                                    min(bb[2] - bb[0], bb[3] - bb[1]),
                                    pkg_pitch(f) - 2 * R.CLEAR))
            placed = False
            start = idx % 3
            order = [ROWS[(start + 3 * k) % len(ROWS)]
                     for k in range(len(ROWS) // 3 + 1)]
            order += [d for d in ROWS if d not in order]
            for d in order:
                s = (round(q[0] + u[0] * half, 3), round(q[1] + u[1] * half, 3))
                e = (round(q[0] + u[0] * (half + d), 3),
                     round(q[1] + u[1] * (half + d), 3))
                if not R.seg_ok(obst, s, e, w, nc, R.F):
                    continue
                win = obst.ij(e[0] - 1.5, e[1] - 1.5) + \
                    obst.ij(e[0] + 1.5, e[1] + 1.5)
                m = obst.via_mask(win, nc)
                ii, jj = obst.ij(*e)
                if m[ii - win[0], jj - win[1]]:
                    continue
                if not a.check:
                    R.add_track(board, s, e, w, R.F, nc)
                    R.add_via(board, e, nc)
                obst.add_seg(s, e, w / 2.0, R.F, nc)
                obst.add_via_at(e, nc)
                made += 1
                placed = True
                break
            if not placed:
                held.append(f"{ref}.{p.GetNumber()}")
        skipped += 1

    print(f"{skipped} fine-pitch packages; {made} pins fanned out to a via")
    if held:
        print(f"{len(held)} pins with no legal row: {held[:12]}"
              + (" ..." if len(held) > 12 else ""))
    if not a.check:
        R.refill(board)
        R.save(board)
        board = R.load()
        print(f"unconnected now {R.unconnected(board)}")


if __name__ == "__main__":
    main()
