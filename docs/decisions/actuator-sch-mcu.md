# `mcu` and `test_debug` — design record

Block task: **MCU + USB + RAM + DEBUG**, covering exactly two sheets —
`hardware/kicad/faff2_cbs1/mcu.kicad_sch` and
`hardware/kicad/faff2_cbs1/test_debug.kicad_sch`. Nothing else in the repo was
edited except this file and the three datasheets listed in §9.

Everything here is subordinate to the authorities named in `AGENTS.md`. The
`.ioc` is quoted, never changed: **no pin on this board was re-assigned.**

---

## 1. What was drawn

| Sheet | Blocks |
|---|---|
| `mcu.kicad_sch` | **A** MCU core (supplies, decoupling, reset, boot, HSE in) · **B** 24 MHz reference · **D** OCTOSPI1 force-profile RAM · **F** USB3320C ULPI PHY · **G** USB-C receptacle · **E** USB PHY rails · MCU port units U1001B..U1001F · spare-I/O breakout |
| `test_debug.kicad_sch` | **T1** SWD + USART3 debug header · **T2** consolidated rail probe header · **T3** GND hooks for scope clips |

60 components, 118 nets. Every symbol comes from the Amodo house library;
**no new library part was created** and no Amodo category file was touched.

---

## 2. Decisions

### D-MCU-01 — HSE and the USB3320 reference share one 24 MHz oscillator (closes OQ-03)

`Y1001 = ABRACON ASEMB-24.000MHZ-LY-T`, a 3.3 V LVCMOS MEMS oscillator, 10 ppm,
3.2 × 2.5 mm, from `Amodo_Crystals.kicad_sym`.

`REQUIREMENTS.md` OQ-03 asked where the HSE external clock comes from, and named
sharing an oscillator with the USB3320 as the candidate. That is what is drawn.

*Why an oscillator at all.* The `.ioc` sets `PH0-OSC_IN` to
*HSE-External-Clock-Source* and leaves `PH1-OSC_OUT` unallocated (`REQ-AR-16`), so
the HSE input must be a driven clock — a bare crystal is impossible without the
second pin. DS13313 Table 31 allows 4–50 MHz on that pin at 0.7·VDD, so a 3.3 V
CMOS oscillator drives it directly.

*Why 24 MHz.* The USB3320 selects its reference frequency on `REFSEL[2:0]`;
`111` = 24 MHz (USB3320 DS Table 5-10). 24 MHz is also a clean PLL input for the
STM32H723's 550 MHz ceiling. USB requires ±500 ppm on the reference; a 10 ppm part
leaves a factor of fifty in hand and also tightens the TIM timebase and the MCO2
clock that the ADS1235 runs from.

*Fan-out.* One CMOS output drives two loads, so each branch gets its own 33 R
source termination (`R1003`, `R1004`) at the oscillator. `EN` is tied to +3V3 — no
`.ioc` pin exists to gate it, and gating the HSE would stop the MCU anyway.

*Consequence for firmware.* The clock tree in the `.ioc` is still the untouched
CubeMX default (PLL from HSI, 64 MHz SYSCLK — DEC-0013 caveat (a)). It must be
re-derived from a 24 MHz HSE. That is an `.ioc` **clock** change, not a **pin**
change, so it does not disturb any block interface.

### D-MCU-02 — the QSPI force-profile RAM is an ISSI IS66WVS4M8**BLL**

`U1003 = IS66WVS4M8BLL-104NLI`, 32 Mbit (4 M × 8) QPI PSRAM, SOIC-8 150 mil, from
`Amodo_Digital_ICs.kicad_sym` (`SymLifecycle = reviewed`).

*Why this part.* `REQ-AR-12` / DEC-0006 fix the interface: OCTOSPI1 port 1, quad
mode, fitted. The library already holds an SPI/QPI PSRAM that matches: 104 MHz,
6 signals (CLK, CE#, SIO0-3) — exactly the six the `.ioc` allocates
(`QSPI_P1_CLK`, `_nCS`, `_IO0..IO3`). 4 MB of true random-access RAM suits a
force-profile buffer far better than the flash alternative (`W25Q16JVSNIQ`) also
in the library, which would need erase cycles to rewrite a profile.

*The A/B trap, and why it matters.* The ISSI part number's third field is the
supply voltage: **`ALL` = 1.8 V, `BLL` = 3.0 V** (66/67WVS4M8ALL-BLL datasheet §9).
The library carries both symbols under near-identical names. The STM32 OCTOSPI I/O
runs at VDD = 3.3 V, so **BLL** (2.7–3.6 V) is the only correct one. This is
recorded on the sheet as well as here, because picking `ALL` would be a silent
kill.

*No series termination, no test points.* The device specifies a 50 Ω output drive
and the link is point-to-point, so series resistors would only add delay. Test
points are forbidden on this bus by DEC-0018 ruling 1. A 10 k pull-up (`R1005`)
holds `CE#` deasserted while the MCU pins are still high-impedance out of reset.

### D-MCU-03 — the USB3320 gets a local 1.8 V LDO, not a new cross-block rail

`U1004 = MIC5365-1.8` (150 mA, SC-70-5) generates `+1V8_USB` from `+3V3_USB`.

The USB3320 datasheet is explicit that `VDD18` (pins 28 and 30) is an **external**
1.8 V supply input, not a regulator output: DS §2.1 pin table, and §5.5.3
*"For USB operation the USB3320 requires the VBAT, VDD33, VDDIO and VDD18
supplies."* The internal LDO only makes VDD33 from VBAT.

`OQ-02` (rail set) is open and owned by `power_rails`, and `AGENTS.md` forbids
inventing an interface that the sheet's stub note does not list. Adding a
board-wide 1.8 V rail mid-wave would do both. Generating it locally for the one IC
that needs it avoids that entirely, and it puts the rail's test point and current
break in the block that produces it — producer-owns-the-break, DEC-0007 and
`TEST_PLAN.md` §3.

*Sequencing note, carried forward.* The USB3320 wants VDD18 stable before VDDIO
(DS §5.5.3), and its absolute maximum for VDDIO with VDD18 at 0 V is 0.7 V
(DS Table 3-1). Deriving 1.8 V from the same 3.3 V rail means the LDO output
tracks its input up with only its own start-up delay, and `RESETB` is held low
throughout by `R1006` (below), which is the datasheet's own remedy. Worth a
scope check on the two rails at bring-up step 3.

### D-MCU-04 — USB3320 support components are datasheet values, not choices

* `RBIAS` = **8.06 k ±1 %** to GND (`R1007`) — DS §2.1 pin 24, mandatory value.
* `RVBUS` = **10 k ±5 %** (`R1008`) between the connector VBUS and the PHY VBUS pin
  — DS Table 5-7, the device-only value. The PHY's integrated over-voltage
  protection works *through* this resistor and is rated to 30 V.
* `ID` tied to VDD33 — DS §5.6.1, the device-only case.
* `REFSEL[2:0]` = 111 to VDDIO — 24 MHz (DS Table 5-10).
* `VDD33` bypass 2.2 µF, `VDDIO` and each `VDD18` 100 nF, all close to the pin —
  DS §2.1 and Table 4-9.
* `CPEN`, `SPK_L`, `SPK_R`, `XO`, `N/C` left unconnected: no OTG VBUS switch, no
  audio switching, and no crystal (the reference comes in on REFCLK).
* `RESETB` has **no** internal pull-down and the datasheet requires the Link to
  drive it at all times including start-up (DS §5.5.2). `R1006` (10 k to GND)
  holds the PHY in reset while `PE4` is still an input.

`VBAT` and `VDD33` are tied together on `+3V3_USB`, which is USB3320 DS Figure 5-7,
the "powered from a 3.3 V supply" case.

### D-MCU-05 — `+3V3_USB` is a separate net behind a 0 R link, deliberately

The PHY rail is not simply `+3V3`. `R1012` (0 R) sits between them.

Three reasons, all pulling the same way:
1. `TEST_PLAN.md` §3.1 requires a current-measurement break per rail, and §3.3 a
   per-block link. The PHY is the one block on this sheet whose consumption is
   worth measuring on its own during bring-up step 12.
2. The USB3320's `VDD33` pin is a **power output** in the symbol (it is the
   internal LDO's output). On the shared `+3V3` net it would eventually sit
   alongside the `power_rails` regulator output and ERC would report a
   power-output conflict. Behind the link it drives its own net cleanly.
3. It lets the PHY be lifted off the rail without unsoldering the QFN.

`TP1004` (SMT pad) sits on `+3V3_USB` and `TP1005` on `+1V8_USB`.

### D-MCU-06 — USB-C: Rd only, VBUS sensed not consumed

`J1001 = USB4110-GF-A`, the GCT USB 2.0-only 16-position Type-C receptacle from
`Amodo_Connectors.kicad_sym`.

`REQ-EL-10` and DEC-0002 say the port carries data and takes no power. DEC-0002
left one thing to this task: *how the device detects host presence.* The answer is
the PHY's own VBUS comparator — connector VBUS → `RVBUS` 10 k → USB3320 `VBUS` pin,
where the SessVld comparator reports host presence over ULPI (DS §5.6.2.2).

Two consequences worth stating:
* **No MCU ADC channel is needed for USB VBUS.** That is independent support for
  DEC-0011's reading of `VBUS_MON` (PC5) as the motor DC-link monitor, and
  therefore for closing **OQ-01** that way.
* 5.1 k Rd on both CC1 and CC2 is all the CC network needs. Without them a
  USB-C host will not attach at all; with them the port is a valid UFP that
  simply never draws from VBUS.

*ESD.* `D1001 = USBLC6-2P6` protects D+/D- and VBUS — the ST part specified for
USB 2.0 high speed, 3.5 pF. **CC1/CC2 are deliberately left unprotected**: each
terminates on a 5.1 k resistor to ground and connects to no semiconductor, so
there is nothing on those nets for a strike to damage. The house standard's
"ESD protection on interfaces" is met where it does work.

`SBU1`/`SBU2` are unused (no alternate mode). The shell goes to GND through a
fitted 0 R (`R1009`) so the layout can change the shield bond without a re-spin.

### D-MCU-07 — boot and reset

* **BOOT0** — 10 k pull-down fitted (`R1002`) = boot from internal flash; a **DNP**
  1 k pull-up (`R1001`) is drawn so the system bootloader (DFU) is a
  one-resistor change. Both are on the schematic rather than described in a note,
  per the `schematic-style` rule that anything intended for the board exists on
  the sheet, fitted or DNP. Test point `TP1001`.
* **NRST** — 100 nF to GND exactly as DS13313 Figure 18; a `SW1001` tactile reset
  button (dev-board convenience, `REQ-AR-17`); `TP1002` as a THT hook because this
  is a net you scope during bring-up; and the hierarchical label `MCU_nRESET` out
  to the debug header.
* **PH1-OSC_OUT, PC14, PC15** — no-connect flags. PH1 is unusable with the HSE in
  bypass; PC14/PC15 are the LSE pins, kept clear so a 32.768 kHz crystal stays
  possible on a later revision.

### D-MCU-08 — decoupling and supply-pin treatment

From DS13313 and AN5419:

| Pins | Treatment |
|---|---|
| VDD ×5 (11, 27, 50, 75, 100) | 100 nF each + one 4.7 µF bulk, on the bus that feeds the pin group |
| VDDA (21), VREF+ (20) | 2 × 100 nF + 2 × 1 µF on `+3V3A` |
| VCAP (48, 73) | 2.2 µF each, ESR < 100 mΩ — DS13313 Table 14 |
| VBAT (6) | tied to +3V3 with 100 nF (no coin cell; the RTC is unused) |
| VSSA (19), VSS ×5 | board GND |

The LQFP100 package has **no** VDD33USB, PDR_ON or SMPS pins — checked against the
DS13313 Rev 4 pin table, where those appear only in the LQFP144/UFBGA144 columns.
The house symbol accounts for all 100 pins and matches.

`VSSA` is tied to the board ground here. The precision analogue ground and
reference strategy is a cross-block concern (`ARCHITECTURE.md` §5.3) owned by
`power_rails` / `loadcell_afe`; the MCU's own ADC path (motor phase current) does
not set that bar.

### D-MCU-09 — the debug header is the ARM 10-pin order with UART on 7/8

`J401` is a 2×5 2.54 mm header (`TSW-105-07-F-D`) wired in the standard ARM Cortex
Debug 10-pin order, so an ordinary SWD probe cable plugs straight on:

> **Superseded, review round 4.** `J1003` is now
> `Amodo_Connectors:SAMTEC_SHF-107-01-L-D-SM`, the STM32 14-way 1.27 mm IDC
> socket, pinned exactly as `ARIA_EITSYS_CBs_1` pins its J11 — plus `SWO` on
> pin 10, which is spare there. `R1015` puts 100 R between the header and
> `+3V3`, matching that board's R625. The 10-pin description below is history.

```
1 VTref(+3V3)   2 SWDIO     3 GND      4 SWCLK    5 GND
6 SWO           7 DBG_RX    8 DBG_TX   9 GND     10 nRESET
```

`REQ-AR-15` and the block diagram both put SWD **and** USART3 on *one* header, so
the two console pins take positions 7 and 8 — KEY and NC on the ARM pinout. An SWD
probe drives only 2, 4 and 10 and reads 6, so it never contends; and this part is
SWD-only regardless, because the `.ioc` sets `Trace_Asynchronous_SW`. The 100 Ω
series resistors (`R401`, `R402`) turn a mis-plugged JTAG probe or a shorted
console pin into a nuisance rather than damage.

A 14-way header would have avoided the reuse, but the only 14-way 2-row symbol in
the house library is `SymLifecycle = draft` with no MPN.

### D-MCU-10 — the rail probe header carries logic rails only

`J402` (6-way, `PH1-06-UA`): `1 +5V, 2 +3V3, 3 +3V3A, 4-6 GND`.

**+24 V is deliberately absent.** 24 V two positions from 3.3 V on a 2.54 mm strip
is one slip away from destroying the board, and `power_entry_24v` already owns the
`+24V_SW` test point and current break that `TEST_PLAN.md` §4 asks for. The rails,
their isolation links and their current breaks all belong to their producing
blocks; this header only observes.

The three supplies are grouped and the three grounds are grouped so that each
power symbol's label clears the lane above it — a drawing constraint, noted on the
sheet so nobody "fixes" it into an alternating order.

### D-MCU-11 — reference designators are allocated per sheet, 100 apart

`mcu` uses **1001+**, `test_debug` uses **401+**, from the block's page number in
the root sheet × 100.

This is not cosmetic. All ten blocks are one KiCad project, so designators must be
unique project-wide; ten parallel workers each starting at `U1` guarantees
collisions that only surface as a corrupted netlist (two different parts merged
under one reference) rather than as an ERC error. Allocating by page number gives
every block a range without anyone having to coordinate:

| Page | Sheet | Range |
|---|---|---|
| 2 | `power_entry_24v` | 201+ |
| 3 | `power_rails` | 301+ |
| 4 | `test_debug` | 401+ |
| 5 | `loadcell_afe` | 501+ |
| 6 | `linear_encoder` | 601+ |
| 7 | `temp_sense` | 701+ |
| 8 | `nvm_calibration` | 801+ |
| 9 | `ui_io` | 901+ |
| 10 | `mcu` | 1001+ |
| 11 | `motor_drive` | 1101+ |

Only the two ranges above are claimed by this task; the rest is a suggestion the
integration pass can adopt or re-annotate away.

### D-MCU-12 — spare-I/O breakout (DNP)

Ten MCU pins are unallocated in the `.ioc`. Seven of them (PA8, PA10, PB4, PB7,
PC13, PE3, PE7) plus +3V3 and two grounds land on `J1002`, a **DNP** 2×5 header.

`OQ-06` (EEPROM `nWP`) and `OQ-07` (rail PGOOD / enable) both note that the pins
they need do not exist in the `.ioc` yet. On a development-board revision
(`REQ-AR-17`) a populate-if-needed header turns those from a board spin into a
wire mod. PC14/PC15 and PH1 are excluded for the reason in D-MCU-07.

---

## 3. `.ioc` conflicts with the block diagram

**None found.** Every net in `ARCHITECTURE.md` §3.2 was traced against
`docs/FAFF-2-Electronics-Full.svg` while drawing, and the two agree on all of the
MCU's interfaces: TIM1 PWM + both BREAK inputs, ADC1/2 phase current, SPI2 config,
TIM3/TIM5 encoders, SPI3 + nDRDY, MCO2 to the ADS1235, I2C1 EEPROM, OCTOSPI1 quad
RAM, ULPI to the USB3320, TIM15 to the SMA, and USART3 + SWD to one debug header.

Two `.ioc` facts that are **not** conflicts but which the next reader needs:

1. **`PC2_C` and `PC3_C` carry `ULPI_DIR` and `ULPI_NXT`.** On the LQFP100 these
   are the only bonded PC2/PC3 pins, and they reach the digital I/O through an
   analog switch that firmware must close via `SYSCFG_PMCR` (`PC2SO`/`PC3SO`).
   DS13313 §6.3.16 Table 56 gives the switch impedance as up to 315 Ω. The ULPI
   bus runs at 60 MHz, so this is worth an early look with a firmware engineer —
   exactly the review `TEST_PLAN.md` §1.1 already requires. The pin choice is
   CubeMX's and is not changed here; the note is on the sheet.
2. **The `.ioc` clock tree is still the CubeMX default** (DEC-0013 caveat (a)) and
   must be re-derived from the 24 MHz HSE of D-MCU-01.

---

## 4. Root sheet needs

Every hierarchical label these two sheets expose. The integration pass adds a
matching sheet pin on each block symbol in `faff2_cbs1.kicad_sch`. Direction is
given from the **mcu** block's point of view.

### 4.1 `mcu` → other blocks

| Net | MCU pin | Dir | Counterpart block |
|---|---|---|---|
| `MOTOR_PWM_AH` / `AL` | PE9 / PE8 | out | `motor_drive` |
| `MOTOR_PWM_BH` / `BL` | PE11 / PE10 | out | `motor_drive` |
| `MOTOR_PWM_CH` / `CL` | PE13 / PE12 | out | `motor_drive` |
| `DRV8323_nFAULT` | PE15 | in | `motor_drive` (TIM1_BKIN) |
| `LIMIT_nBRK` | PE6 | in | `ui_io` (TIM1_BKIN2) |
| `MOTOR_I_A` / `_B` / `_C` | PA6 / PC4 / PA7 | in | `motor_drive` |
| `MOTOR_FETTEMP` | PA4 | in | `motor_drive` |
| `VBUS_MON` | PC5 | in | `motor_drive` (DC link, DEC-0011 / OQ-01) |
| `V24_MON` | PC1 | in | `power_entry_24v` |
| `DRV8323_EN` / `_CAL` / `_nCS` | PD10 / PD5 / PD7 | out | `motor_drive` |
| `MOTOR_ENCODER_A` / `_B` / `_I` | PC6 / PC7 / PC8 | in | `motor_drive` |
| `HALL1` / `HALL2` / `HALL3` | PE14 / PD14 / PD15 | in | `motor_drive` |
| `LINEAR_ENCODER_A` / `_B` / `_Z` | PA0 / PA1 / PA2 | in | `linear_encoder` |
| `ADS1235_SCLK` / `_MOSI` | PC10 / PD6 | out | `loadcell_afe` |
| `ADS1235_MISO` | PC11 | in | `loadcell_afe` |
| `ADS1235_nCS` | PA15 | out | `loadcell_afe` |
| `ADS1235_nDRDY` | PD1 | in | `loadcell_afe` |
| `ADS1235_START` / `_nRESET` | PC12 / PD0 | out | `loadcell_afe` |
| **`ADS1235_CLKIN`** | **PC9 (MCO2)** | **out** | **`loadcell_afe`** |
| `CONFIG_SPI_SCK` / `_MOSI` | PA9 / PB15 | out | `motor_drive`, `temp_sense` |
| `CONFIG_SPI_MISO` | PB14 | in | `motor_drive`, `temp_sense` |
| `ADS1120_nCS` | PD3 | out | `temp_sense` |
| `EEPROM_SCL` / `_SDA` | PB8 / PB9 | bidir | `nvm_calibration` |
| `BTN_1` / `BTN_2` | PE0 / PE1 | in | `ui_io` |
| `LED_1` / `LED_2` | PA12 / PA11 | out | `ui_io` |
| `SYNC_TRIG` | PE5 | out | `ui_io` (TIM15_CH1 → SMA) |
| `LIM_A` / `LIM_B` | PD2 / PD4 | in | `ui_io` |

### 4.2 `mcu` ↔ `test_debug` (both sheets declare these)

| Net | MCU pin | Dir from `mcu` |
|---|---|---|
| `SWDIO` | PA13 | bidir |
| `SWCLK` | PA14 | in |
| `SWO` | PB3 | out |
| `DBG_TX` | PD8 | out |
| `DBG_RX` | PD9 | in |
| `MCU_nRESET` | NRST (14) | bidir |

`MCU_nRESET` is generated in `mcu`, which owns its capacitor, its push button and
its test point.

### 4.3 Global power nets — no sheet pins needed

`+3V3` and `GND` (both sheets), `+3V3A` (both), `+5V` (`test_debug` only, on the
rail probe header). These are KiCad power symbols and connect globally.

**`+3V3A` is a request to `power_rails`.** The `mcu` stub note lists
"VDDA / VREF+ analog supply" as an input to this block, so the rail is taken rather
than invented, using the Amodo `+3V3A` power symbol. If `power_rails` names the
MCU analogue rail something else, both of these sheets follow it — one symbol
substitution in each.

### 4.4 Nets that stay inside `mcu`

Local labels, no sheet pins: `ULPI_D0..D7`, `ULPI_CK`, `ULPI_STP`, `ULPI_DIR`,
`ULPI_NXT`, `QSPI_P1_CLK`, `QSPI_P1_nCS`, `QSPI_P1_IO0..IO3`, `USB_DP`, `USB_DM`,
`USB_VBUS`, `USB_CC1`, `USB_CC2`, `USB3320_nRESET`, `USB_REFCLK_24M`,
`HSE_CLK_24M`, `+3V3_USB`, `+1V8_USB`, `SPARE_PA8/PA10/PB4/PB7/PC13/PE3/PE7`.

---

## 5. Test provisions

`TEST_PLAN.md` §4 asks the `mcu` block for: SWD + USART3 to `test_debug`; test
points on `NRST`, `BOOT0`, each supply pin group, the HSE clock in and MCO2; **no**
test points on ULPI or QSPI; and USB-C shield / CC access.

| Asked for | Provided |
|---|---|
| SWD + USART3 to `test_debug` | six hierarchical labels, §4.2 |
| `NRST` test point | `TP1002`, a THT `TestPointHook` — this net is scoped, not just metered |
| `BOOT0` test point | `TP1001`, SMT `TestPoint` — a static level, DMM is enough |
| HSE clock in | `TP1003`, a `TestPointDual` at the **oscillator output**, not at the MCU pin: signal integrity matters on a 24 MHz clock and the dual pad keeps the probe's ground loop small (DEC-0018 ruling 2). Putting it at the pin would have added a stub to the clock line |
| MCO2 | leaves the sheet as `ADS1235_CLKIN`; its test point belongs to `loadcell_afe`, which produces the load on that net — producer-owns-the-break, DEC-0007 |
| each supply pin group | reachable at the decoupling bank of each group (blocks A, D, E, F); `TP1004` on `+3V3_USB` and `TP1005` on `+1V8_USB`, the two rails this sheet actually produces |
| **no** TPs on ULPI / QSPI | none placed; stated on both blocks |
| USB-C shield / CC access | shield through a fitted 0 R link (`R1009`); CC1/CC2 carried on labelled nets to their Rd resistors |

`test_debug` adds six THT GND loops for scope ground clips, spread across the
board, which is what the design standard asks for wherever `TestPointHook` is used.

Bring-up steps this supports directly: **3** (MCU alive — HSE present at `TP1003`,
SWD attaches on `J401`, reset behaves at `TP1002`), **4** (debug console on the same
header), **12** (USB enumeration; `+3V3_USB` and `+1V8_USB` measurable at their
breaks).

---

## 6. ERC state

```
AMODO_KICAD_LIB=/mnt/c/Amodo/AmodoKiCadLib \
  kicad-cli sch erc --severity-all --exit-code-violations \
  -o /tmp/erc.rpt hardware/kicad/faff2_cbs1/faff2_cbs1.kicad_sch
```

**0 warnings.** 121 errors, all of two classes, both caused by the root sheet being
deliberately unwired (DEC-0009) and by `power_rails` not existing yet:

| Class | Count | Why |
|---|---|---|
| `hier_label_mismatch` | 59 | one per hierarchical label: "no matching sheet pin in the parent sheet". Unavoidable until the integration pass draws the sheet pins listed in §4 |
| `label_dangling` | 58 | the same labels again. KiCad reports a hierarchical label as dangling when its net is otherwise a single pin — the `schematic-style` note that KiCad 9 errors on a labelled single-pin net. Adding the sheet pin gives the net its second connection and clears it |
| `power_pin_not_driven` | 4 | `+3V3`, `+3V3A`, `+5V` and `GND` have no power **output** anywhere in the project yet. `power_rails` (OQ-02) supplies all four |

No PWR_FLAG was added to the shared rails on purpose. It would silence the third
class today and then collide at integration: a PWR_FLAG is a power **output**, so
one per block on `+3V3` — times five parallel blocks, plus the real regulator —
becomes a power-output conflict. The one place a flag would be legitimate, a rail
this sheet originates, does not need one: `+3V3_USB` is driven by the USB3320's
`VDD33` power-output pin and `+1V8_USB` by the LDO's `VOUT`.

**Expected end state:** all 121 clear with no change to these sheets once the root
is wired and `power_rails` lands. The DEC-0021 baseline of 0/0 is restorable.

Other checks run, both **clean**:
* the bundled `check_overlaps.py` — 0 findings on every sheet in the project;
* an exported netlist — 60 components, all references unique, and every ULPI, QSPI,
  USB, clock, reset and boot net verified to have exactly its expected membership.

---

## 7. Deviations and things worth a second opinion

1. **Debug header pins 7/8 reused for the UART** (D-MCU-09). Standards-adjacent
   rather than standard; the alternative was a draft-lifecycle 14-way symbol with
   no MPN.
2. **`+3V3A` assumed as the name of the MCU analogue rail** (§4.3). Taken from the
   stub note's interface list and the Amodo library; `power_rails` owns the truth.
3. **CC lines left without an ESD device** (D-MCU-06) — justified, but it is a
   deliberate omission against a blanket reading of the house standard.
4. **PC2_C / PC3_C on ULPI** (§3) — the `.ioc`'s choice, flagged for the firmware
   review that `TEST_PLAN.md` §1.1 already requires.
5. **Reference-designator ranges** (D-MCU-11) — a convention proposed by this block
   because the wave needs one; the integration pass may re-annotate instead.

---

## 8. Integration follow-ups (not done here, by instruction)

These belong to files this task must not edit:

* `docs/REQUIREMENTS.md` — **OQ-03 is answered** (D-MCU-01) and should graduate to a
  `DEC-` entry. **OQ-01 gains supporting evidence** (D-MCU-06): the USB VBUS is
  sensed by the PHY, so PC5 is free for the motor DC link.
* `docs/DECISIONS.md` — the decisions above are candidates for `DEC-` numbers.
* `hardware/kicad/faff2_cbs1/SCHEMATIC_REVIEW_LOG.md` — round 1 entries for the
  self-check findings that shaped these sheets: mid-wire stubs do not connect
  unless the wire is split; every wire end and pin must sit on the 1.27 mm grid;
  title-block comments longer than ~70 characters clip at the page border
  (the DEC-0020 failure mode, in the comment field this time).
* `datasheets/README.md` — three rows for the PDFs added in §9, and the
  "To be selected" rows for the QSPI RAM and the USB-C receptacle can move to
  "Fixed"/"Collected".
* The root sheet — the sheet pins of §4.

---

## 9. Datasheets added

| File | Part | Source |
|---|---|---|
| `datasheets/STM32H723VE_DS13313.pdf` | STM32H723VE — DS13313 Rev 4, Nov 2023 | ST document, via a distributor mirror (`st.com` was unreachable from this environment) |
| `datasheets/USB3320.pdf` | Microchip USB3320 — DS00001792F | Microchip |
| `datasheets/IS66WVS4M8.pdf` | ISSI IS66/67WVS4M8ALL/BLL — Rev A2, 2024-07-08 | ISSI |
