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

A fifth, found the same way - by a render, after this checker had already
passed the sheet: **net labels and symbol bodies were only ever obstacles, never
subjects.** A label running through a GND arrow, or an arrow grazing a wire it
does not connect to, scored zero findings. Both are subjects now. A body is
excused from a wire that lands on one of its own pins (`Sheet.pin_points`),
which is what every grounded wire does, and a label from whichever wire passes
through its own anchor - the wire it labels.

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
BODY_MIN = 0.25             # mm a body must be penetrated by before it counts
ALONG_MIN = 0.635           # mm a wire must run inside a body before it counts

# Text and an outline need different rules, and conflating them is what made
# the first version of this unusable. A text box is inked edge to edge, so it
# must keep real *clearance*. A symbol body is a bounding box around a triangle
# or a polyline, so its corners are mostly empty: requiring clearance there
# reports every wire that happens to start at a GND arrow's empty corner. A
# body therefore has to be genuinely *penetrated* - or, for a wire, run inside
# it for a real distance - before it is a finding.


def gap(a, b):
    """Signed clearance between two boxes: >0 apart, <0 overlapping by that much."""
    dx = max(a[0] - b[2], b[0] - a[2])
    dy = max(a[1] - b[3], b[1] - a[3])
    if dx >= 0 or dy >= 0:
        return max(dx, dy)                       # apart in at least one axis
    return max(dx, dy)                           # both negative -> penetration


def obstacles(sheet):
    """[(key, label, box)] for everything a subject has to stay clear of.

    Bodies are keyed by the symbol's uuid, not its refdes: a multi-unit part has
    one body per unit under one refdes, and keying by refdes conflates them.
    """
    out = [(("wire", n), "wire", G.seg_box(*w))
           for n, w in enumerate(sheet.wires())]
    out += [(("border", n), "blockborder", G.seg_box(*e))
            for n, e in enumerate(sheet.rect_edges())]
    notes = [G.a(t, 1).split("\\n")[0][:22] for t in G.kids(sheet.sch, "text")]
    out += [(("note", n), 'note "%s"' % notes[n], b)
            for n, b in enumerate(sheet.free_text_boxes())]
    names = [G.a(l, 1) for tag in ("label", "hierarchical_label", "global_label")
             for l in G.kids(sheet.sch, tag)]
    out += [(("netlabel", n), "label:" + names[n], b)
            for n, (b, t, _a) in enumerate(sheet.label_details())]
    for s in sheet.symbols():
        ref = next((G.a(pr, 2) for pr in G.kids(s, "property")
                    if G.a(pr, 1) == "Reference"), "")
        su = G.a(G.kid(s, "uuid"), 1)
        b = sheet.body_box(s)
        if b:
            out.append((("body", su), "body:" + ref, b))
    # Fields are obstacles too. Leaving them out of this list is how a
    # "PWR_FLAG" 0.86 mm inside a neighbouring "100nF" survived a clean run:
    # the subject/obstacle rewrite dropped the field-against-field pass the
    # first version had, and reference-against-value is the commonest defect
    # of the lot.
    out += [(("field", su, prop), "%s.%s" % (ref, prop), box)
            for (su, ref, prop, box, _m) in sheet.visible_fields_by_instance()]
    return out


def on_segment(p, seg, tol=0.01):
    (x1, y1), (x2, y2) = seg
    return (min(x1, x2) - tol <= p[0] <= max(x1, x2) + tol and
            min(y1, y2) - tol <= p[1] <= max(y1, y2) + tol and
            abs((x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1)) < tol * 10)


def reportable(kind, box, obs_key, ob, margin):
    """Does this pair clear the bar for its subject kind? -> (yes, distance)."""
    d = gap(box, ob)
    if kind != "body":
        return d < margin, d
    if obs_key[0] == "wire":
        horiz = ob[1] == ob[3]
        lo, hi = (max(box[0], ob[0]), min(box[2], ob[2])) if horiz else \
                 (max(box[1], ob[1]), min(box[3], ob[3]))
        if hi - lo < ALONG_MIN:
            return False, d          # a corner touch, not a wire through it
        thru = ob[1] if horiz else ob[0]
        edge = (box[1], box[3]) if horiz else (box[0], box[2])
        if not edge[0] - 0.01 <= thru <= edge[1] + 0.01:
            return False, d
        return True, -min(thru - edge[0], edge[1] - thru)
    return d < -BODY_MIN, d


def wire_nodes(wires):
    """Group wire segments into electrical nodes by shared endpoints.

    A label names a node, and every wire of that node may legitimately run
    under its text - that is what "the wire must extend under the entire label"
    asks for. Excusing only the one segment the anchor sits on reported every
    branch dropping off that same node, nine times across mcu and motor_drive.
    """
    parent = list(range(len(wires)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    at_point = {}
    for i, (p, q) in enumerate(wires):
        for e in (p, q):
            at_point.setdefault((round(e[0], 2), round(e[1], 2)), []).append(i)
    for js in at_point.values():
        for j in js[1:]:
            a_, b_ = find(js[0]), find(j)
            if a_ != b_:
                parent[b_] = a_
    return [find(i) for i in range(len(wires))]


def excused(sheet, subj_key, obs_key, wires, pins, anchors, nodes=None):
    """True where a subject and an obstacle are meant to be in contact.

    A symbol body touches every wire that lands on one of its own pins - a GND
    arrow's outline starts at its pin, so all 283 power symbols would otherwise
    report. And a net label sits on its own node, branches included.
    """
    if subj_key[0] == "body" and obs_key[0] == "wire":
        w = wires[obs_key[1]]
        return any(on_segment(pt, w) for pt in pins.get(subj_key[1], ()))
    if subj_key[0] == "body" and obs_key[0] == "body":
        return subj_key[1] == obs_key[1]
    if subj_key[0] == "netlabel":
        if obs_key[0] == "wire":
            own = {nodes[i] for i, w in enumerate(wires)
                   if on_segment(anchors[subj_key[1]], w)} if nodes else set()
            return nodes[obs_key[1]] in own if own else on_segment(
                anchors[subj_key[1]], wires[obs_key[1]])
        if obs_key[0] == "netlabel":
            return subj_key[1] == obs_key[1]
    if subj_key[0] == "note" and obs_key[0] == "note":
        return subj_key[1] == obs_key[1]
    if subj_key[0] == "field" and obs_key[0] == "field":
        return subj_key[1:] == obs_key[1:]
    return False


def subjects(sheet):
    """[(key, name, kind, box)] - everything that must keep its clearance.

    Fields are movable and `--fix` moves them. Labels, notes and bodies are
    reported only: moving a label is forbidden by the round-2 power-label rule
    and moving a body is a design decision, not a tidy-up.
    """
    out = []
    for (su, ref, prop, box, _m) in sheet.visible_fields_by_instance():
        out.append((("field", su, prop), "%s.%s" % (ref, prop), "field", box))
    names = [G.a(l, 1) for tag in ("label", "hierarchical_label", "global_label")
             for l in G.kids(sheet.sch, tag)]
    for n, (b, t, _a) in enumerate(sheet.label_details()):
        out.append((("netlabel", n), "label:" + names[n], "netlabel", b))
    for n, tx in enumerate(G.kids(sheet.sch, "text")):
        out.append((("note", n), 'note "%s"' % G.a(tx, 1).split("\\n")[0][:22],
                    "note", sheet.free_text_boxes()[n]))
    for s in sheet.symbols():
        ref = next((G.a(pr, 2) for pr in G.kids(s, "property")
                    if G.a(pr, 1) == "Reference"), "")
        b = sheet.body_box(s)
        if b:
            out.append((("body", G.a(G.kid(s, "uuid"), 1)),
                        "body:" + ref, "body", b))
    return out


def findings(path, margin):
    sheet = G.Sheet(open(path, encoding="utf-8").read())
    obs = obstacles(sheet)
    subs = subjects(sheet)
    wires = sheet.wires()
    anchors = [a_ for (_b, _t, a_) in sheet.label_details()]
    pins = {G.a(G.kid(s, "uuid"), 1): sheet.pin_points(s)
            for s in sheet.symbols()}
    nodes = wire_nodes(wires)
    out = []
    for (skey, name, kind, box) in subs:
        for okey, olabel, ob in obs:
            if kind == "field" and okey[0] == "body":
                pass                      # a field vs its OWN body still counts
            elif kind == "field" and okey[0] == "field":
                if skey[1:] == okey[1:]:
                    continue
            elif skey[:2] == okey[:2] or (kind, skey[1]) == (okey[0], okey[1]):
                continue
            if excused(sheet, (kind, skey[1]) if kind != "field" else skey,
                       okey, wires, pins, anchors, nodes):
                continue
            hit, d = reportable(kind, box, okey, ob, margin)
            if hit:
                # one line per pair, not two: a body vs a label is the same
                # finding read from either end
                out.append((d, name, kind, olabel, box, ob))
    seen, uniq = set(), []
    for f in sorted(out):
        pair = (round(f[0], 3), frozenset((f[1], f[3])))
        if pair in seen:
            continue
        seen.add(pair)
        uniq.append(f)
    return uniq


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
            x0, y0, txt, just, rot, mir, fang, fk = m
            for (dx, dy) in CANDIDATES:
                nb = G.text_box(x0 + dx, y0 + dy, txt, just, rot, mir, fk)
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
    ap.add_argument("dir", nargs="?", default="hardware/kicad/faff2_cbs1",
                    help="a schematic directory or a single .kicad_sch")
    ap.add_argument("--margin", type=float, default=DEFAULT_MARGIN)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--fix", action="store_true",
                    help="move movable fields until they have the margin")
    a = ap.parse_args()
    total = 0
    paths = ([a.dir] if a.dir.endswith(".kicad_sch")
             else sorted(glob.glob(os.path.join(a.dir, "*.kicad_sch"))))
    assert paths, "no schematics at %s" % a.dir
    for path in paths:
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
            for (d, name, kind, olabel, box, ob) in f:
                word = "overlaps by" if d < 0 else "clears by only"
                print("   %-30s %s %5.2f  vs %-30s @ (%.2f,%.2f)"
                      % (name, word, abs(d), olabel,
                         (ob[0] + ob[2]) / 2, (ob[1] + ob[3]) / 2))
        total += len(f)
    print("TOTAL: %d (margin %.2f mm)" % (total, a.margin))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
