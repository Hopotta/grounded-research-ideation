# Paper notes: IdeaScientist (arXiv:2610.04074)

Liu, Tao, Liao, Jin, Sun, Yang, Zhang, Chen, Huang, Zhang, Yang, He, Xuan, Wanga, Kumar, Diab, Yih, Dong. "IdeaScientist: Orchestrating Agents for Grounded Scientific Ideation." Submitted 2 Oct 2026 (v1). CMU and Meta. Code: github.com/jiarui-liu/IdeaScientist. Data: Hugging Face `Jerry999/SvalbardIdeaVault`. Read for this skill: the paper's full text and appendices, the repository README, and its evaluation prompts file (stated to be verbatim from Appendix C). Not read: the repository's role prompts (`roles.py`, not fetchable) and the paper's Case Studies I.3 and I.4 (the fetched text was truncated; I.1 and I.2 were read).

Contents: 1 Task and idea - 2 Pipeline - 3 Fidelity ledger - 4 Evidence and caveats - 5 Boundaries - 6 What cannot be transferred

## 1. Task and idea

- **Task.** Research ideation is isolated from implementation and experimentation: given a *problem definition* (task input and desired output) and a *challenge* current solutions fail to meet (quality, latency, privacy, ...), produce a grounded research proposal that addresses it. Success is judged before any experiment, when many plausible solutions exist and none is uniquely correct.
- **Intuition.** Novelty emerges by connecting existing knowledge in new ways; a solution for one problem transfers to a seemingly unrelated one when they share the same underlying structure (structure-mapping and analogical-transfer literature). So draw insight from work addressing a similar challenge in a *different* field. The paper's example: web search cuts latency with cheap candidate retrieval before a sophisticated ranker; the same two-stage structure answers latency in recommendation.

## 2. Pipeline

Orchestrator (plan only; cannot search or read) coordinates three producers and two helpers, through files:
**gap finder** (`gaps.md`) -> **innovator** (`candidates.md`) -> **report writer** (`report.json`), with a **reviewer** (`scores.md`) and a **paper reader** (`papers/<id>.md`, the only role that sees full text, in an isolated single-turn context with a 30K-token input cap). Output schemas are fixed and identical at training and deployment. Per-turn and per-role caps: gap finder 15 turns, innovator 20, writer 20, orchestrator 100; at most 20 paper readings per first-tier role per task. Producer artifacts need >= 20 non-whitespace characters before a role may return (3 completion prompts); the orchestrator is re-prompted up to 8 times if it stops before a final proposal exists.

Validity gates (training-time, but they define what "valid" means): schema; assigned-axis match; at most two gaps per axis; every cited id resolves **and was read**; a judged methodological focus (gap finder) or methodological contribution (innovator); all required report fields. Early report-writer episodes failed read-before-cite about half the time until citations were reduced to bare inline ids.

Training (not reproducible in a skill): one LoRA adapter per role, asynchronous GRPO, reward = 0.85 x (validity gate x mean of reference-free score, reference-grounded score, citation F1) + 0.15 x protocol-compliance term. Roles are trained separately because end-to-end training with only a final reward rarely completed the pipeline.

Corpus: Svalbard Idea Vault, 4.7M papers (1986 to 2026-06-18; all arXiv areas; 2.8M with full text), 2.77M decomposed into (problem definition, challenge, gap, intuition, proposal) with measured results removed. Cutoff 2026-01-01; 14,977 post-cutoff ML methodology papers split 14,500 / 200 / 277 (train / validation / test).

## 3. Fidelity ledger

| Element | Paper | This skill | Tag |
|---|---|---|---|
| Task framing: problem definition + challenge | yes | Stage 1, per-axis challenge | P |
| Three producer roles + orchestrator + reviewer + reader | yes | Stages 2-5 and section 4 of SKILL.md | P |
| Orchestrator cannot search or read; edits only the plan | yes | "Orchestrator rules" | P |
| Same-problem vs cross-setting regimes, same tool | yes | `--regime same/cross`, `retrieval.md` | P |
| 4-8 / 6-10 queries; >= 3 sub-fields; <= 2 gaps per axis; >= 2 near-misses | yes | SKILL.md, `check` | P |
| Gap / candidate / report / reviewer / reader schemas | Tables 3-7 | templates, `check` | P |
| Read-before-cite gate | yes (training gate) | `read` + `check` (hard error) | P (applied at inference) |
| Results-masked proposals; falsifiable predictions with refutations | yes | proposal template, rules | P |
| <= 20 reads per role; 30K reader cap | yes | caps in modes table; reader guidance | P (cap), E (30K as guidance) |
| Domain-neutral restatement of the axis | implied by "challenge alone" retrieval view | Stage 1 field, abstraction ladder | E |
| Abstract-level reads allowed for background cites | no (all cited ids read) | `--level abstract`, near-misses and sources still need `full` | E |
| Full-text anchor guard (>= 2 section/equation markers) | paper asks digests to anchor in sections/equations | enforced mechanically by `read` | E |
| Quick mode | none | fewer queries/reads, labelled "lightly grounded" | E |
| "No gap exists" and "negative result" outcomes | not discussed | explicit valid outcomes | E |
| Review loop limits (2 revisions, 3 candidates) | not specified | Stage 4 | E |
| Transfer test as a self-check | an evaluation metric (App. C) | candidate self-test, quote-test | P-eval used as E |
| Blind-derivation stress test | an evaluation metric (App. C) | optional Stage 4 step | P-eval used as E |
| Replay validation | the paper's temporal-holdout design | optional protocol | E, adapted |
| Per-run cutoff enforced at `check` (cited paper dates, query restriction) | one global cutoff, enforced in the retrieval tool | `init --cutoff`, `search` default, `check` | P (idea), E (per-run, checked after the fact) |
| `--force` reads recorded and reported | not applicable | `forced` flag, `status`, `check` warning, delivery note | E |
| Cheapest falsifying experiment in delivery | not in schema | delivery message | E |
| Epistemic-status statement | not in schema | delivery message | E |
| RL-trained roles; vault retrieval with embeddings | yes | **not reproduced** | - |

## 4. Evidence and caveats

All figures are from the paper's Table 1 and appendices. "Overall" is the mean of average novelty and average proposal quality, each on a 0-100 scale; **differences quoted as "%" in the paper are percentage points of that score**, not relative improvements. Every score comes from one LLM judge (Qwen3.6-27B, reasoning off) on 277 held-out ML methodology papers, with retrieval restricted to pre-2026 literature.

- On Qwen3.6-27B: IdeaScientist-Base 73.5 and Trained 74.6, against 60.6 for the best open baseline (DeepScientist), i.e. 12.9 and 14.0 points above. Against general-purpose agents (native SDK harnesses): Trained (on the 27B model) beats Claude Code SDK with Claude-4.8-Opus (68.7) by 5.9 and Codex SDK with GPT-5.4 (69.5) by 5.1. The same harness on those frontier backbones (Base): 77.7 on Claude-4.8-Opus (+9.0 vs the SDK) and 71.9 on GPT-5.4 (+2.4).
- The gain is mostly **novelty**. Average proposal quality was on par or modestly above the strongest baseline (about +1.7 to +2.5 points on the three open backbones). The In-domain (structural-transfer) novelty score is where it separates most: on Claude-4.8-Opus, 54.9 vs 17.0 for Claude Code SDK. That metric is the property the method is designed to produce, so read it as "does what it was built to do" more than as independent validation.
- **Not uniformly better.** On GPT-5.4, the native Codex SDK scored higher than the harness on All-literature novelty (72.4 vs 67.8), Cutoff novelty (71.8 vs 67.5), specificity (88.5 vs 82.1) and actionability (83.4 vs 78.4); the harness won on In-domain transfer (47.7 vs 19.9) and clarity. The general-purpose agents also failed to deliver a scorable proposal on 5 (Claude Code) and 8 (Codex) of 277 problems; the harness had none.
- **Ablations (Qwen3.6-27B).** Adding the gap finder and then the innovator to the report writer raised All and Cutoff novelty at each step (up to +7.7 points on Qwen3.6-27B, +13.0 on Gemma-4-31B). Cross-domain vs same-domain innovator retrieval: All +5.3, Cutoff +3.7, In-domain +30.7 (36.3 to 67.0), mechanism non-obviousness only +2.2 (33.5 to 35.7).
- **Training adds little at the proposal level.** Per-role validation reward rose about 0.10 for each role, but the full-pipeline gain over Base was +1.9 novelty and +0.4 quality points; the blind human comparison (50 papers, 2 annotators) preferred Trained over Base without significance, and against DeepScientist the win rate was 43% (not significant). Against the other systems it was 75-92% and significant (win rates read off Figure 2b).
- **Judge reliability.** Two human experts agreed at r = 0.56; each of the top three LLM judges correlated 0.51-0.59 with the human average. Qwen3.6-27B had negligible self-preference bias. Scoring proposals is inherently subjective.
- **Cost.** About 169K output tokens per delivered proposal for Trained and 190K for Base on the 27B model. A controlled sweep (40 papers, Base) found that more turn budget raised reward from 0.290 to 0.465 and completion from 0.60 to 1.00.
- **Design lessons reported in the appendix.** Metadata-only reading collapsed training (near-zero reward) versus about 0.5 with full-text reading (a training observation, not a direct inference-quality result). A pairwise "is it better than the reference" innovator reward favoured longer, more elaborate answers and collapsed. Richer per-turn process rewards and privileged-reference injection were tried and not adopted.

## 5. Boundaries

1. **Domain.** Evaluated on ML methodology proposals. The corpus spans all arXiv areas, but nothing in the paper shows the workflow works for wet-lab science, pure theory, or fields with little arXiv coverage. Treat those as untested.
2. **Task type.** Targets were papers contributing a new method, model, algorithm, architecture, training procedure, or technical framework. Surveys, position papers, datasets and benchmarks, and empirical engineering reports were excluded.
3. **Inputs.** The method assumes a well-posed problem definition and challenge. Topic discovery is explicitly left to other work.
4. **Validity of proxies.** Novelty and quality are LLM-judged proxies, retrospective, and measured before execution. The paper cites expert studies in which more novel ideas can be less feasible when executed, and notes direct execution is costly and mixes ideation with implementation skill. No proposal was run.
5. **Contamination.** Retrieval is cut off, but model memory is not; the paper's title-only probe found no recall and says it cannot rule out latent contamination.
6. **Low ceiling on deep novelty.** Mechanism non-obviousness was about a third for both variants, so most central mechanisms remain derivable from prior work.
7. **Cost.** Roughly 170-190K generated tokens per proposal in the paper's setting.
8. **Retrieval quality.** The paper's corpus has full text for 60% of papers and embedding views over decomposed records; keyword search over arXiv/OpenAlex is a weaker substitute, so expect lower recall of near-misses and sources.

## 6. What cannot be transferred

- The RL-trained role adapters and the reward machinery.
- The 4.7M-paper vault, its results-masked decompositions, and its embedding search spaces. The skill replaces them with live keyword search plus the read-before-cite ledger.
- The enforced tool-availability isolation (a role with a zero full-text cap never gets the reader tool). The skill can only ask for isolation; it enforces read-before-cite and digest anchoring, not isolation.
- The fixed backbone and budgets. Your model, search quality, and time budget differ, so the paper's numbers are an indication of direction, not a forecast.
