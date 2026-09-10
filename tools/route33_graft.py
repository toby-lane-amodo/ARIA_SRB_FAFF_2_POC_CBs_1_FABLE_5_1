#!/usr/bin/env python3
"""Graft an autorouter's clean nets onto our board, and only the clean ones.

Round 3 ran KiCadRoutingTools over the 60 nets our own router left open, with
our fab floor pinned and its sub-floor rescue pass disabled.  It closed 15 and
the board came back with 166 `clearance` / `hole_clearance` violations that
ours does not have -- and 154 of those, 93%, involve a net it had just routed.
Ten of its fifteen wins are wins only because it drove through copper.

Five are real: it found legal paths for nets our router could not, including
one this project had classed as bounded by immovable copper and two whose pads
graded as having no legal cell to leave at all.  Those five are worth having
and the other ten are not, so this takes the named nets and nothing else.

For each grafted net the tool's copper *replaces* ours wholesale, which is
exact rather than clever: the run used `--keep-input-copper`, so the tool's
set for a net is our copper plus its additions.  Deletion runs in a child
interpreter -- `board.Remove()` mid-script poisons SWIG type resolution.

The graft is only worth keeping if it survives the same bar as everything
else, so this reports unconnected before and after and changes nothing until
`--yes`.
"""
import argparse
import json
import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import route_lib as R  # noqa: E402

CHILD = '''
import json, sys
sys.path.insert(0, {here!r})
import pcbnew, route_lib as R
nets = set(json.loads({nets!r}))
src = pcbnew.LoadBoard({src!r})
b = pcbnew.LoadBoard(R.PCB)
dropped = [t for t in b.GetTracks() if t.GetNetname() in nets]
for t in dropped:
    b.Remove(t)
added = 0
for t in src.GetTracks():
    n = t.GetNetname()
    if n not in nets:
        continue
    try:
        nc = R.netcode(b, n)
    except KeyError:
        continue
    if isinstance(t, pcbnew.PCB_VIA):
        R.add_via(b, R.pt(t.GetPosition()), nc)
    else:
        R.add_track(b, R.pt(t.GetStart()), R.pt(t.GetEnd()),
                    R.tomm(t.GetWidth()), t.GetLayer(), nc)
    added += 1
print(json.dumps({{"dropped": len(dropped), "added": added}}))
R.refill(b)
R.save(b)
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True,
                    help="the autorouter's output board")
    ap.add_argument("--nets", required=True,
                    help="comma-separated nets to graft -- the clean ones")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    nets = [n for n in a.nets.split(",") if n.strip()]

    before = R.unconnected(R.load())
    print(f"unconnected before {before}; grafting {len(nets)} nets")
    for n in nets:
        print(f"   {n}")
    if not a.yes:
        print("dry run -- pass --yes")
        return 0

    src = CHILD.format(here=HERE, nets=json.dumps(nets), src=a.src)
    out = subprocess.run([sys.executable, "-c", src], capture_output=True,
                         text=True)
    if out.returncode != 0:
        print(out.stdout, out.stderr, file=sys.stderr)
        raise SystemExit("graft failed")
    for line in out.stdout.splitlines():
        if line.strip().startswith("{"):
            d = json.loads(line.strip())
            print(f"   dropped {d['dropped']} of ours, added {d['added']}")
    after = R.unconnected(R.load())
    print(f"unconnected {before} -> {after}")
    return 0 if after <= before else 1


if __name__ == "__main__":
    sys.exit(main())
