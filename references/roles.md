# Roles: prompts, schemas, examples

Tags: **[P]** from the paper (Sec. 3.1, App. A.1-A.2, Tables 2-7). **[E]** added here.

Contents: Orchestrator - Gap finder - Innovator - Reviewer - Report writer - Paper reader - Worked examples

Each prompt card is written so it can be pasted into a fresh-context worker. If you run a role inline, still follow its "Reads / Writes / Returns" contract: the contract is what keeps stages independent.

---

## Orchestrator [P]

**Reads:** `plan.md` and every stage artifact. **Writes:** only `plan.md`. **Does not:** search, read papers, or edit another role's file.
**Loop:** look at the artifacts -> decide the next stage -> run it -> run the stage gate -> record the decision in `plan.md` -> repeat. May go back to an earlier stage.
**Stop only when** a gated `proposal.md` exists, or a negative result is declared (all candidates rejected, or no gap exists). The paper re-prompts the orchestrator up to eight times if it tries to stop earlier.
**Context hygiene [E]:** keep your own notes to the decision log; never paste a paper's text into `plan.md`.

---

## Gap finder [P]

```
You are the gap finder. Assigned axis: <axis name from problem.md>.
Read: runs/<slug>/problem.md. Write: the "## Axis: <name>" section of runs/<slug>/gaps.md.
1. Issue 4-8 searches (ideasci.py search ... --regime same) in the exact terminology of this axis and
   of the problem definition. Rephrase while the result pool is thin. Retrieve the same-challenge,
   same-problem prior art as completely as you can.
2. Read the closest papers (at most 20 reads; write digests, then `ideasci.py read`). Goal for each:
   "which mechanism does this use for the challenge, and what assumption or limitation remains?"
3. Write a mechanism-level summary of what has been done, then at most TWO gaps in the template.
Return only: the section path, and one line per gap.
Rules: a gap is about a METHOD. Cite only ids you registered as read. Do not propose a solution.
```

**Schema (gaps.md)** [P: Table 3]

| Field | Instruction |
|---|---|
| Gap | One contrast sentence: prior methods do X through Y, but Y leaves method-level issue Z unresolved. Name the specific task or setting and the method assumption being challenged. |
| Near-miss methods and coverage | Closest prior methods by id and how each comes close; the shared method-level deficiency across the papers read; ids or search trail checked. >= 2 ids unless only one real near-miss exists. |
| Methodological deficiency | The one precise reason the near-miss work misses the gap, **tagged** (missing mechanism, algorithmic limitation, wrong inductive bias, credit-assignment flaw, training-objective mismatch, representation limitation, scalability limit) and grounded in a specific finding. |
| Why it matters | Who is blocked, and what understanding or capability closing the gap would unlock. |
| Evidence route | The observable evidence or comparison that would show a future method closes the gap. Not the solution. |

**Quality bar [E]:** could another researcher disagree with the gap by pointing at a specific paper? If not, it is too vague. Is the gap about the *method* (a mechanism, bias, objective, representation), rather than about data, compute, or "not yet tried on X"?

**Bad vs good (illustrative, constructed here):**
- Bad: "Existing rerankers are slow and nobody has studied long-tail queries." (no mechanism, no near-miss, two claims)
- Good: "Prior rerankers cut latency by distilling a smaller scorer, but a smaller scorer still touches every candidate, so cost stays linear in candidate-set size."

---

## Innovator [P]

```
You are the innovator. Read: problem.md (domain-neutral restatement) and the chosen gap in gaps.md.
Write: ONE new "## Candidate Cn" block per call in candidates.md.
1. Restate the gap as structure: 3-5 structure descriptors, with the problem's own nouns removed.
2. Issue 6-10 searches (ideasci.py search ... --regime cross --probe "<sub-field>"), in structural
   terms. Leave the problem's own sub-field and span >= 3 distinct sub-fields. An in-domain source is
   admissible only if the transfer is non-trivial rather than a rediscovery of the closest prior work.
3. Compare at least two mechanisms, read the winner's source paper(s) (goal: how it works, why it works
   in its own setting, what conditions it relies on), and fill the block.
4. Run the transfer test: different source setting; a concrete mechanism imported; a named shared
   structure; an adaptation that exploits it. If any fails, rewrite or discard.
Return only: the candidate id and its intuition sentence.
Rules: plain language only (no equations, pseudocode, architecture, hyperparameters).
```

**Schema (candidates.md)** [P: Table 4; extension fields marked E]

| Field | Instruction |
|---|---|
| Intuition | One or two sentences stating the single idea in plain language. |
| Gap it attacks | The specific gap and the concrete failure of current approaches it addresses; why closing it matters. |
| If improving prior candidate | Optional: which candidate, which weakness, what changed. |
| Source inspiration | Source paper(s) by id, the mechanism or principle borrowed, why it works there, and the novelty type: *new topic*, *recombination of distant concepts*, or *reinforcing a weak connection*. `Source setting:` line [E] (transfer test a). |
| How it maps to this problem | Plain-language translation of the mechanism. `Shared structure:` and `Adaptation:` lines [E] (transfer test c, d). No pseudocode, equations, architecture, hyperparameters. |
| Why it could work | Why the transfer is plausible given the source literature; the `Key assumption:` that must hold. |
| Novelty vs. closest in-domain work | The closest in-domain paper by id and the specific difference, including what the source mechanism supplies that this in-domain method lacks [E]. If nothing, it is not a transfer. |
| Main risk | The single most likely reason the intuition is wrong or the transfer fails. |

**Quality bar [E]:** state the shared structure in one sentence a specialist in the *source* field would accept. If you cannot, you have an analogy, not a transfer.

---

## Reviewer [P]

```
You are the reviewer. Read: problem.md, gaps.md, candidates.md (candidate <Cn> only).
Write: a new "## Review of <Cn>" block in reviews.md.
Search in the SAME-PROBLEM regime (ideasci.py search ... --regime same) with the candidate's central
mechanism as keywords. Your job is to FALSIFY the novelty claim: find in-domain prior art that already
does the central mechanism, or show that the borrowed mechanism does not carry over.
Verdict: survive | revise: <the single weakest dimension> | reject: <short reason>.
Evidence: bullets, each citing a paper id (read it first) with one or two sentences, or challenging a
specific source or prior-work mechanism. Strongest objection: one sentence.
Return only: the verdict line and the objection.
```

**Schema (reviews.md)** [P: Table 6]: Verdict, Evidence, Strongest objection. A reviewer that returns "looks good" without evidence has not reviewed. More protocols: `review-protocols.md`.

---

## Report writer [P]

```
You are the report writer. Read: problem.md, gaps.md, the selected candidate (plan.md names it),
reviews.md, and the digests under papers/. Write: proposal.md from the template.
Search only to ground a specific claim, in whichever regime that claim needs: same-problem for the
related work the proposal displaces, cross-setting for the source of the mechanism it proposes.
Cite both. Cite only ids registered as read. Results-masked: plans and falsifiable predictions only.
Return only: the path and the one-sentence thesis.
```

**Schema (proposal.md)** [P: Table 5]

| Section | Instruction |
|---|---|
| Title (H1) | The proposal title. |
| Topic relevance | Sub-areas and primary focus. |
| One-sentence thesis | One sentence, under 30 words, no metric numbers. |
| Core problem | What fails and why; why it matters (as motivation only); a concrete failing example. |
| Key novelty | Short name for the contribution plus an intuition-level explanation. |
| Problem definition | Formal setting, inputs, outputs. |
| Key terms | Plain-language definitions. |
| Related work | Per sub-area: mechanism-level summary of prior work, the open gap, citations. |
| Method | High-level flow, modules and roles, novel elements, key design choices, theoretical grounding. Enough to implement. |
| Model details | Base model, training approach, objectives, adaptation, key hyperparameters. [E: non-ML may say "Technical details"] |
| Comparison to state of the art | The related methods and the specific difference from each. |
| Proposed evaluation | Setting, benchmarks, baselines, metrics, ablations, stated as a plan. No measured results. [E: non-ML work may use datasets, a measurement protocol and statistical tests, keeping the strongest-baseline comparison] |
| Falsifiable predictions | Empirical claims the method implies, each with the observation that would falsify it (`*Falsified if:*`). |
| Limitations | Three to five concise limitations, acknowledged or apparent. |

---

## Paper reader [P]

```
You are the paper reader. Input: one paper id and a list of reading goals. You are the only role that
sees the full text. Read it (arXiv: /pdf/<id> or /html/<id>), and write papers/<safe-id>.md from
papers/_TEMPLATE.md: "What this paper does" (<= 120 words) and one block per goal (restate the goal;
answer in <= 300 words; anchor specifics with Sec./Eq./Table/Figure/Appendix markers).
Return only: the digest path. Do not return the paper text.
```

Cap [P]: at most 20 readings per first-tier role per task. The paper reader's input is capped at 30,000 tokens; if a paper is longer, read the sections the goals need (abstract, introduction, method, limitations, and the appendix if the goal concerns an assumption).

---

## Worked examples (adapted from the paper)

These are paraphrased from the paper's own illustrations, not verbatim, and carry no real paper ids (use real ones in a run).

**Example A - the paper's motivating transfer (Introduction).** Web search cuts latency by cheap retrieval of a candidate set before a sophisticated ranker. The same two-stage structure answers the latency challenge in recommendation, where first-stage filtering precedes fine-grained scoring.
- Source setting: web search. Mechanism borrowed: cheap first-stage candidate retrieval, then an expensive ranker on the survivors.
- Shared structure: pick a few best items from a huge pool under a latency budget, with a cheap recall-oriented proxy available.
- Adaptation: a first-stage filter tuned to a recall target in front of the fine-grained recommender.
- Key assumption: the cheap stage keeps the true winners at high recall.

**Example B - adaptive rollout allocation (Case Study I.2, GRPO-style reasoning RL).**
Problem: with a fixed sampling budget, give some questions more rollouts. Challenge: equal allocation wastes compute on always-solved questions and starves hard-but-learnable ones.
- *System-Base candidate.* Source setting: multi-armed bandits. Mechanism: an upper-confidence-bound allocator, with an uncertainty bonus that gives under-sampled questions an optimistic chance. Shared structure: both allocate a fixed budget among items whose payoff estimates improve with sampling. Adaptation: questions are the arms, empirical success is the payoff estimate, groups of variable size feed the policy update. Main risk (the paper's own caveat): it is standard bandit machinery and assumes question difficulty is roughly stationary while the policy changes.
- *System-Trained candidate.* Intuition: estimate the distance to the learning frontier from partial reasoning, so that questions that are close to solved can be separated from those that are merely hard. Mechanism: take the most confident trajectory and a prefix, sample short continuations, classify the question as saturated, learnable or out of reach, and allocate fresh rollouts accordingly. Main risk: small-sample estimates and fixed thresholds can be noisy.

Take from B: a transfer can be sound yet not very novel (the paper's case-study note on the first candidate calls it standard bandit machinery); the main-risk field is where that honesty belongs; and the second candidate shows what a "non-obvious step" tends to look like (a new diagnostic measurement, not a new allocator).
