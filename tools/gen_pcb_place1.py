#!/usr/bin/env python3
"""Placement round 1 for hardware/kicad/faff2_cbs1/faff2_cbs1.kicad_pcb.

Mutates the EXISTING board -- it sets every footprint's position and
orientation and touches nothing else.  It is not a board generator: never run
tools/gen_pcb_setup.py over the board again (its own header says so).

Floorplan, judgement calls and the ratsnest stats: docs/decisions/actuator-pcb-place1.md
House rules obeyed: the pcb-layout-style skill (placement section) + AGENTS.md.

Usage:  AMODO_KICAD_LIB=/mnt/c/Amodo/AmodoKiCadLib python3 tools/gen_pcb_place1.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import place_lib as L   # noqa: E402

# ---------------------------------------------------------------------------
# Region map.  Page coordinates; the board is x 30..240, y 30..160.
#   bench edge  = y 30 (24 V entry, USB-C, SMA, debug, bring-up)
#   actuator edge = y 160 (load cell, temp, linear encoder, limits, motor)
# ---------------------------------------------------------------------------

P = {}          # ref -> (x, y, rot)


def put(ref, x, y, rot=0.0):
    assert ref not in P, "duplicate placement for %s" % ref
    P[ref] = (x, y, rot)


def row(refs, x0, y, dx, rot=0.0):
    for i, r in enumerate(refs):
        put(r, x0 + i * dx, y, rot)


def col(refs, x, y0, dy, rot=0.0):
    for i, r in enumerate(refs):
        put(r, x, y0 + i * dy, rot)


# ===========================================================================
# 1. Mounting holes and the two connector edges
# ===========================================================================
put("H1", 36.0, 36.0)
put("H2", 234.0, 36.0)
put("H3", 234.0, 154.0)
put("H4", 36.0, 154.0)

# --- bench edge (front faces on y = 31.5) ---------------------------------
put("J1002", 55.00, 34.25)          # bring-up header, DNP
put("J902", 90.00, 36.25)           # SMA sync/trigger
put("J1003", 118.00, 36.00)         # SWD + USART3 debug
put("J1001", 150.00, 35.50, 180.0)  # USB-C: opening faces the board edge
put("J201", 215.00, 42.00)          # KPJX-4S 24 V entry, barrel to the edge

# --- actuator edge (front faces on y = 158.5) -----------------------------
put("J501", 62.00, 153.75)          # load cell, 8-way 5 mm
put("J701", 88.25, 152.50)          # temp A, push-in 4-way
put("J702", 106.50, 152.50)         # temp B
put("J601", 128.75, 154.75)         # linear encoder FPC
put("J602", 141.50, 154.00)         # linear encoder 2x5 1.27
put("J903", 156.25, 155.75)         # limit switches
put("J1101", 175.75, 157.25)        # rotary encoder / halls A
put("J1102", 195.00, 157.25)        # rotary encoder / halls B
put("J1103", 222.00, 155.50)        # motor phases U/V/W

# ===========================================================================
# 2. power_entry_24v   region x 167..238, y 32..60
#    flow: J201 -> F201 -> L201 -> Q201 (reverse-polarity FET) -> D201 TVS
#          -> V24_PROT bulk -> R203 (+24V_SW, motor) / R204 (V24_LOGIC, rails)
# ===========================================================================
put("TP206", 171.00, 34.00)                 # GND hooks
put("TP207", 174.50, 34.00)
put("TP205", 177.50, 38.50)                 # 24MON
put("R205", 181.00, 38.50, 90.0)            # V24_MON divider -> MCU PC0
put("R206", 184.00, 38.50, 90.0)
put("C207", 187.00, 38.50, 90.0)
put("R204", 172.00, 43.00)                  # V24_PROT -> V24_LOGIC (rails)
put("TP204", 177.50, 43.00)                 # 24VLG
put("TP201", 203.00, 34.00)                 # 24VIN
put("F201", 197.00, 34.50)                  # 2 A T fuse
put("L201", 196.50, 43.00)                  # common-mode choke
put("Q201", 196.50, 52.50)                  # P-channel series FET
put("R201", 191.00, 51.00, 90.0)            # gate network
put("R202", 191.00, 54.50, 90.0)
put("C203", 188.00, 57.50, 90.0)
put("C201", 202.50, 51.00, 90.0)            # Q201 drain node
put("C202", 205.50, 51.00, 90.0)
put("D201", 205.00, 57.00)                  # TVS, downstream of the FET
put("C204", 176.00, 53.00)                  # 100 uF bulk on V24_PROT
put("C205", 185.50, 53.00, 90.0)
put("C206", 188.50, 51.50, 90.0)
put("TP202", 185.00, 57.50)                 # 24VPR
put("R203", 212.00, 52.00)                  # V24_PROT -> +24V_SW (motor)
put("TP203", 217.50, 52.00)                 # 24VSW
put("R208", 227.00, 40.00, 90.0)            # shield link
put("R207", 227.00, 45.00, 90.0)            # power-on LED, beside the jack
put("D202", 227.00, 49.00, 90.0)

# ===========================================================================
# 3. power_rails   region x 167..238, y 62..97
#    U301+L301 -> +6V0 ; U302 -> +5V ; U303 -> +5VA ; U304+L302 -> +3V3
#    The two LDOs sit at the WEST edge - the closest point in this region to
#    the analog corner they feed.
# ===========================================================================
put("C302", 191.00, 66.75, 90.0)            # buck 1 V24_LOGIC input bank
put("C301", 194.00, 66.75, 90.0)
put("C303", 197.50, 66.75, 90.0)            # HF input cap, across VIN/GND
put("U301", 203.00, 68.00)                  # LMR33630, 400 kHz -> +6V0
put("C305", 203.00, 62.50)                  # BOOT
put("L301", 214.00, 68.00)                  # 15 uH
put("C304", 203.00, 73.00)                  # VCC
put("R315", 192.00, 76.00, 90.0)            # PGOOD isolation
put("R301", 195.00, 76.00, 90.0)            # EN divider
put("R302", 198.00, 76.00, 90.0)
put("R303", 201.00, 76.00, 90.0)            # FB divider
put("R304", 204.00, 76.00, 90.0)
put("C306", 228.00, 64.00, 90.0)            # +6V0 output bank
put("C307", 228.00, 72.00, 90.0)
put("C308", 231.50, 64.00, 90.0)
put("R305", 231.50, 72.00, 90.0)            # +6V0 rail link
put("TP302", 228.00, 78.00)                 # +6V0 dual TP
put("C317", 197.50, 86.75, 90.0)            # buck 2 input bank
put("C315", 191.00, 86.75, 90.0)
put("C316", 194.00, 86.75, 90.0)
put("U304", 203.00, 88.00)                  # LMR33630 -> +3V3
put("C319", 203.00, 82.50)                  # BOOT
put("L302", 211.50, 88.00)                  # 6.8 uH
put("C318", 203.00, 93.00)                  # VCC
put("R316", 192.00, 96.00, 90.0)            # PGOOD isolation
put("R308", 195.00, 96.00, 90.0)            # EN divider
put("R309", 198.00, 96.00, 90.0)
put("R310", 201.00, 96.00, 90.0)            # FB divider
put("R311", 204.00, 96.00, 90.0)
put("C320", 222.50, 84.00, 90.0)            # +3V3 output bank
put("C321", 222.50, 92.00, 90.0)
put("C322", 226.00, 84.00, 90.0)
put("R312", 226.00, 92.00, 90.0)            # +3V3 rail link
put("TP306", 232.00, 88.00)                 # +3V3 dual TP
put("TP307", 232.00, 96.00)                 # +3V3A dual TP
put("TP309", 170.00, 62.00)                 # GND hooks
put("TP310", 169.00, 66.00)
put("U302", 176.00, 68.00)                  # TPS7A20 -> +5V
put("C309", 172.00, 66.50, 90.0)            # +6V0 in
put("C310", 180.00, 69.50, 90.0)            # +5V out
put("C311", 183.00, 69.50, 90.0)
put("R306", 186.50, 69.50, 90.0)            # +5V rail link
put("R317", 170.00, 73.00, 90.0)            # PGOOD isolation
put("TP303", 177.00, 62.50)                 # +5V dual TP
put("U303", 176.00, 82.00)                  # TPS7A20 -> +5VA
put("C312", 172.00, 80.50, 90.0)            # +6V0 in
put("C313", 180.00, 83.50, 90.0)            # +5VA out
put("C314", 183.00, 83.50, 90.0)
put("R307", 186.50, 83.50, 90.0)            # +5VA rail link
put("R318", 176.00, 87.50, 90.0)            # PGOOD isolation
put("TP304", 177.00, 76.00)                 # +5VA dual TP
put("R313", 188.00, 80.50, 90.0)            # RAIL_PGOOD wired-AND pull-up
put("R314", 191.00, 80.50, 90.0)
put("D303", 194.00, 80.50, 90.0)
put("TP308", 197.50, 80.50)                 # PGOOD
put("TP311", 169.00, 87.00)                 # GND hooks
put("TP312", 169.00, 91.00)
put("J301", 181.50, 97.00)                  # 1x6 rail probe header

# ===========================================================================
# 4. motor_drive   region x 167..238, y 98..158
#    Three vertical half-bridge legs in a row (W, V, U left to right), current
#    top-to-bottom: V24_MOT rail -> Q_high -> phase -> Q_low -> shunt -> GND
#    plane.  The DRV8323S sits directly BELOW the row at 180 deg, so phase B
#    and C gates leave its top edge and phase A its right edge; SPI, ENABLE,
#    nFAULT and the current-sense outputs all leave WEST toward the MCU.
#    Gate runs are 12-26 mm, all on F.Cu and via-free (open point 1).
# ===========================================================================
X_W, X_V, X_U = 196.0, 211.0, 226.0         # leg centres, 15 mm pitch
Y_QHI, Y_QLO, Y_SH = 116.0, 123.5, 131.0

# -- the bridge ------------------------------------------------------------
put("Q1105", X_W, Y_QHI)                    # phase C (W) high side
put("Q1106", X_W, Y_QLO)                    # low side
put("R1127", X_W, Y_SH)                     # 0R15 5 W shunt
put("Q1103", X_V, Y_QHI)                    # phase B (V)
put("Q1104", X_V, Y_QLO)
put("R1126", X_V, Y_SH)
put("Q1101", X_U, Y_QHI)                    # phase A (U)
put("Q1102", X_U, Y_QLO)
put("R1125", X_U, Y_SH)
put("U1101", 211.00, 141.00, 180.0)         # DRV8323S WQFN-40

# -- per-leg V24_MOT bypass, in the channel beside each leg's drain --------
put("C1123", 200.00, 115.00, 90.0)          # leg W: 2.2 uF + 100 nF
put("C1124", 200.00, 119.50, 90.0)
put("C1121", 215.00, 115.00, 90.0)          # leg V
put("C1122", 215.00, 119.50, 90.0)
put("C1119", 230.00, 115.00, 90.0)          # leg U
put("C1120", 230.00, 119.50, 90.0)

# -- phase switch-node probes (TestPointDual, no U.FL -- D-MOT-12) --------
put("TP1121", 205.50, 120.00, 90.0)         # PH_W
put("TP1118", 220.50, 120.00, 90.0)         # PH_V
put("TP1115", 235.50, 120.00, 90.0)         # PH_U

# -- DC-link store, sat directly over the high-side drains ----------------
put("C1101", 198.00, 105.00)                # 100 uF
put("C1102", 213.00, 105.00)                # 100 uF
put("C1103", 226.00, 104.00)                # 10 uF ceramic
put("C1104", 232.00, 104.00)                # 100 nF

# -- 24 V entry into the block, and the DC-link sense ---------------------
put("R1101", 170.00, 100.50)                # +24V_SW isolation link
put("R1102", 176.00, 100.50)                # current-measurement break
put("TP1101", 181.50, 100.50)               # 24MOT pad
put("TP1102", 186.00, 105.50)               # 24MOT dual TP
put("R1103", 169.00, 105.00, 90.0)          # VBUS_MON divider, 100k/12k
put("R1104", 172.00, 105.00, 90.0)
put("C1105", 175.00, 105.00, 90.0)
put("TP1103", 178.00, 110.00)               # VBUSM
put("TP1108", 181.50, 110.00)               # GND pad

# -- FET temperature: NTC inside the FET field ----------------------------
put("RT1101", 205.50, 126.00)               # 10k NTC between legs W and V
put("R1105", 220.50, 126.00)
put("C1106", 235.50, 126.00)
put("TP1104", 229.50, 126.00)               # FETT

# -- gate observation loops, one pair beside each leg ---------------------
put("TP1119", 194.00, 138.00)               # GHC
put("TP1120", 198.00, 138.00)               # GLC
put("TP1116", 202.00, 138.00)               # GHB
put("TP1117", 218.00, 138.00)               # GLB
put("TP1113", 222.00, 138.00)               # GHA
put("TP1114", 226.00, 138.00)               # GLA

# -- gate-driver supply, charge pump, references (east of the DRV) -------
put("C1112", 218.50, 142.00)                # CPH-CPL flying cap
put("C1111", 222.50, 142.00)                # VCP reservoir
put("C1110", 228.00, 142.00)                # 10 uF at VM
put("C1109", 218.50, 146.50)                # 100 nF at VM
put("R1114", 224.00, 146.50)                # V24_MOT -> VM_DRV
put("TP1106", 230.00, 146.50)               # VMDRV
put("TP1107", 234.00, 146.50)               # VCP
put("C1115", 209.50, 147.00)                # DVDD
put("C1113", 204.00, 142.50)                # VREF (+3V3)
put("C1114", 204.00, 146.00)

# -- SPI, enable, fault, current-sense filters: MCU side of the DRV ------
put("R1116", 169.00, 137.00, 90.0)          # SPI2 SCK stub link
put("R1117", 172.00, 137.00, 90.0)          # SPI2 MOSI stub link
put("R1118", 175.00, 137.00, 90.0)          # MISO pull-up
put("R1115", 178.00, 137.00, 90.0)          # nCS pull-up
put("R1121", 181.00, 137.00, 90.0)          # ENABLE pull-up
put("R1119", 184.00, 137.00, 90.0)          # nFAULT isolation link
put("R1120", 187.00, 137.00, 90.0)          # nFAULT pull-up
put("R1122", 169.00, 141.00, 90.0)          # SOA 100 R + 100 pF
put("C1116", 172.00, 141.00, 90.0)
put("R1123", 175.00, 141.00, 90.0)          # SOB
put("C1117", 178.00, 141.00, 90.0)
put("R1124", 181.00, 141.00, 90.0)          # SOC
put("C1118", 184.00, 141.00, 90.0)
put("TP1109", 187.50, 141.00)               # nFLT
put("TP1110", 169.50, 145.00)               # SOA
put("TP1111", 173.00, 145.00)               # SOB
put("TP1112", 176.50, 145.00)               # SOC

# -- rotary encoder / hall headers and their conditioning ----------------
put("R1108", 169.00, 149.50, 90.0)          # J1101 pull-ups
put("R1109", 172.00, 149.50, 90.0)
put("R1110", 175.00, 149.50, 90.0)
put("R1128", 169.00, 153.50, 90.0)          # J1101 100 R series to the MCU
put("R1129", 172.00, 153.50, 90.0)
put("R1130", 175.00, 153.50, 90.0)
put("R1106", 178.50, 149.50, 90.0)          # VENC = +3V3 link
put("R1107", 178.50, 153.50, 90.0)          # VENC = +5V link (DNP)
put("C1107", 182.00, 149.50, 90.0)
put("C1108", 182.00, 153.50, 90.0)
put("TP1105", 185.50, 151.50)               # VENC
put("R1111", 189.00, 149.50, 90.0)          # J1102 pull-ups
put("R1112", 192.00, 149.50, 90.0)
put("R1113", 195.00, 149.50, 90.0)
put("R1131", 189.00, 153.50, 90.0)          # J1102 100 R series
put("R1132", 192.00, 153.50, 90.0)
put("R1133", 195.00, 153.50, 90.0)

# ===========================================================================
# 5. mcu   core x 92..136, y 44..96 ; USB sub-block x 134..166, y 40..74
#    LQFP100 at 0 deg: left edge -> the ADS1235 SPI and the analog corner,
#    right edge -> the motor block, top edge -> the debug header, bottom edge
#    -> the linear encoder.  That falls out of the .ioc pin map, not a choice.
# ===========================================================================
put("U1001", 114.00, 70.00)
# one 100 nF per VDD/VSS pair, on the pair's own side of the package
put("C1007", 110.50, 81.50, 90.0)           # VBAT pin 6
put("C1002", 112.75, 81.50)                 # VDD 11 / VSS 10
put("C1003", 125.25, 75.75, 90.0)           # VDD 27 / VSS 26
put("C1004", 125.25, 61.50, 90.0)           # VDD 50 / VSS 49
put("C1005", 107.00, 58.50)                 # VDD 75 / VSS 74
put("C1006", 102.75, 75.75, 90.0)           # VDD 100 / VSS 99
put("C1001", 110.00, 85.50)                 # 4.7 uF bulk on the VDD bus
put("C1008", 110.75, 58.50)                 # VCAP 73
put("C1009", 125.25, 65.00, 90.0)           # VCAP 48
put("C1010", 117.75, 81.50)                 # VDDA 21 / VREF+ 20 / VSSA 19
put("C1011", 115.50, 81.50)
put("C1012", 121.00, 81.50)
put("C1013", 121.00, 84.25)
put("FB301", 124.25, 81.50, 90.0)           # +3V3 -> +3V3A, at the load
put("C323", 124.25, 85.00, 90.0)            # (power_rails refdes, placed
put("C324", 124.25, 88.50, 90.0)            #  by function -- open point 3)
put("C1014", 114.75, 88.00)                 # nRESET
put("SW1001", 99.50, 61.00)                 # reset button
put("TP1002", 104.00, 56.50)                # nRST
put("TP1001", 93.50, 71.00)                 # BOOT0
put("R1001", 96.50, 71.00, 90.0)            # BOOT0 pull-up (DNP)
put("R1002", 99.50, 71.00, 90.0)            # BOOT0 pull-down
put("Y1001", 110.00, 92.00)                 # 24 MHz HSE oscillator
put("R1003", 113.75, 92.00, 90.0)           # 33 R series into OSC_IN
put("C1015", 105.75, 92.00, 90.0)
put("U1003", 131.00, 52.00)                 # QSPI force-profile SRAM
put("C1016", 128.00, 46.75, 90.0)
put("C1017", 131.00, 46.75, 90.0)
put("R1005", 134.75, 47.00, 90.0)           # QSPI nCS pull-up
put("R1015", 111.50, 44.50, 90.0)           # debug-header series resistors
put("R1013", 117.00, 44.50, 90.0)
put("R1014", 120.00, 44.50, 90.0)
# --- USB: ULPI PHY, its 24 MHz crystal, the 1.8 V LDO, the ESD array -----
put("U1002", 148.00, 57.00)                 # USB3320C
put("Y1002", 140.50, 55.50, 90.0)           # 24 MHz, tight to REFCLK/XO
put("C1025", 136.50, 53.25)
put("C1026", 136.50, 57.75)
put("R1006", 141.00, 62.50)                 # PHY RESETB pull-down
put("R1007", 146.25, 64.00, 90.0)           # RBIAS
put("C1020", 143.75, 56.75, 90.0)           # +1V8_USB at pins 28/30
put("C1021", 143.75, 59.50, 90.0)
put("C1018", 147.50, 51.50)                 # VDDIO 100 nF, at pins 20/21
put("C1019", 154.00, 57.75, 90.0)           # VDD33 2.2 uF reservoir
put("C1022", 155.00, 66.00, 90.0)           # LDO input
put("C1024", 157.50, 62.00)                 # LDO output 100 nF
put("C1023", 161.00, 62.00, 90.0)
put("U1004", 158.00, 66.00)                 # MIC5365-1.8
put("TP1004", 153.00, 65.50)                # 3V3U
put("TP1005", 162.50, 66.00)                # 1V8U
put("R1012", 150.00, 68.50)                 # +3V3 -> +3V3_USB link
put("D1001", 150.00, 43.00)                 # USBLC6-2P6 on D+/D-, at J1001
put("R1010", 143.00, 43.00, 90.0)           # CC1
put("R1011", 145.50, 43.00, 90.0)           # CC2
put("R1008", 155.00, 43.00, 90.0)           # VBUS divider
put("R1009", 158.00, 43.00, 90.0)           # shield link
put("TP1006", 136.00, 72.00)                # GND hooks
put("TP1007", 139.50, 72.00)
put("TP1008", 143.00, 72.00)
put("TP1009", 146.50, 72.00)
put("TP1010", 150.00, 72.00)
put("TP1011", 153.50, 72.00)

# ===========================================================================
# 6. ui_io   UI cluster x 60..106, y 40..80 ; limits cluster x 150..167
# ===========================================================================
put("U901", 90.00, 47.50)                   # SN74LVC1G17 SYNC buffer
put("C907", 93.50, 46.25, 90.0)
put("R907", 90.00, 43.50, 90.0)             # 39 R source termination
put("D903", 85.00, 43.50, 90.0)             # ESD on the SMA centre pin
put("TP901", 81.00, 47.50)                  # SYNC, pre-termination
put("TP902", 96.75, 47.50)                  # SYNCO, post-termination
put("R901", 100.00, 48.00, 90.0)            # LED_1 heartbeat
put("D901", 100.00, 52.00, 90.0)
put("R902", 104.00, 48.00, 90.0)            # LED_2 fault/status
put("D902", 104.00, 52.00, 90.0)
put("SW901", 74.00, 62.00)                  # BTN_1
put("SW902", 74.00, 71.00)                  # BTN_2
put("J901", 62.50, 66.50)                   # external homing button
put("R903", 92.00, 66.00, 90.0)             # BTN_1 pull-up / series / filter
put("R905", 95.00, 66.00, 90.0)
put("C901", 98.00, 66.00, 90.0)
put("R904", 92.00, 76.00, 90.0)             # BTN_2
put("R906", 95.00, 76.00, 90.0)
put("C902", 98.00, 76.00, 90.0)
put("R915", 152.00, 120.00, 90.0)           # TIM1 BREAK isolation link
put("R916", 155.00, 120.00, 90.0)           # 1 M hold-off
put("TP905", 158.50, 120.00)                # nBRK
put("U902", 156.00, 125.00)                 # SN74LVC1G11 AND
put("C903", 160.00, 125.00, 90.0)
put("R913", 152.00, 130.50, 90.0)           # LIM_A 100 R to the MCU
put("R914", 155.00, 130.50, 90.0)
put("TP903", 158.50, 130.50)                # LIM_A
put("TP904", 162.00, 130.50)                # LIM_B
put("SW903", 155.00, 137.00)                # assert LIM_A without mechanics
put("SW904", 163.50, 137.00)                # assert LIM_B
put("R911", 152.00, 143.50, 90.0)           # LIM_A 10 k
put("R912", 155.00, 143.50, 90.0)           # LIM_B 10 k
put("C905", 158.50, 143.50, 90.0)
put("C906", 161.50, 143.50, 90.0)
put("R909", 152.00, 148.00, 90.0)           # LIM_A 1 k feed
put("R910", 155.00, 148.00, 90.0)           # LIM_B 1 k feed
put("TP906", 159.50, 148.00)                # GND hooks
put("TP907", 163.00, 148.00)

# ===========================================================================
# 7. nvm_calibration   x 82..104, y 83..100
# ===========================================================================
put("U801", 92.50, 88.00)                   # 24FC16 EEPROM
put("C801", 92.50, 92.00, 90.0)
put("R801", 88.00, 85.00, 90.0)             # SCL isolation link
put("R802", 88.00, 89.00, 90.0)             # SDA isolation link
put("R803", 97.00, 85.00, 90.0)             # 4k7 bus pull-ups
put("R804", 97.00, 89.00, 90.0)
put("SB801", 87.00, 93.50)                  # SCL bus jumper
put("SB802", 87.00, 98.00)                  # SDA bus jumper
put("SB803", 97.00, 93.50)                  # write-protect jumper
put("R805", 101.00, 93.50, 90.0)
put("TP801", 93.00, 98.50)                  # SCL
put("TP802", 96.50, 98.50)                  # SDA
put("TP803", 101.00, 98.00)                 # WP
put("TP804", 83.00, 88.00)                  # GND hooks
put("TP805", 83.00, 92.00)

# ===========================================================================
# 8. linear_encoder   x 121..150, y 102..158
# ===========================================================================
put("R603", 124.00, 146.00, 90.0)           # 120 R terminations at the head
put("R604", 127.00, 146.00, 90.0)
put("R605", 130.00, 146.00, 90.0)
put("SB601", 135.00, 145.00)                # A/B/Z mid-bias jumpers
put("SB602", 143.00, 145.00)
put("SB603", 140.50, 135.50)
put("R606", 143.00, 140.00, 90.0)           # ENC_VREF divider
put("R607", 146.00, 140.00, 90.0)
put("C603", 149.00, 140.00, 90.0)
put("C601", 124.00, 141.50, 90.0)           # +5V_ENC store
put("C602", 127.00, 141.50, 90.0)
put("D601", 131.00, 141.00, 90.0)           # +5V_ENC clamps
put("D602", 134.00, 141.00, 90.0)
put("U601", 131.00, 133.00)                 # AM26LV32 RS-422 receiver
put("C604", 126.50, 126.00, 90.0)           # +3V3 at pins 14/16
put("FB601", 123.50, 128.00, 90.0)          # +5V -> +5V_ENC
put("R601", 123.50, 132.00, 90.0)
put("R602", 123.50, 136.00, 90.0)           # ENC_nPROG pull-up
put("TP601", 139.00, 128.00)                # 5VENC
put("J603", 133.00, 110.00)                 # logic-analyser header

# ===========================================================================
# 9. temp_sense   x 85..121, y 102..158
# ===========================================================================
put("TP701", 87.00, 145.50)                 # PRB1A
put("TP702", 90.50, 145.50)                 # PRB1B
put("R708", 99.00, 145.50, 90.0)            # 3-wire / 2-wire option links
put("R709", 102.00, 145.50, 90.0)
put("TP703", 105.00, 145.50)                # PRB2A
put("TP704", 108.50, 145.50)                # PRB2B
put("R701", 87.00, 141.00, 90.0)            # channel A 100 R input series
put("R702", 90.00, 141.00, 90.0)
put("R705", 93.00, 141.00, 90.0)            # shared reference leg
put("R710", 96.00, 141.00, 90.0)
put("R703", 105.00, 141.00, 90.0)           # channel B
put("R704", 108.00, 141.00, 90.0)
put("R706", 111.00, 141.00, 90.0)
put("R711", 114.00, 141.00, 90.0)
put("R707", 117.50, 141.00, 90.0)           # 5 k reference resistor
put("C701", 87.00, 136.50, 90.0)            # input and reference filters
put("C702", 90.00, 136.50, 90.0)
put("C703", 93.50, 136.50)
put("C707", 96.00, 136.50, 90.0)
put("C708", 99.00, 136.50, 90.0)
put("C709", 102.00, 136.50)
put("C704", 105.00, 136.50, 90.0)
put("C705", 108.00, 136.50, 90.0)
put("C706", 111.50, 136.50)
put("TP705", 114.50, 136.50)                # REFP
put("TP706", 117.50, 136.50)                # REFN
put("U701", 100.00, 130.00)                 # ADS1120
put("C712", 96.00, 124.00)                  # +3V3 at pin 13
put("C713", 99.50, 124.00)
put("C711", 102.50, 124.00)                 # +5VA at pin 12
put("C710", 106.00, 124.00)
put("R712", 96.00, 118.00, 90.0)            # 47 R SPI isolation links
put("R713", 99.00, 118.00, 90.0)
put("R714", 102.00, 118.00, 90.0)
put("R715", 105.00, 118.00, 90.0)
put("TP712", 112.00, 128.00)                # GND hooks
put("TP713", 115.50, 128.00)
put("J703", 100.00, 110.00)                 # logic-analyser header

# ===========================================================================
# 10. loadcell_afe   x 33..84, y 100..158
#     The quiet corner: furthest point on the board from J201, both switching
#     inductors and the DRV8323.  The input filter parts sit in the straight
#     line from J501 to the ADS1235.
# ===========================================================================
put("R501", 44.00, 145.00, 90.0)            # AIN0 / AIN1 100 R input series
put("R502", 47.00, 145.00, 90.0)
put("R508", 50.50, 145.00, 90.0)            # +5VA -> EXC+
put("R503", 55.00, 145.00, 90.0)            # sense -> REFP0 / REFN0
put("R504", 58.00, 145.00, 90.0)
put("R505", 61.00, 145.00, 90.0)            # 100 k bridge-open detect
put("R506", 64.00, 145.00, 90.0)            # 4-wire option links (DNP)
put("R507", 69.50, 145.00, 90.0)
put("R509", 67.00, 145.00, 90.0)            # EXC- return link
put("R510", 72.00, 145.00, 90.0)            # cable shield link
put("C507", 44.00, 141.00, 90.0)            # EXC+ store
put("C508", 47.00, 141.00, 90.0)
put("TP501", 50.50, 141.00)                 # EXC+
put("TP502", 55.00, 141.00)                 # SNS+
put("TP503", 58.00, 141.00)                 # SNS-
put("C501", 62.50, 141.00, 90.0)            # AIN filters, datasheet values
put("C502", 67.00, 141.00, 90.0)
put("C503", 64.75, 137.50)
put("C504", 72.00, 141.00, 90.0)            # reference filters
put("C505", 76.00, 141.00, 90.0)
put("C506", 74.00, 137.50)
put("J503", 54.00, 137.00)                  # U.FL noise-floor taps
put("J504", 58.50, 137.00)
put("TP504", 72.00, 133.50)                 # REFP
put("TP505", 76.00, 133.50)                 # REFN
put("U501", 66.00, 127.00, 180.0)           # ADS1235, inputs facing J501
put("C511", 58.00, 126.00, 90.0)            # +3V3 at pin 17
put("C512", 60.50, 126.00, 90.0)
put("C510", 71.00, 126.00, 90.0)            # +5VA at pin 4
put("C509", 73.00, 126.00, 90.0)
put("C514", 73.50, 130.50)                  # CAPP / CAPN
put("C513", 66.00, 121.00)                  # BYPASS
put("R519", 73.00, 121.50, 90.0)            # PWRDN pull-up
put("TP513", 76.50, 121.50)                 # PWRDN
put("R522", 41.00, 133.50, 90.0)            # unused-input bias
put("R523", 44.00, 133.50, 90.0)
put("R524", 47.00, 133.50, 90.0)
put("R525", 50.00, 133.50, 90.0)
put("R511", 41.00, 117.00, 90.0)            # 47 R SPI isolation links
put("R512", 44.00, 117.00, 90.0)
put("R513", 47.00, 117.00, 90.0)
put("R514", 50.00, 117.00, 90.0)
put("R515", 53.00, 117.00, 90.0)
put("R516", 56.00, 117.00, 90.0)
put("R517", 59.00, 117.00, 90.0)
put("R518", 62.00, 117.00, 90.0)
put("R520", 65.50, 117.00, 90.0)            # CLKIN
put("R521", 68.50, 117.00, 90.0)            # CLKIN fallback link (DNP)
put("TP515", 74.00, 117.00)                 # GND hooks
put("TP516", 77.50, 117.00)
put("J502", 57.00, 110.00)                  # logic-analyser header



def main():
    b = L.load()
    fps = L.by_ref(b)
    missing = sorted(set(fps) - set(P))
    extra = sorted(set(P) - set(fps))
    assert not extra, "placed refs not on the board: %s" % extra
    assert not missing, "unplaced footprints: %s" % missing
    for ref, (x, y, rot) in P.items():
        L.place(fps[ref], x, y, rot)
    L.save(b)
    print("placed %d footprints" % len(P))


if __name__ == "__main__":
    main()
