# Verification record (authoring sandbox, 2026-10-12)

Honest scope: there was no `claude` or `codex` CLI and no API key in the sandbox, so **nothing here was run inside a real
Claude Code or Codex session**, and no live arXiv/OpenAlex request succeeded (network blocked; arXiv's robots policy also
blocked a direct fetch). What was verified, and how:

## Executed
| Check | Method | Result |
|---|---|---|
| Spec lint | skill-creator `quick_validate`; own lint: name = folder, kebab-case, description <= 500 chars (Codex limit), no angle brackets, single-line frontmatter, SKILL.md < 500 lines | pass (SKILL.md 134 lines, ~2.4K words) |
| Script correctness | `python3 evals/test_ideasci.py` | 74/74 pass |
| arXiv parser vs real format | arXiv's official docs example response (redundant xmlns, old-style id, wrapped title) | pass |
| OpenAlex parser | synthetic schema-faithful fixture (inverted-index abstract, null abstract/doi, subfield) | pass |
| Search flow | HTTP patched: ledger + query log, cross-source title dedupe with alias, AND->OR relaxation, partial source failure, bad date | pass |
| Real failure path | unpatched search in the sandbox | exit 2, fallback hint, failed search not logged as coverage |
| Read-before-cite gate | unknown id, missing digest, TODO digest, `full` without text anchors, no downgrade full->abstract | pass |
| Stage gates | one synthetic complete run passes `check --stage all --strict`; 29 single-fault mutations each fail (or warn, for heuristics) with the expected message; 2 positive controls | pass |
| Docs vs CLI | every `ideasci.py` / `$IDEASCI` `<sub> --flag` shown in SKILL.md and references exists; verified to fail when a bogus flag is injected | pass |
| Per-run cutoff | `init --cutoff`; `search` defaults `--before` and refuses a later one; `check` errors on a cited paper dated after the cutoff (full date or year), warns on unrestricted queries and undated papers; `add --date` | pass |
| `--force` trace | `read --force` sets `forced`; shown by `status`; `check` warns for cited forced papers (error under `--strict`); an honest re-read clears it | pass |
| Scenario scorer | `evals/score_run.py` for scenarios 1, 3, 4, 6, 7 against the synthetic good run and mutated runs (thin trail, fabricated citations, unread citation, premature proposal); scenarios 2 and 5 reported as manual | pass |
| Fail-closed | a freshly scaffolded run fails `check` (unfilled TODO) | pass |

## Revision 2 (after an outside review of v1)
Changes: per-run cutoff, `--force` trace, quick-mode wording made consistent (Stages 2-3 now say which numbers are standard),
proportionate epistemic statement (always / only-when-it-applies), "what the source supplies that the closest in-domain method
lacks" folded into an existing field (no new gate), non-ML evaluation wording, scenario scorer.
Declined: relaxing the probe warning in quick mode (quick cuts counts, not breadth); a new mandatory "swap the source" line (the
existing in-domain-difference field plus the four-condition transfer test already cover it).
Found while testing: the docs-vs-CLI test in v1 only matched the literal `ideasci.py`, so the `$IDEASCI` commands in SKILL.md were
never checked. Fixed; SKILL.md's commands were all valid.

## Self-simulated (a judgment, not a harness run)
Trigger routing: each of the 27 labelled prompts + 3 borderline was judged using only `name` + `description`.
- Before the fix, one false-positive risk: the description carried the paper id, so "Summarize arXiv 2610.04074" would
  plausibly match on the id alone. Fixed by removing the id and adding "related-work text, paper summaries" to the exclusions.
- After the fix: 12/12 positives route in, 15/15 negatives (incl. hard negatives: slow SQL, API latency profiling,
  reproduce-a-table, survey in Chinese) route out. Borderline: topic-for-a-first-year-PhD and benchmark design route out
  (out of the paper's scope); "what has been done and what is missing" routes in and should stop after Stage 2.
Treat as a prior. Run section 3 of `README.md` in a real harness to get measured rates.

## Not done
- Live-network `search` against arXiv/OpenAlex.
- Any LLM-driven end-to-end run of the 7 scenarios in `evals.json`.
- Measured trigger rates; description optimisation loop.
- Replay validation against a held-out paper.
