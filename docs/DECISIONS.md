# FAFF 2 CBs_1 - Decision Log

Every judgement call made on the CBs_1 electronics, with its date, reasoning and evidence.
Standing instruction from the captain: **decide routine points and document them here** rather
than escalating. Escalate only where the decision is genuinely above the implementing engineer.

Append new decisions at the end; never renumber. If a decision is reversed, mark the original
**SUPERSEDED BY DEC-xxxx** and leave it in place.

Open questions live in `REQUIREMENTS.md` under [Open Questions](REQUIREMENTS.md#open-questions)
and graduate to a `DEC-` entry when answered.

---

### DEC-0001 - FAFF 1 power architecture is superseded, not inherited
**Date** 2026-09-02 · **Status** Accepted · **Scope** `power_entry_24v`, `power_rails`

FAFF 2 takes a single dedicated 24 V input on a KPJX-4S latching circular connector. The FAFF 1
barrel-jack alternate input, the power-OR stage and the USB-PD controller (CYPD3177-class) are
**all dropped**.

*Reasoning.* `SPEC §6` names 24 V and KPJX-4S outright, and separately states that the USB-C
port "will not power the hardware". With one supply there is nothing to OR. The FAFF 1 block
diagram is explicitly reference-only where it conflicts.

*Consequence.* No CYPD-class part is needed; `datasheets/README.md` records this so nobody
collects one.

### DEC-0002 - USB-C carries data only: no USB-PD, no bus power
**Date** 2026-09-02 · **Status** Accepted · **Scope** `mcu`

The USB-C receptacle implements USB 2.0 high-speed data via the USB3320 ULPI PHY and nothing
else. No PD negotiation, no sink capability, no bus-powered mode.

*Reasoning.* `REQ-EL-10`, verbatim from `SPEC §6`: "This port will not power the hardware."

*Consequence.* CC pins need only the passive resistors that make the port a valid
downstream-facing-device attachment; VBUS is not a supply on this board. The `mcu` task must
still decide how the device detects host presence — see OQ-01 and OQ-03.

### DEC-0003 - Linear encoder is the Bogen IKP11, not the Renishaw ATOM DX
**Date** 2026-09-02 (recording an earlier design-log decision) · **Status** Accepted ·
**Scope** `linear_encoder`

Part: `IKP11-Z1.4-P1-V5-D1-R0.5-F1000-C1`. 1 mm pole pitch, 5 V supply, RS-422 A/B/Z
differential outputs, 0.5 µm resolution, 1 MHz/channel max, 10-way 1.27 mm header.

*Reasoning.* Renishaw quoted a **34-week lead time** on the ATOM DX. Units and 300 mm magnetic
strip (`LMS-I1-L70-W5-A03-K`) were ordered from Bogen for immediate shipment. `ELOG`.

*Consequence.* The `SPEC` assumptions list and the specification design log still name the ATOM
DX — both are stale on this point. Incremental output means homing is required (`REQ-PS-10`),
which is why limit switches exist (`REQ-EL-09`). The electrical interface is an RS-422 receiver
into an STM32 timer in quadrature mode.

### DEC-0004 - The BLDC part number stays open
**Date** 2026-09-02 · **Status** Accepted · **Scope** `motor_drive`

The motor and its rotary encoder are deliberately **not** fixed by this design. Candidates in
`ELOG` include the Nanotec DB42M03 + NME2-UVW-W14-05-C, the StepperOnline 42BLS60-24-01, and
the SkysMotor 42BLS63-24-01 kit.

*Reasoning.* `ELOG` states it directly: "All of the above motor options are compatible with the
same version of the electronics (i.e. I can proceed with electronics design before finalising
specific motor and rotary encoder selection)."

*Consequence.* `motor_drive` must present a generic 3-phase output plus a rotary-encoder /
Hall connector that suits all three: incremental A/B, optional Z index, and three Hall outputs.
Working point for sizing: 0.0442 Nm screw torque, 1.229 A phase current, 240 rpm at 20 mm/s
with a 5 mm/rev lead (`CALC`).

### DEC-0005 - Temperature ADC is the ADS1120
**Date** 2026-09-02 · **Status** Accepted · **Scope** `temp_sense`

`ELOG` asked only for "an external ADC of some kind, probably over SPI". The `.ioc` net
`ADS1120_nCS` and the block diagram box "ADS1120 ADC (temperature measurement)" both name the
part, so it is settled.

*Reasoning.* Two independent authorities agree. The ADS1120 suits `REQ-EL-07` well: 16-bit
delta-sigma, integrated PGA, two matched IDACs for RTD/NTC excitation, internal reference, and
a 4-input mux that covers both probe channels from one device.

### DEC-0006 - QSPI force-profile RAM is fitted, not an option
**Date** 2026-09-02 · **Status** Accepted · **Scope** `mcu`

The external memory for force profiles is a fitted part on OCTOSPI1 port 1 in quad mode.

*Reasoning.* `ELOG` flagged a risk: "Ideally we will have space for some external RAM… This
might need to QSPI as I think ULPI pins collide with OctoSPI." On the STM32H723VET6 in LQFP100
**the collision does not occur**: ULPI occupies PA3/PA5/PB0/PB1/PB5/PB10-13/PC0/PC2_C/PC3_C
while OCTOSPI1 port 1 occupies PB2/PB6/PD11/PD12/PD13/PE2 — disjoint sets. The `.ioc` allocates
both simultaneously and the block diagram shows both. The risk that made it optional is gone.

*Consequence.* Treat it as a normal fitted subsystem. `REQ-AR-12`.

### DEC-0007 - Producer-owns-the-break: test points and isolation links belong to the block that generates the net
**Date** 2026-09-02 · **Status** Accepted · **Scope** all blocks

Test points, isolation links (0R / jumper / solder bridge) and current-measurement breaks are
**distributed into the block sheets**, not gathered onto one test sheet. The owning block is
whichever block *generates* the rail or signal. A separate `test_debug` sheet carries only what
is genuinely system-level: the SWD + USART3 debug header, the consolidated rail probe header,
and any link that sits between two blocks rather than inside one.

*Reasoning.* The brief allows either. Distributing gives every follow-up block worker a single
file to own with no shared-file contention, which is the whole point of the file-per-block
split (DEC-0008). "Producer owns the break" removes the only ambiguity — a link between
`power_rails` and `mcu` would otherwise have two plausible owners.

*Alternative rejected.* One central test-points sheet: it would become a merge-conflict
hotspot, since every one of the ten parallel tasks would need to edit it.

### DEC-0008 - Ten hierarchical blocks, one `.kicad_sch` file each
**Date** 2026-09-02 · **Status** Accepted · **Scope** repo structure

`power_entry_24v`, `power_rails`, `mcu`, `motor_drive`, `loadcell_afe`, `linear_encoder`,
`temp_sense`, `nvm_calibration`, `ui_io`, `test_debug` — each a hierarchical child of the root
sheet, each in its own file.

*Reasoning.* Follow-up tasks fill these blocks in parallel. KiCad rewrites a whole `.kicad_sch`
on every save, so two workers in one file means a guaranteed conflict. One file per block makes
parallel work conflict-free by construction. This also matches the `schematic-style` rule that
hierarchical sheets are standard once more than one block exists.

*Deviation from the brief.* The brief listed nine blocks plus an optional test/connectors
sheet; this is those nine plus `test_debug`, so ten. `test_debug` exists because DEC-0007
leaves a genuine system-level residue (debug header, rail probe header) that no functional
block owns.

### DEC-0009 - The root sheet is a block map, deliberately unwired
**Date** 2026-09-02 · **Status** Accepted, **closed 2026-09-03 by DEC-0022** · **Scope** `faff2_cbs1.kicad_sch`

The root sheet places all ten sheet symbols with a descriptive note, and draws **no** sheet
pins and **no** interconnect wiring.

*Reasoning.* A sheet pin only passes ERC once the child sheet declares a matching hierarchical
label, and those labels are created by the per-block tasks that own each child file. Drawing
sheet pins now would either break ERC or force this task to invent every block's internal
label set — which is exactly the component-level design the brief excludes, and would create
the cross-file coupling DEC-0008 exists to avoid.

*Note.* This decision was made before the block diagram arrived and **re-examined after**. The
diagram (`docs/FAFF-2-Electronics-Full.svg`) settles the interconnect topology, and the child
sheets are now reconciled against it, but it does not change the ERC mechanics above. Root
wiring is the first integration pass **after** the blocks are drawn.

*Deviation from `schematic-style`.* That skill says "top sheet = the block diagram wired with
sheet pins". That is the end state; it is not reachable from an empty skeleton. Recorded here
as a deliberate, temporary deviation to be closed by the integration pass.

*Closed.* The integration pass drew all 113 sheet pins and wired every cross-block net on
2026-09-03. The deviation from `schematic-style` is over: the top sheet is now the block
diagram, wired. See DEC-0022 and `docs/decisions/actuator-sch-integrate.md`.

### DEC-0010 - One AFE design serves both V50N and V10N
**Date** 2026-09-02 · **Status** Accepted · **Scope** `loadcell_afe`

No build variant in the load cell front end. Only the load cell part differs between V50N and
V10N.

*Reasoning.* Both variants use the same HBK S2M family at the same 2 mV/V sensitivity and the
same 5 V excitation (`REQ-FF-09..11`), so the full-scale bridge output is ± 10 mV in both cases
(`CALC`). The ADS1235 at gain 128 has 167 % / 208 % noise headroom against the V50N / V10N
noise specs from a single configuration. The variants differ in *newtons per volt*, which is a
calibration constant, not a circuit change.

*Consequence.* Variant handling lives in the calibration data in `nvm_calibration`. Note that
`REQ-SF-03` (peak current limit "configurable per variant") is a **separate** matter in
`motor_drive` — see OQ-08.

### DEC-0011 - Motor FET temperature belongs to `motor_drive`; `VBUS_MON` provisionally does too
**Date** 2026-09-02 · **Status** Accepted (VBUS_MON provisional) · **Scope** `motor_drive`,
`temp_sense`, `mcu`

`MOTOR_FETTEMP` (PA4, internal ADC) is a `motor_drive` net. `temp_sense` owns **only** the two
precision ADS1120 channels of `REQ-EL-07` (load cell, encoder rail mid-point).
`VBUS_MON` (PC5) is provisionally allocated to `motor_drive` as the inverter DC-link monitor.

*Reasoning.* Two "temperature" things on this board are unrelated: a coarse thermal-protection
reading of the power stage, and a 1 °C-accurate measurement for force/position compensation.
Naming both "temperature sensing" would put one block's parts in another block's sheet.
For `VBUS_MON`: the USB3320 already reports VBUS state to the MCU over ULPI, so a separate MCU
ADC channel for USB VBUS would be redundant, whereas a DC-link monitor is genuinely needed by
the motor control loop and by `REQ-SF-03`. The block diagram supports this — it labels the
motor drive "Phase current, VBUS sense".

*Escalation.* `VBUS_MON` is flagged as **OQ-01** for captain confirmation rather than escalated
as a blocker: the alternative reading changes only which sheet holds one divider, which is
cheap to move.

### DEC-0012 - Limit switches get a hardware brake path in addition to the firmware kill
**Date** 2026-09-02 · **Status** Accepted · **Scope** `ui_io`, `motor_drive`

`LIMIT_nBRK` (PE6) drives `TIM1_BKIN2`, forcing the PWM outputs to their inactive state in
hardware. This is **in addition to** the firmware kill of `REQ-SF-02`, not a replacement.
`DRV8323_nFAULT` (PE15) drives `TIM1_BKIN` on the same principle.

*Reasoning.* `SPEC §9.1` asks only for "firmware to kill motor drive in the case of limit
switch actuation". Both the block diagram ("Limit Switches … BREAK input") and the `.ioc`
(`LIMIT_nBRK` → `TIM1_BKIN2`, `BreakState=TIM_BREAK_ENABLE`) show the stronger hardware path.
A hardware break does not depend on firmware being alive, scheduled, or correct — for a stage
that can drive a probe into a load cell, that is the right side to err on.

*Consequence.* Recorded as `REQ-SF-05` / `REQ-SF-06`. The break nets are cross-block
safety-critical signals: see `ARCHITECTURE.md §5`. Their polarity and drive type must not be
changed by one block alone. Bring-up step 8 of `TEST_PLAN.md` tests this before the motor is
ever energised under load.

### DEC-0013 - MCU pinned to the STM32H723VET6 from the captain's CubeMX file
**Date** 2026-09-02 · **Status** Accepted · **Scope** `mcu`, all blocks

`hardware/cubemx/ARIA_SRB_FAFF_2_POC_CBs_1.ioc` (CubeMX 6.17.0, `Mcu.Name=STM32H723VETx`,
`Mcu.CPN=STM32H723VET6TR`, LQFP100, 77 pins allocated) is committed to the repo and is **the
authority** for every MCU-side pin assignment and net name.

*Reasoning.* Supplied by the captain as the starting point; corroborated by the block diagram
("STM32H723"). Every block interface in `ARCHITECTURE.md §3.2` is quoted from it so that block
workers do not need CubeMX open.

*Caveats for block workers.* (a) The clock tree in the `.ioc` is untouched CubeMX default —
PLL from HSI, SYSCLK 64 MHz — and is **not** a designed clock tree; it will change. (b)
`PH0-OSC_IN` is set to *HSE external clock source* with `PH1-OSC_OUT` unallocated, so HSE must
be a driven clock, not a bare crystal (OQ-03). (c) Some nets the schematic needs have no pin
yet (EEPROM `nWP`, rail PGOOD/enable) — OQ-06, OQ-07. Spare pins exist.

### DEC-0014 - The load cell interface supports both 4-wire and 6-wire
**Date** 2026-09-02 · **Status** Accepted · **Scope** `loadcell_afe`

The load cell connector and AFE accommodate a 4-wire **or** a 6-wire bridge connection.

*Reasoning.* The block diagram states "4 or 6 wire" for the HBK S2M. The specification design
log is emphatic that 6-wire Kelvin sensing is what makes the accuracy budget reachable
("6-wire bridge where we can Kelvin sense to mitigate against V drop in the leads"), and the
S2M is a six-wire part. Supporting both costs two connector positions and two sense inputs;
refusing 4-wire would rule out substitute load cells during PoC bring-up, which is contrary to
the "load cell agnostic" intent of the dev-board build (`SLOG`).

*Consequence.* Provide the sense lines with a documented link option to tie them to the
excitation lines locally for a 4-wire cell. Default build is 6-wire.

### DEC-0015 - The Amodo house library is bound through `${AMODO_KICAD_LIB}`
**Date** 2026-09-02 · **Status** Accepted · **Scope** repo

Project-level `sym-lib-table` (29 `Amodo_*` symbol libraries) and `fp-lib-table` (the `Amodo`
footprint library) live in `hardware/kicad/faff2_cbs1/` and reference the library through the
`${AMODO_KICAD_LIB}` path substitution variable.

*Reasoning.* Captain instruction. The library lives at `C:\Amodo\AmodoKiCadLib` on the
captain's Windows KiCad and `/mnt/c/Amodo/AmodoKiCadLib` from WSL. A path variable is the only
way one committed table opens correctly on both. Project-level tables (rather than each
engineer's global table) mean the project is self-describing.

*Note.* The Amodo footprints already reference 3D models through a **second** variable,
`${AMODO_3D}`, so both must be set. `README.md` documents how each side sets them.

*Rule for the whole project.* Prefer existing Amodo parts. Create a new part **only** where
absolutely necessary, and create it in the Amodo library itself — never scattered in this repo.
During parallel block work, report any new-part addition in a status line so firstmate can
serialise concurrent edits to the same category file. Recorded in `AGENTS.md`.

*Already available, do not recreate:* `ADS1235` exists in `Amodo_ADCs.kicad_sym`. Check the
library before drawing any part.

### DEC-0016 - The skeleton was machine-generated once; the generator is not committed
**Date** 2026-09-02 · **Status** Accepted · **Scope** repo

The eleven `.kicad_sch` files were produced by a one-shot Python generator (deterministic
UUIDs via `uuid5`), which is **deliberately not** committed.

*Reasoning.* Once block workers start editing sheets in KiCad, re-running the generator would
silently destroy their work. A tool whose only safe moment has already passed is a hazard in
the repo, not an asset. From here the schematics are hand-maintained in KiCad.

### DEC-0017 - KiCad 9 only
**Date** 2026-09-02 · **Status** Accepted · **Scope** repo

All schematic and PCB work uses KiCad 9 (`kicad-cli` 9.0.8 here). Files are written at
schematic format version `20250114`. No other KiCad major version may open or save these files.

*Reasoning.* Brief mandate. Practically: opening a KiCad 9 project in KiCad 8 fails, and saving
from a newer version would silently migrate the format for everyone else.

### DEC-0018 - The in-house EEE Hardware Design Standard draft is adopted, with precedence below the spec
**Date** 2026-09-02 · **Status** Accepted · **Scope** all blocks, and the later PCB wave

The captain's draft standard is committed verbatim at `docs/HardwareDesignStandard_DRAFT/` and
applies to CBs_1 design decisions. **Precedence: project specification > this standard >
general practice.**

Rulings taken from it that bind this project:

1. **No test points on very high speed signals.** The standard: "not advisable to place test
   coverage on very high speed interfaces… rise / fall times that are single digit nanosecond".
   On CBs_1 that excludes the **ULPI bus** (60 MHz clock, 12 signals) and the **OCTOSPI/QSPI
   bus**. This overrides the otherwise-blanket "test point on every key signal" instruction of
   the brief for those two buses specifically, and is recorded in `TEST_PLAN.md §2`.
2. **Test point type is chosen per net, from the house library** — `TestPoint` (1.0 mm SMT pad,
   DMM only), `TestPointHook` (THT loop, scope / logic analyser), `TestPointDual` (THT with a
   scope spring-ground hole, for nets where signal integrity matters). Where `TestPointHook` is
   used, place GND hooks nearby for the probe clip.
3. **The "big first revision" is house doctrine**, not just this project's preference — it
   independently confirms `REQ-AR-17`.
4. **Coaxial connectors for nets that will be scoped or injected into repeatedly** (U.FL, with
   the U.FL-to-BNC adapter stocked in the EEE lab). Applied in `TEST_PLAN.md §2`.
5. **Involve firmware from day zero.** Recorded in `TEST_PLAN.md §1` as a process requirement;
   the board carries a `.ioc` from the firmware side already, which is this rule working.
6. **Hardware build/mod state must be tracked** in a Notion database keyed by board serial.
   Recorded as a `TEST_PLAN.md §6` deliverable.
7. **4-layer stackup guidance** — `SIG+PWR : GND : GND : SIG+PWR`, power routed as 0.5 mm
   traces rather than planes, 6 layers if power routing gets awkward. This binds the **later
   PCB wave**, not this schematic skeleton; recorded here so it is not lost.

*Tension noted, not a conflict.* The standard lists "zero ohm links for measuring power
consumption" among good practices but adds "although I never do this". The brief for this task
**mandates** current-measurement breaks on each rail. Spec/brief outranks the standard, and the
standard does not forbid the practice, so the breaks stay — see `TEST_PLAN.md §3`.

*No conflict found with the `schematic-style` skill.* The standard is about test coverage, EMC
and layout; the skill is about schematic drawing conventions. They do not overlap.

### DEC-0019 - The USB PHY stays inside the `mcu` block
**Date** 2026-09-02 · **Status** Accepted · **Scope** `mcu`

The USB3320 ULPI PHY, the USB-C receptacle and the QSPI memory are all in `mcu.kicad_sch`
rather than split into their own sheets, as the brief listed them.

*Reasoning.* This makes `mcu` the largest sheet, which argues for a split, but the ULPI bus is
twelve signals that all terminate on the MCU and whose routing constraints are inseparable from
the MCU pin map. Splitting would put a twelve-signal shared interface across a file boundary
between two parallel workers — the exact coupling DEC-0008 exists to prevent — in exchange for
a sheet-size gain.

*Revisit if.* The `mcu` sheet becomes unmanageable in practice. Splitting `usb_phy` out later
is cheap while the root sheet is still unwired.

### DEC-0020 - A3 sheets throughout
**Date** 2026-09-02 · **Status** Accepted · **Scope** all sheets

Every sheet is A3. Sheet titles use a short `CBs_1 - <block>` form.

*Reasoning.* A3 gives the room the `schematic-style` rule "use space generously" asks for,
while staying printable. The short title form is not cosmetic: the full
`ARIA_SRB_FAFF_2 CBs_1 - <block>` form overran the A3 title-block field and was clipped at the
page border on the `mcu` sheet, which violates the skill's "nothing overlaps, ever" rule.
Caught in the render self-check; titles now fit within the field.

### DEC-0021 - ERC status of the skeleton: clean, with nothing suppressed
**Date** 2026-09-02 · **Status** Accepted · **Scope** all sheets

`kicad-cli sch erc --severity-all` reports **0 errors and 0 warnings** across all eleven sheets.
No ERC severity has been downgraded or excluded in `faff2_cbs1.kicad_pro`; the default rule set
is in force.

There are therefore **no remaining violations to explain**. This is expected for a skeleton
carrying no symbols, no wires and no sheet pins, and it is the baseline every block task must
preserve — see `AGENTS.md`.

*Still true with the design complete (2026-09-03).* 409 components, 253 nets, 113 sheet pins
and the root wired, and `--severity-all` still reports 0 errors and 0 warnings with nothing
suppressed. The three residual classes `AGENTS.md` listed for the parallel block wave -
`hier_label_mismatch`, `label_dangling`, `pin_not_driven` - all cleared at root wiring, which
is what that file predicted. This is the end state, not a temporary one.

*Re-run it with:*
```
AMODO_KICAD_LIB=/mnt/c/Amodo/AmodoKiCadLib \
  kicad-cli sch erc --severity-all --exit-code-violations \
  -o /tmp/erc.rpt hardware/kicad/faff2_cbs1/faff2_cbs1.kicad_sch
```

### DEC-0022 - The root sheet is wired as an aligned star on the MCU
**Date** 2026-09-03 · **Status** Accepted · **Scope** `faff2_cbs1.kicad_sch` — closes DEC-0009

All 113 sheet pins are drawn and every cross-block net is a real wire. Nothing on the root
sheet connects by name.

*Layout.* Left to right as `docs/FAFF-2-Electronics-Full.svg` reads: 24 V in at the top left,
sensing and user I/O down the left column, the STM32H723VET6 in the middle, motor drive on the
right.

*Reasoning.* The interconnect is very nearly a star — 48 of the 55 net names are point-to-point
between the `mcu` block and one peer. So each peer's pin rows are **aligned with the mcu rows
they face**, which makes all 48 single straight horizontal wires: no bends, no crossings, no
junctions, and any net can be followed across the page without tracing it. The three routes out
of `power_entry_24v` and the four SPI2 CONFIG-bus routes are the exceptions, and both sets are
**nested** — outermost route for the outermost pair of endpoints — so those do not cross either.
Total: 70 wires, 3 junctions, 0 crossings.

*Consequence.* `temp_sense` sits under `motor_drive` on the right, not in the sensor column,
because it hangs off the same shared SPI2 bus as the DRV8323 (`ARCHITECTURE §5.1`). The bus is
drawn once with two loads tapped off it. Its two probe channels never leave its own sheet, so
nothing is lost by the move.

*Generated, not hand-placed.* `tools/gen_root_sheet.py` is re-runnable and deterministic. The
ten sheet-symbol uuids are hard-coded in it: every child sheet's symbol instances reference
them as `/<root-uuid>/<sheet-uuid>`, and changing one silently disconnects that whole sheet.

### DEC-0023 - `RAIL_PGOOD` stays inside `power_rails` until OQ-07 closes
**Date** 2026-09-03 · **Status** Accepted · **Scope** `power_rails`

`RAIL_PGOOD` was a hierarchical label with nothing anywhere in the project to consume it. It is
a **sheet-local label** now.

*Reasoning.* `power_rails` exported it for "the `test_debug` rail probe header and a future MCU
GPIO". `J402` carries `+5V`, `+3V3`, `+3V3A` and three grounds with no seventh way, and OQ-07
has never allocated the GPIO. A sheet pin on a net with one endpoint is an ERC error, and
inventing a consumer at integration would be exactly the kind of unilateral contract change
`AGENTS.md` forbids.

*What is kept.* `D303` and `TP308` still observe the net inside `power_rails`, which is where
`DEC-0007` puts a producer's own test point anyway. No requirement asks for PGOOD at the MCU.

*How to reverse it.* **OQ-07 stays open.** Allocate one of the spare MCU pins in the `.ioc`
(`SPARE_PA8/PA10/PB4/PB7/PC13/PE3/PE7`), then promote the label back and add the matching label
in `mcu` — one line in each of two sheets plus a root sheet pin.

### DEC-0024 - Power symbols follow the same per-sheet designator range as everything else
**Date** 2026-09-03 · **Status** Accepted · **Scope** all sheets

`#PWR` and `#FLG` references are allocated per sheet, 100 apart, by the block's page number,
exactly like ordinary designators: `#PWR2xx` for `power_entry_24v` through `#PWR11xx` for
`motor_drive`.

*Reasoning.* `loadcell_afe` and `temp_sense` had both annotated from `#PWR001`, so 19 references
were shared between two sheets. KiCad raises nothing — `#`-prefixed references never reach the
netlist — but two sheets' power symbols silently become one component set, which is the same
trap `AGENTS.md` already documents for ordinary designators, with even less warning.

*State.* All 272 power and flag references across the ten sheets are unique, asserted
programmatically. The rule is in `AGENTS.md`.

### DEC-0025 - The DRV8323S land pattern is TI RTA0040B, drawn on the RHA0040B equivalence
**Date** 2026-09-03 · **Status** Accepted · **Scope** `motor_drive`, `faff2.pretty` — closes D-MOT-01

`faff2.pretty/Texas_RTA0040B_WQFN-40-1EP_6x6mm_P0.5mm_EP4.15x4.15mm`, `FPLifecycle draft`.

*Why it was owed.* `SLVSDJ3D` ships the `RTV0032E` and `RGZ0048A` package drawings and not
`RTA0040`'s. TI's own `MPQF134A` drawing for the RTA package is the 2004 single-page style: it
gives the outline but refers the exposed-pad dimension back to the data sheet that omits it.

*How it was sourced.* TI drawing **4219112/A (07/2018), RTA0040B**, found in the DRV8353 data
sheet pp. 98-100 and committed as `datasheets/DRV832x_RTA0040B_package_4219112A.pdf`. Set
beside TI **4219052/A (06/2016), RHA0040B**, the two give an identical outline and an identical
land pattern — 6.1/5.9 body, 36X 0.5 pitch, 2X 4.5 span, 40X 0.5/0.3 terminals, 4.15 ±0.1
exposed pad, land 40X (0.6)×(0.22) inside (5.8), stencil 9X (1.17) on (1.37) — and differ only
in package height, 0.8 mm WQFN against 1.0 mm VQFN. That difference touches the 3D model, not
the copper.

*What was drawn.* KiCad 9's official `Texas_RHA0040B` footprint is therefore a dimension-verified
base, which is what `pcb-layout-style` allows, and its perimeter pads, silkscreen, fab outline
and courtyard are reproduced by `tools/gen_rta0040b_footprint.py`. Two departures: the stencil
apertures are TI's own 9X (1.17) on (1.37) rather than KiCad's 1.12 on 1.38 (71.5 % coverage
against TI's stated 71 %), and the perimeter pads stay IPC-nominal — a superset of TI's tighter
land, matching the house QFN footprints and leaving an inspectable toe outside the body edge.

*Proof.* Geometry asserted after generation: 40 pads, ten a side, 0.5 mm pitch, 4.5 mm span,
2.9375 row offset, EP 4.15 square. Pin 1 is the top pad of the **left** column, numbering
anticlockwise — `SLVSDJ3D` figure 6-6, the DRV8323S top view — and the project-local `DRV8323S`
symbol's 41 pins (pin 41 = `PAD`) match that figure name for name.

*Open.* `FPLifecycle` is `draft`: the PCB wave confirms the land against a real part before the
first order.

### DEC-0026 - A review PDF is committed under `docs/review/`, deviating from `schematic-style`
**Date** 2026-09-03 · **Status** Accepted · **Scope** `docs/review/`

`docs/review/faff2_cbs1_schematic.pdf` — all 11 pages, from `kicad-cli sch export pdf`.

*Reasoning.* `schematic-style` says "never produce or commit review PDFs — the client reviews in
the KiCad GUI". The captain's integration brief asks for exactly that PDF as the deliverable, so
the more specific and more recent instruction wins. Recorded here so nobody mistakes it for the
general rule changing: renders remain a self-check, and the GUI remains the review surface.

*Maintenance.* Regenerate it from the schematic; never hand-edit it. The command is in
`docs/decisions/actuator-sch-integrate.md §8`.
