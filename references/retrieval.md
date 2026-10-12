# Retrieval: two regimes, one tool

Tags: **[P]** from the paper (App. A.1; repository README). **[E]** added here.

Contents: 1 Regimes - 2 Abstraction ladder - 3 Choosing probes - 4 Query hygiene - 5 Thin or noisy results - 6 Backends and limits - 7 Temporal cutoff and replay - 8 Optional: the Svalbard Idea Vault

## 1. Regimes [P]

The paper's roles all use the same keyword-search interface. The regime is a property of how the query is phrased, not of a separate tool.

| | Same-problem regime | Cross-setting regime |
|---|---|---|
| Used by | gap finder, reviewer; report writer for displaced related work | innovator; report writer for the mechanism source |
| Phrase queries with | the exact terminology of the axis and the problem definition | the structure of the *challenge alone*, with the problem's own nouns removed |
| Goal | the same-challenge, same-problem prior art, as completely as possible | work that fought the same difficulty elsewhere, where a transferable mechanism lives |
| Volume | 4-8 queries per axis, rephrased while the pool is thin | 6-10 queries, leaving the problem's own sub-field, spanning >= 3 sub-fields |
| Output it must support | near-misses and why each falls short | a named source paper, mechanism, and the condition the transfer relies on |
| Flag | `--regime same` | `--regime cross --probe "<sub-field>"` |

The paper's corpus makes this literal: its search spaces are `problem_definition`, `challenge`, `intuition`, `solution`. Same-problem retrieval queries problem definition and challenge together; cross-setting retrieval queries the challenge alone. You emulate that by deleting problem-definition words from the query.

An in-domain hit is admissible as a *source* only when the transfer is non-trivial rather than a rediscovery of the closest prior work. In the paper, restricting the innovator to same-domain retrieval cut in-domain novelty from 67.0% to 36.3%.

## 2. Abstraction ladder [E]

Cross-setting queries need the right level of abstraction. Write the same challenge at three levels, then search from L1 and L2.

| Level | What it contains | Example (rollout allocation for reasoning RL) |
|---|---|---|
| L0 problem-specific | the problem's own nouns | "GRPO rollouts per question difficulty" |
| L1 challenge-only | the failing desideratum, domain words removed | "allocate a fixed sampling budget across items with uncertain solvability" |
| L2 structure-only | the mathematical or algorithmic form | "budgeted adaptive sampling", "best-arm identification", "multi-armed bandit exploration bonus" |

L0 finds in-domain work (use it in Stage 2). L1 finds work that fought the same difficulty under other names. L2 finds the field whose core concern this structure is. If L2 returns only textbook material, descend to L1 inside that field to find the current state of the art.

Prompts for naming the structure: what is being chosen, ranked, allocated, estimated, compressed, or scheduled? Under what uncertainty and what budget? Is the feedback delayed, noisy, or adversarial? Is the object a sequence, a graph, a distribution, a constraint set?

## 3. Choosing probes [E]

A probe is a sub-field where the structure is a core concern. Pick probes by asking "who else has this problem and had to solve it for survival?" rather than from a fixed list. Examples of the kind of field to consider: operations research and scheduling, bandits and online learning, databases and query processing, networking and congestion control, control theory, signal processing, experimental design and statistics, mechanism design and economics, operating systems, computational biology, statistical physics. Choose at least three distinct ones and log each with `--probe`; `check --stage all` warns when fewer than three probes were used.

Prefer a probe where the source mechanism has theory or a clear assumption, because the transfer test needs "why it works there" and "what it relies on".

## 4. Query hygiene

- arXiv search is keyword-based, not semantic. Use 2-5 content words, not sentences. Quote phrases: `"filter then refine"`. The script ANDs terms and retries with OR if AND returns nothing.
- Vary vocabulary: synonyms, abbreviations, the metric ("latency", "throughput"), the object ("candidate set"), the technique family.
- Use `--after` / `--before` (YYYY-MM-DD) to separate recent work from classics. Sorting is by relevance.
- Read the abstract snippet printed by `search`; do not read full text of anything you will not rely on.
- Follow one hop of citations from a strong source paper (its related-work section names the field's standard mechanisms). [E: the paper's corpus builder also expanded reference lists one hop]

## 5. Thin or noisy results [E]

- Zero or few relevant hits: move up a level on the ladder, add a synonym, drop the least informative term, or switch `--source` (`arxiv,openalex`).
- Many hits but all in-domain: you are still at L0. Remove domain nouns.
- Many hits but all textbook-level: you are at L2 without a bridge. Add the field name plus the specific challenge.
- Saturation: stop a regime when two consecutive rephrasings surface no new close papers. Record that in `plan.md`; the gap's "search trail" cites it.
- Do not lower the bar to hit a query count. A shorter trail with honest notes beats padding.

## 6. Backends and limits

| Backend | Covers | Notes |
|---|---|---|
| `--source arxiv` (default) | arXiv, all subject areas | Keyword search; the script waits ~3 s between calls as arXiv requests; `field` = primary category (e.g. `cs.IR`). |
| `--source openalex` | scholarly works across fields, including non-arXiv venues | Since February 2026 OpenAlex expects an API key (free); set `OPENALEX_API_KEY`. Without one it may be rate limited or refused; the script then reports the HTTP status. `mailto` is ignored. Abstracts are rebuilt from an inverted index; `field` = OpenAlex subfield. |
| Platform web search + `add` | anything the search tool finds | Register each paper you will rely on with `ideasci.py add`. |

If the sandbox blocks the network, `search` exits with code 2 and prints the fallback. Ask the user to allow network access, or use the platform's web search and `add`. A failed search is not logged as coverage.

Results from different sources are deduplicated by normalised title; a duplicate is recorded as an alias, so citing either id works.

## 7. Temporal cutoff and replay [P/E]

The paper evaluates ideation by hiding the future: retrieval is restricted to papers before 2026-01-01 and proposals are compared with directions human papers pursued afterwards. `--before YYYY-MM-DD` gives you the same control per query, and `init --cutoff` makes it per run: searches default to the cutoff, a later `--before` is refused, and `check` rejects cited papers dated after it (`review-protocols.md`, section 5). Web-search fallbacks are not date-restricted, so register them with `add --date`. Two caveats the paper itself states: model memory cannot be controlled (a title-only probe found no recall, which cannot rule out latent contamination), and your own session may already know the answer.

## 8. Optional: the Svalbard Idea Vault

The paper releases its corpus as a Hugging Face dataset (`Jerry999/SvalbardIdeaVault`): papers reduced to results-masked records with four views (problem definition, challenge, intuition, solution). The repository README states a CC BY-NC 4.0 license; check the dataset card before use, and note the non-commercial term. It is **not bundled** with this skill and this skill's scripts do not read it. If you have it locally, use the `challenge` view for cross-setting queries and `problem_definition` + `challenge` for same-problem queries, and register what you rely on with `ideasci.py add`.
