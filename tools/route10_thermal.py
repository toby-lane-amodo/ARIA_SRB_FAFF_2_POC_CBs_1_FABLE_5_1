#!/usr/bin/env python3
"""Routing step 10 -- thermal copper at the power FETs, by widening.

House G1a/G3 says power is deliberate traces on the outer layers, **no pours**,
so every current path stays explicit.  The FETs still have to get rid of their
heat, and on this stackup they have no plane to do it into: both internal
layers are GND and a FET drain is not, so a drain's only path is outer-layer
copper.  The answer that satisfies both is G1c -- widen locally, on the copper
that is already the current path.

What gets widened, and why that copper and not other copper:

* the **phase link**, high-side source to low-side drain.  It is the leg's own
  commutation loop and it is millimetres long; every extra tenth is width the
  di/dt sees as less inductance as well as heat spreading.
* the **24 V bus into each high-side drain**, and the **low-side source down to
  its shunt** -- the two ends of the same loop.
* the **phase output** where it leaves the node.

Nothing else: a rail's long haul is sized by `route4c_widen.py` from the
current it carries, and widening it further here would just be copper.

The mechanism is `route4c`'s: `SetWidth` in place, never a reroute.  The
centreline already clears everything, so the only question is whether the extra
half-width still does, and `seg_ok` answers it against foreign copper only.
Each segment grows to the widest rung the channel actually has, capped at the
pad it lands on -- a trace wider than its own land buys nothing.

`--check` reports without touching the board.
"""
import argparse
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402

# The six power FETs and the shunts, by leg.  A segment counts as FET-local
# when both its ends sit within REACH of one of these parts' power pads.
LEGS = [("Q1101", "Q1102", "R1125", "/motor_drive/MOTOR_U", "Net-(Q1102-S_3)"),
        ("Q1103", "Q1104", "R1126", "/motor_drive/MOTOR_V", "Net-(Q1104-S_3)"),
        ("Q1105", "Q1106", "R1127", "/motor_drive/MOTOR_W", "Net-(Q1106-S_3)")]
BUS = "/motor_drive/V24_MOT"
REACH = 3.0            # mm from a FET power pad's box
LADDER = [1.00, 1.20, 1.40, 1.60, 1.80, 2.00, 2.29]
CAP = 2.29             # the big drain land is 2.29 mm; wider buys nothing


def power_pads(board):
    """The FET drain/source lands and the shunt pads, with their bboxes."""
    want = set()
    for qh, ql, sh, _ph, _sn in LEGS:
        want |= {(qh, "1_2_3"), (qh, "5_6_7_8"), (ql, "1_2_3"),
                 (ql, "5_6_7_8"), (sh, "1"), (sh, "2")}
    out = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if (f.GetReference(), p.GetNumber()) in want:
                out.append(R.pad_bbox(p))
    return out


def near(boxes, q):
    for b in boxes:
        if (b[0] - REACH <= q[0] <= b[2] + REACH
                and b[1] - REACH <= q[1] <= b[3] + REACH):
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    board = R.load()
    obst = R.Obstacles(board)
    boxes = power_pads(board)
    nets = {BUS} | {ph for _a, _b, _c, ph, _s in LEGS} \
                 | {sn for _a, _b, _c, _p, sn in LEGS}

    print(f"{'net':<26} {'from':>18} {'to':>18} {'was':>5} {'now':>5}")
    grown, held, total = 0, 0, 0.0
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            continue
        net = t.GetNetname()
        if net not in nets:
            continue
        s, e = R.pt(t.GetStart()), R.pt(t.GetEnd())
        if not (near(boxes, s) and near(boxes, e)):
            continue
        w = R.tomm(t.GetWidth())
        nc = t.GetNetCode()
        got = w
        for cand in LADDER:
            if cand <= got + 1e-6 or cand > CAP + 1e-6:
                continue
            if R.seg_ok(obst, s, e, cand, nc, t.GetLayer()):
                got = cand
        if got > w + 1e-6:
            if not a.check:
                t.SetWidth(R.mm(got))
                obst.add_seg(s, e, got / 2.0, t.GetLayer(), nc)
            grown += 1
            total += R.dist(s, e) * (got - w)
        else:
            held += 1
        print(f"{net:<26} {str(s):>18} {str(e):>18} "
              f"{w:5.2f} {got:5.2f}" + ("" if got > w + 1e-6 else "   (held)"))

    print(f"\n{grown} segments widened, {held} already at the channel's limit; "
          f"{total:.1f} mm^2 of extra copper on the FET lands")
    if not a.check:
        R.refill(board)
        R.save(board)
        print("saved")


if __name__ == "__main__":
    main()
