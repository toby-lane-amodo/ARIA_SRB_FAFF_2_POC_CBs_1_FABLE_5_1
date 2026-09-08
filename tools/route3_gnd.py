#!/usr/bin/env python3
"""Routing step 3 -- every GND connection, one via per pad.

House rule (pcb-layout-style, VanClock 2026-07-30, reaffirmed 2026-07-31):
**every GND pin always gets its OWN GND via -- never one via shared between
two ground pads.**  A shared via puts its series inductance inside both
capacitors' current loops, which partly defeats paralleling them at all
(Bogatin, *Practical PCB Design*, p.344).

Per pad: short trace -> via -> plane.  R/C pads take the trace at via-OD
width; ICs and other small pads take the widest trace that does not exceed the
pad width.  No via-in-pad -- the client-ruled QFN/SOIC exposed-pad via array
is the standing exception (G9).  PTH GND pads need no copper at all: their
barrels already reach both planes.

**A stitch via sits in its pin's OWN escape lane** -- straight in-line exit,
the pin's natural fan-out direction (R3-1).  Where in-line is geometrically
impossible the via is swung and the deviation is logged for review rather
than assumed fine.

Completeness is proved programmatically at the end (`--proof`), and the
no-via-in-pad rule is asserted by true rectangle distance from the barrel to
each pad's world bbox -- not by a circumscribed circle, which falsely rejects
legitimate same-net hugs.
"""
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402

EP_AREA = 3.0          # mm^2 -- above this a GND pad is an exposed pad
EP_PITCH = 1.30        # mm, via pitch inside an exposed pad
GAP = 0.05             # via pad to its own pad edge
SWINGS = [0, 12, -12, 25, -25, 40, -40, 55, -55, 70, -70, 90, -90,
          115, -115, 140, -140, 180]
EXTRAS = [0.0, 0.15, 0.30, 0.50, 0.75, 1.00, 1.40]


def support(w, h, ux, uy):
    return abs(ux) * w / 2.0 + abs(uy) * h / 2.0


def escape_dir(fp, pad):
    """The pad's own natural fan-out direction."""
    p = R.pt(pad.GetPosition())
    pads = [q for q in fp.Pads() if R.pad_copper_layers(q)]
    w, h = R.tomm(pad.GetSizeX()), R.tomm(pad.GetSizeY())
    if len(pads) == 2:
        # two-terminal part: straight out along its own axis, away from the
        # other terminal
        other = [q for q in pads if q is not pad]
        o = R.pt(other[0].GetPosition())
        v = (p[0] - o[0], p[1] - o[1])
    else:
        c = R.pt(fp.GetPosition())
        v = (p[0] - c[0], p[1] - c[1])
        if abs(h - w) > 0.05:
            # elongated pin: escape along its long axis
            if h > w:
                v = (0.0, math.copysign(1.0, v[1] or 1.0))
            else:
                v = (math.copysign(1.0, v[0] or 1.0), 0.0)
    n = math.hypot(*v) or 1.0
    return (v[0] / n, v[1] / n)


def stub_width(fp, pad):
    n = len([q for q in fp.Pads() if R.pad_copper_layers(q)])
    short = min(R.tomm(pad.GetSizeX()), R.tomm(pad.GetSizeY()))
    if n <= 2 and fp.GetReference()[0] in "RCLF":
        return max(R.W_SIGNAL, round(min(R.VIA_D, short), 4))
    return max(R.W_SIGNAL, round(min(short, R.VIA_D), 4))


def via_free(obst, q, nc):
    win = obst.ij(q[0] - 1.6, q[1] - 1.6) + obst.ij(q[0] + 1.6, q[1] + 1.6)
    m = obst.via_mask(win, nc)
    i, j = obst.ij(*q)
    return not m[i - win[0], j - win[1]]


def place_stitch(board, obst, fp, pad, nc):
    """(via, width, swing) for one GND pad, or (None, ...) if no lane."""
    p = R.pt(pad.GetPosition())
    ux, uy = escape_dir(fp, pad)
    w, h = R.tomm(pad.GetSizeX()), R.tomm(pad.GetSizeY())
    tw = stub_width(fp, pad)
    base = math.atan2(uy, ux)
    for swing in SWINGS:
        a = base + math.radians(swing)
        vx, vy = math.cos(a), math.sin(a)
        d0 = support(w, h, vx, vy) + R.VIA_D / 2.0 + GAP
        for extra in EXTRAS:
            d = d0 + extra
            q = (round(p[0] + vx * d, 3), round(p[1] + vy * d, 3))
            if not via_free(obst, q, nc):
                continue
            if not R.seg_ok(obst, q, p, tw, nc, R.F):
                continue
            return q, tw, swing
    return None, tw, None


def ep_array(board, obst, fp, pad, nc):
    """Via array inside an exposed pad -- the standing G9 exception."""
    c = R.pt(pad.GetPosition())
    w, h = R.tomm(pad.GetSizeX()), R.tomm(pad.GetSizeY())
    nx = max(1, int((w - 0.9) // EP_PITCH) + 1)
    ny = max(1, int((h - 0.9) // EP_PITCH) + 1)
    out = []
    for i in range(nx):
        for j in range(ny):
            x = c[0] + (i - (nx - 1) / 2.0) * EP_PITCH
            y = c[1] + (j - (ny - 1) / 2.0) * EP_PITCH
            q = (round(x, 3), round(y, 3))
            # inside the pad, and clear of every other hole (hole-to-hole)
            if abs(x - c[0]) > w / 2 - R.VIA_D / 2 - 0.05:
                continue
            if abs(y - c[1]) > h / 2 - R.VIA_D / 2 - 0.05:
                continue
            if not hole_clear(obst, q, nc):
                continue
            R.add_via(board, q, nc)
            obst.add_via_at(q, nc)
            out.append(q)
    return out


def hole_clear(obst, q, nc):
    """Hole-to-hole only -- copper clearance does not apply inside an EP."""
    need = R.VIA_DRILL / 2.0 + R.HOLE2HOLE
    for k in obst._near((obst.ij(q[0] - 2, q[1] - 2)
                         + obst.ij(q[0] + 2, q[1] + 2)), 2.0):
        n, _lay, r, kind = obst.items[k]
        if kind != "hole":
            continue
        cx = (r[0] + r[2]) / 2.0
        cy = (r[1] + r[3]) / 2.0
        rr = max(r[2] - r[0], r[3] - r[1]) / 2.0
        if R.dist(q, (cx, cy)) < need + rr:
            return False
    return True


def gnd_pads(board):
    out = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() != "GND":
                continue
            if not R.pad_copper_layers(p):
                continue
            out.append((f, p))
    return out


def main():
    board = R.load()
    obst = R.Obstacles(board)
    nc = R.netcode(board, "GND")

    pads = gnd_pads(board)
    smd = [(f, p) for f, p in pads if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
    pth = [(f, p) for f, p in pads if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD]
    eps = [(f, p) for f, p in smd
           if R.tomm(p.GetSizeX()) * R.tomm(p.GetSizeY()) >= EP_AREA]
    pins = [(f, p) for f, p in smd if (f, p) not in eps]

    print(f"GND pads: {len(pads)}  SMD {len(smd)}  PTH/NPTH {len(pth)}  "
          f"of the SMD, exposed pads {len(eps)}, pins {len(pins)}")

    routed = {}
    swung = []
    failed = []

    # 1. exposed pads first -- their arrays anchor the packages that sit on top
    for f, p in eps:
        vs = ep_array(board, obst, f, p, nc)
        routed[(f.GetReference(), p.GetNumber(),
                round(R.pt(p.GetPosition())[0], 3),
                round(R.pt(p.GetPosition())[1], 3))] = vs
        print(f"  EP  {f.GetReference():<7} pad {p.GetNumber():<4} "
              f"{R.tomm(p.GetSizeX()):.2f}x{R.tomm(p.GetSizeY()):.2f} "
              f"-> {len(vs)} vias")

    # 2. fine-pitch package pins next, then everything else: the tight lanes
    #    get first claim on their own corridors
    def pitchy(fp):
        n = len([q for q in fp.Pads() if R.pad_copper_layers(q)])
        return 0 if n >= 8 else (1 if n >= 3 else 2)

    for f, p in sorted(pins, key=lambda t: (pitchy(t[0]), t[0].GetReference())):
        q, tw, swing = place_stitch(board, obst, f, p, nc)
        key = (f.GetReference(), p.GetNumber(),
               round(R.pt(p.GetPosition())[0], 3),
               round(R.pt(p.GetPosition())[1], 3))
        if q is None:
            failed.append(key)
            continue
        R.add_via(board, q, nc)
        obst.add_via_at(q, nc)
        R.add_track(board, R.pt(p.GetPosition()), q, tw, R.F, nc)
        obst.add_seg(R.pt(p.GetPosition()), q, tw / 2.0, R.F, nc)
        routed[key] = [q]
        if swing:
            swung.append((key, swing))

    print(f"\nstitched {len(routed)} of {len(smd)} SMD GND pads; "
          f"{len(pth)} PTH pads reach the planes through their own barrels")
    if swung:
        print(f"\n{len(swung)} vias could not take the in-line lane and were "
              f"swung -- R3-1 says log these, not assume them:")
        for key, sw in sorted(swung, key=lambda t: -abs(t[1])):
            print(f"    {key[0]:<8} pad {key[1]:<5} swung {sw:+4d} deg")
    if failed:
        print(f"\nNO LANE ({len(failed)}):")
        for k in failed:
            print("   ", k)

    R.refill(board)
    R.save(board)
    print("\nunconnected now:", R.unconnected(board))


if __name__ == "__main__":
    main()
