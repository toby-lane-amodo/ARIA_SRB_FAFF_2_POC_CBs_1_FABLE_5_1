#!/usr/bin/env python3
"""Retire the last two project-local pre-rotated passives.

The rotation rule is settled: rotating a part on the schematic is normal, and
needing an orientation is not a reason to make a library variant. Two variants
predated that and still had users - `RES_TF_39R_0603_H` and `RES_TF_0R_0603_H`,
one instance each on `ui_io`. Both instances move to the house symbol, rotated
90 with their field angles compensated to 270 so the reference and value still
render horizontal.

Pin order is preserved and therefore so is the netlist: the `_H` variant has
pin 1 at (0,0) and pin 2 at (5.08,0), and the house symbol at 90 deg puts pin 1
at (X,Y) and pin 2 at (X+5.08,Y) - pin 1 on the left either way. Only the
libsource, and the description string cached on the instance, change.

`faff2_passives.kicad_sym` held nothing else, so the file and its `sym-lib-table`
entry go with them.

Re-runnable from a pinned base.
"""
import os
import subprocess
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sch_edit as E

BASE = "06d0e8d"
D = "hardware/kicad/faff2_cbs1/"
LIBSRC = "/mnt/c/Amodo/AmodoKiCadLib/Amodo_Resistors.kicad_sym"

# (refdes, old lib_id, new lib_id)
SWAPS = [("R907", "faff2_passives:RES_TF_39R_0603_H",
          "Amodo_Resistors:RES_TF_39R_0603"),
         ("R915", "faff2_passives:RES_TF_0R_0603_H",
          "Amodo_Resistors:RES_TF_0R_0603")]
LOCAL_LIB = "faff2_passives"


def main():
    path = D + "ui_io.kicad_sch"
    text = E.normalise(subprocess.run(["git", "show", BASE + ":" + path],
                                      check=True, capture_output=True,
                                      text=True).stdout)
    src = open(LIBSRC, encoding="utf-8").read()
    for ref, old, new in SWAPS:
        text = E.set_lib_id(text, ref, new)
        # refresh the cached strings too: the local variant's description said
        # "horizontal variant", which is no longer what the part is
        text = E.sync_properties(text, ref, src, new.split(":", 1)[1])
        text = E.set_rotation(text, ref, 90, 270)
        text = E.embed_lib_symbol(text, src, new)
        text = E.del_lib_symbol(text, old)
    assert LOCAL_LIB not in text, "a faff2_passives reference survived on ui_io"
    open(path, "w", encoding="utf-8", newline="\n").write(text)
    print("ui_io: %s onto house symbols at 90 deg"
          % ", ".join(r for r, _o, _n in SWAPS))

    # the local library held nothing else
    lib = D + "faff2_passives.kicad_sym"
    if os.path.exists(lib):
        subprocess.run(["git", "rm", "-q", lib], check=True)
        print("removed %s" % lib)

    tbl = D + "sym-lib-table"
    t = open(tbl, encoding="utf-8").read()
    line = [l for l in t.splitlines() if '(name "%s")' % LOCAL_LIB in l]
    assert len(line) == 1, line
    t = t.replace(line[0] + "\n", "")
    open(tbl, "w", encoding="utf-8", newline="\n").write(t)
    print("sym-lib-table: %s entry removed" % LOCAL_LIB)


if __name__ == "__main__":
    main()
