from common import generate

PROMPT = """Create a 3:2 landscape illustration for a portfolio section about a policy profile for Croissant, the dataset descriptor. The point of the picture: a dataset carries its own written conditions, a gate decides every request from those conditions alone, and every decision - permit or refuse - leaves a printed record.

HERO (centre-left, rendered object): a closed archival data case in matte brushed aluminium with rounded corners and two latches, sitting on a pale surface. A small engraved plate on its front reads "dataset". Tied to its handle with a thin red cord hangs a stiff white card tag, the descriptor. On the tag, printed in small slab-serif type, a heading "conditions" and below it exactly five short rounded chips in a column, each one word: "min", "max", "in", "equals", "present". Nothing else is written on the tag.

SECOND OBJECT (centre-right): one waist-high matte brushed-steel turnstile beside the case, with a small engraved plate "policy gate". Its arm is DOWN and carries a thin red accent stripe. In front of it sits one small plain white rounded disc, a request token, with no text, stopped by the arm.

THIRD OBJECT (right, in front of the turnstile): a short strip of white thermal-paper receipt curling out of a slot in the turnstile's side, the decision record. Printed on it in small monospace-like slab type, exactly these four lines and nothing more:
"verdict: REFUSE"
"class: CONDITION_VIOLATED"
"descriptor version"
"every condition checked"
The word REFUSE is the only red text on the receipt.

FLOATING ANNOTATION (thin and light): one thin slate leader line from the tag to a small white chip above it that reads "decided from the descriptor alone". One small white chip at the upper right with two lines: "+0.0 microseconds warm" and "+11.7 microseconds cold, per decision".

LOWER BAND (full width, white panel with hairline border and a thin red rule along its top edge): one line of slab-serif text: "Written conditions, decided and recorded either way."

Do not draw a croissant or any pastry or food, any bread, any human, any hand, any padlock, any arrow chain between boxes, any second turnstile, any extra chips or numbers beyond those given."""

generate(PROMPT, "croissant-policy-profile.png")
