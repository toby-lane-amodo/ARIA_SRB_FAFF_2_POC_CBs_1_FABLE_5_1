# Analog front end design record — `loadcell_afe` and `temp_sense`

Design reasoning for the two analog front-end block sheets of
`ARIA_SRB_FAFF_2_POC_CBs_1`. Written by the `actuator-sch-afe` block task,
2026-09-03.

Scope: `hardware/kicad/faff2_cbs1/loadcell_afe.kicad_sch` and
`hardware/kicad/faff2_cbs1/temp_sense.kicad_sch`. Also added:
`hardware/kicad/faff2_cbs1/faff2_afe.kicad_sym` (project-local symbol library,
one entry in `sym-lib-table`), five datasheets, and the `AGENTS.md` library rule
correction. `docs/DECISIONS.md` and `SCHEMATIC_REVIEW_LOG.md` were deliberately
left untouched during the parallel wave — §8 lists what should be folded into
them.

**This file answers `OQ-04` (RTD vs NTC for the two temperature channels).**

---

## 1. What was built

### `loadcell_afe` — ADS1235 bridge front end

```
J501 (8-way 5 mm screw terminal, HBK S2M six-wire cable)
  SIG+/SIG-   ── 100R 0.1% ──┬── 1nF C0G to GND (x2)  ──┬─▶ AIN4 / AIN5
                             └── 10nF C0G differential ─┘   (PGA gain 128)
  SENSE+/SENSE- ─ 100R 0.1% ─┬── 1nF C0G to GND (x2)  ──┬─▶ REFP0 / REFN0
                             ├── 10nF C0G differential ─┘   (ratiometric)
                             └── 100k reference monitor
  EXC+  ◀── R508 (0R link) ◀── +5VA          EXC- ──▶ R509 (0R link) ──▶ GND
  SHLD  ──▶ R510 (0R link) ──▶ GND
  R506 / R507 (0R, DNP)  tie SENSE to EXC at the connector for a 4-wire cell

ADS1235   AVDD = +5VA, DVDD = +3V3, AIN0..AIN3 biased to AVDD through 10k
          SPI3 + START + nRESET + nDRDY through 47R series terminators
          CLKIN from MCO2 through R520; R521 (DNP) instead grounds CLKIN
```

### `temp_sense` — ADS1120, two 3-wire Pt1000 channels

```
J701 / J702 (4-way 3.5 mm push-in: 1 = lead A, 2 = lead B, 3 = return, 4 = screen)
   lead A ── 100R 0.1% ──┬── 10nF to GND  ──┬─▶ AIN0 (ch1) / AIN3 (ch2)
   lead B ── 100R 0.1% ──┼── 10nF to GND  ──┤   AIN1 (ch1) / AIN2 (ch2)
                         └── 100nF differential
   returns ─────────────────▶ R707 5k 0.05% ──▶ GND      (shared by both channels)
                                │
                                └─ 100R/10nF/100nF filter ─▶ REFP0 / REFN0

R708 / R709 (0R, DNP) tie lead B to the return for a 2-wire probe
ADS1120   AVDD = +5VA, DVDD = +3V3, CLK tied to DGND (internal oscillator)
          SPI2 (shared config bus) through 47R series terminators
```

---

## 2. Decisions

### DEC-A1 — `OQ-04` answered: RTD, not NTC. Pt1000, 3-wire, class A

**Sensing element: a 3-wire Pt1000 to IEC 60751 class A**, on both channels.

*Reasoning.* `REQ-EL-07` asks for 1 °C at the load cell and at the linear-encoder
rail mid-point, over the 10…40 °C operating range (`REQ-EN-01`). Three things
decide it:

1. **The ADS1120 was chosen for this job** (DEC-0005). Its two matched IDACs
   exist to excite an RTD ratiometrically and to cancel lead resistance
   automatically; with an NTC that hardware sits idle.
2. **Interchangeability.** A class-A RTD is accurate to ±(0.15 + 0.002·|t|) °C
   *without* per-part calibration. An NTC needs its β and R25 characterised per
   part to reach 1 °C, and `nvm_calibration` would have to carry a curve per
   probe. The probes are on the actuator, replaceable, and the board should not
   care which one is fitted.
3. **Linearity and self-heating.** Pt1000 changes 3.85 Ω/°C linearly; a 10 k NTC
   changes by ~4 %/°C and needs a much larger dynamic range or a series
   linearising resistor.

**Pt1000 rather than Pt100** because every source of error in this circuit is an
error *in ohms* — filter-resistor mismatch, lead resistance, IDAC compliance
drop — and at 3.85 Ω/°C instead of 0.385 Ω/°C each one costs ten times less in
degrees. The worked comparison is on the sheet.

*Consequence, and the NTC path is not closed.* The block diagram allows
"RTD / NTC" and the sheet keeps that open: **R708 / R709 (0R, DNP) tie the sense
lead to the return at the connector**, which turns each channel into a 2-wire
measurement that will take a 2-wire Pt1000, a Pt100 or a thermistor. Lead
compensation is lost, so it is the lower-accuracy option, and an NTC would also
need different IDAC and gain settings. The house-stocked
`RTD_PT100_3W_D6X50_3M` probe is a Pt100 and works with **no BOM change at all**
— see DEC-A3.

### DEC-A2 — Two 3-wire RTDs share one ADS1120 and one reference resistor

The ADS1120 datasheet (SBAS535D §9.2.2) gives two 3-wire arrangements. The
default routes the IDACs to two *spare* pins, which costs four analog inputs per
channel — one channel per device. The variant used here routes each IDAC to the
same pin it measures, and the datasheet states its consequence directly: *"even
two 3-wire RTDs sharing the same reference resistor can be measured with a
single device"*. That is what makes one ADS1120 enough for `REQ-EL-07`.

Its condition is that the input filter resistors, which then carry the IDAC
current, are *"small enough and well matched"* — because a mismatch ΔR adds
directly to the measured RTD resistance. Hence **100 Ω 0.1 %** (worst case
ΔR = 0.2 Ω ⇒ 0.05 °C on a Pt1000, and it is a fixed offset that calibrates out).
This is also the second reason Pt1000 beats Pt100 here: the same 0.2 Ω would be
0.52 °C on a Pt100.

### DEC-A3 — Operating point: 250 µA IDACs, 5 k reference, gain 4

| | Pt1000 (default fit) | Pt100 (alternate) |
|---|---|---|
| IDAC1 = IDAC2 | 250 µA | 250 µA |
| R707 | 5 kΩ 0.05 %, 5 ppm/°C | **unchanged** |
| VREF = 2·I·R707 | 2.5 V | 2.5 V |
| PGA gain | 4 | 32 |
| FSR = ±VREF/gain | ±625 mV | ±78.1 mV |
| RTD over 10…40 °C | 1039…1155 Ω | 103.9…115.5 Ω |
| PGA input | 260…289 mV | 26…29 mV |

**Only the ADS1120 register settings differ — no BOM and no layout change.** So
the board takes either probe type.

VREF is set near AVDD/2 so the RTD common-mode voltage lands in the middle of
the PGA range, as the datasheet advises; the checks it asks for all pass with
margin (V_CM ≈ 2.64 V against a 1.36…3.64 V window at gain 4; IDAC compliance
needs ≤ 4.1 V and the highest node sits at 2.79 V).

**Gain 4 rather than 8 is deliberate.** Gain 8 would use the range better but
over-ranges above about 65 °C. These probes sit on an actuator whose motor is
adjacent, an over-range is a silent failure, and the resolution at gain 4 is
still 0.02 °C — fifty times better than `REQ-EL-07` needs. Firmware can move to
gain 8 if a build ever needs the extra resolution over a bounded range.

`R707` is a Vishay PLT0805Z5001AST5: 0.05 %, **5 ppm/°C**, comfortably inside
the datasheet's "±10 ppm/°C or better is advisable". Its stability is the single
most important passive value on the sheet, because it sets the measurement
scale directly.

### DEC-A4 — Temperature error budget (Pt1000 build)

| Term | Contribution |
|---|---|
| Pt1000 class A at 40 °C | ±0.23 °C |
| R707 tolerance 0.05 % | ±0.14 °C |
| R707 drift, 5 ppm/°C over ±15 °C from calibration | ±0.02 °C |
| Filter-resistor mismatch, 0.2 Ω worst case | ±0.05 °C |
| ADS1120 INL, 20 ppm FSR | ±0.02 °C |
| **RSS** | **±0.28 °C** |
| Worst-case sum | ±0.46 °C |

Two further terms are pure **gain** errors and are excluded above because either
remedy removes them: ADC gain error (0.1 % max) and IDAC current mismatch
(0.3 % max, i.e. ±0.41 °C on its own). They are removed by a one-point
calibration into the `nvm_calibration` EEPROM, or in firmware by **IDAC
rotation** — swapping which IDAC drives which input between readings and
averaging, which this topology supports directly and which the ADS1120's IDAC
routing registers make a register write. Even with neither, the total stays
inside `REQ-EL-07`. Self-heating is 63 µW in 1000 Ω, under 0.02 °C.

### DEC-A5 — Load cell: ratiometric 6-wire by default, 4-wire by fitting two links

`DEC-0014` requires both. The sense lines drive REFP0/REFN0, which is exactly
what the ADS1235 datasheet §8.3.4.2 prescribes for a six-wire bridge: *"for
6-wire strain-gauge bridge applications that use excitation-sense connections,
connect the excitation sense lines to the reference input pins"*. Because the
reference and the signal then come from the same excitation, drift and noise in
the 5 V rail cancel — the rail does not have to be a precision reference, which
is why `+5VA` from `power_rails` is enough.

**R506 and R507 are DNP.** Fitting them ties SENSE± to EXC± at the connector,
which is the 4-wire configuration: the reference stops tracking the cable drop
and Kelvin sensing is lost. Default build is 6-wire, per DEC-0014.

`J501` is a Phoenix 1729076 8-way 5 mm screw terminal, ordered
SIG+, SIG−, EXC+, SENSE+, SENSE−, EXC−, SHLD, SHLD. That order is not
cosmetic: it is the order that lets the six conductors fan out to the ADS1235's
input and reference pins **without a single wire crossing**, and it keeps the
two excitation terminals apart so a slip cannot short the excitation. The S2M
cable colours are silkscreened on the sheet from data sheet B03594.

Screw terminals rather than a plug were chosen so that the resistive bridge
simulator of `TEST_PLAN.md` bring-up step 6 can be wired in without a mating
connector — the same reason the temperature probes use push-in terminals.

### DEC-A6 — Input and reference filters are the datasheet reference design

Both sheets use the same shape: series resistors per leg, a common-mode
capacitor from each leg to AVSS, and a differential capacitor ten times larger
between the legs. The 10:1 ratio is the datasheet's own recommendation and it is
what desensitises the filter to common-mode capacitor mismatch, which would
otherwise convert common-mode noise into differential noise straight into the
measurement.

**The signal filter and the reference filter are deliberately identical** in
both sheets, because the datasheet requires their corner frequencies to match
for a ratiometric measurement to settle correctly. `loadcell_afe`: 100 Ω / 1 nF
C0G / 10 nF C0G — 76 kHz differential, 1.6 MHz common mode, against the ADC's
own 60 kHz PGA antialias filter (C514, 4.7 nF C0G). `temp_sense`: 100 Ω / 10 nF
/ 100 nF, tighter because the temperature channels run at tens of SPS.

The 1 nF common-mode capacitors in `loadcell_afe` are 1 % C0G parts. On the
40 nV-scale bridge path their **matching** is what matters, not their value.

`R505` (100 k across the sense pair) is the datasheet's reference-monitor
resistor: it collapses VREF if the load cell is unplugged so the ADC's REFL_ALM
flag asserts, which turns a disconnected cable into a reported fault instead of
a plausible-looking reading. It sits on the **bridge side** of the reference
filter resistors deliberately — on the ADC side its 50 µA would develop ~10 mV
across them and put a 0.2 % scale error on every force reading.

### DEC-A7 — Unused ADS1235 inputs are biased through resistors, not tied

The datasheet says to tie unused analog inputs to mid-supply or to AVDD.
AIN0..AIN3 go to AVDD **through 10 k each** (R522..R525) rather than directly,
because those same pins are the ADS1235's GPIO and AC-bridge-excitation outputs,
referenced to AVDD/AVSS. A hard tie means a firmware mistake shorts an output to
the rail; 10 k limits it to 0.5 mA and costs four resistors. Input leakage is
nanoamps, so the pins still sit at AVDD.

### DEC-A8 — The 47 Ω series resistors are also the SPI isolation links

The ADS1235 datasheet asks for series resistors on the digital lines to damp
overshoot; `TEST_PLAN.md §3.3` asks for links that take each peripheral off its
shared bus. One part does both jobs: remove R511..R518 (SPI3, `loadcell_afe`) or
R712..R715 (SPI2, `temp_sense`) and that ADC is off the bus. This matters more
on SPI2, which `temp_sense` shares with `motor_drive` (`ARCHITECTURE.md §5`).

Likewise **R508 and R509 serve as both the isolation link and the
current-measurement break** on the bridge excitation feed and return. Opening
one isolates the load cell; replacing one with a meter measures the excitation
current against the 15 mA of the `CALC` power budget. `TEST_PLAN.md §3.1` lists
those as separate provisions; they are never needed simultaneously, and a second
0R in series would only add a joint. Recorded here as a deliberate reading.

### DEC-A9 — CLKIN has a bring-up fallback, and the MCO2 clock tree needs work

`REQ-AR-09` puts the ADS1235's master clock on MCO2. `R520` (fitted) carries it;
`R521` (DNP) instead grounds CLKIN, which selects the ADC's internal 7.3728 MHz
oscillator. Fit one, never both. The fallback costs one DNP resistor and means
`loadcell_afe` can be brought up (`TEST_PLAN.md` step 6, the most important
electrical result on the board) before the MCU clock tree is finished.

**Finding for the `mcu` / firmware task:** the `.ioc` leaves
`RCC.MCO2PinFreq_Value` at the CubeMX default **64 MHz**. The ADS1235 accepts
1–8 MHz on CLKIN (7.3728 MHz nominal), so as it stands the clock tree would
drive the ADC four times over its absolute maximum. This is a clock-tree
question, not a schematic one — `DEC-0013` already flags the clock tree as
untouched CubeMX default — but it must be resolved before firmware enables MCO2.

### DEC-A10 — Test provisions, and where they deviate from the skill

Per `TEST_PLAN.md §4`, `loadcell_afe` has test points on the excitation, both
sense lines, the ADC reference and every MCU-facing net; `temp_sense` has them
on all four probe leads, the reference and the SPI2 nets; both have GND hooks in
the same column for the scope ground clip. `FL501`/`FL502` are U.FL connectors
on the ADC-side SIG+/SIG− nodes — `TEST_PLAN.md §2.3` names that net as the U.FL
candidate because its noise floor decides `REQ-FF-04`. They are placed
**symmetrically** (same stub length either side) so the differential pair stays
balanced.

*Tension recorded.* The `schematic-style` skill says bring-up access should go on
populate-if-needed connectors rather than bare test points. This project's own
`TEST_PLAN.md §4` asks specifically for "SPI3 hooks", and `DEC-0018` ruling 2
adopts the house standard's per-net test-point selection. Project artefacts
outrank general practice (`DEC-0018` precedence), so hooks are used; the
system-level debug header stays `test_debug`'s.

### DEC-A13 — No ESD protection on `J501`, `J701` or `J702` (closed, `DEC-0027`)

Confirmed by the captain in review round 3. A clamp's capacitance and reverse leakage land
directly on the paths `REQ-FF-04` is written about, and on the ratiometric bridge an asymmetric
load becomes a differential error. Both connectors are internal and not hot-plugged in service.
`DEC-0027` carries the full reasoning and the condition that reopens it; the design-wide,
exposure-based protection policy this follows is audited interface by interface in
`docs/decisions/actuator-sch-review-r1.md`, round 2 item 3.

### DEC-A11 — One ground, and no PWR_FLAGs on these sheets

`GND` is a single net across both sheets; there is no separate AGND. Analog and
digital return separation is a layout concern on a 4-layer stackup with solid
ground planes (`DEC-0018` ruling 7), not a schematic one, and split grounds in
the schematic would force a star point that no block owns. This matches the
cross-block rule from the power blocks.

`AVDD` on both ADCs and the bridge excitation come from **`+5VA`**, the quiet
analog rail; `DVDD` comes from `+3V3` so both serial interfaces sit at STM32
logic level. No `PWR_FLAG` appears on either sheet — the power sheets own every
one of them, and a second flag on a shared rail is a power-output conflict at
merge.

### DEC-A12 — Corrected ADS1235 symbol lives in a project-local library

`Amodo_ADCs:ADS1235` has a defect: its exposed-pad pin carries **number 31**,
which is REFN0 on the real part (SBAS824 pin table). The VQFN RHB footprint's
thermal pad is **pad 33**. As shipped, the symbol shorts the thermal pad to the
negative reference and leaves pad 33 unassigned — a netlist-level fault that
would reach the board.

Fixed copy in `hardware/kicad/faff2_cbs1/faff2_afe.kicad_sym`, registered in the
project `sym-lib-table` through `${KIPRJMOD}`:

1. EP pin number **31 → 33**.
2. Datasheet URL `ads1120.pdf` → **`ads1235.pdf`** (it pointed at the wrong part).
3. BYPASS pin type `power_in` → **`passive`**. The datasheet calls it an analog
   output (internal sub-regulator bypass); as a power input it demands a driver
   that does not exist and produces a false ERC error.

**For the captain:** these three corrections should be made in
`Amodo_ADCs.kicad_sym` upstream, after which this project-local copy can go.

*Incident worth recording.* `ADS1235` is an **uncommitted local addition** to the
AmodoKiCadLib working copy. A targeted `git checkout -- Amodo_ADCs.kicad_sym`
therefore does not revert an edit to it — it deletes the whole symbol. That
happened here and was repaired by restoring the original block from
`Amodo_ADCs.bak` (24 symbols, CRLF, EP = 31, BYPASS `power_in`,
`ads1120.pdf` — verified byte-level after restoration). The library is back
exactly as found. `AGENTS.md` now warns about it.

---

## 3. Root sheet needs

Every interface these two sheets expose. The integration pass that wires the
root sheet (`DEC-0009`) needs a sheet pin per row.

### `loadcell_afe` hierarchical labels

| Label | Shape | MCU pin (`.ioc`) | Function |
|---|---|---|---|
| `ADS1235_SCLK` | input | PC10 | SPI3 clock |
| `ADS1235_MOSI` | input | PD6 | SPI3 MOSI → ADS1235 DIN |
| `ADS1235_MISO` | output | PC11 | ADS1235 DOUT/nDRDY → SPI3 MISO |
| `ADS1235_nCS` | input | PA15 | SPI3 hardware NSS |
| `ADS1235_nDRDY` | output | PD1 | data ready, EXTI1 |
| `ADS1235_START` | input | PC12 | conversion start |
| `ADS1235_nRESET` | input | PD0 | hardware reset |
| `ADS1235_CLKIN` | input | PC9 | RCC_MCO2 ADC master clock — see DEC-A9 |

### `temp_sense` hierarchical labels

| Label | Shape | MCU pin (`.ioc`) | Function |
|---|---|---|---|
| `ADS1120_nCS` | input | PD3 | chip select |
| `CONFIG_SPI_SCK` | input | PA9 | SPI2 clock, **shared bus** |
| `CONFIG_SPI_MOSI` | input | PB15 | SPI2 MOSI, **shared bus** |
| `CONFIG_SPI_MISO` | tri_state | PB14 | SPI2 MISO, **shared bus** |

`CONFIG_SPI_MISO` is declared `tri_state`, not `output`: three blocks drive that
one wire, each only while its own chip select is low. If `motor_drive` declared
it `output`, the root sheet would have two outputs on one net. Worth reconciling
at integration.

**`ADS1120_nDRDY` has no `.ioc` pin.** It is brought out to `J703` CH0 (it was
`TP707` until the round-3 review put the whole interface on one plug) and nothing
else; firmware polls the dual-function DOUT/DRDY line instead, which is what the
datasheet expects when the dedicated pin is unused, and at a few readings per
second it costs nothing. If an interrupt is ever wanted, allocate a spare GPIO in
the `.ioc` first (`DEC-0013`) and the wire is a short run on this sheet.

### Global power nets consumed (no sheet pin needed)

`+5VA` — ADS1235 AVDD **and** the 5 V bridge excitation (~15 mA), ADS1120 AVDD.
`+3V3` — both DVDDs. `GND`. All three are global power symbols, so they connect
across the hierarchy without root wiring.

---

## 4. Reference designators

`loadcell_afe` uses the **500 series**, `temp_sense` the **700 series**, per the
scheme `AGENTS.md` records. Checked: no instance designator on these sheets
collides with any other sheet in the project.

---

## 5. Verification

Run from the repo root, against the whole project (a single sheet on its own has
no `sym-lib-table` and reports spurious library and hierarchy errors):

```sh
AMODO_KICAD_LIB=/mnt/c/Amodo/AmodoKiCadLib AMODO_3D=/mnt/c/Amodo/AmodoKiCadLib/3D \
  kicad-cli sch erc --severity-all --exit-code-violations \
  -o /tmp/erc.rpt hardware/kicad/faff2_cbs1/faff2_cbs1.kicad_sch
```

| Check | Result |
|---|---|
| ERC, `--severity-all` | `loadcell_afe` 8 violations, `temp_sense` 4 — **all `hier_label_mismatch`, one per hierarchical label.** No warnings, no other class, nothing suppressed |
| Netlist vs. an independent connectivity model | **All 47 `loadcell_afe` nets and all 25 `temp_sense` nets identical, node for node** |
| Designator uniqueness across all sheets | no collisions |
| Bundled overlap checker | 1 + 9 findings, **every one a checker artefact** confirmed against renders (§7) |
| Render sweep | both sheets swept at 10 px/mm |

The `hier_label_mismatch` errors are the residual `AGENTS.md` describes: no sheet
pin exists on the parent until the root sheet is wired. They clear at
integration. Neither sheet contributes a `label_dangling` error, because every
labelled net also reaches a test point — a side effect of the `TEST_PLAN.md §4`
provisions rather than a workaround.

---

## 6. Datasheets added

| File | Part | Used for |
|---|---|---|
| `ADS1235.pdf` | SBAS824, Oct 2018 | pin table, figure 84 filter design, noise table 1, §8.3.4.2 ratiometric reference, §9.1.3 unused inputs |
| `ADS1120.pdf` | SBAS535D, Jun 2026 | pin table, §9.2.2 3-wire RTD, IDAC and PGA limits |
| `HBK_S2M.pdf` | B03594, Feb 2025 | six-wire cable colours, 350 Ω bridge, 2 mV/V, 5 V reference excitation |

Also copied in on the captain's instruction, as record-keeping for the already
landed power block (no design action here):
`Littelfuse-Fuse-157T-Datasheet.pdf`, `tvs-diodes-5.pdf`, `QFLB9101-1111029.pdf`.

---

## 7. Tooling notes

Two are worth passing on because they cost real time.

**A stub that lands mid-wire does not connect, junction dot or not.** KiCad only
joins wires that actually end at the point. The tell is `pin_not_connected` on a
part that looks fully wired, or a power symbol that connects to one capacitor and
nothing else. Already recorded in `AGENTS.md`.

**A child sheet's symbol instance path must use the *root sheet's* sheet-symbol
UUID**, not the child file's own UUID. Get it wrong and the sheet loads, all
components appear, and almost nothing is connected — a very quiet failure.

The bundled `check_overlaps.py` disagrees with KiCad on rotated symbols, in two
ways. Both were resolved against renders at 10 px/mm, and both are worth fixing
in the `schematic-style` skill:

- It mis-places the **body** of a mirrored or 90°-rotated symbol, reflecting it
  about the symbol origin. That produces false `body-vs-wire` and
  `body-vs-blockborder` hits — here on `J701`, `J702` and the rotated 100 Ω
  resistors — and could equally hide a real one.
- **KiCad flips field justification for a 180°-rotated symbol**, so `justify
  left` there renders right-aligned and the text grows *leftward* from its
  anchor. The checker does not model the flip. These sheets set `justify right`
  on 180°-rotated symbols so every field grows rightward like all the others,
  which is what the field offsets are designed around; the checker then reports
  those fields on the wrong side. All four such findings were checked in a
  render.

Its findings on unrotated symbols are reliable, and all of those were fixed.

---

## 8. To fold into the shared docs

Left for the captain / integration pass, since `docs/DECISIONS.md` and
`SCHEMATIC_REVIEW_LOG.md` are shared files that this parallel task did not edit.

- **`DECISIONS.md`:** DEC-A1 answers `OQ-04` and should graduate to a numbered
  `DEC-` entry. DEC-A3, DEC-A5, DEC-A8, DEC-A9 and DEC-A12 are the other
  judgement calls worth numbering.
- **`REQUIREMENTS.md`:** `OQ-04` can be closed.
- **`SCHEMATIC_REVIEW_LOG.md`:** two in-house review points — the
  `schematic-style` "connectors not bare test points" tension resolved in favour
  of `TEST_PLAN.md §4` (DEC-A10), and the corrected ADS1235 symbol (DEC-A12).
- **`datasheets/README.md`:** the three parts of §6 belong in its *Collected*
  table, and its "to be selected" row for the temperature probes is now answered
  by DEC-A1.
- **`ARCHITECTURE.md` §6:** the `OQ-04` gap row can go.
