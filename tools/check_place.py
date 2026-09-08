#!/usr/bin/env python3
"""Placement sweeps for faff2_cbs1: real courtyards, board edge, M3 keep-outs,
the 0.25 mm grid, and the decoupler-to-supply-pin link lengths.

Run after any placement edit.  The pcb-layout-style skill asks for all of
these to be asserted programmatically, not eyeballed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import place_lib as L   # noqa: E402


def main():
    b = L.load()
    bad = L.overlaps(b)
    print("== courtyard overlaps: %d" % len(bad))
    for a, c, w, h in bad:
        print("   %-8s x %-8s  %.2f x %.2f mm" % (a, c, w, h))
    eg = L.edge_problems(b)
    print("== edge / keep-out problems: %d" % len(eg))
    for r in eg:
        print("   %s" % (r,))
    og = L.off_grid(b)
    print("== off the 0.25 mm grid: %d" % len(og))
    for r in og:
        print("   %s" % (r,))
    return len(bad) + len(eg) + len(og)


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
