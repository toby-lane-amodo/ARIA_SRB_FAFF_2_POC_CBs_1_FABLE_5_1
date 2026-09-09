#!/usr/bin/env python3
"""Round 2, step 1 -- restack the board to six layers.

The captain's round-2 ruling: *"If needed, remove all power connections, and
only route signals for now. Then, we can add two additional internal layers
and use these for routing power."*

Arrangement, his words: **SIG / GND / PWR / PWR / GND / SIG**.  The two layers
adjacent to the outer signal layers stay unbroken ground planes, so house G1's
substance is preserved -- every outer-layer signal is still referenced to a
solid plane 0.2104 mm below it -- and the two middle layers become the power
routing layers G1 previously denied.

**Stackup: JLCPCB `JLC06161H-7628`**, their published 6-layer 1.6 mm build at
1 oz outer / 0.5 oz inner, the same copper weights and the same no-surcharge
class as the 4-layer board this replaces.

The choice is not arbitrary among JLC's ten 6-layer options.  `-7628` is the
one whose **outer prepreg is identical to the 4-layer board's**: 7628 glass at
0.2104 mm, Dk 4.40.  Every impedance number already derived and already routed
therefore carries over untouched -- the USB pair stays 0.30 mm on 0.20 mm gap
for 90.6 ohm, the SYNC line stays 0.37 mm for 50 ohm, and the pair drawn in
round 1 does not have to be redrawn.  The alternatives (1080 at 0.0764, 2116
at 0.1164/0.1270, 3313 at 0.0994) would all have moved the reference plane
closer and forced both geometries to narrow.

Source: JLCPCB's own impedance-template data, `templateName JLC06161H-7628`,
1 oz outer / 0.5 oz inner.  Materials are Nan Ya NP-155F throughout, as on the
4-layer.

KiCad 9 only.  The board file is the master: this mutates it.
"""
import os
import re
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402
from place_lib import PCB, save  # noqa: E402

# JLC06161H-7628, top to bottom.  Thicknesses in mm, exactly as published.
CU_OUTER, CU_INNER = 0.035, 0.0152
PREPREG = ("7628", 0.2104, 4.40, 0.02)      # F.Cu->In1, In2->In3, In4->B.Cu
CORE = ("Core", 0.4000, 4.36, 0.02)         # In1->In2 and In3->In4
MASK = 0.01

# (KiCad layer id, name, type, user name).  Copper ids in KiCad 9 are even:
# F=0, B=2, In1=4, In2=6, In3=8, In4=10.
LAYERS = [
    (pcbnew.F_Cu,   "F.Cu",   "mixed", None),
    (pcbnew.In1_Cu, "In1.Cu", "power", "GND Plane L2"),
    (pcbnew.In2_Cu, "In2.Cu", "power", "PWR Plane L3"),
    (pcbnew.In3_Cu, "In3.Cu", "power", "PWR Plane L4"),
    (pcbnew.In4_Cu, "In4.Cu", "power", "GND Plane L5"),
    (pcbnew.B_Cu,   "B.Cu",   "mixed", None),
]

STACKUP = f'''		(stackup
			(layer "F.SilkS"
				(type "Top Silk Screen")
			)
			(layer "F.Paste"
				(type "Top Solder Paste")
			)
			(layer "F.Mask"
				(type "Top Solder Mask")
				(thickness {MASK})
			)
			(layer "F.Cu"
				(type "copper")
				(thickness {CU_OUTER})
			)
			(layer "dielectric 1"
				(type "prepreg")
				(thickness {PREPREG[1]})
				(material "NP-155F {PREPREG[0]}")
				(epsilon_r {PREPREG[2]})
				(loss_tangent {PREPREG[3]})
			)
			(layer "In1.Cu"
				(type "copper")
				(thickness {CU_INNER})
			)
			(layer "dielectric 2"
				(type "core")
				(thickness {CORE[1]})
				(material "NP-155F Core")
				(epsilon_r {CORE[2]})
				(loss_tangent {CORE[3]})
			)
			(layer "In2.Cu"
				(type "copper")
				(thickness {CU_INNER})
			)
			(layer "dielectric 3"
				(type "prepreg")
				(thickness {PREPREG[1]})
				(material "NP-155F {PREPREG[0]}")
				(epsilon_r {PREPREG[2]})
				(loss_tangent {PREPREG[3]})
			)
			(layer "In3.Cu"
				(type "copper")
				(thickness {CU_INNER})
			)
			(layer "dielectric 4"
				(type "core")
				(thickness {CORE[1]})
				(material "NP-155F Core")
				(epsilon_r {CORE[2]})
				(loss_tangent {CORE[3]})
			)
			(layer "In4.Cu"
				(type "copper")
				(thickness {CU_INNER})
			)
			(layer "dielectric 5"
				(type "prepreg")
				(thickness {PREPREG[1]})
				(material "NP-155F {PREPREG[0]}")
				(epsilon_r {PREPREG[2]})
				(loss_tangent {PREPREG[3]})
			)
			(layer "B.Cu"
				(type "copper")
				(thickness {CU_OUTER})
			)
			(layer "B.Mask"
				(type "Bottom Solder Mask")
				(thickness {MASK})
			)
			(layer "B.Paste"
				(type "Bottom Solder Paste")
			)
			(layer "B.SilkS"
				(type "Bottom Silk Screen")
			)
			(copper_finish "ENIG")
			(dielectric_constraints no)
		)'''

THICK = round(4 * CU_INNER + 2 * CU_OUTER + 3 * PREPREG[1] + 2 * CORE[1]
              + 2 * MASK, 4)


def main():
    board = pcbnew.LoadBoard(PCB)
    board.SetCopperLayerCount(6)
    for lid, name, _t, user in LAYERS:
        board.SetLayerName(lid, name)
    # the second ground plane moves from In2 (now a power layer) to In4
    moved = 0
    for z in board.Zones():
        if z.GetNetname() == "GND" and z.GetLayer() == pcbnew.In2_Cu:
            z.SetLayer(pcbnew.In4_Cu)
            moved += 1
    print(f"   ground plane zones moved In2.Cu -> In4.Cu: {moved}")
    save(board)

    # The stackup and the layer roles are file-level: pcbnew rewrites the
    # stackup to defaults on a layer-count change, so it is put back here
    # verbatim, with the anchor asserted.
    s = open(PCB).read()
    new_layers = "\n".join(
        f'\t\t({lid} "{name}" {typ}' + (f' "{user}")' if user else ")")
        for lid, name, typ, user in LAYERS)
    s, n = re.subn(r'\t\(layers\n(?:\t\t\(\d+ "[FB]\.Cu"[^\n]*\n|\t\t\(\d+ "In\d\.Cu"[^\n]*\n)+',
                   "\t(layers\n" + new_layers + "\n", s, count=1)
    assert n == 1, "layer table anchor did not match"
    s, n = re.subn(r"\t\t\(stackup\n.*?\n\t\t\)", STACKUP, s, count=1,
                   flags=re.S)
    assert n == 1, "stackup anchor did not match"
    s, n = re.subn(r"\(thickness [\d.]+\)\n\t\t\(legacy_teardrops",
                   f"(thickness {THICK})\n\t\t(legacy_teardrops", s, count=1)
    assert n == 1, "board thickness anchor did not match"
    open(PCB, "w").write(s)

    board = pcbnew.LoadBoard(PCB)
    print(f"   copper layers: {board.GetCopperLayerCount()}")
    for lid, name, _t, user in LAYERS:
        print(f"      {board.GetLayerName(lid):<8} {user or ''}")
    print(f"   board thickness {THICK} mm "
          f"(JLC06161H-7628 + 2 x {MASK} mm mask)")
    print(f"   outer prepreg {PREPREG[0]} {PREPREG[1]} mm Dk {PREPREG[2]} "
          f"-- unchanged from the 4-layer, so 90 ohm and 50 ohm carry over")
    z = [(zz.GetNetname(), board.GetLayerName(zz.GetLayer()))
         for zz in board.Zones()]
    print(f"   zones: {z}")


if __name__ == "__main__":
    main()
