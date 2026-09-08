#!/usr/bin/env python3
"""Routing step 3b -- close out the ground-via completeness proof.

Step 3 gives every SMD ground land its own via along the pad's own escape
lane, swinging the lane only where it must (R3-1) and, where the lane is a
closed pocket, tying a QFN pin straight into its IC's exposed pad (R-C3-1).
It left one land with no answer at all -- `C1021` pad 2, the PHY's +1V8 rail
decoupler, walled in by that rail's own feed on the north and by the USB3320
bias resistor's run on the west.

Step 3's search is deliberately narrow: in-line first, then a swing about the
pad, then a short maze stub *along the swing*.  This stage widens it to the
only thing that actually matters -- **any** legal via slot within reach, with
a maze-routed stub to it -- and runs it over whatever lands the proof still
reports open.  C1021's answer is 0.87 mm east-south-east of the pad centre,
which no swing about the in-line axis was ever going to find.

`DEFER` names the lands a *later* stage owns, so this stage must not put a
via where that stage's geometry needs one: `D1001` pad 2 sits between the two
USB data lines and its via is part of step 5's pair geometry.

The board file is the master -- this mutates it, create-only.
"""
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402
from route3_gnd import EP_PADS  # noqa: E402

DEFER = {("D1001", "2")}        # step 5 -- the USB pair's own geometry
REACH = 3.5                     # mm, how far a stub may look for a slot
STUB_W = (0.30, 0.25, 0.20, R.W_SIGNAL)


def lands(board):
    """SMD GND pads merged into lands, exactly as the proof counts them."""
    raw = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() != "GND" or not R.pad_copper_layers(p):
                continue
            if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            raw.append((f.GetReference(), p.GetNumber(), R.pad_bbox(p), p))
    used = [False] * len(raw)
    out = []
    for i, a in enumerate(raw):
        if used[i]:
            continue
        grp = [a]
        used[i] = True
        again = True
        while again:
            again = False
            for j, b in enumerate(raw):
                if used[j] or b[0] != a[0]:
                    continue
                for m in grp:
                    if (b[2][0] <= m[2][2] and m[2][0] <= b[2][2]
                            and b[2][1] <= m[2][3] and m[2][1] <= b[2][3]):
                        grp.append(b)
                        used[j] = True
                        again = True
                        break
        out.append(grp)
    return out


def open_lands(board):
    """Lands whose own stub copper does not reach a via.

    Built the way the proof builds it -- over track and via items only, so a
    land that merely shares the plane with another land does not count as
    covered by that land's via.
    """
    items = [it for it in R.net_items(board, "GND") if it[0] != "pad"]
    uf = R._touch_graph(items)
    comp = {}
    for i, it in enumerate(items):
        comp.setdefault(uf.find(i), []).append(it)
    out = []
    for grp in lands(board):
        boxes = [bb for _r, _n, bb, _p in grp]
        hit = False
        for its in comp.values():
            if not any(R._boxes_touch(it[3], boxes) for it in its):
                continue
            if any(it[0] == "via" for it in its):
                hit = True
                break
        if not hit:
            out.append(grp)
    return out


def ep_tied(board, grp):
    """True when this land is a client-ruled R-C3-1 tie into its own EP.

    The tie is only worth anything if the exposed pad it lands on carries the
    via array, so that is asserted here rather than assumed.
    """
    ref = grp[0][0]
    ep = None
    for f in board.GetFootprints():
        if f.GetReference() != ref:
            continue
        for p in f.Pads():
            if (ref, p.GetNumber()) in EP_PADS:
                ep = p
    if ep is None:
        return False
    eb = R.pad_bbox(ep)
    boxes = [bb for _r, _n, bb, _p in grp]
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA) or t.GetNetname() != "GND":
            continue
        a, b = R.pt(t.GetStart()), R.pt(t.GetEnd())
        hw = R.tomm(t.GetWidth()) / 2.0
        seg = R._seg_obstacle_boxes(a, b, hw)
        if R._boxes_touch(seg, boxes) and R._boxes_touch(seg, [eb]):
            nv = sum(1 for v in board.GetTracks()
                     if isinstance(v, pcbnew.PCB_VIA)
                     and v.GetNetname() == "GND"
                     and eb[0] <= R.pt(v.GetPosition())[0] <= eb[2]
                     and eb[1] <= R.pt(v.GetPosition())[1] <= eb[3])
            if nv:
                print(f"   {ref}.{grp[0][1]}: R-C3-1 tie into the {ref} "
                      f"exposed pad, which carries {nv} vias")
                return True
    return False


def slot_and_stub(board, obst, maze, grp):
    """Nearest legal via slot with a maze-routed stub from the land."""
    nc = R.netcode(board, "GND")
    pads = [p for _r, _n, _bb, p in grp]
    c = R.pt(pads[0].GetPosition())
    win = obst.ij(c[0] - REACH, c[1] - REACH) + obst.ij(c[0] + REACH,
                                                        c[1] + REACH)
    vm = obst.via_mask(win, nc)
    cands = []
    for i in range(win[0], win[2] + 1):
        for j in range(win[1], win[3] + 1):
            if vm[i - win[0], j - win[1]]:
                continue
            x, y = obst.xy(i, j)
            cands.append((math.hypot(x - c[0], y - c[1]), x, y))
    cands.sort()
    srect = {R.F: [R.pad_target_rect(p) for p in pads
                   if R.F in R.pad_copper_layers(p)],
             R.B: [R.pad_target_rect(p) for p in pads
                   if R.B in R.pad_copper_layers(p)]}
    lay = R.F if srect[R.F] else R.B
    for d, x, y in cands[:40]:
        for w in STUB_W:
            res = maze.route(nc, [c], [(x, y)], w, layers=(lay,),
                             start_rects=srect,
                             goal_rects={lay: [(x - 0.12, y - 0.12,
                                                x + 0.12, y + 0.12)]},
                             margin=6)
            if res is None:
                continue
            R.emit_result(board, obst, res, w, nc)
            R.add_via(board, (x, y), nc)
            obst.add_via_at((x, y), nc)
            return (x, y), w, R.route_len(res), d
    return None, None, None, None


def main():
    board = R.load()
    obst = R.Obstacles(board)
    maze = R.Maze(obst)

    todo = open_lands(board)
    print(f"== {len(todo)} ground lands still without a via of their own")
    made, left = [], []
    for grp in todo:
        key = (grp[0][0], grp[0][1])
        if key in DEFER:
            print(f"   {key[0]}.{key[1]}: deferred to step 5 (USB pair "
                  f"geometry owns this via)")
            continue
        if ep_tied(board, grp):
            continue
        q, w, ln, d = slot_and_stub(board, obst, maze, grp)
        if q is None:
            left.append(key)
            print(f"   {key[0]}.{key[1]}: NO SLOT within {REACH} mm "
                  f"-- needs the engineer")
            continue
        made.append((key, q, w, ln, d))
        print(f"   {key[0]}.{key[1]}: via at {q[0]:.3f},{q[1]:.3f} "
              f"({d:.2f} mm out), stub {ln:.2f} mm @ {w:.2f}")

    if made:
        R.refill(board)
        R.save(board)
    print(f"\n{len(made)} vias added, {len(left)} still open")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
