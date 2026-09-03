# Power schematic design record — `power_entry_24v` and `power_rails`

Design reasoning for the two power block sheets of `ARIA_SRB_FAFF_2_POC_CBs_1`.
Written by the `actuator-sch-power` block task, 2026-09-03.

Scope: `hardware/kicad/faff2_cbs1/power_entry_24v.kicad_sch` and
`hardware/kicad/faff2_cbs1/power_rails.kicad_sch`. Nothing else in the repo was
edited except the datasheets added below and this file.

**This file also answers `OQ-02` (rail set and topology) and `OQ-07` (rail
PGOOD / enable lines).** The captain should fold the numbered decisions below
into `docs/DECISIONS.md`; that file is shared and was deliberately left
untouched during the parallel block wave.

---

## 1. What was built

```
KPJX-4S ─ F201 ─ L201 ─ Q201 ─┬─ D201 TVS + C204..C206 ── V24_PROT
 24 V     2 A T   CM     rev-  │                            (protected bus)
                  choke  pol   │
                               ├─ R203 (0R link) ─▶ +24V_SW    → motor_drive
                               ├─ R204 (0R link) ─▶ V24_LOGIC  → power_rails
                               └─ R205/R206 divider ─▶ V24_MON → mcu PC1

V24_LOGIC ─┬─ U301 LMR33630 buck ─▶ +5V5 ─┬─ U302 TPS7A20 ─▶ +5V   (5.0 V)
           │   400 kHz, 5.525 V           └─ U303 TPS7A20 ─▶ +5VA  (5.0 V)
           └─ U304 LMR33630 buck ─▶ +3V3 ──── FB301 ferrite ─▶ +3V3A
               400 kHz, 3.326 V
```

Every rail leaves through one 0R link that is both its isolation link and its
current-measurement break, with a test point downstream. `RAIL_PGOOD` is the
wired-AND of both converters' open-drain PG flags.

## 2. Decisions

### DEC-P1 — Rail set: `+5V5` pre-regulator, `+5V`, `+5VA`, `+3V3`, `+3V3A` (answers OQ-02)

Two buck converters from the protected 24 V, and the 5 V rails post-regulated
by LDOs from a 5.5 V pre-regulator.

*Reasoning.* The load cell path is the accuracy-critical circuit on the board
(`REQ-FF-04`, 2.4 µV pk-pk input-referred noise at the ADC), and the IKP11 read
head is a switching digital load of the same order of current on the same
nominal voltage. Putting both on one 5 V rail lets read-head current modulate
the ADC analog supply. Separating them needs two 5 V regulators, and an LDO
needs headroom above 5 V, so a single pre-regulator at 5.5 V feeding two LDOs
costs one extra converter and post-regulates *both* 5 V rails — the digital one
gets ripple rejection for free.

5.5 V specifically: TPS7A20 recommended input maximum is 6.0 V (6.5 V absolute),
and its dropout is 140 mV max at the full 300 mA, so 5.5 V ± 3 % sits inside the
recommended range with about half a volt of dropout headroom.

*Alternative rejected.* One 5 V buck feeding everything, with a ferrite to the
analog side. A ferrite does not reject the read head's low-frequency current
steps, only its HF content, and this is a "big first revision" board where the
noise floor is the measurement that decides the design (`TEST_PLAN` step 6).

*Alternative rejected.* An ultra-low-noise LDO (LT3045, 0.8 µV<sub>RMS</sub>)
directly from 24 V for `+5VA`. Its input maximum is 20 V, so it cannot run from
24 V at all; and 19 V across it would put ~0.6 W of dissipation next to the most
temperature-sensitive circuit on the board.

### DEC-P2 — Both bucks are LMR33630 at 400 kHz

> **Partly superseded, review round 1 batch 2.** `U301`, the `+5V5`
> pre-regulator, is now an **LMR51610XFDBVR** - the buck
> `ARIA_EITSYS_CBs_1` uses - with the divider, inductor and PGOOD
> consequences re-derived. `U304` stays LMR33630 because this rail's 1.1 A
> exceeds the LMR51610's 1 A rating. See
> [`actuator-sch-review-r1.md`](actuator-sch-review-r1.md).

`LMR33630ADDAR`, 3.8–36 V in, 3 A, HSOIC-8 with PowerPAD. One part number and
one identical layout block for both rails.

*Reasoning.* 400 kHz is forced by the 3.3 V rail: 3.3/24 at 1.4 MHz is a ~98 ns
on-time, too close to the device minimum. Running both converters at the same
frequency also avoids beat products between them. The 3 A part is oversized for
both rails (1.1 A and 0.25 A); that is deliberate on a dev board — it is the
same footprint either way and it removes current headroom from the list of
things bring-up has to think about.

Values follow the TI datasheet procedure (§9.2.2) with K = 0.3 of the *device*
rating, which is what TI specifies when the load is much smaller than the part:

| | `+5V5` (U301) | `+3V3` (U304) |
|---|---|---|
| R<sub>FBT</sub> / R<sub>FBB</sub> | 100 k 0.1 % / 22.1 k 0.1 % | 100 k 0.1 % / 43 k 1 % |
| V<sub>OUT</sub> (V<sub>FB</sub> = 1.000 V) | 5.525 V | 3.326 V |
| L | 15 µH, 5.3 A<sub>rms</sub> | 6.8 µH, 4.5 A<sub>rms</sub> |
| C<sub>IN</sub> | 2 × 10 µF 50 V + 220 nF | same |
| C<sub>OUT</sub> | 2 × 22 µF 16 V + 100 nF | same |
| C<sub>BOOT</sub> / C<sub>VCC</sub> | 100 nF / 1 µF | same |
| C<sub>FF</sub> | none — TI's tables list "open" for every 400 kHz case | none |

Inductor saturation ratings are above the 4.5 A high-side current limit, as TI
asks, so the inductor does not saturate into an output short.

### DEC-P3 — Both 5 V rails are TPS7A20 (`TPS7A2050PDBVR`)

> **Re-examined and upheld, review round 1 batch 2**, against the captain's
> ask to move to `ARIA_EITSYS_CBs_1`'s ADPL42005. Kept on noise: 7 µV<sub>RMS</sub>
> against the ADPL42005's 32 µV<sub>RMS</sub>, on the rail that carries
> `REQ-FF-04`. Raised for the captain to overrule.

Fixed 5.0 V, 300 mA, 7 µV<sub>RMS</sub> with no noise-bypass capacitor needed,
PSRR 95 dB at 1 kHz and ~60 dB at 100 kHz, SOT-23-5.

*Reasoning.* One part number for both 5 V rails. The margin is comfortable:
`+5V` carries the IKP11 (< 65 mA unloaded, plus RS-422 drive into 120 Ω
terminations, ~115 mA worst case) and `+5VA` carries the two ADCs' AVDD plus the
AFE's excitation and reference chain (~30 mA). The `CALC` power budget's 200 mA
figure for the encoder was for the superseded Renishaw ATOM DX; the IKP11
datasheet is the authority now, and it is much lower.

Noise headroom is not marginal, so the exotic option was not needed: the bridge
path is ratiometric, so excitation noise cancels to first order, and 400 kHz
buck ripple reaching `+5VA` is attenuated by the LDO before it meets the
ADS1235's own supply rejection.

*Symbol note.* Pin 4 of the DBV package is "no internal electrical connection"
in the TI datasheet, and the Amodo symbol models it as a hidden no-connect. That
is correct, not a symbol defect — the TPS7A20 does not have an NR/SS pin.

EN has an internal 500 kΩ pull-down and must be driven, so each LDO's EN is tied
to its own input. The 5 V rails therefore follow the pre-regulator with no
sequencing logic.

### DEC-P4 — `+3V3A` is ferrite-isolated from `+3V3`, not separately regulated

`FB301`, 600 Ω at 100 MHz, 800 mA, with 10 µF + 100 nF on the analog side.

*Reasoning.* `+3V3A` supplies only DVDD of the ADS1235 and ADS1120 — the ADCs'
*digital* core, whose supply noise couples into the measurement far more weakly
than AVDD's does. A ferrite plus local bulk keeps the ADCs' own digital switching
current out of the MCU's 3V3, which is the direction that actually matters. The
ferrite doubles as the rail's isolation link and current break: lift it and both
ADCs' digital supplies are cut loose.

### DEC-P5 — Reverse polarity is a P-channel series FET, TVS downstream of it

`Q201` = DMP6023LFG-7 (−60 V, ±20 V V<sub>GS</sub>, 25 mΩ at −10 V / 33 mΩ max
at −4.5 V, 7.7 A). **Drain to the supply, source to the load**, so on a reversed
supply the body diode is reverse-biased and nothing downstream conducts at all.
Gate held by a divider, R201 100 k source→gate and R202 47 k gate→GND.

* V<sub>GS</sub> = −24 × 47/147 = **−7.7 V** — fully enhanced (V<sub>GS(th)</sub>
  −1 to −3 V), and inherently under the ±20 V limit for any input up to 62 V, so
  no Zener clamp is needed.
* C203 100 nF sits gate-to-**source**, not gate-to-ground. At power-on the gate
  therefore starts at the source potential (V<sub>GS</sub> = 0, device off) and
  ramps down with τ = (R201‖R202)·C203 ≈ **3.2 ms**, which limits inrush into the
  bulk capacitance. A gate-to-ground capacitor would instead present the full
  −24 V across V<sub>GS</sub> at the instant the source rises, exceeding the
  ±20 V rating.
* Conduction loss at the 1.05 A peak-power current is ~30 mV / 30 mW.

The TVS (`D201`, 5.0SMDJ26A, 26 V stand-off, 5 kW) sits **after** the FET. A
reversed supply is then simply blocked rather than blowing the fuse through a
forward-biased TVS, and positive transients still reach the clamp because the
FET is on. The 5 kW part rather than a 400 W SMAJ because the LMR33630's
absolute maximum V<sub>IN</sub> is 38 V: the larger die's lower dynamic
resistance keeps the clamp well below that at realistic surge currents.

The bulk electrolytic is downstream of the FET for the same reason — a polarised
capacitor must never see a reversed supply.

### DEC-P6 — 2 A time-lag fuse and a common-mode choke on the input

`F201` = Littelfuse 157 series 2 A T in a replaceable clip. 25 W at 24 V is
1.04 A; a 2 A fuse derated 25 % holds 1.5 A indefinitely, and the time-lag
characteristic rides through the inrush that the FET soft-start still allows.
The replaceable clip is a dev-board choice: a blown fuse should cost a spare
cartridge, not a rework station.

`L201` = PLT10HH1026R0PN# (1000 Ω at 10 MHz, 6 A, 100 V) in **both** lines.
`REQ-SC-01` waives formal EMC testing, but this board hangs a 3-phase inverter
off a 24 V cable, and the design standard's argument for EMC practice is about
intra-system problems, not the test. Board ground is defined on the choke's load
side, so the connector-side return is a separate node (`V0_IN`) by construction.

The connector's four contacts are doubled up (1, 2 = +24 V; 3, 4 = 0 V) to halve
contact resistance; pin 5 is the shell, tied to board ground through `R208`, a
fitted 0R link so the tie can be opened during EMC investigation.

### DEC-P7 — One `GND` net board-wide; AGND / DGND / PGND are layout partitions

The block stub notes name `AGND`, `DGND` and `PGND`. **These are not separate
nets.** Both power sheets use the single Amodo `GND` power symbol throughout,
and so should every other block.

*Reasoning.* The Amodo library has no AGND/DGND/PGND symbols, which is itself
the house answer. Splitting them would need three new library symbols adopted
mid-wave by five workers already drawing, and TI's own guidance for both the
ADS1235 and the ADS1120 is a single ground plane with the partition made by
placement and routing, not by separate nets. The star point stays a layout
instruction, where it belongs, rather than a schematic net-tie that constrains
the plane before the layout exists.

*Consequence for the PCB wave.* The partition is real even though the net is
one: keep the inverter return loop local to its bulk capacitor, and keep the
load cell and ADC return paths out of it.

### DEC-P8 — Designators follow the project range scheme: 2xx and 3xx

`power_entry_24v` uses **2xx** (J201, F201, C201…), `power_rails` uses **3xx**.

*Reasoning.* Reference designators are global across a hierarchical project, and
ten blocks drawn in parallel with `C1`, `R1`, `TP1` in each collide the moment
the netlist is generated — this task caught it locally when its own two sheets
both produced a `C1`, and the `mcu` task hit the same thing and landed the
project-wide answer in `AGENTS.md`: 100 apart, allocated by the block's page
number in the root sheet. These sheets were renumbered onto that scheme rather
than keeping the 1xx/2xx allocation they were first drawn with, so there is one
convention rather than two.

Verified after rebasing onto the `mcu` / `test_debug` landing: 148 components
across the project, no duplicate references.

### DEC-P9 — `RAIL_PGOOD` is a wired-AND, isolated by 1 k per converter (answers OQ-07)

> **Partly superseded, review round 1 batch 2.** The LMR51610 has no PG pin,
> so `RAIL_PGOOD` is now the `+3V3` buck's PG alone, through `R316`; `R315`
> is gone. Still open-drain, still sheet-local.

Both LMR33630 PG pins are open drain. They are joined through `R315` / `R316`
(1 k each) into one `RAIL_PGOOD` node pulled up to `+3V3` by `R313` (100 k), with
a test point and a red LED (`D303`, through `R314` 330 Ω) that lights while
*either* converter reports not-good.

*Reasoning for the 1 k resistors.* The Amodo LMR33630 symbol declares PG as an
`output` rather than `open_collector`, so tying the two pins directly makes ERC
report an output-to-output conflict. The series resistors make the wired-AND
explicit, cost ~33 mV of low-level offset through the 100 k pull-up, and would
also protect the pins if a future part turned out to be push-pull. The
alternative — editing a shared library symbol's pin type mid-wave — was rejected
as disproportionate.

*Answer to OQ-07.* No `.ioc` change is requested. `RAIL_PGOOD` is exported as a
hierarchical label so the integration pass can route it to `test_debug`'s rail
probe header; if the captain later wants MCU visibility of rail state, it needs
one spare GPIO and an `.ioc` revision, and the net is already provisioned for it.
Rail *enables* need no pin at all: the shared EN divider (R301/R302 and
R308/R309, 100 k / 8.2 k) gives a 16.2 V rising UVLO from the 24 V input, which
holds both converters off until the input is real.

### DEC-P10 — Per-rail links, not per-consumer links

`TEST_PLAN.md §3.1` asks for a test point, an isolation link **and** a current
break on every rail; §3.3 additionally asks for a link between `power_rails` and
each consuming block. The sheets deliver §3.1 in full and deliberately do not
deliver §3.3's per-block links.

* **One link serves as both.** A single 0R (1206 for the 24 V branches, 0603 for
  the low-current rails) is opened to isolate and replaced by a meter or shunt to
  measure. A second series part in the same rail would add joints and resistance
  and no capability.
* **Per-consumer links cannot exist without per-consumer net names.** Every block
  takes the same global `+3V3` / `+5V` net, which is what their frozen stub
  contracts say. Giving `mcu` its own `+3V3_MCU` would force a change in five
  other workers' sheets mid-wave, for a link each of them can add themselves: a
  0R between the global rail and a sheet-local supply node stays entirely inside
  the owning block's file and changes no interface. That is the recommendation
  passed to the other block owners.
* The one place per-branch isolation genuinely matters — keeping the motor stage
  unpowered while the rest of the board is exercised — **is** implemented, as two
  independent links in `power_entry_24v` (`R203`, `R204`). That is the link
  `TEST_PLAN` step 8 depends on.

### DEC-P11 — Test point types

> **Superseded in part, review round 1 batch 2.** Every regulator output now
> carries a `TestPointDual` - probe tip and ground clip - and no test point
> sits on a PSU feedback node (`TP301` and `TP305` removed).

`TestPointHook` (THT loop) on every rail, with `TestPointHook`-to-`GND` pairs
distributed for scope grounds; `TestPoint` (SMT pad) on the two feedback nodes
and on `V24_MON`, which are DMM-only nets where a THT loop would add stray
capacitance to a sensitive node.

`TestPointDual` was considered for the rails, per `TEST_PLAN §2.1`'s "signal
integrity matters" category, and not used: its second pin is a ground hole, so
placing it on a rail either shorts the rail to ground or needs a contrived stub.
The hook-plus-adjacent-ground-hook arrangement gives the same short probe loop
with no such trap. `TestPointDual` remains the right choice for the AFE's
low-level analog nets, where it can be placed on a branch rather than a rail.

## 3. Root sheet needs

The root sheet is deliberately unwired (`DEC-0009`). When the integration pass
wires it, these two sheets need the following **sheet pins**, and nothing else.

### `power_entry_24v`

| Sheet pin | Direction | Goes to |
|---|---|---|
| `+24V_SW` | output | `motor_drive` — protected 24 V, downstream of the motor-branch link |
| `V24_LOGIC` | output | `power_rails` — protected 24 V, downstream of the logic-branch link |
| `V24_MON` | output | `mcu` PC1 / ADC1_INP11 — scaled 24 V monitor |

### `power_rails`

| Sheet pin | Direction | Comes from / goes to |
|---|---|---|
| `V24_LOGIC` | input | `power_entry_24v` |
| `RAIL_PGOOD` | output | `test_debug` rail probe header (and a future MCU GPIO, OQ-07) |

### Nets that need **no** sheet pin

`GND`, `+5V`, `+5VA`, `+3V3`, `+3V3A` are Amodo power symbols, i.e. global
labels. They connect across the whole hierarchy without root wiring, which is
why they are not in the tables above. `+5V5` is a sheet-local label inside
`power_rails` and never leaves it.

### Contract changes other block owners must know about

1. **`motor_drive` keeps `+24V_SW`** exactly as its stub note says. What changed
   is on the other side: `power_rails` is fed by a *second, independent* branch
   named **`V24_LOGIC`**, not by `+24V_SW`. Both sheets are owned by this task,
   so no other block's contract moved. Nothing in `motor_drive` needs to change.
2. **`loadcell_afe` should take its excitation and AVDD from `+5VA`, not `+5V`.**
   Its stub note says `+5V` because the analog rail had not been decided yet.
   Both rails exist and are 5.0 V; `+5VA` is the post-regulated analog one and is
   the reason `+5V5` exists at all. `temp_sense` likewise: `+5VA` for AVDD,
   `+3V3A` for DVDD.
3. **`AGND` / `DGND` / `PGND` are one net, `GND`** — DEC-P7.
4. **PWR_FLAG ownership.** ERC needs exactly one power-output source per power
   net, and two flags on one net is itself an ERC error. `power_entry_24v` owns
   the single flag for **`GND`** and for **`+24V_SW`**; `power_rails` owns the
   flags for **`V24_LOGIC`**, **`+5V5`**, **`+5V`**, **`+5VA`**, **`+3V3`** and
   **`+3V3A`** (the column at the bottom right of that sheet). **No other sheet
   may add a PWR_FLAG to any of these nets.**
5. **Designator ranges** — DEC-P8.

## 4. Verification

Run from the repo root:

```sh
AMODO_KICAD_LIB=/mnt/c/Amodo/AmodoKiCadLib \
  kicad-cli sch erc --severity-all --exit-code-violations \
  -o /tmp/erc.rpt hardware/kicad/faff2_cbs1/faff2_cbs1.kicad_sch
```

| Check | Result |
|---|---|
| ERC, `--severity-all`, nothing suppressed | these two sheets contribute **0 warnings and 5 errors**, all `hier_label_mismatch` — see below |
| `schematic-style` overlap checker, whole project | **0 findings** |
| Exported netlist, orientation-sensitive parts | verified by node membership, not by eye — see below |
| Render sweep of both sheets | done in the scratchpad; no review PDFs committed |

### Residual ERC violations, and why they are expected

All five are the same violation: a hierarchical label in a child sheet with no
matching sheet pin in the parent, because the root sheet is deliberately unwired
(`DEC-0009`). They are the *mechanical evidence* that these sheets have declared
their interfaces and are waiting for the integration pass; the pass that adds the
sheet pins in §3 clears all five.

| Sheet | Label | Cleared by |
|---|---|---|
| `power_entry_24v` | `+24V_SW`, `V24_LOGIC`, `V24_MON` | root sheet pins |
| `power_rails` | `V24_LOGIC`, `RAIL_PGOOD` | root sheet pins |

There are **no** violations of any other class from these two sheets: no
`label_dangling`, no `endpoint_off_grid`, no `power_pin_not_driven`, no
`pin_to_pin` conflict, and 0 warnings of any kind.

Landing this block also **clears a class for everyone else**. `AGENTS.md` lists
`power_pin_not_driven` on `+3V3`, `+3V3A`, `+5V` and `GND` as expected during the
wave, "until `power_rails` exists". It exists now: the PWR_FLAGs listed in §3
drive those nets, and after rebasing onto the `mcu` / `test_debug` landing the
whole project reports that class **zero** times. Every remaining project-wide
violation is `hier_label_mismatch` or `label_dangling` from the unwired root.

### Netlist checks on orientation-sensitive parts

Taken from the exported netlist, not from the drawing:

| Part | Expected | Netlist |
|---|---|---|
| `Q201` P-FET | drain on the supply side, source on the load | `Net-(Q201-D)` = `L201.2`, `C201.1`, `C202.1`, `Q201.5/D`; `V24_PROT` contains `Q201.1/S` |
| `D201` TVS | cathode to the bus, anode to ground | `V24_PROT` ∋ `D201.2/A2`; `GND` ∋ `D201.1/A1` |
| `C204` 100 µF alu | `+` to the bus | `V24_PROT` ∋ `C204.1`; `GND` ∋ `C204.2` |
| `D202` green LED | anode via `R207` to the bus | `Net-(D202-Pad1)` = `D202.1`, `R207.2`; `GND` ∋ `D202.2` |
| `D303` red LED | anode to `+3V3` via `R314`, cathode to `RAIL_PGOOD` | `Net-(D303-Pad1)` = `D303.1`, `R314.2`; `RAIL_PGOOD` ∋ `D303.2` |
| `FB301` ferrite | `+3V3` in, `+3V3A` out | `+3V3` ∋ `FB301.1`; `+3V3A` ∋ `FB301.2` |

88 components, no duplicate references.

## 5. Budget check

| Rail | Load assumed | Source |
|---|---|---|
| `+3V3` | 1.1 A — STM32 0.5 A, other ICs 0.5 A, rotary encoder 0.1 A | `CALC` power budget |
| `+5V` | ~115 mA — IKP11 < 65 mA unloaded plus RS-422 drive | IKP11 datasheet rev 3.7 |
| `+5VA` | ~30 mA — ADS1235 and ADS1120 AVDD, bridge excitation | device datasheets, `CALC` |
| `+3V3A` | ~10 mA — ADS1235 and ADS1120 DVDD | device datasheets |

That is ~5.0 W of rail output, ~5.8 W at the 24 V input allowing for converter
loss, against the `CALC` quiescent total of 5.185 W of device power — consistent,
since `CALC` counts device power and not conversion loss. It leaves ~19 W of the
25 W peak (`REQ-EL-03`) for the motor branch, i.e. ~0.8 A at 24 V, comfortably
inside both the 2 A fuse and the 10 A 0R branch links.

## 6. Datasheets

Added to `datasheets/` by this task:

| File | Part | Used for |
|---|---|---|
| `KPJX.pdf` | Kycon KPJX series | the 24 V input connector |
| `LMR33630.pdf` | TI LMR33630 | both bucks; pinout, V<sub>FB</sub>, external component procedure |
| `TPS7A20.pdf` | TI TPS7A20 | both 5 V LDOs; V<sub>IN</sub> range, dropout, PSRR, pin 4 = N/C |
| `DMP6023LFG.pdf` | Diodes DMP6023LFG | the reverse-polarity FET; V<sub>GS</sub> limit, R<sub>DS(ON)</sub> |

`datasheets/README.md` has **not** been updated: every block task is adding
datasheets to the same table this week and it would be a guaranteed conflict.
The integration pass should add these four rows in one edit.

Not obtainable from this environment — littelfuse.com and bourns.com both return
403 to this network, and analog.com and st.com time out:

| Part | Where it is used | Needed for |
|---|---|---|
| Littelfuse 5.0SMDJ26A | `D201` input TVS | clamping voltage vs surge current curve |
| Littelfuse 157 series (`0157002.DRT`) | `F201` input fuse | I²t and derating curves |
| Bourns PLT10HH1026R0PN# | `L201` CM choke | impedance vs frequency, saturation |

None of these blocks the design — the ratings quoted above come from the Amodo
symbol descriptions and are consistent with the parts' published summaries — but
they should be collected before the board is ordered, particularly the TVS
clamping curve, which is what protects the LMR33630's 38 V absolute maximum.

## 7. One item for `AGENTS.md`

`AGENTS.md` is a shared file and this task ran during a parallel block wave, so
this is recorded here rather than edited in from a block task. The two other
candidates this task would have raised — per-block designator ranges, and "a
stub that lands mid-wire does not connect" — were landed by the `mcu` task while
this one was drawing, and these sheets now follow both.

**Sharp edge, KiCad 9 `lib_symbols`.** When a symbol is copied into a schematic's
`lib_symbols` block, only the *outer* symbol takes the `Library:Name` form. The
unit sub-symbols keep their bare `Name_1_1` names. Add the library prefix to a
unit sub-symbol as well and KiCad refuses the whole file with nothing but
`Failed to load schematic` — the same unhelpful message `AGENTS.md` already
documents for a literal newline inside a quoted string. Only matters when
writing `.kicad_sch` files programmatically rather than from the GUI.
