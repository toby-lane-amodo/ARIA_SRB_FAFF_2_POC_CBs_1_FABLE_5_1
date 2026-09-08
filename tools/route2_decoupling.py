#!/usr/bin/env python3
"""Routing step 2 -- positive feeds to every decoupling capacitor.

House flow (pcb-layout-style, VanClock R1-3/R1-4): **feed via -> capacitor pad
-> IC pin**, never pin-first, never a stub.  The via->cap-pad trace is at the
via outer diameter; the cap-pad->pin link runs at the IC pin-pad width.  The
GND sides wait for step 3.

Two documented departures, both the skill's own carve-outs:

* **Source-chain capacitors keep their feed on the outer layer.**  The skill
  exempts a PTH-fed reservoir ("its positive feed routes in-line on the outer
  layer from the source pad ... to the cap pad at power-trace width") and puts
  the *source* chain's via at the end of the chain, not in front of it.  Every
  cap listed in SOURCE_CHAIN sits within a few mm of its own source pad on
  F.Cu -- the 24 V entry, both buck output nodes, both LDO output nodes, the
  +3V3A filter output and the whole V24_MOT bridge rail.  Feeding those
  through a via would put a 0.6 mm barrel inside the commutation loop and
  inside each switcher's output path.  They are routed in-line in step 4.
* **A two-node cap net has no feed via** -- C304, C318, C513, C1008, C1009 and
  C1115 are each alone on their net with one IC pin, so there is no
  distribution to feed them from.  They get the in-line link only.

Everything else -- every consumer decoupler on a distributed rail -- takes the
full pattern.  The feed vias this stage plants are what step 4's B.Cu rail
distribution anchors to; they legitimately read as `via_dangling` until then.
"""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402

# Consumer decouplers: every cap that sits on a distributed rail and bypasses
# an IC pin.  Target pin is resolved as the nearest same-net pin of the part
# named here -- the placement round put each cap at its own pin (place1 S4),
# so nearest-of-that-part reproduces the schematic pairing.
CONSUMER = [
    # --- mcu -----------------------------------------------------------
    ("C1002", "U1001"), ("C1003", "U1001"), ("C1004", "U1001"),
    ("C1005", "U1001"), ("C1006", "U1001"), ("C1007", "U1001"),
    ("C1010", "U1001"), ("C1011", "U1001"), ("C1012", "U1001"),
    ("C1013", "U1001"),
    ("C1001", "Y1001"), ("C1015", "Y1001"),
    ("C1016", "U1003"), ("C1017", "U1003"),
    ("C1018", "U1002"), ("C1019", "U1002"),
    ("C1020", "U1002"), ("C1021", "U1002"),
    ("C1022", "U1004"), ("C1023", "U1004"), ("C1024", "U1004"),
    # --- loadcell_afe --------------------------------------------------
    ("C509", "U501"), ("C510", "U501"), ("C511", "U501"), ("C512", "U501"),
    # --- linear_encoder ------------------------------------------------
    ("C604", "U601"), ("C601", "J601"), ("C602", "J601"),
    # --- temp_sense ----------------------------------------------------
    ("C710", "U701"), ("C711", "U701"), ("C712", "U701"), ("C713", "U701"),
    # --- nvm / ui_io ---------------------------------------------------
    ("C801", "U801"), ("C907", "U901"), ("C903", "U902"),
    # --- power_rails ---------------------------------------------------
    ("C301", "U301"), ("C302", "U301"), ("C303", "U301"),
    ("C315", "U304"), ("C316", "U304"), ("C317", "U304"),
    ("C309", "U302"), ("C312", "U303"),
    # --- motor_drive ---------------------------------------------------
    ("C1113", "U1101"), ("C1114", "U1101"),
    ("C1109", "U1101"), ("C1110", "U1101"),
    ("C1107", "J1102"), ("C1108", "J1102"),
]

# Two-node cap nets: link only, no feed via (nothing else on the net).
LINK_ONLY = [
    ("C304", "U301"), ("C318", "U304"), ("C513", "U501"),
    ("C1008", "U1001"), ("C1009", "U1001"), ("C1115", "U1101"),
]

# Source-chain capacitors -- fed in-line on the outer layer in step 4.
SOURCE_CHAIN = ["C201", "C202", "C204", "C205", "C206",
                "C306", "C307", "C308", "C320", "C321", "C322",
                "C310", "C311", "C313", "C314", "C323", "C324",
                "C1101", "C1102", "C1103", "C1104",
                "C1119", "C1120", "C1121", "C1122", "C1123", "C1124"]

# Trial directions for a feed via, in preference order: straight out from the
# pin, then swung away in 15 deg steps.  R3-1: the via sits in the pad's own
# escape lane, in line, not parked sideways in a neighbour's corridor.
SWINGS = [0, 15, -15, 30, -30, 45, -45, 60, -60, 90, -90, 120, -120, 180]


def support(w, h, ux, uy):
    """Half-extent of an axis-aligned w x h rectangle along (ux, uy)."""
    return abs(ux) * w / 2.0 + abs(uy) * h / 2.0


def via_slot(board, obst, sup_pad, away_from, nc):
    """A legal feed-via centre in the supply pad's own escape lane."""
    import math
    s = R.pt(sup_pad.GetPosition())
    # world bbox, not GetSizeX/Y: a 90 deg rotated footprint swaps its pads'
    # local x/y, and a slot sized from the local size lands the via ON the pad
    bb = R.pad_bbox(sup_pad)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    base = math.atan2(s[1] - away_from[1], s[0] - away_from[0])
    for swing in SWINGS:
        a = base + math.radians(swing)
        ux, uy = math.cos(a), math.sin(a)
        d0 = support(w, h, ux, uy) + R.VIA_D / 2.0 + 0.05
        for extra in (0.0, 0.15, 0.30, 0.50, 0.75):
            d = d0 + extra
            q = (round(s[0] + ux * d, 3), round(s[1] + uy * d, 3))
            if via_ok(obst, q, nc) and R.seg_ok(obst, q, s, R.W_VIA_OD, nc):
                return q, swing, d
    return None, None, None


def via_ok(obst, q, nc):
    win = (obst.ij(q[0] - 1.5, q[1] - 1.5) + obst.ij(q[0] + 1.5, q[1] + 1.5))
    win = (win[0], win[1], win[2], win[3])
    m = obst.via_mask(win, nc)
    i, j = obst.ij(*q)
    return not m[i - win[0], j - win[1]]


def link_width(cap_pad, pin_pad):
    """Widest clean trace: never wider than either pad it lands on."""
    a = min(R.tomm(cap_pad.GetSizeX()), R.tomm(cap_pad.GetSizeY()))
    b = min(R.tomm(pin_pad.GetSizeX()), R.tomm(pin_pad.GetSizeY()))
    return max(R.W_SIGNAL, round(min(a, b, 0.6), 4))


def main():
    board = R.load()
    if len(board.GetTracks()):
        raise SystemExit("route2: board already carries copper -- this stage "
                         "runs once, on the zones-only board")
    obst = R.Obstacles(board)
    maze = R.Maze(obst)
    fps = R.by_ref(board)

    rows = []
    fails = []

    def order(caps):
        """Nearest cap to its pin first, so a further cap on the same pin
        chains onto the link that is already there instead of being swept
        over by it."""
        out = []
        for cref, tref in caps:
            sup = [p for p in fps[cref].Pads() if p.GetNetname() != "GND"][0]
            net = sup.GetNetname()
            t = min((p for p in fps[tref].Pads() if p.GetNetname() == net),
                    key=lambda p: R.dist(R.pt(p.GetPosition()),
                                         R.pt(sup.GetPosition())))
            out.append((R.dist(R.pt(sup.GetPosition()), R.pt(t.GetPosition())),
                        cref, tref))
        return [(c, t) for _d, c, t in sorted(out)]

    for caps, want_via in ((order(CONSUMER), True), (order(LINK_ONLY), False)):
        for cref, tref in caps:
            cap = fps[cref]
            pads = list(cap.Pads())
            sup = [p for p in pads if p.GetNetname() != "GND"][0]
            net = sup.GetNetname()
            nc = sup.GetNetCode()
            tgt = min((p for p in fps[tref].Pads() if p.GetNetname() == net),
                      key=lambda p: R.dist(R.pt(p.GetPosition()),
                                           R.pt(sup.GetPosition())))
            s = R.pt(sup.GetPosition())
            t = R.pt(tgt.GetPosition())
            w = link_width(sup, tgt)

            # same-net copper that already existed BEFORE this cap's own
            # feed trace -- an earlier cap's link is a legal join point, this
            # cap's own feed stub is not (it would make the link zero-length)
            same = R.board_net_rects(board, nc)
            same[R.B] = []

            via = None
            if want_via:
                via, swing, d = via_slot(board, obst, sup, t, nc)
                if via is None:
                    fails.append((cref, "no via slot"))
                else:
                    R.add_via(board, via, nc)
                    obst.add_via_at(via, nc)
                    R.add_track(board, via, s, R.W_VIA_OD, R.F, nc)
                    obst.add_seg(via, s, R.W_VIA_OD / 2.0, R.F, nc)

            # cap pad -> IC pin, on the component layer, as short as it goes
            gs = R.node_geom([(cref, sup)])
            gt = R.node_geom([(tref, tgt)])
            goal = {R.F: gt[1][R.F] + same[R.F], R.B: gt[1][R.B]}
            res = maze.route(nc, gs[2], gt[2], w, layers=(R.F,),
                             start_rects=gs[1], goal_rects=goal, margin=8)
            if res is None:
                res = maze.route(nc, gs[2], gt[2], R.W_SIGNAL, layers=(R.F,),
                                 start_rects=gs[1], goal_rects=goal, margin=14)
                w = R.W_SIGNAL
            if res is None:
                # last resort: let the link change layer.  Logged, because the
                # house pattern wants this link on the component layer.
                res = maze.route(nc, gs[2], gt[2], R.W_SIGNAL,
                                 start_rects=gs[1], goal_rects=goal,
                                 margin=16, via_cost=60)
                w = R.W_SIGNAL
                if res is not None:
                    fails.append((cref, "link needed a via"))
            if res is None:
                fails.append((cref, "no link"))
                rows.append((cref, net, f"{tref}.{tgt.GetNumber()}", w,
                             None, None))
                continue
            R.emit_result(board, obst, res, w, nc)
            rows.append((cref, net, f"{tref}.{tgt.GetNumber()}", w,
                         R.route_len(res), via))

    print("cap      net                        -> pin        link_w  len_mm  feed via")
    for cref, net, pin, w, ln, via in sorted(rows):
        v = f"{via[0]:.2f},{via[1]:.2f}" if via else "-- (in-line/2-node)"
        print(f"{cref:<8} {net:<26} -> {pin:<10} {w:6.3f} "
              f"{(ln or 0):7.2f}  {v}")
    print(f"\n{len(rows)} decouplers fed; feed vias: "
          f"{sum(1 for r in rows if r[5])}; source-chain deferred to step 4: "
          f"{len(SOURCE_CHAIN)}")
    if fails:
        print("FAILURES:", fails)
    R.refill(board)
    R.save(board)
    print("unconnected now:", R.unconnected(board))


if __name__ == "__main__":
    main()
