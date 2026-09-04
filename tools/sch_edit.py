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
    """Insert top-level content before the sheet's first junction block."""
    for s, _b in _blocks(text, "junction"):
        return text[:s] + chunk + "\t" + text[s:]
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
