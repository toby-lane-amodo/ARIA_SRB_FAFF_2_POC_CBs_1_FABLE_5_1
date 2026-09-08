#!/usr/bin/env python3
"""Shared helpers for the placement scripts.

Board geometry, the .kicad_pro guard around SaveBoard, and the sweeps the
pcb-layout-style skill asks for (real courtyards, edge margin, keep-outs,
0.25 mm grid, decoupler-to-pin link lengths).

KiCad 9 only -- AGENTS.md.
"""
import os
import shutil

import pcbnew

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRJ = os.path.join(REPO, "hardware", "kicad", "faff2_cbs1")
PCB = os.path.join(PRJ, "faff2_cbs1.kicad_pcb")
PRO = os.path.join(PRJ, "faff2_cbs1.kicad_pro")

# Board outline on the A2 page (docs/decisions/actuator-pcb-setup.md S4).
BX, BY, BW, BH = 30.0, 30.0, 210.0, 130.0
EDGE_KEEP = 0.30           # copper-to-board-edge, DRC constraint
MOUNTS = [(36.0, 36.0), (234.0, 36.0), (234.0, 154.0), (36.0, 154.0)]
MOUNT_KEEP = 2.80          # the M3 footprint's own 5.5 mm keepout, radius
SNAP = 0.25                # house soft placement grid


def mm(v):
    return pcbnew.FromMM(v)


def load():
    b = pcbnew.LoadBoard(PCB)
    for f in b.GetFootprints():
        f.BuildCourtyardCaches()
    return b


def save(b):
    """SaveBoard rewrites the sibling .kicad_pro wholesale -- snapshot it."""
    with open(PRO, "rb") as fh:
        keep = fh.read()
    b.Save(PCB)
    with open(PRO, "wb") as fh:
        fh.write(keep)


def by_ref(b):
    return {f.GetReference(): f for f in b.GetFootprints()}


def place(fp, x, y, rot):
    fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    fp.SetOrientationDegrees(rot)


def courtyard_bbox(fp):
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    if not cy.OutlineCount():
        cy = fp.GetCourtyard(pcbnew.B_CrtYd)
    if not cy.OutlineCount():
        return None
    r = cy.BBox()
    return (pcbnew.ToMM(r.GetLeft()), pcbnew.ToMM(r.GetTop()),
            pcbnew.ToMM(r.GetRight()), pcbnew.ToMM(r.GetBottom()))


def courtyard_poly(fp):
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    if not cy.OutlineCount():
        cy = fp.GetCourtyard(pcbnew.B_CrtYd)
    return cy if cy.OutlineCount() else None


def pad_world(fp, number):
    """[(x, y)] in mm for every pad carrying this pad number."""
    out = []
    for p in fp.Pads():
        if p.GetNumber() == number:
            q = p.GetPosition()
            out.append((pcbnew.ToMM(q.x), pcbnew.ToMM(q.y)))
    return out


def pads_on_net(fp, net):
    out = []
    for p in fp.Pads():
        if p.GetNetname() == net:
            q = p.GetPosition()
            out.append((pcbnew.ToMM(q.x), pcbnew.ToMM(q.y)))
    return out


def overlaps(b, skip=()):
    """Real-courtyard overlap pairs.  Mounting holes included deliberately."""
    fps = [f for f in b.GetFootprints() if f.GetReference() not in skip]
    boxes = {}
    polys = {}
    for f in fps:
        bb = courtyard_bbox(f)
        if bb is None:
            continue
        boxes[f.GetReference()] = bb
        polys[f.GetReference()] = courtyard_poly(f)
    refs = sorted(boxes)
    bad = []
    for i, a in enumerate(refs):
        ax0, ay0, ax1, ay1 = boxes[a]
        for bq in refs[i + 1:]:
            bx0, by0, bx1, by1 = boxes[bq]
            if ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0:
                continue
            pa = pcbnew.SHAPE_POLY_SET(polys[a])
            pa.BooleanIntersection(polys[bq])
            if pa.OutlineCount():
                r = pa.BBox()
                bad.append((a, bq, round(pcbnew.ToMM(r.GetWidth()), 3),
                            round(pcbnew.ToMM(r.GetHeight()), 3)))
    return bad


def edge_problems(b):
    """Courtyards leaving the board, or biting an M3 keep-out."""
    out = []
    for f in b.GetFootprints():
        bb = courtyard_bbox(f)
        if bb is None:
            continue
        ref = f.GetReference()
        x0, y0, x1, y1 = bb
        if (x0 < BX + EDGE_KEEP or y0 < BY + EDGE_KEEP
                or x1 > BX + BW - EDGE_KEEP or y1 > BY + BH - EDGE_KEEP):
            out.append((ref, "off-board", (round(x0, 2), round(y0, 2),
                                           round(x1, 2), round(y1, 2))))
        if ref.startswith("H"):
            continue
        for (mx, my) in MOUNTS:
            dx = max(x0 - mx, 0.0, mx - x1)
            dy = max(y0 - my, 0.0, my - y1)
            if (dx * dx + dy * dy) ** 0.5 < MOUNT_KEEP:
                out.append((ref, "M3 keepout", (round(mx, 1), round(my, 1))))
    return out


def off_grid(b, skip=()):
    out = []
    for f in b.GetFootprints():
        ref = f.GetReference()
        if ref in skip:
            continue
        x = pcbnew.ToMM(f.GetPosition().x)
        y = pcbnew.ToMM(f.GetPosition().y)
        for v in (x, y):
            if abs(round(v / SNAP) * SNAP - v) > 1e-4:
                out.append((ref, round(x, 4), round(y, 4)))
                break
    return out
