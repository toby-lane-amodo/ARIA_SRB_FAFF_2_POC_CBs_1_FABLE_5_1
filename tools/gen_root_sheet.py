#!/usr/bin/env python3
"""Regenerate the FAFF 2 CBs_1 root sheet: hierarchical sheet pins plus the
root-level interconnect wiring (docs/decisions/actuator-sch-integrate.md).

Re-runnable and deterministic: every uuid is a uuid5 of a stable string, and the
nine sheet-symbol uuids are the ones the child sheets' instance paths already
reference, so they must never change.

test_debug was dissolved into mcu (docs/decisions/actuator-rev-testdebug.md), so
the pages renumber 2..10 with no gap and the reference-designator ranges are no
longer derived from the page number - 4xx is retired, see AGENTS.md.
"""
import uuid, os

NS = uuid.UUID("5edb00fd-45c9-5fe7-8d71-adbf38f38546")   # the root sheet's own uuid
ROOT_UUID = "5edb00fd-45c9-5fe7-8d71-adbf38f38546"

def uid(key):
    return str(uuid.uuid5(NS, key))

# ---------------------------------------------------------------- geometry ---
LX, LR = 12.70, 76.20            # left column: left edge, right edge (pins)
PRX, PRR = 101.60, 165.10        # power_rails
MX, MR = 139.70, 208.28          # mcu: left edge (pins), right edge (pins)
RX, RR = 254.00, 317.50          # right column: left edge (pins), right edge
BUS24 = 45.72                    # +24V_SW corridor, above the mcu block

# Sheet symbol uuids - fixed, referenced by every child's instance paths.
SHEETS = {
    "power_entry_24v": ("4ec0bd1c-b43d-5810-bc42-5f18ea0c8497", 2),
    "power_rails":     ("cfac6e86-3b1f-5c4c-b992-5519585fa944", 3),
    "loadcell_afe":    ("94a105e9-fddd-5aae-8f2a-964f0eaa6212", 4),
    "linear_encoder":  ("7f1522a2-4954-524c-ba63-158dc350920f", 5),
    "temp_sense":      ("4e1514d5-7414-55f0-9f35-1d20cac21a6b", 6),
    "nvm_calibration": ("9fddfe18-c15c-5dd7-9f89-62033d73aa2a", 7),
    "ui_io":           ("3ac83d89-6c2b-5de7-a46b-dbc34c85888b", 8),
    "mcu":             ("1d7ef20a-ceb5-5848-8c8d-02f7ee5f958f", 9),
    "motor_drive":     ("25605169-cb1e-52bd-8388-77d0027da969", 10),
}

def col(y0, names, x, side):
    """Pin rows on 2.54 mm pitch from y0. names = [(name, type), ...]."""
    return [(n, t, x, round(y0 + i * 2.54, 2), side) for i, (n, t) in enumerate(names)]

# --- the 21 nets motor_drive shares only with mcu, in drawing order ----------
MOTOR21 = ["MOTOR_PWM_AH", "MOTOR_PWM_AL", "MOTOR_PWM_BH", "MOTOR_PWM_BL",
           "MOTOR_PWM_CH", "MOTOR_PWM_CL",
           "DRV8323_EN", "DRV8323_nCS", "DRV8323_CAL", "DRV8323_nFAULT",
           "MOTOR_I_A", "MOTOR_I_B", "MOTOR_I_C",
           "MOTOR_FETTEMP", "VBUS_MON",
           "MOTOR_ENCODER_A", "MOTOR_ENCODER_B", "MOTOR_ENCODER_I",
           "HALL1", "HALL2", "HALL3"]
# direction seen from the mcu
MOTOR21_MCU = dict(zip(MOTOR21, ["output"] * 6 + ["output", "output", "output", "input"]
                                 + ["input"] * 5 + ["input"] * 6))
MOTOR21_DRV = {n: ("input" if MOTOR21_MCU[n] == "output" else "output") for n in MOTOR21}

Y_MOTOR = 60.96          # first mcu/motor_drive shared row
Y_SPI2 = 121.92          # CONFIG_SPI_SCK row (a clear gap under the motor rows)
Y_TSCS = 129.54          # ADS1120_nCS row out of the mcu
Y_TS = 147.32            # first temp_sense row

# ---------------------------------------------------------------- the sheets -
blocks = []   # (name, x, y, w, h, pins)

# power_entry_24v's three outputs fan out to three different places, so they sit on
# a 5.08 mm pitch: it leaves room for the +24V_SW and V24_MON wires to peel away
# without either one crossing the other.
blocks.append(("power_entry_24v", LX, 20.32, 63.5, 20.32,
    [("V24_LOGIC", "output", LR, 25.40, "R"),
     ("+24V_SW",   "output", LR, 30.48, "R"),
     ("V24_MON",   "output", LR, 35.56, "R")]))

blocks.append(("power_rails", PRX, 20.32, 63.5, 20.32,
    [("V24_LOGIC", "input", PRX, 25.40, "L")]))

AFE = [("ADS1235_SCLK", "input"), ("ADS1235_MOSI", "input"), ("ADS1235_MISO", "output"),
       ("ADS1235_nCS", "input"), ("ADS1235_nDRDY", "output"), ("ADS1235_START", "input"),
       ("ADS1235_nRESET", "input"), ("ADS1235_CLKIN", "input")]
blocks.append(("loadcell_afe", LX, 60.96, 63.5, 27.94, col(66.04, AFE, LR, "R")))

ENC = [("LINEAR_ENCODER_A", "output"), ("LINEAR_ENCODER_B", "output"),
       ("LINEAR_ENCODER_Z", "output")]
blocks.append(("linear_encoder", LX, 96.52, 63.5, 15.24, col(101.60, ENC, LR, "R")))

NVM = [("EEPROM_SCL", "bidirectional"), ("EEPROM_SDA", "bidirectional")]
blocks.append(("nvm_calibration", LX, 119.38, 63.5, 12.70, col(124.46, NVM, LR, "R")))

UI = [("LED_1", "input"), ("LED_2", "input"), ("BTN_1", "output"), ("BTN_2", "output"),
      ("SYNC_TRIG", "input"), ("LIM_A", "output"), ("LIM_B", "output"),
      ("LIMIT_nBRK", "output")]
blocks.append(("ui_io", LX, 139.70, 63.5, 27.94, col(144.78, UI, LR, "R")))

# SWD, USART3 and MCU_nRESET no longer cross a block boundary: the debug header
# moved onto the mcu sheet with the rest of test_debug, so those six nets are
# sheet-local there and carry no sheet pin.

# --- mcu ---------------------------------------------------------------------
def flip(t):
    return {"input": "output", "output": "input"}.get(t, t)

mcu_pins = [("V24_MON", "input", MX, 55.88, "L")]
mcu_pins += col(66.04, [(n, flip(t)) for n, t in AFE], MX, "L")
mcu_pins += col(101.60, [(n, flip(t)) for n, t in ENC], MX, "L")
mcu_pins += col(124.46, NVM, MX, "L")
mcu_pins += col(144.78, [(n, flip(t)) for n, t in UI], MX, "L")
mcu_pins += col(Y_MOTOR, [(n, MOTOR21_MCU[n]) for n in MOTOR21], MR, "R")
mcu_pins += col(Y_SPI2, [("CONFIG_SPI_SCK", "output"), ("CONFIG_SPI_MOSI", "output"),
                         ("CONFIG_SPI_MISO", "input")], MR, "R")
mcu_pins += [("ADS1120_nCS", "output", MR, Y_TSCS, "R")]
blocks.append(("mcu", MX, 50.80, 68.58, 121.92, mcu_pins))

# --- motor_drive -------------------------------------------------------------
mot_pins = [("+24V_SW", "input", RX, BUS24, "L")]
mot_pins += col(Y_MOTOR, [(n, MOTOR21_DRV[n]) for n in MOTOR21], RX, "L")
mot_pins += col(Y_SPI2, [("CONFIG_SPI_SCK", "input"), ("CONFIG_SPI_MOSI", "input"),
                         ("CONFIG_SPI_MISO", "tri_state")], RX, "L")
blocks.append(("motor_drive", RX, 38.10, 63.5, 93.98, mot_pins))

# --- temp_sense --------------------------------------------------------------
ts_pins = col(Y_TS, [("CONFIG_SPI_SCK", "input"), ("CONFIG_SPI_MOSI", "input"),
                     ("CONFIG_SPI_MISO", "tri_state"), ("ADS1120_nCS", "input")], RX, "L")
blocks.append(("temp_sense", RX, 142.24, 63.5, 17.78, ts_pins))

# ------------------------------------------------------------------- wiring --
wires, junctions = [], []
def w(a, b):
    wires.append((a, b))

# top strip
w((LR, 25.40), (PRX, 25.40))                                   # V24_LOGIC
w((LR, 30.48), (96.52, 30.48))                                 # +24V_SW
w((96.52, 30.48), (96.52, BUS24))
w((96.52, BUS24), (RX, BUS24))
w((LR, 35.56), (86.36, 35.56))                                 # V24_MON
w((86.36, 35.56), (86.36, 55.88))
w((86.36, 55.88), (MX, 55.88))

# left column -> mcu, one straight wire per row
for _n, _t, _x, y, side in mcu_pins:
    if side == "L" and y != 55.88:
        w((LR, y), (MX, y))

# mcu -> motor_drive, one straight wire per row
for i in range(len(MOTOR21)):
    y = round(Y_MOTOR + i * 2.54, 2)
    w((MR, y), (RX, y))

# the shared SPI2 CONFIG bus: tapped once per wire, nested so nothing crosses
for i, xt in enumerate((248.92, 246.38, 243.84)):
    ym = round(Y_SPI2 + i * 2.54, 2)
    yt = round(Y_TS + i * 2.54, 2)
    w((MR, ym), (xt, ym))
    w((xt, ym), (RX, ym))
    w((xt, ym), (xt, yt))
    w((xt, yt), (RX, yt))
    junctions.append((xt, ym))

# ADS1120_nCS: mcu -> temp_sense, clear of the bus taps
w((MR, Y_TSCS), (241.30, Y_TSCS))
w((241.30, Y_TSCS), (241.30, 154.94))
w((241.30, 154.94), (RX, 154.94))

# -------------------------------------------------------------- annotations --
NOTE = (
 "ROOT SHEET - THE BLOCK MAP, WIRED.  DEC-0009 is closed.\n"
 "\n"
 "Every net that crosses a block boundary is drawn: one sheet pin for each hierarchical label a\n"
 "child sheet declares, each one on a wire.  Nothing on this sheet connects by name.\n"
 "\n"
 "NINE BLOCKS, NOT TEN.  test_debug was dissolved into the sheets its circuits serve: the SWD +\n"
 "USART3 header, the rail probe header and the GND hooks all moved onto mcu, so SWDIO, SWCLK,\n"
 "SWO, MCU_nRESET, DBG_TX and DBG_RX are sheet-local there and no longer cross a boundary.\n"
 "Test coverage lives on the circuit page it covers - docs/decisions/actuator-rev-testdebug.md.\n"
 "\n"
 "GLOBAL POWER NETS CARRY NO SHEET PIN.  GND, +5V, +5VA, +3V3 and +3V3A are Amodo power symbols\n"
 "and connect across the hierarchy on their own.  power_rails produces all four and owns their\n"
 "PWR_FLAGs; power_entry_24v owns the flags for GND and +24V_SW.  Only +24V_SW, V24_LOGIC and\n"
 "V24_MON leave power_entry_24v as ordinary nets, and they are drawn along the top of the sheet.\n"
 "\n"
 "LAYOUT follows docs/FAFF-2-Electronics-Full.svg left to right: 24 V in at the top left, sensing\n"
 "and user I/O down the left column, the STM32H723VET6 in the middle, motor drive on the right.\n"
 "temp_sense sits under motor_drive rather than in the sensor column because it hangs off the same\n"
 "shared SPI2 CONFIG bus as the DRV8323 (ARCHITECTURE 5.1); the three bus wires are tapped once\n"
 "each, at the junctions between the two blocks.  Its two probe channels stay inside its own sheet.\n"
 "\n"
 "REFERENCE DESIGNATORS are allocated per sheet, 100 apart, from a fixed table - NOT from the\n"
 "page number, which changed when test_debug went: 2xx power_entry_24v, 3xx power_rails,\n"
 "5xx loadcell_afe, 6xx linear_encoder, 7xx temp_sense, 8xx nvm_calibration, 9xx ui_io,\n"
 "10xx mcu, 11xx motor_drive.  4xx is retired.  Power symbols follow the same ranges\n"
 "(#PWR5xx, #PWR7xx, ...) so that no two sheets merge into one part at netlist time.\n"
 "\n"
 "Requirements docs/REQUIREMENTS.md - architecture docs/ARCHITECTURE.md - decisions\n"
 "docs/DECISIONS.md and docs/decisions/actuator-sch-integrate.md - bring-up docs/TEST_PLAN.md"
)

TEXTS = [
    (93.98, 62.23, "SPI3 + MCO2 clock"),
    (93.98, 91.44, "TIM5 encoder mode"),
    (93.98, 116.84, "I2C1 calibration EEPROM"),
    (93.98, 135.89, "GPIO / TIM15 / TIM1_BKIN2"),
    (210.82, 53.34, "TIM1 PWM, ADC1/2 sense, TIM3"),
    (210.82, 116.84, "SPI2 CONFIG bus + ADS1120 nCS"),
]

# ------------------------------------------------------------------- output --
out = []
A = out.append
A('(kicad_sch')
A('\t(version 20250114)')
A('\t(generator "eeschema")')
A('\t(generator_version "9.0")')
A('\t(uuid "%s")' % ROOT_UUID)
A('\t(paper "A3")')
A('\t(title_block')
A('\t\t(title "ARIA_SRB_FAFF_2 CBs_1 - Root")')
A('\t\t(date "2026-09-03")')
A('\t\t(rev "0.2")')
A('\t\t(company "Amodo Design")')
A('\t\t(comment 1 "Proof-of-concept control board - development-board form factor")')
A('\t\t(comment 2 "Hierarchical block map, wired; see docs/ARCHITECTURE.md")')
A('\t\t(comment 3 "Requirements: docs/REQUIREMENTS.md")')
A('\t\t(comment 4 "Decisions: docs/DECISIONS.md")')
A('\t)')
A('\t(lib_symbols)')

for (x, y) in junctions:
    A('\t(junction')
    A('\t\t(at %g %g)' % (x, y))
    A('\t\t(diameter 0)')
    A('\t\t(color 0 0 0 0)')
    A('\t\t(uuid "%s")' % uid("junction %g %g" % (x, y)))
    A('\t)')

for (x1, y1), (x2, y2) in wires:
    A('\t(wire')
    A('\t\t(pts')
    A('\t\t\t(xy %g %g) (xy %g %g)' % (x1, y1, x2, y2))
    A('\t\t)')
    A('\t\t(stroke')
    A('\t\t\t(width 0)')
    A('\t\t\t(type default)')
    A('\t\t)')
    A('\t\t(uuid "%s")' % uid("wire %g %g %g %g" % (x1, y1, x2, y2)))
    A('\t)')

for x, y, s in TEXTS:
    A('\t(text "%s"' % s)
    A('\t\t(exclude_from_sim no)')
    A('\t\t(at %g %g 0)' % (x, y))
    A('\t\t(effects')
    A('\t\t\t(font')
    A('\t\t\t\t(size 1.27 1.27)')
    A('\t\t\t)')
    A('\t\t\t(justify left)')
    A('\t\t)')
    A('\t\t(uuid "%s")' % uid("text %g %g" % (x, y)))
    A('\t)')

A('\t(text "%s"' % NOTE.replace("\n", "\\n"))
A('\t\t(exclude_from_sim no)')
A('\t\t(at 12.7 209.55 0)')
A('\t\t(effects')
A('\t\t\t(font')
A('\t\t\t\t(size 1.27 1.27)')
A('\t\t\t)')
A('\t\t\t(justify left top)')
A('\t\t)')
A('\t\t(uuid "%s")' % uid("root note"))
A('\t)')

for name, x, y, wdt, hgt, pins in blocks:
    su, page = SHEETS[name]
    A('\t(sheet')
    A('\t\t(at %g %g)' % (x, y))
    A('\t\t(size %g %g)' % (wdt, hgt))
    A('\t\t(exclude_from_sim no)')
    A('\t\t(in_bom yes)')
    A('\t\t(on_board yes)')
    A('\t\t(dnp no)')
    A('\t\t(fields_autoplaced yes)')
    A('\t\t(stroke')
    A('\t\t\t(width 0.1524)')
    A('\t\t\t(type solid)')
    A('\t\t)')
    A('\t\t(fill')
    A('\t\t\t(color 0 0 0 0.0000)')
    A('\t\t)')
    A('\t\t(uuid "%s")' % su)
    A('\t\t(property "Sheetname" "%s"' % name)
    A('\t\t\t(at %g %g 0)' % (x, round(y - 0.7118, 4)))
    A('\t\t\t(effects')
    A('\t\t\t\t(font')
    A('\t\t\t\t\t(size 1.27 1.27)')
    A('\t\t\t\t)')
    A('\t\t\t\t(justify left bottom)')
    A('\t\t\t)')
    A('\t\t)')
    A('\t\t(property "Sheetfile" "%s.kicad_sch"' % name)
    A('\t\t\t(at %g %g 0)' % (x, round(y + hgt + 0.7118, 4)))
    A('\t\t\t(effects')
    A('\t\t\t\t(font')
    A('\t\t\t\t\t(size 1.27 1.27)')
    A('\t\t\t\t)')
    A('\t\t\t\t(justify left top)')
    A('\t\t\t)')
    A('\t\t)')
    for pn, pt, px, py, side in pins:
        A('\t\t(pin "%s" %s' % (pn, pt))
        A('\t\t\t(at %g %g %d)' % (px, py, 180 if side == "L" else 0))
        A('\t\t\t(uuid "%s")' % uid("pin %s %s" % (name, pn)))
        A('\t\t\t(effects')
        A('\t\t\t\t(font')
        A('\t\t\t\t\t(size 1.27 1.27)')
        A('\t\t\t\t)')
        A('\t\t\t\t(justify %s)' % ("left" if side == "L" else "right"))
        A('\t\t\t)')
        A('\t\t)')
    A('\t\t(instances')
    A('\t\t\t(project "faff2_cbs1"')
    A('\t\t\t\t(path "/%s"' % ROOT_UUID)
    A('\t\t\t\t\t(page "%d")' % page)
    A('\t\t\t\t)')
    A('\t\t\t)')
    A('\t\t)')
    A('\t)')

A('\t(sheet_instances')
A('\t\t(path "/"')
A('\t\t\t(page "1")')
A('\t\t)')
A('\t)')
A('\t(embedded_fonts no)')
A(')')

dest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "hardware", "kicad", "faff2_cbs1", "faff2_cbs1.kicad_sch")
with open(os.path.normpath(dest), "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(out) + "\n")

npins = sum(len(p) for *_ , p in blocks)
print("sheet pins %d, wires %d, junctions %d -> %s"
      % (npins, len(wires), len(junctions), os.path.normpath(dest)))
