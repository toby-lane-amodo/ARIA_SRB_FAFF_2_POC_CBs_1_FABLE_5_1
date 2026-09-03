#!/usr/bin/env python3
"""Round-2 batch, item 2: put power_rails' PWR_FLAGs at their regulators.

"Can power flags on the power_rails sheet be placed near the regulators, rather
than on their own?" - they were in a column of their own in block D, each one
hung off a duplicate power symbol that existed only to give it a net. Each flag
now taps the rail it declares, on the output side of that rail's 0R link, and
the four duplicate power symbols go with the column.

The flags for +5V5 and +3V3 sit on the post-link run rather than the buck output,
because before the link is a different net.
"""
import os, re, subprocess, sys, uuid

SHEET = "hardware/kicad/faff2_cbs1/power_rails.kicad_sch"

# ref -> (flag pin x, y, the rail wire it taps, the split point)
MOVE_FLAGS = {
    "#FLG344": (186.69, 50.80,  (182.88, 53.34, 190.50, 53.34)),   # +5V5
    "#FLG345": (287.02, 81.28,  (281.94, 83.82, 292.10, 83.82)),   # +5V
    "#FLG347": (388.62, 81.28,  (383.54, 83.82, 393.70, 83.82)),   # +5VA
    "#FLG349": (186.69, 158.75, (182.88, 161.29, 190.50, 161.29)), # +3V3
    "#FLG351": (276.86, 179.07, (264.16, 181.61, 287.02, 181.61)), # +3V3A
}
# the duplicate power symbols the old column hung on; each rail already has one
# at its output (#PWR317, #PWR322, #PWR334, #PWR337)
DELETE = ["#PWR346", "#PWR348", "#PWR350", "#PWR352"]
DEL_LABELS = [("+5V5", 360.68, 198.12)]
DEL_WIRES = [(353.06, 198.12, 360.68, 198.12), (353.06, 207.01, 360.68, 207.01),
             (353.06, 215.90, 360.68, 215.90), (353.06, 224.79, 360.68, 224.79),
             (353.06, 233.68, 360.68, 233.68)]

OLD_NOTE = ("POWER SOURCE DECLARATIONS\\nOne PWR_FLAG per rail produced here;\\n"
            "no other sheet may add one for these nets.")
NEW_NOTE = ("POWER SOURCE DECLARATIONS\\nOne PWR_FLAG per rail produced here, at the\\n"
            "regulator that makes it, on the load side of\\nthat rail's 0R link. "
            "No other sheet may add\\none for these nets.")


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


def each(t, marker):
    pos = 0
    while True:
        i = t.find(marker, pos)
        if i < 0:
            return
        e = block_end(t, i + 1)
        yield i, e, t[i:e]
        pos = e


def wire_block(x1, y1, x2, y2, ns):
    u = str(uuid.uuid5(ns, "review-r2-flags/wire %g %g %g %g" % (x1, y1, x2, y2)))
    return ("\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n"
            "\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            "\t\t(uuid \"%s\")\n\t)\n" % (g(x1), g(y1), g(x2), g(y2), u))


def junction_block(x, y, ns):
    u = str(uuid.uuid5(ns, "review-r2-flags/junction %g %g" % (x, y)))
    return ("\t(junction\n\t\t(at %s %s)\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n"
            "\t\t(uuid \"%s\")\n\t)\n" % (g(x), g(y), u))


def main():
    root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                   text=True).strip()
    os.chdir(root)
    t = subprocess.check_output(["git", "show", "HEAD:" + SHEET], text=True)
    ns = uuid.UUID(re.search(r'\n\t\(uuid "([0-9a-f-]+)"\)', t).group(1))

    # ---- symbols: move the flags, drop the duplicate power symbols
    out, pos, seen = [], 0, set()
    for i, e, sym in each(t, "\t(symbol\n"):
        m = re.search(r'\(property "Reference" "([^"]+)"', sym)
        ref = m.group(1) if m else ""
        out.append(t[pos:i])
        if ref in DELETE:
            pass
        elif ref in MOVE_FLAGS:
            x, y, _ = MOVE_FLAGS[ref]
            sym = re.sub(r"\n\t\t\(at [-\d.]+ [-\d.]+ [-\d.]+\)",
                         "\n\t\t(at %s %s 0)" % (g(x), g(y)), sym, count=1)
            # every field rides with the symbol; the Value sits above the flag
            def fix(pm, x=x, y=y):
                dy = -3.81 if pm.group(1) == "Value" else 0.0
                return '(property "%s" %s\n\t\t\t(at %s %s 0)' % (
                    pm.group(1), pm.group(2), g(x), g(y + dy))
            sym = re.sub(r'\(property "([^"]+)" ("[^"\\]*(?:\\.[^"\\]*)*")'
                         r'\n\t\t\t\(at [^\n]*\)', fix, sym)
            out.append(sym)
            seen.add(ref)
        else:
            out.append(sym)
        pos = e
    out.append(t[pos:])
    t = "".join(out)
    if set(MOVE_FLAGS) - seen:
        sys.exit("flags not found: %s" % sorted(set(MOVE_FLAGS) - seen))

    # ---- labels
    for (nm, x, y) in DEL_LABELS:
        old = '\t(label "%s"\n\t\t(at %s %s 0)' % (nm, g(x), g(y))
        i = t.find(old)
        if i < 0:
            sys.exit("label not found: %s" % nm)
        t = t[:i] + t[block_end(t, i + 1):]

    # ---- wires: drop the old column, split each tapped rail, add the stubs
    def wkey(blk):
        m = re.search(r"\(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)", blk)
        k = tuple(round(float(v), 3) for v in m.groups())
        return min(k, k[2:] + k[:2])
    drop = {wkey("(xy %g %g) (xy %g %g)" % w) for w in DEL_WIRES}
    drop |= {wkey("(xy %g %g) (xy %g %g)" % r) for _, _, r in MOVE_FLAGS.values()}
    out, pos, hit = [], 0, set()
    for i, e, blk in each(t, "\t(wire\n"):
        k = wkey(blk)
        out.append(t[pos:i])
        if k in drop:
            hit.add(k)
        else:
            out.append(blk)
        pos = e
    out.append(t[pos:])
    t = "".join(out)
    if drop - hit:
        sys.exit("wires not found: %s" % sorted(drop - hit))

    adds = ""
    for ref, (x, y, (rx1, ry1, rx2, ry2)) in MOVE_FLAGS.items():
        adds += wire_block(rx1, ry1, x, ry1, ns)      # rail, split at the tap
        adds += wire_block(x, ry1, rx2, ry2, ns)
        adds += wire_block(x, y, x, ry1, ns)          # the stub up to the flag
        adds += junction_block(x, ry1, ns)
    anchor = t.index("\t(symbol\n")
    t = t[:anchor] + adds + t[anchor:]

    if OLD_NOTE not in t:
        sys.exit("declarations note not found")
    t = t.replace(OLD_NOTE, NEW_NOTE, 1)

    with open(SHEET, "w", encoding="utf-8", newline="") as f:
        f.write(t)
    print("flags moved: %d to their regulators, %d duplicate power symbols "
          "dropped, %d column wires removed" % (len(MOVE_FLAGS), len(DELETE),
                                                len(DEL_WIRES)))


if __name__ == "__main__":
    main()
