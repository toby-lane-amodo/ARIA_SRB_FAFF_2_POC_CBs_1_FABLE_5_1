# FAFF 2 CBs_1 - Schematic Review Log

Required by the `schematic-style` skill: the client's verbatim review advice lands here first,
with its resolution. Newly general rules migrate from here into the skill itself.

**Consult this log before starting schematic work.** One table per review round.

## Round 0 - skeleton (2026-09-02)

No client review yet: the schematic is a skeleton with no circuitry. This round records the
in-house instructions that already bind the schematic work, so they are not lost between rounds.

| # | Source | Point (verbatim where quoted) | Resolution |
|---|---|---|---|
| 0.1 | Captain, via firstmate | "use the Amodo KiCad library for all components… prefer existing Amodo parts; create new parts ONLY where absolutely necessary, and new parts are created in that local library (not scattered in the repo)" | Project `sym-lib-table` / `fp-lib-table` bound via `${AMODO_KICAD_LIB}`. DEC-0015; rule in `AGENTS.md` |
| 0.2 | Captain, via firstmate | New-part additions to a category file must be reported in a status line so concurrent edits can be serialised | In `AGENTS.md` under parallel block work |
| 0.3 | Captain, via firstmate | KiCad 9 only | DEC-0017 |
| 0.4 | EEE Hardware Design Standard draft | "not advisable to place test coverage on very high speed interfaces or signals" | No test points on ULPI or QSPI. DEC-0018 ruling 1; `TEST_PLAN.md §2.2` |
| 0.5 | EEE Hardware Design Standard draft | Test point type chosen per net: `TestPoint` / `TestPointHook` / `TestPointDual`; GND hooks beside signal hooks | `TEST_PLAN.md §2.1`; DEC-0018 ruling 2 |
| 0.6 | EEE Hardware Design Standard draft | Use a coaxial connector for nets you will scope or inject into repeatedly (U.FL, U.FL-to-BNC adapter in the EEE lab) | `TEST_PLAN.md §2.3`; DEC-0018 ruling 4 |
| 0.7 | `schematic-style` skill | Top sheet should be the block diagram wired with sheet pins | **Deliberate temporary deviation** — root is unwired until child sheets declare hierarchical labels. DEC-0009 |
| 0.8 | Self-check (render sweep) | Full-length sheet titles overran the A3 title-block field and clipped at the page border on `mcu` | Titles shortened to `CBs_1 - <block>`. DEC-0020 |

## Round 1 - first block review

_Not yet held. Add a table here when the first drawn blocks are reviewed._
