# `motor_drive` — design record

Block task: **MOTOR DRIVE**, covering exactly one sheet —
`hardware/kicad/faff2_cbs1/motor_drive.kicad_sch`. Outside that sheet this task
added only this file, two datasheets (§8), one project-local symbol library (§9),
its `sym-lib-table` entry, and two sharp edges in `AGENTS.md` (§7.2).

Everything here is subordinate to the authorities named in `AGENTS.md`. The
`.ioc` is quoted, never changed: **no pin on this board was re-assigned.**

77 components, 100 nets, 25 hierarchical labels.

---

## 1. What was drawn

| Block on the sheet | Contents |
|---|---|
| 24 V motor bus | isolation link, current-measurement break, 210 µF bulk store, DC-link sense divider |
| Power-stage temperature | 10 k NTC + pull-up into `MOTOR_FETTEMP` |
| Rotary encoder + halls | two 6-way headers, link-selected supply, pull-ups |
| Gate driver | DRV8323S, charge pump, DVDD/VREF decoupling, SPI2 stub links, break path |
| 3-phase power stage | 6 FETs, 3 shunts, phase connector, gate and switch-node test points |

Designators run from **1101** (`motor_drive` is page 11 of the root sheet).

---

## 2. Decisions

### D-MOT-01 — the gate driver is a DRV8323**S** in WQFN-40 (RTA), not the RS

`U1101 = DRV8323SRTAR`. The `.ioc` fixes the interface: `DRV8323_nCS` on SPI2
means an S variant, and `REQ-AR-02` / the block diagram fix the family.

*Why not the DRV8323RS.* The RS adds an LMR16006 600 mA buck and comes in a
48-pin RGZ package for which the house library already has a footprint — which
was the only argument for it. It was rejected: the buck would be unused (this
board's rails are `power_rails`' job, OQ-02), and an idle 700 kHz switcher sitting
on a board whose headline requirement is 2.4 µV pk-pk load-cell noise
(`REQ-FF-04`) is a noise liability, not a convenience. The S variant is also
MSL-1 against the RS's MSL-2/1-year.

*Consequence — one footprint is owed.* No 40-pin 6×6 mm 0.5 mm-pitch QFN exists
in the house footprint library, so the symbol ships with an **empty Footprint
field** and a
`ki_fp_filters` of `*WQFN*40*6x6mm*P0.5mm*`. It is deliberately empty rather than
pointing at a footprint that does not exist. Drawing it is PCB-wave work
(`pcb-layout-style`), and it needs a land pattern this task could not obtain:
**TI's current SLVSDJ3D PDF omits the RTA0040 package drawing — pages 88 and 96
are blank.** Take the land pattern from TI package drawing 4225197 or the product
folder's mechanical data, not from the RHA0040 drawing that the PDF does carry;
RHA is a different 6×6 40-pin body. The exposed pad is pin **41** in the symbol.

### D-MOT-02 — the per-variant peak current limit: three layers, no board variant (closes OQ-08)

This is `REQ-SF-03`: *"Peak motor current sense limit. Prevents linear actuator
overloading 150 % load cell absolute maximum. Must be configurable per variant."*

**Reading of the requirement.** Taken as: the actuator must not be able to apply
more than **150 % of the load cell's nominal rated force** — 75 N on V50N, 15 N on
V10N. That is exactly the HBK S2M *limit force* (Fl = 150 % Fnom), which makes the
sentence self-consistent. The alternative reading (150 % of the cell's own
absolute maximum, i.e. 225 % of nominal) would allow the actuator to destroy the
cell and is rejected. **Flagged for the captain** — if the intent was different,
only the SPI register values below change, not the circuit.

**Mechanics → amps.** From `CALC` (BLDC sheet): lead 5 mm/rev, efficiency 0.90,
Kt 0.036 N·m/A, so T = F·lead / (2π·η) and I = T / Kt, giving **0.02458 A/N**.

| Variant | Nominal | Phase I | Trip force | Phase I at trip | V across 0R15 |
|---|---|---|---|---|---|
| V50N | 50 N | 1.229 A | 75 N | **1.843 A** | 276 mV |
| V10N | 10 N | 0.246 A | 15 N | **0.369 A** | 55 mV |

**Layer 1 — measurement, and the primary per-variant limit.** One shunt value,
`R1301/R1302/R1303 = 0R15` (Vishay WSR5, 5 W, 4527), for both variants. The
DRV8323 CSA gain is an SPI register (`CSA_GAIN`, 5/10/20/40 V/V), VREF = +3V3, so
the output biases at 1.65 V with a linear range of 0.25 V … VREF−0.25 V — ±1.4 V
usable either side of the bias.

| Variant | CSA gain | Scale | Full scale | Trip point sits at |
|---|---|---|---|---|
| V50N | 5 V/V | 0.75 V/A | ±1.867 A = **±75.9 N** | 98.8 % of full scale |
| V10N | 20 V/V | 3.00 V/A | ±0.467 A = **±19.0 N** | 79 % of full scale |

The 4:1 gain step covers the 5:1 variant ratio with the safety limit inside range
on both, and on V50N the ADC saturates almost exactly at the limit — full scale
*is* the safety limit, which is the cleanest possible pairing. Firmware compares
the measured current against the per-variant threshold every control cycle.

**Layer 2 — hardware backstop, also SPI-configurable.** The DRV8323's VSENSE
overcurrent comparator watches SPx directly against `SEN_LVL` = 0.25/0.5/0.75/1.0 V
(SLVSDJ3D §7.5). At 0R15:

| `SEN_LVL` | Trip current | Trip force |
|---|---|---|
| `00b` (0.25 V) | 1.667 A | **67.8 N** |
| `01b` (0.50 V) | 3.333 A | 135.6 N |

`00b` is the operational setting for V50N: 67.8 N is *below* the 75 N cell limit,
so the hardware trip fires first. For V10N, 67.8 N is far above 15 N, so on that
build layer 2 protects the FETs and the motor, not the cell — the cell is
protected by layer 1 plus the directly measured force from `loadcell_afe`.

*Option recorded on the sheet.* A V10N build that wants a hardware trip at the
cell limit fits **0R68 instead of 0R15** in the same 4527 land: 0.25 V / 0.68 Ω =
0.368 A = 15.0 N, exact. One BOM line, no layout change. Not the default, because
0R68 would dissipate 1.0 W per shunt on a V50N build and cost 19 % of the 7 W
typical budget.

**Layer 3 — MOSFET protection.** `VDS_LVL` overcurrent across the FET RDS(on):
short-circuit protection, not force protection.

**All three layers end in the same place.** `nFAULT` is open drain and drives
`TIM1_BKIN` on PE15, forcing the PWM outputs inactive **in hardware**, with no
firmware in the path (`REQ-SF-06`, DEC-0012).

*Answer to OQ-08:* **no build variant is needed in `motor_drive`.** The shunt,
the footprint and the BOM are identical; the variant is two SPI register values
and a firmware threshold. This keeps `motor_drive` consistent with DEC-0010,
which reached the same conclusion for the load-cell AFE.

### D-MOT-03 — power FETs: BSZ099N06LS5, 60 V / 9.9 mΩ

`Q1101`–`Q1106`, Infineon OptiMOS-5, PG-TSDSON-8, `SymLifecycle = reviewed` in
`Amodo_Power_Transistors.kicad_sym`. 2.5× voltage margin on the 24 V bus, which
matters because the switch node rings on an inductive load; the current rating is
enormously over-specified, which is free here and keeps conduction loss and
junction temperature negligible (34 mW per FET at the 1.843 A trip current).

The high RDS(on) margin does mean VDS at working current is ~18 mV, far below the
60 mV minimum `VDS_LVL`, so layer 3 above is a genuine short-circuit trip only —
that is the intended role.

### D-MOT-04 — no series gate resistors and no gate-source pull-downs

TI's Smart Gate Drive sets slew rate through the `IDRIVE`/`TDRIVE` SPI registers
(10 mA–1 A source, 20 mA–2 A sink), which is the manufacturer's mechanism;
external gate components degrade the VDS and gate-drive-fault monitors that
depend on watching the gate move. Nothing is fitted, and no DNP part is drawn,
because nothing is intended.

Gate-source pull-downs were considered and rejected: SLVSDJ3D §8.4.1.1 states
that in sleep mode **and** under VM undervoltage the device pulls GHx to SHx and
GLx to PGND with internal resistors, so the bridge is held off in exactly the
cases an external pull-down would cover.

### D-MOT-05 — ENABLE is the master off; INHx/INLx get no external pull-downs

SLVSDJ3D §7.5 specifies an internal 100 kΩ pull-down (`RPD`) on CAL, ENABLE,
INHx, INLx, nSCS, SCLK and SDI. Six external PWM pull-downs would therefore be
redundant.

`R1208 = 10 k` to GND on ENABLE is fitted anyway, because ENABLE is the
single point that disables the whole bridge and 100 kΩ is weak for a
safety-relevant pull-down on a motor board. With PD10 high-impedance out of MCU
reset, the bridge is off. `CAL` relies on its internal pull-down.

`nSCS` is the exception that needs an external part in the other direction:
its internal resistor pulls it **low**, i.e. selected. `R1202 = 10 k` to +3V3
holds the device deselected; against the internal 100 kΩ that is 3.0 V, a solid
logic high.

### D-MOT-06 — VREF comes from +3V3, so phase current is ratiometric

The CSA output goes to the STM32's own ADC. Tying VREF to the same +3V3 the ADC
references makes gain and bias track the reference, so a rail shift cancels
instead of appearing as a current error. VREF draws 2–3 mA, decoupled at the pin
by `C1205`/`C1206` (100 nF ∥ 1 µF). A series filter resistor was rejected: at
3 mA it would introduce a gain error precisely by breaking that ratiometry.

### D-MOT-07 — SPI2 stub links on SCK and MOSI only, none on MISO

`TEST_PLAN.md` §3.3 asks for a way to remove one peripheral from a shared bus.
`R1203`/`R1204` (0R, fitted) are that: lift both and U1101 is off SPI2, and its
chip select is already private.

MISO gets no link. The DRV8323's SDO is **open drain and Hi-Z whenever nSCS is
high** (SLVSDJ3D Table 6-3), so it cannot load or corrupt the line that
`temp_sense`'s ADS1120 shares — there is nothing to isolate. `R1205 = 10 k` to
+3V3 is the pull-up that open-drain output requires. Reported here because SPI2
is a cross-block concern (`ARCHITECTURE.md` §5): **`motor_drive` adds a 10 kΩ
pull-up and two 0R stub resistors to SPI2 and nothing else.**

### D-MOT-08 — the TIM1 BREAK path, and the link that must default fitted

`R1206` (0R) sits in the `DRV8323_nFAULT` net between the driver and PE15, so the
`LIMIT_nBRK` trip source can be exercised alone at bring-up step 8. It is marked
on the sheet as safety-critical and **default fitted**. `R1207` (10 k to +3V3) is
deliberately on the **MCU side** of that link, so opening the link leaves PE15
pulled high — no break, defined state — rather than floating. `TP1114` is a hook
on the same segment for forcing the trip by hand.

Polarity and drive type are unchanged from `ARCHITECTURE.md` §5: active low, open
drain. Neither is this block's to change alone.

### D-MOT-09 — bulk store 210 µF, all 63 V or better

`C1101`/`C1102` 100 µF electrolytic + `C1103` 10 µF + `C1104` 100 nF ceramic.
Worst-case DC-link ripple ΔV = I·D·(1−D)/(fsw·C) = 1.843 × 0.25 / (20 kHz ×
210 µF) = **0.11 V**, 0.5 % of the bus. SLVSDJ3D §11.1 asks for ≥ 10 µF local to
VM plus separate bulk on the FET current path; `C1201`/`C1202` (100 nF + 10 µF)
are the VM-local pair. 63 V/100 V parts on a 24 V bus give 2.6× margin for
inductive kickback, not the 1.5× a 35 V part would.

### D-MOT-10 — DC-link sense: 100 k / 12 k, full scale 30.8 V

24.0 V reads 2.571 V, i.e. 78 % of a 3.3 V scale, leaving headroom for a supply
that runs high or a regenerative kick. Draw is 214 µA. `C1105` (10 nF) at the tap
is the ADC's sampling-charge reservoir — the divider's 10.7 kΩ source impedance is
too high to charge the sampling capacitor directly. `VBUS_MON` → PC5 / ADC2_INP8,
per DEC-0011 (provisional, OQ-01).

### D-MOT-11 — rotary encoder and halls: two 6-way headers, supply link-selected

Two `Header_Male_6-way_1-row` connectors rather than one combined header, because
that is what suits **all three** candidate motors (DEC-0004): the Nanotec
DB42M03 + NME2-UVW is one combined cable, while the StepperOnline and SkysMotor
kits bring halls out of the motor and A/B/Z out of a separate encoder. Splitting
the connector costs nothing and covers both. Both are wired
`1 VENC, 2/3/4 signals, 5/6 GND`, single-row, pins in numeric order.

*Supply.* `R1106` (0R, fitted) selects +3V3 — the `CALC` power budget's
"BLDC rotary encoder 3.3 V / 0.1 A" — and `R1107` (0R, **DNP**) is the 5 V
alternative for a 5 V read head. Fit one only; marked on the sheet.

*Pull-ups go to +3V3, never to VENC.* 2k2 on A/B/Z (fast enough for ~270 kHz down
a motor cable), 10 k on the halls. This is deliberate: with a 5 V open-collector
encoder the MCU still sees a 3.3 V high, so the 5 V option cannot present 5 V to
the pins at all. The `.ioc` pins are 5 V-tolerant FT anyway, which covers a
push-pull 5 V driver.

*No series resistors and no TVS array on this interface.* It is an internal cable
inside the actuator, not an external port; `datasheets/README.md` lists ESD
devices for the external interfaces, which these are not.

### D-MOT-12 — TestPointDual on the switch nodes, no U.FL

DEC-0018 ruling 4 prefers a coaxial connector for nets that will be scoped
repeatedly, and `TEST_PLAN.md` §4 names "U.FL candidate on one phase node and the
DC link". Not fitted, deliberately: a U.FL is a 50 Ω jack, and a DC-coupled 24 V
switching node into a scope input left on 50 Ω is 11 W into the input stage. A
50 Ω-terminated measurement of a switch node is also meaningless. `TP1119`–`TP1121`
(`TestPointDual`, signal hole plus spring-ground hole) give the small measurement
loop the design standard actually wants there, and `TP1102` does the same on the
DC link.

### D-MOT-13 — one GND net, with the star point specified on the sheet

AGND, PGND and the thermal pad all land on `GND`. The DRV8323 requires AGND and
PGND joined externally in any case (SLVSDJ3D Table 6-3). A 0R link between a
"PGND" and "GND" would have to carry the full motor return current, and its
inductance in the power return is worse than the split is worth. Instead the
sheet carries the layout instruction: **shunt → PGND → bulk-capacitor negative is
one tight loop, joined to system ground at a single point at the bulk
capacitors.** That is a PCB-wave constraint recorded where layout will read it.

### D-MOT-14 — 24 V feed: isolation link, current break, and a local bus net

`+24V_SW` → `R1101` (isolation link) → `R1102` (current-measurement break) →
`V24_MOT`, the sheet-local motor bus. Both 0R 1206 10 A, both fitted;
`TEST_PLAN.md` §3.1 wants all three of test point, isolation link and current
break, and `TP1101` is the test point. Opening `R1101` leaves the entire logic
side alive with the actuator dead, which is the state bring-up steps 1–8 run in.

`V24_MOT` → `R1201` (0R) → `VM_DRV` gives the separate gate-driver supply
isolation that `TEST_PLAN.md` §4 asks for. `VDRAIN` is **not** taken from VM: it
goes to the high-side FET drains on `V24_MOT`, so the VDS monitor sees the real
bridge rail even with `R1201` out (SLVSDJ3D §11.1).

---

## 3. Deviations recorded

1. **Unequal stubs on some shunt components.** `schematic-style` asks for equal
   wire stubs either side of a vertical two-terminal part. Where a pull-up or
   pull-down hangs off a dense pin fan-out (the SPI/control group and the CSA
   outputs), the part body is placed in a clear band above or below the wire
   bundle instead, giving one long stub and one short one. The alternative — an
   equal-stub placement — puts the component body across other wires, which is
   the more serious defect the same skill forbids. Bodies are aligned in rows so
   the group still reads tidily.
2. **Wire crossings.** A 26-pin fan-out cannot be drawn crossing-free. Crossings
   were minimised by ordering the drop points; the sheet has 11, none of them a
   junction, all wire-over-wire.

---

## 4. Residual ERC violations

`kicad-cli sch erc --severity-all` over the whole project, with the `mcu` and
`test_debug` blocks landed. `motor_drive`'s share:

| Class | Count | Why, and what clears it |
|---|---|---|
| `hier_label_mismatch` | 25 | One per hierarchical label — no sheet pin exists on the parent yet (DEC-0009). Clears at the root-wiring integration pass. |
| `label_dangling` | 25 | The same 25 labels: KiCad 9 errors on a labelled single-pin net. Same fix. |
| `pin_not_driven` | 7 | `INHA`–`INLC` and `CAL` on U1101 are inputs whose drivers (TIM1 and PD5) live on the `mcu` sheet. Clears with the same root wiring. |


**Nothing else.** No `pin_not_connected`, no `wire_dangling`, no
`unconnected_wire_endpoint`, no `multiple_net_names`, no `power_pin_not_driven`,
no `lib_symbol_issues`, no `endpoint_off_grid`, no warnings, and nothing
suppressed — `faff2_cbs1.kicad_pro` still carries no ERC severity overrides.
The bundled `schematic-style` overlap checker also reports this sheet **clean**.

The one **PWR_FLAG** on the sheet (`#FLG1101`, on `VM_DRV`) is deliberate and
permanent. `AGENTS.md` forbids flags on *shared* rails because one per block
becomes a power-output conflict at merge; `VM_DRV` is generated on this sheet
behind `R1201`, so no other block can ever drive it and no other block will ever
flag it. Without it this sheet could not reach the DEC-0021 end state.

---

## 5. Root sheet needs

Every hierarchical label this sheet exposes. Direction is given from
**`motor_drive`**'s point of view. All names match
`docs/decisions/actuator-sch-mcu.md` §4.1 exactly.

| Net | Dir | MCU pin | Function |
|---|---|---|---|
| `MOTOR_PWM_AH` / `AL` | in | PE9 / PE8 | TIM1_CH1 / CH1N |
| `MOTOR_PWM_BH` / `BL` | in | PE11 / PE10 | TIM1_CH2 / CH2N |
| `MOTOR_PWM_CH` / `CL` | in | PE13 / PE12 | TIM1_CH3 / CH3N |
| `DRV8323_nFAULT` | **out** | PE15 | TIM1_BKIN — hardware trip |
| `DRV8323_EN` | in | PD10 | gate-driver enable |
| `DRV8323_CAL` | in | PD5 | CSA offset calibration |
| `DRV8323_nCS` | in | PD7 | SPI2 chip select |
| `CONFIG_SPI_SCK` | in | PA9 | SPI2, shared with `temp_sense` |
| `CONFIG_SPI_MOSI` | in | PB15 | SPI2, shared with `temp_sense` |
| `CONFIG_SPI_MISO` | **out** | PB14 | SPI2, shared with `temp_sense` |
| `MOTOR_I_A` / `_B` / `_C` | **out** | PA6 / PC4 / PA7 | ADC1_INP3 / ADC2_INP4 / ADC1_INP7 |
| `MOTOR_FETTEMP` | **out** | PA4 | ADC1_INP18 |
| `VBUS_MON` | **out** | PC5 | ADC2_INP8 (DEC-0011, OQ-01) |
| `MOTOR_ENCODER_A` / `_B` / `_I` | in | PC6 / PC7 / PC8 | TIM3 CH1 / CH2 / CH3 |
| `HALL1` / `HALL2` / `HALL3` | in | PE14 / PD14 / PD15 | GPIO in |

| `+24V_SW` | in | — | motor bus from `power_entry_24v` (**hierarchical label**, see below) |

`+24V_SW` is consumed as a **hierarchical label**, not as a global power symbol,
because `power_entry_24v` exports it as a sheet pin
(`docs/decisions/actuator-sch-power.md`). Getting this wrong is silent: a global
`+24V_SW` power symbol here would have made a *separate* net that never touches
the power block's, and the only symptom was one `power_pin_not_driven`.

Power nets consumed as global Amodo power symbols, which need no sheet pin:
**`+3V3`**, **`+5V`** (the DNP encoder-supply option only) and **`GND`**.
Sheet-local nets the root must *not* try to wire: `V24_MOT`, `VM_DRV`, `VENC`,
`MOTOR_U` / `_V` / `_W`.

---

## 6. Connectors this block owns

| Ref | Part | Pinout |
|---|---|---|
| `J1101` | Molex Micro-Fit 3.0, 1×3 | 1 `MOTOR_U`, 2 `MOTOR_V`, 3 `MOTOR_W` |
| `J1102` | 1×6 header, 2.54 mm | 1 `VENC`, 2 A, 3 B, 4 Z, 5 GND, 6 GND |
| `J1103` | 1×6 header, 2.54 mm | 1 `VENC`, 2 HALL1, 3 HALL2, 4 HALL3, 5 GND, 6 GND |

Unplugging `J1101` is the means `TEST_PLAN.md` §4 asks for to spin the motor with
the load cell out of the force path.

---

## 7. Notes carried forward

### 7.1 For the PCB wave

* The DRV8323S WQFN-40 (RTA) footprint is owed — see D-MOT-01 for the land-pattern
  source and the pin-41 thermal pad.
* The power-return star point is specified on the sheet (D-MOT-13).
* Gate loops (GHx→gate→SHx, GLx→gate→PGND) must be short and via-free; the
  low-side path especially (SLVSDJ3D §11.1).
* `SPx`/`SNx` must be Kelvin connections to the shunt — `SPx` is the VDS monitor
  return as well as the CSA input, so series impedance there shifts the trip
  threshold.

### 7.2 Two KiCad traps found the hard way, added to `AGENTS.md`

* **Symbol instance paths must start at the root sheet UUID** —
  `/<root-uuid>/<sheet-uuid>`, not `/<sheet-uuid>`. With the short form KiCad
  still shows the right references, but the pins drop out of hierarchical
  connectivity and ERC invents `wire_dangling` / `label_dangling` /
  `pin_not_driven` errors on wiring that is perfectly correct. This cost most of
  a debugging session.
* **`kicad-cli sch erc` prints "Found 0 violations" when the schematic fails to
  load.** A clean run is only meaningful alongside "Failed to load schematic" on
  stderr being absent, or a netlist export showing the expected component count.

---

## 8. Datasheets added

| File | Part | Note |
|---|---|---|
| `datasheets/DRV8323SRTAR.pdf` | TI DRV832x | SLVSDJ3D, rev D, March 2022. **RTA0040 package drawing missing** — see D-MOT-01 |
| `datasheets/BSZ099N06LS5ATMA1.pdf` | Infineon OptiMOS-5 | 60 V, 9.9 mΩ |

## 9. Library part added

`DRV8323S` lives in **`hardware/kicad/faff2_cbs1/faff2_motor.kicad_sym`**, a
project-local library, with a `sym-lib-table` entry bound through `${KIPRJMOD}`.
`SymLifecycle = draft`, `mpn = DRV8323SRTAR`. Pin numbers, names and electrical
types are transcribed from SLVSDJ3D Table 6-3, DRV8323S column — the only 40-pin
SPI variant.

The **Amodo house library is read-only** and is left byte-identical: the symbol
was first added there and then migrated out, and
`/mnt/c/Amodo/AmodoKiCadLib/Amodo_Motor_ICs.kicad_sym` was reverted with a
targeted `git checkout --` on that one file. No footprint was added anywhere, so
this block needs no `fp-lib-table` entry — see D-MOT-01 for the footprint that is
owed to the PCB wave.
