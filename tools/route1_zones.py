#!/usr/bin/env python3
"""Routing step 1 -- establish the two internal GND planes.

House process (pcb-layout-style): step 1 is the ground planes, before any
track.  Full GND fill on both internal layers, 0.15 mm minimum width, 0.15 mm
clearance, 0.25 mm corner fillet, islands always removed, pad connections with
thermal reliefs -- reliefs are acceptable here only because these are internal
layers.  G1/G10: the planes are unbroken and never split.

Idempotent: re-running replaces nothing, it only fills what is already there.
"""
import sys

import pcbnew

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from place_lib import PCB, mm, save  # noqa: E402
import route_lib as R  # noqa: E402

MIN_W = 0.15
CLEARANCE = 0.15
FILLET = 0.25
TR_GAP = 0.50
TR_SPOKE = 0.50


def make_zone(board, layer, code):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNetCode(code)
    z.SetAssignedPriority(0)
    z.SetLocalClearance(mm(CLEARANCE))
    z.SetMinThickness(mm(MIN_W))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(mm(TR_GAP))
    z.SetThermalReliefSpokeWidth(mm(TR_SPOKE))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetCornerSmoothingType(pcbnew.ZONE_SETTINGS.SMOOTHING_FILLET)
    z.SetCornerRadius(mm(FILLET))
    z.SetIsFilled(False)
    # Outline follows the board rectangle; KiCad clips the fill back to the
    # 0.30 mm copper-to-edge constraint, including the R2 corners.
    pts = pcbnew.VECTOR_VECTOR2I()
    for x, y in ((R.BX, R.BY), (R.BX + R.BW, R.BY),
                 (R.BX + R.BW, R.BY + R.BH), (R.BX, R.BY + R.BH)):
        pts.append(R.P(x, y))
    z.AddPolygon(pts)
    board.Add(z)
    return z


def main():
    board = pcbnew.LoadBoard(PCB)
    gnd = R.netcode(board, "GND")
    have = {z.GetLayer() for z in board.Zones()}
    made = []
    for layer, name in ((R.IN1, "In1.Cu"), (R.IN2, "In2.Cu")):
        if layer in have:
            print(f"  {name}: zone already present")
            continue
        make_zone(board, layer, gnd)
        made.append(name)
    R.refill(board)
    for z in board.Zones():
        a = z.GetFilledArea()
        print(f"  {board.GetLayerName(z.GetLayer())}: net={z.GetNetname()} "
              f"filled={pcbnew.ToMM(pcbnew.ToMM(a)):.1f} mm^2 "
              f"outlines={z.GetFilledPolysList(z.GetLayer()).OutlineCount()}")
    save(board)
    print("created:", made or "none (already existed)")


if __name__ == "__main__":
    main()
