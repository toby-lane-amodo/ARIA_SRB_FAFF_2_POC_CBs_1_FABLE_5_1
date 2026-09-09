#!/usr/bin/env python3
"""Routing proofs for `faff2_cbs1.kicad_pcb`.

Everything the house rules say must be *proved programmatically* rather than
eyeballed, plus the numbers the routing decisions file quotes.

  --gnd      every SMD GND pad owns its own via (the step-3 completeness
             proof), and no via is shared between two ground lands.  The one
             client-ruled exception is R-C3-1: a QFN ground pin whose lane is
             a closed pocket ties into its own IC's exposed pad, and the
             proof follows the tie through to the EP's via array
  --viainpad no via's DRILL sits in a pad and no via's copper touches a
             FOREIGN pad, both by true rectangle distance to the pad's world
             bbox -- the QFN/SOIC exposed pads are the standing client-ruled
             exception to the first.  A via whose copper hugs its OWN pad is
             counted and listed, not failed: the barrel is nowhere near the
             land, nothing can wick down it, and G1d makes same-net
             via-to-pad proximity free
  --power    via count per power net against the 1.0 A/via budget, and a
             brute-force minimum-via-cut: if removing fewer vias than the
             budget requires splits the net, the net leans on too few
  --usb      differential pair geometry, length and skew
  --analog   closest approach between any switching node and any analog net
             -- the floorplan promised the quiet side, this measures whether
             the routing kept it.  Reports, never fails
  --g5       every signal via's nearest GND via (guideline G5)
  --nets     which nets are still in more than one island

With no flag it runs the lot.  Exit code 1 if any proof fails.
"""
import argparse
import itertools
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402
from route3_gnd import EP_PADS  # noqa: E402
from route3b_gndfix import ep_tied as _ep_tied  # noqa: E402

BUDGET = {
    "/power_entry_24v/V24_IN": 3.0, "Net-(F201-Pad2)": 3.0,
    "Net-(Q201-D)": 3.0, "/power_entry_24v/V24_PROT": 3.0,
    "/power_entry_24v/V0_IN": 3.0, "/power_entry_24v/+24V_SW": 3.0,
    "Net-(R1101-Pad2)": 3.0, "/motor_drive/V24_MOT": 3.0,
    "/motor_drive/MOTOR_U": 3.0, "/motor_drive/MOTOR_V": 3.0,
    "/motor_drive/MOTOR_W": 3.0,
    # the low-side source nets: same leg current, named after the FET
    "Net-(Q1102-S_3)": 3.0, "Net-(Q1104-S_3)": 3.0, "Net-(Q1106-S_3)": 3.0,
    "/power_entry_24v/V24_LOGIC": 0.3, "Net-(U301-SW)": 0.7,
    "Net-(C306-Pad1)": 0.7, "/power_rails/+6V0": 0.6,
    "Net-(U302-SENSE)": 0.3, "Net-(U303-SENSE)": 0.3,
    "+5V": 0.3, "+5VA": 0.3, "Net-(U304-SW)": 1.5, "Net-(C320-Pad1)": 1.5,
    "+3V3": 1.5, "+3V3A": 0.2, "/mcu/+3V3_USB": 0.3, "/mcu/+1V8_USB": 0.2,
    "/linear_encoder/+5V_ENC": 0.3, "/motor_drive/VENC": 0.3,
    "/motor_drive/VM_DRV": 0.1,
}

fails = []


def vias(board, net=None):
    out = []
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA) and (net is None
                                              or t.GetNetname() == net):
            out.append((R.pt(t.GetPosition()), t.GetNetname()))
    return out


def tracks(board, net=None):
    out = []
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            continue
        if net is None or t.GetNetname() == net:
            out.append((R.pt(t.GetStart()), R.pt(t.GetEnd()),
                        R.tomm(t.GetWidth()), t.GetLayer(), t.GetNetname()))
    return out


def inside(p, bb, slack=0.0):
    return (bb[0] - slack <= p[0] <= bb[2] + slack
            and bb[1] - slack <= p[1] <= bb[3] + slack)


# --------------------------------------------------------------------------
def check_gnd(board):
    print("== GND completeness (step 3: one via per pad)")
    # merge physically overlapping pads into one land -- a USB-C shell pin
    # pair (A1/B12) is one piece of copper, not two
    raw = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() != "GND" or not R.pad_copper_layers(p):
                continue
            if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            raw.append((f.GetReference(), p.GetNumber(), R.pad_bbox(p)))
    used = [False] * len(raw)
    lands = []
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
        lands.append(grp)

    gvias = [q for q, n in vias(board) if n == "GND"]
    # components of GND copper made only of tracks and vias -- the stubs
    items = [it for it in R.net_items(board, "GND") if it[0] != "pad"]
    uf = R._touch_graph(items)
    comp = {}
    for i, it in enumerate(items):
        comp.setdefault(uf.find(i), []).append(it)

    covered, owners = set(), {}
    for grp in lands:
        key = (grp[0][0], grp[0][1])
        mine = set()
        for root, its in comp.items():
            touches = any(any(R._boxes_touch(it[3], [bb]) for _r, _n, bb in grp)
                          for it in its)
            if not touches:
                continue
            for it in its:
                if it[0] == "via":
                    mine.add(it[1])
        if mine:
            covered.add(key)
            for v in mine:
                owners.setdefault(v, set()).add(key)

    missing, tied = [], []
    for g in lands:
        key = (g[0][0], g[0][1])
        if key in covered:
            continue
        # R-C3-1: a pin whose lane is a closed pocket may tie into its own
        # IC's exposed pad.  Follow the tie -- and prove the EP has vias.
        grp = [(r, n, bb, None) for r, n, bb in g]
        if _ep_tied(board, grp):
            tied.append(key)
            continue
        missing.append(key)
    shared = {v: o for v, o in owners.items() if len(o) > 1}
    # A cap's ground pad tied straight to the IC ground pin it decouples is
    # the loop G4b asks for, not the shared via R4-1 forbids -- provided the
    # group still owns one via per land.  Assert that, don't assume it.
    thin = []
    seen_grp = set()
    for o in shared.values():
        k = tuple(sorted(o))
        if k in seen_grp:
            continue
        seen_grp.add(k)
        nv = sum(1 for v, oo in owners.items() if tuple(sorted(oo)) == k)
        if nv < len(k):
            thin.append((k, nv))
        else:
            print(f"   {len(k)} lands on one stub island {list(k)}: "
                  f"{nv} vias -- one per land, G4b loop")
    print(f"   SMD GND pads          {sum(len(g) for g in lands)} "
          f"in {len(lands)} lands")
    print(f"   lands reaching a via  {len(lands) - len(missing)}")
    print(f"   GND vias on the board {len(gvias)}")
    print(f"   vias reachable from more than one land: {len(shared)}")
    if tied:
        print(f"   lands tied into their own IC exposed pad (R-C3-1): "
              f"{sorted(tied)}")
    if missing:
        print(f"   MISSING: {sorted(missing)}")
        fails.append(f"GND: {len(missing)} lands without a via")
    if thin:
        for k, nv in thin:
            print(f"   SHARED: {list(k)} share {nv} via(s)")
        fails.append(f"{len(thin)} land groups with fewer vias than lands")
    isl = R.net_islands(board, "GND", plane=True)
    with_pads = [g for g in isl if any(k == "pad" for k, *_ in g)]
    print(f"   GND islands carrying pads: {len(with_pads)} (must be 1)")
    if len(with_pads) != 1:
        fails.append("GND is not one island")


# --------------------------------------------------------------------------
def check_viainpad(board):
    print("\n== via-in-pad (true rectangle distance to the pad's world bbox)")
    allowed = set()
    for f in board.GetFootprints():
        for p in f.Pads():
            if (f.GetReference(), p.GetNumber()) in EP_PADS:
                allowed.add((f.GetReference(), p.GetNumber()))
    drill, foreign, hug = [], [], []
    inpad = 0
    pads = [(f.GetReference(), p.GetNumber(), R.pad_bbox(p), p)
            for f in board.GetFootprints() for p in f.Pads()
            if R.pad_copper_layers(p)]
    for q, net in vias(board):
        for ref, num, bb, p in pads:
            dx = max(bb[0] - q[0], 0.0, q[0] - bb[2])
            dy = max(bb[1] - q[1], 0.0, q[1] - bb[3])
            d = math.hypot(dx, dy)
            if d >= R.VIA_D / 2.0:
                continue
            if (ref, num) in allowed:
                inpad += 1
                continue
            if d < R.VIA_DRILL / 2.0:
                # solder wicks down a barrel that opens into a land
                drill.append((ref, num, q, net, round(d, 3)))
            elif p.GetNetname() != net:
                foreign.append((ref, num, q, net, round(d, 3)))
            else:
                hug.append((ref, num, q, net, round(d, 3)))
    print(f"   vias in an allowed exposed pad (client-ruled): {inpad}")
    print(f"   vias whose DRILL opens into a pad:             {len(drill)}")
    print(f"   vias whose copper touches a FOREIGN pad:       {len(foreign)}")
    print(f"   vias whose copper hugs their OWN pad (G1d):    {len(hug)}"
          + (f"  closest {min(h[4] for h in hug):.3f} mm, barrel "
             f"{min(h[4] for h in hug) + (R.VIA_D - R.VIA_DRILL) / 2.0:.3f} mm"
             " clear" if hug else ""))
    for label, rows in (("DRILL IN PAD", drill), ("FOREIGN PAD", foreign)):
        for b in rows[:20]:
            print(f"     {label}: {b}")
    if drill:
        fails.append(f"{len(drill)} vias drilled into a pad")
    if foreign:
        fails.append(f"{len(foreign)} vias touching a foreign pad")


# --------------------------------------------------------------------------
def islands_without(items, drop):
    keep = [it for i, it in enumerate(items) if i not in drop]
    uf = R._touch_graph(keep)
    groups = {}
    for i, it in enumerate(keep):
        groups.setdefault(uf.find(i), []).append(it)
    return [g for g in groups.values() if any(k == "pad" for k, *_ in g)]


def check_power(board):
    print("\n== power vias against the 1.0 A/via budget "
          "(n = ceil(I/1.0), min 2 on a layer change)")
    print(f"   {'net':<30} {'I des':>6} {'need':>5} {'vias':>5} "
          f"{'min w':>6}  min-cut")
    for net, amps in sorted(BUDGET.items(), key=lambda kv: -kv[1]):
        v = [q for q, n in vias(board, net)]
        tr = tracks(board, net)
        layers = {t[3] for t in tr}
        need = max(2, math.ceil(amps / R.VIA_A)) if len(layers) > 1 else 0
        minw = min((t[2] for t in tr), default=0.0)
        cut = "-"
        if need:
            items = R.net_items(board, net)
            vidx = [i for i, it in enumerate(items) if it[0] == "via"]
            base = len(islands_without(items, set()))
            found = None
            for k in range(1, min(need, 3)):
                for combo in itertools.combinations(vidx, k):
                    if len(islands_without(items, set(combo))) > base:
                        found = k
                        break
                if found:
                    break
            cut = f"{found}" if found else f">={min(need,3)}"
            if found:
                fails.append(f"{net}: splits when {found} via(s) removed, "
                             f"budget needs {need}")
        flag = "" if (not need or len(v) >= need) else "  <-- TOO FEW"
        print(f"   {net:<30} {amps:6.2f} {need:5d} {len(v):5d} "
              f"{minw:6.3f}  {cut}{flag}")
        if need and len(v) < need:
            fails.append(f"{net}: {len(v)} vias, needs {need}")


# --------------------------------------------------------------------------
def _copper_path(board, net, a, b):
    """Shortest electrical path between two pad boxes through the net's copper.

    Total copper length is not the pair length: the USB nets carry the two
    B-row ties as branches off the through path, and counting those makes a
    matched pair look 4.6 mm skewed.  What matters is the run the signal
    actually takes, so walk the graph -- track ends are nodes, a via joins the
    two layers at zero cost -- and take the shortest route between the two
    pads.
    """
    import heapq
    key = lambda q, l: (round(q[0], 3), round(q[1], 3), l)
    adj = {}

    def edge(u, v, w):
        adj.setdefault(u, []).append((v, w))
        adj.setdefault(v, []).append((u, w))

    for s, e, _w, lay, _n in tracks(board, net):
        edge(key(s, lay), key(e, lay), R.dist(s, e))
    for q, _n in vias(board, net):
        edge(key(q, R.F), key(q, R.B), 0.0)
    # A run may stop anywhere inside its pad rather than on the centre, so
    # match the ends by the pad's own box, not by an exact coordinate.
    def within(box, u):
        return box[0] - 0.01 <= u[0] <= box[2] + 0.01 and \
               box[1] - 0.01 <= u[1] <= box[3] + 0.01
    src = [u for u in adj if within(a, u)]
    dst = {u for u in adj if within(b, u)}
    dist = {u: 0.0 for u in src}
    pq = [(0.0, u) for u in dist]
    heapq.heapify(pq)
    while pq:
        d, u = heapq.heappop(pq)
        if u in dst:
            return d
        if d > dist.get(u, 1e18):
            continue
        for v, w in adj.get(u, ()):
            nd = d + w
            if nd < dist.get(v, 1e18) - 1e-9:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return None


# The through path each half of the pair actually takes: the A-row connector
# pad, the two clamp pads of D1001 it passes, and the PHY pin.
USB_PATH = {
    "/mcu/USB_DM": [("J1001", "A7"), ("D1001", "6"), ("D1001", "1"),
                    ("U1002", "19")],
    "/mcu/USB_DP": [("J1001", "A6"), ("D1001", "4"), ("D1001", "3"),
                    ("U1002", "18")],
}


def check_usb(board):
    print("\n== USB 2.0 HS pair (target 90 ohm: 0.30 mm wide, 0.20 mm gap)")
    out = {}
    for net in ("/mcu/USB_DM", "/mcu/USB_DP"):
        tr = tracks(board, net)
        ws = sorted({round(t[2], 3) for t in tr})
        lay = sorted({board.GetLayerName(t[3]) for t in tr})
        nv = len(vias(board, net))
        pts = []
        for ref, num in USB_PATH[net]:
            g = R.pad_group(board, ref, num)
            pts.append(R.pad_bbox(g[0][1]) if g else None)
        ln, ok = 0.0, True
        for a, b in zip(pts, pts[1:]):
            d = _copper_path(board, net, a, b) if a and b else None
            if d is None:
                ok = False
                break
            ln += d
        out[net] = ln if ok else None
        print(f"   {net:<16} "
              + (f"{ln:7.2f} mm" if ok else "  NO PATH")
              + f"  widths {ws}  layers {lay}  vias {nv}"
              + f"  (copper total {sum(R.dist(a, b) for a, b, *_ in tr):.2f})")
    if out["/mcu/USB_DM"] is None or out["/mcu/USB_DP"] is None:
        fails.append("USB through path not continuous")
        return
    skew = abs(out["/mcu/USB_DM"] - out["/mcu/USB_DP"])
    print(f"   through-path skew {skew:.3f} mm "
          f"({'within' if skew < 1.0 else 'OVER'} the 1 mm working tolerance)")
    if skew >= 1.0:
        fails.append(f"USB skew {skew:.2f} mm")


# --------------------------------------------------------------------------
# The quiet side is a placement promise; this is what checks it held in copper.
NOISY = ("Net-(U301-SW)", "Net-(U304-SW)", "Net-(U301-BOOT)",
         "Net-(U304-BOOT)", "/motor_drive/MOTOR_U", "/motor_drive/MOTOR_V",
         "/motor_drive/MOTOR_W", "/motor_drive/V24_MOT",
         "Net-(Q1101-G)", "Net-(Q1102-G)", "Net-(Q1103-G)",
         "Net-(Q1104-G)", "Net-(Q1105-G)", "Net-(Q1106-G)")
ANALOG_WANT = 5.0        # mm -- what the floorplan promised, not a DRC rule


def check_analog(board):
    """Closest approach between any switching node and any analog net.

    The placement put the load-cell AFE bottom-left and the switchers and the
    bridge in the right-hand column, and the routing order gave the analog
    chains their corridor before the general fill could claim it.  Both of
    those are claims about distance, so measure it: for every pair of
    (switching-node segment, analog segment) take the segment-to-segment
    distance and report the worst.  This is not a DRC rule and nothing fails
    the build on it -- it is the number that says whether the separation the
    floorplan promised actually survived the routing.
    """
    print(f"\n== analog separation (floorplan promise: {ANALOG_WANT} mm)")
    from route5_critical import ANALOG  # noqa: E402

    def segs(names):
        out = []
        for a, b, _w, _l, n in tracks(board):
            if n in names:
                out.append((a, b, n))
        return out

    noisy = segs(set(NOISY))
    quiet = segs(set(ANALOG))
    if not noisy or not quiet:
        print("   nothing to compare")
        return

    def seg_dist(p, q, r, s):
        # segment-segment distance, 2D, no intersection test needed here
        def pt_seg(a, b, c):
            vx, vy = c[0] - b[0], c[1] - b[1]
            L = vx * vx + vy * vy
            t = 0.0 if L == 0 else max(0.0, min(1.0, ((a[0] - b[0]) * vx
                                                      + (a[1] - b[1]) * vy) / L))
            return math.hypot(a[0] - (b[0] + t * vx), a[1] - (b[1] + t * vy))
        return min(pt_seg(p, r, s), pt_seg(q, r, s),
                   pt_seg(r, p, q), pt_seg(s, p, q))

    worst = None
    for a, b, na in noisy:
        for c, d, nq in quiet:
            # cheap reject on bounding boxes before the exact distance
            if (min(a[0], b[0]) - max(c[0], d[0]) > ANALOG_WANT
                    or min(c[0], d[0]) - max(a[0], b[0]) > ANALOG_WANT
                    or min(a[1], b[1]) - max(c[1], d[1]) > ANALOG_WANT
                    or min(c[1], d[1]) - max(a[1], b[1]) > ANALOG_WANT):
                continue
            dd = seg_dist(a, b, c, d)
            if worst is None or dd < worst[0]:
                worst = (dd, na, nq, a, c)
    if worst is None:
        print(f"   no switching node comes within {ANALOG_WANT} mm of an "
              f"analog net")
        return
    d, na, nq, a, c = worst
    print(f"   closest approach {d:.2f} mm: {na} at "
          f"{a[0]:.1f},{a[1]:.1f}  vs  {nq} at {c[0]:.1f},{c[1]:.1f}")
    if d < ANALOG_WANT:
        print(f"   NOTE: under the {ANALOG_WANT} mm the floorplan promised "
              f"-- for the captain's eye, not a failure")


# --------------------------------------------------------------------------
def check_g5(board):
    print("\n== G5: every signal via wants a GND via beside it")
    g = [q for q, n in vias(board) if n == "GND"]
    rows = []
    for q, net in vias(board):
        if net == "GND":
            continue
        d = min((R.dist(q, p) for p in g), default=1e9)
        rows.append((d, net, q))
    rows.sort(reverse=True)
    far = [r for r in rows if r[0] > 3.0]
    print(f"   non-GND vias {len(rows)};  nearest GND via: "
          f"median {sorted(r[0] for r in rows)[len(rows)//2]:.2f} mm, "
          f"worst {rows[0][0]:.2f} mm")
    print(f"   further than 3.0 mm from any GND via: {len(far)}")
    for d, net, q in far[:15]:
        print(f"     {d:6.2f} mm  {net:<28} at {q[0]:.2f},{q[1]:.2f}")


# --------------------------------------------------------------------------
def check_nets(board):
    print("\n== net completeness")
    nets = sorted({p.GetNetname() for f in board.GetFootprints()
                   for p in f.Pads() if p.GetNetname()
                   and not p.GetNetname().startswith("unconnected-")})
    split = []
    for n in nets:
        if len(R.pad_nodes(board, n)) < 2:
            continue
        if not R.net_is_whole(board, n, plane=(n == "GND")):
            split.append((n, len(R.net_islands(board, n, plane=(n == "GND")))))
    print(f"   {len(nets)} nets;  still split: {len(split)}")
    for n, k in split:
        print(f"     {n:<40} {k} islands")
    if split:
        fails.append(f"{len(split)} nets still split")
    t = [x for x in board.GetTracks() if not isinstance(x, pcbnew.PCB_VIA)]
    v = [x for x in board.GetTracks() if isinstance(x, pcbnew.PCB_VIA)]
    ln = {}
    for x in t:
        k = board.GetLayerName(x.GetLayer())
        ln[k] = ln.get(k, 0.0) + R.dist(R.pt(x.GetStart()), R.pt(x.GetEnd()))
    print(f"   tracks {len(t)}  vias {len(v)}  copper "
          + "  ".join(f"{k} {vv:.0f} mm" for k, vv in sorted(ln.items())))


def main():
    ap = argparse.ArgumentParser()
    for f in ("gnd", "viainpad", "power", "usb", "analog", "g5", "nets"):
        ap.add_argument("--" + f, action="store_true")
    a = ap.parse_args()
    run_all = not any(vars(a).values())
    board = R.load()
    if run_all or a.gnd:
        check_gnd(board)
    if run_all or a.viainpad:
        check_viainpad(board)
    if run_all or a.power:
        check_power(board)
    if run_all or a.usb:
        check_usb(board)
    if run_all or a.analog:
        check_analog(board)
    if run_all or a.g5:
        check_g5(board)
    if run_all or a.nets:
        check_nets(board)
    print("\n" + ("ALL PROOFS PASS" if not fails else "FAILURES:"))
    for f in fails:
        print("   " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
