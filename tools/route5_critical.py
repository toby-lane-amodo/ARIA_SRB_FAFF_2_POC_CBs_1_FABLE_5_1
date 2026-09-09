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


def link(board, obst, maze, net, a, b, w, layers=(R.F,), margin=12, **kw):
    """R.link, with a printable length and an explicit ok flag."""
    ln, width, nv, direct = R.link(board, obst, maze, net, a, b, w,
                                   layers=layers, margin=margin, **kw)
    return (ln if ln is not None else float("nan")), width, nv, (ln is not None)


def fmt(ln, ok):
    return f"{ln:6.2f} mm" if ok else "   FAILED"


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


# Phase-node via drops.  P1-03: each phase leaves the node on B.Cu and runs
# south to J1103, which keeps the whole discontinuous di/dt inside the bridge
# and keeps F.Cu free for the six gate runs.  3 vias at 1.0 A each for the 3 A
# peak (setup S3).  x is the FET column, y sits in the gap between the
# high-side source and the low-side drain.
PHASE_DROP = {"/motor_drive/MOTOR_U": (226.0, (119.1, 120.0, 120.9)),
              "/motor_drive/MOTOR_V": (211.0, (119.1, 120.0, 120.9)),
              "/motor_drive/MOTOR_W": (196.0, (119.1, 120.0, 120.9))}


def phase_drop(board, obst, maze, net):
    """Plant the phase's via cluster on the node and return the via centres."""
    nc = R.netcode(board, net)
    x, ys = PHASE_DROP[net]
    out = []
    for y in ys:
        q = None
        for dx in (0.0, 0.35, -0.35, 0.7, -0.7, 1.05, -1.05):
            c = (round(x + dx, 3), y)
            win = obst.ij(c[0] - 1.8, c[1] - 1.8) + obst.ij(c[0] + 1.8,
                                                            c[1] + 1.8)
            m = obst.via_mask(win, nc)
            i, j = obst.ij(*c)
            if not m[i - win[0], j - win[1]]:
                q = c
                break
        if q is None:
            continue
        R.add_via(board, q, nc)
        obst.add_via_at(q, nc)
        out.append(q)
    # tie the cluster together on F.Cu at motor width -- it sits on the node
    for a, b in zip(out, out[1:]):
        R.add_track(board, a, b, W_PHASE, R.F, nc)
        obst.add_seg(a, b, W_PHASE / 2.0, R.F, nc)
    return out


def bridge(board, obst, maze):
    """Three passes over the bridge, and the order is the whole point.

    Pass A closes each leg's own commutation loop: the phase node from the
    high-side source to the low-side drain, and the low-side source down to
    its shunt.  Both are millimetres long, both are at motor width, and
    neither has an alternative path -- they go first because nothing else can
    be allowed to sit in them.

    Pass B then draws the **six gate runs**, all three legs together, before
    any of the short taps.  They are the hardest nets in the block: 13-27 mm
    of F.Cu each, via-free by P1-05 open point 1, through channels the legs
    themselves narrow.  Drawing them per leg -- gates for U, then everything
    for U, then gates for V -- is what lost four of them: leg U's own sense
    and Kelvin taps had already taken the channel leg V's gates needed.
    Hardest first, and the short taps route around them.

    Pass C takes the taps that have room to detour (phase sense, Kelvin,
    test points) and pass D the three phase outputs, on B.Cu from a via drop
    on the node itself (P1-03, 3 A peak at 1.0 A/via) -- last, because a 1 mm
    phase output on F.Cu cuts straight through the neighbouring leg's gate
    corridor.
    """
    print("== commutation loop -- pass A: phase nodes and shunt paths")
    for (phase, qh, ql, gh, gl, sh, shunt, snet, sp, sn, tp, jp) in LEGS:
        d, w, v, ok = link(board, obst, maze, phase, (qh, "1_2_3"),
                           (ql, "5_6_7_8"), W_PHASE, margin=8)
        print(f"   {phase:<24} {qh}.S -> {ql}.D     {fmt(d, ok)} @ {w:.2f}")
        d3, w3, _, ok3 = link(board, obst, maze, snet, (ql, "1_2_3"),
                              (shunt, "1"), W_PHASE, margin=10)
        print(f"   {snet:<24} {ql}.S -> {shunt}.1   {fmt(d3, ok3)} @ {w3:.2f}")

    print("\n== pass B: the six gate runs, all three legs, hardest first")
    gates = []
    for (phase, qh, ql, gh, gl, sh, shunt, snet, sp, sn, tp, jp) in LEGS:
        for q, pin in ((qh, gh), (ql, gl)):
            ga = R.node_geom(R.pad_group(board, q, "4"))[0]
            gb = R.node_geom(R.pad_group(board, "U1101", pin))[0]
            gates.append((R.dist(ga, gb), f"Net-({q}-G)", q, pin))
    for _d, net, q, pin in sorted(gates, reverse=True):
        dd, ww, nv, ok = link(board, obst, maze, net, (q, "4"),
                              ("U1101", pin), W_GATE, margin=22,
                              allow_layer_change=False)
        if not ok:
            # F.Cu only is the intent, not a law of physics -- take the layer
            # change rather than leave a gate open, and say so.
            dd, ww, nv, ok = link(board, obst, maze, net, (q, "4"),
                                  ("U1101", pin), W_GATE, layers=(R.F, R.B),
                                  margin=26, via_cost=120)
        note = "" if nv == 0 else f"  <-- {nv} via(s), not via-free"
        print(f"   {net:<20} {q}.G -> U1101.{pin:<3} {fmt(dd, ok)} "
              f"@ {ww:.2f}{note}")

    print("\n== pass C: phase sense, Kelvin taps and the phase test points")
    for (phase, qh, ql, gh, gl, sh, shunt, snet, sp, sn, tp, jp) in LEGS:
        d7, w7, nv7, ok7 = link(board, obst, maze, phase, (ql, "5_6_7_8"),
                                ("U1101", sh), 0.35, layers=(R.F, R.B),
                                margin=22, via_cost=70)
        print(f"   {phase:<24} SH   -> U1101.{sh:<3}   {fmt(d7, ok7)} @ "
              f"{w7:.2f}  vias {nv7}")
        d4, w4, _, ok4 = link(board, obst, maze, snet, (shunt, "1"),
                              ("U1101", sp), W_KELVIN, layers=(R.F, R.B),
                              margin=22, via_cost=70)
        print(f"   {snet:<24} KELVIN {shunt}.1 -> U1101.{sp:<3} "
              f"{fmt(d4, ok4)} @ {w4:.2f}")
        dt, wt, _, okt = link(board, obst, maze, phase, (ql, "5_6_7_8"),
                              (tp, "1"), 0.6, margin=12)
        print(f"   {phase:<24} TP   -> {tp:<10} {fmt(dt, okt)} @ {wt:.2f}")

    print("\n== SNx returns: a dedicated trace only where it is really short")
    for (phase, qh, ql, gh, gl, sh, shunt, snet, sp, sn, tp, jp) in LEGS:
        d5, w5, _, ok5 = link(board, obst, maze, "GND", (shunt, "2"),
                              ("U1101", sn), W_KELVIN, layers=(R.F, R.B),
                              margin=20, via_cost=70, max_len=14.0)
        print(f"   {shunt}.2 -> U1101.{sn:<3} "
              + (f"{d5:6.2f} mm @ {w5:.2f}" if ok5
                 else "  none: over 14 mm, the plane is the return"))

    print("\n== pass D: phase outputs to J1103, on B.Cu from the node drop")
    for (phase, qh, ql, gh, gl, sh, shunt, snet, sp, sn, tp, jp) in LEGS:
        vias = phase_drop(board, obst, maze, phase)
        nc = R.netcode(board, phase)
        gb = R.node_geom(R.pad_group(board, "J1103", jp))
        done = False
        for ww in (W_PHASE, 0.80, 0.60):
            for v in vias:
                res = maze.route(nc, [v], gb[2], ww, layers=(R.B,),
                                 start_rects={R.B: [(v[0] - 0.2, v[1] - 0.2,
                                                     v[0] + 0.2, v[1] + 0.2)]},
                                 goal_rects=gb[1], margin=25)
                if res is None:
                    continue
                R.emit_result(board, obst, res, ww, nc)
                print(f"   {phase:<24} {len(vias)} node vias, B.Cu to "
                      f"J1103.{jp}  {R.route_len(res):6.2f} mm @ {ww:.2f}")
                done = True
                break
            if done:
                break
        if not done:
            d2, w2, v2, ok2 = link(board, obst, maze, phase, (ql, "5_6_7_8"),
                                   ("J1103", jp), W_PHASE, layers=(R.F, R.B),
                                   margin=25, via_cost=30)
            print(f"   {phase:<24} -> J1103.{jp} FALLBACK on F.Cu "
                  f"{fmt(d2, ok2)} @ {w2:.2f} vias {v2}")


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
    print(f"   {obst.reserve_pin_escapes(board)} fine-pitch pin escape lanes held")
    R.escape_pass(board, obst)
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
        d, ww, v, okk = link(board, obst, maze, net, a, b, w, margin=14,
                             layers=(R.F, R.B), via_cost=80)
        print(f"   {net:<20} {a[0]}.{a[1]} -> {b[0]}.{b[1]}  "
              f"{fmt(d, okk)} @ {ww:.2f}")
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
