#!/usr/bin/env python3
"""Round-1 captain review, batch 1 - power_entry_24v.kicad_sch (graphical only).

Re-runnable: it edits the committed HEAD copy of the sheet, so running it twice
gives the same file.  Every change here is placement; no net membership moves.

Captain's five points, and what each one does here:
  1  mirror J201 so its pins leave to the right and no wire routes round the body
  2  Q201 laid horizontal (rot 90) - pins 1/5 in line with the rail, gate down
  3  R201/R202 divider stacked in one vertical column at x=137.16
  4  D201 and D202 drawn vertically, like the C204/C205/C206 they sit beside
  5  R206 and C207 GND flags brought to a common height (y=96.52)

Rotation transform, verified against KiCad 9.0.8 by experiment and against the
27 rotated symbols already in this project:
     rot 90   dx = -py   dy = -px        rot 270  dx = +py   dy = +px
     mirror y dx = -px   dy = -py
"""
import os, subprocess, sys, uuid, re

SHEET = "hardware/kicad/faff2_cbs1/power_entry_24v.kicad_sch"
SHEET_UUID = "c6fcd1f2-81af-5930-b510-4ffbb5f4ea2e"
NS = uuid.UUID(SHEET_UUID)


def uid(key):
    return str(uuid.uuid5(NS, "review-r1-batch1/" + key))


def g(v):
    """KiCad writes coordinates with trailing zeros stripped."""
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


# ---------------------------------------------------------------- symbol moves
# ref -> (x, y, rot, mirror, {property: (x, y, rot)})
SYMS = {
    # 1. input connector mirrored: body left of origin, pins leaving right
    "J201":    (22.86, 43.18, 0, "y", {"Reference": (19.05, 38.10, 0),
                                       "Value":     (19.05, 40.64, 0)}),
    "R208":    (31.75, 57.15, 0, None, {"Reference": (33.78, 58.15, 0),
                                        "Value":     (33.78, 60.55, 0)}),
    "#PWR201": (31.75, 64.77, 0, None, {"Value": (31.75, 68.58, 0)}),

    # 2. protection FET horizontal - drain left, source right, gate down
    "Q201":    (109.22, 71.12, 90, None, {"Reference": (106.68, 64.77, 270),
                                          "Value":     (106.68, 67.17, 270)}),
    # C203 moved right so the V24_PROT label clears its junction dot
    "C203":    (129.54, 87.63, 0, None, {"Reference": (131.57, 88.63, 0),
                                         "Value":     (131.57, 91.03, 0)}),

    # 3. gate divider stacked in one column, both halves moved together so
    #    C203's value text still clears R201's body
    # R201's fields ride 2.4 lower than the usual offset so its reference
    # clears the GND label under D201, which stays level with the bank's
    "R201":    (140.97, 85.09, 0, None, {"Reference": (143.00, 88.49, 0),
                                         "Value":     (143.00, 90.89, 0)}),
    "R202":    (140.97, 106.68, 0, None, {"Reference": (143.00, 107.68, 0),
                                          "Value":     (143.00, 110.08, 0)}),
    "#PWR206": (140.97, 114.30, 0, None, {"Value": (140.97, 118.11, 0)}),

    # 4. TVS vertical, in line with the shunt bank, GND flag level with theirs
    "D201":    (147.32, 78.74, 90, None, {"Reference": (149.35, 76.20, 270),
                                          "Value":     (149.35, 78.60, 270)}),
    "#PWR207": (147.32, 81.28, 0, None, {"Value": (147.32, 85.09, 0)}),

    # bank shifted 5.08 right to clear D201's value text
    "C204":    (165.10, 76.20, 0, None, {"Reference": (167.13, 77.20, 0),
                                         "Value":     (167.13, 79.60, 0)}),
    "#PWR208": (165.10, 81.28, 0, None, {"Value": (165.10, 85.09, 0)}),
    "C205":    (175.26, 76.20, 0, None, {"Reference": (177.29, 77.20, 0),
                                         "Value":     (177.29, 79.60, 0)}),
    "#PWR209": (175.26, 81.28, 0, None, {"Value": (175.26, 85.09, 0)}),
    "C206":    (185.42, 76.20, 0, None, {"Reference": (187.45, 77.20, 0),
                                         "Value":     (187.45, 79.60, 0)}),
    "#PWR210": (185.42, 81.28, 0, None, {"Value": (185.42, 85.09, 0)}),

    # 4. power LED vertical, stacked under its series resistor
    "R207":    (195.58, 74.93, 0, None, {"Reference": (197.61, 75.93, 0),
                                         "Value":     (197.61, 78.33, 0)}),
    "D202":    (195.58, 83.82, 270, None, {"Reference": (197.61, 85.09, 90),
                                           "Value":     (197.61, 87.49, 90)}),
    "#PWR211": (195.58, 95.25, 0, None, {"Value": (195.58, 99.06, 0)}),

    # 5. C207 dropped so its GND flag sits level with R206's
    "C207":    (336.55, 90.17, 0, None, {"Reference": (338.58, 91.17, 0),
                                         "Value":     (338.58, 93.57, 0)}),
    "#PWR216": (336.55, 96.52, 0, None, {"Value": (336.55, 100.33, 0)}),
}

# KiCad flips field justification for a mirrored symbol, so J201's fields carry
# "right" in the file to read left-to-right on the page.
JUSTIFY = {"J201": {"Reference": "right", "Value": "right"}}

LABELS = {           # local label -> new anchor
    "V24_IN":   (29.21, 38.10),
    "V0_IN":    (46.99, 82.55),
    "V24_PROT": (116.84, 71.12),
}

DEL_WIRES = [
    # J201 fan-out, which used to route back round the left of the body
    (21.59, 49.53, 21.59, 52.07), (21.59, 49.53, 33.02, 49.53),
    (21.59, 52.07, 21.59, 82.55), (21.59, 52.07, 33.02, 52.07),
    (21.59, 82.55, 24.13, 82.55), (24.13, 82.55, 57.15, 82.55),
    (26.67, 54.61, 26.67, 57.15), (26.67, 54.61, 33.02, 54.61),
    (26.67, 62.23, 26.67, 64.77),
    (27.94, 38.10, 27.94, 44.45), (27.94, 38.10, 29.21, 38.10),
    (27.94, 44.45, 27.94, 46.99), (27.94, 44.45, 33.02, 44.45),
    (27.94, 46.99, 33.02, 46.99), (29.21, 38.10, 38.10, 38.10),
    # Q201's vertical drop and the gate loop that ran round its left
    (104.14, 38.10, 104.14, 60.96),
    (104.14, 71.12, 106.68, 71.12), (106.68, 71.12, 111.76, 71.12),
    (92.71, 66.04, 92.71, 104.14), (92.71, 66.04, 97.79, 66.04),
    (92.71, 104.14, 111.76, 104.14),
    # R201 and C203 in their old columns
    (111.76, 71.12, 111.76, 85.09), (111.76, 71.12, 121.92, 71.12),
    (111.76, 90.17, 111.76, 104.14), (111.76, 104.14, 121.92, 104.14),
    (121.92, 71.12, 121.92, 85.09), (121.92, 90.17, 121.92, 104.14),
    (121.92, 71.12, 133.35, 71.12), (121.92, 104.14, 137.16, 104.14),
    (137.16, 104.14, 137.16, 106.68), (137.16, 111.76, 137.16, 114.30),
    # D201's horizontal jog, and the rail either side of it
    (133.35, 71.12, 147.32, 71.12), (142.24, 83.82, 142.24, 88.90),
    (147.32, 71.12, 147.32, 83.82), (147.32, 71.12, 160.02, 71.12),
    # shunt bank, shifted right
    (160.02, 71.12, 160.02, 73.66), (160.02, 71.12, 170.18, 71.12),
    (160.02, 78.74, 160.02, 81.28),
    (170.18, 71.12, 170.18, 73.66), (170.18, 71.12, 180.34, 71.12),
    (170.18, 78.74, 170.18, 81.28),
    (180.34, 71.12, 180.34, 73.66), (180.34, 71.12, 190.50, 71.12),
    (180.34, 78.74, 180.34, 81.28),
    # R207 / D202's horizontal jog
    (190.50, 71.12, 190.50, 74.93), (190.50, 71.12, 228.60, 71.12),
    (190.50, 80.01, 190.50, 83.82), (190.50, 83.82, 198.12, 83.82),
    (205.74, 83.82, 205.74, 88.90),
    # C207's stubs, lengthened so its GND lands level with R206's
    (336.55, 83.82, 336.55, 86.36), (336.55, 91.44, 336.55, 93.98),
]

ADD_WIRES = [
    # J201: +24 V pair joins just clear of the pins, then straight up to the rail
    (26.67, 44.45, 29.21, 44.45), (26.67, 46.99, 29.21, 46.99),
    (29.21, 44.45, 29.21, 46.99), (29.21, 38.10, 29.21, 44.45),
    (29.21, 38.10, 38.10, 38.10),
    # 0 V pair runs right, clear of R208's text, then drops to the choke
    (26.67, 49.53, 44.45, 49.53), (26.67, 52.07, 44.45, 52.07),
    (44.45, 49.53, 44.45, 52.07), (44.45, 52.07, 44.45, 82.55),
    (44.45, 82.55, 46.99, 82.55), (46.99, 82.55, 57.15, 82.55),
    # shield, out to the right then down through R208
    (26.67, 54.61, 31.75, 54.61), (31.75, 54.61, 31.75, 57.15),
    (31.75, 62.23, 31.75, 64.77),
    # V24_IN drops straight onto Q201's drain; source carries on right
    (104.14, 38.10, 104.14, 71.12),
    (114.30, 71.12, 116.84, 71.12), (116.84, 71.12, 129.54, 71.12),
    # gate drops straight down and runs right into the divider
    (109.22, 77.47, 109.22, 104.14), (109.22, 104.14, 129.54, 104.14),
    (129.54, 104.14, 140.97, 104.14),
    # C203, in parallel with R201 and drawn the same way up
    (129.54, 71.12, 129.54, 85.09), (129.54, 90.17, 129.54, 104.14),
    (129.54, 71.12, 133.35, 71.12),
    # divider column
    (133.35, 71.12, 140.97, 71.12), (140.97, 71.12, 147.32, 71.12),
    (140.97, 71.12, 140.97, 85.09), (140.97, 90.17, 140.97, 104.14),
    (140.97, 104.14, 140.97, 106.68), (140.97, 111.76, 140.97, 114.30),
    # TVS, now vertical with 2.54 stubs like the caps beside it
    (147.32, 71.12, 147.32, 73.66), (147.32, 78.74, 147.32, 81.28),
    (147.32, 71.12, 165.10, 71.12),
    (165.10, 71.12, 165.10, 73.66), (165.10, 78.74, 165.10, 81.28),
    (165.10, 71.12, 175.26, 71.12),
    (175.26, 71.12, 175.26, 73.66), (175.26, 78.74, 175.26, 81.28),
    (175.26, 71.12, 185.42, 71.12),
    (185.42, 71.12, 185.42, 73.66), (185.42, 78.74, 185.42, 81.28),
    (185.42, 71.12, 195.58, 71.12),
    # R207 over D202, both vertical, in one column
    (195.58, 71.12, 195.58, 74.93), (195.58, 80.01, 195.58, 83.82),
    (195.58, 91.44, 195.58, 95.25), (195.58, 71.12, 228.60, 71.12),
    # C207 stubs at 3.81, matching R206's, so both GND flags land at 96.52
    (336.55, 83.82, 336.55, 87.63), (336.55, 92.71, 336.55, 96.52),
]

DEL_JUNCTIONS = [(21.59, 52.07), (27.94, 44.45), (111.76, 71.12),
                 (111.76, 104.14), (121.92, 71.12), (121.92, 104.14),
                 (160.02, 71.12), (170.18, 71.12), (180.34, 71.12),
                 (190.50, 71.12)]
ADD_JUNCTIONS = [(29.21, 44.45), (44.45, 52.07), (129.54, 71.12),
                 (129.54, 104.14), (140.97, 71.12), (140.97, 104.14),
                 (165.10, 71.12), (175.26, 71.12), (185.42, 71.12),
                 (195.58, 71.12)]


def block_end(t, i):
    """Index just past the s-expression that starts at i."""
    d = 0
    j = i
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


def edit_symbols(t):
    out, pos = [], 0
    while True:
        i = t.find("\t(symbol\n", pos)
        if i < 0:
            break
        e = block_end(t, i + 1)
        blk = t[i:e]
        m = re.search(r'\(property "Reference" "([^"]+)"', blk)
        ref = m.group(1) if m else None
        if ref in SYMS:
            x, y, rot, mir, props = SYMS[ref]
            # the symbol's own placement
            blk = re.sub(r"\n\t\t\(at [^\n]*\)",
                         "\n\t\t(at %s %s %d)" % (g(x), g(y), rot), blk, count=1)
            blk = re.sub(r"\n\t\t\(mirror [xy]\)", "", blk)
            if mir:
                blk = blk.replace("\n\t\t(at %s %s %d)" % (g(x), g(y), rot),
                                  "\n\t\t(at %s %s %d)\n\t\t(mirror %s)"
                                  % (g(x), g(y), rot, mir), 1)
            # each property: named ones get their own spot, hidden ones follow
            # the body so they never drift off on their own
            def fix(pm):
                name = pm.group(1)
                px, py, prot = props.get(name, (x, y, rot))
                return '(property "%s" %s\n\t\t\t(at %s %s %d)' % (
                    name, pm.group(2), g(px), g(py), prot)
            # unrolled string pattern - the naive "(?:[^"\\]|\\.)*" form
            # backtracks catastrophically on the GND symbols' \"GND\" description
            blk = re.sub(r'\(property "([^"]+)" ("[^"\\]*(?:\\.[^"\\]*)*")'
                         r'\n\t\t\t\(at [^\n]*\)', fix, blk)
            for pname, how in JUSTIFY.get(ref, {}).items():
                ps = blk.index('(property "%s" ' % pname)
                pe = block_end(blk, ps)
                blk = (blk[:ps]
                       + blk[ps:pe].replace("(justify left)", "(justify %s)" % how)
                       + blk[pe:])
        out.append(t[pos:i])
        out.append(blk)
        pos = e
    out.append(t[pos:])
    return "".join(out)


def edit_labels(t):
    def fix(m):
        name = m.group(1)
        if name not in LABELS:
            return m.group(0)
        x, y = LABELS[name]
        return '(label "%s"\n\t\t(at %s %s %s)' % (name, g(x), g(y), m.group(2))
    return re.sub(r'\(label "([^"]+)"\n\t\t\(at [-\d.]+ [-\d.]+ ([-\d.]+)\)', fix, t)


def norm(v):
    return round(float(v), 3)


def drop_blocks(t, kind, targets):
    """Remove every `kind` block whose key is in targets. Returns text, hits."""
    targets = {tuple(norm(c) for c in k) for k in targets}
    out, pos, hits = [], 0, set()
    marker = "\t(%s\n" % kind
    while True:
        i = t.find(marker, pos)
        if i < 0:
            break
        e = block_end(t, i + 1)
        blk = t[i:e]
        if kind == "wire":
            m = re.search(r"\(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)", blk)
            key = tuple(norm(v) for v in m.groups())
            key = min(key, key[2:] + key[:2])
        else:
            m = re.search(r"\(at ([-\d.]+) ([-\d.]+)\)", blk)
            key = tuple(norm(v) for v in m.groups())
        out.append(t[pos:i])
        if key in targets:
            hits.add(key)
        else:
            out.append(blk)
        pos = e
    out.append(t[pos:])
    return "".join(out), hits


def wire_block(x1, y1, x2, y2):
    return ("\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n"
            "\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            "\t\t(uuid \"%s\")\n\t)\n"
            % (g(x1), g(y1), g(x2), g(y2),
               uid("wire %g %g %g %g" % (x1, y1, x2, y2))))


def junction_block(x, y):
    return ("\t(junction\n\t\t(at %s %s)\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n"
            "\t\t(uuid \"%s\")\n\t)\n" % (g(x), g(y), uid("junction %g %g" % (x, y))))


def main():
    root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                   text=True).strip()
    os.chdir(root)
    base = subprocess.check_output(["git", "show", "HEAD:" + SHEET], text=True)
    t = base

    t = edit_symbols(t)
    t = edit_labels(t)

    t, hitw = drop_blocks(t, "wire", DEL_WIRES)
    t, hitj = drop_blocks(t, "junction", DEL_JUNCTIONS)
    missw = {tuple(norm(c) for c in min(w, w[2:] + w[:2])) for w in DEL_WIRES} - hitw
    missj = {tuple(norm(c) for c in j) for j in DEL_JUNCTIONS} - hitj
    if missw or missj:
        sys.exit("wires not found: %s\njunctions not found: %s" % (missw, missj))

    # new geometry goes in ahead of the first symbol, where the sheet keeps
    # its wires and junctions already
    anchor = t.index("\t(symbol\n")
    add = "".join(wire_block(*w) for w in ADD_WIRES) + \
          "".join(junction_block(*j) for j in ADD_JUNCTIONS)
    t = t[:anchor] + add + t[anchor:]

    with open(SHEET, "w", encoding="utf-8", newline="") as f:
        f.write(t)
    print("batch 1 applied: %d symbols moved, %d wires removed, %d added, "
          "%d junctions removed, %d added"
          % (len(SYMS), len(DEL_WIRES), len(ADD_WIRES),
             len(DEL_JUNCTIONS), len(ADD_JUNCTIONS)))


if __name__ == "__main__":
    main()
