---
name: grounded-research-ideation
description: Turn an open research problem plus a stated challenge into a literature-grounded, falsifiable research proposal (IdeaScientist method) - find method-level gaps in same-problem work, borrow mechanisms from analogous problems in other fields, review, then write with verified citations. Use for "propose a novel method", "existing approaches fail at X", cross-field inspiration, 研究思路/创新点/课题方案. Not for coding, running experiments, surveys or related-work text, paper summaries, or paper review.
---

# Grounded Research Ideation

Operationalizes the IdeaScientist method (Liu et al., arXiv:2610.04074). Given a **problem definition + a challenge** current solutions fail, you will (1) pin down the method-level gap in same-problem prior work, (2) borrow a mechanism that solved a *structurally analogous* problem in another field, (3) try to falsify the idea, (4) write a falsifiable, results-masked proposal whose citations you actually read.

This reproduces the paper's training-free harness. It does not reproduce its RL-trained roles or its 4.7M-paper corpus, and the paper's evidence is retrospective and LLM-judged (see section 7 and `references/paper-notes.md`). Tags used below: **[P]** specified by the paper, **[E]** engineering extension added here.

`$IDEASCI` = `python3 <this skill's folder>/scripts/ideasci.py` (use `python` on Windows). It needs only the Python standard library.

## 0. Does this apply?

| Situation | Action |
|---|---|
| Wants a **new method / approach / research direction** for a stated problem and challenge, grounded in literature | Run the workflow |
| Gives a problem and a complaint but no explicit challenge | Infer the axes from the complaint, state them in one line, proceed. Ask at most one question |
| Wants only "what has been done / what is missing" | Run Stages 1-2 only, deliver `gaps.md` |
| Wants to implement, debug, tune, run or analyze experiments, reproduce a paper | Do not use this skill |
| Wants a survey, related-work text, paper summary, citation lookup, peer review of a given draft | Do not use this skill (Stage 4 protocols in `references/review-protocols.md` may help a review) |
| Wants a dataset, benchmark, position paper, or "what should I research?" with no problem | Out of the paper's scope. Offer to help formulate problem + challenge first, then run |
| No way to retrieve literature (no network, no search tool) | Do not run it. Say a proposal would be ungrounded; offer a brainstorm labelled **ungrounded, no citations** |

## 1. Core idea (read once)

- Novelty comes from connecting known mechanisms in new ways: a solution transfers to a seemingly unrelated problem when both share the same underlying structure. Search for work that fought the same *challenge* in another field, not only for in-domain work. [P]
- One keyword-search interface, two regimes, set only by how you phrase queries. **Same-problem** regime: exact terminology of the problem, to find near-misses. **Cross-setting** regime: structural terms of the challenge with the problem's own nouns removed, to find transferable mechanisms. [P]
- Stages talk only through files. Each artifact is the whole interface to the next stage, which makes each stage inspectable and re-runnable. [P]
- Nothing is cited unless read. A fabricated near-miss id is the cheapest way to look good, so the gate is mechanical (`check`), not a judgment call. [P]

## 2. Setup

```
$IDEASCI init runs/<slug> [--mode quick]     # scaffolds problem/plan/gaps/candidates/reviews/proposal + ledger.json
```

Real research: leave `Cutoff: none` in `plan.md`. **Retrospective replay only** (`references/review-protocols.md`, section 5): `init ... --cutoff YYYY-MM-DD`. Searches then default to `--before` that date (a later `--before` is refused), and `check` errors on any cited paper dated after it and warns about unrestricted queries and undated papers. Papers found by web-search fallback need `add --date`. [E: the paper fixes a global cutoff in its retrieval tool; this makes it per-run]

Keep heading names, and the English labels the checker reads (`Novelty type:`, `Shared structure:`, `Adaptation:`, `Key assumption:`, `Falsified if:`, verdict words, `[@id]` citations). Write the prose in the user's language. Add `runs/` to `.gitignore` if the repo should not track it.

Modes: **standard** (paper-aligned) or **quick** [E] (exploratory brief; label the output "lightly grounded").

| | quick [E] | standard [P-aligned] |
|---|---|---|
| Axes | 1 | 1-3 |
| Same-regime queries per axis | 3-4 | 4-8 |
| Cross-regime queries | 4-6 over >= 3 probes | 6-10 over >= 3 sub-fields |
| Full-text reads per stage | <= 6 | <= 20 (the paper's cap) |
| Candidates | 1 | 1-3 |

Quick mode cuts query and read counts, not breadth: it still spans >= 3 probes, so `check` keeps the same probe warning in both modes. The numbers quoted in Stages 2-3 are standard; quick uses this table.

Do not starve the run: in the paper, raising the turn budget lifted completion 0.60 to 1.00 and reward 0.29 to 0.47. A run costs on the order of 170-190K generated tokens there; budget accordingly or use quick mode.

## 3. Workflow

Keep the orchestrator rules of section 4 in force throughout. Open `references/roles.md` at the start of Stages 2-5 for the field-by-field schema and a role prompt.

### Stage 1 - Intake -> `problem.md`
Fill: problem definition (input, desired output, setting); 1-3 challenge axes, each with the failing desideratum, an observable, a concrete failing example; a **domain-neutral restatement** of each axis (describe the structure, drop the problem's own nouns; Stage 3 depends on it); what the requester already tried (counts as near-misses). Gate: `$IDEASCI check --run runs/<slug> --stage problem`.
Do not put a candidate solution in the problem statement. If you notice a method name or method-specific term in it, remove it.

### Stage 2 - Gap finding -> `gaps.md` (same-problem regime) [P]
Per axis:
1. Run 4-8 searches (standard; quick: 3-4) in the exact terminology of the axis and problem; rephrase while the pool is thin: `$IDEASCI search "<keywords>" --run runs/<slug> --regime same`. Goal: the same-challenge, same-problem prior art, as completely as you can.
2. Read the 3-8 closest papers (section 5). Reading goal: what mechanism does it use for this challenge, and what assumption or limitation remains?
3. Write the axis section: a mechanism-level summary (group by mechanism, not by paper) and **at most two gaps**, each with the five fields in the template.
A gap is a contrast sentence about a **method**: "prior methods do X through Y, but Y leaves method-level issue Z unresolved", naming the task and the assumption challenged. Tag the deficiency (missing mechanism, algorithmic limitation, wrong inductive bias, credit-assignment flaw, training-objective mismatch, representation limitation, scalability limit). "Nobody has run it on dataset D" is not a gap. Near-misses: >= 2 ids unless truly only one exists. *Evidence route* says what observation would show the gap closed, without proposing the solution.
**If a paper you read already solves the challenge as stated, there is no gap [E].** Report it (id, what it solves, residual differences) and either narrow the challenge with the user or stop. That is a valid outcome.
Gate: `$IDEASCI check --run runs/<slug> --stage gaps`.

### Stage 3 - Innovation -> `candidates.md` (cross-setting regime) [P]
1. From the gap and the domain-neutral restatement, write 3-5 **structure descriptors** (what the problem looks like once its domain is removed) and list sub-fields where that structure is a core concern. See `references/retrieval.md` for the abstraction ladder.
2. Run 6-10 searches (standard; quick: 4-6) phrased in structural terms, leaving the problem's own sub-field and spanning >= 3 distinct sub-fields in both modes. Declare each: `$IDEASCI search "<structural keywords>" --run runs/<slug> --regime cross --probe "<sub-field>" --source arxiv,openalex`. An in-domain source is admissible only if the transfer is non-trivial, not a rediscovery of the closest prior work.
3. Compare at least two candidate mechanisms before choosing; read the source papers (goal: how it works, why it works in its own setting, what conditions it relies on).
4. Write **one candidate block per candidate** in plain language: no equations, pseudocode, architecture, hyperparameters yet. Name the source paper, mechanism, and the condition the transfer relies on; the novelty type; the closest in-domain work, the specific difference, and what the source mechanism supplies that the closest in-domain method lacks (if nothing, it is not a transfer); the main risk.
5. Transfer self-test [E, from the paper's In-domain judge]: all four must hold or the candidate is a superficial analogy: (a) the source setting differs from the target; (b) a concrete mechanism is imported, not just a citation or generic tool; (c) a shared structure explains why it should transfer; (d) the adaptation exploits that structure. These map to `Source setting:`, `Mechanism borrowed:`, `Shared structure:`, `Adaptation:`.
Gate: `$IDEASCI check --run runs/<slug> --stage candidates`.

### Stage 4 - Review -> `reviews.md` [P, loop rules E]
Fresh context if you can (section 4). The reviewer searches in the **same-problem** regime and tries to falsify the novelty claim: is there in-domain work that already does the central mechanism? Verdict per candidate: `survive`, `revise: <single weakest dimension>`, or `reject: <reason>`; evidence bullets each cite an id; one strongest objection. Loop: revise -> re-review, at most 2 revision rounds per candidate; on reject write a new candidate; at most 3 candidates unless the user extends. If all fail, deliver a **negative result** (gaps, why each candidate failed, what to try next) rather than forcing a proposal.
Optional novelty stress test (blind derivation): `references/review-protocols.md`.
Gate: `$IDEASCI check --run runs/<slug> --stage reviews`.

### Stage 5 - Report -> `proposal.md` [P]
Set `Selected candidate: Cn` in `plan.md` (it must have survived). Write the sections in the template order. Rules: thesis is one sentence under 30 words with no metric numbers; **results-masked**, so describe plans and predictions, never measured outcomes; Method detailed enough to implement; per-method differences in "Comparison to state of the art"; evaluation is a plan (setting, benchmarks, baselines, metrics, ablations); every prediction ends with `*Falsified if:* ...`; 3-5 limitations; cite both the related work the proposal displaces and the source of the mechanism it borrows.
Non-ML work: retitle "Model details" as "Technical details" (the checker accepts either), and "Proposed evaluation" may use datasets, a measurement protocol and statistical tests in place of benchmarks, baselines, metrics and ablations. Keep the comparison against the strongest existing approach and the observation that would falsify each prediction.

### Stage 6 - Gate and deliver
`$IDEASCI check --run runs/<slug> --stage all` must exit 0. Errors are the paper's validity gates (schema, caps, citation grounding): fix the stage that owns the error, not downstream text. Warnings are heuristics: read each and either fix or justify in `plan.md`. Then reply in the user's language, briefly: thesis; the gap; the source setting and shared structure; key assumption and main risk; the **cheapest experiment that could falsify it** [E]; paths; reads used (and any `--force` reads that `check` lists, plainly); and the epistemic status (section 7, proportionately). Do not paste the whole proposal unless asked.

## 4. Orchestration rules

- You are the orchestrator [P]: you keep `plan.md` (status, decisions, next action) and decide which stage runs next. You do not carry paper full text. Roles communicate through files only.
- Reading and reviewing are context-hungry. If your platform can spawn a fresh-context worker (a subagent, or a separate headless run), delegate paper reading and review to it, using the prompts in `references/roles.md`. If it cannot, do the same work inline but sequentially: write the digest file, register it, and continue from the file, not from the paper text. [E: the paper isolates reading in a separate 30K-token context]
- Revisit earlier stages when evidence demands: a reviewer finds in-domain prior art that closes the gap -> Stage 2; the transfer test fails -> Stage 3. [P]
- Do not stop before either a final `proposal.md` passes the gate or a negative result is declared. If a stage artifact is thin, fix it rather than hand off. [P]
- Run `$IDEASCI status --run runs/<slug>` to see reads, queries and unfilled artifacts when you lose track.

## 5. Reading papers (the "read" in read-before-cite)

For each paper you will rely on: get the full text (arXiv: the `/pdf/<id>` or `/html/<id>` page; otherwise the DOI/open-access link), extract only what the reading goal needs, and write `runs/<slug>/papers/<safe-id>.md` (safe-id = the id with `:` and `/` replaced by `_`, e.g. `arxiv_2401.00001.md`; copy `papers/_TEMPLATE.md`): a <= 120-word "What this paper does" plus one block per goal (<= 300 words each) anchored in the text with `Sec.`, `Eq.`, `Table`, `Figure`, `Appendix` markers. Then register it:

```
$IDEASCI read arxiv:<id> --run runs/<slug> --level full       # near-misses and mechanism sources need full
$IDEASCI read oa:W<digits> --run runs/<slug> --level abstract # background citations only [E]
```

`full` is refused without >= 2 text anchors: that is the guard against "reading" from an abstract. `--force` bypasses it but is recorded; `status` and `check` list forced papers, and you must say so in the delivery. If search returned a paper you found some other way, register it first: `$IDEASCI add --run runs/<slug> --id arxiv:<id> --title "<title>" --year <Y> --field <category>`. If retrieval fails (blocked network, rate limit), use your platform's web search, then `add`. If you still cannot retrieve a paper, do not cite it.

## 6. Hard rules (and why)

- Never cite an id you did not read; never cite from memory or a snippet. Why: unverifiable citations are the main failure of LLM ideation, and the paper made this a hard gate.
- Never report predictions as results. Why: the paper's proposals are results-masked; a rule that banned all numbers was too brittle, so judge the *meaning*, not the digits.
- Do not call a same-domain rediscovery "cross-domain", and do not dress up a routine extension in new vocabulary. Why: the paper's novelty judge rewards real, non-obvious steps and explicitly not "novelty by jargon".
- Do not reward length. Concise and specific beats elaborate. Why: in the paper a comparative reward drifted toward longer, more elaborate answers independent of substance, then collapsed.
- Do not skip stages to save effort. Why: in the paper's ablation each added role (gap finder, then innovator) raised novelty; weaker backbones gained most.
- Do not put the solution into the gap, the evidence route, or the problem statement. Why: it leaks the answer and breaks the independence of Stages 2-3.
- Do not treat novelty as feasibility. Why: expert studies cited by the paper find more novel ideas can be harder to execute; the paper never executed its proposals.

## 7. Epistemic status (state it proportionately)

**Always**, in one or two sentences: the output is an unvalidated proposal (no experiment was run; your novelty judgment is a proxy, not proof), and how well it is grounded (papers read in full vs abstract, which backends were searched, anything forced or unreachable).

**Only when it applies:**
- *Non-ML domain:* the paper evaluated machine-learning methodology proposals only, so the method's transfer to this domain is untested.
- *A stress test was run, or the user asks how novel it is:* the paper's mechanism non-obviousness stayed low (about 0.34-0.36), so a "routine extension" verdict is normal. If no stress test was run, say the novelty claim has not been stress-tested.
- *The user asks why to trust the method, or how it compares with a plain agent:* its gain was mostly cross-setting novelty, not proposal quality; on GPT-5.4 the native Codex SDK beat the harness on two novelty scopes and on specificity and actionability; RL-trained roles added only +1.9 novelty / +0.4 quality points over the untrained harness you are reproducing, with a non-significant blind human comparison. LLM-judge agreement with humans was about r = 0.5-0.6.

Omit the rest. Do not recite this section in every delivery; the figures and sources are in `references/paper-notes.md`.

## 8. Reference map (load on demand)

- `references/roles.md` - role prompts, field-by-field schemas, worked examples. Open at Stages 2-5.
- `references/retrieval.md` - the two regimes, the abstraction ladder, backends, thin or noisy results. Open before the first cross-setting search.
- `references/review-protocols.md` - reviewer protocol, transfer test, blind-derivation stress test, delivery checklist, replay validation. Open at Stage 4 and Stage 6.
- `references/paper-notes.md` - what is from the paper vs added here, evidence and caveats. Open before claiming "the paper shows ..." or when asked about limits.
