# Proposal: style rules to fold into `schematic-style`

**Status: proposal only. The `schematic-style` skill has not been touched.** The standing rule is
that the skill changes only with the captain's explicit approval, so this document exists to be
evaluated, edited and accepted or rejected item by item.

Everything here was established by the captain across schematic review rounds 1–4 and the
verification round on **FAFF 2 `CBs_1`**, but only rules that generalise beyond that board are
listed. Part selections, rail voltages, pin allocations and other FAFF-2 engineering decisions
are deliberately excluded — they live in `docs/DECISIONS.md` and the per-block decision files.

Each item gives:

* **Rule** — the text as it would appear in the skill: terse, imperative, checkable.
* **Origin** — where it came from. *Reference only: origins are not pushed to the skill.*
* **Status** — against the *current* skill text: **NEW**, **REFINES** (naming the rule),
  or **CONTRADICTS** (naming the rule and showing both).
* **Disposition** — the ruling, and what to do with the item.

## How to apply this document

This is the spec for the skill update. Four rules govern it:

1. **Only the Rule text goes into the skill.** Origins do not: where a rule came from is not
   relevant to someone reading the skill.
2. **A refinement is folded into the existing skill line as added detail — not added as a new
   line or a new attribute.** Where an item's Status names an existing rule, extend that rule;
   do not create a second bullet saying something adjacent.
3. **Plain designer-to-designer style throughout.** No process narration, no roles, no review
   rounds, no project names. A rule reads as an instruction to the next engineer.
4. **Anything not commented on is approved as written.**

Every item is ruled on; nothing is held.

---

## A. Placement and wiring

### 1. Four-way junctions — the ERC will not catch them

**Rule.** Never join four wires at one point. KiCad's `four_way_junction` ERC rule **defaults to
`ignore`**, so a clean ERC is not evidence: check geometrically, by counting wire endpoints that
coincide with each junction.

**Origin.** *"Never ever use a 4-way net connection."*

**Status.** **REFINES** *"Wire crossings are acceptable in moderation; 4-way junctions never."*
The prohibition is already there; what is missing is that the automated check is off by default,
which is how one survives a 0/0 ERC.

**Disposition.** **APPROVED** — as written. Fold into the named rule as added detail; do not add a new bullet.

### 2. Series elements lie along the flow

**Rule.** Place series elements — 0 Ω links, ferrite beads, series terminators, current-sense
elements — **horizontally**, in line with the left-to-right flow of the net they sit in, so power
and signal run in one direction without unnecessary corners.

**Origin.** *"Series output zero ohm links for regulators should be placed horizontally, not
vertically."* and *"Ferrite beads used for rail filtering should be placed horizontally … to keep
flow of power in one direction, without un-necessary corners."*

**Status.** **REFINES** *"No unnecessary bends: place parts so connected pin rows align and wires
run straight."* The existing rule is about wires; this one says which way the *part* goes, and
names the classes that are always in-line.

**Disposition.** **APPROVED** — as written. Fold into the named rule as added detail; do not add a new bullet.

### 3. Parallel elements stand vertically, matching their neighbours

**Rule.** A part in parallel with a column of others is drawn like them — same orientation, same
body height. A diode across a decoupling capacitor is vertical because the capacitors are.

**Origin.** *"D201 is in parallel with C204, etc, so graphically it should also be placed
vertically like C204 etc. Same for D202."*

**Status.** **REFINES** *"Paired elements align (e.g. two I2C pull-ups side by side at the same
height, supply flags level)."* Extends alignment from *pairs of the same part* to *anything in
parallel across the same net*, including mixed part types.

**Disposition.** **APPROVED** — as written. Fold into the named rule as added detail; do not add a new bullet.

### 4. Parallel parts share one ground-flag height

**Rule.** Every part in a parallel row puts its GND flag at the **same y**. Four flags on four
heights draws as a staircase. Where a row already agrees, the odd one out joins it; otherwise the
right height is the one that makes the bottom stub match the top stub. A local fix that solves a
collision by dropping one flag out of its row is not a fix.

**Origin.** *"It would be nice if GND connections for parallel components are vertically aligned.
R206 and C207 GND flags should be at the same vertical height."*, escalated in round 4 to
*"Parallel components share ONE GND-flag height — sweep ALL sets of parallel capacitors and
parallel parts across the design"*, with `C1113` named as the good case and `C1101`/`C1102` as the
bad one.

**Status.** **REFINES** the same *"Paired elements align … supply flags level"* clause. What is new
is that it is a **design-wide sweep**, not a local nicety, and that it overrides local collision
fixes. Worth pairing with a detector: group two-terminal parts by upper net and body y, split into
visual runs, and report any run whose flags disagree. Keep the thresholds in the tool rather than
in prose — what counts as "one row" is a judgement the tool encodes, not a number to memorise.

**Disposition.** **APPROVED** — as written. Fold into the named rule as added detail; do not add a new bullet. The row-detection thresholds stay in the tool, not in the skill text.

### 5. Potential dividers stack vertically

**Rule.** Draw a potential divider as one vertical column: top resistor, tap, bottom resistor,
ground, all on the same x.

**Origin.** *"Where you have a potential divider … make sure they are vertically aligned."*

**Status.** **NEW.** The skill covers even spacing and alignment of two-terminal parts but says
nothing about the divider as a shape.

**Disposition.** **APPROVED** — as written.

### 6. Power LEDs are vertical

**Rule.** Power-indicator LEDs and their series resistors are drawn vertically, in a column from
the rail to ground.

**Origin.** *"Power LEDs should also ideally be placed vertically."*

**Status.** **NEW.**

**Disposition.** **APPROVED** — as written.

### 7. Connectors face their wiring

**Rule.** Mirror or rotate a connector so its pins emerge on the side its wires leave towards.
Wires must never have to route around a connector body to reach the circuit.

**Origin.** *"Mirror the input power connector so that the pins come out left to right, and wires
don't have to route around its body."*

**Status.** **NEW**, and it interacts with the symbol rule below — see item 22. Note the mechanical
trap that comes with it: on a `(mirror y)` symbol, `(justify left)` renders text **leftward**, so a
mirrored connector's reference and value can run off the page while the file still reads as
left-justified.

**Disposition.** **APPROVED** — as written.

### 8. GND symbols always point down, and are never mirrored

**Rule.** A ground symbol points down. Never rotate one, never mirror one, and never make a
pre-rotated or mirrored ground variant. Where a dense pin row leaves no vertical room for one
ground per pin, stub every ground pin to a single vertical rail and terminate that rail in **one**
downward GND below the block; split the rail at every stub so each landing is a real tee.

**Origin.** *"GND connections are upside down. You must never ever do this."*

**Status.** **REFINES** *"GND symbols always face down — never rotate a ground, and never make a
pre-rotated ground variant."* The addition is the explicit word **mirrored**: a mirrored ground
draws identically to an unmirrored one in some orientations, so "never rotate" does not cover it.

**Disposition.** **APPROVED** — as written. Fold into the named rule as added detail; do not add a new bullet.

### 9. A body never straddles a wire, and a power symbol's arrow never grazes one

**Rule.** No component body may sit across a wire. Extend this to power symbols: a GND arrow's tip
or a rail arrow's tip touching a wire it does not connect to reads as a connection and is a defect,
even at zero overlap depth. Check by requiring the wire to run inside the body's outline for a real
distance (≳0.6 mm) rather than by looking for area overlap, and excuse only wires that land on that
symbol's own pins.

**Origin.** Round 3, from the captain's screenshots of `power_rails`; nine further instances were
then found design-wide by the same test.

**Status.** **REFINES** *"a component body must never straddle a wire."* The existing rule is
stated for component bodies; the failure in practice is power-symbol arrows, whose bounding boxes
are mostly empty triangle, so an area test finds nothing and a clearance test finds false hits
everywhere.

**Disposition.** **APPROVED** — as written. Fold into the named rule as added detail; do not add a new bullet.

---

## B. Text, labels and clearance

### 10. Power-symbol net names: one placement, everywhere

**Rule.** A power symbol's net name sits **directly above or below the symbol, centred on it, with
no sideways offset, close** — above a rail arrow, below a ground (the mirror is deliberate: "above"
a ground is where its wire arrives). The label is **pinned**: where it collides, move the *symbol*
along its own stub, move the neighbouring part or note, or grow the block box — never nudge the
label sideways to dodge.

**Origin.** *"Power labels are missing on most of the power flags on the design"*, then the round-2
ruling fixing the placement.

**Status.** **REFINES** *"power nets use power symbols with their text always visible."* Visibility
is in the skill; the placement discipline, and above all the "the label does not move, the world
moves" rule, are not.

**Disposition.** **APPROVED** — as written. Fold into the named rule as added detail; do not add a new bullet.

### 11. Sheet entry and exit flags read back over their own wire, in clean columns

**Rule.** Hierarchical labels at a sheet or block boundary are right-justified and read back over
the wire they name, aligned in a column. Text may lie over its **own** net — that is what "the wire
must extend under the entire label" requires — but never over a foreign wire, a body or another
label. Do not mix justifications within a column.

**Origin.** *"Same as other sheet review for sheet entry / exit labels justification. This text
should not overlap the wires."*, and round 4's `VBUS_MON`, which was the only label on its sheet
with the opposite justification.

**Status.** **REFINES** *"Net labels sit over their wire … At a wire end, anchor the label there
right-justified (angle 180 + justify right bottom) so the text reads back over the wire."*
**It also resolves an ambiguity that reads as a contradiction.** Taken literally, "this text should
not overlap the wires" forbids what the skill requires. The reconciliation is *electrical*: text
over its own **node** — the wire it labels and every branch of that node — is correct; text over
any other conductor is a defect. A checker needs the node, not just the one segment under the
anchor, or every branch dropping off a labelled wire reports as an overlap.

**Disposition.** **APPROVED** — as written. Fold into the named rule as added detail; do not add a new bullet.

### 12. Text clearance is measured against wires, borders, bodies and other text

**Rule.** Sweep text against **every** neighbour class: wires, block-box borders, symbol outlines
including the field's own symbol, notes, net labels, and other fields. Require real **clearance**,
not merely the absence of overlap — once both stroke widths are drawn, text a few tenths of a
millimetre off a wire reads as touching. Calibrate the margin to the library in use rather than
fixing a number: sweep at increasing margins, find where the finding count jumps because the
library's own default field offsets have started reporting, and set the margin just below that.

**Origin.** *"Text overlap around C1101"*, *"J601 has text overlapping component body. Check all
the schematic for instance of this and fix if required."*, and round 3: *"This all needs fixing
before we can proceed."*

**Status.** **REFINES** *"Nothing overlaps, ever: no text over components, wires, or other text."*
The rule exists; what is missing is that it must be *measured*, that "no overlap" is a weaker bar
than "clearance", and that a field must be compared against its **own** symbol's outline — the
commonest single miss.

**Disposition.** **APPROVED** — as written. Fold into the named rule as added detail; do not add a new bullet. The clearance margin is left as a calibration method rather than a number: a fixed figure is only right for the library it was measured against, and a library that places its fields tighter would see normal house placement reported everywhere. The method — sweep upwards, find where the count jumps, sit just below it — transfers; the number does not.

### 13. Character advance and text box geometry

**Rule.** Do not trust a remembered figure for character width — measure it on a render before
relying on it. Whatever the figure, scale it by the field's own font size: block titles are
typically bold and half again the default size, so a box computed at the default size comes back a
third too narrow. A field or label justified `bottom` puts its glyphs **above** the
anchor and one justified `top` puts them below; centring everything vertically hides
reference-over-value collisions completely. Text grows leftward when `justify right` **XOR** symbol
at 180° **XOR** mirrored — but a *label* takes no 180° flip, so its growth is justify-driven alone.

**Origin.** Measured off renders during rounds 1–4, each figure confirmed against at least one
render before being trusted.

**Status.** **CONTRADICTS** *"budget the rendered length of every net label (~1.06 mm per character
at 1.27 size)"*.
Current skill: `~1.06 mm per character`.
Proposed: `~1.19 mm per character at size 1.27, scaled by the field's own font size`.
On a 15-character label that is 1.95 mm of difference — enough to pass a real collision.

**Disposition.** **APPROVED in the safer form.** The rule now says to measure the character advance on a render rather than quoting a figure, so the skill carries no second number to go stale. The font-size scaling and the justify/growth geometry are exact and stay as written. Fold into the named rule as added detail; do not add a new bullet.

### 14. A graphical line must never be confusable with a wire

**Rule.** Keep block-box borders, notes' leader lines and any other graphic clear of the paths
wires take. A graphic running along or through a wire's route, or a wire jogging along a border,
must be moved: the reader cannot tell them apart at review zoom.

**Origin.** *"wire obscured by a graphical line"*.

**Status.** **NEW.** The skill governs bounding boxes' appearance ("outline only — never colour or
fill") but not their collision with wiring.

**Disposition.** **APPROVED** — as written.

### 15. Block boxes cross nothing

**Rule.** A block bounding box must not cross a component body, a sheet boundary, or another block
box. Its top edge must be inside the drawing area — on a KiCad frame the drawing area starts inside the
outer border, below the ruler band, not at the border itself.

**Origin.** *"`temp_sense` content crosses the top sheet boundary"*, *"The `+5VA` bridge-excitation
label/wiring falls outside the sheet boundary at the top"*, and the verification round, where a
hand-dragged border stopped in the middle of the IC the block is named after.

**Status.** **REFINES** *"Size the box to the block's real extent, then re-check the title still
fits inside it."* Sizing is covered; crossing a body or the frame is not.

**Disposition.** **APPROVED — checkable half only.** The rule keeps *a box crosses nothing*; the sentence about growing a box past the part it names is removed, because inferring a box's intent is a judgement, not a check. Fold into the named rule as added detail; do not add a new bullet.

---

## C. Symbols, designators and libraries

### 16. Rotate the part on the schematic; keep its text horizontal

**Rule.** Rotating a part on the schematic is acceptable and normal. Needing an orientation is not
a reason to make a library variant — use the standard symbol and turn it. Keep the reference and
value rendering **horizontal**: a property's `(at x y angle)` angle is *relative to the symbol*, so
compensate the field angles — 270 on a symbol at 90, 90 on one at 270 — or the text comes out
sideways. Verify it in a render.

**Origin.** *"`R1128`-`R1133` use a different 100R symbol — why, and unify"*, ruled *"unify onto the
standard 100R symbol regardless"*, then settled directly: *"It is perfectly acceptable to rotate a
part in a schematic. Needing to rotate a part should not require a new library variant to be
made."*

**Status.** **CONTRADICTS** *"Orientation variants are pre-rotated in the library, never
instance-rotated — this keeps reference/value text horizontal. If a part must sit horizontally
(in-line series resistor, rotated FET), make a `_H`/pre-rotated local variant."*
Current skill: pre-rotated library variant; never rotate the instance.
Proposed: rotate the instance; no variant is needed for orientation. The *purpose* of the old rule
— reference and value text rendering horizontal — is kept, and the Rule above says how to achieve
it while rotating.

**Disposition.** **APPROVED — this one REPLACES the text it contradicts.** It is the single
exception to folding a change in as added detail: the existing sentence says the opposite, so it
comes out and the Rule above goes in its place. The `_H`/pre-rotated-variant sentence goes with it.

### 17. Reference-designator prefixes follow the part's function

**Rule.** The prefix says what the part is, not where it sits in the circuit. A coaxial or board
connector is `J` even if it sits in a filter chain; `FL` is a filter. When in doubt, take the
library symbol's own default prefix — overriding it on the instance is how these diverge.

**Origin.** *"`FL501`/`FL502` are connectors — re-designate as `J`"*.

**Status.** **NEW.**

**Disposition.** **APPROVED** — as written.

### 18. Designators are unique across the whole project, and per-sheet ranges keep them so

**Rule.** Fix a designator scheme for the project and hold to it — sequential through the
schematic, or per-sheet ranges from the page number — and apply it to power symbols and power
flags as well as parts. Whichever scheme is used, designators must be unique across the whole
project: two sheets both starting at `U1` do **not** raise an ERC error, they silently merge into
one component at netlist time.

**Origin.** Established during integration on this project; the failure mode was then demonstrated
for real in the verification round (item 26).

**Status.** **NEW.**

**Disposition.** **APPROVED as designer discretion.** Either scheme is fine — sequential through the schematic, or page number × 100 — and which one suits depends on the project's setup defaults. The rule now says *fix a scheme and hold to it*. What is not discretionary is uniqueness across the project, and that the ERC will not catch a clash.

---

## D. Test and debug provision

### 19. Test coverage lives on the page it covers

**Rule.** Test points, probe headers, scope hooks and debug connectors belong to the block whose
nets they observe. Do not create a test-and-debug sheet. If you find a sheet that already contains
test coverage, do not collapse it without asking the designer first.

**Origin.** *"Can all of the test_debug page be implemented on the relevant circuits page?"*

**Status.** **NEW.** The skill has a related but different rule about *what form* debug access
takes; it says nothing about *which sheet* it lives on.

**Disposition.** **APPROVED**, with the addition now carried in the rule: if a sheet already contains test coverage, do not collapse it without asking the designer first. The reservation I raised about large designs is withdrawn — the rule globalises as written.

### 20. One keyed header beats a row of digital test points

**Rule.** For a digital interface, fit the house keyed logic-analyser header rather than individual
test points per signal — one plug, one ground reference, no clip slipping off a series terminator.
Tap the bus on the controller side of any series terminator or isolation link so the header still
sees the bus with a link lifted. Keep the ground hooks the probe leads clip to.

**Origin.** *"Rather than using individual test points for the digital interface, can you use the
amodokicadlib header for the logic analyser?"*

**Status.** **REFINES** *"Bring-up/debug access goes on simple populate-if-needed connectors (DNP
by default), not bare test points."* Same direction; this names the specific case, the house part
and the "tap which side of the terminator" detail.

**Disposition.** **APPROVED** — as written. Fold into the named rule as added detail; do not add a new bullet.

### 21. Dual scope points at regulator outputs

**Rule.** Every regulator output gets a **dual** test point — signal pad and ground pad adjacent —
so a scope probe and its ground clip land together.

**Origin.** *"At the output of all regulators, use a dual test point, so that I can hook up an
oscilloscope probe."*

**Status.** **NEW.**

**Disposition.** **APPROVED** — as written.

### 22. No test coverage on feedback nodes or high-speed signals

**Rule.** Never place a test point on a PSU feedback node — the stub is in the control loop. Do not
place test coverage on very high-speed interfaces; probe the same information somewhere it costs
nothing, such as a receiver's single-ended output rather than the terminated differential pair.

**Origin.** *"Also, do not place test coverage on PSU feedback nodes."* and, earlier, *"not
advisable to place test coverage on very high speed interfaces or signals"*.

**Status.** **NEW.**

**Disposition.** **APPROVED** — as written.

### 23. Test-point silkscreen names

**Rule.** Every test point carries a short name saying what it measures, taken from the net it
actually lands on, **under 6 characters**. In the rare case where shortening a net's name that far
would hide its meaning, a longer name is acceptable.

**Origin.** *"Across the schematic, can you label all of the TPs with some text for what they
measure … keep them as short as possible (< 6 characters)"*.

**Status.** **NEW.**

**Disposition.** **APPROVED**, with the exception now carried in the rule: where shortening a net's name below six characters would hide its meaning, a longer name is acceptable.

---

## E. Verification

### 24. `kicad-cli` exit codes and the silent-pass traps

**Rule.** Three traps, all of which produce a clean-looking result from a broken schematic:

* `kicad-cli sch erc` **exits 0 even when it finds violations** unless
  `--exit-code-violations` is given. Always pass it, and always read the report.
* `kicad-cli sch erc` prints **"Found 0 violations" when the sheet failed to load** — the
  "Failed to load schematic" line goes to **stderr**. Never accept a clean ERC without also
  checking stderr and the component count from a netlist export.
* **An invalid token truncates a sheet silently.** KiCad stops parsing at the bad token, keeps
  everything before it and drops the rest, with no error, and the plotter still renders what
  survived. The tell is a component count well below what the sheet contains.

**Origin.** All three hit during this review; the third cost a sheet truncated to 349 of 409
components behind a "clean" render.

**Status.** **NEW** as a group. The skill's verification list assumes ERC output is trustworthy.

**Disposition.** **APPROVED** — as written.

### 25. Node-set invariance is the proof for geometry work

**Rule.** For any pure-geometry rework, compare the **multiset** of per-net node sets — each net as
a set of `(refdes, pin)` — before and after. Net *names* may legitimately change; membership may
not. "ERC is still clean" is not a substitute: ERC passes happily on a wire that merged two nets.

**Origin.** Used throughout; it caught a real short (two gate nets merged by collinear stubs) and a
real disconnection (two resistors moved without their ground flag) that ERC alone did not localise.

**Status.** **REFINES** *"Pure-geometry reworks proven safe by comparing per-net node sets of
before/after netlists (names may change; membership may not)."* Already present and correct; the
addition is **multiset** — comparing name-keyed dictionaries reports every renamed net as a
difference and buries the real one.

**Disposition.** **APPROVED** — as written. Fold into the named rule as added detail; do not add a new bullet.

### 26. Annotation is not checked by ERC — check it at the netlist

**Rule.** An unannotated part (`J?`, `R?`) passes ERC with **zero violations**. Two of them merge
into a **single netlist component** carrying duplicated pin numbers and only one part's value and
footprint — so a real part silently vanishes from the BOM and its nets land on the wrong footprint.
The check is the netlist export, which prints **"schematic has annotation errors"**, plus a
component-count comparison. To repair, set the specific references back rather than running a blind
re-annotate, which renumbers unrelated parts.

**Origin.** The verification round: two connectors on different sheets lost their designators during
manual editing and merged into one 17-node component.

**Status.** **NEW**, and the sharpest of these: it is a defect class that every automated check in
the current skill's list passes.

**Disposition.** **APPROVED** — as written.

### 27. A reference designator lives in two places

**Rule.** A symbol's designator is stored both in its `Reference` property and in its
`(instances … (reference …))` entry. A sheet where the two disagree loads without complaint and
exports the **instance** value. Change both together.

**Origin.** Found while repairing item 26.

**Status.** **NEW.**

**Disposition.** **APPROVED** — as written.

### 28. Renaming a net is a sweep, not an edit

**Rule.** When a net's name changes, sweep every place the old name appears: the label, any power
symbol, test-point silkscreen names, title-block comments, sheet notes, block notes and the
project documentation. A net whose name disagrees with what the drawing says about it is worse than
either name alone.

**Origin.** *"You did not update the other documentation on the power_rails sheet for the 6V change!
Test point and net label are all still wrong."*

**Status.** **NEW.**

**Disposition.** **APPROVED** — as written.

### 29. The render is the last word, and a checker miss is a checker bug

**Rule.** After every automated sweep, render the changed areas and look. When a render disagrees
with a checker, the checker is wrong: fix the checker, then re-sweep the whole design with it — the
same blind spot is almost never in one place only.

**Origin.** The skill already says this; this round proved it five times, each time finding a whole
class rather than an instance.

**Status.** **REFINES** *"treat a checker miss that a render reveals as a checker bug to fix."*
The addition is the second half: **re-sweep design-wide after fixing the checker.** Each of the five
blind spots found this round turned single-figure finding counts into double-figure ones.

**Disposition.** **APPROVED** — as written. Fold into the named rule as added detail; do not add a new bullet.

---

## F. Tooling practice

### 30. Never infer free space from a partial dump

**Rule.** Before placing anything, list **everything** the sheet draws inside the target rectangle —
wires, bodies, fields, labels, notes, borders. A partial wire dump is how new parts land collinear
with existing nets.

**Origin.** Round 1: capacitor stubs placed into a band believed empty landed collinear with two
gate verticals and shorted them; ERC reported the short two sheets away.

**Status.** **NEW.**

**Disposition.** **APPROVED** — as written.

### 31. A re-runnable edit script pins its base commit

**Rule.** A script that rebuilds sheets from git must name an explicit **base commit**, not `HEAD`.
Rebuilding from `HEAD` works exactly once: after the script's own commit lands, `HEAD` already
contains its edits and a re-run double-applies them. After any manual editing, such a script must
not be re-run until its base is re-pinned — it would overwrite the manual work.

**Origin.** Hit during round 3; stated as a hand-over warning before the captain took the helm.

**Status.** **NEW.**

**Disposition.** **APPROVED** — as written.

### 32. Edit primitives assert that they changed something

**Rule.** Every programmatic edit asserts it matched. `str.replace` says nothing when it matches
nothing, so a "successful" run can have done none of its edits.

**Origin.** Round 3, where five of six edits silently did nothing behind a success message.

**Status.** **NEW.**

**Disposition.** **APPROVED** — as written.

### 33. Multi-unit parts are keyed by symbol uuid, not by refdes

**Rule.** A multi-unit part has one `Reference` field per unit under one refdes. Anything that walks
fields must key them by the symbol's **uuid**; keying by refdes collapses every unit onto one point.

**Origin.** Round 3, which stacked all five units' references of a quad receiver on a single point.

**Status.** **NEW.**

**Disposition.** **APPROVED** — as written.

---

## G. Review surface

### 34. The design is reviewed in the KiCad files, never in an export

**Rule.** Never produce, commit or hand over a review PDF. An engineer reviews the KiCad files
themselves. An export is a snapshot: it goes stale the moment anyone saves, it cannot be probed,
cross-probed or netlist-checked, and reviewing it invites comments against a drawing that no longer
matches the design. Renders are your own self-check — export them to a scratchpad, look at them,
and leave them there; they are not a deliverable and they do not enter the repository.

**Origin.** *"The engineer should always review the KiCad files, and not a pdf. Do not generate
one."*

**Status.** **REFINES** *"Never produce or commit review PDFs — the client reviews in the KiCad
GUI."* The stance is already the skill's; what is added is the reason, which is what makes it
stick, and the explicit permission for scratchpad renders so the rule is not read as forbidding
looking at your own work.

**Disposition.** **APPROVED** — as written, and the stance stays **absolute**: no per-project
deviation. Fold into the named rule as added detail; do not add a new bullet.

---

## Rulings on the flagged items

I flagged seven items as ones I would not globalise without a decision. All seven are now ruled on;
the rulings are carried in the items themselves, and repeated here so the reasoning is in one
place.

| # | Item | Ruling |
|---|---|---|
| 1 | 16 — instance rotation vs pre-rotated variants | **Ruled: rotate the part.** *"It is perfectly acceptable to rotate a part in a schematic. Needing to rotate a part should not require a new library variant to be made."* The item now **replaces** the never-instance-rotate text rather than folding into it, keeping that rule's purpose — horizontal reference and value — as the condition on rotating. |
| 2 | 13 — character advance | **Use the safer version.** The rule now says to measure it on a render rather than quoting a number. |
| 3 | 12 — the clearance margin | **Left to my judgement; decided: no fixed number.** The rule gives a calibration method instead — sweep at increasing margins, find where the finding count jumps because the library's own field offsets have started reporting, sit just below that. A number measured against one library is wrong for the next one; the method is not. |
| 4 | 19 — test coverage on its own sheet | **Disagreed with my reservation: test coverage goes on the sheet.** The rule globalises as written and my large-design caveat is withdrawn. The one addition is that an existing sheet carrying test coverage is not collapsed without asking the designer first. |
| 5 | 15 — block boxes | **As proposed: the checkable half only.** "A box crosses nothing" stays; inferring what a box was meant to enclose does not. |
| 6 | Review PDFs | **Ruled: no PDF, ever.** The skill's never-commit stance stays absolute, and gains the principle above as item 34. In this repository the committed PDF has been deleted and the decision that authorised it is superseded. |
| 7 | 4 — row-detection thresholds | **Approved as proposed.** The numbers live in the tool; the skill states the rule. |

---

## Summary for the skill update

* **34 items, all approved.** Nothing is held.
* **Refinements are folded into the named existing rule as added detail** — they do not become new
  bullets. Items 1, 2, 3, 4, 8, 9, 10, 11, 12, 15, 20, 25, 29 and 34 name the rule they extend, and
  item 13 amends a figure inside an existing line in the same way.
* **One item replaces rather than extends: item 16.** The existing "never instance-rotated"
  sentence, and the `_H`/pre-rotated-variant sentence with it, come out; the Rule in item 16 goes
  in their place. That rule's purpose — reference and value rendering horizontal — is preserved as
  the condition on rotating.
* **Origins are not pushed.** They exist in this document only.
* **The Rule text is the only text that transfers**, and it is already written in plain
  designer-to-designer style: no process narration, no roles, no review rounds, no project names.
