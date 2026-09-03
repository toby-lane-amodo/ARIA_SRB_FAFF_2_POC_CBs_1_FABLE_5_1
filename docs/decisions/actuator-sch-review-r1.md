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

> **Overruled by the captain, round 3 item 3: both rails are now
> `ADPL42005ACPZ-5.0-R7`.** The record below is why I argued the other way; it
> is not the design. Round 3's own section has the swap.

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

---

## Final pass - the design-wide sweep

Five sweeps the captain asked for once the per-sheet batches had landed, run over
all nine block sheets plus the root. **ERC 0/0, 404 components, 251 nets, and the
per-net node sets identical to the pre-sweep export** - nothing here is
electrical. Applied by `tools/apply_review_r1_sweep.py`, which rebuilds every
sheet from `HEAD`, and verified with `tools/sch_geom.py`.

| Sweep | Found | Done |
|---|---|---|
| Power labels missing | 92 hidden rail names, all on `loadcell_afe`, `motor_drive` and `temp_sense` | all shown, placed to the house pattern |
| Test point silkscreen names | 66 of 83 still carried the library default `TestPoint` | all 83 named from the net they land on, longest 5 characters |
| Text over wires, borders, bodies | 16 collisions, several invisible to the bundled checker | all cleared |
| Ground symbols upside down | **none** - 0 of 285 power symbols is rotated or mirrored | nothing to do; recorded as verified |
| Graphic lines shadowing wires | 1 - `power_rails` block D's bottom border lay along the last `PWR_FLAG`'s wire | the five-row flag column moved up 2.54 |

### The overlap checker has three blind spots, and they matter

This is the most re-usable thing the sweep produced. `check_overlaps.py` was
treated as the arbiter by the earlier waves - `actuator-sch-integrate.md §7`
dismisses eleven findings as artefacts on that basis. It is a good first pass, but
it is wrong in three separable ways, each established here by measuring a render
rather than by reading the format:

1. **It grows every text field rightward from its anchor.** Text actually renders
   leftward when `justify right` is set, when the symbol carries `(mirror y)`, or
   when the symbol sits at 180° - and any two of those cancel. So for a field in
   any of those states the checker's box is a mirror image of the truth: it
   invents collisions that are not there (`J201`, `J501`, `TP505`, `TP702`,
   `TP704`, `TP705`, `TP706`) and misses ones that are (`C1016` on `mcu`, whose
   reference and value lay on `U1003`'s VDD wire; `R314` on `power_rails`).
2. **It measures text at about 1.06 mm per character.** A 6 px/mm render says
   `5.0SMDJ26A` inks 11.435 mm over ten characters and `100uF` 5.65 over five,
   which back out to a **~1.19 mm advance**. The checker therefore under-measures
   every box by about a tenth, and a "clear by 0.3 mm" verdict can be a real
   overlap. Four of the sixteen collisions this sweep fixed were of exactly that
   size.
3. **It reflects a rotated or mirrored symbol's body about the origin**, and
   reports a degenerate box at the wrong place. Every `body-vs-*` finding on such
   a symbol is noise - already known, and now explained.

`tools/sch_geom.py` implements the transforms and the text model that the renders
support, and is the cross-check to run before believing either tool. Its rules:

```
pin/graphic transform   rot 0    (x+px, y-py)      rot 180  (x-px, y+py)
                        rot 90   (x-py, y-px)      rot 270  (x+py, y+px)
                        mirror y (x-px, y-py)

text grows left when    (justify right) XOR (symbol at 180) XOR (mirrored)
                        - but a hierarchical or local label takes no 180 flip
note box                grows down from the anchor only with (justify ... top);
                        otherwise it grows UP, and the line pitch is 1.85 mm
```

The last two lines were both bugs in my own first model, each caught by the
checker disagreeing with me and then settled by a render. Neither tool is
authoritative alone; the render is.

### Placement was searched, not guessed

Making 177 fields visible at a fixed offset produced 36 new collisions. The sweep
instead **tries candidate offsets against every wire, block border, symbol body,
note, label and already-placed field on the sheet, and takes the first that is
clear**, with a 0.35 mm margin. A third pass then nudges any field that was
already colliding before the sweep. That is what took the design from 16
collisions to none, and it is why the script is worth keeping: re-run it after any
placement change and it re-solves.

### Test point silkscreen names

Under six characters, taken from the net each test point actually lands on in the
exported netlist - not from what its old value said. `GND` is used unqualified
wherever a test point is a plain ground pad.

| Sheet | Names |
|---|---|
| `power_entry_24v` | `24VIN` `24VPR` `24VSW` `24VLG` `24MON`, 2x `GND` |
| `power_rails` | `+5V5` `+5V` `+5VA` `+3V3` `+3V3A` `PGOOD`, 4x `GND` |
| `loadcell_afe` | `EXC+` `SNS+` `SNS-` `REFP` `REFN` `PWRDN`, 2x `GND` |
| `linear_encoder` | `5VENC` |
| `temp_sense` | `PRB1A` `PRB1B` `PRB2A` `PRB2B` `REFP` `REFN` `DRDY` `nCS` `SCK` `MOSI` `MISO`, 2x `GND` |
| `nvm_calibration` | `SCL` `SDA` `WP`, 2x `GND` |
| `ui_io` | `SYNC` `SYNCO` `LIM_A` `LIM_B` `nBRK`, 2x `GND` |
| `mcu` | `BOOT0` `nRST` `24MHZ` `3V3U` `1V8U`, 6x `GND` |
| `motor_drive` | 2x `24MOT`, `VBUSM` `FETT` `VENC` `VMDRV` `VCP` `nFLT` `SOA` `SOB` `SOC` `GHA` `GLA` `GHB` `GLB` `GHC` `GLC` `PH_U` `PH_V` `PH_W`, `GND` |

`REFP`/`REFN` appear on both `loadcell_afe` and `temp_sense`: each is that ADC's
own reference pair, unambiguous on its own sheet and on the board beside its own
part. `TP1101` and `TP1102` are both `24MOT` because they are two pads on one net -
a hook and a scope pair - and the label says what is measured, not which pad.

### The instance-rotation rule, narrowed

`AGENTS.md` briefly forbade instance rotation outright, on the grounds that it
turns field text sideways. It does not, provided the field angle is compensated -
a property's `(at x y angle)` is **relative to the symbol**, so 270 on a symbol at
90 sums to 360 and the text comes out horizontal. 38 instances across the design
rely on this and all of them render correctly. The rule now permits rotation with
that condition and the requirement to prove it in a render, and still points at
`faff2_passives.kicad_sym` as the lower-effort path. Ruled by firstmate on the
captain's behalf; the 11 instances from batches 1 and 2 stand.

---

# Round 2 - the captain's second pass

## Item 1 - `U301` back to the LMR33630

The captain overruled the reference-design part swap, for `U301` only. Reverted:
the buck, `R304` (16.9k back to 22.1k), `L301` (33 µH back to 15 µH), and the
three parts the LMR51610 had no pins for - `C304` on V<sub>CC</sub>, the
thermal-pad ground, and `R315` in the PG leg. `RAIL_PGOOD` is the wired-AND of
both converters again.

Restoration is **verbatim from 48a5f4f**, the last tree with the LMR33630, so the
seven symbols come back with their original uuids rather than as look-alikes, and
the sheet notes revert with them.

Everything else round 1 did to this sheet stands, because none of it depended on
which buck was fitted: the five dual test points, the horizontal 0R links and
ferrite, the vertical power LED, and - the point worth stating - **no test point
on either feedback node**. `TP301` stays deleted.

406 components, 253 nets (`Net-(U301-VCC)` and `Net-(U301-PG)` are back), ERC 0/0.
`datasheets/LMR51610.pdf` stays committed; it is the record of why the swap was
evaluated and what it would have cost.

## Item 2 - PWR_FLAGs moved to their regulators

They were a column of their own in block D, each flag hung off a **duplicate**
power symbol that existed only to give it a net. Each flag now taps the rail it
declares, on the **load side of that rail's 0R link** - before the link is a
different net, so a flag there would declare the wrong thing:

| Flag | Rail | Now taps |
|---|---|---|
| `#FLG344` | `+5V5` | the run out of `R305`, at x=186.69 |
| `#FLG345` | `+5V` | `U302`'s output run, beside `#PWR317` |
| `#FLG347` | `+5VA` | `U303`'s output run, beside `#PWR322` |
| `#FLG349` | `+3V3` | the run out of `R312`, at x=186.69 |
| `#FLG351` | `+3V3A` | the `+3V3A` run past `FB301` |

`#PWR346`, `#PWR348`, `#PWR350` and `#PWR352` went with the column. Each of those
rails already carries a power symbol at its output (`#PWR317`, `#PWR322`,
`#PWR334`, `#PWR337`), so the duplicates declared nothing the sheet did not
already say - node sets are identical across the change, which is the proof.
`#FLG301` stays where it is: `V24_LOGIC` arrives at the sheet rather than being
made on it, and the flag already sits on that input beside `U301`.

### Caught while checking the render: five fields were rendering sideways

`TP302`/`TP303`/`TP304`/`TP306`/`TP307` are `TestPointDual` at 270°, and round
1's placement pass rewrote their Value with **angle 0** instead of keeping the 90
that compensates the rotation - so the silkscreen names read vertically. Fixed,
and `tools/apply_review_r1_sweep.py` now preserves a field's angle when it moves
it. Neither the overlap checker nor the netlist can see this class; only a render
can.

## Item 3 - D601/D602, and an ESD audit of every external interface

### Why D601 and D602 are in parallel

**Not per-connector ESD.** `D602` is a **DNP second footprint in parallel with
`D601`**, both on the read head's `+5V_ENC` feed, and it was added at the
captain's own request in the AFE review round - `actuator-rev-afe.md` records it
as "a second SC-79 clamp position at the connector. Populate both for more
peak-pulse capability, or fit a different clamp voltage / bidirectional part here
without reworking `D601`'s pads." It is one of **three** DNP parallel bring-up
positions on that supply, and the sheet note says so: `R608` parallels `R601`
(fit a shunt and lift `R601` to meter head current in circuit), `R609` parallels
`FB601` (bypass the bead), `D602` parallels `D601`. None fitted by default.

So it has nothing to do with J601 and J602 being two connectors. Those two are
the *same ten signals in parallel* - one FFC receptacle and one 1.27 mm header
for the same head, pin n to pin n - so a clamp on either serves both.

### Why the other IOs do not all have clamps

They follow a policy that is already written down and is **exposure-based, not
per-connector**. Protection goes where a pin is exposed outside the enclosure or
gets hot-plugged; everywhere else the current is bounded by a series resistor and
an RC into a device that can absorb it. `REQ-SC-01` - prototype, EMC best
practice, no formal testing, no CE mark - is what makes that proportionate.

| Interface | Leaves the enclosure? | Protection | Where it is argued |
|---|---|---|---|
| `J201` 24 V input | yes | `D201` 5.0SMDJ26A TVS, 5 kW | `actuator-sch-power.md` DEC-P5 |
| `J1001` USB-C | yes | `D1001` USBLC6-2P6 on D+/D-/VBUS | `actuator-sch-mcu.md` |
| `J902` SMA sync | yes | `D903` ESD8351XV2T1G, 0.55 pF so the edge survives | `actuator-sch-periph.md` D-PER-16 |
| `J601`/`J602` read head | no, but the FFC is hot-plugged | `D601` (+`D602` DNP) on the supply; the A/B/Z pairs terminate into an AM26LV32 line receiver, not the MCU; `ENC_SDO`/`ENC_nPROG` go through 1 k + 100 nF | `actuator-rev-afe.md` |
| `J903` limit switches | no, internal harness | 1 k feed + 100 R + 10 nF, into the AND gate's and MCU's own clamps | `actuator-sch-periph.md` |
| `J901` panel button | the button is user-touchable | 100 R + 100 nF - an 8 kV contact discharge is ~150 nC, which puts 1.5 V on 100 nF and microamps through the 100 R | `actuator-sch-periph.md` D-PER-15 |
| `J501` load cell, `J701`/`J702` probes | no, internal | none, deliberately - these are the accuracy-critical analog paths and diode capacitance and leakage land straight on them | `actuator-sch-afe.md` |
| `J1103` motor phases | no | none, and a clamp would be wrong: this is a bridge-protection question, answered by the FET avalanche rating and the DC-link TVS |  |
| `J1002`/`J1003`/`J1004`/`J502`/`J603` | no, bench debug only | none needed |  |

### The one gap, and what was done about it

`J1101`/`J1102` - the motor rotary encoder and hall harness - ran **connector ->
pull-up -> MCU pin with nothing in between**, on six pins. `D-MOT-11` justified
that as an internal cable, which is true; but the **limit harness is equally
internal and gets 1 k + 100 R + 10 nF, and the buttons get 100 R + 100 nF**,
both explicitly "to protect the MCU pins". Two internal harnesses, two different
answers, and the six bare ones are the safety-adjacent motor feedback.

**Added `R1128`-`R1133`, 100 Ω in series**, one per line, between each pull-up
node and its MCU pin. That is the cheap end of the same treatment the rest of the
board already gets: at the ~270 kHz `D-MOT-11` sizes these lines for, 100 Ω into
a few pF of pin capacitance is nothing, and it bounds the fault current into six
GPIOs. **No TVS array** - the cable is internal, and an array would load the
lines for exposure the design does not have.

A pre-rotated `RES_TF_100R_0603_H` joins `faff2_passives.kicad_sym` rather than
six rotated instances, which is what `AGENTS.md` asks for.

**Not added, and why**: nothing on `J501`, `J701`/`J702` - diode capacitance and
leakage on a 2 mV/V bridge and on RTD/NTC inputs is a decision for the AFE owner
against `REQ-FF-04`, not a sweep. Raised rather than taken.

## Items 4-7 - four per-sheet placement fixes

| # | Sheet | What was wrong | What was done |
|---|---|---|---|
| 4 | `linear_encoder` | `U601A`'s GND body ended at y=166.37 and `U601E`'s `+3V3` body began at **exactly** 166.37 - the two flags were touching | the whole `U601E` group (unit, both flags, four wires and the no-connect on its unused output) drops 7.62, leaving 7.6 mm of clear space |
| 5 | `temp_sense` | `C704`/`C705`'s grounds sat 0.6 mm above the REFP row, with `TP705`'s reference on the row itself; and three verticals at x=137.16/139.70/142.24 ran straight through the block title | the two caps and their grounds move up 5.08, off the REFP row; the title is shortened to "CHANNEL 2 FILTER + SHARED REF", which at size 1.778 ends at x=135.9 and clears the leftmost vertical |
| 6 | `ui_io` | `R915`'s reference sat on its own body: it is the **horizontal** 0R variant but its fields were still on the vertical pattern | fields moved to the `_H` symbol's own pattern - reference above the body, value below |
| 7 | `motor_drive` | `#PWR1109`/`#PWR1110` bodies ended exactly on the block border at y=143.51 and their `GND` text was **outside the box** | both grounds move up to y=138.43, so symbol and text sit inside with 0.6 mm to spare |

The `U601E` move is the one that needed care beyond the symbols: a `no_connect`
caps its unused output, and it does not ride with the symbol - ERC caught that as
`pin_not_connected` plus a dangling no-connect the first time round. Worth
remembering: **a no_connect is placed by coordinate, not attached to the pin.**

## Item 8 - one placement rule for every power symbol's net name

> "When a power rail symbol is placed, it should always have its text for the net
> located directly above it, centre justified, and close. Go through the whole
> schematic and check this."

Applied as **no sideways offset, centred, 3.81 mm away** - above a rail arrow,
**below a ground**. All 283 power symbols now carry it; 103 did not before, most
of them left-anchored rather than centred, and a handful offset by up to 7.6 mm
sideways by round 1's auto-placer.

**The ground mirror is an interpretation, and it is the one thing here worth
challenging.** "Above" a GND symbol is where its wire arrives, so a name there
would sit on the wire; 137 instances and every schematic convention put GND's
name under the triangle. If the captain meant it literally for grounds too, it is
a one-line change in `tools/apply_review_r2_labels.py`.

### The label is pinned, so everything else moves

That is what makes this rule different from round 1's sweep, where the label was
free to dodge. Here, in order:

1. the **symbol** slides along its own stub (never sideways), if that clears it;
2. a **note** that a name lands on is relocated to the nearest clear position;
3. a **block box** gives way - six names sat on a border, and each had 2.5 mm or
   more of clear space beyond it, so five rectangles grew;
4. two `PWR_FLAG`s are **placed by hand**: their names are 9.5 mm wide and the
   rail runs they tap are only 10 mm, so the automatic pass kept shuffling them
   into `+5V` / `+5VA`.

### Thirteen exceptions, listed rather than hidden

These still graze something. Each needs local placement rework on a crowded
sheet - moving the parts around them, not the label - which is more than a label
sweep should do unasked:

| Sheet | Name | Grazes |
|---|---|---|
| `motor_drive` | `#PWR1111`, `#PWR1112` | the "MOTOR ROTARY ENCODER AND HALL SENSORS" title |
| `motor_drive` | `#PWR1130` | the TIM1 note - which has **nowhere to go**: a 47.6 x 8.7 mm box has no clear position anywhere in that block |
| `motor_drive` | `#PWR1113` | a vertical wire |
| `power_entry_24v` | `#FLG203` | `C201`'s body |
| `power_rails` | `#PWR304`, `#PWR325`, `#FLG345`, `#FLG347` | a wire |
| `power_rails` | `#PWR327` | `C318`'s body |
| `temp_sense` | `#PWR714`, `#PWR717` | `C711`'s value and body, and a wire |

Thirteen of 283 is 95.4 % on the rule with clear space. The gate-driver block on
`motor_drive` and the ADS1120 supply corner on `temp_sense` are where the density
bites; both would need their parts respaced to take the rule fully.

### A measurement bug worth remembering

My own severity metric scored these at **zero** for a while. A wire or a block
border is a *zero-thickness* segment, so "overlap depth" between it and a text box
is always 0 - even when the line runs straight through the middle of the glyphs.
Ranking by that number hid every wire-through-text case behind a wall of
harmless-looking zeros. **For a zero-thickness obstacle the severity is how far
inside the box the line sits, not the box intersection.** A render caught it; the
number did not.

---

# Round 3

## Item 1 - a text-clearance checker that can actually see these, and the sweep

The captain found two overlaps on `power_rails` by eye that every previous pass
had passed: `C312`'s reference against the vertical wire beside it, and **`U303`'s
own value text sitting on its own body's top edge**. Both were real. Four
separate reasons the tooling could not see them:

| # | Blind spot | Whose |
|---|---|---|
| 1 | grows every field rightward from its anchor, so the box is a mirror image whenever the text renders leftward (`justify right`, `(mirror y)`, or a symbol at 180°) | `check_overlaps.py` |
| 2 | measures text at ~1.06 mm per character where the real advance is ~1.19 | `check_overlaps.py` |
| 3 | **never compares a field against its own symbol's outline** - exactly the `U303` case | both it and my round-1/2 model |
| 4 | reports strict overlap only, so text 0.3 mm off a wire passes - and once both stroke widths are drawn, that reads as touching | both |

`tools/check_text_clearance.py` is the recorded successor. It uses the transforms
and text model in `sch_geom.py` (each settled against a render), compares every
field against **every** symbol outline including its own, and requires a real
**clearance** rather than the absence of overlap. `--fix` moves what it can.

**Margin: 0.35 mm.** Calibrated, not guessed - the finding count is flat at 60
from 0.30 to 0.35 and jumps to 149 at 0.40, because the Amodo library's own field
offsets land at ~0.38 mm from a body. 0.35 passes normal house placement and
catches the real thing.

Result: **60 findings down to 13**, and all 13 are power-symbol Values, which
round 2 pinned and this pass therefore may not move. They are item 4.

### One bug worth recording

The first `--fix` keyed fields by **refdes**, and a multi-unit part has one
Reference field per unit under one refdes - so it stacked all five `U601` units'
references on a single point, and both `U901` units' values, and `U902`'s. The
checker reported it immediately as `field:U601.Reference` overlapping itself by
exactly one line height, which is what a coincident pair looks like.
`sch_geom.visible_fields_by_instance()` now keys by symbol uuid, and anything
that walks fields on a sheet with a multi-unit part must do the same.

## Item 1, continued - a fifth blind spot, found the same way

The checker above passed `temp_sense` clean. The render did not: the label I had
just placed on the `ADS1120_nDRDY` stub ran straight through `TP712`'s GND
arrow. **Net labels and symbol bodies were only ever obstacles in that checker,
never subjects** - nothing was ever measured *from* them - so a label through a
body, or a body grazing a wire it does not connect to, scored zero. Both are
subjects now.

Two exemptions keep that honest, and without them it is unusable:

* A symbol body touches every wire that lands on one of its own pins - a GND
  arrow's outline *starts* at its pin - so all 283 power symbols would report.
  `Sheet.pin_points()` gives each instance's connection points and those pairs
  are excused.
* A net label sits on the wire it names, by design. Whichever wire passes
  through the label's own anchor is excused; every other wire still counts.

**Text and outlines need different rules.** A text box is inked edge to edge, so
it must keep real clearance (0.35 mm). A body box is the bounding box of a
triangle or a polyline and its corners are mostly empty - requiring clearance
there reported every wire that merely started at a GND arrow's empty corner, six
of them on `power_rails` alone. So a body counts only when it is genuinely
*penetrated*, and for a wire, only when the wire runs inside it for at least
0.635 mm. That one test separates "wire through the arrow's tip" (2.54 mm of
overlap along the wire - real, and what I had just drawn) from "wire starts at
the arrow's bounding-box corner" (a single point - nothing there at all).

`label_details()` also replaced the label box model: a label anchored `bottom`
puts its glyphs entirely **above** the anchor, one line high, not in a 2.54 mm
band straddling the wire, and a label takes no 180 deg text flip - so growth is
justify-driven alone. Only hierarchical and global labels draw the flag glyph.
`label_boxes()` stays as a thin wrapper because the round-1 and round-2 apply
scripts take bare boxes.

Design-wide this leaves **53 findings**, all pre-existing: power-symbol Values
overlapped by a neighbouring bundle wire, notes and hierarchical labels crossing
block borders, and a handful of body grazes. They are item 4's worklist, which
is therefore larger than the 13 that round 2 recorded.

## Item 2 - temp_sense: TP707..TP711 become one keyed header, J703

`tools/apply_review_r3_j703.py`. Five hooks on the SPI2 nets meant five probe
leads and five chances to slip a clip off a 47R terminator.
`docs/decisions/actuator-rev-afe.md` §7 had already recommended exactly this
part for exactly this sheet, so this applies a standing recommendation rather
than deciding anything new; `J502` and `J603` are the two existing instances.

**Channel map**, copied from J603 pin for pin:

| Pin | Channel | Net | Pin | Channel | Net |
|---|---|---|---|---|---|
| 1 | CH0 | `ADS1120_nDRDY` | 2 | CH1 | `ADS1120_nCS` |
| 3 | CH2 | `CONFIG_SPI_SCK` | 4 | CH3 | `CONFIG_SPI_MOSI` |
| 5 | CH4 | `CONFIG_SPI_MISO` | 6, 7, 8 | CH5..CH7 | no-connect |
| 9 | GND | ground lead | 10 | GND | ground lead |

Tapped MCU-side of `R712`..`R715`, so the bus is still visible with an isolation
link out - the same choice `J502` records. `TP712`/`TP713` stay: they are the
GND hooks the analyser's leads clip to, and `linear_encoder` kept `TP601` for
the same reason.

**It reaches its nets by local labels, not by wires.** The five nets arrive at
7.62 mm pitch and the header's pins are at 2.54, so wiring them directly is five
doglegs. `J502` solved that with local labels matching the sheet's hierarchical
label names, and the netlist proves the idiom: `loadcell_afe`'s SPI3 nets are
already `/loadcell_afe/ADS1235_*` because of it. `temp_sense`'s four bus nets
move from `/mcu/...` to `/temp_sense/...` for the same reason - a rename, with
identical membership, and there is no board yet to disturb.

**Why the block box grew.** A label has to sit entirely over its wire, so each
side of the header needs ~19 mm of run: 66 mm of cluster against a 58 mm box
whose left third already carries U701's descending bundle. The clean space was
the empty band under the box, so `ADS1120 SUPPLIES AND SPI2` extends from
y=154.94 to y=181.61 and the header sits at (209.55, 165.10).

**`TP712`'s GND cluster moved up 5.08 mm**, and needed to regardless: its arrow
tip sat exactly on the `ADS1120_nDRDY` wire at y=106.68. No connection - but it
draws as one, and it was why the label had nowhere to go. This is the defect
that exposed the fifth blind spot above.

`ADS1120_nDRDY` is the name `actuator-sch-afe.md` already used for the net;
it stays sheet-local (DEC-0023) because the `.ioc` still has no DRDY pin.

Net count 259 -> 262: the three no-connect channels each become an
`unconnected-(J703-CHn-Padn)` net, exactly as J603's three do. Components
412 -> 408: five hooks out, one connector in. ERC 0/0.

## Item 3 - both 5 V LDOs become ADPL42005ACPZ-5.0-R7

`tools/apply_review_r3_adpl.py`. The captain overruled round 2's decision to
keep the TPS7A20 (DEC-P3 asked to be overruled, and was). The part was already
in the house library, `SymLifecycle: tested`, with its LFCSP-8 footprint
present - so nothing went project-local and no symbol work was needed.

**The datasheet.** `analog.com` times out from this environment - twice, on two
routes - so `datasheets/ADPL42005.pdf` is a mirror copy of the same Rev. 0
document from `datasheetall.com`, verified as a real PDF and parsed with pypdf.
The `datasheets/README.md` row says so and asks for a re-fetch from the vendor
when a machine can reach it. Nothing below is from memory.

**Pin-by-pin, against Table 5:**

| Pin | Datasheet says | Here |
|---|---|---|
| 8 VIN | "Bypass VIN to GND with a 1µF or greater capacitor" | `+5V5`, C309/C312 |
| 5 EN | "For automatic startup, connect EN to VIN" | tied to `+5V5`, as the TPS7A20 was |
| 4 NC | "Do Not Connect to This Pin" | left bare; the pin's own type is `no_connect` |
| 3, 6 GND | ground | both wired |
| EPAD | internally GND, "highly recommended" on the ground plane | wired |
| 1 VOUT | "Bypass VOUT to GND with a 1µF or greater capacitor" | C310/C313 + C311/C314 |
| 2 SENSE | "Connect SENSE as close as possible to the load" | **to VOUT at the regulator** - see below |
| 7 PG | open drain, pull-up to VIN or VOUT; "may be left open" if unused | no-connect - see below |

Three left-side pins land on a 2.54 mm row (GND, GND, EPAD), so they stub out to
one vertical rail terminating in a single downward GND below the block, which is
`schematic-style`'s dense-pin-row rule. The GND that hung under the SOT-23
became that rail's terminus.

**SENSE goes to VOUT at the regulator, not past the 0R link.** "As close as
possible to the load" argues for the far side of `R306`/`R307` - but those are
TEST_PLAN 3.2 current-measurement breaks that get lifted on purpose during
bring-up, and sensing downstream would open the feedback loop the moment one
came out. The datasheet's own specifications are given for "SENSE connected to
VOUT" (p.3), so this is the characterised configuration; what it costs is IR-drop
correction across a 0 Ω link, which is nothing.

**PG is a no-connect, and that is worth a decision.** DEC-P9 makes `RAIL_PGOOD`
a wired-AND of each converter's PG through 1 k, and the only reason the 5 V rails
are absent from it is that the TPS7A20 had no PG pin. Both LDOs now have one. Two
more 1 k resistors would put all four converters on `RAIL_PGOOD` and make a dead
5 V rail visible at `D303`/`TP308`, where today it is not. **I have not done it:**
the ask was a part swap with re-derived passives, not new rail supervision, and
nothing regresses by leaving it - but it is the obvious next step and the captain
should decide. The datasheet permits the pin left open (Table 5).

**The one passive that had to change: CIN, 1 µF -> 10 µF.** Capacitor Selection
(p.17) requires COUT >= 1 µF with ESR <= 1 Ω, and then: "if greater than 1µF of
output capacitance is required, the input capacitor should be increased to match
it." COUT is 10 µF + 100 nF, kept because the datasheet says a larger COUT
improves transient response, so CIN follows to 10 µF.

C309/C312 use `CAP_MLCC_10uF_0805_20%_25V`, not the 0603 10 V part the outputs
use. They sit on the 5.5 V pre-regulator rail, and a 10 V X5R at 5.5 V DC bias
loses most of its capacitance - the wrong way to satisfy a "match COUT"
requirement. `loadcell_afe` already uses this exact part for a 10 µF on a
5 V-class rail. The wider 0805 body moved the library's Value offset 0.44 mm
into the EN feed wire; the Value anchor now lines up with the Reference above it.

**Headroom, and a question for the captain.** 5.5 V in, 5.0 V out is 500 mV.
Worst-case dropout is 325 mV at 300 mA and 600 mV at 500 mA (Table 1), so the
part cannot deliver its rated 500 mA from this rail - it does not need to, since
`+5V` draws ~115 mA and `+5VA` ~30 mA. But the regulation, noise and PSRR figures
are all specified at V<sub>IN</sub> = V<sub>OUT</sub> + 1 V, which 5.5 V does not
give, and the reason `+5V5` is 5.5 V was the TPS7A20's 6.0 V input ceiling - a
constraint the ADPL42005's 4-20 V range removes. Raising `+5V5` would recover the
specified performance on the rail that carries `REQ-FF-04`. That is U301's
feedback divider (`R303`/`R304`), so it is a real change and the captain's call;
DEC-P1 now carries the note.

Net count 262 -> 264: the two unused PG pins each become an `unconnected-(...)`
net. Components unchanged at 408. ERC 0/0.

## Item 5 - ESD stays off the AFE inputs: closed

The captain confirmed the round-2 audit's answer, so this is no longer an open
question. **`DEC-0027`** records it design-wide: the reasoning (clamp capacitance
and leakage land straight on the `REQ-FF-04` measurement, and the bridge is
ratiometric so an asymmetric load becomes a differential error), the policy it is
an instance of rather than an exception to, and the condition that would reopen
it - either connector reaching a panel, or the probes becoming field-swappable.

No schematic change. The audit table in round 2 item 3 stays the working
reference for every other interface.
