# Schematic review round 1 - captain's graphical/stylistic pass

The captain is reviewing the completed schematic sheet by sheet. Each batch of his
points is applied here, one commit per batch. This file records the judgement calls;
`hardware/kicad/faff2_cbs1/SCHEMATIC_REVIEW_LOG.md` gets the consolidated
round-1 table in the final pass, once the parallel workers have landed and this
branch is rebased (editing it per batch would collide with them on the same lines).

Every batch is verified the same way, and none of it is optional:

| Check | Bar |
|---|---|
| `kicad-cli sch erc --severity-all`, stderr read too | 0 errors, 0 warnings |
| `kicad-cli sch export netlist` + per-net **node-set** compare against the pre-batch netlist | identical membership, for a graphical batch |
| `check_overlaps.py` from the `schematic-style` skill | no finding that is not a proven checker artefact |
| Render sweep at 3.2x | every changed area read by eye |

Net *names* and net *codes* may legitimately move; node sets may not. The comparator
is `netcmp.py` - it buckets each net as a frozenset of `(ref, pin)` and compares the
multisets, so a renamed net passes and a flipped diode fails.

---

## Rotation and mirror geometry - settled by experiment, not by memory

Every batch that turns a part needs this, and getting it wrong flips a diode
silently. KiCad's symbol library is Y-up, the sheet is Y-down. For a symbol
instance at `(X, Y)`, a library pin at `(px, py)` lands at:

| instance | pin lands at |
|---|---|
| `(at X Y 0)` | `(X + px, Y - py)` |
| `(at X Y 90)` | `(X - py, Y - px)` |
| `(at X Y 270)` | `(X + py, Y + px)` |
| `(at X Y 0)` + `(mirror y)` | `(X - px, Y - py)` |

Two of these are load-bearing and were **not** guessable from the project alone -
all 27 symbols already rotated 90 deg here are resistors and test points whose pins
sit on `px = 0`, so the `dy` term cancels and two different transforms fit the
evidence equally well. The tie was broken with a throwaway sheet holding a
DMP6023LFG-7 and a 5.0SMDJ26A at 90 deg, wires to both candidate pin positions, and
a distinct label on each: `kicad-cli sch export netlist` then says which candidate
the pin actually joined. Do that again rather than trusting the table if a future
part has an off-axis pin and the result looks wrong.

Consequences worth stating outright:

- A P-FET at 90 deg puts **drain left, source right, gate down**.
- A two-pin part at 90 deg puts **pin 2 above pin 1**; at 270 deg, **pin 2 below
  pin 1**. That is the whole of diode and LED polarity, so pick the angle from the
  polarity you want and confirm it in the netlist, never by eye.

### Instance rotation, not a pre-rotated library variant

`schematic-style` says orientation variants should be pre-rotated in the library so
reference and value text stays horizontal. This project instance-rotates instead -
27 symbols already do - and the render proves the text still comes out horizontal,
because a symbol property's `(at x y angle)` angle is **relative to the symbol**:
angle 270 on a symbol rotated 90 sums to 360. So the rule's stated purpose is met.

Rotating in place was therefore preferred over cloning `DMP6023LFG-7` into a local
`_H` variant, which would have changed the component's `libsource` in the netlist -
a visible diff on a batch whose whole contract is that the netlist does not move -
and would have forked one part away from the house library for a placement choice.

**Field angle to use: 270 for a symbol at 90, 90 for a symbol at 270.**

### KiCad flips field justification on a mirrored symbol

`(justify left)` on a `(mirror y)` symbol renders growing **leftward**. So a mirrored
connector whose text should read left-to-right needs `(justify right)` in the file.
`J201` carries that; the render confirms it.

This is a live defect elsewhere: **`J501` (`loadcell_afe`) and `J701`/`J702`
(`temp_sense`) are mirrored with `(justify left)`, so their reference and value text
runs leftward across the block border** - `J501`'s `1729076` crosses its own dashed
block edge. The bundled overlap checker does not catch it, because the checker
models the text box growing right. Picked up for the final design-wide text-overlap
sweep.

### Overlap-checker artefacts this batch leaves behind

Five findings on `power_entry_24v` survive, all confirmed against the render as
checker bugs of two classes already documented in `actuator-sch-afe.md` §7:

| Finding | Why it is an artefact |
|---|---|
| `text-vs-blockborder` on `J201` Reference and Value | the checker grows a right-justified field rightward, ignoring the mirror flip; the text actually sits inside the block, reading rightward from x=19.05 |
| `body-vs-wire` on `D201`, `body-vs-body` `R207`/`D202`, `body-vs-wire` on `D202` | the checker reflects a rotated symbol's body about its origin and reports a degenerate box at the wrong y; both parts sit centred between their own stubs |

---

## Batch 1 - `power_entry_24v` (refdes 2xx)

Five captain points, all graphical. ERC 0/0, 409 components, 253 nets, node sets
identical to the pre-batch netlist.

Applied by `tools/apply_review_r1_batch1.py`, which is **re-runnable**: it rebuilds
the sheet from the committed `HEAD` copy every time, so re-running it after an edit
gives the same file rather than compounding. Coordinates live in tables at the top.

| # | Captain's point | What was done |
|---|---|---|
| 1 | "Mirror the input power connector so that the pins come out left to right, and wires don't have to route around its body." | `J201` mirrored (`mirror y`) and moved to x=22.86 so the body sits left of its pins. All five pins now leave rightward: the +24 V pair joins at x=29.21 and rises straight to the input rail, the 0 V pair runs right to x=44.45 and drops to the choke, the shield goes right into `R208`. No wire passes the body any more, and nothing crosses |
| 2 | "Have the input protection FET horizontal, so that pins 1 and 5 are horizontal not vertical." | `Q201` rotated 90 deg at (109.22, 71.12): drain on the left taking the `V24_IN` drop, source on the right feeding `V24_PROT`, gate straight down into the divider. The old gate net looped left round the body to x=92.71 and back; it now drops vertically and runs right |
| 3 | "Where you have a potential divider ... make sure they are vertically aligned." | `R201` and `R202` share x=140.97, `R201` from the rail to the gate node and `R202` from the gate node to GND. The gate node is a **3-way tee** (rail in from the left, `R201` up, `R202` down) - putting the column mid-rail instead would have made it a 4-way |
| 4 | "D201 is in parallel with C204, etc, so graphically it should also be placed vertically like C204 etc. Same for D202." | `D201` rotated 90 deg to sit vertically at x=147.32 with 2.54 stubs, exactly like `C204`/`C205`/`C206`, and its GND flag lands on their y=81.28. `D202` rotated 270 deg to sit vertically under `R207` at x=195.58, anode up. Both previously jogged sideways between two vertical wires |
| 5 | "It would be nice if GND connections for parallel components are vertically aligned. R206 and C207 GND flags should be at the same vertical height." | `C207` dropped to (336.55, 90.17) and its stubs lengthened to 3.81 to match `R206`'s, so both GND flags sit at y=96.52 and both parts' pins line up |

### Placement consequences that had to be worked out

- **The shunt bank moved 5.08 right** (`C204`/`C205`/`C206`/`R207` and their GND
  symbols). `D201`'s value string `5.0SMDJ26A` is 10 characters; once the part
  stood vertical, that text ran into `C204`'s body at the old 10.16 pitch.
- **`C203` moved to x=129.54 and the divider to x=140.97.** The `V24_PROT` label is
  9.3 mm of text and has to sit over the rail without covering `C203`'s junction
  dot; `C203`'s own value text then has to clear `R201`'s body. Both constraints
  push right, and the divider follows `C203` so the gate rail stays a single
  left-to-right run.
- **`R201`'s fields sit 2.4 mm below the usual offset**, so its reference clears the
  `GND` label under `D201`. Moving the `GND` label instead would have broken the
  alignment point 5 asks for.
- **The `V24_IN` drop stays at x=104.14.** Moving it left to 99.06 (to buy the
  `V24_PROT` label more room) put it through `C202`'s value text and `#PWR205`'s
  `GND` - caught by the overlap checker, reverted, and the room found further right
  instead.
- **`R208` moved to x=31.75**, clear of both the 0 V drop and the +24 V riser, so
  the three nets leaving the connector never share a column.

### Noted, not changed

- The sheet note under section A reads "C103 sits gate-to-SOURCE"; the part is
  **`C203`**. A one-character typo in explanatory text, left alone because this
  batch is placement only. Worth a line in a later batch.
- `TP202` sits at x=133.35 between `C203` and the divider, 3.81 from `R201`'s tap.
  Legible - its text is above the rail, `R201`'s below - but it is the tightest
  dot spacing on the sheet.

---

## Batch 2 - `power_rails` (refdes 3xx)

Six captain points. Point 4 was an authorised design change, so this batch does
move the netlist: **409 -> 405 components, 253 -> 251 nets**, ERC still 0/0. Every
node-set change was checked one by one against the intended edit; the list is
below. Applied by `tools/apply_review_r1_batch2.py`, re-runnable from `HEAD`.

| # | Captain's point | What was done |
|---|---|---|
| 1 | "Never ever use a 4-way net connection (junction for R303, TP301, R304 and U301 pin 5). Also, do not place test coverage on PSU feedback nodes." | `TP301` deleted. That is the same edit twice over: it takes the test point off the feedback node **and** leaves the node a plain 3-way tee (R303 down, R304 up, FB in from the left). `TP305` on the `+3V3` feedback node was the identical case one section down and went with it |
| 2 | "At the output of all regulators, use a dual test point, so that I can hook up an oscilloscope probe." | `TP302` `+5V5`, `TP303` `+5V`, `TP304` `+5VA`, `TP306` `+3V3`, `TP307` `+3V3A` are all `Amodo_Connectors:TestPointDual` now - the probe pad and its ground clip, 2.54 apart. Each hangs on a short stub **below** its rail with its own GND symbol, rather than sitting on the rail: the pads project sideways from the pins, so on the rail itself they would straddle the wire they tap |
| 3 | "Series output zero ohm links for regulators should be placed horizontally, not vertically." | `R305`, `R306`, `R307`, `R312` rotated 90. Each rail now runs left to right through its link and steps down once, instead of the link being the step |
| 4 | "For regulators in general, can you tend towards using the same parts as used in this design" | `U301` -> **LMR51610XFDBVR**. `U304` and both LDOs kept, with reasons - see below |
| 5 | "Ferrite beads used for rail filtering should be placed horizontally ... to keep flow of power in one direction, without un-necessary corners." | `FB301` rotated 90 and moved onto the `+3V3` rail itself, so `+3V3` -> ferrite -> `+3V3A` is one straight run |
| 6 | "Power LEDs should also ideally be placed vertically." | `D303` rotated 270 - anode up out of `R314`, cathode down into `RAIL_PGOOD` |

### Point 4 - what moved to the reference design's parts, and what did not

`ARIA_EITSYS_CBs_1/Power.kicad_sch` was cloned read-only and read for its
regulator vocabulary: **LMR51610XFDBVR** bucks (3 off), **ADPL42005** LDOs
(6 off), a TPS7A39 for the +/-15 V analog pair, and `TestPointDual` on every
rail. The test-point pattern is adopted wholesale under point 2.

**`U301`, the `+5V5` pre-regulator: swapped to `LMR51610XFDBVR`.** It meets
every requirement this rail has, and beats the LMR33630 on all of them:

| | LMR33630 (was) | LMR51610XFDBVR (now) |
|---|---|---|
| V<sub>IN</sub> | 3.8-36 V | **4-65 V** |
| I<sub>OUT</sub> | 3 A | 1 A, against this rail's ~0.25 A |
| f<sub>SW</sub> | set by design at 400 kHz | **fixed 400 kHz** in the "X" variant |
| Package | HSOIC-8 + PowerPAD | SOT-23-6 |
| V<sub>FB</sub> | 1.0 V | 0.8 V |

Everything downstream re-derived from `datasheets/LMR51610.pdf` (SLUSEY1B),
whose own worked example in §8.2.2 is a 24 V -> 5 V, 400 kHz design - our case
almost exactly:

* **Feedback divider.** R<sub>FBT</sub> = (V<sub>OUT</sub> − V<sub>REF</sub>)/V<sub>REF</sub> × R<sub>FBB</sub>.
  `R303` stays 100 k 0.1 %; `R304` 22.1 k -> **16.9 k 0.1 %**, giving
  0.8 × (1 + 100/16.9) = **5.534 V**. R<sub>FBT</sub> = 100 k sits at the top of
  TI's recommended 10 k-100 k window. With the reference's ±1.5 % the rail spans
  5.45-5.62 V: still under the TPS7A20's 6.0 V recommended input maximum, and
  still 0.53 V of dropout headroom over the 5.0 V it has to make.
* **Inductor.** L<sub>MIN</sub> = ((V<sub>IN</sub>−V<sub>OUT</sub>)/V<sub>IN</sub>) × V<sub>OUT</sub>/(K<sub>IND</sub>·I<sub>OUT</sub>·f) = 35.3 µH at K<sub>IND</sub> = 0.3,
  so `L301` 15 µH -> **33 µH** (`IND_SMD_33uH`, Bourns SRN6045TA, 1.8 A<sub>rms</sub> /
  2.5 A<sub>sat</sub>). Ripple works out at 0.32 A, K<sub>IND</sub> = 0.32, inside TI's
  20-60 % band, and the ratings match what TI asks for its own example
  (1.5 A<sub>rms</sub>, 2.5 A<sub>sat</sub>).
  *Not* `IND_SMD_33uH_4.0A`, the other 33 µH house part: its footprint
  `Amodo:L_Bourns_SRP7050WA` is not in the library, so it fails ERC's
  footprint-link check, and its symbol is `draft`. Worth an upstream fix.
* **Enable / UVLO unchanged.** The LMR51610's V<sub>EN(R)</sub> is 1.227 V typ,
  the same as the LMR33630's, so `R301`/`R302` (100 k / 8.2 k) still give the
  16.2 V rising UVLO DEC-P9 specified. No change.
* **Input and output capacitors unchanged.** TI asks for >=2.2 µF rated at twice
  V<sub>IN</sub>, and >=22 µF out; the sheet already carries 2x10 µF 50 V + 220 nF in
  and 2x22 µF + 100 nF out.
* **`C305` 100 nF is now the CB (bootstrap) cap** rather than BOOT - same part,
  same value, same job, different pin name.
* **Deleted: `C304` (the LMR33630's V<sub>CC</sub> cap) and `#PWR307`/`#PWR308`.**
  The LMR51610 has neither a V<sub>CC</sub> pin nor a thermal-pad pin.

**`U304`, the `+3V3` buck: kept as LMR33630.** This rail's budget is
**1.1 A** - STM32 0.5 A, rotary encoder 0.1 A, other 3V3 ICs 0.5 A
(`REQUIREMENTS.md` power budget) - against the LMR51610's 1 A rating. There is no
margin at all, so the reference design's part does not meet this rail's
requirement. The board now carries two buck part numbers where DEC-P2 wanted
one; that is the price of the swap, and it is a fair one because the two rails
are a 4x current apart and the 3 A part was always oversized for the 0.25 A one.

**`U302`/`U303`, the 5 V LDOs: kept as TPS7A20.** The reference design's
**ADPL42005** is a 20 V, 500 mA, **32 µV<sub>RMS</sub>** low-noise LDO; the
TPS7A20 is **7 µV<sub>RMS</sub>** with 95 dB PSRR at 1 kHz. `+5VA` carries the
ADS1235's AVDD and the load-cell excitation chain, and `REQ-FF-04`'s 2.4 µV pk-pk
input-referred noise budget is the measurement this board exists to make - a
4.6x noisier supply there is a step backwards, and splitting the two 5 V rails
across two part numbers to take the reference part on the digital one only would
cost the BOM commonality DEC-P3 was built on. **Flagged for the captain**: if he
wants the house part regardless, the fixed-output `ADPL42005ACPZ-5.0-R7` is in
the library and drops in without a divider.

A second reason to raise rather than swap: **analog.com is unreachable from this
environment**, so the ADPL42005 datasheet could not be fetched and its passives
could not be re-derived from a primary source, which is what this batch's brief
asks for. The 32 µV<sub>RMS</sub> figure above comes from ADI's product
description, not the datasheet. `datasheets/LMR51610.pdf` is committed;
that one downloaded cleanly.

### RAIL_PGOOD after the swap

The LMR51610 has no PG pin, so `R315` and the section-A leg of the wired-AND are
gone. `RAIL_PGOOD` is now the `+3V3` buck's open-drain PG alone, through `R316`,
still pulled up by `R313` and still driving only `D303` and `TP308`. The `+5V5`
rail loses its own power-good report; the two 5 V rails never had one (the
TPS7A20 has no PG pin either), and a failed pre-regulator shows as both 5 V rails
collapsing. `RAIL_PGOOD` remains OQ-07's open question.

### Netlist changes, checked one by one

| Net | Change | Why |
|---|---|---|
| `V24_LOGIC` | `U301` pin 2 -> pin 5 | VIN pin number differs |
| `Net-(U301-EN)` | pin 3 -> pin 4 | EN pin number differs |
| `Net-(U301-SW)` | pin 8 -> pin 6 | SW pin number differs |
| `Net-(U301-BOOT)` -> `Net-(U301-CB)` | pin 7 -> pin 1 | same net, renamed by the pin |
| `Net-(U301-FB)` | pin 5 -> pin 3, `TP301` gone | point 1 |
| `Net-(U301-PG)`, `Net-(U301-VCC)` | gone | pins do not exist |
| `Net-(U304-FB)` | `TP305` gone | point 1 |
| `RAIL_PGOOD` | `R315` gone | no PG to isolate |
| `GND` | `U301` pins 1 and TP, `C304`, `R315` gone; `TP302/303/304/306/307` pin 2 added | the five dual test points' ground pads |

Components 409 -> 405: `TP301`, `TP305`, `C304`, `R315` removed (power symbols
are not BOM components, so the five new GND symbols do not count). Nets 253 ->
251: `Net-(U301-PG)` and `Net-(U301-VCC)` gone.

### Also fixed while in the sheet

`R314`'s reference and value were right-justified at an anchor left of its body,
so `330R` sat against `C324`'s `GND` label. **The bundled overlap checker misses
this class** - it grows every field rightward from the anchor and never checks
`justify right` - so a render caught it where the checker did not. Fields flipped
to `justify left` on the right-hand side, which the LED standing up freed. Worth
carrying into the design-wide text sweep: **anywhere a field is `justify right`,
the checker's finding, or its silence, means nothing.**

### Overlap-checker residue

One finding left on this sheet: `body-vs-body R314 / D303`, the rotated-symbol
artefact described at the top of this file - the checker reflects `D303`'s body
about its origin and lands it on `R314`. The render shows 2.5 mm of clear space
between them.

---

## Batch 3 - `motor_drive` (refdes 11xx)

Four captain points. Point 4 is an authorised design change and adds six parts:
**398 -> 404 components, 251 nets unchanged**, ERC 0/0. The only nets that move
are `V24_MOT` and `GND`, each gaining the six new capacitor pins; every other net's
node set is identical to `main`. Applied by `tools/apply_review_r1_motor.py`.

| # | Captain's point | What was done |
|---|---|---|
| 1 | "R1101 and R1102 are in series, so I think the comment is wrong about fitting one vs the other. Also, the comment says R101 and R102, which I think is a mistake?" | The refdes were wrong - **the captain is right, they should read R1101/R1102** - and the note was written so it *could* be read as alternatives. The circuit is genuinely two 0R in series, both fitted (`actuator-sch-motor.md` D-MOT-14 says so explicitly), so this is a wording fix, not a rewire. The note now leads with "in SERIES and both fitted ... not alternatives to each other" and gives each link its own job |
| 2 | "Text overlap around C1101" | Real: at the old 8.89 pitch, `C1101`'s reference ran 0.33 mm into `C1102`'s body, and the same for the next two. The bulk column is respaced to 57.15 / 68.58 / 80.01 / 90.17, and `TP1103` moved 5.08 right - its pad sat in the row the capacitor values occupy, so widening the column pushed `C1104`'s value onto it |
| 3 | "Same as other sheet review for sheet entry / exit labels justification. This text should not overlap the wires." | **Eight labels fixed.** Seven had their wire arriving from the *left* while the label was `rot 180` + `justify right`, so the text grew back along the wire and the wire ran straight through it - `MOTOR_FETTEMP`, `MOTOR_ENCODER_A/B/I`, `HALL1/2/3`. All are now `rot 0` + `justify left`: flag at the wire's end, text to the right in clear space, in one aligned column at x=91.44 (moved in from 99.06 so the longest name fits inside the block). The eighth, `+24V_SW`, was `rot 90`, and its vertical text ran up into the block title; it is horizontal now. The other seventeen labels on the sheet already had their wire on the right and were left alone |
| 4 | "Should there be some bulk decoupling on this sheet? Also, decoupling per FET, or is this not usually done?" | Answered below, and six capacitors added |

### Point 4 - the answer, and what was added

**Bulk decoupling was already there; what was missing was decoupling at the
bridge.** Three separate jobs, and the sheet only did two of them:

| Job | Where | Was it there? |
|---|---|---|
| DC-link bulk store | `C1101`-`C1104`, 210 µF at the bus entry | yes |
| Gate-driver VM bypass | `C1109` 100 nF + `C1110` 10 µF at U1101 | yes - exactly TI's "0.1 µF ceramic and >= 10 µF local capacitance between VM and PGND" |
| **Half-bridge commutation loop** | at each leg | **no - nothing at all in the power-stage block** |

TI asks for the third one in as many words (SLVSDJ3D §10): *"Additional bulk
capacitance is required to bypass the external half-bridge MOSFETs"*, and §11.1:
*"placed such that it minimizes the length of any high current paths through the
external MOSFETs."* The house standard makes the same argument from the other end
- return current follows the lowest-impedance path, and a large loop is what
radiates. The 210 µF sits at the sheet's bus entry, the far side of `R1101`,
`R1102` and the whole `V24_MOT` run; it cannot be in the commutation loop.

**Added: one 2.2 µF 1206 100 V X7R + one 100 nF 0805 100 V per half-bridge** -
`C1119`/`C1120` phase U, `C1121`/`C1122` phase V, `C1123`/`C1124` phase W, each
from `V24_MOT` to `GND`, drawn beside its own leg. Sizing: the loop has to supply
the phase-current step at each edge; at the sheet's own operating point (1.9 A,
20 kHz - the figure the DC-link ripple note already uses) and a ~100 ns edge, that
is ~190 nC, so 0.4 V of sag needs ~0.5 µF. 2.2 µF at 100 V derates very little at
24 V and leaves 4x margin. The 100 nF in the smaller 0805 has the lower ESL and
takes the fast edge - the same two-part pattern the sheet already uses at the bus
entry and at VM.

**"Decoupling per FET" is not a thing, and that is the useful half of the answer.**
A capacitor across a single MOSFET is a *snubber*, not decoupling: it damps
ringing, costs switching loss, and needs a series resistor sized against the
measured ringing frequency. It is a bring-up decision taken with a scope on the
switch node, not a default. The right granularity for decoupling is the
half-bridge - one pair per leg, which is what was added.

### Where the caps could and could not go

The first placement shorted two gate nets to ground and had to be redone. The
DRV8323's gate and SHx fan-out leaves U1101 as a **diagonal staircase** - five
horizontals per phase group, each turning down a vertical at x = 260.35, 265.43,
270.51, 275.59, 280.67, 285.75, 290.83, 295.91, 300.99, 306.07, 311.15, 316.23,
321.31, 326.39. Two of the first cap columns landed exactly on x=270.51 and
x=280.67, and a vertical stub **collinear with an existing wire merges into it** -
so each capacitor bridged a gate net to `GND`. ERC caught it as
`pin_to_pin` between `GHC` and a `PWR_FLAG` two sheets away.

The lesson is the general one: **do not infer free space from a partial wire
dump.** The three bands finally used were checked against every wire in the block
for overlap *and* crossing, and none of the new geometry does either:

| Leg | Cap pair | Band, and why it is clear |
|---|---|---|
| U | `C1119`/`C1120` at x=275.59 / 285.75, y=73.66 | between the phase-A fan-out (ends y=72.39) and the phase-B one (starts y=87.63); the verticals at those x start at y>=97.79 |
| V | `C1121`/`C1122` at x=311.15 / 321.31, y=102.87 | right of the fan-out; x=311.15's vertical ends at y=100.33, x=316.23's at 91.44 |
| W | `C1123`/`C1124` at x=292.10 / 302.26, y=153.67 | below the phase-B verticals (all end by y=151.13) and above phase C's gates (y=167.64) |

### Noted, not changed

`MOTOR_ENCODER_A/B/I` and `HALL1/2/3` are declared `input` on this sheet, but
`J1101`/`J1102` are the connectors those signals *come from* - they read like
outputs of `motor_drive`. ERC is clean and the root agrees, so the shapes are at
least self-consistent; raising it rather than changing an interface contract
mid-review.
