#!/usr/bin/env python3
"""Round-2 batch, items 4-7: four per-sheet placement fixes.

  4  linear_encoder - "space out U601E and U601A as the power and GND flags are
     getting a little close". U601A's GND body ended at y=166.37 and U601E's
     +3V3 body started at exactly 166.37; the whole U601E group drops 7.62.
  5  temp_sense - "space out the connections around C704 etc ... Also the wires
     should not cross the box title." C704/C705 and their grounds move up 5.08,
     off the REFP row; the CHANNEL 2 title is shortened so the three verticals
     at x=137.16/139.70/142.24 no longer run through it.
  6  ui_io - R915's fields sat on its own body: it is the horizontal 0R variant,
     and its fields were still on the vertical pattern.
  7  motor_drive - "By RT1101 there are GND flags hanging below the bounding
     graphic box." Both grounds move up so symbol and text sit inside.
"""
import os, re, subprocess, sys

DIR = "hardware/kicad/faff2_cbs1"

# sheet -> {ref: (x, y, rot, {property: (x, y, rot)})}
MOVE = {
    "linear_encoder": {
        "U601:5":  (162.56, 180.34, 0, {"Reference": (162.56, 179.44, 0),
                                        "Value":     (162.56, 186.04, 0)}),
        "#PWR617": (154.94, 176.53, 0, {"Value": (154.94, 172.72, 0)}),
        "#PWR618": (157.48, 191.77, 0, {"Value": (157.48, 195.58, 0)}),
    },
    "temp_sense": {
        "C704":    (109.22, 104.14, 0, {"Reference": (111.51, 103.50, 0),
                                        "Value":     (111.51, 105.41, 0)}),
        "#PWR706": (109.22, 106.68, 0, {"Value": (109.22, 110.49, 0)}),
        "C705":    (119.38, 104.14, 0, {"Reference": (121.67, 103.50, 0),
                                        "Value":     (121.67, 105.41, 0)}),
        "#PWR707": (119.38, 106.68, 0, {"Value": (119.38, 110.49, 0)}),
    },
    "ui_io": {
        # the _H variant's own field pattern: reference above, value below
        "R915":    (190.50, 194.31, 0, {"Reference": (193.04, 192.28, 0),
                                        "Value":     (193.04, 196.60, 0)}),
    },
    "motor_drive": {
        "#PWR1109": (30.48, 138.43, 0, {"Value": (30.48, 142.24, 0)}),
        "#PWR1110": (41.91, 138.43, 0, {"Value": (41.91, 142.24, 0)}),
    },
}

DEL_WIRES = {
    "linear_encoder": [(154.94, 168.91, 154.94, 173.99), (154.94, 173.99, 160.02, 173.99),
                       (157.48, 176.53, 157.48, 184.15), (157.48, 176.53, 160.02, 176.53)],
    "temp_sense":     [(109.22, 91.44, 109.22, 106.68), (119.38, 96.52, 119.38, 106.68)],
    "motor_drive":    [(30.48, 137.16, 30.48, 140.97), (41.91, 137.16, 41.91, 140.97)],
}
ADD_WIRES = {
    "linear_encoder": [(154.94, 176.53, 154.94, 181.61), (154.94, 181.61, 160.02, 181.61),
                       (157.48, 184.15, 157.48, 191.77), (157.48, 184.15, 160.02, 184.15)],
    "temp_sense":     [(109.22, 91.44, 109.22, 101.60), (119.38, 96.52, 119.38, 101.60)],
    "motor_drive":    [(30.48, 137.16, 30.48, 138.43), (41.91, 137.16, 41.91, 138.43)],
}

# a no_connect rides with the pin it caps
MOVE_NOCONNECT = {"linear_encoder": [((168.91, 175.26), (168.91, 182.88))]}

TEXT_EDITS = {
    # 29 characters at size 1.778 reach x=135.9, clear of the vertical at 137.16
    "temp_sense": [('"CHANNEL 2 FILTER AND SHARED REFERENCE"',
                    '"CHANNEL 2 FILTER + SHARED REF"')],
}


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


def wire_block(x1, y1, x2, y2, seed):
    import uuid
    u = str(uuid.uuid5(uuid.UUID(seed), "r2-layout/%g %g %g %g" % (x1, y1, x2, y2)))
    return ("\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n"
            "\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            "\t\t(uuid \"%s\")\n\t)\n" % (g(x1), g(y1), g(x2), g(y2), u))


def main():
    root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                   text=True).strip()
    os.chdir(root)
    total = 0
    for name in sorted(set(list(MOVE) + list(DEL_WIRES) + list(TEXT_EDITS))):
        path = "%s/%s.kicad_sch" % (DIR, name)
        t = subprocess.check_output(["git", "show", "HEAD:" + path], text=True)
        seed = re.search(r'\n\t\(uuid "([0-9a-f-]+)"\)', t).group(1)

        out, pos, seen = [], 0, set()
        for i, e, sym in each(t, "\t(symbol\n"):
            m = re.search(r'\(property "Reference" "([^"]+)"', sym)
            ref = m.group(1) if m else ""
            unit = re.search(r"\n\t\t\(unit (\d+)\)", sym)
            key = "%s:%s" % (ref, unit.group(1)) if unit else ref
            mk = key if key in MOVE.get(name, {}) else ref
            spec = MOVE.get(name, {}).get(mk)
            out.append(t[pos:i])
            if spec:
                x, y, rot, fl = spec
                sym = re.sub(r"\n\t\t\(at [-\d.]+ [-\d.]+ [-\d.]+\)",
                             "\n\t\t(at %s %s %d)" % (g(x), g(y), rot), sym, count=1)

                def fix(pm, x=x, y=y, rot=rot, fl=fl):
                    nm = pm.group(1)
                    px, py, prot = fl.get(nm, (x, y, rot))
                    return '(property "%s" %s\n\t\t\t(at %s %s %d)' % (
                        nm, pm.group(2), g(px), g(py), prot)
                sym = re.sub(r'\(property "([^"]+)" ("[^"\\]*(?:\\.[^"\\]*)*")'
                             r'\n\t\t\t\(at [^\n]*\)', fix, sym)
                seen.add(mk)
            out.append(sym)
            pos = e
        out.append(t[pos:])
        t = "".join(out)
        want = set(MOVE.get(name, {}))
        if want - seen:
            sys.exit("%s: symbols not found for %s" % (name, sorted(want - seen)))

        if name in DEL_WIRES:
            def wkey(b):
                m = re.search(r"\(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)", b)
                k = tuple(round(float(v), 3) for v in m.groups())
                return min(k, k[2:] + k[:2])
            drop = {wkey("(xy %g %g) (xy %g %g)" % w) for w in DEL_WIRES[name]}
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
                sys.exit("%s: wires not found %s" % (name, sorted(drop - hit)))
            anchor = t.index("\t(symbol\n")
            t = (t[:anchor]
                 + "".join(wire_block(*w, seed=seed) for w in ADD_WIRES[name])
                 + t[anchor:])

        for (ox, oy), (nx, ny) in MOVE_NOCONNECT.get(name, []):
            # coordinates are written with trailing zeros here, so match loosely
            pat = re.compile(r"\t\(no_connect\n\t\t\(at 0*%s0* 0*%s0*\)"
                             % (re.escape(g(ox)), re.escape(g(oy))))
            if not pat.search(t):
                sys.exit("%s: no_connect not found at %g,%g" % (name, ox, oy))
            t = pat.sub("\t(no_connect\n\t\t(at %s %s)" % (g(nx), g(ny)), t, count=1)

        for old, new in TEXT_EDITS.get(name, []):
            if old not in t:
                sys.exit("%s: text not found %r" % (name, old[:50]))
            t = t.replace(old, new, 1)

        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(t)
        n = len(MOVE.get(name, {})) + len(DEL_WIRES.get(name, []))
        print("  %-16s %d symbols moved, %d wires rerouted" %
              (name, len(MOVE.get(name, {})), len(DEL_WIRES.get(name, []))))
        total += n
    print("items 4-7 applied (%d edits)" % total)


if __name__ == "__main__":
    main()
