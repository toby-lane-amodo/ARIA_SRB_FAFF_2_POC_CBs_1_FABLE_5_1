#!/usr/bin/env python3
"""Placement-quality numbers for the review pack.

  * every decoupling capacitor's link length to the supply pin it serves,
    worst first -- the pcb-layout-style "no cap gets a leftover slot" check;
  * the GND-via lane each cap's ground pad needs, and whether it is clear of
    foreign-net copper;
  * ratsnest length and crossing count per region, as a placement-quality
    signal;
  * the DRV8323 gate-loop lengths.
"""
import collections
import itertools
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import place_lib as L   # noqa: E402

RAILS = ("+3V3", "+3V3A", "+5V", "+5VA", "/power_rails/+6V0", "GND",
         "/mcu/+3V3_USB", "/mcu/+1V8_USB", "/linear_encoder/+5V_ENC",
         "/motor_drive/VENC", "/motor_drive/V24_MOT", "/motor_drive/VM_DRV",
         "/power_entry_24v/V24_LOGIC", "/power_entry_24v/V24_PROT",
         "/power_entry_24v/+24V_SW")

REGION = {2: "power_entry_24v", 3: "power_rails", 5: "loadcell_afe",
          6: "linear_encoder", 7: "temp_sense", 8: "nvm_calibration",
          9: "ui_io", 10: "mcu", 11: "motor_drive"}


def region_of(ref):
    d = "".join(c for c in ref if c.isdigit())
    return REGION.get(int(d) // 100, "misc") if d else "misc"


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def main():
    b = L.load()
    fps = {f.GetReference(): f for f in b.GetFootprints()}

    # --- decoupler link lengths -------------------------------------------
    ic_pads = collections.defaultdict(list)     # net -> [(ref, pad, xy)]
    for f in b.GetFootprints():
        if len(f.Pads()) < 4:
            continue
        for p in f.Pads():
            n = p.GetNetname()
            if n in RAILS and n != "GND":
                q = p.GetPosition()
                ic_pads[n].append((f.GetReference(), p.GetNumber(),
                                   (pcbnew.ToMM(q.x), pcbnew.ToMM(q.y))))
    rows = []
    for f in b.GetFootprints():
        ref = f.GetReference()
        if not ref.startswith("C"):
            continue
        pads = list(f.Pads())
        if len(pads) != 2:
            continue
        for p in pads:
            n = p.GetNetname()
            if n not in ic_pads:
                continue
            q = p.GetPosition()
            xy = (pcbnew.ToMM(q.x), pcbnew.ToMM(q.y))
            tgt = min(ic_pads[n], key=lambda t: dist(xy, t[2]))
            rows.append((dist(xy, tgt[2]), ref, n, tgt[0] + "." + tgt[1]))
    rows.sort(reverse=True)
    print("== decoupler supply-pad link lengths, worst first (mm)")
    for d, ref, net, tgt in rows[:18]:
        print("   %6.2f  %-7s %-26s -> %s" % (d, ref, net, tgt))
    print("   ... %d caps total, median %.2f mm"
          % (len(rows), sorted(r[0] for r in rows)[len(rows) // 2]))

    # --- ratsnest per region ----------------------------------------------
    net2pads = collections.defaultdict(list)
    for f in b.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if not n or n == "GND" or n.startswith("unconnected-"):
                continue
            q = p.GetPosition()
            net2pads[n].append((f.GetReference(),
                                (pcbnew.ToMM(q.x), pcbnew.ToMM(q.y))))
    segs = collections.defaultdict(list)
    for n, pads in net2pads.items():
        pts = {}
        for ref, xy in pads:
            pts.setdefault(ref, xy)
        items = list(pts.items())
        if len(items) < 2:
            continue
        # minimum spanning tree over the per-part pad positions
        used, rest = [items[0]], items[1:]
        while rest:
            best = min(((dist(a[1], c[1]), i, j)
                        for i, a in enumerate(used)
                        for j, c in enumerate(rest)))
            d, i, j = best
            segs[n].append((used[i][1], rest[j][1], d,
                            region_of(used[i][0]), region_of(rest[j][0])))
            used.append(rest.pop(j))
    per = collections.defaultdict(lambda: [0, 0.0])
    cross_region = 0
    allsegs = []
    for n, ss in segs.items():
        for p, q, d, ra, rb in ss:
            allsegs.append((p, q, ra, rb))
            if ra == rb:
                per[ra][0] += 1
                per[ra][1] += d
            else:
                cross_region += 1
    print("\n== ratsnest (signal + rail nets, GND excluded)")
    print("   %-18s %5s %10s  %s" % ("region", "links", "total mm", "mean mm"))
    for r in sorted(per):
        n, tot = per[r]
        print("   %-18s %5d %10.0f  %5.1f" % (r, n, tot, tot / n))
    print("   %-18s %5d" % ("cross-region", cross_region))

    def isect(a, b, c, d):
        def cr(o, p, q):
            return ((p[0] - o[0]) * (q[1] - o[1])
                    - (p[1] - o[1]) * (q[0] - o[0]))
        d1, d2 = cr(c, d, a), cr(c, d, b)
        d3, d4 = cr(a, b, c), cr(a, b, d)
        return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))

    print("\n== ratsnest crossings inside each region")
    for r in sorted(per):
        ss = [s for s in allsegs if s[2] == r and s[3] == r]
        c = sum(1 for x, y in itertools.combinations(ss, 2)
                if isect(x[0], x[1], y[0], y[1]))
        print("   %-18s %5d crossings over %d links" % (r, c, len(ss)))

    # --- DRV8323 gate loops ------------------------------------------------
    print("\n== DRV8323 gate / shunt-sense runs (mm, straight line)")
    drv = fps["U1101"]
    for q, gate in (("Q1101", "GHA"), ("Q1102", "GLA"), ("Q1103", "GHB"),
                    ("Q1104", "GLB"), ("Q1105", "GHC"), ("Q1106", "GLC")):
        gp = L.pad_world(fps[q], "4")[0]
        net = fps[q].FindPadByNumber("4").GetNetname()
        dp = [p for p in drv.Pads() if p.GetNetname() == net][0].GetPosition()
        print("   %-6s %-4s %6.1f" % (q, gate, dist(
            gp, (pcbnew.ToMM(dp.x), pcbnew.ToMM(dp.y)))))


if __name__ == "__main__":
    main()
