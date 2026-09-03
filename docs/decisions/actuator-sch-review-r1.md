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
