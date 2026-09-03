#!/usr/bin/env python3
"""Round-2 batch, item 1: put U301 back to the LMR33630.

The captain overruled the reference-design part swap for U301 only. Everything
else round 1 did to power_rails stands: the dual test points, the horizontal 0R
links and ferrite, the vertical power LED, and no test point on a feedback node.

Restoration is verbatim from 48a5f4f, the commit before the swap, so U301, R304,
L301, C304, R315 and their two GND symbols come back with their original uuids
rather than as look-alikes.
"""
import os, re, subprocess, sys, uuid

SHEET = "hardware/kicad/faff2_cbs1/power_rails.kicad_sch"
BEFORE = "48a5f4f"          # review r1 batch 1 - the last tree with the LMR33630

# whole symbol blocks to take back from BEFORE
RESTORE_SYMS = ["U301", "R304", "L301", "C304", "R315", "#PWR307", "#PWR308"]
# lib_symbols the LMR33630 build needs back, and the ones only the swap used
LIB_RESTORE = ["Amodo_Inductors:IND_SMD_15uH_5.3A",
               "Amodo_Resistors:RES_TNF_22.1k_0603_0.1%"]
LIB_DROP = ["Amodo_Power_ICs:LMR51610XFDBVR", "Amodo_Inductors:IND_SMD_33uH",
            "Amodo_Resistors:RES_TNF_16.9k_0603_0.1%"]

DEL_WIRES = [   # the LMR51610 routing
    (60.96, 33.02, 60.96, 40.64),
    (76.20, 40.64, 99.06, 40.64), (99.06, 40.64, 99.06, 45.72),
    (76.20, 45.72, 88.90, 45.72), (88.90, 45.72, 88.90, 53.34),
    (76.20, 50.80, 80.01, 50.80), (80.01, 50.80, 80.01, 59.69),
    (80.01, 59.69, 127.00, 59.69),
]
ADD_WIRES = [   # the LMR33630 routing, including VCC, the pad and the PG leg
    (60.96, 33.02, 60.96, 43.18),
    (57.15, 57.15, 57.15, 59.69), (57.15, 57.15, 60.96, 57.15),
    (57.15, 64.77, 57.15, 67.31),
    (72.39, 67.31, 72.39, 71.12),
    (83.82, 43.18, 99.06, 43.18), (99.06, 43.18, 99.06, 45.72),
    (83.82, 48.26, 88.90, 48.26), (88.90, 48.26, 88.90, 53.34),
    (83.82, 59.69, 127.00, 59.69),
    (83.82, 54.61, 86.36, 54.61), (86.36, 54.61, 86.36, 78.74),
    (86.36, 78.74, 86.36, 81.28), (86.36, 86.36, 86.36, 88.90),
    (86.36, 88.90, 86.36, 93.98), (86.36, 93.98, 104.14, 93.98),
]
ADD_LABELS = [("RAIL_PGOOD", 104.14, 93.98)]

TEXT_EDITS = [
    ("(LMR51610, 400 kHz)", "(LMR33630, 400 kHz)"),
    ("+5V5   LMR51610 buck from V24_LOGIC. Pre-regulator only,",
     "+5V5   LMR33630 buck from V24_LOGIC. Pre-regulator only,"),
    ("RAIL_PGOOD is open drain from the +3V3 buck alone, through\\n"
     "       R316 - the LMR51610 pre-regulator has no PG pin.",
     "RAIL_PGOOD is open drain, the wired-AND of both converters\\n"
     "       through R315 / R316."),
]


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


def sym_ref(blk):
    m = re.search(r'\(property "Reference" "([^"]+)"', blk)
    return m.group(1) if m else None


def wire_block(x1, y1, x2, y2, ns):
    u = str(uuid.uuid5(ns, "review-r2-u301/wire %g %g %g %g" % (x1, y1, x2, y2)))
    return ("\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n"
            "\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            "\t\t(uuid \"%s\")\n\t)\n" % (g(x1), g(y1), g(x2), g(y2), u))


def main():
    root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                   text=True).strip()
    os.chdir(root)
    t = subprocess.check_output(["git", "show", "HEAD:" + SHEET], text=True)
    old = subprocess.check_output(["git", "show", "%s:%s" % (BEFORE, SHEET)],
                                  text=True)
    ns = uuid.UUID(re.search(r'\n\t\(uuid "([0-9a-f-]+)"\)', t).group(1))

    # ---- lib_symbols
    ls = t.index("\t(lib_symbols\n")
    le = block_end(t, ls + 1)
    blk = t[ls:le]
    for lib_id in LIB_DROP:
        i = blk.index('(symbol "%s"\n' % lib_id)
        s = blk.rindex("\t\t", 0, i)
        blk = blk[:s] + blk[block_end(blk, i):].lstrip("\n")
    add = ""
    for lib_id in LIB_RESTORE:
        i = old.index('(symbol "%s"\n' % lib_id)
        s = old.rindex("\t\t", 0, i)
        add += old[s:block_end(old, i)] + "\n"
    cut = blk.rindex("\t)")
    t = t[:ls] + blk[:cut] + add + blk[cut:] + t[le:]

    # ---- symbols: drop the swapped ones, splice the originals back verbatim
    restored = ""
    for i, e, sym in each_symbol(old):
        if sym_ref(sym) in RESTORE_SYMS:
            restored += sym
    found = [sym_ref(s) for _, _, s in each_symbol(old) if sym_ref(s) in RESTORE_SYMS]
    if sorted(found) != sorted(RESTORE_SYMS):
        sys.exit("not all originals found: %s" % sorted(set(RESTORE_SYMS) - set(found)))

    out, pos = [], 0
    for i, e, sym in each_symbol(t):
        out.append(t[pos:i])
        if sym_ref(sym) not in RESTORE_SYMS:
            out.append(sym)
        pos = e
    out.append(t[pos:])
    t = "".join(out)
    anchor = t.index("\t(symbol\n")
    t = t[:anchor] + restored + t[anchor:]

    # ---- wires
    def wkey(blk):
        m = re.search(r"\(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)", blk)
        k = tuple(round(float(v), 3) for v in m.groups())
        return min(k, k[2:] + k[:2])
    want = {wkey("(xy %g %g) (xy %g %g)" % w) for w in DEL_WIRES}
    out, pos, hit = [], 0, set()
    while True:
        i = t.find("\t(wire\n", pos)
        if i < 0:
            break
        e = block_end(t, i + 1)
        k = wkey(t[i:e])
        out.append(t[pos:i])
        if k in want:
            hit.add(k)
        else:
            out.append(t[i:e])
        pos = e
    out.append(t[pos:])
    t = "".join(out)
    if want - hit:
        sys.exit("wires not found: %s" % sorted(want - hit))

    anchor = t.index("\t(symbol\n")
    adds = "".join(wire_block(*w, ns=ns) for w in ADD_WIRES)
    for (nm, x, y) in ADD_LABELS:
        u = str(uuid.uuid5(ns, "review-r2-u301/label %s" % nm))
        adds += ('\t(label "%s"\n\t\t(at %s %s 0)\n\t\t(effects\n\t\t\t(font\n'
                 '\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n'
                 '\t\t)\n\t\t(uuid "%s")\n\t)\n' % (nm, g(x), g(y), u))
    t = t[:anchor] + adds + t[anchor:]

    for a_, b_ in TEXT_EDITS:
        if a_ not in t:
            sys.exit("text not found: %r" % a_[:60])
        t = t.replace(a_, b_, 1)

    with open(SHEET, "w", encoding="utf-8", newline="") as f:
        f.write(t)
    print("U301 reverted to LMR33630: %d symbols restored verbatim, "
          "%d wires removed, %d added" % (len(RESTORE_SYMS), len(DEL_WIRES),
                                          len(ADD_WIRES)))


if __name__ == "__main__":
    main()
