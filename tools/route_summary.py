#!/usr/bin/env python3
"""One-screen state of the routed board, for the review pack and the log.

Everything a routing round has to quote in one place: copper by layer, the via
population by net class, what is still open and where, and -- given a DRC JSON
-- the violation counts split into the known library residuals and everything
else.  The point is that the numbers in the decisions file are produced, not
transcribed.

    AMODO_KICAD_LIB=... kicad-cli pcb drc --severity-all --format json \\
        -o /tmp/drc.json hardware/kicad/faff2_cbs1/faff2_cbs1.kicad_pcb
    python3 tools/route_summary.py --drc /tmp/drc.json
"""
import argparse
import collections
import json
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402

# Board setup S8: the four library residual classes, not routing defects.
RESIDUAL = {"items_not_allowed", "lib_footprint_mismatch", "annular_width",
            "lib_footprint_issues"}
# In-progress classes that a finished round must not contain.
INPROGRESS = {"track_dangling", "via_dangling"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drc", help="path to a kicad-cli DRC json")
    a = ap.parse_args()

    board = R.load()
    seg = [t for t in board.GetTracks() if not isinstance(t, pcbnew.PCB_VIA)]
    via = [t for t in board.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]

    print("== copper")
    by = collections.defaultdict(float)
    for t in seg:
        by[board.GetLayerName(t.GetLayer())] += R.tomm(t.GetLength())
    for k in sorted(by):
        print(f"   {k:<8} {by[k]:8.1f} mm")
    print(f"   {len(seg)} segments, {len(via)} vias, "
          f"{len(list(board.Zones()))} zones")

    print("\n== vias by net class")
    cls = collections.Counter(R.net_class(v.GetNetname()) if v.GetNetname()
                              else "GND" for v in via)
    gnd = sum(1 for v in via if v.GetNetname() == "GND")
    for k, n in cls.most_common():
        print(f"   {k:<10} {n}")
    print(f"   of which GND: {gnd}")

    print("\n== still open")
    seen, split = set(), []
    for f in board.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if not n or n in seen or n.startswith("unconnected-"):
                continue
            seen.add(n)
            if len(R.pad_nodes(board, n)) < 2:
                continue
            if not R.net_is_whole(board, n, plane=(n == "GND")):
                split.append(n)
    for n in sorted(split):
        isl = R.net_islands(board, n)
        pads = ["+".join(sorted(x[1] for x in g if x[0] == "pad"))
                for g in isl]
        print(f"   {n:<34} {len(isl)} islands  {pads}")
    print(f"   {len(split)} nets still split; "
          f"unconnected {R.unconnected(board)}")

    if a.drc:
        d = json.load(open(a.drc))
        c = collections.Counter(v["type"] for v in d["violations"])
        res = sum(n for k, n in c.items() if k in RESIDUAL)
        prog = sum(n for k, n in c.items() if k in INPROGRESS)
        real = sum(n for k, n in c.items()
                   if k not in RESIDUAL and k not in INPROGRESS)
        print("\n== DRC")
        for k, n in c.most_common():
            tag = ("library residual" if k in RESIDUAL
                   else "in progress" if k in INPROGRESS else "REAL")
            print(f"   {k:<26} {n:4}  {tag}")
        print(f"   residual {res}, in-progress {prog}, real {real}; "
              f"unconnected {len(d['unconnected_items'])}, "
              f"parity {len(d['schematic_parity'])}")


if __name__ == "__main__":
    main()
