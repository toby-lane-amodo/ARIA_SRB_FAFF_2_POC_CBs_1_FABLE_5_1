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

**The stub has to be allowed to jog, and that is the whole difference between
124 pins placed and nearly all of them.**  The first cut drew it as a straight
in-line segment, which cannot work and the arithmetic says why: a via barrel is
0.6 mm across and the clearance floor is 0.1524 mm, so a min-width stub passing
*beside* one needs 0.3 + 0.1524 + 0.0762 = 0.5286 mm of lateral room against a
0.5 mm pitch -- 29 microns short, everywhere, for every pin whose row is deeper
than its neighbour's.  Two same-row vias are 1.5 mm apart, which leaves a
0.9 mm channel, and the two stubs that must thread it need
0.1524 x 5 = 0.762 mm between the barrels.  There is room; it is just not on
the straight line.  So each stub is a maze route on F.Cu from the pad to its
own slot, in a 1.2 mm window -- the jog it needs is about 30 microns, and the
router finds it.
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
# The slot does not have to be on the pin's own lane, and insisting that it is
# was the real reason 183 of 291 pins found "no legal row": the check that
# rejects them is `via_mask`, before the stub is even considered, and it fails
# identically whether the stub is drawn straight or maze-routed.  The field is
# not short of room -- a 12 mm package edge has some seven rows of legal
# 0.78 mm-spaced slots in the 1.05-5.25 mm band -- it is that the pin's own
# lane is often occupied by a GND stitch via, which the house rule puts beside
# every ground pad and which therefore lives in the ring by construction.  So
# each depth is tried at a lateral offset too, nearest first, and the stub
# reaches the offset slot by maze route.
LATERAL = (0.0, 0.25, -0.25, 0.5, -0.5, 0.75, -0.75, 1.0, -1.0,
           1.25, -1.25)
SKIP = {"GND"}

# One pin in three is a CORRIDOR: it gets no via, and its lane is drawn out
# past the deepest via row before any via is placed, so nothing can be put
# across it.
#
# Without this the field is assigned greedily, pin by pin, and simply fills
# up: 190 of 291 pins found a slot and the other 101 were left inside a ring
# with no way through it.  A pin between two same-row barrels 1.00 mm apart
# has a 0.40 mm channel and needs 0.4572 mm, and no amount of jogging fixes
# 57 microns -- the board cannot host a via for every pin of a 0.5 mm-pitch
# package, so a third of them have to leave on the outer layer instead, and
# they need a lane that was reserved rather than one that happened to survive.
#
# The two neighbours either side of a corridor are nudged 0.03 mm away from
# it, which is what makes the lane legal: a barrel one pitch away leaves
# 0.5000 mm where a min-width trace needs 0.5286, and 0.53 mm clears it.
BAND_IN = 1.6           # mm off the pad edge where open board starts
BAND_OUT = 4.5          # mm -- past every fan-out row
BAND_HALF = 3.0         # mm of lateral room the band spans
#
# Measured, and it loses.  Four fields were built on the same ripped board and
# filled to a plateau; only the last column is a verdict, the others are
# proxies that disagree with it:
#
#   field                          pins served   walled after   FILLED TO
#   no corridors, lateral slots     190 (vias)        47           94
#   straight-ladder corridors       193 (68+125)      30            -
#   strict 5.8 mm corridors         167 (37+130)       -            -
#   maze corridors to the band      182 (88+94)       40          101
#
# A corridor is worth more per pin than a via and the ring likes it better --
# walled pins fall - but it costs more room than it saves, and the fill ends
# seven items worse.  So corridors are OFF by default.  Set `--corridors 3` to
# reproduce the measurement; the code stays because the reasoning is sound and
# a board with more room round its fine-pitch packages would take it.
CORRIDOR_EVERY = 0
# A corridor is not a straight line, and insisting it was cost more than it
# bought.  It has to clear the deepest via row -- ROWS[-1] is 5.25 mm and a
# barrel needs 0.45 mm beyond that -- or the via phase drops one past the end
# of it and seals the lane again; but a straight 5.8 mm stub fits for only 37
# pins of 291, and the room it takes comes out of the via field.  A ladder of
# shorter straight lengths fits 68 and none of them is a real corridor.
#
# So the corridor is maze-routed to the same band of open board
# `route28_escape_ring` aims at, free to jog round whatever is in the way, and
# a pin whose lane will not reach falls through and takes a via like the rest.
CORRIDOR_PUSH = 0.03


def band(q, u, half):
    """The rectangle of open board a pin should reach, on its own side."""
    a = (q[0] + u[0] * (half + BAND_IN), q[1] + u[1] * (half + BAND_IN))
    b = (q[0] + u[0] * (half + BAND_OUT), q[1] + u[1] * (half + BAND_OUT))
    v = (-u[1], u[0])
    xs = [a[0] + v[0] * s * BAND_HALF for s in (-1, 1)] + \
         [b[0] + v[0] * s * BAND_HALF for s in (-1, 1)]
    ys = [a[1] + v[1] * s * BAND_HALF for s in (-1, 1)] + \
         [b[1] + v[1] * s * BAND_HALF for s in (-1, 1)]
    return (min(xs), min(ys), max(xs), max(ys)), b


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
    ap.add_argument("--straight", action="store_true",
                    help="the round-2 straight in-line stub (placed 124/291)")
    ap.add_argument("--via", type=float, default=None,
                    help="evaluate a different via PAD diameter for the new "
                         "vias only, in mm (G2 is 0.60; needs the captain's "
                         "ruling before it is used for real)")
    ap.add_argument("--board", help="read this board instead of the project's")
    ap.add_argument("--corridors", type=int, default=CORRIDOR_EVERY,
                    help="reserve every Nth pin as an outer-layer lane "
                         "(0 disables)")
    a = ap.parse_args()

    if a.board:
        R.PCB = a.board
    board = R.load()
    obst = R.Obstacles(board)
    # After the model is built, so the vias already on the board keep their
    # real 0.60 mm pads as obstacles and only the *candidate* shrinks.  That
    # is the honest form of the question: what would a smaller via buy us on
    # the board as it stands, not what would it buy if the whole board had
    # been drawn with one.
    if a.via:
        R.VIA_D = a.via
        print(f"evaluating a {a.via:.2f} mm via pad for new vias "
              f"(G2 is 0.60 -- this is a measurement, not a change)")
    maze = R.Maze(obst)
    want = set(a.refs.split(",")) if a.refs else None

    made, held, skipped, lanes = 0, [], 0, 0
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
        # Phase 1 -- the corridors, before any via exists to sit across one.
        corridor = set()
        for idx, p in enumerate(pads):
            net = p.GetNetname()
            if not net or net in SKIP or net.startswith("unconnected-"):
                continue
            if a.corridors <= 0 or idx % a.corridors != 1:
                continue
            nc = p.GetNetCode()
            q, u, half = outward(f, p)
            w = R.W_SIGNAL
            rect, goal = band(q, u, half)
            res = maze.route(nc, [q], [goal], w, layers=(R.F,), margin=3.0,
                             hw=1.8, max_nodes=200_000,
                             start_rects={R.F: [R.pad_target_rect(p)]},
                             goal_rects={R.F: [rect]})
            if res is None:
                continue
            if a.check:
                for lay, pts in res[0]:
                    for x, y in zip(pts, pts[1:]):
                        obst.add_seg(x, y, w / 2.0, lay, nc)
            else:
                R.emit_result(board, obst, res, w, nc)
            corridor.add(idx)
            lanes += 1

        # Phase 2 -- a via for everyone else, on a slot that now has to
        # respect the corridors.
        for idx, p in enumerate(pads):
            net = p.GetNetname()
            if not net or net in SKIP or net.startswith("unconnected-"):
                continue
            if idx in corridor:
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
            v = (-u[1], u[0])
            push = 0.0
            if (idx - 1) in corridor:
                push = CORRIDOR_PUSH
            elif (idx + 1) in corridor:
                push = -CORRIDOR_PUSH
            slots = [(d, lat + push) for d in order for lat in LATERAL]
            for d, lat in slots:
                s = (round(q[0] + u[0] * half, 3), round(q[1] + u[1] * half, 3))
                e = (round(q[0] + u[0] * (half + d) + v[0] * lat, 3),
                     round(q[1] + u[1] * (half + d) + v[1] * lat, 3))
                win = obst.ij(e[0] - 1.5, e[1] - 1.5) + \
                    obst.ij(e[0] + 1.5, e[1] + 1.5)
                m = obst.via_mask(win, nc)
                ii, jj = obst.ij(*e)
                if m[ii - win[0], jj - win[1]]:
                    continue
                # Straight first, always.  A jogged stub is wider than its
                # own lane for part of its length and a greedy one steals the
                # neighbour's -- routing every pin by maze placed *fewer*
                # pins than the straight version did (108 against 124).  The
                # jog is the fallback, not the rule.
                res = None
                if R.seg_ok(obst, s, e, w, nc, R.F):
                    res = ([(R.F, [s, e])], [])
                elif not a.straight:
                    goal = (e[0] - 0.03, e[1] - 0.03, e[0] + 0.03, e[1] + 0.03)
                    res = maze.route(nc, [q], [e], w, layers=(R.F,),
                                     margin=1.2, hw=1.6, bend_cost=3.0,
                                     max_nodes=80_000,
                                     start_rects={R.F: [R.pad_target_rect(p)]},
                                     goal_rects={R.F: [goal]})
                if res is None:
                    continue
                if not a.check:
                    R.emit_result(board, obst, res, w, nc)
                    R.add_via(board, e, nc)
                    obst.add_via_at(e, nc)
                else:
                    for lay, pts in res[0]:
                        for x, y in zip(pts, pts[1:]):
                            obst.add_seg(x, y, w / 2.0, lay, nc)
                    obst.add_via_at(e, nc)
                made += 1
                placed = True
                break
            if not placed:
                held.append(f"{ref}.{p.GetNumber()}")
        skipped += 1

    print(f"{skipped} fine-pitch packages; {lanes} corridors reserved, "
          f"{made} pins fanned out to a via")
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
