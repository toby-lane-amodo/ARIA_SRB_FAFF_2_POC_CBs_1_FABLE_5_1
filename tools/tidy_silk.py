#!/usr/bin/env python3
"""Place every visible reference designator clear of copper, of the board
edge, of footprint silkscreen graphics and of its neighbours' text.

Silkscreen hygiene is a placement-round requirement (pcb-layout-style): refs
legible, local to their own part, never over pads or over each other.  A dense
row of 0603s at 3 mm pitch cannot carry a horizontal five-character reference,
so each field is offered candidate slots -- eight directions at two text
angles, at increasing stand-off -- and takes the first that is clear.  Fields
with no clear slot keep their library position and are reported.

Run after tools/gen_pcb_place1.py.  Text positions only; nothing else moves.
"""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import place_lib as L   # noqa: E402

SILK = (pcbnew.F_SilkS, pcbnew.B_SilkS)
PAD_M = pcbnew.FromMM(0.15)
TXT_M = pcbnew.FromMM(0.20)
EDGE_M = pcbnew.FromMM(0.30)


def box(item):
    r = item.GetBoundingBox()
    return (r.GetLeft(), r.GetTop(), r.GetRight(), r.GetBottom())


def hits(a, b, m):
    return not (a[2] + m <= b[0] or b[2] + m <= a[0]
                or a[3] + m <= b[1] or b[3] + m <= a[1])


def main():
    b = L.load()
    fps = list(b.GetFootprints())

    # House floor is 0.8 mm; several Amodo footprints ship 0.7 mm text.  The
    # board is the place to fix that -- the library is read-only.
    floor = pcbnew.FromMM(0.8)
    for f in fps:
        texts = [f.Reference(), f.Value()]
        texts += [g for g in f.GraphicalItems()
                  if isinstance(g, pcbnew.PCB_TEXT)]
        for t in texts:
            if t.GetTextHeight() < floor:
                t.SetTextSize(pcbnew.VECTOR2I(floor, floor))
                t.SetTextThickness(pcbnew.FromMM(0.12))

    pads, silk = [], []
    labels = []
    for f in fps:
        for p in f.Pads():
            pads.append(box(p))
        for g in f.GraphicalItems():
            if g.GetLayer() not in SILK:
                continue
            if isinstance(g, pcbnew.PCB_TEXT) and g.IsVisible():
                labels.append((f, g))
            else:
                silk.append(box(g))
        v = f.Value()
        if v.IsVisible() and v.GetLayer() in SILK:
            silk.append(box(v))

    edges = [box(d) for d in b.GetDrawings()
             if d.GetLayer() == pcbnew.Edge_Cuts]

    plan = []
    subjects = [(f, f.Reference()) for f in fps] + labels
    for f, fld in subjects:
        if not fld.IsVisible() or fld.GetLayer() not in SILK:
            continue
        cy = L.courtyard_bbox(f)
        if cy is None:
            continue
        plan.append((f, fld,
                     pcbnew.FromMM((cy[0] + cy[2]) / 2.0),
                     pcbnew.FromMM((cy[1] + cy[3]) / 2.0),
                     pcbnew.FromMM((cy[2] - cy[0]) / 2.0),
                     pcbnew.FromMM((cy[3] - cy[1]) / 2.0)))
    plan.sort(key=lambda t: -(t[4] * t[5]))

    # 0.8 mm is the house legibility floor; give crowded two-pad parts the
    # floor rather than the 1.0 mm default so a dense row still fits.
    small = pcbnew.FromMM(0.8)
    for f, fld, cx, cy_, hx, hy in plan:
        if len(f.Pads()) <= 3 and hx * hy < pcbnew.FromMM(3.0) ** 2:
            fld.SetTextSize(pcbnew.VECTOR2I(small, small))
            fld.SetTextThickness(pcbnew.FromMM(0.12))

    def run(order):
        taken, stuck = [], []
        for f, fld, cx, cy_, hx, hy in order:
            gap = fld.GetTextHeight() + pcbnew.FromMM(0.25)
            cands = []
            for k in (1, 1.5, 2, 2.5, 3, 4, 5, 6):
                for ang in (0, 900):
                    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0),
                                   (-1, -1), (1, -1), (-1, 1), (1, 1)):
                        cands.append((ang,
                                      cx + dx * (hx + k * gap),
                                      cy_ + dy * (hy + k * gap)))
            keep = (fld.GetTextAngleDegrees(), fld.GetPosition().x,
                    fld.GetPosition().y)
            best = None
            for ang, x, y in cands:
                fld.SetTextAngle(
                    pcbnew.EDA_ANGLE(ang, pcbnew.TENTHS_OF_A_DEGREE_T))
                fld.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                bb = box(fld)
                if any(hits(bb, p, PAD_M) for p in pads):
                    continue
                if any(hits(bb, sk, TXT_M) for sk in silk):
                    continue
                if any(hits(bb, e, EDGE_M) for e in edges):
                    continue
                if any(hits(bb, t, TXT_M) for t in taken):
                    continue
                best = (ang, int(x), int(y), bb)
                break
            if best is None:
                fld.SetTextAngle(pcbnew.EDA_ANGLE(keep[0], pcbnew.DEGREES_T))
                fld.SetPosition(pcbnew.VECTOR2I(keep[1], keep[2]))
                taken.append(box(fld))
                stuck.append(f.GetReference())
                continue
            fld.SetTextAngle(
                pcbnew.EDA_ANGLE(best[0], pcbnew.TENTHS_OF_A_DEGREE_T))
            fld.SetPosition(pcbnew.VECTOR2I(best[1], best[2]))
            taken.append(best[3])
        return stuck

    stuck = run(plan)
    if stuck:                       # give the losers first pick and redo
        first = [t for t in plan if t[0].GetReference() in stuck]
        stuck = run(first + [t for t in plan if t not in first])

    # Whatever the directional candidates cannot seat gets a fine search:
    # a 0.5 mm grid around the part, nearest clear slot wins.
    if stuck:
        placed = []
        for f, fld, cx, cy_, hx, hy in plan:
            if f.GetReference() not in stuck:
                placed.append(box(fld))
        for f, fld, cx, cy_, hx, hy in plan:
            if f.GetReference() not in stuck:
                continue
            step = pcbnew.FromMM(0.5)
            best = None
            for r in range(2, 26):
                for ang in (0, 900):
                    for i in range(-r, r + 1):
                        for j in (-r, r):
                            for x, y in ((cx + i * step, cy_ + j * step),
                                         (cx + j * step, cy_ + i * step)):
                                fld.SetTextAngle(pcbnew.EDA_ANGLE(
                                    ang, pcbnew.TENTHS_OF_A_DEGREE_T))
                                fld.SetPosition(
                                    pcbnew.VECTOR2I(int(x), int(y)))
                                bb = box(fld)
                                if any(hits(bb, p, PAD_M) for p in pads):
                                    continue
                                if any(hits(bb, sk, TXT_M) for sk in silk):
                                    continue
                                if any(hits(bb, e, EDGE_M) for e in edges):
                                    continue
                                if any(hits(bb, t, TXT_M) for t in placed):
                                    continue
                                best = (ang, int(x), int(y), bb)
                                break
                            if best:
                                break
                        if best:
                            break
                    if best:
                        break
                if best:
                    break
            if best:
                fld.SetTextAngle(pcbnew.EDA_ANGLE(
                    best[0], pcbnew.TENTHS_OF_A_DEGREE_T))
                fld.SetPosition(pcbnew.VECTOR2I(best[1], best[2]))
                placed.append(best[3])
                stuck = [r for r in stuck if r != f.GetReference()]
            else:
                placed.append(box(fld))

    L.save(b)
    print("placed %d of %d silk texts; no clear slot for %d: %s"
          % (len(plan) - len(stuck), len(plan), len(stuck), " ".join(stuck)))


if __name__ == "__main__":
    main()
