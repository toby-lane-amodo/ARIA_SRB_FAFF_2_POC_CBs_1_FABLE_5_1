#!/usr/bin/env python3
"""Stage A -- grade every package's escape room, and score a candidate move.

The captain authorised placement changes to end the escape starvation routing
round 2 proved.  This is the instrument for choosing them: guessing which way
to nudge a QFN is how you spend an afternoon and move it the wrong way.

For each pad of a package it measures the **reachable free area** in the pad's
escape direction -- not the 0.9 mm straight lane `route_sealed` tests, which
answers "can it leave the pad" and says nothing about whether the corridor goes
anywhere.  `U501.12` passed that test with a slot 0.3 mm tall that dead-ends
after 1.5 mm.  What matters is the second millimetre, so this floods outward
from the pad through free cells and reports how much board it can actually see.

    starved   < 2 mm^2 reachable -- the corridor is a pocket
    tight     2 to 6 mm^2
    open      > 6 mm^2

`--move REF:dx,dy` re-measures with a footprint shifted, without saving, so a
candidate can be scored before anything is committed.

`--bare` is the mode that matters for a *placement* decision: it strips every
track and via first and measures the escape room the placement itself
provides.  Measured against the routed board you cannot tell starvation from
congestion, and you would move parts to fix something a reroute would have
fixed.  Placement is answerable for the room; routing is answerable for what
it does with it.
"""
import argparse
import collections
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402

STARVED, TIGHT = 2.0, 6.0       # mm^2 of reachable free area
FLOOD = 6.0                     # mm, how far out the flood looks
CELL = R.GRID * R.GRID          # mm^2 per grid cell


def reachable_area(obst, pad, width, layer=R.F):
    """Free area a trace of `width` can flood into from this pad, in mm^2."""
    q = R.pt(pad.GetPosition())
    nc = pad.GetNetCode()
    r = width / 2.0 + R.CLEAR
    win = obst.ij(q[0] - FLOOD, q[1] - FLOOD) + \
        obst.ij(q[0] + FLOOD, q[1] + FLOOD)
    m = obst.track_mask(win, nc, layer, r)
    i0, j0, i1, j1 = win
    W, H = i1 - i0 + 1, j1 - j0 + 1
    si, sj = obst.ij(*q)
    si, sj = si - i0, sj - j0
    if not (0 <= si < W and 0 <= sj < H) or m[si, sj]:
        return 0.0
    seen = {(si, sj)}
    stack = [(si, sj)]
    while stack:
        i, j = stack.pop()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = i + di, j + dj
            if 0 <= a < W and 0 <= b < H and (a, b) not in seen \
                    and not m[a, b]:
                seen.add((a, b))
                stack.append((a, b))
    return len(seen) * CELL


def pin_pitch(f):
    """Smallest centre-to-centre distance between two pads of a footprint."""
    cs = [R.pt(p.GetPosition()) for p in f.Pads() if R.pad_copper_layers(p)]
    return min((R.dist(a, b) for i, a in enumerate(cs) for b in cs[i + 1:]),
               default=99.0)


def escape_width(f, p, net):
    """The widest trace that can actually leave this pin.

    Three things bound it and the pitch is the one that is easy to forget: a
    0.45 mm trace cannot leave a 0.65 mm-pitch pin whatever the pad measures,
    because the neighbour is 0.65 away and both need their clearance.  Grading
    U701 without this called two pads starved that are nothing of the sort --
    they are Power-class nets, 0.50 mm, landing on a TSSOP, and the answer is
    that the link necks down at the pin exactly as the house rules say.
    """
    bb = R.pad_bbox(p)
    return max(R.W_SIGNAL, min(R.net_width(net),
                               min(bb[2] - bb[0], bb[3] - bb[1]),
                               pin_pitch(f) - 2 * R.CLEAR))


def grade(board, obst, refs, only_open_nets=None):
    rows = []
    for f in board.GetFootprints():
        if f.GetReference() not in refs:
            continue
        for p in f.Pads():
            n = p.GetNetname()
            if not n or n == "GND" or n.startswith("unconnected-"):
                continue
            if only_open_nets is not None and n not in only_open_nets:
                continue
            if not R.pad_copper_layers(p):
                continue
            w = escape_width(f, p, n)
            a = reachable_area(obst, p, w)
            rows.append((a, f"{f.GetReference()}.{p.GetNumber()}", n))
    rows.sort()
    return rows


STRIP = """
import sys
sys.path.insert(0, {here!r})
import pcbnew, route_lib as R
b = pcbnew.LoadBoard(R.PCB)
for t in list(b.GetTracks()):
    b.Remove(t)
for z in list(b.Zones()):
    b.Remove(z)
b.Save({dst!r})
"""


def strip_copy():
    """A copy of the board with every track, via and zone removed."""
    import subprocess
    dst = R.PCB + ".bare.kicad_pcb"
    src = STRIP.format(here=os.path.dirname(os.path.abspath(__file__)),
                       dst=dst)
    out = subprocess.run([sys.executable, "-c", src], capture_output=True,
                         text=True)
    if out.returncode != 0 or not os.path.exists(dst):
        print(out.stderr, file=sys.stderr)
        raise SystemExit("strip failed")
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", default="U1001,U1101,U1002,U501,U701,U601")
    ap.add_argument("--move", action="append", default=[],
                    help="REF:dx,dy in mm -- scored, never saved")
    ap.add_argument("--open-only", action="store_true",
                    help="only pads on nets that are still split")
    ap.add_argument("--bare", action="store_true",
                    help="ignore all routing -- grade the placement itself")
    ap.add_argument("--list", type=int, default=0)
    a = ap.parse_args()

    src = R.PCB
    if a.bare:
        # The strip has to happen in a child that writes a scratch board:
        # board.Remove() mid-script poisons SWIG type resolution for every
        # later wrapped return, and doing it here segfaulted on the first try.
        # AGENTS.md records that trap; this is what walking into it looks like.
        src = strip_copy()
    board = pcbnew.LoadBoard(src)
    for f in board.GetFootprints():
        f.BuildCourtyardCaches()
    for spec in a.move:
        ref, _, d = spec.partition(":")
        dx, dy = (float(v) for v in d.split(","))
        for f in board.GetFootprints():
            if f.GetReference() == ref:
                p = f.GetPosition()
                f.SetPosition(pcbnew.VECTOR2I(p.x + R.mm(dx),
                                              p.y + R.mm(dy)))
                print(f"   (scored with {ref} moved {dx:+.2f},{dy:+.2f})")
    open_nets = None
    if a.open_only:
        from route6_signals import open_nets as _o
        open_nets = set(_o(board))

    obst = R.Obstacles(board)
    refs = set(a.refs.split(","))
    rows = grade(board, obst, refs, open_nets)
    by = collections.Counter()
    per = collections.defaultdict(lambda: [0, 0, 0])
    for area, name, net in rows:
        k = "starved" if area < STARVED else \
            ("tight" if area < TIGHT else "open")
        by[k] += 1
        i = {"starved": 0, "tight": 1, "open": 2}[k]
        per[name.split(".")[0]][i] += 1
    print(f"{len(rows)} pads graded: "
          + ", ".join(f"{by[k]} {k}" for k in ("starved", "tight", "open")))
    print(f"   {'package':<8} {'starved':>8} {'tight':>6} {'open':>6}")
    for ref in sorted(per):
        s, t, o = per[ref]
        print(f"   {ref:<8} {s:8} {t:6} {o:6}")
    if a.list:
        print("\n   tightest pads:")
        for area, name, net in rows[:a.list]:
            print(f"      {name:<12} {area:6.2f} mm^2  {net}")


if __name__ == "__main__":
    main()
