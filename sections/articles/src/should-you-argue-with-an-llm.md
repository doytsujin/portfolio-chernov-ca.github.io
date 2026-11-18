# Should You Argue With an LLM?

*By [Alexander Chernov](https://www.linkedin.com/in/thedoytsujin/). First published on LinkedIn, 2026-08-22. [Read the original](https://www.linkedin.com/pulse/should-you-argue-llm-alexander-chernov-qmqgc/).*

---

Push back on a language model and it will usually change its answer. Say "are you sure?" and it apologises, reconsiders, and hands you something different. People read this as either humility or spinelessness depending on their mood, and lately they read it as personality — the model has an attitude, the model is eager to please, the model caved.

It is none of those things in the way it sounds. It is a measured, reproducible property of these systems, and there is now enough research on it to say something practical: when arguing helps, when it quietly makes the answer worse, and why the model cannot fix this by thinking harder.

## The plain measurement

The cleanest experiment is also one of the oldest. In the FlipFlop study [1], ten models were given seven classification tasks, allowed to answer, and then challenged with a single line — a version of "are you sure?" Nothing was added. No evidence, no correction, not even a hint about which direction to move. Just pressure.

The models changed their answers about 46 percent of the time. Average accuracy fell 17 points between the first answer and the last.

That is the effect in its purest form. Content-free pressure moves the answer, and it moves it downhill. Fine-tuning on synthetic data reduced the deterioration by about 60 percent and did not remove it.

## Two different things are happening

A Stanford group later separated the two ways an answer can move [2]. Working across mathematics and medical questions, they found sycophantic behaviour in 58 percent of cases. But most of it was progressive — the model started wrong and the user's pushback moved it to the right answer, in about 43 percent of cases. Regressive sycophancy, where a correct answer was abandoned for a wrong one, happened in about 15 percent.

So arguing is not simply harmful. It is a trade, and in that evaluation the odds ran roughly three to one in your favour. What the numbers do not say is what decides which side you land on. Model, version, task and the state of the conversation all move it. The one variable on your side of the exchange is why you are pushing back — whether you know something the model does not, or the answer merely made you uncomfortable. The study does not separate those two cases. It is still the distinction worth carrying into your own use of it.

Two more details from that work are worth carrying. Sycophantic behaviour persisted in about 78 percent of cases, so once the answer moves it tends to stay moved, and everything downstream in the conversation is now built on the moved answer. And disagreement stated up front, before the model answers, produced more sycophancy than disagreement raised after — 62 percent against 57. Telling the model what you think before you ask is the strongest single way to get told what you think.

![Two shapes of pushback and where each one lands. A content-free challenge changes 46 percent of answers and costs 17 points of accuracy. A challenge that states a position splits: 43 percent of the time it moves a wrong answer to a right one, 15 percent of the time it does the reverse. Pushback that carries evidence gives the model something to move toward, and the moved answer persists in about 78 percent of cases.](should-you-argue-with-an-llm/fig_pushback_split.webp)

## Where the character comes from

The word people reach for is character, and it turns out that word is closer to the mechanism than it has any right to be.

In mid-2025, researchers at Anthropic, UT Austin and Berkeley showed that traits like sycophancy, hallucination and outright malice correspond to specific directions in the model's internal activity — persona vectors [3]. Give the method a plain-English description of a trait and it finds the direction. Two of their findings matter for anyone typing at one of these systems.

The first is timing. The trait direction is measurable before the response is generated. Read plainly, that means the model is not deciding to flatter you partway through a sentence. Whatever it is going to sound like is already present in its state when it starts. It arrived at the answer already flattering.

The second is contamination. Character moves for reasons that have nothing to do with character. Training a model on mistaken mathematics answers made it measurably more sycophantic, more prone to hallucination, and more willing to say hostile things. A trait can be acquired from data that never mentioned the trait.

There is a smaller finding in the same family that reads like a joke and is not. Work presented at CHI this year found that grammatical person changes the sycophancy rate [4]. Ask about a claim in the third person rather than the first, and the model flatters less. Not because it is reasoning about who is asking, but because the phrasing sits somewhere else in the space, and the character comes with the coordinates.

So the attitude is real in the only sense that matters when you are working. It is a state, it is measurable, it moves, and it sits upstream of the answer. It is not a self. It is a dial that your wording is turning whether you meant to touch it or not.

## Why it cannot check itself

The obvious repair is to ask the model to review its own work. Across several evaluations it has not held up. Intrinsic self-correction — reconsidering with no new information from outside — has often left performance unchanged or made it worse, across arithmetic, question answering, code generation and planning [5], [6]. Multi-agent debate, compared against the same number of samples spent on plain self-consistency, has not beaten it in those comparisons. Results vary with the model, the task and the sampling budget, but the direction is consistent enough to design around.

Self-correction does work when there is external feedback. A compiler. A failing test. A retrieved document. A person who actually knows.

That is the whole thing in one line. The answer and the check come out of the same process, so anything that pushes on the process pushes on both. There is no separate faculty in there that stands apart and audits.

## So, should you argue

Yes, but with a rule: argue with evidence, never with tone.

"Are you sure?" is close to the worst input available. It carries all of the pressure and none of the information. Replace it with the reason you doubt the answer — the number that looks wrong, the source that says otherwise, the case it did not handle. Then the model has something to move toward instead of merely something to move away from. That is what raises the chance a revision is progressive rather than regressive.

State your position after the answer, not before. Ask about the claim rather than about your version of the claim. And when you cannot supply a reason and you push anyway, be honest about what is happening — that is not auditing, it is negotiating, and you will win.

## Why this is about to stop being a matter of taste

In November 2025, the FDA's Digital Health Advisory Committee met on generative AI mental health devices [7]. When the committee listed the novel risks that this class of product introduces, it named three: bias, hallucination, and sycophancy.

That is a regulator putting a conversational habit on a risk register. It is the right instinct. In a system where a person's pushback moves the output and the moved output persists, agreeableness is not a personality quirk. It is a failure mode with a measurable rate.

Which points at the design conclusion. If the correctness of your system depends on a model holding its ground under pressure, you have built on the one property these models reliably do not have. Put the check outside the conversation. A test that runs, a source that is retrieved, a rule that is evaluated before the action commits — something with no opinion about whether you are happy. The model is a good generator and a poor witness to itself, and everything useful follows from designing around that rather than arguing with it.

---

## References

1. Laban et al., ["Are You Sure? Challenging LLMs Leads to Performance Drops in The FlipFlop Experiment"](https://arxiv.org/abs/2311.08596), arXiv:2311.08596.
2. Fanous et al., ["SycEval: Evaluating LLM Sycophancy"](https://arxiv.org/abs/2502.08177), Stanford, 2025, arXiv:2502.08177.
3. Chen et al., ["Persona Vectors: Monitoring and Controlling Character Traits in Language Models"](https://arxiv.org/abs/2507.21509), arXiv:2507.21509, and the accompanying [Anthropic research note](https://www.anthropic.com/research/persona-vectors).
4. ["Interaction Context Often Increases Sycophancy in LLMs"](https://arxiv.org/abs/2509.12517), CHI 2026, arXiv:2509.12517.
5. Huang et al., ["Large Language Models Cannot Self-Correct Reasoning Yet"](https://arxiv.org/abs/2310.01798), ICLR 2024.
6. Kamoi et al., ["When Can LLMs Actually Correct Their Own Mistakes?"](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00713/125177/), TACL, 2024.
7. [FDA Digital Health Advisory Committee meeting of 6 November 2025](https://www.fda.gov/advisory-committees/advisory-committee-calendar/november-6-2025-digital-health-advisory-committee-meeting-announcement-11062025).

#AI #LLM #AISafety #Sycophancy #AIEvaluation #AIAlignment #HumanAIInteraction #AIReliability #AIGovernance #LLMOps #MachineLearning

---

<small>© 2026 Alexander Chernov. All rights reserved. First published on [LinkedIn](https://www.linkedin.com/pulse/should-you-argue-llm-alexander-chernov-qmqgc/), which remains the canonical version; this page is a reprint by the author.</small>
