from common import generate

PROMPT = """Create a 3:2 landscape illustration of a live perception stack in which every camera frame receives a recorded decision: run the vision model, reuse the earlier result, or report no perception. It is the architecture of a working system, drawn as physical objects on one pale surface, read left to right.

HERO OBJECTS (rendered, left to right on one pale matte surface):
1. LEFT: a compact automotive front camera module in matte black with a glass lens, on a small windshield bracket. From it a translucent film strip of five small road-scene frames (a city street with cars, seen from a car) curves to the right, toward the centre.
2. CENTRE, the largest object: a precision sorting gate in brushed steel, like a laboratory sample sorter, where the film strip enters and leaves along TWO lanes. The UPPER lane runs into a matte dark-grey GPU accelerator card with a heatsink, engraved "gated model". The LOWER lane bypasses the card; the frame on it carries a small white tag reading "earlier result reused". A small engraved plate on the gate reads "admission". The gate is a closed, solid object: draw no internal parts, dials, formulas or rules on it.
3. ABOVE THE GATE, smaller: two small detector modules watching the film strip. The left one, a small light module, is engraved "descriptor channel"; the right one, a different shape (a rounded module with a second lens), is engraved "independent observer".
4. RIGHT, upper: a slim rendered car instrument-cluster display panel. On its screen, three short lines in slab serif: "Vehicle.ADAS.AgenticVision", "Decision: REUSE", "PerceptionAge: 800 ms". A small chip beside it reads "VSS overlay, read-only over VISS".
5. RIGHT, lower: a closed matte strongbox with a stack of white paper records going into a slot on top; a small engraved plate reads "decision ledger".
6. Along the bottom edge of the surface, under all objects, a thin brushed-steel rail engraved "ROS 2" connects the camera, the gate, the display and the strongbox.

FLOATING ANNOTATION (thin slate leader lines, small white chips, exactly these three chips and no others):
- chip near the gate, with a thin red accent rule on its left edge, two lines: "900 of 900 decisions" and "reproduced by replay"
- chip near the GPU card: "model down 15 s: no stale results"
- chip near the display: "86 ms median per decision"

LOWER BAND (full width, white panel with hairline border and a thin red rule along its top edge): one line of slab-serif text: "Every frame gets a recorded decision. None is a guess."

The red accent appears only on the band's top rule and the one chip's rule. Spell every label exactly as given. Do not draw: any arrow chain between boxes, any flowchart, any formula, threshold, equation or rule text, any steering wheel, speedometer needle, speed value or vehicle signal other than the three display lines given, any person or hand, any vendor or car-maker logo, any robot, any cloud icon, any extra chips, numbers or words beyond those given."""

generate(PROMPT, "agentic-vision-stack.png")
