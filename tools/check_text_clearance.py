#!/usr/bin/env python3
"""Text clearance checker for the FAFF 2 schematic - the recorded successor to
`check_overlaps.py` from the `schematic-style` skill.

Why this exists. The bundled checker passed two overlaps the captain found by
eye on power_rails (round 3): `C312`'s reference running into the vertical wire
feeding `U303`'s IN pin, and `U303`'s own value text sitting on its body's top
edge. Four separate reasons it could not see them, all fixed here:

  1  it grows every text field rightward from its anchor, so its box is a mirror
     image whenever the text renders leftward - which `justify right`, a
     `(mirror y)` symbol and a symbol at 180 deg each do, and any two cancel;
  2  it measures text at about 1.06 mm per character; the real advance at size
     1.27 is ~1.19, so every box is a tenth too small;
  3  it never compares a field against **its own symbol's** outline, which is
     exactly the `U303` case;
  4  it only reports strict overlap. Text and a wire 0.3 mm apart read as
     touching once both stroke widths are drawn, which is the `C312` case.

So this one uses the transforms and text model in `sch_geom.py` (each settled
against a render, not the file format), compares against every symbol outline
including the field's own, and requires a real **clearance**, not just absence of
overlap.

    python3 tools/check_text_clearance.py [--margin 0.4] [dir]
"""
import argparse, glob, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sch_geom as G

DEFAULT_MARGIN = 0.4        # mm of white space text must keep from anything


def gap(a, b):
    """Signed clearance between two boxes: >0 apart, <0 overlapping by that much."""
    dx = max(a[0] - b[2], b[0] - a[2])
    dy = max(a[1] - b[3], b[1] - a[3])
    if dx >= 0 or dy >= 0:
        return max(dx, dy)                       # apart in at least one axis
    return max(dx, dy)                           # both negative -> penetration


def obstacles(sheet):
    """[(key, label, box)] for everything text has to stay clear of.

    Bodies are keyed by the symbol's uuid, not its refdes: a multi-unit part has
    one body per unit under one refdes, and keying by refdes conflates them.
    """
    out = [(("wire", n), "wire", G.seg_box(*w))
           for n, w in enumerate(sheet.wires())]
    out += [(("border", n), "blockborder", G.seg_box(*e))
            for n, e in enumerate(sheet.rect_edges())]
    out += [(("note", n), "note", b)
            for n, b in enumerate(sheet.free_text_boxes())]
    out += [(("netlabel", n), "netlabel", b)
            for n, b in enumerate(sheet.label_boxes())]
    for s in sheet.symbols():
        ref = next((G.a(pr, 2) for pr in G.kids(s, "property")
                    if G.a(pr, 1) == "Reference"), "")
        su = G.a(G.kid(s, "uuid"), 1)
        b = sheet.body_box(s)
        if b:
            out.append((("body", su), "body:" + ref, b))
    return out


def findings(path, margin):
    sheet = G.Sheet(open(path, encoding="utf-8").read())
    obs = obstacles(sheet)
    flds = sheet.visible_fields_by_instance()
    out = []
    for i, (su, ref, prop, box, _m) in enumerate(flds):
        for key, label, ob in obs:
            d = gap(box, ob)
            if d < margin:
                out.append((d, ref, prop, label))
        for (su2, r2, p2, b2, _m2) in flds[i + 1:]:
            d = gap(box, b2)
            if d < margin:
                out.append((d, ref, prop, "field:%s.%s" % (r2, p2)))
    out.sort()
    return out


def block_end(t, i):
    d, j = 0, i
    while True:
        c = t[j]
        if c == '"':
            j += 1
            while t[j] != '"' or t[j - 1] == "\\":
                j += 1
        elif c == "(":
            d += 1
        elif c == ")":
            d -= 1
            if d == 0:
                return j + 1
        j += 1


def each_symbol(t):
    pos = 0
    while True:
        i = t.find("\t(symbol\n", pos)
        if i < 0:
            return
        e = block_end(t, i + 1)
        yield i, e, t[i:e]
        pos = e


def _fmt(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


# offsets tried when a field has to find clearance, nearest first
_STEPS = [0.635 * k for k in range(1, 13)]
CANDIDATES = sorted({(dx, dy) for s in _STEPS for dx in (-s, 0, s)
                     for dy in (-s, 0, s)} - {(0.0, 0.0)},
                    key=lambda d: (abs(d[0]) + abs(d[1]), abs(d[0])))


def fix_sheet(path, margin):
    """Move every movable field until it has `margin` of clearance.

    Keyed by symbol uuid: a multi-unit part's units each own a Reference field,
    and an earlier version of this keyed by refdes and stacked all five U601
    references on one point. A power symbol's Value may not move - round 2
    pinned those - so those are reported instead.
    """
    import re
    text = open(path, encoding="utf-8").read()
    for _round in range(80):
        sheet = G.Sheet(text)
        obs = obstacles(sheet)
        flds = sheet.visible_fields_by_instance()
        boxes = {(su, p): b for (su, r, p, b, m) in flds}
        meta = {(su, p): (r, m) for (su, r, p, b, m) in flds}

        def clear(key, box):
            for _k, _l, ob in obs:
                if gap(box, ob) < margin:
                    return False
            for k2, b2 in boxes.items():
                if k2 != key and gap(box, b2) < margin:
                    return False
            return True

        pick = None
        for key in sorted(boxes):
            ref, m = meta[key]
            if key[1] == "Value" and ref.startswith(("#PWR", "#FLG")):
                continue
            if clear(key, boxes[key]):
                continue
            x0, y0, txt, just, rot, mir, fang = m
            for (dx, dy) in CANDIDATES:
                nb = G.text_box(x0 + dx, y0 + dy, txt, just, rot, mir)
                if clear(key, nb):
                    pick = (key[0], key[1], x0 + dx, y0 + dy, fang)
                    break
            if pick:
                break
        if pick is None:
            break
        su, prop, nx, ny, fang = pick
        out, pos = [], 0
        for i, e, sym in each_symbol(text):
            if ('(uuid "%s")' % su) in sym:
                k = sym.find('(property "%s"' % prop)
                if k >= 0:
                    ke = block_end(sym, k)
                    blk = re.sub(r"\(at [-\d.]+ [-\d.]+ [-\d.]+\)",
                                 "(at %s %s %d)" % (_fmt(nx), _fmt(ny), fang),
                                 sym[k:ke], count=1)
                    sym = sym[:k] + blk + sym[ke:]
            out.append(text[pos:i]); out.append(sym); pos = e
        out.append(text[pos:])
        text = "".join(out)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", nargs="?", default="hardware/kicad/faff2_cbs1")
    ap.add_argument("--margin", type=float, default=DEFAULT_MARGIN)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--fix", action="store_true",
                    help="move movable fields until they have the margin")
    a = ap.parse_args()
    total = 0
    for path in sorted(glob.glob(os.path.join(a.dir, "*.kicad_sch"))):
        if a.fix:
            new = fix_sheet(path, a.margin)
            if new != open(path, encoding="utf-8").read():
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new)
        f = findings(path, a.margin)
        name = os.path.basename(path)
        if not f:
            print("=== %s: clear" % name)
            continue
        print("=== %s: %d finding(s)" % (name, len(f)))
        if not a.quiet:
            for (d, ref, prop, kind) in f:
                word = "overlaps by" if d < 0 else "clears by only"
                print("   %-9s %-10s %s %6.2f mm  vs %s"
                      % (ref, prop, word, abs(d), kind))
        total += len(f)
    print("TOTAL: %d (margin %.2f mm)" % (total, a.margin))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
