#!/usr/bin/env python3
"""Everything a sheet draws inside a rectangle - the reconnaissance step.

    python3 tools/dump_region.py <sheet.kicad_sch> x1 y1 x2 y2

Round 1 taught the reason this exists: I placed capacitor stubs into a band I
believed was empty from a partial wire dump, and they landed collinear with two
gate verticals and shorted them. Never infer free space from a partial dump -
ask for the whole rectangle.
"""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sch_geom as G


def main(path, x1, y1, x2, y2):
    sh = G.Sheet(open(path, encoding="utf-8").read())

    def hit(x, y):
        return x1 <= x <= x2 and y1 <= y <= y2

    def hitbox(b):
        return b and not (b[2] < x1 or b[0] > x2 or b[3] < y1 or b[1] > y2)

    for sym in sh.symbols():
        p = G.at(sym)
        if not hit(p[0], p[1]):
            continue
        ref = val = "?"
        for pr in G.kids(sym, "property"):
            if G.a(pr, 1) == "Reference":
                ref = G.a(pr, 2)
            elif G.a(pr, 1) == "Value":
                val = G.a(pr, 2)
        mir = " mirror" if G.kids(sym, "mirror") else ""
        lid = G.a(G.kid(sym, "lib_id"), 1).split(":")[-1]
        print(f'sym  {ref:8s} {val[:18]:18s} at ({p[0]:.2f},{p[1]:.2f}) rot={p[2]:g}{mir}'
              f'  body={sh.body_box(sym)}  [{lid[:44]}]')

    for (p, q) in sh.wires():
        if hit(*p) or hit(*q):
            print(f"wire ({p[0]:.2f},{p[1]:.2f})-({q[0]:.2f},{q[1]:.2f})")
    for tag in ("junction", "no_connect", "bus_entry"):
        for e in G.kids(sh.sch, tag):
            p = G.at(e)
            if hit(p[0], p[1]):
                print(f"{tag} ({p[0]:.2f},{p[1]:.2f})")
    for tag in ("label", "hierarchical_label", "global_label"):
        for e in G.kids(sh.sch, tag):
            p = G.at(e)
            if hit(p[0], p[1]):
                ef = G.kid(e, "effects")
                ju = G.kid(ef, "justify") if ef else None
                jt = " ".join(str(v) for v in ju[1:]) if ju else "-"
                print(f'{tag} "{G.a(e, 1)}" at ({p[0]:.2f},{p[1]:.2f}) '
                      f'rot={p[2]:g} justify={jt}')
    for box, tx in zip(sh.free_text_boxes(), G.kids(sh.sch, "text")):
        if hitbox(box):
            first = G.a(tx, 1).split("\\n")[0][:50]
            print(f"text box={tuple(round(v, 2) for v in box)} {first!r}...")
    for r in G.kids(sh.sch, "rectangle"):
        s, e = G.kid(r, "start"), G.kid(r, "end")
        b = (float(G.a(s, 1)), float(G.a(s, 2)), float(G.a(e, 1)), float(G.a(e, 2)))
        if hitbox((min(b[0], b[2]), min(b[1], b[3]), max(b[0], b[2]), max(b[1], b[3]))):
            print(f"rect ({b[0]:.2f},{b[1]:.2f})-({b[2]:.2f},{b[3]:.2f})")


if __name__ == "__main__":
    main(sys.argv[1], *map(float, sys.argv[2:6]))
