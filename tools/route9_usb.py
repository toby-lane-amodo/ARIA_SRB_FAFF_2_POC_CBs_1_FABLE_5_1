#!/usr/bin/env python3
"""Routing step 9 -- the USB 2.0 HS pair, drawn by hand.

Step 5 let the maze router loose on `/mcu/USB_DM` and `/mcu/USB_DP`, and it
did what a maze router does when one net has two pads in a 0.5 mm row: it
treated them as interchangeable and ran DM along the pad row *through* A6,
which is a DP pad.  That is where the nine `shorting_items`, the two
`tracks_crossing` and the two `solder_mask_bridge` violations came from.

A differential pair is not a connectivity problem, so the pair is not asked of
a router here.  DM and DP are explicit polylines, mirror images about
x = 150.0 wherever they run together, so the match is by construction rather
than by measurement.  Everything else in the block -- the two B-row
duplicates, both CC lines, VBUS -- is left to the router, which now has the
pair down as immovable copper to route around.  That split is the point: hand
work where the geometry is the specification, the router where only
connectivity is.

Three facts about the geometry set the shape:

* **J1001 interleaves the rows.**  Along x the pads read B6(DP) A7(DM) A6(DP)
  B7(DM) at 0.5 mm pitch, so each row's duplicate sits on the far side of the
  other net's lane and the two ties must cross.  The A row carries the pair;
  the B-row pads are tied across on B.Cu.  0.5 mm pitch will not take a 0.6 mm
  via, so nothing is fanned inside the pad field, and nothing at all is routed
  under the connector body on either layer -- the shell lands there and
  soldermask is not an insulator under a metal shell.
* **D1001 pin 5 is VBUS and its only escape is due north**, straight between
  the two halves of the pair.  So the pair opens to 1.4 mm pitch across the
  corridor: the channel is then 1.10 mm and the VBUS via drops in with
  0.25 mm each side.  The bulge is symmetric, so it costs no skew.
* **D1001's pad 2 GND stitch owns the lane the pair wants south of the
  device.**  Pad 2 sits between the two signal pads and its only escape is
  straight south, so the pair parts around it -- DM west, DP east -- and
  converges again below.  That is the one place the two are not coupled, and
  it is what the 0.41 mm of skew is spent on.

`kicad-cli pcb drc` is the arbiter, as always; run it after this.
"""
import json
import math
import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import route_lib as R  # noqa: E402

W = 0.30                     # USB_HS class: 0.30 / 0.20 gap = 90.6 ohm

RIP_BOX = (140.0, 30.0, 160.0, 60.0)
RIP_NETS = ["/mcu/USB_DM", "/mcu/USB_DP", "/mcu/USB_CC1", "/mcu/USB_CC2",
            "/mcu/USB_VBUS"]

DM = [                       # J1001.A7 -> D1001.6
    (149.75, 39.18), (149.75, 40.50), (149.30, 40.95), (149.30, 41.90),
    (149.50, 42.10), (149.50, 42.195),
]
DP = [                       # J1001.A6 -> D1001.4   (mirror about x = 150.0)
    (150.25, 39.18), (150.25, 40.50), (150.70, 40.95), (150.70, 41.90),
    (150.50, 42.10), (150.50, 42.195),
]
# D1001 is four independent clamp cells in one SOT666 and the schematic ties
# two of them to each line, so the netlist wants pads 6 and 1 (and 4 and 3)
# joined in copper.  The link runs straight down the pad's own x through the
# 0.62 mm gap between the pad rows, 0.20 mm clear of the pad-2 ground land
# either side -- also the shortest path the line can take through the part.
DM_BR = [(149.50, 42.195), (149.50, 43.805)]
DP_BR = [(150.50, 42.195), (150.50, 43.805)]
DM_S = [                     # D1001.1 -> U1002.19, west of the pad-2 stitch
    (149.50, 43.805), (149.25, 44.30), (149.25, 45.50), (148.75, 46.00),
    (148.75, 54.45),
]
DP_S = [                     # D1001.3 -> U1002.18, east of it, then across
    (150.50, 43.805), (150.75, 44.30), (150.75, 45.50), (149.25, 47.00),
    (149.25, 54.45),
]
# VBUS out of D1001 pin 5.  Its via sits in the channel the pair's bulge
# opens; y is set by the via-in-pad rule, not by taste -- the drill has to
# clear the pad's own edge at y = 41.70 by more than its radius.
VBUS = [(150.00, 42.195), (150.00, 41.35)]
VBUS_VIA = (150.00, 41.35)

# The two B-row ties.  Neither pad can fan in its own lane -- 0.5 mm pitch
# will not take a 0.6 mm via -- so each descends its flank, fanning as it
# goes, and drops to B.Cu where the lane is wide enough.  B6 goes west past
# A8 (an unconnected SBU pin: its lane is dead and free to borrow); B7 goes
# east, and CC1 fans one further step east ahead of it so the two never
# share a depth.  Both land back on their own half of the pair *north* of
# D1001.  DP lands north of the device; DM's band would have to cross both
# VBUS's B.Cu spine and DP's own band to do the same, so it lands 1.6 mm past
# pad 1 instead -- still 0.2 mm from a clamp cell of its own and nine
# millimetres of trace ahead of the PHY, so the clamp is still in front of
# everything it protects.
TIE_DP_F = [(149.25, 39.18), (149.25, 39.95), (148.65, 40.55), (148.65, 42.20)]
TIE_DM_F = [(150.75, 39.18), (150.75, 40.15), (151.45, 40.85), (151.45, 45.00)]
# The two ties span overlapping x, so on one layer their bands would have to
# cross.  They do not: DM's crossing runs *north* of its landing vias and
# DP's *south* of its own, which nests the two instead of interleaving them.
TIE_DM_B = [(151.45, 45.00), (151.45, 45.90), (149.25, 45.90), (149.25, 45.45)]
TIE_DP_B = [(148.65, 42.20), (148.65, 39.90), (150.70, 39.90), (150.70, 41.05)]
TIE_VIAS = {"/mcu/USB_DP": [(148.65, 42.20), (150.70, 41.05)],
            "/mcu/USB_DM": [(151.45, 45.00), (149.25, 45.45)]}
# CC1 has to reach R1010, 8 mm west, from the eastmost lane of the group.  It
# fans one step east of B7's descent and crosses on B.Cu; the router finishes
# it.  Hand-drawn only as far as its via, because that fan is what keeps B7's
# lane open.
CC1_F = [(151.25, 39.18), (151.25, 39.95), (151.75, 40.45), (152.10, 40.80),
         (152.10, 41.60)]
CC1_VIA = (152.10, 41.60)
# VBUS at the A4/B9 end fans east of CC1's via on its way to R1008, clear of
# the corner ground stitch at (153.2, 40.105) on the way past.
VBUS_E = [(152.40, 39.18), (152.40, 40.30), (152.80, 40.70), (152.80, 42.10)]
VBUS_W = [(147.60, 39.18), (147.60, 41.20)]
# The two connector VBUS pads meet pin 5's via on B.Cu, south of D1001 and
# clear of both tie bands.  R1008 is the router's last hop.
VBUS_B = [(147.60, 41.20), (147.60, 43.30), (152.80, 43.30), (152.80, 42.10)]
VBUS_B5 = [(150.00, 41.35), (150.00, 43.30)]
VBUS_VIAS = [(147.60, 41.20), (152.80, 42.10)]
# CC2 has to reach R1011 past VBUS's via and the DP tie's, and the gap
# between the two is 0.60 mm -- five microns short of what a 0.30 mm trace
# needs.  At its own class width (0.1524, Default) it walks through with
# 0.22 mm each side, which is what the class is for.
W_CC = 0.1524
CC2_F = [(148.25, 39.18), (148.25, 41.75), (147.75, 42.25), (146.60, 42.25),
         (146.60, 43.825), (145.50, 43.825)]

# Nothing is routed under the connector: the shell lands on the board there
# and soldermask is not an insulator under a metal shell.  The maze router
# found its way under it twice before this reservation went in.
BODY = (145.0, 31.5, 155.0, 38.40)

REST = ("/mcu/USB_DM", "/mcu/USB_DP", "/mcu/USB_VBUS",
        "/mcu/USB_CC2", "/mcu/USB_CC1")


def plen(pts):
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


CHILD = '''
import json, sys
sys.path.insert(0, {here!r})
import pcbnew, route_lib as R
box = {box}; nets = set({nets})
b = pcbnew.LoadBoard(R.PCB)
def ins(p):
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]
doomed = []
for t in b.GetTracks():
    if t.GetNetname() not in nets:
        continue
    if isinstance(t, pcbnew.PCB_VIA):
        if ins(R.pt(t.GetPosition())):
            doomed.append(t)
    elif ins(R.pt(t.GetStart())) and ins(R.pt(t.GetEnd())):
        doomed.append(t)
for t in doomed:
    b.Remove(t)
print(json.dumps({{"removed": len(doomed)}}))
R.refill(b)
R.save(b)
'''


def rip():
    src = CHILD.format(here=HERE, box=json.dumps(list(RIP_BOX)),
                       nets=json.dumps(RIP_NETS))
    out = subprocess.run([sys.executable, "-c", src], capture_output=True,
                         text=True)
    if out.returncode != 0:
        print(out.stdout)
        print(out.stderr, file=sys.stderr)
        raise SystemExit("rip failed")
    for line in out.stdout.splitlines():
        if line.strip().startswith("{"):
            return json.loads(line)["removed"]
    return 0


def draw(board, net, pts, width, layer):
    R.polyline(board, pts, width, layer, R.netcode(board, net))


def main():
    print(f"ripped {rip()} items of {RIP_NETS}")
    board = R.load()

    for net, pts in (("/mcu/USB_DM", DM), ("/mcu/USB_DP", DP),
                     ("/mcu/USB_DM", DM_BR), ("/mcu/USB_DP", DP_BR),
                     ("/mcu/USB_DM", DM_S), ("/mcu/USB_DP", DP_S),
                     ("/mcu/USB_VBUS", VBUS), ("/mcu/USB_VBUS", VBUS_E),
                     ("/mcu/USB_VBUS", VBUS_W),
                     ("/mcu/USB_CC1", CC1_F),
                     ("/mcu/USB_DP", TIE_DP_F), ("/mcu/USB_DM", TIE_DM_F)):
        draw(board, net, pts, W, R.F)
    draw(board, "/mcu/USB_DP", TIE_DP_B, W, R.B)
    draw(board, "/mcu/USB_DM", TIE_DM_B, W, R.B)
    draw(board, "/mcu/USB_VBUS", VBUS_B, W, R.B)
    draw(board, "/mcu/USB_VBUS", VBUS_B5, W, R.B)
    for q in [VBUS_VIA] + VBUS_VIAS:
        R.add_via(board, q, R.netcode(board, "/mcu/USB_VBUS"))
    R.add_via(board, CC1_VIA, R.netcode(board, "/mcu/USB_CC1"))
    draw(board, "/mcu/USB_CC2", CC2_F, W_CC, R.F)
    for net, vs in TIE_VIAS.items():
        nc = R.netcode(board, net)
        for q in vs:
            R.add_via(board, q, nc)
    R.refill(board)
    R.save(board)

    board = R.load()
    obst = R.Obstacles(board)
    obst.reserve_pin_escapes(board)
    y0, y1 = BODY[1], BODY[3]
    while y0 <= y1:
        obst.reserve([(BODY[0], y0), (BODY[2], y0)], 0.15)
        y0 += 0.25
    maze = R.Maze(obst)
    for net in ("/mcu/USB_VBUS", "/mcu/USB_CC1"):
        f = R.connect_net(board, obst, maze, net, width=R.net_width(net),
                          via_cost=45, margin=24, verbose=False)
        if f:
            print(f"   ! {net} unrouted {sorted(set(f))}")
    R.refill(board)
    R.save(board)

    board = R.load()
    n = (plen(DM) + plen(DM_BR) + plen(DM_S),
         plen(DP) + plen(DP_BR) + plen(DP_S))
    print(f"   DM {n[0]:6.3f} mm   DP {n[1]:6.3f} mm   "
          f"skew {abs(n[0] - n[1]):.3f} mm")
    print("   coupled run 0.30 mm wide / 0.20 mm gap over In1.Cu -> 90.6 ohm")
    for net in REST:
        print(f"   {net:<22} "
              f"{'whole' if R.net_is_whole(board, net) else 'SPLIT'}")
    print("unconnected now:", R.unconnected(board))


if __name__ == "__main__":
    main()
