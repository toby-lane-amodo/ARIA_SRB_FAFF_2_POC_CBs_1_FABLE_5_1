# CubeMX

`ARIA_SRB_FAFF_2_POC_CBs_1.ioc` is the STM32CubeMX starting point from the captain, and is
**the authority for the MCU part and every MCU-side pin assignment and net name** (DEC-0013).
Pin allocations are quoted in `docs/ARCHITECTURE.md §3.2` so you need not open CubeMX to
draw a block; if a block needs a pin that is not there, change the `.ioc` first and re-commit it.
