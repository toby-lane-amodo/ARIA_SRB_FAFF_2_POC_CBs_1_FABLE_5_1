#!/usr/bin/env python3
"""Round-2 batch, item 3b: series resistors on the motor encoder and hall lines.

The ESD audit behind this is in docs/decisions/actuator-sch-review-r1.md. Short
version: the design's protection policy is exposure-based and already written
down - clamps on the pins exposed outside the enclosure and on the one hot-plugged
connector - and every other external line bounds its current with a series
resistor and an RC into a device that can take it. Six lines did not:
J1101/J1102's encoder and hall signals ran connector -> pull-up -> MCU pin with
nothing in between, while the equally internal limit harness gets 1k + 100R + 10n
and the buttons get 100R + 100n. This closes that inconsistency at the cheap end.

A pre-rotated RES_TF_100R_0603_H joins faff2_passives.kicad_sym, per AGENTS.md,
rather than rotating six instances.
"""
import os, re, subprocess, sys, uuid

SHEET = "hardware/kicad/faff2_cbs1/motor_drive.kicad_sch"
LIBFILE = "hardware/kicad/faff2_cbs1/faff2_passives.kicad_sym"
LIB_ID = "faff2_passives:RES_TF_100R_0603_H"

# ref -> (x of pin 1, y, the wire it splits: junction x -> label x)
NEW_R = {
    "R1128": (81.28, 190.50, 62.23, 91.44),   # MOTOR_ENCODER_A
    "R1129": (81.28, 204.47, 69.85, 91.44),   # MOTOR_ENCODER_B
    "R1130": (81.28, 218.44, 77.47, 91.44),   # MOTOR_ENCODER_I
    "R1131": (81.28, 236.22, 62.23, 91.44),   # HALL1
    "R1132": (81.28, 250.19, 69.85, 91.44),   # HALL2
    "R1133": (81.28, 264.16, 77.47, 91.44),   # HALL3
}

NOTE_OLD = ("*Pull-ups go to +3V3, never to VENC.*")   # marker only, not edited
SHEET_NOTE_OLD = ("J102 A/B/Z -> TIM3 CH1/CH2/CH3 (PC6/PC7/PC8).  "
                  "J103 halls -> PE14/PD14/PD15 (GPIO).\\n"
                  "Motor not fixed (DEC-0004): this pinout suits every candidate "
                  "BLDC in the design log.")
SHEET_NOTE_NEW = ("J102 A/B/Z -> TIM3 CH1/CH2/CH3 (PC6/PC7/PC8).  "
                  "J103 halls -> PE14/PD14/PD15 (GPIO).\\n"
                  "Motor not fixed (DEC-0004): this pinout suits every candidate "
                  "BLDC in the design log.\\n"
                  "R1128..R1133 100R bound the current into the six MCU pins, the "
                  "same treatment the\\nlimit and button harnesses get. The cable "
                  "is internal, so no TVS array - see the\\nESD audit in "
                  "docs/decisions/actuator-sch-review-r1.md.")

SYM_DEF = '''	(symbol "RES_TF_100R_0603_H"
		(pin_numbers
			(hide yes)
		)
		(pin_names
			(hide yes)
		)
		(exclude_from_sim no)
		(in_bom yes)
		(on_board yes)
		(property "Reference" "R"
			(at 2.54 2.032 0)
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)
		(property "Value" "100R"
			(at 2.54 -2.286 0)
			(effects
				(font
					(size 1.27 1.27)
				)
			)
		)
		(property "Footprint" "Amodo:R_0603_1608Metric"
			(at 0 0 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
		(property "Datasheet" "https://www.mouser.co.uk/datasheet/2/315/AOA0000C304-1149620.pdf"
			(at 0 0 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
		(property "Description" "SMD Thick Film Resistor 100R 0603 1% 100mW - horizontal variant"
			(at 0 0 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
		(property "mpn" "ERJ-3EKF1000V"
			(at 0 0 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
		(property "gpn" "GPR0603100R"
			(at 0 0 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
		(property "SymLifecycle" "draft"
			(at 0 0 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)
		(symbol "RES_TF_100R_0603_H_0_1"
			(rectangle
				(start -1.016 1.016)
				(end 6.096 -1.016)
				(stroke
					(width 0.254)
					(type default)
				)
				(fill
					(type none)
				)
			)
		)
		(symbol "RES_TF_100R_0603_H_1_1"
			(pin passive line
				(at 0 0 0)
				(length 1.016)
				(name "~"
					(effects
						(font
							(size 1.27 1.27)
						)
					)
				)
				(number "1"
					(effects
						(font
							(size 1.27 1.27)
						)
					)
				)
			)
			(pin passive line
				(at 5.08 0 180)
				(length 1.016)
				(name "~"
					(effects
						(font
							(size 1.27 1.27)
						)
					)
				)
				(number "2"
					(effects
						(font
							(size 1.27 1.27)
						)
					)
				)
			)
		)
	)
'''


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


def main():
    root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                   text=True).strip()
    os.chdir(root)

    # ---- the pre-rotated 100R joins the project passives library
    lib = subprocess.check_output(["git", "show", "HEAD:" + LIBFILE], text=True)
    if 'RES_TF_100R_0603_H' not in lib:
        cut = lib.rindex(")")
        lib = lib[:cut] + SYM_DEF + lib[cut:]
    with open(LIBFILE, "w", encoding="utf-8", newline="") as f:
        f.write(lib)

    t = subprocess.check_output(["git", "show", "HEAD:" + SHEET], text=True)
    ns = uuid.UUID(re.search(r'\n\t\(uuid "([0-9a-f-]+)"\)', t).group(1))
    ipath = re.search(r'\(path "([^"]+)"', t).group(1)

    def uid(k):
        return str(uuid.uuid5(ns, "review-r2-esd/" + k))

    # ---- embed the symbol so the sheet is self-contained
    body = SYM_DEF.split("\n")
    body[0] = '\t\t(symbol "%s"' % LIB_ID
    embedded = "\n".join([body[0]] + ["\t" + l for l in body[1:] if l]) + "\n"
    ls = t.index("\t(lib_symbols\n")
    le = block_end(t, ls + 1)
    blk = t[ls:le]
    cut = blk.rindex("\t)")
    t = t[:ls] + blk[:cut] + embedded + blk[cut:] + t[le:]

    # ---- split each run and drop the resistor in
    def wkey(b):
        m = re.search(r"\(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)", b)
        k = tuple(round(float(v), 3) for v in m.groups())
        return min(k, k[2:] + k[:2])
    drop = {wkey("(xy %g %g) (xy %g %g)" % (jx, y, lx, y))
            for (x, y, jx, lx) in NEW_R.values()}
    out, pos, hit = [], 0, set()
    while True:
        i = t.find("\t(wire\n", pos)
        if i < 0:
            break
        e = block_end(t, i + 1)
        k = wkey(t[i:e])
        out.append(t[pos:i])
        if k in drop:
            hit.add(k)
        else:
            out.append(t[i:e])
        pos = e
    out.append(t[pos:])
    t = "".join(out)
    if drop - hit:
        sys.exit("runs not found: %s" % sorted(drop - hit))

    adds = ""
    for ref, (x, y, jx, lx) in NEW_R.items():
        for (x1, y1, x2, y2) in ((jx, y, x, y), (x + 5.08, y, lx, y)):
            adds += ("\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n"
                     "\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
                     "\t\t(uuid \"%s\")\n\t)\n"
                     % (g(x1), g(y1), g(x2), g(y2),
                        uid("wire %s %g %g %g %g" % (ref, x1, y1, x2, y2))))
        props = [("Reference", ref, x + 2.54, y - 2.032, False),
                 ("Value", "100R", x + 2.54, y + 2.286, False),
                 ("Footprint", "Amodo:R_0603_1608Metric", x, y, True),
                 ("Datasheet",
                  "https://www.mouser.co.uk/datasheet/2/315/AOA0000C304-1149620.pdf",
                  x, y, True),
                 ("Description",
                  "SMD Thick Film Resistor 100R 0603 1% 100mW - horizontal variant",
                  x, y, True),
                 ("mpn", "ERJ-3EKF1000V", x, y, True),
                 ("gpn", "GPR0603100R", x, y, True),
                 ("SymLifecycle", "draft", x, y, True)]
        L = ["\t(symbol", '\t\t(lib_id "%s")' % LIB_ID,
             "\t\t(at %s %s 0)" % (g(x), g(y)), "\t\t(unit 1)",
             "\t\t(exclude_from_sim no)", "\t\t(in_bom yes)", "\t\t(on_board yes)",
             "\t\t(dnp no)", "\t\t(fields_autoplaced no)",
             '\t\t(uuid "%s")' % uid("sym " + ref)]
        for (pn, pv, px, py, hide) in props:
            L += ['\t\t(property "%s" "%s"' % (pn, pv),
                  "\t\t\t(at %s %s 0)" % (g(px), g(py)),
                  "\t\t\t(effects", "\t\t\t\t(font", "\t\t\t\t\t(size 1.27 1.27)",
                  "\t\t\t\t)"]
            if hide:
                L.append("\t\t\t\t(hide yes)")
            L += ["\t\t\t)", "\t\t)"]
        for pn in ("1", "2"):
            L += ['\t\t(pin "%s"' % pn,
                  '\t\t\t(uuid "%s")' % uid("pin %s %s" % (ref, pn)), "\t\t)"]
        L += ["\t\t(instances", '\t\t\t(project "faff2_cbs1"',
              '\t\t\t\t(path "%s"' % ipath, '\t\t\t\t\t(reference "%s")' % ref,
              "\t\t\t\t\t(unit 1)", "\t\t\t\t)", "\t\t\t)", "\t\t)", "\t)"]
        adds += "\n".join(L) + "\n"

    anchor = t.index("\t(symbol\n")
    t = t[:anchor] + adds + t[anchor:]

    if SHEET_NOTE_OLD not in t:
        sys.exit("encoder note not found")
    t = t.replace(SHEET_NOTE_OLD, SHEET_NOTE_NEW, 1)

    with open(SHEET, "w", encoding="utf-8", newline="") as f:
        f.write(t)
    print("added %d series resistors on the encoder and hall lines" % len(NEW_R))


if __name__ == "__main__":
    main()
