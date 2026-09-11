#!/usr/bin/env python3
"""Round 4 placement — grow the board, then give the fine-pitch rings room.

The captain granted full placement authority to reach zero unconnected, and
the evidence names the moves rather than taste doing it.  Four packages carry
65 of the 85 open-net pads -- `U1001` (35), `U1101` (16), `U1002` (10),
`U501` (4) -- and every one of them is walled by copper in its own fan-out
band.  `U1001` has 27 parts within 6 mm, ten of them touching.

R2b.4 is why this is a placement problem and not a routing one: at 0.5 mm
pitch a 0.6 mm via cannot be placed for every pin, so a third of each ring has
to escape *radially on the outer layer* into open board -- and there is no open
board to escape into.  Widening the ring is the fix that no routing order can
substitute for.

Two levels, in this order:

1. **Grow the outline.**  Footprint bounding boxes already cover 61% of the
   210x130 board, 86% in the motor block and 85% along the actuator edge.  The
   captain ruled at setup that size is unimportant on this dev board, and
   growing a congested region beats heroics.  210x130 -> 250x165.
2. **Evict from the bands what does not have to be there.**  A decoupling
   capacitor must stay beside its own pin (G1b, and the loop doctrine), and a
   crystal must stay tight to its oscillator pins -- those never move here.  A
   **test point** has no such claim: it must be probe-reachable, which the whole
   board is.  Eighteen of them sit inside the four fan-out bands, each with a
   pad and a ground via in a lane a pin needs.

The board file is the master: this mutates it and never regenerates it.
"""
import argparse
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import route_lib as R  # noqa: E402

OLD = (30.0, 30.0, 240.0, 160.0)
NEW = (30.0, 30.0, 280.0, 195.0)
CORNER = 2.0            # outline corner radius (setup: R2, no sharp corners)
HOLE_IN = 6.0           # M3 NPTH centres, in from each corner


def grow_outline(board):
    """Redraw Edge_Cuts as the new rounded rectangle."""
    old = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    x0, y0, x1, y1 = NEW
    r = CORNER
    for d in old:
        board.Remove(d)
    def line(a, b):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetStart(pcbnew.VECTOR2I(R.mm(a[0]), R.mm(a[1])))
        s.SetEnd(pcbnew.VECTOR2I(R.mm(b[0]), R.mm(b[1])))
        s.SetWidth(R.mm(0.1))
        board.Add(s)
    def arc(centre, start, end):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetCenter(pcbnew.VECTOR2I(R.mm(centre[0]), R.mm(centre[1])))
        s.SetStart(pcbnew.VECTOR2I(R.mm(start[0]), R.mm(start[1])))
        s.SetEnd(pcbnew.VECTOR2I(R.mm(end[0]), R.mm(end[1])))
        s.SetWidth(R.mm(0.1))
        board.Add(s)
    line((x0 + r, y0), (x1 - r, y0))
    line((x1, y0 + r), (x1, y1 - r))
    line((x1 - r, y1), (x0 + r, y1))
    line((x0, y1 - r), (x0, y0 + r))
    arc((x0 + r, y0 + r), (x0, y0 + r), (x0 + r, y0))
    arc((x1 - r, y0 + r), (x1 - r, y0), (x1, y0 + r))
    arc((x1 - r, y1 - r), (x1, y1 - r), (x1 - r, y1))
    arc((x0 + r, y1 - r), (x0 + r, y1), (x0, y1 - r))
    return len(old)


def grow_zones(board):
    """Stretch each pour to the new outline, proportionally.

    The two GND planes span the whole board and simply follow it.  The +3V3
    pour is inset (R2.3) and keeps its inset by scaling about the fixed
    north-west corner.
    """
    sx = (NEW[2] - NEW[0]) / (OLD[2] - OLD[0])
    sy = (NEW[3] - NEW[1]) / (OLD[3] - OLD[1])
    done = []
    for z in board.Zones():
        out = z.Outline()
        for i in range(out.TotalVertices()):
            p = out.CVertex(i)
            x, y = R.tomm(p.x), R.tomm(p.y)
            nx = NEW[0] + (x - OLD[0]) * sx
            ny = NEW[1] + (y - OLD[1]) * sy
            out.SetVertex(i, pcbnew.VECTOR2I(R.mm(nx), R.mm(ny)))
        done.append(z.GetNetname())
    return done


def move_holes(board):
    """M3 NPTH back to 6 mm in from each new corner."""
    x0, y0, x1, y1 = NEW
    want = {"H1": (x0 + HOLE_IN, y0 + HOLE_IN), "H2": (x1 - HOLE_IN, y0 + HOLE_IN),
            "H3": (x1 - HOLE_IN, y1 - HOLE_IN), "H4": (x0 + HOLE_IN, y1 - HOLE_IN)}
    moved = []
    for f in board.GetFootprints():
        ref = f.GetReference()
        if ref in want:
            old = R.pt(f.GetPosition())
            f.SetPosition(pcbnew.VECTOR2I(R.mm(want[ref][0]), R.mm(want[ref][1])))
            moved.append((ref, old, want[ref]))
    return moved


BLOCK = {2: "power_entry_24v", 3: "power_rails", 5: "loadcell_afe",
         6: "linear_encoder", 7: "temp_sense", 8: "nvm_calibration",
         9: "ui_io", 10: "mcu", 11: "motor_drive"}


def block_of(ref):
    """The schematic block a refdes belongs to -- 100 apart, per AGENTS.md."""
    digits = "".join(c for c in ref if c.isdigit())
    if not digits:
        return None
    return int(digits) // 100 or None


def spread(board):
    """Translate each block rigidly so the blocks share out the new area.

    Rigidly is the whole point.  Scaling part positions individually would
    stretch every decoupler link, every Kelvin tap and every crystal stub by
    the scale factor -- the house rules are about those distances, so they must
    come through untouched.  So each block's *centroid* is scaled about the
    fixed north-west corner and the whole block is translated by that delta:
    the gaps between blocks grow, the geometry inside each block does not
    change at all.

    The edge plan rides along for free.  An actuator-edge connector scales to
    the new actuator edge and a bench-edge one barely moves, because the bench
    edge is the fixed corner's own edge.
    """
    sx = (NEW[2] - NEW[0]) / (OLD[2] - OLD[0])
    sy = (NEW[3] - NEW[1]) / (OLD[3] - OLD[1])
    groups = {}
    for f in board.GetFootprints():
        ref = f.GetReference()
        if ref.startswith("H"):
            continue                    # mounting holes are placed explicitly
        blk = block_of(ref)
        if blk is None:
            continue
        groups.setdefault(blk, []).append(f)
    rows = []
    for blk, fps in sorted(groups.items()):
        xs = [R.pt(f.GetPosition())[0] for f in fps]
        ys = [R.pt(f.GetPosition())[1] for f in fps]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        nx = NEW[0] + (cx - OLD[0]) * sx
        ny = NEW[1] + (cy - OLD[1]) * sy
        # Snap the delta, not the parts.  The 0.25 mm placement grid is
        # asserted programmatically (check_place), and an unsnapped delta puts
        # every part in the block off it -- 408 of them.  Snapping the delta
        # keeps the block rigid AND on grid, because every part was on grid
        # before it moved; snapping each part afterwards would not, it would
        # nudge parts relative to one another and break the very adjacencies
        # this translation exists to preserve.
        dx = round((nx - cx) / 0.25) * 0.25
        dy = round((ny - cy) / 0.25) * 0.25
        for f in fps:
            q = R.pt(f.GetPosition())
            f.SetPosition(pcbnew.VECTOR2I(R.mm(q[0] + dx), R.mm(q[1] + dy)))
        rows.append((blk, BLOCK.get(blk, "?"), len(fps), cx, cy, dx, dy))
    return rows


FINE = ("U1001", "U1101", "U1002", "U501")
BAND = 8.0              # mm of ring a fine-pitch package needs to itself
STEP = 0.25


def _box(f):
    bb = f.GetBoundingBox()
    return (R.tomm(bb.GetLeft()), R.tomm(bb.GetTop()),
            R.tomm(bb.GetRight()), R.tomm(bb.GetBottom()))


def _gap(a, c):
    dx = max(a[0] - c[2], 0.0, c[0] - a[2])
    dy = max(a[1] - c[3], 0.0, c[1] - a[3])
    return math.hypot(dx, dy)


def _pinned(f, host_nets):
    """True for a part whose distance to its host IS the design.

    A decoupling capacitor sharing a supply net with the package it sits
    beside is the loop (G1b and the loop doctrine); a crystal and its load
    caps are the oscillator.  Neither may be pushed out of the ring to buy
    routing room -- that trades a rule for a convenience.  Everything else in
    the band is there by habit, and a test point most of all: it has to be
    probe-reachable, which the whole board is.
    """
    ref = f.GetReference()
    if ref.startswith("J"):
        # Connectors are pinned by the edge plan, which is a standing captain
        # ruling.  Without this, settle() cheerfully relocated the SMA off the
        # board edge to resolve an overlap with the ESD diode placed beside it.
        return True
    if ref.startswith("Y"):
        return True
    nets = {p.GetNetname() for p in f.Pads() if p.GetNetname()}
    if ref.startswith("C") and (nets & host_nets) - {"GND"}:
        return True
    if ref.startswith("C") and any(n.startswith("Net-(Y") for n in nets):
        return True
    return False


def relieve(board):
    """Push what may move out of the fine-pitch bands, then part the overlaps."""
    fps = list(board.GetFootprints())
    hosts = {r: f for f in fps for r in FINE if f.GetReference() == r}
    rows = []
    for ref, host in hosts.items():
        hb = _box(host)
        hc = ((hb[0] + hb[2]) / 2.0, (hb[1] + hb[3]) / 2.0)
        host_nets = {p.GetNetname() for p in host.Pads() if p.GetNetname()}
        for f in fps:
            if f.GetReference() == ref or f.GetReference().startswith("H"):
                continue
            if _gap(hb, _box(f)) >= BAND or _pinned(f, host_nets):
                continue
            q = R.pt(f.GetPosition())
            u = (q[0] - hc[0], q[1] - hc[1])
            L = math.hypot(*u) or 1.0
            u = (u[0] / L, u[1] / L)
            k = STEP
            while k <= 24.0:
                cand = (round((q[0] + u[0] * k) / STEP) * STEP,
                        round((q[1] + u[1] * k) / STEP) * STEP)
                f.SetPosition(pcbnew.VECTOR2I(R.mm(cand[0]), R.mm(cand[1])))
                if _gap(hb, _box(f)) >= BAND:
                    break
                k += STEP
            rows.append((f.GetReference(), ref, q,
                         R.pt(f.GetPosition())))
    return rows


def part_overlaps(board, rounds=40):
    """Nudge courtyard overlaps apart, never moving a pinned part."""
    import place_lib as P
    moved = []
    for _ in range(rounds):
        bad = P.overlaps(board)
        if not bad:
            break
        for row in bad:
            a, c = row[0], row[1]
            fa = {f.GetReference(): f for f in board.GetFootprints()}
            A, C = fa.get(a), fa.get(c)
            if A is None or C is None:
                continue
            na = {p.GetNetname() for p in A.Pads() if p.GetNetname()}
            nc = {p.GetNetname() for p in C.Pads() if p.GetNetname()}
            mover = C if not _pinned(C, na) else (A if not _pinned(A, nc) else C)
            other = A if mover is C else C
            p, o = R.pt(mover.GetPosition()), R.pt(other.GetPosition())
            u = (p[0] - o[0], p[1] - o[1])
            L = math.hypot(*u) or 1.0
            u = (u[0] / L, u[1] / L)
            cand = (round((p[0] + u[0] * STEP * 2) / STEP) * STEP,
                    round((p[1] + u[1] * STEP * 2) / STEP) * STEP)
            mover.SetPosition(pcbnew.VECTOR2I(R.mm(cand[0]), R.mm(cand[1])))
            moved.append((mover.GetReference(), other.GetReference()))
    return moved


def settle(board, rounds=60):
    """Resolve every courtyard overlap by relocating, not by nudging.

    Nudging 0.5 mm per round oscillates whenever a part is squeezed between
    two others -- 535 nudges left more overlaps than it started with.  A part
    that is in the way needs somewhere to go, so this searches a widening ring
    for a spot that is on grid, inside the board, clear of the M3 keep-outs and
    clear of every courtyard, and puts it there.

    Test points move first and furthest: a probe pad's only placement claim is
    that a probe can reach it.
    """
    import place_lib as P
    x0, y0 = P.BX + 3.0, P.BY + 3.0
    x1, y1 = P.BX + P.BW - 3.0, P.BY + P.BH - 3.0
    moved = []
    for _ in range(rounds):
        bad = P.overlaps(board)
        if not bad:
            break
        fps = {f.GetReference(): f for f in board.GetFootprints()}
        a, c = bad[0][0], bad[0][1]
        A, C = fps.get(a), fps.get(c)
        if A is None or C is None:
            break
        na = {p.GetNetname() for p in A.Pads() if p.GetNetname()}
        nc = {p.GetNetname() for p in C.Pads() if p.GetNetname()}
        if a.startswith("TP"):
            mover = A
        elif c.startswith("TP"):
            mover = C
        elif not _pinned(C, na):
            mover = C
        else:
            mover = A
        home = R.pt(mover.GetPosition())
        placed = False
        for ring in [r * 0.5 for r in range(2, 60)]:
            for ang in range(0, 360, 15):
                t = math.radians(ang)
                cand = (round((home[0] + ring * math.cos(t)) / STEP) * STEP,
                        round((home[1] + ring * math.sin(t)) / STEP) * STEP)
                if not (x0 <= cand[0] <= x1 and y0 <= cand[1] <= y1):
                    continue
                mover.SetPosition(pcbnew.VECTOR2I(R.mm(cand[0]), R.mm(cand[1])))
                bb = P.courtyard_bbox(mover)
                if bb is None:
                    placed = True
                    break
                if any(math.hypot(max(bb[0] - mx, 0, mx - bb[2]),
                                  max(bb[1] - my, 0, my - bb[3])) < P.MOUNT_KEEP
                       for mx, my in P.MOUNTS):
                    continue
                hits = [r for r in P.overlaps(board)
                        if mover.GetReference() in (r[0], r[1])]
                if not hits:
                    placed = True
                    break
            if placed:
                break
        if not placed:
            mover.SetPosition(pcbnew.VECTOR2I(R.mm(home[0]), R.mm(home[1])))
            break
        moved.append((mover.GetReference(), home, R.pt(mover.GetPosition())))
    return moved


# The named fixes: (refdes, x, y, rot or None, why).  Each is either a
# captain-named round-1 finding handed over as placement, or a defect this
# round's own block spread introduced.
FIXES = [
    # C323/C324 are the MCU's +3V3A decouplers and sat 18/21 mm from the pin
    # they serve, in the power_rails block.  U1001.21 is at (118.0, 77.75) and
    # the package's south edge is y = 79.0, so they go just below it.
    # (The sheet-membership question that put them in power_rails is a
    # SCHEMATIC matter and is flagged, not touched.)
    ("C323", 115.0, 82.0, 0.0, "+3V3A decoupler to U1001.21"),
    ("C324", 118.5, 82.0, 0.0, "+3V3A decoupler to U1001.21"),
    # C1112 walls in its own net: 68% of Net-(U1101-CPH)'s pocket boundary is
    # C1112's OTHER pad (R2b.6).  U1101 pins 2 and 3 are at x = 213.94, one
    # 0.5 mm below the other; rotating the cap 90 puts its pads on separate
    # rows facing them instead of one behind the other.
    ("C1112", 217.75, 142.5, 90.0, "rotate off its own net's escape"),
    # ESD as close as physically possible to the source pin (skill): D903
    # clamps SYNC where it enters at the SMA J902 (90.0, 36.25), and sat
    # 8.8 mm away.
    ("D903", 90.0, 39.75, 0.0, "ESD onto the SMA it protects"),
]


def apply_fixes(board):
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    rows = []
    for ref, x, y, rot, why in FIXES:
        f = fps.get(ref)
        if f is None:
            continue
        old = R.pt(f.GetPosition())
        oldrot = f.GetOrientationDegrees()
        f.SetPosition(pcbnew.VECTOR2I(R.mm(x), R.mm(y)))
        if rot is not None:
            f.SetOrientationDegrees(rot)
        rows.append((ref, old, oldrot, (x, y), rot, why))
    return rows


BENCH_EDGE = ("J1001", "J1002", "J1003", "J902", "J201")
ACT_EDGE = ("J501", "J601", "J602", "J701", "J702", "J903",
            "J1101", "J1102", "J1103")


def restore_edges(board, before):
    """Put the edge connectors back on their edges after the block spread.

    The spread scales a block's centroid about the fixed north-west corner,
    which is right for the interior and wrong for the periphery: it dragged
    every connector inboard, the SMA by 18 mm.  The edge plan is a standing
    captain ruling, so each connector recovers the exact offset from its own
    edge that it had before this round -- read from the pre-round-4 board
    rather than retyped, so it cannot drift.
    """
    old = pcbnew.LoadBoard(before)
    was = {f.GetReference(): R.pt(f.GetPosition()) for f in old.GetFootprints()}
    rows = []
    for f in board.GetFootprints():
        ref = f.GetReference()
        if ref not in BENCH_EDGE and ref not in ACT_EDGE:
            continue
        if ref not in was:
            continue
        q = R.pt(f.GetPosition())
        if ref in BENCH_EDGE:
            ny = was[ref][1]                       # same offset from y = 30
        else:
            ny = NEW[3] - (OLD[3] - was[ref][1])   # same offset from the far edge
        ny = round(ny / STEP) * STEP
        f.SetPosition(pcbnew.VECTOR2I(R.mm(q[0]), R.mm(ny)))
        rows.append((ref, q[1], ny))
    return rows


def mcu_core(board, radius=6.0):
    """U1001 and the parts pinned to it -- its own decouplers and satellites.

    Connectors are excluded deliberately: the edge plan is a standing ruling,
    and every block SWAP that would cut haul cost (nvm<->motor and
    ui_io<->motor at 17%, lin_enc<->mcu at 14%) moves a block whose connectors
    are pinned to an edge.  Moving the core alone is the version of that lever
    which does not break the plan.
    """
    u = board.FindFootprintByReference("U1001")
    UB = _box(u)
    unets = {p.GetNetname() for p in u.Pads() if p.GetNetname()}
    core = [u]
    for f in board.GetFootprints():
        r = f.GetReference()
        if r == "U1001" or r.startswith(("H", "J")):
            continue
        nets = {p.GetNetname() for p in f.Pads() if p.GetNetname()}
        if _gap(UB, _box(f)) <= radius and (nets & unets):
            core.append(f)
    return core


def move_mcu(board, dx, dy):
    """Slide the MCU core along the vector toward the motor block.

    25 nets cross 97.7 mm between the MCU and the motor drive -- by far the
    dominant traffic on the board, and the cost the fill has been paying all
    along.  Ring crowding, which round 4's first two attempts chased, is a
    symptom of that.
    """
    core = mcu_core(board)
    dx = round(dx / STEP) * STEP
    dy = round(dy / STEP) * STEP
    for f in core:
        q = R.pt(f.GetPosition())
        f.SetPosition(pcbnew.VECTOR2I(R.mm(q[0] + dx), R.mm(q[1] + dy)))
    return [f.GetReference() for f in core], dx, dy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--mcu", metavar="DX,DY",
                    help="slide the MCU core toward the motor block")
    ap.add_argument("--edges", metavar="BEFORE_BOARD",
                    help="restore edge connectors to their original edge "
                         "offsets, read from the pre-round-4 board")
    ap.add_argument("--fixes", action="store_true",
                    help="apply the named placement fixes")
    ap.add_argument("--settle", action="store_true",
                    help="relocate parts until no courtyard overlaps remain")
    ap.add_argument("--relieve", action="store_true",
                    help="clear the fine-pitch bands and part the overlaps")
    ap.add_argument("--spread", action="store_true",
                    help="also translate each block to the grown board")
    a = ap.parse_args()
    board = R.load()
    print(f"outline {OLD} -> {NEW} "
          f"({NEW[2]-NEW[0]:.0f} x {NEW[3]-NEW[1]:.0f} mm, was "
          f"{OLD[2]-OLD[0]:.0f} x {OLD[3]-OLD[1]:.0f})")
    if not a.yes:
        print("dry run -- pass --yes")
        return 0
    if a.mcu:
        dx, dy = (float(v) for v in a.mcu.split(","))
        refs, dx, dy = move_mcu(board, dx, dy)
        print(f"\n  MCU core: {len(refs)} parts by ({dx:+.2f},{dy:+.2f})")
        print("   ", ", ".join(sorted(refs)))
        R.refill(board)
        R.save(board)
        board = R.load()
        print(f"   unconnected {R.unconnected(board)}")
        return 0

    if a.edges:
        rows = restore_edges(board, a.edges)
        print(f"\n  {len(rows)} edge connectors returned to their edges:")
        for ref, oy, ny in rows:
            print(f"   {ref:<8} y {oy:7.2f} -> {ny:7.2f}")
        R.refill(board)
        R.save(board)
        board = R.load()
        print(f"   unconnected {R.unconnected(board)}")
        return 0

    if a.fixes:
        for ref, o, orot, n, rot, why in apply_fixes(board):
            print(f"   {ref:<8} ({o[0]:6.1f},{o[1]:6.1f})@{orot:5.1f} -> "
                  f"({n[0]:6.1f},{n[1]:6.1f})@{rot if rot is not None else orot:5.1f}  {why}")
        R.refill(board)
        R.save(board)
        board = R.load()
        print(f"   unconnected {R.unconnected(board)}")
        return 0

    if a.settle:
        rows = settle(board)
        print(f"\n  {len(rows)} parts relocated to clear courtyard overlaps:")
        for ref, o, n in rows:
            print(f"   {ref:<8} ({o[0]:6.1f},{o[1]:6.1f}) -> ({n[0]:6.1f},{n[1]:6.1f})")
        R.refill(board)
        R.save(board)
        board = R.load()
        print(f"   unconnected {R.unconnected(board)}")
        return 0

    if a.relieve:
        rows = relieve(board)
        print(f"\n  {len(rows)} parts pushed out of the fine-pitch bands:")
        for ref, host, old, new in rows:
            print(f"   {ref:<8} out of {host:<7} "
                  f"({old[0]:6.1f},{old[1]:6.1f}) -> ({new[0]:6.1f},{new[1]:6.1f})")
        nud = part_overlaps(board)
        print(f"   {len(nud)} nudges to part courtyard overlaps")
        R.refill(board)
        R.save(board)
        board = R.load()
        print(f"   unconnected {R.unconnected(board)}")
        return 0

    if a.spread:
        print("\n  block                 parts    centroid        delta")
        for blk, name, n, cx, cy, dx, dy in spread(board):
            print(f"   {blk:2d} {name:<18} {n:4d}  "
                  f"({cx:6.1f},{cy:6.1f})  ({dx:+6.2f},{dy:+6.2f})")
        R.refill(board)
        R.save(board)
        board = R.load()
        print(f"   unconnected {R.unconnected(board)}")
        return 0
    n = grow_outline(board)
    print(f"   redrew Edge_Cuts ({n} shapes replaced by 8)")
    print(f"   stretched zones: {grow_zones(board)}")
    for ref, old, new in move_holes(board):
        print(f"   {ref} {old} -> {new}")
    R.refill(board)
    R.save(board)
    board = R.load()
    bb = board.GetBoardEdgesBoundingBox()
    print(f"   board now {R.tomm(bb.GetRight())-R.tomm(bb.GetLeft()):.1f} x "
          f"{R.tomm(bb.GetBottom())-R.tomm(bb.GetTop()):.1f} mm; "
          f"unconnected {R.unconnected(board)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
