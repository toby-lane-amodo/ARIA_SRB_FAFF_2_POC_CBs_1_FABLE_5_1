#!/usr/bin/env python3
"""Routing step 3 -- every GND connection, one via per pad.

House rule (pcb-layout-style, VanClock 2026-07-30, reaffirmed 2026-07-31):
**every GND pin always gets its OWN GND via -- never one via shared between
two ground pads.**  A shared via puts its series inductance inside both
capacitors' current loops, which partly defeats paralleling them at all
(Bogatin, *Practical PCB Design*, p.344).

Per pad: short trace -> via -> plane.  R/C pads take the trace at via-OD
width; ICs and other small pads take the widest trace that does not exceed the
pad width.  PTH GND pads need no copper at all -- their barrels already reach
both planes.

**No via-in-pad.**  The only in-pad arrays on this board are the seven IC
exposed pads in EP_PADS, which is the standing client-ruled G9 exception.
Every other big GND land -- the shunts, the DC-link cans, the TVS, the
common-mode choke, the FPC shells -- gets a *fan of vias beside the pad*,
sized by the pad's edge length, so nothing wicks solder into a barrel.

**A stitch via sits in its pin's OWN escape lane** -- straight in-line exit,
the pin's natural fan-out direction (R3-1).  Where in-line is impossible the
via is swung and the deviation is logged for review.  Where no lane exists at
all and the package carries its own GND exposed pad, the pin ties straight
into that EP (client ruling R-C3-1, 2026-09-02) -- the EP is that IC's own
return, so this is not the shared-via case.

`tools/route_check.py --gnd` is the completeness proof.
"""
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402

# The only pads that may carry vias inside them -- IC exposed thermal pads.
EP_PADS = {("U301", "TP"), ("U304", "TP"), ("U302", "9"), ("U303", "9"),
           ("U501", "33"), ("U1002", "33"), ("U1101", "41")}
EP_PITCH = 1.30
FAN_PITCH = 1.10        # spacing of a fan of vias along a big pad's edge
# GND lands that carry real current: via count from the 1.0 A/via budget
# (docs/decisions/actuator-pcb-setup.md S3), not from the pad's edge length.
FORCE_VIAS = {("L201", "3"): 3,        # 24 V input return through the choke
              ("D201", "1"): 3,        # TVS clamp return, surge
              ("R1125", "2"): 4, ("R1126", "2"): 4, ("R1127", "2"): 4,
              ("C1101", "2"): 4, ("C1102", "2"): 4, ("C204", "2"): 4}
BIG = 1.60              # mm -- a pad edge this long gets a fan, not one via
GAP = 0.05
SWINGS = [0, 10, -10, 20, -20, 30, -30, 42, -42, 55, -55, 70, -70,
          85, -85, 100, -100, 120, -120, 145, -145, 180]
# Controlled-impedance corridors held clear of ground stitching.  The house
# step order puts ground before signals, so without this a stitch via lands in
# the middle of the USB pair's only run (it did: 148.61,51.50 and
# 150.00,44.90) and the pair has nowhere legal to go.  These live in the
# obstacle model only -- step 5 rebuilds it and routes them for real.
RESERVED_CORRIDORS = [
    # USB 2.0 HS pair: J1001 A6/A7 -> D1001 -> U1002 pins 18/19.  Without it a
    # stitch via lands in the middle of the pair's only run (it did:
    # 148.61,51.50 and 150.00,44.90) and the pair has nowhere legal to go.
    ([(150.00, 38.60), (150.00, 42.30)], 0.42),
    # across D1001 the pair opens to 1.6 mm pitch so the ESD device's GND pin
    # can take its own via between the two lines -- reserve the wider band
    ([(150.00, 43.60), (150.00, 46.20)], 1.05),
    ([(149.60, 46.20), (149.00, 47.60), (149.00, 55.20)], 0.42),
]
# Stitch vias that belong to a controlled-impedance geometry and are placed
# with it in step 5 instead: D1001's GND pin sits *between* the two USB data
# lines, so its via and the pair's local spread have to be drawn together.
DEFER = {("D1001", "2")}
EXTRAS = [0.0, 0.12, 0.25, 0.40, 0.55, 0.75, 1.00, 1.30, 1.70, 2.20]


def support(w, h, ux, uy):
    return abs(ux) * w / 2.0 + abs(uy) * h / 2.0


def groups_of(board):
    """SMD GND pads, merged where they physically overlap (one land)."""
    pads = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() != "GND" or not R.pad_copper_layers(p):
                continue
            if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            pads.append((f, p))
    used = [False] * len(pads)
    out = []
    for i, (f, p) in enumerate(pads):
        if used[i]:
            continue
        grp = [(f, p)]
        used[i] = True
        again = True
        while again:
            again = False
            for j, (g, q) in enumerate(pads):
                if used[j] or g is not f:
                    continue
                a = R.pad_bbox(q)
                for _fx, m in grp:
                    b = R.pad_bbox(m)
                    if (a[0] <= b[2] and b[0] <= a[2]
                            and a[1] <= b[3] and b[1] <= a[3]):
                        grp.append((g, q))
                        used[j] = True
                        again = True
                        break
        out.append(grp)
    return out


def grp_bbox(grp):
    bs = [R.pad_bbox(p) for _f, p in grp]
    return (min(b[0] for b in bs), min(b[1] for b in bs),
            max(b[2] for b in bs), max(b[3] for b in bs))


def escape_dir(fp, bb):
    """The land's own natural fan-out direction."""
    cx, cy = (bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0
    pads = [q for q in fp.Pads() if R.pad_copper_layers(q)]
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    if len(pads) == 2:
        other = [q for q in pads if q.GetNetname() != "GND"]
        if other:
            o = R.pt(other[0].GetPosition())
            v = (cx - o[0], cy - o[1])
            n = math.hypot(*v) or 1.0
            return (v[0] / n, v[1] / n)
    c = R.pt(fp.GetPosition())
    v = (cx - c[0], cy - c[1])
    if abs(h - w) > 0.05:
        if h > w:
            v = (0.0, math.copysign(1.0, v[1] or 1.0))
        else:
            v = (math.copysign(1.0, v[0] or 1.0), 0.0)
    n = math.hypot(*v) or 1.0
    return (v[0] / n, v[1] / n)


def stub_width(fp, bb):
    short = min(bb[2] - bb[0], bb[3] - bb[1])
    return max(R.W_SIGNAL, round(min(short, R.VIA_D), 4))


def via_free(obst, q, nc):
    win = obst.ij(q[0] - 1.8, q[1] - 1.8) + obst.ij(q[0] + 1.8, q[1] + 1.8)
    m = obst.via_mask(win, nc)
    i, j = obst.ij(*q)
    return not m[i - win[0], j - win[1]]


def hole_clear(obst, q):
    need = R.VIA_DRILL / 2.0 + R.HOLE2HOLE
    for k in obst._near((obst.ij(q[0] - 2, q[1] - 2)
                         + obst.ij(q[0] + 2, q[1] + 2)), 2.0):
        _n, _lay, r, kind = obst.items[k]
        if kind != "hole":
            continue
        cx, cy = (r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0
        rr = max(r[2] - r[0], r[3] - r[1]) / 2.0
        if R.dist(q, (cx, cy)) < need + rr:
            return False
    return True


def place_one(board, obst, fp, bb, nc, anchor, tw):
    """One stitch via for a land, from `anchor` outward in its own lane."""
    ux, uy = escape_dir(fp, bb)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    cx, cy = (bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0
    base = math.atan2(uy, ux)
    for swing in SWINGS:
        a = base + math.radians(swing)
        vx, vy = math.cos(a), math.sin(a)
        d0 = support(w, h, vx, vy) + R.VIA_D / 2.0 + GAP
        for extra in EXTRAS:
            q = (round(cx + vx * (d0 + extra), 3),
                 round(cy + vy * (d0 + extra), 3))
            if not via_free(obst, q, nc):
                continue
            if not R.seg_ok(obst, q, anchor, tw, nc, R.F):
                continue
            return q, swing
    return None, None


def fan(board, obst, fp, bb, nc, tw, want=None):
    """A block of vias beside a big land's escape edge.

    Columns run along the edge, rows step outward, until `want` vias are down
    -- so a land whose edge is too short for its current budget gets a second
    row rather than a single under-rated via.
    """
    ux, uy = escape_dir(fp, bb)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    cx, cy = (bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0
    px, py = -uy, ux                      # along the escape edge
    edge = abs(px) * w + abs(py) * h
    ncols = max(1, min(4, int(edge // FAN_PITCH)))
    want = want or ncols
    d0 = support(w, h, ux, uy) + R.VIA_D / 2.0 + GAP
    out = []
    row = 0
    while len(out) < want and row < 4:
        depth = d0 + row * (R.VIA_D + R.CLEAR + 0.15)
        for k in range(ncols):
            if len(out) >= want:
                break
            off = (k - (ncols - 1) / 2.0) * FAN_PITCH
            anchor = (min(max(round(cx + px * off, 3), bb[0] + 0.1), bb[2] - 0.1),
                      min(max(round(cy + py * off, 3), bb[1] + 0.1), bb[3] - 0.1))
            placed = False
            for extra in (0.0, 0.15, 0.30, 0.50):
                q = (round(cx + px * off + ux * (depth + extra), 3),
                     round(cy + py * off + uy * (depth + extra), 3))
                if not via_free(obst, q, nc) or not hole_clear(obst, q):
                    continue
                if not R.seg_ok(obst, q, anchor, tw, nc, R.F):
                    continue
                R.add_via(board, q, nc)
                obst.add_via_at(q, nc)
                R.add_track(board, anchor, q, tw, R.F, nc)
                obst.add_seg(anchor, q, tw / 2.0, R.F, nc)
                out.append(q)
                placed = True
                break
            if not placed:
                continue
        row += 1
    return out


def place_far(board, obst, maze, fp, bb, nc, anchor, tw):
    """Last resort before an EP tie: find a free via slot in the outward
    half-plane within a few mm and maze-route the stub to it on F.Cu."""
    ux, uy = escape_dir(fp, bb)
    cx, cy = (bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0
    cands = []
    for r in [x * 0.25 for x in range(4, 33)]:
        for a in range(-170, 171, 10):
            ang = math.atan2(uy, ux) + math.radians(a)
            q = (round(cx + math.cos(ang) * r, 3), round(cy + math.sin(ang) * r, 3))
            cands.append((r, q))
    seen = set()
    for r, q in cands:
        if q in seen:
            continue
        seen.add(q)
        if not via_free(obst, q, nc) or not hole_clear(obst, q):
            continue
        res = maze.route(nc, [anchor], [q], tw, layers=(R.F,),
                         start_rects={R.F: [(anchor[0] - 0.03, anchor[1] - 0.03,
                                             anchor[0] + 0.03, anchor[1] + 0.03)]},
                         goal_rects={R.F: [(q[0] - 0.03, q[1] - 0.03,
                                            q[0] + 0.03, q[1] + 0.03)]},
                         margin=5)
        if res is None:
            continue
        R.add_via(board, q, nc)
        obst.add_via_at(q, nc)
        R.emit_result(board, obst, res, tw, nc)
        return q, round(r, 2)
    return None, None


def ep_array(board, obst, pad, nc):
    c = R.pt(pad.GetPosition())
    w, h = R.tomm(pad.GetSizeX()), R.tomm(pad.GetSizeY())
    nx = max(1, int((w - R.VIA_D - 0.2) // EP_PITCH) + 1)
    ny = max(1, int((h - R.VIA_D - 0.2) // EP_PITCH) + 1)
    out = []
    for i in range(nx):
        for j in range(ny):
            q = (round(c[0] + (i - (nx - 1) / 2.0) * EP_PITCH, 3),
                 round(c[1] + (j - (ny - 1) / 2.0) * EP_PITCH, 3))
            if abs(q[0] - c[0]) > w / 2 - R.VIA_D / 2 - 0.05:
                continue
            if abs(q[1] - c[1]) > h / 2 - R.VIA_D / 2 - 0.05:
                continue
            if not hole_clear(obst, q):
                continue
            R.add_via(board, q, nc)
            obst.add_via_at(q, nc)
            out.append(q)
    return out


def ep_of(board, fp):
    for ref, num in EP_PADS:
        if ref != fp.GetReference():
            continue
        for p in fp.Pads():
            if p.GetNumber() == num:
                return p
    return None


def main():
    board = R.load()
    if any(isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == "GND"
           for t in board.GetTracks()):
        raise SystemExit("route3: GND vias already present -- runs once")
    obst = R.Obstacles(board)
    obst.reserve_pin_escapes(board)
    for pts, hw in RESERVED_CORRIDORS:
        obst.reserve(pts, hw)
    maze = R.Maze(obst)
    nc = R.netcode(board, "GND")

    grps = groups_of(board)
    n_smd = sum(len(g) for g in grps)
    n_pth = sum(1 for f in board.GetFootprints() for p in f.Pads()
                if p.GetNetname() == "GND" and R.pad_copper_layers(p)
                and p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD)
    print(f"GND: {n_smd} SMD pads in {len(grps)} lands, "
          f"{n_pth} PTH pads (barrels reach the planes)")

    eps, fans, singles = [], [], []
    for g in grps:
        f = g[0][0]
        key = (f.GetReference(), g[0][1].GetNumber())
        if key in EP_PADS:
            eps.append(g)
            continue
        bb = grp_bbox(g)
        if max(bb[2] - bb[0], bb[3] - bb[1]) >= BIG:
            fans.append(g)
        else:
            singles.append(g)

    done = {}
    swung, nolane, tied, far = [], [], [], []

    for g in eps:
        f, p = g[0]
        vs = ep_array(board, obst, p, nc)
        done[id(g)] = vs
        print(f"  EP   {f.GetReference():<7} pad {p.GetNumber():<4} "
              f"{R.tomm(p.GetSizeX()):.2f}x{R.tomm(p.GetSizeY()):.2f} "
              f"-> {len(vs)} in-pad vias (G9 exception)")

    for g in fans:
        f = g[0][0]
        bb = grp_bbox(g)
        tw = stub_width(f, bb)
        vs = fan(board, obst, f, bb, nc, tw,
                 FORCE_VIAS.get((f.GetReference(), g[0][1].GetNumber())))
        done[id(g)] = vs
        print(f"  FAN  {f.GetReference():<7} pad {g[0][1].GetNumber():<4} "
              f"{bb[2]-bb[0]:.2f}x{bb[3]-bb[1]:.2f} -> {len(vs)} vias beside")

    def pitchy(fp):
        n = len([q for q in fp.Pads() if R.pad_copper_layers(q)])
        return 0 if n >= 8 else (1 if n >= 3 else 2)

    for g in sorted(singles, key=lambda t: (pitchy(t[0][0]),
                                            t[0][0].GetReference())):
        f, p = g[0]
        if (f.GetReference(), p.GetNumber()) in DEFER:
            done[id(g)] = ["deferred to step 5"]
            continue
        bb = grp_bbox(g)
        tw = stub_width(f, bb)
        anchor = R.pt(p.GetPosition())
        q, swing = place_one(board, obst, f, bb, nc, anchor, tw)
        key = (f.GetReference(), p.GetNumber())
        if q is None:
            q, rr = place_far(board, obst, maze, f, bb, nc, anchor, tw)
            if q is not None:
                done[id(g)] = [q]
                far.append((key, rr))
                continue
        if q is None:
            ep = ep_of(board, f)
            if ep is not None:
                # R-C3-1: tie straight into the IC's own exposed pad
                e = R.pt(ep.GetPosition())
                eb = R.pad_bbox(ep)
                tgt = (min(max(anchor[0], eb[0] + 0.2), eb[2] - 0.2),
                       min(max(anchor[1], eb[1] + 0.2), eb[3] - 0.2))
                R.add_track(board, anchor, tgt, tw, R.F, nc)
                obst.add_seg(anchor, tgt, tw / 2.0, R.F, nc)
                done[id(g)] = ["EP-tie"]
                tied.append(key)
                continue
            nolane.append(key)
            continue
        R.add_via(board, q, nc)
        obst.add_via_at(q, nc)
        R.add_track(board, anchor, q, tw, R.F, nc)
        obst.add_seg(anchor, q, tw / 2.0, R.F, nc)
        done[id(g)] = [q]
        if swing:
            swung.append((key, swing))

    covered = sum(len(g) for g in grps if done.get(id(g)))
    print(f"\n{covered} of {n_smd} SMD GND pads connected, in "
          f"{len(done)} of {len(grps)} lands")
    if tied:
        print(f"\n{len(tied)} pins had no via lane and tie into their own "
              f"IC exposed pad (client ruling R-C3-1):")
        for k in tied:
            print(f"    {k[0]:<8} pad {k[1]}")
    if swung:
        print(f"\n{len(swung)} vias could not take the in-line lane and were "
              f"swung -- R3-1 says log these, not assume them:")
        for key, sw in sorted(swung, key=lambda t: -abs(t[1])):
            print(f"    {key[0]:<8} pad {key[1]:<5} swung {sw:+4d} deg")
    if far:
        print(f"\n{len(far)} pins had no in-line lane at all and take a "
              f"maze-routed stub to a nearby slot:")
        for k, rr in far:
            print(f"    {k[0]:<8} pad {k[1]:<5} via {rr:.2f} mm out")
    if nolane:
        print(f"\nNO LANE ({len(nolane)}) -- needs the engineer:")
        for k in nolane:
            print("   ", k)

    R.refill(board)
    R.save(board)
    print("\nunconnected now:", R.unconnected(board))


if __name__ == "__main__":
    main()
