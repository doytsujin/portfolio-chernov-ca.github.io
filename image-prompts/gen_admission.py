from common import generate

PROMPT = """Create a 3:2 landscape illustration for a portfolio section about a per-task admission gate in front of a real bioinformatics pipeline. The point of the picture: before each pipeline task runs, a gate decides from the dataset's descriptor whether it may run; one task is ADMITTED and runs, the next is REFUSED and never starts, and both decisions leave a printed record.

HERO (rendered objects, left to right on one pale benchtop): a short matte white laboratory conveyor running left to right, carrying small clear sample tubes with white caps (sequencing reads), no text on the tubes. Along the conveyor stand TWO waist-high matte brushed-steel turnstiles, one behind the other, each with a small engraved plate:
- the LEFT turnstile plate reads "FASTQC". Its arm is UP (plain steel, no red), and one sample tube has already passed through it and sits beyond it on the conveyor. This task was admitted.
- the RIGHT turnstile plate reads "SEQTK_TRIM". Its arm is DOWN and carries a thin red accent stripe; a sample tube waits in front of it and has NOT passed. This task was refused.
The left one admits, the right one refuses - do not swap them.

RECORDS: from a slot in the side of EACH turnstile curls a short strip of white thermal-paper receipt.
- Left receipt, exactly two lines: "verdict: PERMIT" and "task: FASTQC". No red on it.
- Right receipt, exactly three lines: "verdict: REFUSE", "class: CONDITION_VIOLATED", "minReadLength 10, needs at least 20". The word REFUSE is the only red text.

FLOATING ANNOTATION (thin and light): one small white chip above the turnstiles, connected by a thin slate leader line to the right turnstile, reading "runs before the task script". One small white chip at the upper right with two lines: "119 microseconds median" and "210 decisions". One small white chip at the upper left reading "SEQTK_TRIM ran 0 of 30 times".

LOWER BAND (full width, white panel with hairline border and a thin red rule along its top edge): one line of slab-serif text: "When the gate refuses, the tool never runs."

Do not draw any DNA double helix, any human, any hand, any cloud or cloud-provider icon, any whale or container ship, any arrow chain between boxes, any third turnstile, any extra chips, numbers or words beyond those given."""

generate(PROMPT, "per-task-admission-control.png")
