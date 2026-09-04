#!/usr/bin/env python3
"""Find rows of parallel parts whose ground flags do not share one height.

The captain's round-4 rule: parallel components share ONE GND-flag height.
`C1113`/`C1114` are the good case, level; `C1101`..`C1104` are the bad one, four
flags on four different heights, which reads as a staircase.

A "row" here is deliberately conservative: two or more two-terminal parts whose
bodies sit at the same y, whose upper pins are on the same net, and whose lower
pins each reach a GND symbol. That is exactly what a reviewer sees as parallel.

    python3 tools/gnd_rows.py [netlist]        # report
"""
import re
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sch_geom as G
from netlist_nodes import node_sets

D = "hardware/kicad/faff2_cbs1/"
RUN_GAP = 25.4      # mm: parts further apart than this are not one visual row
SHEETS = ["power_entry_24v", "power_rails", "loadcell_afe", "linear_encoder",
          "temp_sense", "nvm_calibration", "ui_io", "mcu", "motor_drive"]


def net_of(nets, ref, pin):
    for name, nodes in nets.items():
        if (ref, pin) in nodes:
            return name
    return None


def rows(sheet_name, nets):
    sh = G.Sheet(open(D + sheet_name + ".kicad_sch", encoding="utf-8").read())
    syms, gnds = [], []
    for s in sh.symbols():
        ref = next((G.a(pr, 2) for pr in G.kids(s, "property")
                    if G.a(pr, 1) == "Reference"), "")
        val = next((G.a(pr, 2) for pr in G.kids(s, "property")
                    if G.a(pr, 1) == "Value"), "")
        p, pins = G.at(s), sorted(sh.pin_points(s))
        if ref.startswith("#PWR") and val == "GND":
            gnds.append((ref, p, pins[0] if pins else None))
        elif not ref.startswith(("#PWR", "#FLG")) and len(pins) == 2:
            syms.append((ref, p, pins))

    # walk each ground's stub back to the part pin it serves
    wires = sh.wires()
    served = {}
    for gref, gp, gpin in gnds:
        if not gpin:
            continue
        seen, front = {gpin}, [gpin]
        while front:
            pt = front.pop()
            for (a, b) in wires:
                for e, o in ((a, b), (b, a)):
                    if abs(e[0] - pt[0]) < 0.01 and abs(e[1] - pt[1]) < 0.01 \
                            and (round(o[0], 2), round(o[1], 2)) not in \
                            {(round(x, 2), round(y, 2)) for x, y in seen}:
                        seen.add(o)
                        front.append(o)
        for ref, p, pins in syms:
            for pin in pins:
                if any(abs(pin[0] - s[0]) < 0.01 and abs(pin[1] - s[1]) < 0.01
                       for s in seen):
                    served.setdefault(ref, []).append((gref, gp, pin))

    # group by (upper net, body y): what a reviewer reads as one parallel row
    groups = {}
    for ref, p, pins in syms:
        if ref not in served:
            continue
        gref, gp, gpin = served[ref][0]
        top = [pn for pn in pins if abs(pn[1] - gpin[1]) > 0.01]
        if not top:
            continue
        n = net_of(nets, ref, "1") or net_of(nets, ref, "2")
        tops = [net_of(nets, ref, k) for k in ("1", "2")]
        upper = next((t for t in tops if t and not t.endswith("GND")
                      and t != "GND"), None)
        groups.setdefault((upper, round(p[1], 2)), []).append(
            (ref, p, gref, gp, gpin))
    # ...then split each group into visual runs. Two parts 100 mm apart share a
    # net and a y without reading as a row, and levelling their flags would say
    # nothing to a reviewer.
    out = []
    for key, members in sorted(groups.items()):
        members.sort(key=lambda m: m[1][0])
        run = []
        for m in members:
            if run and m[1][0] - run[-1][1][0] > RUN_GAP:
                if len(run) > 1 and len({round(r[3][1], 2) for r in run}) > 1:
                    out.append((key, run))
                run = []
            run.append(m)
        if len(run) > 1 and len({round(r[3][1], 2) for r in run}) > 1:
            out.append((key, run))
    return out


def main(argv):
    nl = argv[0] if argv else "/tmp/nl_final.net"
    if not os.path.exists(nl):
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "-o", nl,
                        D + "faff2_cbs1.kicad_sch"], check=True,
                       env={**os.environ,
                            "AMODO_KICAD_LIB": "/mnt/c/Amodo/AmodoKiCadLib"},
                       capture_output=True)
    nets = node_sets(nl)
    total = 0
    for name in SHEETS:
        rr = rows(name, nets)
        if not rr:
            continue
        print("=== %s" % name)
        for (upper, by), members in rr:
            print("  row on %s at y=%.2f:" % (upper, by))
            for ref, p, gref, gp, gpin in members:
                print("     %-8s x=%7.2f  ->  %-9s at y=%.2f" %
                      (ref, p[0], gref, gp[1]))
            total += 1
    print("TOTAL misaligned rows: %d" % total)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
