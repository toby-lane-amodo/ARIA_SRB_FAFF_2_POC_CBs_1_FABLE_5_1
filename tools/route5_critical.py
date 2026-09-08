#!/usr/bin/env python3
"""Routing step 5 -- the critical nets, before the general signal fill.

Order inside the stage, tightest constraint first:

1. **Commutation loop.**  Each leg's phase node is drawn high-source to
   low-drain first and kept on F.Cu; the per-leg bypass and the DC-link store
   went down in step 4, directly above the drains, so the loop
   rail -> high FET -> phase -> low FET -> shunt -> plane encloses as little
   area as the three-in-a-row floorplan allows.  Gate runs stay on F.Cu and
   via-free in the channels between legs (place1 open point 1).
2. **Shunt Kelvin.**  The current-sense tap is taken at the shunt pad itself
   on a thin trace, never off the power path, and the DRV's SNx return gets a
   dedicated F.Cu trace back to the shunt's own ground pad *in addition to*
   the plane -- see the review note in the decisions file: the schematic ties
   SNx to GND, so a true four-wire Kelvin is not available on the low side and
   this trace is the best the layout can offer.
3. **USB 2.0 HS pair**, 90 ohm differential: 0.30 mm wide, 0.20 mm gap, drawn
   from a single centreline and offset, so the two are matched by
   construction; plane-referenced on F.Cu over In1.Cu for the whole run.
4. **RS-422 encoder pairs**, routed pair-by-pair so each P/N run stays
   together, with the match reported.
5. **Analog**: the load-cell bridge and excitation chain and the RTD chain,
   both on the quiet side, kept off the digital corridors by routing them
   before the general fill claims the space.
6. **50 ohm sync** to the SMA, source-terminated at R907, ESD in line.
7. **Clocks**: the ADS1235 MCO2 clock kept clear of the analog inputs, and
   both crystals' loops.
"""
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402

W_GATE = 0.40
W_PHASE = 1.00
W_KELVIN = 0.25
USB_W = 0.30
USB_GAP = 0.20


def grp(board, ref, num):
    out = []
    for f in board.GetFootprints():
        if f.GetReference() != ref:
            continue
        for p in f.Pads():
            if p.GetNumber() == num and R.pad_copper_layers(p):
                out.append((ref, p))
    if not out:
        raise KeyError(f"{ref}.{num}")
    return out


def gmin(g):
    bs = [R.pad_bbox(p) for _r, p in g]
    bb = (min(b[0] for b in bs), min(b[1] for b in bs),
          max(b[2] for b in bs), max(b[3] for b in bs))
    return min(bb[2] - bb[0], bb[3] - bb[1])


def link(board, obst, maze, net, a, b, w, layers=(R.F,), margin=12, **kw):
    nc = R.netcode(board, net)
    ga, gb = grp(board, *a), grp(board, *b)
    width = max(R.W_SIGNAL, round(min(w, gmin(ga), gmin(gb)), 4))
    na, nb = R.node_geom(ga), R.node_geom(gb)
    for m in (margin, margin * 2, margin * 4):
        res = maze.route(nc, na[2], nb[2], width, layers=layers,
                         start_rects=na[1], goal_rects=nb[1], margin=m, **kw)
        if res is not None:
            R.emit_result(board, obst, res, width, nc)
            return R.route_len(res), width, len(res[1])
    return None, width, 0


# --------------------------------------------------------------------------
# 1/2  bridge
# --------------------------------------------------------------------------
LEGS = [
    # phase net, high FET, low FET, gate pins, phase sense pin, shunt,
    # source net, SPx pin, SNx pin, phase test point, connector pin
    ("/motor_drive/MOTOR_U", "Q1101", "Q1102", "6", "8", "7", "R1125",
     "Net-(Q1102-S_3)", "9", "10", "TP1115", "1"),
    ("/motor_drive/MOTOR_V", "Q1103", "Q1104", "15", "13", "14", "R1126",
     "Net-(Q1104-S_3)", "12", "11", "TP1118", "2"),
    ("/motor_drive/MOTOR_W", "Q1105", "Q1106", "16", "18", "17", "R1127",
     "Net-(Q1106-S_3)", "19", "20", "TP1121", "3"),
]


def bridge(board, obst, maze):
    print("== commutation loop")
    for (phase, qh, ql, gh, gl, sh, shunt, snet, sp, sn, tp, jp) in LEGS:
        # phase node: high-side source straight down onto the low-side drain
        d, w, v = link(board, obst, maze, phase, (qh, "1_2_3"), (ql, "5_6_7_8"),
                       W_PHASE, margin=8)
        print(f"   {phase:<24} {qh}.S -> {ql}.D   {d:6.2f} mm @ {w:.2f}")
        # phase observation point, then out to the connector on B.Cu (P1-03)
        link(board, obst, maze, phase, (ql, "5_6_7_8"), (tp, "1"), 0.6,
             margin=10)
        d2, w2, v2 = link(board, obst, maze, phase, (ql, "5_6_7_8"),
                          ("J1103", jp), W_PHASE, layers=(R.F, R.B),
                          margin=16, via_cost=40)
        print(f"   {phase:<24} {ql}.D -> J1103.{jp} {d2:6.2f} mm @ {w2:.2f}"
              f"  vias {v2}")
        # low-side source -> shunt, power width; then the Kelvin sense tap
        d3, w3, _ = link(board, obst, maze, snet, (ql, "1_2_3"), (shunt, "1"),
                         W_PHASE, margin=10)
        print(f"   {snet:<24} {ql}.S -> {shunt}.1 {d3:6.2f} mm @ {w3:.2f}")
        d4, w4, _ = link(board, obst, maze, snet, (shunt, "1"), ("U1101", sp),
                         W_KELVIN, margin=16)
        print(f"   {snet:<24} KELVIN {shunt}.1 -> U1101.{sp} "
              f"{d4:6.2f} mm @ {w4:.2f}")
        # SNx return: dedicated trace from the shunt's own ground pad
        d5, w5, _ = link(board, obst, maze, "GND", (shunt, "2"),
                         ("U1101", sn), W_KELVIN, margin=18)
        print(f"   GND                      KELVIN-RTN {shunt}.2 -> "
              f"U1101.{sn} {d5:6.2f} mm @ {w5:.2f}")
        # gate drives, F.Cu, via-free
        for q, pin in ((qh, gh), (ql, gl)):
            d6, w6, _ = link(board, obst, maze, f"Net-({q}-G)", (q, "4"),
                             ("U1101", pin), W_GATE, margin=16)
            print(f"   Net-({q}-G){'':<10} {q}.G -> U1101.{pin:<3} "
                  f"{d6:6.2f} mm @ {w6:.2f}")
        # high-side source sense (SHx) shares the phase node
        d7, w7, _ = link(board, obst, maze, phase, (ql, "5_6_7_8"),
                         ("U1101", sh), 0.35, margin=16)
        print(f"   {phase:<24} SH   -> U1101.{sh:<3} {d7:6.2f} mm @ {w7:.2f}")


# --------------------------------------------------------------------------
# 3  USB 2.0 HS differential pair
# --------------------------------------------------------------------------
def offset_polyline(pts, d):
    """Offset a polyline by d (left positive), mitring at the vertices."""
    def norm(a, b):
        vx, vy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(vx, vy)
        return (-vy / n, vx / n)

    segs = []
    for a, b in zip(pts, pts[1:]):
        nx, ny = norm(a, b)
        segs.append(((a[0] + nx * d, a[1] + ny * d),
                     (b[0] + nx * d, b[1] + ny * d)))
    out = [segs[0][0]]
    for s0, s1 in zip(segs, segs[1:]):
        p = intersect(s0[0], s0[1], s1[0], s1[1])
        out.append(p if p else s0[1])
    out.append(segs[-1][1])
    return [(round(x, 4), round(y, 4)) for x, y in out]


def intersect(a, b, c, d):
    x1, y1, x2, y2 = a[0], a[1], b[0], b[1]
    x3, y3, x4, y4 = c[0], c[1], d[0], d[1]
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-9:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def plen(pts):
    return sum(R.dist(a, b) for a, b in zip(pts, pts[1:]))


# Hand-drawn because the geometry is fixed by three things at once: the
# USB-C flip pads interleave DP and DM, D1001's GND pin sits *between* the two
# data lines, and U1002's pins 18/19 are 0.5 mm apart.  The pair spreads to
# 1.6 mm pitch across D1001 so that GND pin can take its own via between them,
# then closes back to 0.5 mm at the PHY.
USB_SEGMENTS = [
    # (centreline, DM offset sign) -- DM is west (A7 = 149.75), DP east
    [(150.00, 39.18), (150.00, 40.40), (150.00, 41.60)],       # J1001 -> D1001
    [(150.00, 43.80), (150.00, 45.60), (149.00, 47.60),
     (149.00, 54.60)],                                          # D1001 -> PHY
]
USB_FANS = [
    # (net, from, to) short fan segments at the pitch changes
    ("/mcu/USB_DM", (149.75, 41.60), (149.50, 42.20)),
    ("/mcu/USB_DP", (150.25, 41.60), (150.50, 42.20)),
]
USB_SPREAD = 0.80   # half-pitch across D1001, so its GND via fits between


def usb_pair(board, obst, maze):
    print("\n== USB 2.0 HS pair (90 ohm differential, 0.30/0.20)")
    dm = R.netcode(board, "/mcu/USB_DM")
    dp = R.netcode(board, "/mcu/USB_DP")
    half = (USB_W + USB_GAP) / 2.0
    lens = {"/mcu/USB_DM": 0.0, "/mcu/USB_DP": 0.0}

    # J1001 -> D1001 south pads, 0.5 mm pitch
    c = USB_SEGMENTS[0]
    a = offset_polyline(c, -half)
    b = offset_polyline(c, +half)
    R.polyline(board, a, USB_W, R.F, dm)
    R.polyline(board, b, USB_W, R.F, dp)
    for pts, nc in ((a, dm), (b, dp)):
        for p, q in zip(pts, pts[1:]):
            obst.add_seg(p, q, USB_W / 2, R.F, nc)
    lens["/mcu/USB_DM"] += plen(a)
    lens["/mcu/USB_DP"] += plen(b)
    for net, p, q in USB_FANS:
        nc = R.netcode(board, net)
        R.add_track(board, p, q, USB_W, R.F, nc)
        obst.add_seg(p, q, USB_W / 2, R.F, nc)
        lens[net] += R.dist(p, q)

    # D1001 north pads -> U1002, spreading around D1001's own GND via
    c = USB_SEGMENTS[1]
    spread = [USB_SPREAD, USB_SPREAD, half, half]
    a, b = [], []
    for i, p in enumerate(c):
        a.append((round(p[0] - spread[i], 4), p[1]))
        b.append((round(p[0] + spread[i], 4), p[1]))
    # the pair leaves D1001 pins 1/3 at +/-0.5, opens to +/-0.8, then closes
    a[0] = (149.50, 43.80)
    b[0] = (150.50, 43.80)
    R.polyline(board, a, USB_W, R.F, dm)
    R.polyline(board, b, USB_W, R.F, dp)
    for pts, nc in ((a, dm), (b, dp)):
        for p, q in zip(pts, pts[1:]):
            obst.add_seg(p, q, USB_W / 2, R.F, nc)
    lens["/mcu/USB_DM"] += plen(a)
    lens["/mcu/USB_DP"] += plen(b)

    # D1001's ground pin, deferred out of step 3, now has room between them
    gnd = R.netcode(board, "GND")
    for q in ((150.00, 45.10),):
        R.add_via(board, q, gnd)
        obst.add_via_at(q, gnd)
        R.add_track(board, (150.00, 43.80), q, 0.30, R.F, gnd)
        obst.add_seg((150.00, 43.80), q, 0.15, R.F, gnd)
    print(f"   D1001 GND pin: own via at 150.00,45.10 between the two lines")

    print(f"   DM {lens['/mcu/USB_DM']:6.2f} mm   DP {lens['/mcu/USB_DP']:6.2f}"
          f" mm   skew {abs(lens['/mcu/USB_DM']-lens['/mcu/USB_DP']):.3f} mm")

    # the flip pads (B6/B7) and everything else on those nets
    for net in ("/mcu/USB_DM", "/mcu/USB_DP"):
        f = R.connect_net(board, obst, maze, net, width=USB_W, via_cost=45,
                          margin=14)
        if f:
            print(f"   ! {net} left {f}")


# --------------------------------------------------------------------------
# 4-7  pairs, analog, RF, clocks
# --------------------------------------------------------------------------
RS422 = [("/linear_encoder/ENC_A_P", "/linear_encoder/ENC_A_N"),
         ("/linear_encoder/ENC_B_P", "/linear_encoder/ENC_B_N"),
         ("/linear_encoder/ENC_Z_P", "/linear_encoder/ENC_Z_N")]

ANALOG = [
    # load cell: connector -> series R -> filter -> ADC, and the reference leg
    "Net-(J501-Pad1)", "Net-(J501-Pad2)", "Net-(J501-Pad4)", "Net-(J501-Pad5)",
    "Net-(J501-Pad6)", "Net-(J501-Pad7)", "Net-(C507-Pad1)",
    "Net-(J503-In)", "Net-(J504-In)",
    "Net-(U501B-REFP0)", "Net-(U501B-REFN0)",
    "Net-(U501B-AIN0)", "Net-(U501B-AIN1)", "Net-(U501B-AIN2)",
    "Net-(U501B-AIN3)",
    "Net-(U501A-CAPP)", "Net-(U501A-CAPN)",
    # temp sense
    "Net-(J701-Pad1)", "Net-(J701-Pad2)", "Net-(J701-Pad3)", "Net-(J701-Pad4)",
    "Net-(J702-Pad1)", "Net-(J702-Pad2)", "Net-(J702-Pad4)",
    "Net-(U701-AIN0{slash}REFP1)", "Net-(U701-AIN1)", "Net-(U701-AIN2)",
    "Net-(U701-AIN3{slash}REFN1)", "Net-(U701-REFP0)", "Net-(U701-REFN0)",
    # linear encoder reference
    "/linear_encoder/ENC_VREF",
]

RF = ["Net-(D903-K)", "Net-(R907-Pad1)", "/mcu/SYNC_TRIG"]

CLOCKS = ["/loadcell_afe/ADS1235_CLKIN", "Net-(U501A-CLKIN)",
          "/mcu/HSE_CLK_24M", "Net-(Y1001-OUT)",
          "/mcu/USB_REFCLK_24M", "/mcu/USB_XO_24M"]


def main():
    board = R.load()
    obst = R.Obstacles(board)
    maze = R.Maze(obst)

    bridge(board, obst, maze)
    usb_pair(board, obst, maze)

    print("\n== RS-422 encoder pairs")
    for p, n in RS422:
        for net in (p, n):
            f = R.connect_net(board, obst, maze, net, width=0.20,
                              via_cost=60, margin=16)
            ln = sum(R.dist(R.pt(t.GetStart()), R.pt(t.GetEnd()))
                     for t in board.GetTracks()
                     if t.GetNetname() == net
                     and not isinstance(t, pcbnew.PCB_VIA))
            print(f"   {net:<32} {ln:6.2f} mm"
                  + ("  UNROUTED " + ",".join(f) if f else ""))

    print("\n== analog (quiet side first)")
    for net in ANALOG:
        w = R.net_width(net)
        f = R.connect_net(board, obst, maze, net, width=max(w, 0.25),
                          via_cost=70, margin=18)
        if f:
            print(f"   ! {net} left {f}")
    print(f"   {len(ANALOG)} analog nets routed at >= 0.25 mm")

    print("\n== 50 ohm sync chain (ESD in line, source terminated at R907)")
    for a, b, net, w in ((("J902", "1"), ("D903", "1"), "Net-(D903-K)", 0.37),
                         (("D903", "1"), ("R907", "2"), "Net-(D903-K)", 0.37),
                         (("R907", "1"), ("U901", "4"), "Net-(R907-Pad1)",
                          0.37)):
        d, ww, v = link(board, obst, maze, net, a, b, w, margin=14)
        print(f"   {net:<20} {a[0]}.{a[1]} -> {b[0]}.{b[1]}  "
              f"{(d or 0):6.2f} mm @ {ww:.2f}")
    for net in RF:
        f = R.connect_net(board, obst, maze, net,
                          width=R.net_width(net), via_cost=80, margin=20)
        if f:
            print(f"   ! {net} left {f}")

    print("\n== clocks")
    for net in CLOCKS:
        f = R.connect_net(board, obst, maze, net, width=0.20, via_cost=80,
                          margin=20)
        print(f"   {net:<34}" + ("  UNROUTED " + ",".join(f) if f else "  ok"))

    R.refill(board)
    R.save(board)
    print("\nunconnected now:", R.unconnected(board))


if __name__ == "__main__":
    main()
