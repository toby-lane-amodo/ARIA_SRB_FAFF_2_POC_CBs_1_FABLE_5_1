#!/usr/bin/env python3
"""Per-net node sets from a kicad-cli netlist, and the invariance proof.

The proof that a *geometry* rework changed nothing electrical is not "ERC is
still clean" - ERC passes happily on a wire that merged two nets. It is that
every net still has exactly the same set of (refdes, pin) endpoints. Net
*names* may legitimately change (KiCad renames an unlabelled net after its
first node), so the comparison is over node sets as a multiset, not a dict
keyed by name.

    python3 tools/netlist_nodes.py before.net after.net     # compare
    python3 tools/netlist_nodes.py one.net                  # summarise
    python3 tools/netlist_nodes.py one.net --net +3V3       # list one net

Exit 0 when identical, 1 when not - safe in a shell &&-chain.
"""
import re
import sys
from collections import Counter

NET = re.compile(r'\(net \(code "[^"]*"\) \(name "([^"]*)"\)')
NODE = re.compile(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)')


def node_sets(path):
    """{net name: frozenset((ref, pin))} for every net in the netlist."""
    text = open(path, encoding="utf-8").read()
    starts = [(m.start(), m.group(1)) for m in NET.finditer(text)]
    out = {}
    for i, (pos, name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        out[name] = frozenset(NODE.findall(text[pos:end]))
    return out


def components(path):
    text = open(path, encoding="utf-8").read()
    body = text[text.index("(components"):text.index("(libparts")]
    return set(re.findall(r'\(comp \(ref "([^"]+)"\)', body))


def compare(a, b):
    na, nb = node_sets(a), node_sets(b)
    ca, cb = Counter(na.values()), Counter(nb.values())
    if ca == cb:
        print(f"NODE SETS IDENTICAL ({len(na)} nets)")
        return 0

    print(f"NODE SETS DIFFER: {len(na)} nets -> {len(nb)} nets")
    # Report by name where the name survived, since that is what a human reads.
    for name in sorted(set(na) | set(nb)):
        if na.get(name) != nb.get(name):
            gone = (na.get(name, frozenset())) - (nb.get(name, frozenset()))
            new = (nb.get(name, frozenset())) - (na.get(name, frozenset()))
            print(f"  {name}")
            if gone:
                print(f"    lost  {sorted(gone)}")
            if new:
                print(f"    gained {sorted(new)}")
    lost_c, new_c = components(a) - components(b), components(b) - components(a)
    if lost_c:
        print(f"  components removed: {sorted(lost_c)}")
    if new_c:
        print(f"  components added:   {sorted(new_c)}")
    return 1


def main(argv):
    if len(argv) >= 2 and argv[1] == "--net":
        for name, nodes in sorted(node_sets(argv[0]).items()):
            if name == argv[2]:
                print(f"{name} ({len(nodes)} nodes)")
                for ref, pin in sorted(nodes):
                    print(f"  {ref}.{pin}")
        return 0
    if len(argv) == 1:
        ns = node_sets(argv[0])
        print(f"{len(components(argv[0]))} components, {len(ns)} nets")
        return 0
    return compare(argv[0], argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
