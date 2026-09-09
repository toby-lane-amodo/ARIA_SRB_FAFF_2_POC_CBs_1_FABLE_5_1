#!/usr/bin/env python3
"""Which of the still-open nets are *sealed*, and which are merely unrouted.

The distinction decides what to do next, and it is not visible in a router's
"UNROUTED" line.  A pad with no legal way out of its own pin ring cannot be
reached at any width on either layer, however wide the search window; the only
fix is to rip whatever is standing in its lane, route it first, and put the
sealer back (R3-1, and `tools/route_ripup.py` holds the plans).  A pad that can
get out but whose net still would not close is a different problem entirely --
that one wants a wider window or a different corridor.

So for every net that is still in more than one island, this walks each island
that holds pads and asks a concrete question of each pad: can a trace of the
net's own class width leave this pad, in any of eight directions, for a lane
length?  A pad that answers no to all eight is sealed, and the report names the
copper sitting in its best direction so the rip has something to aim at.

Reports only.  Nothing here touches the board.
"""
import argparse
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402

LANE = 0.90            # mm of straight lane a pad wants to count as free
TIGHT = 0.30           # below this it is sealed; between the two it is tight
# A straight-lane test is a proxy, not the truth: a real router turns.  So the
# verdict is graded.  Under TIGHT the pad has nowhere to go at all and only a
# rip will help.  Between TIGHT and LANE it has a stub's worth of room and a
# router can usually work with it -- worth listing, not worth ripping for.
DIRS = [(math.cos(math.radians(a)), math.sin(math.radians(a)))
        for a in range(0, 360, 45)]


def pin_width(net, pad):
    """The width to test the escape at: the class width, capped by the pad.

    A net's class width is what it wants in open board, not what it can start
    at.  VM_DRV is Motor class, 1.00 mm; SYNC_TRIG is RF50, 0.37 mm; both land
    on 0.30 mm pads at 0.5 mm pitch, where neither will fit by construction.
    Testing at the class width calls those pins sealed when what is actually
    true is that the link necks down at the pad, which is the house rule for
    every fine-pitch pin: the widest trace that does not exceed the pad.
    """
    bb = R.pad_bbox(pad)
    return min(R.net_width(net), max(R.W_SIGNAL,
                                     min(bb[2] - bb[0], bb[3] - bb[1])))


def half_at(bb, u):
    """Half-extent of an axis-aligned pad box along direction u.

    Using max(w, h) for every direction -- which is what this did at first --
    overshoots badly on the tall thin pads of a fine-pitch package: U302's
    pin 8 is 0.30 wide and 0.80 tall, so a 0.40 mm offset eastward starts the
    test *inside* pin 7 and every direction reports sealed.  Three of the
    twelve pads in the first scan were that, not a real seal.
    """
    return abs(u[0]) * (bb[2] - bb[0]) / 2.0 + abs(u[1]) * (bb[3] - bb[1]) / 2.0


def escapes(board, obst, pad, width):
    """Which of the eight directions a `width` trace can leave this pad by."""
    q = R.pt(pad.GetPosition())
    bb = R.pad_bbox(pad)
    nc = pad.GetNetCode()
    out = []
    for u in DIRS:
        half = half_at(bb, u)
        a = (round(q[0] + u[0] * half, 3), round(q[1] + u[1] * half, 3))
        b = (round(q[0] + u[0] * (half + LANE), 3),
             round(q[1] + u[1] * (half + LANE), 3))
        for layer in (R.F, R.B):
            if layer not in R.pad_copper_layers(pad):
                continue
            if R.seg_ok(obst, a, b, width, nc, layer):
                out.append((u, board.GetLayerName(layer)))
                break
    return out


def reach(board, obst, pad, width, u):
    """How far a `width` trace can get out of this pad in direction u, mm."""
    q = R.pt(pad.GetPosition())
    bb = R.pad_bbox(pad)
    half = half_at(bb, u)
    nc = pad.GetNetCode()
    layers = [l for l in (R.F, R.B) if l in R.pad_copper_layers(pad)]
    best = 0.0
    for layer in layers:
        lo, hi = 0.0, LANE
        a = (round(q[0] + u[0] * half, 3), round(q[1] + u[1] * half, 3))
        for _ in range(7):
            mid = (lo + hi) / 2.0
            b = (round(a[0] + u[0] * mid, 3), round(a[1] + u[1] * mid, 3))
            if R.seg_ok(obst, a, b, width, nc, layer):
                lo = mid
            else:
                hi = mid
        best = max(best, lo)
    return best


def blocker(board, pad, u, d):
    """Nearest foreign-net copper to where the lane in direction u ran out."""
    q = R.pt(pad.GetPosition())
    bb = R.pad_bbox(pad)
    half = half_at(bb, u)
    at = (q[0] + u[0] * (half + d), q[1] + u[1] * (half + d))
    nc = pad.GetNetCode()
    best = None
    for t in board.GetTracks():
        if t.GetNetCode() == nc:
            continue
        if isinstance(t, pcbnew.PCB_VIA):
            dd = R.dist(at, R.pt(t.GetPosition()))
            what = "via"
        else:
            a, b = R.pt(t.GetStart()), R.pt(t.GetEnd())
            vx, vy = b[0] - a[0], b[1] - a[1]
            L = vx * vx + vy * vy
            tt = 0.0 if L == 0 else max(0.0, min(1.0, ((at[0] - a[0]) * vx
                                                       + (at[1] - a[1]) * vy) / L))
            dd = math.hypot(at[0] - (a[0] + tt * vx), at[1] - (a[1] + tt * vy))
            what = "track"
        if best is None or dd < best[0]:
            best = (dd, t.GetNetname() or "GND", what)
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetCode() == nc:
                continue
            bx = R.pad_bbox(p)
            dd = math.hypot(max(bx[0] - at[0], 0, at[0] - bx[2]),
                            max(bx[1] - at[1], 0, at[1] - bx[3]))
            if best is None or dd < best[0]:
                best = (dd, f"{f.GetReference()}.{p.GetNumber()}", "pad")
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", help="only this net")
    a = ap.parse_args()

    board = R.load()
    obst = R.Obstacles(board)

    seen, split = set(), []
    for f in board.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if not n or n in seen or n == "GND" or n.startswith("unconnected-"):
                continue
            seen.add(n)
            if a.net and n != a.net:
                continue
            if len(R.pad_nodes(board, n)) < 2:
                continue
            if not R.net_is_whole(board, n):
                split.append(n)

    pads = {}
    for f in board.GetFootprints():
        for p in f.Pads():
            pads[f"{f.GetReference()}.{p.GetNumber()}"] = p

    sealed, tight, open_ = [], [], []
    for net in sorted(split):
        isl = R.net_islands(board, net)
        for g in isl:
            for key in sorted({x[1] for x in g if x[0] == "pad"}):
                p = pads.get(key)
                if p is None or not R.pad_copper_layers(p):
                    continue
                w = pin_width(net, p)
                e = escapes(board, obst, p, w)
                if e:
                    open_.append((net, key, e))
                    continue
                best = max(reach(board, obst, p, w, u) for u in DIRS)
                (sealed if best < TIGHT else tight).append((net, key, e))

    print(f"{len(split)} nets still split, "
          f"{len(sealed) + len(tight) + len(open_)} pads in them")
    print(f"\n== SEALED -- under {TIGHT} mm in every direction, so only a rip "
          f"will help ({len(sealed)} pads)")
    for net, key, _e in sealed:
        p = pads[key]
        w = pin_width(net, p)
        by = sorted(((reach(board, obst, p, w, u), u) for u in DIRS),
                    reverse=True)
        d, u = by[0]
        deg = int(round(math.degrees(math.atan2(u[1], u[0]))))
        b = blocker(board, p, u, d)
        note = (f"{b[2]} {b[1]} at {b[0]:.2f} mm" if b else "?")
        print(f"   {net:<34} {key:<12} best {d:.2f} mm at {deg:>4} deg, "
              f"stopped by {note}")
    print(f"\n== TIGHT -- between {TIGHT} and {LANE} mm: a stub's worth of "
          f"room, which a router can usually turn in ({len(tight)} pads)")
    for net, key, _e in tight:
        p = pads[key]
        w = pin_width(net, p)
        by = sorted(((reach(board, obst, p, w, u), u) for u in DIRS),
                    reverse=True)
        d, u = by[0]
        deg = int(round(math.degrees(math.atan2(u[1], u[0]))))
        b = blocker(board, p, u, d)
        note = (f"{b[2]} {b[1]} at {b[0]:.2f} mm" if b else "?")
        print(f"   {net:<34} {key:<12} best {d:.2f} mm at {deg:>4} deg, "
              f"stopped by {note}")

    print(f"\n== escapable, so the net is a routing problem not a lane one "
          f"({len(open_)} pads)")
    for net, key, e in open_[:60]:
        dirs = ",".join(f"{d}" for d, _l in
                        [(f"{int(round(math.degrees(math.atan2(u[1], u[0]))))}",
                          l) for u, l in e])
        print(f"   {net:<36} {key:<14} out at {dirs} deg")
    if len(open_) > 60:
        print(f"   ... and {len(open_) - 60} more")
    return 1 if sealed else 0


if __name__ == "__main__":
    sys.exit(main())
