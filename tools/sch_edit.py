#!/usr/bin/env python3
"""Small, exact edit primitives for a KiCad 9 schematic held as text.

Every one of these asserts that it changed something. The round-1 lesson that
made that non-negotiable: `str.replace` says nothing when it matches nothing, so
a re-runnable script reported success while five of its six edits had silently
done nothing. Coordinates here are matched loosely (0.01 mm) because KiCad
writes them with trailing zeros - "168.9100" - and re-writes them without.
"""
import re

GRID = 1.27


def fmt(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def on_grid(*vals):
    for v in vals:
        assert abs(round(v / GRID) * GRID - v) < 1e-6, "%g is off the 1.27 grid" % v


def block(text, start):
    """The balanced s-expression starting at `start` (which must be the '(')."""
    d, j = 0, start
    while True:
        c = text[j]
        if c == '"':
            j += 1
            while not (text[j] == '"' and text[j - 1] != "\\"):
                j += 1
        elif c == "(":
            d += 1
        elif c == ")":
            d -= 1
            if d == 0:
                return text[start:j + 1]
        j += 1


def sym_span(text, ref):
    i = text.index('(property "Reference" "%s"' % ref)
    cands = [s for s, _b in _blocks(text, "symbol") if s < i]
    assert cands, ref
    s = cands[-1]
    e = s + len(block(text, s))
    assert s < i < e, ref
    return s, e


def move_symbol(text, ref, dx, dy):
    """Shift a symbol and every field it owns; fields carry absolute positions."""
    s, e = sym_span(text, ref)

    def shift(m):
        return "(at %s %s%s)" % (fmt(float(m.group(1)) + dx),
                                 fmt(float(m.group(2)) + dy), m.group(3) or "")
    new = re.sub(r"\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)", shift, text[s:e])
    assert new != text[s:e], ref
    return text[:s] + new + text[e:]


def _nums(blk):
    return [float(v) for v in re.findall(r"-?\d+\.?\d*", blk)]


_OPEN = re.compile(r"\n\t\((\w+)[\n ]")


def normalise(text):
    """Put back the newline between two top-level blocks.

    A round-1 script closed one block and opened the next with a tab and no
    newline - `\n\t)\t(symbol` - eighteen times across motor_drive and
    power_rails. KiCad does not care, which is why ERC and the netlist never
    noticed, but it hides a block from anything that anchors on line starts.
    """
    n = 0
    while "\n\t)\t(" in text:
        text = text.replace("\n\t)\t(", "\n\t)\n\t(")
        n += 1
        assert n < 100
    return text


def _blocks(text, tag):
    """Every top-level `tag` block. Two formats are in play: sheets KiCad has
    saved put each field on its own line, and generated sheets use the compact
    one-line form `(wire (pts (xy ...) (xy ...))`. Matching only the first is
    how a re-runnable script silently did nothing on `mcu`."""
    for m in _OPEN.finditer(text):
        if m.group(1) == tag:
            s = m.start() + 2
            yield s, block(text, s)


def _find(text, tag, pred):
    for s, blk in _blocks(text, tag):
        if pred(_nums(blk)):
            return s, blk
    return None


def move_wire(text, p, q, np_, nq):
    """Re-route one wire segment, keeping its uuid."""
    on_grid(np_[0], np_[1], nq[0], nq[1])
    hit = _find(text, "wire", lambda n: (
        abs(n[0] - p[0]) < 0.01 and abs(n[1] - p[1]) < 0.01 and
        abs(n[2] - q[0]) < 0.01 and abs(n[3] - q[1]) < 0.01))
    assert hit, (p, q)
    s, blk = hit
    new = re.sub(r"\(xy [-\d.]+ [-\d.]+\) \(xy [-\d.]+ [-\d.]+\)",
                 "(xy %s %s) (xy %s %s)" % (fmt(np_[0]), fmt(np_[1]),
                                            fmt(nq[0]), fmt(nq[1])), blk, count=1)
    return text[:s] + new + text[s + len(blk):]


def move_point(text, tag, p, np_):
    """Move a junction or no_connect."""
    on_grid(np_[0], np_[1])
    hit = _find(text, tag, lambda n: (abs(n[0] - p[0]) < 0.01 and
                                      abs(n[1] - p[1]) < 0.01))
    assert hit, (tag, p)
    s, blk = hit
    new = re.sub(r"\(at [-\d.]+ [-\d.]+\)",
                 "(at %s %s)" % (fmt(np_[0]), fmt(np_[1])), blk, count=1)
    return text[:s] + new + text[s + len(blk):]


def move_note(text, key, x, y):
    """Move a free-text note, keyed by a unique substring of its content."""
    # A note carries its content on the same line as its opening token, and the
    # key can also appear inside another note, so walk the text blocks and take
    # the one that actually contains it - exactly one must.
    hits = [s for s, blk in _blocks(text, "text") if key in blk]
    assert len(hits) == 1, (key, len(hits))
    s = hits[0]
    blk = block(text, s)
    new = re.sub(r"\(at [-\d.]+ [-\d.]+ ([-\d.]+)\)",
                 lambda m: "(at %s %s %s)" % (fmt(x), fmt(y), m.group(1)),
                 blk, count=1)
    assert new != blk, key
    return text[:s] + new + text[s + len(blk):]


def edit_note(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def move_label(text, name, occurrence, dx, dy):
    """Move the nth (0-based) label of this name, whatever its flavour."""
    seen = 0
    for tag in ("label", "hierarchical_label", "global_label"):
        for s, blk in list(_blocks(text, tag)):
            if not blk.startswith('(%s "%s"' % (tag, name)):
                continue
            if seen == occurrence:
                new = re.sub(
                    r"\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)",
                    lambda m: "(at %s %s%s)" % (fmt(float(m.group(1)) + dx),
                                                fmt(float(m.group(2)) + dy),
                                                m.group(3) or ""), blk, count=1)
                assert new != blk, name
                return text[:s] + new + text[s + len(blk):]
            seen += 1
    raise AssertionError((name, occurrence))


def set_rect(text, old, new):
    """Resize a block bounding box: old/new are (x1, y1, x2, y2)."""
    o = "(start %s %s)" % (fmt(old[0]), fmt(old[1]))
    oe = "(end %s %s)" % (fmt(old[2]), fmt(old[3]))
    assert text.count(o) >= 1 and text.count(oe) >= 1, old
    hits = [(s, blk) for s, blk in _blocks(text, "rectangle")
            if o in blk and oe in blk]
    assert len(hits) == 1, old
    s, blk = hits[0]
    nb = blk.replace(o, "(start %s %s)" % (fmt(new[0]), fmt(new[1])))
    nb = nb.replace(oe, "(end %s %s)" % (fmt(new[2]), fmt(new[3])))
    return text[:s] + nb + text[s + len(blk):]


def set_field(text, ref, prop, x, y):
    s, e = sym_span(text, ref)
    blk = text[s:e]
    k = blk.index('(property "%s"' % prop)
    ke = k + len(block(blk, k))
    fld = re.sub(r"\(at [-\d.]+ [-\d.]+ ([-\d.]+)\)",
                 lambda m: "(at %s %s %s)" % (fmt(x), fmt(y), m.group(1)),
                 blk[k:ke], count=1)
    assert fld != blk[k:ke], (ref, prop)
    return text[:s] + blk[:k] + fld + blk[ke:] + text[e:]


def del_wire(text, p, q):
    hit = _find(text, "wire", lambda n: (
        abs(n[0] - p[0]) < 0.01 and abs(n[1] - p[1]) < 0.01 and
        abs(n[2] - q[0]) < 0.01 and abs(n[3] - q[1]) < 0.01))
    assert hit, (p, q)
    s, blk = hit
    return text[:s - 1] + text[s + len(blk) + 1:]


def del_point(text, tag, p):
    hit = _find(text, tag, lambda n: (abs(n[0] - p[0]) < 0.01 and
                                      abs(n[1] - p[1]) < 0.01))
    assert hit, (tag, p)
    s, blk = hit
    return text[:s - 1] + text[s + len(blk) + 1:]


def add(text, chunk):
    """Insert top-level content before the sheet's first junction block.

    The insert lands at a LINE start. Getting this wrong put one extra tab in
    front of everything added - KiCad does not care, but every tool here that
    anchors on "\\n\\t(" stopped seeing those blocks, so a resistor that was in
    the netlist could not be found on the sheet.
    """
    for s, _b in _blocks(text, "junction"):
        assert text[s - 1] == "\t" and text[s - 2] == "\n"
        return text[:s - 1] + chunk + text[s - 1:]
    raise AssertionError("no junction to anchor to")


def wire_block(p, q, uid):
    on_grid(p[0], p[1], q[0], q[1])
    return (f"\t(wire\n\t\t(pts\n\t\t\t(xy {fmt(p[0])} {fmt(p[1])}) "
            f"(xy {fmt(q[0])} {fmt(q[1])})\n\t\t)\n\t\t(stroke\n"
            f"\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            f'\t\t(uuid "{uid}")\n\t)\n')


def junction_block(x, y, uid):
    on_grid(x, y)
    return (f"\t(junction\n\t\t(at {fmt(x)} {fmt(y)})\n\t\t(diameter 0)\n"
            f'\t\t(color 0 0 0 0)\n\t\t(uuid "{uid}")\n\t)\n')


def set_label_justify(text, name, occurrence, justify):
    """Flip which way a label's text grows. Used when a label reads off the end
    of its own wire into a neighbour - the growth direction is the defect, not
    the position."""
    seen = 0
    for tag in ("label", "hierarchical_label", "global_label"):
        for s, blk in list(_blocks(text, tag)):
            if not blk.startswith('(%s "%s"' % (tag, name)):
                continue
            if seen == occurrence:
                new = re.sub(r"\(justify [a-z ]+\)", "(justify %s)" % justify,
                             blk, count=1)
                assert new != blk, name
                return text[:s] + new + text[s + len(blk):]
            seen += 1
    raise AssertionError((name, occurrence))


def uid5(*parts):
    """A stable uuid for generated content, from the parts that identify it."""
    import uuid
    return str(uuid.uuid5(uuid.UUID("5edb00fd-45c9-5fe7-8d71-adbf38f38546"),
                          "|".join(str(p) for p in parts)))


def rename_symbol(text, old, new):
    """Re-designate a part: its Reference field and its instance path entry.

    Both must change together. The Reference property is what the sheet draws;
    the `(instances ... (reference ...))` entry is what the netlist reads, and a
    sheet with the two disagreeing loads without complaint and exports the old
    name.
    """
    s, e = sym_span(text, old)
    blk = text[s:e]
    n = blk.count('"%s"' % old)
    assert n >= 2, (old, n)
    return text[:s] + blk.replace('"%s"' % old, '"%s"' % new) + text[e:]


def note_block(body, x, y, uid, size=1.27, justify="left top"):
    """A free-text note. Multi-line content uses \\n escapes, never a literal
    newline - a real newline inside a quoted s-expression makes KiCad fail to
    load the sheet with nothing but "Failed to load schematic"."""
    assert "\n" not in body, "use \\n escapes"
    return (f'\t(text\n\t\t"{body}"\n\t\t(exclude_from_sim no)\n'
            f"\t\t(at {fmt(x)} {fmt(y)} 0)\n\t\t(effects\n\t\t\t(font\n"
            f"\t\t\t\t(size {size} {size})\n\t\t\t)\n"
            f"\t\t\t(justify {justify})\n\t\t)\n"
            f'\t\t(uuid "{uid}")\n\t)\n')


def del_symbol(text, ref):
    s, e = sym_span(text, ref)
    return text[:s - 1] + text[e + 1:]


def set_rotation(text, ref, angle, field_angle):
    """Rotate an instance and compensate its field angles.

    A property's `(at x y angle)` angle is RELATIVE to the symbol, so a field
    left at 0 on a symbol rotated to 90 renders sideways. 270 on a 90 symbol
    sums to 360 and comes out horizontal. Prove it in a render, every time.
    """
    s, e = sym_span(text, ref)
    blk = text[s:e]
    # the symbol's own (at) is the first one in the block
    m = re.search(r"\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)", blk)
    assert m, ref
    blk = blk[:m.start()] + "(at %s %s %d)" % (m.group(1), m.group(2), angle) \
        + blk[m.end():]
    out, pos = [], 0
    while True:
        i = blk.find('(property "', pos)
        if i < 0:
            break
        pb = block(blk, i)
        nb = re.sub(r"\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)",
                    lambda mm: "(at %s %s %d)" % (mm.group(1), mm.group(2),
                                                  field_angle), pb, count=1)
        out.append(blk[pos:i]); out.append(nb)
        pos = i + len(pb)
    out.append(blk[pos:])
    return text[:s] + "".join(out) + text[e:]


def set_lib_id(text, ref, lib_id):
    s, e = sym_span(text, ref)
    blk = re.sub(r'\(lib_id "[^"]*"\)', '(lib_id "%s")' % lib_id,
                 text[s:e], count=1)
    return text[:s] + blk + text[e:]


def del_lib_symbol(text, name):
    """Drop an embedded library symbol that no instance uses any more."""
    marker = '\t\t(symbol "%s"\n' % name
    assert text.count(marker) == 1, name
    i = text.index(marker) + 2
    blk = block(text, i)
    assert '(lib_id "%s")' % name not in text, "%s still instantiated" % name
    return text[:i - 2] + text[i + len(blk) + 1:]


def label_block(name, x, y, rot, justify, uid):
    return (f'\t(label "{name}"\n\t\t(at {fmt(x)} {fmt(y)} {rot:g})\n'
            "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
            f"\t\t\t(justify {justify})\n\t\t)\n"
            f'\t\t(uuid "{uid}")\n\t)\n')


def embed_lib_symbol(text, src, lib_id):
    """Copy a symbol from a library file into the sheet's lib_symbols."""
    if '(symbol "%s"' % lib_id in text:
        return text
    bare = lib_id.split(":", 1)[1]
    i = src.index('\t(symbol "%s"\n' % bare) + 1
    sym = block(src, i)
    sym = re.sub(r'^\(symbol "', '(symbol "%s:' % lib_id.split(":", 1)[0],
                 sym, count=1)
    sym = "\n".join("\t" + l if l else l for l in sym.split("\n"))
    anchor = "\t\t(symbol \""
    j = text.index(anchor)
    return text[:j] + "\t\t" + sym.lstrip("\t") + "\n" + text[j:]


def sync_properties(text, ref, src, bare, keep=("Reference",), value=None):
    """Refresh an instance's cached property values from its library symbol.

    `set_lib_id` alone leaves the instance carrying the OLD part's mpn,
    datasheet and description - a swap that looks right on the sheet and ships
    the wrong part number to the BOM. Positions and visibility stay as they
    are; only the strings change.
    """
    i = src.index('\t(symbol "%s"\n' % bare) + 1
    lib = block(src, i)
    want = {m.group(1): m.group(2) for m in
            re.finditer(r'\(property "([^"]*)" "((?:[^"\\]|\\.)*)"', lib)}
    if value is not None:
        want["Value"] = value
    s, e = sym_span(text, ref)
    blk, out, pos = text[s:e], [], 0
    while True:
        k = blk.find('(property "', pos)
        if k < 0:
            break
        pb = block(blk, k)
        m = re.match(r'\(property "([^"]*)" "((?:[^"\\]|\\.)*)"', pb)
        name = m.group(1)
        if name in want and name not in keep:
            pb = pb[:m.start(2)] + want[name] + pb[m.end(2):]
        out.append(blk[pos:k]); out.append(pb)
        pos = k + len(block(blk, k))
    out.append(blk[pos:])
    return text[:s] + "".join(out) + text[e:]


def nc_block(x, y, uid):
    on_grid(x, y)
    return (f"\t(no_connect\n\t\t(at {fmt(x)} {fmt(y)})\n"
            f'\t\t(uuid "{uid}")\n\t)\n')


def clone_symbol(text, model, ref, x, y, uid):
    """A new instance cloned from an existing one on the same sheet.

    Cloning beats hand-building: the property set, effects, instance path and
    library id all come out right, and a hand-built block is how a stray
    str.replace once put `(hide yes)` inside a font block and truncated a sheet.
    """
    s, e = sym_span(text, model)
    blk = text[s:e]
    m = re.search(r"\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)", blk)
    dx, dy = x - float(m.group(1)), y - float(m.group(2))

    def shift(mm):
        return "(at %s %s%s)" % (fmt(float(mm.group(1)) + dx),
                                 fmt(float(mm.group(2)) + dy),
                                 mm.group(3) or "")
    out = re.sub(r"\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)", shift, blk)
    out = out.replace('"%s"' % model, '"%s"' % ref)
    out = re.sub(r'\(uuid "[0-9a-f-]{36}"\)', '(uuid "%s")' % uid, out, count=1)
    n = [0]

    def pinuid(mm):
        n[0] += 1
        return '(uuid "%s")' % uid5(ref, "pin", n[0])
    head, tail = out.split('(pin "1"', 1)
    return "\t" + head + '(pin "1"' + re.sub(
        r'\(uuid "[0-9a-f-]{36}"\)', pinuid, tail) + "\n"


def symbol_block(lib_id, ref, value, x, y, path, src, uid, fields, npins):
    """A fresh instance of a library part, properties taken from the library."""
    i = src.index('\t(symbol "%s"\n' % lib_id.split(":", 1)[1]) + 1
    lib = block(src, i)
    props = {m.group(1): m.group(2) for m in
             re.finditer(r'\(property "([^"]*)" "((?:[^"\\]|\\.)*)"', lib)}
    props["Reference"], props["Value"] = ref, value
    eff_shown = ("\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
                 "\t\t\t\t)\n\t\t\t)\n")
    eff_hidden = ("\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
                  "\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n")
    s = ['\t(symbol\n\t\t(lib_id "%s")\n\t\t(at %s %s 0)\n\t\t(unit 1)\n'
         % (lib_id, fmt(x), fmt(y)),
         "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n",
         '\t\t(dnp no)\n\t\t(fields_autoplaced no)\n\t\t(uuid "%s")\n' % uid]
    for name, val in props.items():
        px, py = fields.get(name, (x, y))
        s.append('\t\t(property "%s" "%s"\n\t\t\t(at %s %s 0)\n%s\t\t)\n'
                 % (name, val, fmt(px), fmt(py),
                    eff_shown if name in fields else eff_hidden))
    for n in range(1, npins + 1):
        s.append('\t\t(pin "%d"\n\t\t\t(uuid "%s")\n\t\t)\n'
                 % (n, uid5(ref, "pin", n)))
    s.append('\t\t(instances\n\t\t\t(project "faff2_cbs1"\n\t\t\t\t(path "%s"\n'
             '\t\t\t\t\t(reference "%s")\n\t\t\t\t\t(unit 1)\n'
             "\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n" % (path, ref))
    return "".join(s)


def move_label_to(text, name, occurrence, x, y):
    seen = 0
    for tag in ("label", "hierarchical_label", "global_label"):
        for s, blk in list(_blocks(text, tag)):
            if not blk.startswith('(%s "%s"' % (tag, name)):
                continue
            if seen == occurrence:
                new = re.sub(r"\(at [-\d.]+ [-\d.]+( [-\d.]+)?\)",
                             lambda m: "(at %s %s%s)" % (fmt(x), fmt(y),
                                                         m.group(1) or ""),
                             blk, count=1)
                return text[:s] + new + text[s + len(blk):]
            seen += 1
    raise AssertionError((name, occurrence))


def set_rotation_label(text, name, occurrence, angle):
    seen = 0
    for tag in ("label", "hierarchical_label", "global_label"):
        for s, blk in list(_blocks(text, tag)):
            if not blk.startswith('(%s "%s"' % (tag, name)):
                continue
            if seen == occurrence:
                new = re.sub(r"\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)",
                             lambda m: "(at %s %s %g)" % (m.group(1),
                                                          m.group(2), angle),
                             blk, count=1)
                return text[:s] + new + text[s + len(blk):]
            seen += 1
    raise AssertionError((name, occurrence))


def _label_at(text, name, xy):
    """The label of this name whose anchor is at `xy`.

    Keying labels by an occurrence index is a trap: a net is usually labelled
    at both ends, and moving "the first SWDIO" moved the one at the MCU pin
    rather than the one at the header - four dangling labels and an ERC error
    each. Position is the identity that means something.
    """
    for tag in ("label", "hierarchical_label", "global_label"):
        for s, blk in list(_blocks(text, tag)):
            if not blk.startswith('(%s "%s"' % (tag, name)):
                continue
            m = re.search(r"\(at ([-\d.]+) ([-\d.]+)", blk)
            if abs(float(m.group(1)) - xy[0]) < 0.01 and \
               abs(float(m.group(2)) - xy[1]) < 0.01:
                return s, blk
    raise AssertionError((name, xy))


def move_label_at(text, name, xy, x, y, rot=None, justify=None):
    s, blk = _label_at(text, name, xy)
    new = re.sub(r"\(at [-\d.]+ [-\d.]+( [-\d.]+)?\)",
                 lambda m: "(at %s %s %s)" % (
                     fmt(x), fmt(y),
                     ("%g" % rot) if rot is not None
                     else (m.group(1) or " 0").strip()), blk, count=1)
    if justify is not None:
        new = re.sub(r"\(justify [a-z ]+\)", "(justify %s)" % justify, new,
                     count=1)
    return text[:s] + new + text[s + len(blk):]
