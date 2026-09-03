#!/usr/bin/env python3
"""Generate the DRV8323S land pattern: TI RTA0040B, WQFN-40, 6x6 mm, 0.5 mm
pitch, 4.15 mm exposed pad.

Sources, both read 2026-09-03:
  * TI drawing 4219112/A (07/2018) "RTA0040B  WQFN - 0.8 mm max height" -
    package outline, land pattern example and stencil design.  SLVSDJ3D (the
    DRV832x datasheet) omits this drawing; it was taken from the DRV8353
    datasheet, https://www.ti.com/lit/ds/symlink/drv8353.pdf pp. 98-100, and a
    copy is committed as datasheets/DRV832x_RTA0040B_package_4219112A.pdf.
  * TI drawing 4219052/A (06/2016) "RHA0040B  VQFN - 1 mm max height",
    https://www.ti.com/lit/ds/symlink/msp430g2755.pdf#page=72.

The two drawings give an identical outline and an identical land pattern -
body 6.1/5.9 square, 36X 0.5 pitch, 2X 4.5 terminal span, 40X 0.5/0.3 terminal
length, 4.15+/-0.1 exposed pad, land 40X (0.6)x(0.22) inside (5.8), stencil 9X
(1.17) on (1.37) - and differ only in package height (0.8 mm WQFN vs 1.0 mm
VQFN).  So KiCad 9's official Texas_RHA0040B footprint is a dimension-verified
base for this package, which is what the pcb-layout-style skill allows; its
perimeter pads, silkscreen, fab outline and courtyard are reproduced here.

Two deliberate departures from that base:
  * the exposed-pad stencil apertures use TI's own 9X (1.17) on (1.37) TYP
    with (R0.05) corners rather than KiCad's 1.12 on 1.38, giving TI's stated
    71% paste coverage;
  * perimeter pads stay IPC-nominal (0.875 x 0.25 on a 2.9375 row offset), a
    superset of TI's own (0.6) x (0.22) on 2.6 land.  That matches the house
    QFN footprints in Amodo.pretty, and the extra 0.375 mm of toe outside the
    body edge is what makes the joint inspectable.
"""
import uuid, os

NS = uuid.UUID("9c5b8f2e-4d6a-5f1b-9c3e-7a2d4b6e8f10")
NAME = "Texas_RTA0040B_WQFN-40-1EP_6x6mm_P0.5mm_EP4.15x4.15mm"

def uid(k):
    return str(uuid.uuid5(NS, NAME + "/" + k))

ROW = 2.9375          # pad row offset from centre
FIRST = -2.25         # first pad position along the row
PITCH = 0.5
PL, PW = 0.875, 0.25  # pad length (outward), pad width
EP = 4.15
PASTE, PASTE_PITCH = 1.17, 1.37

DESCR = (
    "Texas Instruments RTA0040B, WQFN 40 pin, 6x6 mm body, 0.5 mm pitch, "
    "4.15 mm square exposed thermal pad, pad 41. Package outline and land "
    "pattern from TI drawing 4219112/A 07/2018, read 2026-09-03 - SLVSDJ3D "
    "omits it, so it was taken from the DRV8353 data sheet pp.98-100 and "
    "committed as datasheets/DRV832x_RTA0040B_package_4219112A.pdf. That "
    "drawing and TI 4219052/A (RHA0040B) give an identical outline and land "
    "pattern and differ only in package height (0.8 mm vs 1.0 mm), so the "
    "perimeter pads, silkscreen, fab outline and courtyard are KiCad 9's "
    "dimension-verified Texas_RHA0040B footprint; exposed-pad stencil "
    "apertures are TI's own 9X (1.17) on (1.37) TYP, 71% coverage. Pin 1 is "
    "the top pad of the LEFT column, numbering anticlockwise, per SLVSDJ3D "
    "figure 6-6 (DRV8323S top view). 3D model is the 1.0 mm-tall RHA body of "
    "the same outline - 0.2 mm proud of the RTA's 0.8 mm max, conservative "
    "for clearance."
)

def pads():
    out = []
    for i in range(10):                                  # 1-10 left, downward
        out.append((str(i + 1), -ROW, FIRST + i * PITCH, PL, PW))
    for i in range(10):                                  # 11-20 bottom, rightward
        out.append((str(i + 11), FIRST + i * PITCH, ROW, PW, PL))
    for i in range(10):                                  # 21-30 right, upward
        out.append((str(i + 21), ROW, -FIRST - i * PITCH, PL, PW))
    for i in range(10):                                  # 31-40 top, leftward
        out.append((str(i + 31), -FIRST - i * PITCH, -ROW, PW, PL))
    return out

SILK = [((-3.11, -3.11), (-2.635, -3.11)), ((-3.11, -2.635), (-3.11, -3.11)),
        ((-3.11, 3.11), (-3.11, 2.635)),   ((-2.635, 3.11), (-3.11, 3.11)),
        ((2.635, -3.11), (3.11, -3.11)),   ((3.11, -3.11), (3.11, -2.635)),
        ((3.11, 2.635), (3.11, 3.11)),     ((3.11, 3.11), (2.635, 3.11))]

CRTYD = [((-3.63, -2.63), (-3.25, -2.63)), ((-3.63, 2.63), (-3.63, -2.63)),
         ((-3.25, -3.25), (-2.63, -3.25)), ((-3.25, -2.63), (-3.25, -3.25)),
         ((-3.25, 2.63), (-3.63, 2.63)),   ((-3.25, 3.25), (-3.25, 2.63)),
         ((-2.63, -3.63), (2.63, -3.63)),  ((-2.63, -3.25), (-2.63, -3.63)),
         ((-2.63, 3.25), (-3.25, 3.25)),   ((-2.63, 3.63), (-2.63, 3.25)),
         ((2.63, -3.63), (2.63, -3.25)),   ((2.63, -3.25), (3.25, -3.25)),
         ((2.63, 3.25), (2.63, 3.63)),     ((2.63, 3.63), (-2.63, 3.63)),
         ((3.25, -3.25), (3.25, -2.63)),   ((3.25, -2.63), (3.63, -2.63)),
         ((3.25, 2.63), (3.25, 3.25)),     ((3.25, 3.25), (2.63, 3.25)),
         ((3.63, -2.63), (3.63, 2.63)),    ((3.63, 2.63), (3.25, 2.63))]

L = []
A = L.append
A('(footprint "%s"' % NAME)
A('\t(version 20241229)')
A('\t(generator "pcbnew")')
A('\t(generator_version "9.0")')
A('\t(layer "F.Cu")')
A('\t(descr "%s")' % DESCR)
A('\t(tags "Texas WQFN QFN NoLead DRV8323")')

def prop(name, value, at, layer, hide, size, thick, key):
    A('\t(property "%s" "%s"' % (name, value))
    A('\t\t(at %g %g 0)' % at)
    A('\t\t(layer "%s")' % layer)
    if hide:
        A('\t\t(hide yes)')
    A('\t\t(uuid "%s")' % uid(key))
    A('\t\t(effects')
    A('\t\t\t(font')
    A('\t\t\t\t(size %g %g)' % (size, size))
    A('\t\t\t\t(thickness %g)' % thick)
    A('\t\t\t)')
    A('\t\t)')
    A('\t)')

prop("Reference", "REF**", (0, -4.4), "F.SilkS", False, 1, 0.15, "ref")
prop("Value", NAME, (0, 4.4), "F.Fab", False, 1, 0.15, "val")
prop("Datasheet", "https://www.ti.com/lit/ds/symlink/drv8323.pdf",
     (0, 0), "F.Fab", True, 1.27, 0.15, "ds")
prop("Description", "TI RTA0040B WQFN-40 6x6mm 0.5mm pitch, 4.15mm exposed pad",
     (0, 0), "F.Fab", True, 1.27, 0.15, "desc")
prop("FPLifecycle", "draft", (0, 0), "User.3", False, 1, 0.1, "life")

A('\t(attr smd)')

for (a, b) in SILK:
    A('\t(fp_line')
    A('\t\t(start %g %g)' % a)
    A('\t\t(end %g %g)' % b)
    A('\t\t(stroke')
    A('\t\t\t(width 0.12)')
    A('\t\t\t(type solid)')
    A('\t\t)')
    A('\t\t(layer "F.SilkS")')
    A('\t\t(uuid "%s")' % uid("silk %g %g %g %g" % (a + b)))
    A('\t)')

# pin 1 marker, outside the courtyard, pointing at the pin 1 pad
A('\t(fp_poly')
A('\t\t(pts')
A('\t\t\t(xy -3.64 -2.25) (xy -3.97 -2.01) (xy -3.97 -2.49)')
A('\t\t)')
A('\t\t(stroke')
A('\t\t\t(width 0.1)')
A('\t\t\t(type solid)')
A('\t\t)')
A('\t\t(fill yes)')
A('\t\t(layer "F.SilkS")')
A('\t\t(uuid "%s")' % uid("pin1 marker"))
A('\t)')

for (a, b) in CRTYD:
    A('\t(fp_line')
    A('\t\t(start %g %g)' % a)
    A('\t\t(end %g %g)' % b)
    A('\t\t(stroke')
    A('\t\t\t(width 0.05)')
    A('\t\t\t(type solid)')
    A('\t\t)')
    A('\t\t(layer "F.CrtYd")')
    A('\t\t(uuid "%s")' % uid("crtyd %g %g %g %g" % (a + b)))
    A('\t)')

# fab body outline, pin 1 corner chamfered
A('\t(fp_poly')
A('\t\t(pts')
A('\t\t\t(xy -2 -3) (xy 3 -3) (xy 3 3) (xy -3 3) (xy -3 -2)')
A('\t\t)')
A('\t\t(stroke')
A('\t\t\t(width 0.1)')
A('\t\t\t(type solid)')
A('\t\t)')
A('\t\t(fill no)')
A('\t\t(layer "F.Fab")')
A('\t\t(uuid "%s")' % uid("fab body"))
A('\t)')

A('\t(fp_text user "${REFERENCE}"')
A('\t\t(at 0 0 0)')
A('\t\t(layer "F.Fab")')
A('\t\t(uuid "%s")' % uid("fab ref"))
A('\t\t(effects')
A('\t\t\t(font')
A('\t\t\t\t(size 1 1)')
A('\t\t\t\t(thickness 0.15)')
A('\t\t\t)')
A('\t\t)')
A('\t)')

for num, x, y, sx, sy in pads():
    A('\t(pad "%s" smd roundrect' % num)
    A('\t\t(at %g %g)' % (x, y))
    A('\t\t(size %g %g)' % (sx, sy))
    A('\t\t(layers "F.Cu" "F.Mask" "F.Paste")')
    A('\t\t(roundrect_rratio 0.25)')
    A('\t\t(uuid "%s")' % uid("pad " + num))
    A('\t)')

A('\t(pad "41" smd rect')
A('\t\t(at 0 0)')
A('\t\t(size %g %g)' % (EP, EP))
A('\t\t(property pad_prop_heatsink)')
A('\t\t(layers "F.Cu" "F.Mask")')
A('\t\t(zone_connect 2)')
A('\t\t(uuid "%s")' % uid("pad 41"))
A('\t)')

for gy in (-PASTE_PITCH, 0.0, PASTE_PITCH):
    for gx in (-PASTE_PITCH, 0.0, PASTE_PITCH):
        A('\t(pad "" smd roundrect')
        A('\t\t(at %g %g)' % (gx, gy))
        A('\t\t(size %g %g)' % (PASTE, PASTE))
        A('\t\t(layers "F.Paste")')
        A('\t\t(roundrect_rratio %.7f)' % (0.05 / PASTE))
        A('\t\t(uuid "%s")' % uid("paste %g %g" % (gx, gy)))
        A('\t)')

A('\t(embedded_fonts no)')
A('\t(model "${KICAD9_3DMODEL_DIR}/Package_DFN_QFN.3dshapes/'
  'Texas_RHA0040B_VQFN-40-1EP_6x6mm_P0.5mm_EP4.15x4.15mm.step"')
A('\t\t(offset')
A('\t\t\t(xyz 0 0 0)')
A('\t\t)')
A('\t\t(scale')
A('\t\t\t(xyz 1 1 1)')
A('\t\t)')
A('\t\t(rotate')
A('\t\t\t(xyz 0 0 0)')
A('\t\t)')
A('\t)')
A(')')

dest = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..",
    "hardware", "kicad", "faff2_cbs1", "faff2.pretty", NAME + ".kicad_mod"))
with open(dest, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(L) + "\n")
print("wrote", dest)
