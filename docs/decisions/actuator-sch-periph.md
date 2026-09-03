# `linear_encoder`, `nvm_calibration`, `ui_io` — design record

Block task: **PERIPHERALS**, covering exactly three sheets —
`hardware/kicad/faff2_cbs1/linear_encoder.kicad_sch`,
`hardware/kicad/faff2_cbs1/nvm_calibration.kicad_sch` and
`hardware/kicad/faff2_cbs1/ui_io.kicad_sch`. Nothing else in the repo was edited
except this file and the five datasheets listed in §8.

Everything here is subordinate to the authorities named in `AGENTS.md`. The `.ioc`
is quoted, never changed: **no pin on this board was re-assigned.**

---

## 1. What was drawn

| Sheet | Blocks | Parts | Nets |
|---|---|---|---|
| `linear_encoder.kicad_sch` | **A** IKP11 read-head connectors J601/J602 · **B** termination + mode select · **C** RS-422 → 3V3 receivers · **D** outputs to TIM5 · **E** 5 V read-head supply + head config access · **F** receiver supply, enables, spare channel | 26 | 18 |
| `nvm_calibration.kicad_sch` | **A** I2C1 bus, pull-ups, isolation · **B** EEPROM, decoupling, write protect · **C** ground hooks | 15 | 12 |
| `ui_io.kicad_sch` | **1** status LEDs · **2** user buttons + external button connector · **3** SYNC/TRIGGER out · **4** end-of-stroke limits + TIM1 break | 39 | 27 |

Reference designators follow the `AGENTS.md` per-sheet allocation keyed to the
root page number: `linear_encoder` **6xx**, `nvm_calibration` **8xx**,
`ui_io` **9xx**. Verified by exported netlist — no designator collides with the
`mcu`, `test_debug`, `power_*`, `loadcell_afe`, `temp_sense` or `motor_drive`
sheets already on `main`.

---

## 2. `linear_encoder` decisions

### D-PER-01 — Both mating connectors are fitted, in parallel

The ordered head is `IKP11-…-C1`, and the **C1 option carries two interfaces on
the read head at once**: a 10-way 0.5 mm FFC receptacle (Würth 687110182122) and
a 1×10 row of 1.27 mm solder pads (datasheet rev 3.7, pp. 5–6). The board
therefore presents both, wired in parallel:

* **J601** `FH12-10S-0.5SH(55)` — 10-way 0.5 mm FFC. Mates the stock Bogen
  accessory cable (`KABL-FFC-P0.5x10-L100` / `-L300`), so the head can be
  connected with no fabrication at all. This is the primary path.
* **J602** `FTSH-105-01-L-DV-K-TR` — 2×5 1.27 mm shrouded header. This is the
  "10-way 1.27 mm header" of `REQ-PS-09`, reached from the head's solder-pad row
  with a ribbon, **and** it is the quadrature injection point that `TEST_PLAN §4`
  asks for. Head pin *n* = J602 pin *n*.

*Why both.* One connector costs a few pads on a board that is deliberately
oversized (`REQ-AR-17`). Fitting only the FFC would leave the build dependent on
one cable's contact orientation; fitting only the 1.27 mm header would throw away
the vendor-supported cable. `REQ-PS-09` names the 1.27 mm header, and the task
brief names both, so both are drawn.

*Open build point, recorded on the sheet.* The FFC cable's contact side (type A =
same side, type D = opposite side) must be checked against J601 — a **bottom
contact** receptacle — before the cable is ordered. Bogen do not state it in the
IKP11 datasheet. If the stock cable turns out to be wrong-handed, J602 is the
fallback and nothing else changes.

### D-PER-02 — Receiver is the AM26LV32, run from 3V3

`Amodo_Digital_ICs:AM26LS32Ax` (symbol name is stale; its `Value`, `mpn` and
datasheet are all **AM26LV32**, `AM26LV32CDR`, SOIC-16). Pin map verified
against TI SLLS202H Table 5-1, fetched live and committed.

Three of the four receivers carry A/B/Z; the fourth is the spare. Why this part:

* **3.3 V supply**, so the outputs are native 3V3 logic — `REQ-PS-06` is met
  without a level shifter in the 1 MHz path.
* **−0.3 V to +5.5 V input common-mode range** accepts the 5 V head directly.
* **32 MHz** switching against the 1 MHz per channel of `REQ-PS-07` — 32× margin.
* **Open-circuit, shorted *and* 100 Ω-terminated fail-safe** (SLLS202H §8.4.1).

Both enables are tied active: `G` (pin 4) high, `~G` (pin 12) low.

### D-PER-03 — No external fail-safe bias network

The obvious RS-422 practice — bias the pair with a pull-up/pull-down pair so an
absent driver reads as a defined level — is **deliberately omitted**, because the
AM26LV32 already has *terminated* fail-safe. With the 120 Ω fitted and the head
unplugged or unpowered, the outputs sit high. The failure mode is a stalled
count, which firmware can detect as "commanded to move, position not changing",
rather than the random counts an unbiased receiver would produce. Six resistors
saved and one fewer thing to get wrong.

### D-PER-04 — Termination is 120 Ω per pair; a documented single-ended mode replaces the usual bias

`R603` / `R604` / `R605` = 120 Ω across each pair, exactly as the IKP11 datasheet
asks ("load resistor Z0 = 120 Ω at receiving end"). `TEST_PLAN §4` wants the
termination fitted **and** removable: these are ordinary 0603 parts, removed with
an iron when the block is switched to single-ended mode.

`SB601` / `SB602` / `SB603` (normally-open solder bridges) tie each inverting
input to `ENC_VREF`, a 1.65 V mid-rail from a 1 k/1 k divider with a 100 nF
bypass. Two documented modes:

| Mode | Termination | Bridges | Use |
|---|---|---|---|
| RS-422 (default, matches the ordered `D1` head) | fitted | open | normal operation |
| Single-ended / TTL | removed | closed | a `D3` TTL head, or bench injection through J602 with no head fitted |

In single-ended mode a 0–3.3 V or 0–5 V source on `ENC_x_P` decodes against the
1.65 V reference. This is what makes "inject a quadrature signal without the read
head" (`TEST_PLAN §4`) a two-minute job rather than a differential test rig.

### D-PER-05 — 5 V read-head supply is filtered and separately meterable

`+5V` → `R601` 0 Ω (the block current break of `TEST_PLAN §3.1`) → `FB601`
600 Ω@100 MHz ferrite → `+5V_ENC`, with 10 µF + 100 nF and `TP601`. Lifting R601
meters the read head against the 200 mA the `CALC` budget allots it; the head
draws < 65 mA, so this is a real budget check rather than a formality.

`+5V_ENC` is a **local label**, not a power symbol: the house library has no
`+5V_ENC` symbol and adding one for a single branch rail is not justified. The
net is drawn as an explicit run so the break is visible.

`D601` (PESD5V0U1UB) clamps the supply at the connector — the FFC is the one
thing on this sheet that gets hot-plugged during bring-up.

### D-PER-06 — `!PROG` is held inactive; `SDO` gets an observation point

The IKP11 is user-reconfigurable (resolution, filter, maximum output frequency)
through `!PROG` / `SDO`. No `.ioc` pin exists for either and none is requested.
`R602` (10 k to `+5V_ENC`) holds `!PROG` inactive so the head can never fall into
programming mode by accident; `TP602` observes `SDO`. Both signals appear on
J602, so a Bogen programming adapter can reach them without board changes.

### D-PER-07 — No test points on the differential pairs

`TEST_PLAN §4` asks for test points on the receiver outputs and the 5 V supply,
which is what is fitted (`TP603`–`TP605` hooks, `TP601` pad). Nothing is placed
on the terminated 1 MHz differential lines: a probe stub there is exactly the
discontinuity `TEST_PLAN §2.2` and DEC-0018 ruling 1 forbid, and the receiver
outputs carry the same information single-ended.

---

## 3. `nvm_calibration` decisions

### D-PER-08 — EEPROM is the 24FC16T-I/OT

`Amodo_Digital_ICs:24FC16T-I/OT`, Microchip 16 kbit (2048 × 8) I²C EEPROM in
SOT-23-5. Pin map verified against DS20001703R p.1 by extracting the package
drawing's text coordinates (`1 SCL · 2 VSS · 3 SDA · 4 VCC · 5 WP`) — the Amodo
symbol matches. 1.7–5.5 V, 1 MHz capable, 4 M erase/write cycles.

*Sizing.* 2 KB holds coefficients, not tables: force and temperature calibration
constants, the variant (V50N / V10N — under DEC-0010 the variants differ only by
a calibration constant), the board serial number and the build state that
`TEST_PLAN §1.4` requires. Bulk force profiles live in the OCTOSPI1 RAM on the
`mcu` sheet (DEC-0006).

*Recorded caveat.* The 24xx**16** uses all three block-select bits internally, so
it answers to the whole `1010xxx` address space and has no A0/A1/A2 pins. **No
second `1010`-family device can share I2C1.** It is the only device on the bus
today; if another is ever added, drop to a 24xx02/04 first. This is on the sheet.

### D-PER-09 — Write protect resolved without an MCU pin — closes OQ-06

OQ-06 asked whether `nWP` should be tied off or given a pin. **Tied off, with a
link and a test point**, and no `.ioc` change:

* The part's pin is **active-high `WP`**, not `nWP` — the stub note's name was a
  placeholder. The net is `WP`.
* `R805` 10 k to GND holds it low, so the device is writable and firmware can
  store calibration whenever it likes. This is the right default for a PoC that
  will be recalibrated repeatedly.
* `SB803` (normally-open bridge) to `+3V3` locks the device permanently, for a
  unit going out of the lab.
* `TP803` lets a programming jig drive `WP` either way.

Spending an MCU pin on a line that changes once per board life is not a good
trade on a part that has 4 million write cycles.

### D-PER-10 — Pull-ups and bus isolation, and who owns them

* `R803`/`R804` 4k7 pull-ups, each in series with a **removable 0 Ω link**
  (`R801`/`R802`) — the "pull-ups on removable links" of `TEST_PLAN §4`.
* `SB801`/`SB802`, in-line normally-closed solder bridges, cut to take the
  EEPROM off I2C1 **while the bus stays pulled up** — the block isolation of
  `TEST_PLAN §3.3`. A bridge is used rather than a 0 Ω because it keeps the bus
  run straight; the pull-up links are vertical, so 0 Ω resistors suit there.
* `TP801`/`TP802` hooks plus two GND hooks (`TP804`/`TP805`).

**Cross-block:** these are the only pull-ups on I2C1 and this block owns the bus
break. The `mcu` block must not add either.

The SDA pull-up crosses the SCL run with no junction — a deliberate crossing so
both pull-up columns sit at the same height, per the `schematic-style`
paired-alignment rule.

---

## 4. `ui_io` decisions

### D-PER-11 — Limit switches are normally-closed, sensed independently, ANDed into the break

The safety-critical part of this task. `SPEC §9.1` asks only for a firmware kill
(`REQ-SF-02`); the block diagram and the `.ioc` both carry the stronger hardware
path (`REQ-SF-05`, DEC-0012). What is drawn:

* **Normally-closed** switches. Each has its own two-wire loop:
  `+3V3 → 1 k → J-LIM feed → switch → J-LIM return → node → 10 k → GND`.
  A closed switch (in range) pulls its node **high**, about 3.0 V. An open
  switch — or a broken wire, or an unplugged J-LIM — lets the 10 k take it
  **low**. Low therefore means *"at that end of stroke, or the wiring has
  failed"*, which is the safe direction to fail in.
* `J903` (`B4B-XH-AM`, 4-way JST XH): **1** LIM_A feed · **2** LIM_B feed ·
  **3** LIM_A return · **4** LIM_B return. Feeds first so the two return rows
  leave the connector below every feed wire, with no crossings.
* `U902` `SN74LVC1G11` (triple-input AND, pin map verified against TI SCES487I
  Table 4-1) ANDs the two healthy-limit nodes into `LIMIT_nBRK`. Third input
  tied high. `LIMIT_nBRK` is high only while both switches are closed and both
  harness legs are intact; anything else — including a dead 3V3 rail, which
  takes the gate output low — drives `TIM1_BKIN2` and the PWM outputs go
  inactive with firmware taking no part.
* `LIM_A` / `LIM_B` reach the MCU on their own EXTI pins through 100 Ω, for the
  `REQ-SF-02` firmware kill and for telling the two ends apart.

*Alternative rejected: a single series safety chain.* Wiring the two NC switches
in series is the classic industrial pattern and needs no gate, but it cannot be
stimulated one end at a time — shorting the chain anywhere reads as "the earliest
break". `TEST_PLAN §4` explicitly requires a means to assert **each** limit
without the mechanics, so the independent-loops-plus-gate form was chosen and the
gate is accepted in the path. It is one LVC gate, and its own failure modes
(unpowered, output low) all trip the brake rather than mask it.

### D-PER-12 — The break link and its pull-up

`R915` 0 Ω is the `TEST_PLAN §3.3` link that lets the two TIM1 BREAK sources be
exercised alone. Fitted by default; **must be marked on the silkscreen**.

With R915 lifted the net would float into a break input, so `R916` **1 MΩ** to
`+3V3` holds `LIMIT_nBRK` high — the limit break is disabled and the
`DRV8323_nFAULT` path can be tested on its own (`TEST_PLAN` bring-up step 8).
1 MΩ is weak enough that a tripped chain still pulls the net to about 30 mV
through the 100 Ω + 10 k it sees, so the pull-up costs no noise margin when the
link is fitted. The firmware kill through `LIM_A`/`LIM_B` is unaffected either
way.

### D-PER-13 — On-board test buttons assert each limit

`SW903`/`SW904` pull their node low through the 1 k feed (3.3 mA) — exactly the
state that end of stroke produces. This is the `TEST_PLAN §4` "means to assert
each limit switch without the mechanics", and it works per channel precisely
because the loops are independent (D-PER-11).

### D-PER-14 — Filtering, and no discrete TVS on the limit lines

`C905`/`C906` 10 nF against the ~0.9 k source give about 9 µs of rise filtering
and 100 µs of fall. At the 20 mm/s of `REQ-ME-03` the fall figure is 2 µm of
extra travel before the break asserts, against millimetres of switch overtravel —
free debounce. `R913`/`R914` 100 Ω protect the MCU pins.

No discrete TVS is fitted on the limit lines: the harness stays inside the
instrument, and the RC plus the series resistor already bound the current into
the MCU's own clamps. The SMA is the one externally exposed pin on this sheet and
it does get a clamp (§D-PER-16). `REQ-SC-01` (prototype, no formal EMC) supports
spending protection where it is actually needed.

### D-PER-15 — Buttons, and the external homing trigger

`REQ-CC-06` asks for homing from the API **or an external button**. Both
channels are therefore drawn identically — 10 k pull-up, 100 Ω, 100 nF, on-board
tact switch — and `J901`, a 3-way header, parallels **both** on-board switches so
a panel button can be wired in. The 100 Ω sets the debounce with the cap (~1 ms
rise, 10 µs fall) and limits the contact current; the external button shares it.

Which of `BTN_1` / `BTN_2` is HOME is **OQ-05** and stays open: it is a firmware
and silkscreen matter only, and the two channels are electrically identical, so
nothing here blocks on it.

### D-PER-16 — SYNC/TRIGGER is buffered, then source terminated

`REQ-EL-05` / `REQ-EL-06`: 3.3 V push-pull, 50 Ω source terminated, SMA jack.

`U901` `SN74LVC1G17` (Schmitt buffer, pin map verified against TI SCES351Y)
buffers `SYNC_TRIG` (PE5, TIM15_CH1). Three reasons to buffer rather than drive
the SMA from the pin: the MCU pin never sees the cable; a 50 Ω far-end load would
draw 33 mA, which is past what an H7 pin should source; and the buffer gives a
*repeatable* output impedance, which a GPIO does not.

`R907` **39 Ω** in series. The LVC output impedance is 10–15 Ω typical at 3.3 V,
so the total is about 50 Ω — the value the specification asks for. `TP901` is
pre-termination and `TP902` post-termination, as `TEST_PLAN §4` requires; the SMA
itself is the coaxial access of `TEST_PLAN §2.3`.

`D903` `ESD8351XV2T1G` clamps the SMA centre pin. Chosen for **0.55 pF**, so it
does not soften the trigger edge.

### D-PER-17 — LED choice

`LED_1` = `LED_SMD_0805_GREEN` (SM0805UGC, Vf ≈ 2.0 V) as the heartbeat of
`TEST_PLAN` bring-up step 3; `LED_2` = `LED_SMD_0805_ORANGE` (SM0805UOC) as the
fault/status lamp. Both active-high through 470 Ω, about 2.8 mA.

The `tested`-lifecycle `LED_SMD_0603_GREEN` was rejected: at Vf = 3.0 V it leaves
0.3 V of headroom on a 3V3 rail, so its brightness would track rail tolerance.
`LED_SMD_0805_GREEN` is `draft` lifecycle — flagged in §9 — but electrically it
is the correct part.

---

## 5. Root sheet needs

Hierarchical labels these three sheets expose. The integration pass (DEC-0009)
must add a matching **sheet pin** on the root for each, and wire it. All names
are quoted from the `.ioc`.

| Sheet | Hierarchical label | Shape | `.ioc` pin | Goes to |
|---|---|---|---|---|
| `linear_encoder` | `LINEAR_ENCODER_A` | output | PA0 · TIM5_CH1 | `mcu` |
| `linear_encoder` | `LINEAR_ENCODER_B` | output | PA1 · TIM5_CH2 | `mcu` |
| `linear_encoder` | `LINEAR_ENCODER_Z` | output | PA2 · TIM5_CH3 | `mcu` |
| `nvm_calibration` | `EEPROM_SCL` | bidirectional | PB8 · I2C1_SCL | `mcu` |
| `nvm_calibration` | `EEPROM_SDA` | bidirectional | PB9 · I2C1_SDA | `mcu` |
| `ui_io` | `LED_1` | input | PA12 · GPIO out | `mcu` |
| `ui_io` | `LED_2` | input | PA11 · GPIO out | `mcu` |
| `ui_io` | `BTN_1` | output | PE0 · GPIO in | `mcu` |
| `ui_io` | `BTN_2` | output | PE1 · GPIO in | `mcu` |
| `ui_io` | `SYNC_TRIG` | input | PE5 · TIM15_CH1 | `mcu` |
| `ui_io` | `LIM_A` | output | PD2 · EXTI2 | `mcu` |
| `ui_io` | `LIM_B` | output | PD4 · EXTI4 | `mcu` |
| `ui_io` | `LIMIT_nBRK` | output | PE6 · TIM1_BKIN2 | `mcu` |

13 sheet pins in total. **Shapes are written from the child sheet's point of
view** — `input` means the signal arrives here.

Power crosses on **global power symbols**, so it needs no sheet pins:

| Net | Sheets that consume it | Source |
|---|---|---|
| `+3V3` | all three | `power_rails` |
| `+5V` | `linear_encoder` only | `power_rails` |
| `GND` | all three | `power_rails` |

No net not listed above leaves these three sheets. No interface was invented:
every name matches the stub-note contract, except that `nWP` in the
`nvm_calibration` stub is drawn as active-high `WP` (D-PER-09) and no MCU-side
net exists for it at all.

---

## 6. Residual ERC — and proof they are hierarchy-context only

`kicad-cli sch erc --severity-all` over the whole project, after rebasing onto
`fca9982`:

| Sheet | Class | Count |
|---|---|---|
| `linear_encoder` | `hier_label_mismatch` | 3 |
| `nvm_calibration` | `hier_label_mismatch` | 2 |
| `nvm_calibration` | `power_pin_not_driven` | 2 |
| `ui_io` | `hier_label_mismatch` | 8 |
| `ui_io` | `pin_not_driven` | 3 |

**0 warnings.** Every one is in the three classes `AGENTS.md` records as
expected during the parallel wave:

* `hier_label_mismatch` — one per hierarchical label in §5; cleared when the root
  gets its sheet pins.
* `power_pin_not_driven` — `U801` VCC/VSS. Nothing on any block sheet drives
  `+3V3` or `GND`; `power_rails` (OQ-02) will.
* `pin_not_driven` — `D901`/`D902` anodes and `U901` input. These are fed from
  the MCU through `LED_1`, `LED_2` and `SYNC_TRIG`; a hierarchical label is not
  an ERC driver, the parent's driver is.

**No `PWR_FLAG` was placed.** An earlier revision of these sheets used them and
it was wrong: `PWR_FLAG` is a power *output*, so one per block collides at merge
(`pin_to_pin`: "Pins of type Power output and Power output are connected"). That
was reproduced here on `+3V3` between `linear_encoder` and `nvm_calibration`
before they were removed, and it is the same conclusion `AGENTS.md` now records.

---

## 7. Amodo library — one new part

Announced on the status file for serialisation before the edit, and no
countermanding instruction arrived.

### `FH12-10S-0.5SH(55)` — symbol + footprint

Hirose 10-way 0.5 mm FPC/FFC receptacle, bottom contact, ZIF. **JLC `C506791`**
(verified live), so it is orderable on the same board as everything else.

* **Symbol** appended to `Amodo_Connectors.kicad_sym`, modelled exactly on the
  existing `FH12-20S-0.5SH(55)`: ten contacts in numeric order on one side, no
  pin names, two shell tabs on the other — the `schematic-style` rule that a
  catalogue connector's symbol must stay generic. `SymLifecycle draft`.
* **Footprint** `Amodo.pretty/FH12-10S-0.5SH(55).kicad_mod`, derived from the
  in-house `FH12-20S-0.5SH(55)` land pattern: ten contacts removed and every
  other feature moved 2.5 mm inward per side. `FPLifecycle draft`.

*Why the derivation is safe, and it is cited in the footprint `descr`.* The FH12
series datasheet (Hirose, Digi-Key mirror `FH12_Series.pdf`, read 2026-09-02)
tabulates four dimensions against contact count. Between the 20-way and the
10-way, **all four shrink by exactly 5.0 mm** — contact span `A = 0.5(n−1)`
4.5 mm, body `B = A + 3.6` 8.1 mm, `C = A + 4.6`, `D = A + 1.07`. Every feature
therefore keeps a constant offset from the contact array, which is precisely what
the transform assumes. Two of those dimensions are independently confirmed in the
derived footprint: the contact span measures 4.5 mm and the silk/fab body edges
land at ±4.05 mm = `B`/2.

The `pcb-layout-style` skill was invoked before the footprint was touched, per
`AGENTS.md`. The new part should be reviewed and promoted out of `draft` by the
library owner before fabrication.

**Nothing else in the Amodo library was modified.**

---

## 8. Datasheets added

Committed to `datasheets/`. `datasheets/README.md` was **not** edited — it is a
shared doc and every parallel block task is adding to it; the index entries below
are for whoever consolidates.

| File | Part | Used by | Confirms |
|---|---|---|---|
| `AM26LV32.pdf` | TI AM26LV32 (SLLS202H) | `linear_encoder` | pin map Table 5-1; fail-safe §8.4.1; CM range |
| `24FC16T-I-OT.pdf` | Microchip 24AA16/24LC16B/24FC16 (DS20001703R) | `nvm_calibration` | SOT-23-5 pin map; whole-`1010` addressing |
| `SN74LVC1G11.pdf` | TI SN74LVC1G11 (SCES487I) | `ui_io` | pin map Table 4-1 |
| `SN74LVC1G17.pdf` | TI SN74LVC1G17 (SCES351Y) | `ui_io` | DBV pin map |
| `FH12-10S-0.5SH-55.pdf` | Hirose FH12 series | `linear_encoder` | the A/B/C/D dimension table behind §7 |

This closes three of the `datasheets/README.md` "to be selected" rows: **I2C
EEPROM**, **RS-422 receiver**, and the **SMA jack** (`SMA-J-P-H-ST-TH1`, already
in the house library).

---

## 9. Points a reviewer should look at

1. **FFC cable handedness** (D-PER-01) — the one thing that cannot be settled
   from the IKP11 datasheet. Check before ordering cable.
2. **`Amodo_Digital_ICs:AM26LS32Ax` is misnamed.** The symbol is the AM26LV32
   and its pin map is correct, but the symbol *name* says AM26LS32, its
   `SymLifecycle` is `draft`, and its `Footprint` property is **empty**. The
   footprint is set on the schematic instances here (`Amodo:SOIC-16-N`) rather
   than editing a second Amodo category file during a parallel wave. The library
   owner should fix the symbol.
3. **`LED_SMD_0805_GREEN` is `draft` lifecycle** (D-PER-17). Electrically right,
   but unpromoted.
4. **`R915` must be marked on the silkscreen** as a safety link, default fitted
   (`TEST_PLAN §3.3`). This is a layout-wave action.
5. **OQ-05 stays open** — which button is HOME. Not blocking (D-PER-15).
6. **Series shunt links in the PoC** — `R801`/`R802`, `SB801`–`SB803`,
   `SB601`–`SB603`, `R601`, `R915` are all deliberate bring-up conveniences on a
   development-board revision (`REQ-AR-17`). A miniaturised revision should
   replace them with solid copper.

### Verification run

* ERC `--severity-all`: §6 — 0 warnings, residuals only in the three expected
  classes.
* Exported netlist checked pin-by-pin for every block: the differential pairs,
  the fail-safe/termination nodes, the EEPROM bus split across its isolation
  bridges, the limit-switch loops, the AND gate inputs and the break net all have
  exactly the intended membership.
* Bundled `schematic-style` overlap checker over
  `hardware/kicad/faff2_cbs1/`: **clean on all eleven sheets except one known
  false positive**, `body-vs-wire` on `U601` in `linear_encoder`. The checker
  merges the graphic primitives of *every* unit of a multi-unit symbol into each
  instance's body box, so unit 1's body (symbol x 0 → 7.62) is projected onto
  unit 2's position and appears to swallow unit 2's output wire. Unit 2's own
  primitives stop at symbol x 3.81 → 161.29 mm, and the wire begins at the pin
  connection point, 163.83 mm. No overlap exists.
* Page extents checked: all content inside the A3 frame and clear of the title
  block.
