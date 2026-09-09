#!/usr/bin/env python3
"""Routing step 4c -- no power rail leaves the board through a thin segment.

`connect_net` walks a width ladder: it tries the rail width, then 0.30, then
0.20, then 6 mil, and takes the first that fits.  That is the right behaviour
for the last hop onto a 0.5 mm-pitch pin, and the wrong one for a segment the
whole rail has to cross -- a 0.152 mm trace carries 0.61 A at a 10 degC rise
(setup S3), and +3V3 is designed for 1.5.

The segment that matters is a **bridge**: one whose removal splits the net, so
everything on the far side goes through it.  A bridge whose far side holds
nothing but decoupling capacitors and test points carries only that
capacitor's ripple and is left alone; a bridge with a real load behind it --
an IC supply pin, a connector, a regulator input, another net's series
element -- has to carry the rail.

Widening is done in place, `SetWidth` on the existing track, never a reroute:
the centreline already clears everything, so the only question is whether the
extra half-width still does, and `seg_ok` answers it against foreign copper
only (same-net copper is not an obstacle).  Each segment is grown to the
widest rung that fits, so a bridge that cannot reach the full rail width
still gets everything the channel has.

IPC-2221 external, 1 oz, 10 degC rise -- `docs/decisions/actuator-pcb-setup.md`
S3.  `--check` reports without touching the board.
"""
import argparse
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402
from route4_power import VIA_BUDGET  # noqa: E402

# width mm -> amps at 10 degC rise, 1 oz external (setup S3 table)
CAPACITY = [(0.1524, 0.61), (0.20, 0.75), (0.25, 0.88), (0.30, 1.00),
            (0.40, 1.24), (0.50, 1.45), (0.65, 1.75), (0.80, 2.05),
            (1.00, 2.39)]

# A pad behind a bridge that is only ever a bypass or a probe is not a load.
PASSIVE_PREFIX = ("C", "TP", "J50", "J30")


def need_width(amps):
    for w, a in CAPACITY:
        if a >= amps:
            return w
    return CAPACITY[-1][0]


def target(net, amps, loads):
    """What this particular bridge segment has to carry.

    The rail's design current is what the *trunk* carries.  A branch with one
    pad behind it carries that pad, and most of those pads are an IC supply
    pin or a sense input drawing milliamps -- U1101 pin 5 is VDRAIN, a
    high-impedance drain sense, and sizing its stub for the motor bus's 3 A
    would be theatre.  So a one-pad branch is held to the net-class width,
    which is the house floor for the class anyway (G3), and only a segment
    with the rail's real load behind it is sized from the current.

    Neither is a licence to go below the class width: that is the floor in
    both cases.
    """
    cls = R.net_width(net)
    if len(loads) <= 1:
        return cls, "branch"
    return max(cls, need_width(amps)), "trunk"


def islands_without(items, drop):
    keep = [it for i, it in enumerate(items) if i not in drop]
    uf = R._touch_graph(keep)
    groups = {}
    for i, it in enumerate(keep):
        groups.setdefault(uf.find(i), []).append(it)
    return [g for g in groups.values() if any(k == "pad" for k, *_ in g)]


def is_load(name):
    ref = name.split(".")[0]
    if ref.startswith("TP"):
        return False
    if ref.startswith("C") and not ref.startswith("CN"):
        return False
    return True


def bridges(board, net):
    """[(track index in board order, side pads)] for every bridge segment."""
    items = R.net_items(board, net)
    base = islands_without(items, set())
    out = []
    for i, it in enumerate(items):
        if it[0] != "track":
            continue
        cut = islands_without(items, {i})
        if len(cut) <= len(base):
            continue
        smaller = min(cut, key=lambda g: sum(1 for k, *_ in g if k == "pad"))
        out.append((it[1], [x[1] for x in smaller if x[0] == "pad"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    board = R.load()
    obst = R.Obstacles(board)

    by_key = {}
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            continue
        p, q = R.pt(t.GetStart()), R.pt(t.GetEnd())
        by_key.setdefault(
            f"{p[0]:.2f},{p[1]:.2f}-{q[0]:.2f},{q[1]:.2f}", []).append(t)

    print(f"{'net':<30} {'I':>5}  bottlenecks "
          f"(trunk = sized from the rail current, branch = class floor)")
    thin, fixed, stuck = 0, 0, []
    for net, amps in sorted(VIA_BUDGET.items(), key=lambda kv: -kv[1]):
        try:
            nc = R.netcode(board, net)
        except KeyError:
            continue
        rows = []
        for key, pads in bridges(board, net):
            loads = [p for p in pads if is_load(p)]
            want, kind = target(net, amps, loads)
            for t in by_key.get(key, []):
                if t.GetNetCode() != nc:
                    continue
                w = R.tomm(t.GetWidth())
                if w >= want - 1e-6:
                    continue
                if not loads:
                    continue
                thin += 1
                got = w
                if not a.check:
                    for cand in [c for c, _ in reversed(CAPACITY)
                                 if c <= want and c > w]:
                        s, e = R.pt(t.GetStart()), R.pt(t.GetEnd())
                        if R.seg_ok(obst, s, e, cand, nc, t.GetLayer()):
                            t.SetWidth(R.mm(cand))
                            obst.add_seg(s, e, cand / 2.0, t.GetLayer(), nc)
                            got = cand
                            break
                rows.append((key, w, got, want, kind, loads[:4]))
                if got >= want - 1e-6:
                    fixed += 1
                else:
                    stuck.append((net, key, got, want, kind, loads[:4]))
        if rows:
            cw = R.net_width(net)
            note = ("" if cw >= need_width(amps) - 1e-6 else
                    f"   (class {cw:.2f} mm carries "
                    f"{[a for w, a in CAPACITY if abs(w - cw) < 1e-6][0]:.2f} A"
                    f" at a 10 degC rise; the trunk wants "
                    f"{need_width(amps):.2f} mm)")
            print(f"{net:<30} {amps:5.2f}{note}")
            for key, w, got, want, kind, loads in rows:
                arrow = "" if got == w else f" -> {got:.3f}"
                print(f"    {kind:<6} {key:<32} {w:.3f}{arrow} "
                      f"of {want:.2f}  behind it: {loads}")

    if not a.check and fixed:
        R.refill(board)
        R.save(board)
    print(f"\n{thin} load-bearing bridge segments below their rail width; "
          f"{fixed} widened to it")
    if stuck:
        print("STILL BELOW -- the channel has no more room, needs the "
              "engineer:")
        for net, key, got, want, kind, loads in stuck:
            print(f"   {kind:<6} {net} {key}  {got:.3f} of {want:.2f}  "
                  f"behind: {loads}")
    return 1 if stuck else 0


if __name__ == "__main__":
    sys.exit(main())
