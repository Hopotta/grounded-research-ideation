# evals (not part of the runtime skill; `package_skill` excludes this folder)

## 1. Offline tests (no network, no model)
    python3 evals/test_ideasci.py -v          # 74 tests: parsers, search flow with HTTP patched, read gate,
                                              # a synthetic good run, 29 single-fault negatives + 2 positive controls, cutoff and --force traces, the scorer, docs-vs-CLI flags,
                                              # frontmatter lint (Codex 500-char description limit, kebab-case name)
All paper ids in the tests are synthetic. Fixtures: `fixtures/arxiv_official_example.xml` is copied from arXiv's own
API documentation; `arxiv_sample.xml` and `openalex_sample.json` are synthetic, schema-faithful.

## 2. Install
    Claude Code (user):    ~/.claude/skills/grounded-research-ideation/
    Claude Code (project): <repo>/.claude/skills/grounded-research-ideation/
    Codex (user):          ~/.agents/skills/grounded-research-ideation/      (older Codex builds: ~/.codex/skills/)
    Codex (project):       <repo>/.agents/skills/grounded-research-ideation/
One copy plus a symlink works for both. Restart the agent if the skills directory did not exist at session start.

## 3. Trigger evaluation (needs a real harness; not run in the authoring sandbox)
`trigger_cases.json` = 12 should-trigger and 15 should-not-trigger prompts (includes hard negatives such as
"this SQL query is slow" and "summarize arXiv 2610.04074"). `trigger_borderline.json` = 3 prompts whose right
behaviour is described in `note`; do not score them.
Claude Code, using the skill-creator scripts:
    python -m scripts.run_loop --eval-set <skill>/evals/trigger_cases.json --skill-path <skill> --model <model-id> --max-iterations 5
Codex: start a session in a repo that has the skill installed, paste each prompt, and record whether the skill is
selected (ask "which skill did you use?" after the first turn). Target: >= 11/12 positives, <= 1/15 negatives.

## 4. Scenario acceptance (needs a real harness)
`evals.json` has 7 scenarios. For each: run the prompt in a scratch repo with the skill installed (network on; scenario 3 with it off),
save the agent's final message to `reply.txt`, then score the run directory it created:

    python3 evals/score_run.py runs/<slug> --scenario <N> --reply reply.txt

Scenarios 1, 3, 4, 6, 7 have mechanical assertions (check exit codes, query/probe counts, no unread citations, no artifacts
for gap-only requests, reply mentions the epistemic status). Scenarios 2 and 5 need a human to read the transcript:
2 = at most one clarifying question; 5 = existing work is named and no gap is invented. Record results in a table like
the one in `RESULTS.md`. The scorer itself is tested offline; the agent runs are what you add.

## 5. Replay validation on your domain
See `references/review-protocols.md`, section 5.
