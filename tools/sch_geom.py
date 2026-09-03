#!/usr/bin/env python3
"""Geometry for KiCad 9 schematics: where things actually land on the page.

Written for the round-1 review sweep, because the bundled overlap checker
grows every text field rightward from its anchor and so cannot see a field
that renders leftward. Both facts below were settled by experiment against
KiCad 9.0.8 renders, not from the format documentation:

  pin/graphic transform   rot 0    (x+px, y-py)
                          rot 90   (x-py, y-px)
                          rot 180  (x-px, y+py)
                          rot 270  (x+py, y+px)
                          mirror y (x-px, y-py)

  text grows leftward when  (justify right) XOR (symbol at 180) XOR (mirrored)
"""
import re

CHAR_W = 1.19          # mm per character advance at text size 1.27.
                       # Measured off a 6 px/mm render: "5.0SMDJ26A" inks
                       # 11.435 mm over 10 characters and "100uF" 5.65 over 5,
                       # which back out to a ~1.17-1.19 mm advance. The bundled
                       # overlap checker uses ~1.06, so it under-measures every
                       # text box by about a tenth and passes real near-misses.
LINE_H = 1.27
LINE_PITCH = 1.85     # KiCad's line spacing for a multi-line note, measured


def note_height(n):
    return LINE_H + (n - 1) * LINE_PITCH



def toks(s):
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1; continue
        if c in "()":
            yield c; i += 1; continue
        if c == '"':
            j = i + 1; b = []
            while True:
                if s[j] == "\\":
                    b.append(s[j:j + 2]); j += 2; continue
                if s[j] == '"':
                    break
                b.append(s[j]); j += 1
            yield ("STR", "".join(b)); i = j + 1; continue
        j = i
        while j < n and not s[j].isspace() and s[j] not in '()"':
            j += 1
        yield ("ATOM", s[i:j]); i = j


def parse(s):
    st = [[]]
    for t in toks(s):
        if t == "(":
            st.append([])
        elif t == ")":
            v = st.pop(); st[-1].append(v)
        else:
            st[-1].append(t)
    return st[0][0]


def head(e):
    return e[0][1] if e and isinstance(e[0], tuple) else None


def kids(e, name):
    return [x for x in e if isinstance(x, list) and head(x) == name]


def kid(e, name):
    k = kids(e, name)
    return k[0] if k else None


def a(e, i):
    return e[i][1] if i < len(e) and isinstance(e[i], tuple) else None


def at(e):
    n = kid(e, "at")
    if not n:
        return None
    return (float(a(n, 1)), float(a(n, 2)),
            float(a(n, 3)) if len(n) > 3 else 0.0)


def xform(px, py, rot, mirror):
    if mirror:
        return (-px, -py) if int(rot) == 0 else (px, py)
    r = int(rot) % 360
    if r == 0:
        return (px, -py)
    if r == 90:
        return (-py, -px)
    if r == 180:
        return (-px, py)
    return (py, px)


def grows_left(justify, rot, mirror):
    return bool((justify == "right") ^ (int(rot) == 180) ^ bool(mirror))


def text_box(x, y, text, justify, rot, mirror):
    lines = text.split("\\n")
    w = max(len(l) for l in lines) * CHAR_W
    h = len(lines) * LINE_H
    if grows_left(justify, rot, mirror):
        x0, x1 = x - w, x
    elif justify == "left" or justify == "right":
        x0, x1 = x, x + w
    else:
        x0, x1 = x - w / 2, x + w / 2
    return (x0, y - h / 2, x1, y + h / 2)


def seg_box(p, q, pad=0.0):
    return (min(p[0], q[0]) - pad, min(p[1], q[1]) - pad,
            max(p[0], q[0]) + pad, max(p[1], q[1]) + pad)


def overlaps(a_, b_, tol=0.1):
    return (a_[0] < b_[2] - tol and b_[0] < a_[2] - tol and
            a_[1] < b_[3] - tol and b_[1] < a_[3] - tol)


class Sheet:
    def __init__(self, text):
        self.text = text
        self.sch = parse(text)
        self._libgraphics = {}
        for s in kids(kid(self.sch, "lib_symbols") or ["lib_symbols"], "symbol"):
            pts = {}
            for u in kids(s, "symbol"):
                m = re.match(r".*_(\d+)_(\d+)$", a(u, 1) or "")
                unit = int(m.group(1)) if m else 0
                acc = pts.setdefault(unit, [])
                for g in u:
                    if not isinstance(g, list):
                        continue
                    h = head(g)
                    if h in ("rectangle", "circle", "arc"):
                        r = kid(g, "radius")
                        rad = float(a(r, 1)) if r else 0.0
                        for tag in ("start", "end", "center", "mid"):
                            k = kid(g, tag)
                            if k:
                                cx, cy = float(a(k, 1)), float(a(k, 2))
                                acc += [(cx - rad, cy - rad), (cx + rad, cy + rad)]
                    elif h == "polyline":
                        for p in kids(kid(g, "pts"), "xy"):
                            acc.append((float(a(p, 1)), float(a(p, 2))))
            self._libgraphics[a(s, 1)] = pts

    def wires(self):
        out = []
        for w in kids(self.sch, "wire"):
            xy = [(float(a(x, 1)), float(a(x, 2)))
                  for x in kids(kid(w, "pts"), "xy")]
            out.append((xy[0], xy[1]))
        return out

    def rect_edges(self):
        out = []
        for r in kids(self.sch, "rectangle"):
            s, e = kid(r, "start"), kid(r, "end")
            x1, y1 = float(a(s, 1)), float(a(s, 2))
            x2, y2 = float(a(e, 1)), float(a(e, 2))
            out += [((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)),
                    ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))]
        return out

    def body_box(self, sym):
        lid = a(kid(sym, "lib_id"), 1)
        p = at(sym)
        mir = bool(kid(sym, "mirror"))
        unit = int(a(kid(sym, "unit"), 1) or 1)
        pts = self._libgraphics.get(lid, {})
        acc = pts.get(0, []) + pts.get(unit, [])
        if not acc:
            return None
        xs, ys = [], []
        for (px, py) in acc:
            dx, dy = xform(px, py, p[2], mir)
            xs.append(p[0] + dx); ys.append(p[1] + dy)
        return (min(xs), min(ys), max(xs), max(ys))

    def symbols(self):
        return kids(self.sch, "symbol")

    def visible_fields(self, skip_refs=()):
        """[(ref, propname, box, skip)] for every field that renders.

        A multi-unit part has one Reference field per unit instance, all with
        the same refdes, so anything that keys these by refdes collapses them -
        which once put all five U601 units' references on one point. Use
        `visible_fields_by_instance` when identity matters.
        """
        out = []
        for s in self.symbols():
            p = at(s)
            mir = bool(kid(s, "mirror"))
            ref = next((a(pr, 2) for pr in kids(s, "property")
                        if a(pr, 1) == "Reference"), "")
            for pr in kids(s, "property"):
                eff = kid(pr, "effects")
                h = kid(eff, "hide") if eff else None
                if h and a(h, 1) == "yes":
                    continue
                j = [a(x, 1) for x in kids(eff, "justify")] if eff else []
                just = j[0] if j and j[0] in ("left", "right") else None
                pa = at(pr)
                out.append((ref, a(pr, 1),
                            text_box(pa[0], pa[1], a(pr, 2), just, p[2], mir),
                            (ref, a(pr, 1)) in skip_refs))
        return out

    def free_text_boxes(self):
        out = []
        for t in kids(self.sch, "text"):
            p = at(t)
            eff = kid(t, "effects")
            # a justify node carries several tokens - (justify left top) - so
            # take them all, not just the first
            j = [a(x, i) for x in kids(eff, "justify")
                 for i in range(1, len(x))] if eff else []
            just = j[0] if j and j[0] in ("left", "right") else None
            lines = a(t, 1).split("\\n")
            w = max(len(l) for l in lines) * CHAR_W
            h = note_height(len(lines))
            x0 = p[0] if just != "right" else p[0] - w
            y0 = p[1] if "top" in j else p[1] - h
            out.append((x0, y0, x0 + w, y0 + h))
        return out

    def label_boxes(self):
        out = []
        for tag in ("label", "hierarchical_label", "global_label"):
            for l in kids(self.sch, tag):
                p = at(l)
                eff = kid(l, "effects")
                j = [a(x, 1) for x in kids(eff, "justify")] if eff else []
                just = j[0] if j and j[0] in ("left", "right") else None
                txt = a(l, 1)
                w = len(txt) * CHAR_W + 2.0      # allow for the flag glyph
                if int(p[2]) in (90, 270):
                    out.append((p[0] - LINE_H, min(p[1], p[1] - w),
                                p[0] + LINE_H, max(p[1], p[1] + w)))
                elif just == "right":
                    out.append((p[0] - w, p[1] - LINE_H, p[0], p[1] + LINE_H))
                else:
                    out.append((p[0], p[1] - LINE_H, p[0] + w, p[1] + LINE_H))
        return out

    def visible_fields_by_instance(self):
        """[(uuid, ref, propname, box, meta)] - one entry per field per unit."""
        out = []
        for s in self.symbols():
            p = at(s)
            mir = bool(kid(s, "mirror"))
            su = a(kid(s, "uuid"), 1)
            ref = next((a(pr, 2) for pr in kids(s, "property")
                        if a(pr, 1) == "Reference"), "")
            for pr in kids(s, "property"):
                eff = kid(pr, "effects")
                h = kid(eff, "hide") if eff else None
                if h and a(h, 1) == "yes":
                    continue
                j = [a(x, 1) for x in kids(eff, "justify")] if eff else []
                just = j[0] if j and j[0] in ("left", "right") else None
                pa = at(pr)
                out.append((su, ref, a(pr, 1),
                            text_box(pa[0], pa[1], a(pr, 2), just, p[2], mir),
                            (pa[0], pa[1], a(pr, 2), just, p[2], mir, pa[2])))
        return out
