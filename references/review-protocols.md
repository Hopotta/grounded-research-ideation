# Review protocols

Tags: **[P]** the paper's generation harness. **[P-eval]** the paper's *evaluation* protocol (App. C), reused here as a self-check, which is an extension of how the paper used it. **[E]** added here.

Contents: 1 Reviewer protocol - 2 Transfer test - 3 Blind-derivation stress test - 4 Delivery checklist - 5 Replay validation

## 1. Reviewer protocol [P]

Purpose: falsify the novelty claim against same-problem prior art before any write-up effort is spent.

1. Extract the candidate's **central technical operation** in one sentence.
2. Search the same-problem regime with that operation (and its synonyms) as keywords. Read what you will cite.
3. Look for three things: (a) in-domain work that already performs the operation; (b) work showing the source mechanism fails under the condition the transfer relies on; (c) a simpler baseline that gets the same effect.
4. Verdict:
   - `survive`: you tried and could not falsify it. Say what you checked.
   - `revise: <single weakest dimension>`: fixable (name the one thing to fix: the shared structure, the adaptation, the key assumption, the novelty claim).
   - `reject: <reason>`: the operation exists, or the transfer breaks.
5. Evidence bullets each cite a read paper id with one or two sentences, or challenge a specific source mechanism. One strongest objection, one sentence.

Reviewer anti-patterns: approving on plausibility; rewarding elaborate prose; checking only that citations exist. The paper found judges can reward length and style independent of substance.

## 2. Transfer test [P-eval, used as a self-check]

The paper scores "structural cross-setting transfer" as 1 only if all four hold, and 0 for no transfer, unsupported claims, or superficial analogy. It also requires supporting the verdict with a verbatim quote of at most 35 words from the proposal; if no single quote supports all four, the score is 0.

1. A source problem setting that differs from the target setting is identified.
2. A concrete mechanism, abstraction, or analysis technique is imported from it. A citation or a general-purpose tool alone does not count.
3. A shared underlying structure that explains why the mechanism should transfer is identified.
4. The adaptation that exploits that structure in the target setting is specified.

Use it on every candidate before review. Quote-test [E]: if you cannot point to one passage (<= 35 words) that carries all four, rewrite until you can.

## 3. Blind-derivation stress test (optional) [P-eval, extension of use]

Question: could a competent researcher have derived the central mechanism from the closest prior work without seeing your proposal? In the paper this is the "mechanism non-obviousness" measure, run as two separate calls, because a single call that has seen the answer can always reverse-engineer a derivation.

**Call 1 - proposal-blind derivation.** Fresh context. Input: the problem definition, the challenge, and digests of the three nearest pre-cutoff mechanism-side papers. **Never the proposal.**
Prompt essence: "You are a senior researcher solving this problem using only these papers and standard techniques. Independently derive up to three concrete candidate mechanisms. For each give: the central technical operation; a step-by-step derivation from the supplied papers and standard techniques; which reference supplies each nonstandard step; the key assumption. Do not restate the problem or list broad directions. A new combination is allowed only if you explain concretely how its pieces compose. If no concrete mechanism can be derived, return an empty list."

**Call 2 - frozen comparison.** Input: Call 1's candidates, the same papers, and the proposal's mechanism section.
Prompt essence: "The candidate list is frozen. Do not invent, repair, merge, or extend candidates after reading the proposal. Step 1: state the proposal's central operation in one sentence. Step 2: compare it with every frozen candidate; pick the closest, list shared steps and the consequential steps the candidate lacks, or NONE; topical similarity is not derivation. Step 3: if the candidate list is empty, malformed, or too vague, return *unscored* and do not infer non-obviousness from a failed derivation. Otherwise assign one level."

| Level | Meaning |
|---|---|
| trivial combination | a frozen candidate already contains the mechanism through direct reuse or combination |
| routine extension | a frozen candidate reaches it with ordinary implementation steps and no new structural observation |
| non-obvious step | every frozen candidate misses a consequential step or structural observation the proposal supplies |
| surprising | the missing step also runs against a clear expectation set by the supplied papers |

Use the upper two levels only if you can name the consequential missing step. Do not reward vocabulary, length, or confident phrasing.

**How to act on it [E].** `trivial` or `routine`: tell the user plainly that the central mechanism is likely derivable from prior work; either revise (find the missing consequential step) or present the proposal as a solid, low-risk application rather than a novel mechanism. `non-obvious` or `surprising`: say which step is hardest to guess. In the paper this measure was the hardest one (about 0.34-0.36 for both innovator variants), so a `routine` result is normal, not a failure of the run.
**Without a fresh context [E]:** Call 1 cannot be blind if you already know the proposal. Run it in a separate worker or headless process; if impossible, mark the result "unblinded (weak evidence)".

## 4. Delivery checklist [E, distilled from the paper's judge rubrics]

Answer yes/no for each before sending; fix any "no".

Relevance and clarity
- Does the proposal address *this* problem and *this* challenge, not an adjacent one?
- Could a reader state the contribution after the thesis sentence alone?

Specificity and actionability
- Are the mechanism, inputs, outputs, and key hyperparameters or design choices concrete enough to implement?
- Are datasets, baselines, metrics, and ablations named (or explicitly left open with a reason)?

Soundness
- Are assumptions explicit, with the key one tied to a falsifiable prediction?
- Is every claim supported by a read paper or marked as your own inference?
- Is there any language that reads as a measured result?

Novelty
- Does "Comparison to state of the art" name the closest method and the specific difference?
- Did the transfer test pass, and did the reviewer try to falsify?
- Is the novelty claim calibrated to the stress-test result (if run)?

Impact and honesty
- Is the "why it matters" about who is blocked, rather than generic importance?
- Does the delivery state that the proposal is unvalidated and name the cheapest falsifying experiment?

## 5. Replay validation (optional, to test this skill on your own domain) [E, adapted from the paper's design]

Purpose: check whether the workflow lands near directions humans actually pursued, without waiting for experiments.

1. Pick a method paper P published recently in your domain.
2. Write a problem definition and challenge from P's introduction, with **no method terms**. Audit it for leakage (the paper manually checked 50 extracted inputs and found none leaking the target method).
3. Scaffold with `ideasci.py init runs/replay --cutoff <date of P minus a margin>`. Searches then default to that `--before` date, and `check` rejects any cited paper dated later. Papers you register by hand need `add --date`.
4. Compare your `proposal.md` with P field by field: core problem, key novelty, method, evaluation plan, falsifiable predictions, limitations. Score similarity 1-10 per field (the paper's reference-grounded dimensions); N/A where a field does not apply.
5. Interpret with the paper's caveats: your session's model may remember P; a different valid direction is not a failure (the paper's reward allows a valid alternative to score well); one replay is an anecdote, ten are a signal.
