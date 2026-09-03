#!/usr/bin/env python3
"""Round-2 batch, item 8: one placement rule for every power symbol's net name.

The captain: "When a power rail symbol is placed, it should always have its text
for the net located directly above it, centre justified, and close. Go through
the whole schematic and check this."

Applied as: **no sideways offset, centred, 3.81 mm away** - above a rail arrow,
below a ground. The mirror for ground is deliberate and is called out in the
decisions file: "above" a GND symbol is where its wire arrives, and 137 existing
instances plus every schematic convention put GND's name under the triangle. If
the captain meant it literally for grounds too, that is a one-line change here.

A second pass then nudges any *other* field that collides, so normalising the
power names does not leave the sheets worse than it found them.
"""
import os, re, subprocess, sys, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sch_geom as G

DIR = "hardware/kicad/faff2_cbs1"
OFFSET = 3.81

# Two flags that pass C shuffles into their rail symbol's own name. Their
# labels are 9.5 mm wide and the rail runs are only 10 mm, so they are placed by
# hand instead: far enough left that "PWR_FLAG" clears "+5V" / "+5VA" outright.
FIX_FLAGS = {
    "power_rails": {
        "#FLG345": (284.48, 81.28, [
            ("wire", (281.94, 83.82, 287.02, 83.82), (281.94, 83.82, 284.48, 83.82)),
            ("wire", (287.02, 83.82, 292.10, 83.82), (284.48, 83.82, 292.10, 83.82)),
            ("wire", (287.02, 81.28, 287.02, 83.82), (284.48, 81.28, 284.48, 83.82)),
            ("junction", (287.02, 83.82), (284.48, 83.82))]),
        "#FLG347": (386.08, 81.28, [
            ("wire", (383.54, 83.82, 388.62, 83.82), (383.54, 83.82, 386.08, 83.82)),
            ("wire", (388.62, 83.82, 393.70, 83.82), (386.08, 83.82, 393.70, 83.82)),
            ("wire", (388.62, 81.28, 388.62, 83.82), (386.08, 81.28, 386.08, 83.82)),
            ("junction", (388.62, 83.82), (386.08, 83.82))]),
    },
}

# Six power names land on a block border. The rule pins the label, and the
# border is only a drawn box, so the box gives way - each of these has 2.5 mm or
# more of clear space beyond it.
GROW_RECTS = {
    "loadcell_afe": [((95.25, 40.64, 166.37, 78.74), (95.25, 40.64, 166.37, 81.28)),
                     ((196.85, 13.97, 245.11, 33.02), (196.85, 13.97, 245.11, 35.56))],
    "temp_sense":   [((17.78, 11.43, 84.46, 46.99), (17.78, 11.43, 84.46, 49.53)),
                     ((17.78, 78.74, 84.46, 115.57), (17.78, 78.74, 84.46, 118.11)),
                     ((86.36, 78.74, 146.05, 146.05), (86.36, 78.74, 149.86, 146.05))],
}

NUDGE = sorted(((dx, dy) for dx in (0, 1.27, -1.27, 2.54, -2.54, 3.81, -3.81,
                                    5.08, -5.08)
                for dy in (0, 1.27, -1.27, 2.54, -2.54, 3.81, -3.81)),
               key=lambda d: abs(d[0]) + abs(d[1]))[1:]


def g(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


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


def prop_span(sym, name):
    pos = 0
    while True:
        i = sym.find('(property "%s"' % name, pos)
        if i < 0:
            return None
        e = block_end(sym, i)
        return i, e


def set_value_field(sym, x, y):
    """Put the Value at (x, y), centred, visible."""
    span = prop_span(sym, "Value")
    if not span:
        return sym
    i, e = span
    blk = sym[i:e]
    blk = re.sub(r"\(at [-\d.]+ [-\d.]+ [-\d.]+\)",
                 "(at %s %s 0)" % (g(x), g(y)), blk, count=1)
    blk = re.sub(r"\n\t+\(justify [^)]*\)", "", blk)      # centred
    blk = re.sub(r"\n\t+\(hide yes\)", "", blk)           # visible
    return sym[:i] + blk + sym[e:]


def collisions(text, movable):
    """Return {(ref, prop): box} for every visible field that collides."""
    sheet = G.Sheet(text)
    PAD = 0.05
    def grow(b):
        return (b[0] - PAD, b[1] - PAD, b[2] + PAD, b[3] + PAD)
    fixed = [G.seg_box(*w) for w in sheet.wires()]
    fixed += [G.seg_box(*e) for e in sheet.rect_edges()]
    fixed += sheet.free_text_boxes() + sheet.label_boxes()
    bodies = {}
    for s in sheet.symbols():
        ref = next((G.a(pr, 2) for pr in G.kids(s, "property")
                    if G.a(pr, 1) == "Reference"), "")
        b = sheet.body_box(s)
        if b:
            bodies.setdefault(ref, []).append(b)
    info, boxes = {}, {}
    for s in sheet.symbols():
        p = G.at(s)
        mir = bool(G.kid(s, "mirror"))
        ref = next((G.a(pr, 2) for pr in G.kids(s, "property")
                    if G.a(pr, 1) == "Reference"), "")
        for pr in G.kids(s, "property"):
            eff = G.kid(pr, "effects")
            h = G.kid(eff, "hide") if eff else None
            if h and G.a(h, 1) == "yes":
                continue
            j = [G.a(x, 1) for x in G.kids(eff, "justify")] if eff else []
            just = j[0] if j and j[0] in ("left", "right") else None
            pa = G.at(pr)
            k = (ref, G.a(pr, 1))
            info[k] = (pa[0], pa[1], G.a(pr, 2), just, p[2], mir)
            boxes[k] = G.text_box(pa[0], pa[1], G.a(pr, 2), just, p[2], mir)

    def clashes(key, b):
        if any(G.overlaps(grow(b), o) for o in fixed):
            return True
        for r2, bs in bodies.items():
            if r2 != key[0] and any(G.overlaps(grow(b), bb) for bb in bs):
                return True
        return any(k2 != key and G.overlaps(grow(b), b2)
                   for k2, b2 in boxes.items())

    moved, stuck = {}, []
    for key in sorted(info):
        if not clashes(key, boxes[key]):
            continue
        if key not in movable:
            stuck.append(key)
            continue
        x0, y0, txt, just, rot, mir = info[key]
        for (dx, dy) in NUDGE:
            b = G.text_box(x0 + dx, y0 + dy, txt, just, rot, mir)
            if not clashes(key, b):
                moved[key] = (x0 + dx, y0 + dy)
                boxes[key] = b
                break
        else:
            stuck.append(key)
    return moved, stuck



def try_move_symbol(text, ref):
    """Shorten a power symbol's stub so its pinned label clears.

    The label may not move - that is the rule - so the symbol does, along the
    wire it hangs on and never sideways. Returns the new text, or None.
    """
    sheet = G.Sheet(text)
    target = None
    for s in sheet.symbols():
        r = next((G.a(pr, 2) for pr in G.kids(s, "property")
                  if G.a(pr, 1) == "Reference"), "")
        if r == ref:
            target = s
            break
    if target is None:
        return None
    px, py, _ = G.at(target)
    val = next((G.a(pr, 2) for pr in G.kids(target, "property")
                if G.a(pr, 1) == "Value"), "")
    dy_label = OFFSET if val == "GND" else -OFFSET

    stub = None
    for (a_, b_) in sheet.wires():
        for (p, q) in ((a_, b_), (b_, a_)):
            if abs(p[0] - px) < 0.01 and abs(p[1] - py) < 0.01:
                stub = (p, q)
    if stub is None or abs(stub[0][0] - stub[1][0]) > 0.01:
        return None                       # only vertical stubs are handled
    far_y = stub[1][1]
    length = abs(far_y - py)
    # try shortening the stub first, then lengthening it

    PAD = 0.05
    def grow(b):
        return (b[0] - PAD, b[1] - PAD, b[2] + PAD, b[3] + PAD)
    obst = [G.seg_box(*w) for w in sheet.wires() if w != stub]
    obst += [G.seg_box(*e) for e in sheet.rect_edges()]
    obst += sheet.free_text_boxes() + sheet.label_boxes()
    for s in sheet.symbols():
        r = next((G.a(pr, 2) for pr in G.kids(s, "property")
                  if G.a(pr, 1) == "Reference"), "")
        b = sheet.body_box(s)
        if b and r != ref:
            obst.append(b)
    for (r2, p2, b2, _) in sheet.visible_fields():
        if r2 != ref:
            obst.append(b2)
    base = sheet.body_box(target)

    toward = 1.27 if far_y > py else -1.27
    # what it hits now - the move only has to clear these and add nothing new
    lb0 = G.text_box(px, py + dy_label, val, None, 0, False)
    before = sum(1 for o in obst
                 if G.overlaps(grow(lb0), o) or G.overlaps(grow(base), o))
    for d in sorted([toward * k for k in range(1, 5)]
                    + [-toward * k for k in range(1, 5)], key=abs):
        if (far_y > py and d > 0 and length - d < 1.27) or \
           (far_y < py and d < 0 and length + d < 1.27):
            continue
        ny = py + d
        lb = G.text_box(px, ny + dy_label, val, None, 0, False)
        bb = (base[0], base[1] + d, base[2], base[3] + d)
        after = sum(1 for o in obst
                    if G.overlaps(grow(lb), o) or G.overlaps(grow(bb), o))
        if after >= before:
            continue
        # rewrite the symbol and shorten its stub
        out, pos = [], 0
        for i, e, sym in each_symbol(text):
            m = re.search(r'\(property "Reference" "([^"]+)"', sym)
            if m and m.group(1) == ref:
                sym = re.sub(r"\n\t\t\(at [-\d.]+ [-\d.]+ ([-\d.]+)\)",
                             lambda mm: "\n\t\t(at %s %s %s)"
                             % (g(px), g(ny), mm.group(1)), sym, count=1)
                def fixp(pm, ny=ny):
                    nm = pm.group(1)
                    ty = ny + dy_label if nm == "Value" else ny
                    return '(property "%s" %s\n\t\t\t(at %s %s 0)' % (
                        nm, pm.group(2), g(px), g(ty))
                sym = re.sub(r'\(property "([^"]+)" ("[^"\\]*(?:\\.[^"\\]*)*")'
                             r'\n\t\t\t\(at [^\n]*\)', fixp, sym)
            out.append(text[pos:i]); out.append(sym); pos = e
        out.append(text[pos:])
        text = "".join(out)
        old_w = "(xy %s %s) (xy %s %s)" % (g(stub[0][0]), g(stub[0][1]),
                                           g(stub[1][0]), g(stub[1][1]))
        new_w = "(xy %s %s) (xy %s %s)" % (g(px), g(ny),
                                           g(stub[1][0]), g(stub[1][1]))
        if old_w in text:
            return text.replace(old_w, new_w, 1)
        old_w = "(xy %s %s) (xy %s %s)" % (g(stub[1][0]), g(stub[1][1]),
                                           g(stub[0][0]), g(stub[0][1]))
        new_w = "(xy %s %s) (xy %s %s)" % (g(stub[1][0]), g(stub[1][1]),
                                           g(px), g(ny))
        if old_w in text:
            return text.replace(old_w, new_w, 1)
        return None
    return None



def relocate_notes(text):
    """A pinned power name wins; a free-text note gets out of its way.

    Each note that overlaps one searches outward from where it is for the
    nearest position that is clear of everything, so it stays beside the
    circuit it explains.
    """
    import itertools
    sheet = G.Sheet(text)
    PAD = 0.3
    pinned = [b for (r, pn, b, _) in sheet.visible_fields()
              if r.startswith(("#PWR", "#FLG")) and pn == "Value"]
    obst = [G.seg_box(*w) for w in sheet.wires()]
    obst += [G.seg_box(*e) for e in sheet.rect_edges()]
    obst += sheet.label_boxes()
    for s in sheet.symbols():
        b = sheet.body_box(s)
        if b:
            obst.append(b)
    for (r, pn, b, _) in sheet.visible_fields():
        obst.append(b)

    notes = []
    for tnode in G.kids(sheet.sch, "text"):
        p = G.at(tnode)
        eff = G.kid(tnode, "effects")
        j = [G.a(x, i) for x in G.kids(eff, "justify") for i in range(1, len(x))]
        lines = G.a(tnode, 1).split("\\n")
        fs = G.kid(eff, "font")
        size = float(G.a(G.kid(fs, "size"), 1)) if G.kid(fs, "size") else 1.27
        w = max(len(l) for l in lines) * G.CHAR_W * (size / 1.27)
        h = G.note_height(len(lines)) * (size / 1.27)
        x0 = p[0] if "right" not in j else p[0] - w
        y0 = p[1] if "top" in j else p[1] - h
        notes.append((p, (x0, y0, x0 + w, y0 + h), w, h))

    others = [n[1] for n in notes]
    moves = []
    for idx, (p, box, w, h) in enumerate(notes):
        if not any(G.overlaps(box, pb, 0.05) for pb in pinned):
            continue
        rest = obst + [b for k, b in enumerate(others) if k != idx]
        found = None
        for d in range(1, 24):
            for (sx, sy) in sorted(set(itertools.product((-1, 0, 1), repeat=2)) - {(0, 0)},
                                   key=lambda v: (abs(v[0]) + abs(v[1]), v)):
                nx, ny = p[0] + sx * 1.27 * d, p[1] + sy * 1.27 * d
                nb = (box[0] + (nx - p[0]), box[1] + (ny - p[1]),
                      box[2] + (nx - p[0]), box[3] + (ny - p[1]))
                grown = (nb[0] - PAD, nb[1] - PAD, nb[2] + PAD, nb[3] + PAD)
                if any(G.overlaps(grown, o) for o in rest):
                    continue
                if any(G.overlaps(nb, pb, 0.05) for pb in pinned):
                    continue
                found = (nx, ny)
                break
            if found:
                break
        if found:
            moves.append((p, found))
            others[idx] = (box[0] + (found[0] - p[0]), box[1] + (found[1] - p[1]),
                           box[2] + (found[0] - p[0]), box[3] + (found[1] - p[1]))
    for (op, np_) in moves:
        old = "\n\t\t(at %s %s 0)" % (g(op[0]), g(op[1]))
        if old in text:
            text = text.replace(old, "\n\t\t(at %s %s 0)" % (g(np_[0]), g(np_[1])), 1)
    return text, len(moves)



def pin_flag(text, ref, nx, ny, edits):
    """Place one PWR_FLAG by hand: move the symbol and rewrite exactly the
    wires and junction named in `edits`. Exact coordinates only - a range
    sweep here took out an unrelated rail and broke +3V3A."""
    out, pos = [], 0
    for i, e, sym in each_symbol(text):
        m = re.search(r'\(property "Reference" "([^"]+)"', sym)
        if m and m.group(1) == ref:
            sym = re.sub(r"\n\t\t\(at [-\d.]+ [-\d.]+ ([-\d.]+)\)",
                         lambda mm: "\n\t\t(at %s %s %s)" % (g(nx), g(ny), mm.group(1)),
                         sym, count=1)

            def fixp(pm):
                nm = pm.group(1)
                ty = ny - OFFSET if nm == "Value" else ny
                return '(property "%s" %s\n\t\t\t(at %s %s 0)' % (
                    nm, pm.group(2), g(nx), g(ty))
            sym = re.sub(r'\(property "([^"]+)" ("[^"\\]*(?:\\.[^"\\]*)*")'
                         r'\n\t\t\t\(at [^\n]*\)', fixp, sym)
        out.append(text[pos:i]); out.append(sym); pos = e
    out.append(text[pos:])
    text = "".join(out)

    for kind, old, new in edits:
        if kind == "wire":
            o = "(xy %s %s) (xy %s %s)" % tuple(g(v) for v in old)
            n = "(xy %s %s) (xy %s %s)" % tuple(g(v) for v in new)
            if o not in text:
                sys.exit("pin_flag %s: wire %s not found" % (ref, old))
            text = text.replace(o, n, 1)
        else:
            o = "\t\t(at %s %s)" % (g(old[0]), g(old[1]))
            n = "\t\t(at %s %s)" % (g(new[0]), g(new[1]))
            if o not in text:
                sys.exit("pin_flag %s: junction %s not found" % (ref, old))
            text = text.replace(o, n, 1)
    return text


def main():
    root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                   text=True).strip()
    os.chdir(root)
    n_norm = n_nudge = n_notes = 0
    all_stuck = []
    for path in sorted(glob.glob("%s/*.kicad_sch" % DIR)):
        name = os.path.basename(path)
        t = subprocess.check_output(["git", "show", "HEAD:" + path], text=True)

        # ---- pass A: every power symbol's net name, to the rule
        out, pos = [], 0
        for i, e, sym in each_symbol(t):
            m = re.search(r'\(property "Reference" "([^"]+)"', sym)
            ref = m.group(1) if m else ""
            out.append(t[pos:i])
            if ref.startswith(("#PWR", "#FLG")):
                sm = re.search(r"\n\t\t\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)", sym)
                sx, sy = float(sm.group(1)), float(sm.group(2))
                val = re.search(r'\(property "Value" "([^"]*)"', sym).group(1)
                dy = OFFSET if val == "GND" else -OFFSET
                sym = set_value_field(sym, sx, sy + dy)
                n_norm += 1
            out.append(sym)
            pos = e
        out.append(t[pos:])
        t = "".join(out)

        # ---- pass B: nudge anything else that now collides
        movable = set()
        for i, e, sym in each_symbol(t):
            m = re.search(r'\(property "Reference" "([^"]+)"', sym)
            ref = m.group(1) if m else ""
            if ref.startswith(("#PWR", "#FLG")):
                continue          # the rule pins these; they may not be nudged
            for pr in re.findall(r'\(property "([^"]+)"', sym):
                movable.add((ref, pr))
        moved, stuck = collisions(t, movable)
        if moved:
            out, pos = [], 0
            for i, e, sym in each_symbol(t):
                m = re.search(r'\(property "Reference" "([^"]+)"', sym)
                ref = m.group(1) if m else ""
                for (cref, cpn), (cx, cy) in moved.items():
                    if cref != ref:
                        continue
                    span = prop_span(sym, cpn)
                    if not span:
                        continue
                    a_, b_ = span
                    blk = re.sub(r"\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)",
                                 lambda mm: "(at %s %s %s)" % (g(cx), g(cy),
                                                               mm.group(3)),
                                 sym[a_:b_], count=1)
                    sym = sym[:a_] + blk + sym[b_:]
                out.append(t[pos:i]); out.append(sym); pos = e
            out.append(t[pos:])
            t = "".join(out)
            n_nudge += len(moved)

        # ---- pass B2: a note that a pinned power name lands on moves aside
        t, n_notes_moved = relocate_notes(t)
        n_notes += n_notes_moved
        moved, stuck = collisions(t, movable)

        # ---- pass C: the rule pins the label, so where it still collides the
        # symbol moves instead - shortened along its own stub, never sideways
        for _ in range(4):
            stuck = [s for s in stuck if s[0].startswith(("#PWR", "#FLG"))]
            if not stuck:
                break
            fixed_any = False
            pinned_by_hand = set(FIX_FLAGS.get(name[:-len(".kicad_sch")], {}))
            for (ref, _pn) in list(stuck):
                if ref in pinned_by_hand:
                    continue
                t2 = try_move_symbol(t, ref)
                if t2 is not None:
                    t = t2
                    fixed_any = True
            moved2, stuck = collisions(t, movable)
            if moved2:
                out, pos = [], 0
                for i, e, sym in each_symbol(t):
                    m = re.search(r'\(property "Reference" "([^"]+)"', sym)
                    r = m.group(1) if m else ""
                    for (cref, cpn), (cx, cy) in moved2.items():
                        if cref != r:
                            continue
                        span = prop_span(sym, cpn)
                        if not span:
                            continue
                        a_, b_ = span
                        blk = re.sub(r"\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)",
                                     lambda mm: "(at %s %s %s)"
                                     % (g(cx), g(cy), mm.group(3)),
                                     sym[a_:b_], count=1)
                        sym = sym[:a_] + blk + sym[b_:]
                    out.append(t[pos:i]); out.append(sym); pos = e
                out.append(t[pos:])
                t = "".join(out)
                n_nudge += len(moved2)
            if not fixed_any:
                break

        # ---- pass D0: block boxes give way to a pinned power name
        for old_r, new_r in GROW_RECTS.get(name[:-len(".kicad_sch")], []):
            o = "(start %s %s)" % (g(old_r[0]), g(old_r[1]))
            o2 = "(end %s %s)" % (g(old_r[2]), g(old_r[3]))
            i = t.find(o)
            while i >= 0 and t.find(o2, i, i + 400) < 0:
                i = t.find(o, i + 1)
            if i < 0:
                sys.exit("%s: rect %s not found" % (name, old_r))
            j = t.find(o2, i)
            t = (t[:i] + "(start %s %s)" % (g(new_r[0]), g(new_r[1]))
                 + t[i + len(o):j] + "(end %s %s)" % (g(new_r[2]), g(new_r[3]))
                 + t[j + len(o2):])

        # ---- pass D: the two hand-placed flags, last word
        for ref, (nx, ny, edits) in FIX_FLAGS.get(name[:-len(".kicad_sch")], {}).items():
            t = pin_flag(t, ref, nx, ny, edits)

        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(t)
        if stuck:
            all_stuck += [(name, s) for s in stuck]
    print("item 8: %d power names normalised, %d other fields nudged clear, "
          "%d notes moved aside" % (n_norm, n_nudge, n_notes))
    if all_stuck:
        print("still colliding, needs the symbol moved rather than the label:")
        for n, s in all_stuck:
            print("   %-26s %s" % (n, s))


if __name__ == "__main__":
    main()
