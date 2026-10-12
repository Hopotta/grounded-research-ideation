# Grounded Research Ideation

A research-ideation skill for turning a **well-defined research problem and a concrete challenge** into a literature-grounded, falsifiable proposal. It follows the IdeaScientist workflow: identify method-level gaps in work on the same problem, look for mechanisms that address a structurally similar challenge in another field, review the candidate idea, and write a proposal with citations that were read.

This is an agent skill, not a standalone proposal generator. The skill instructions guide a compatible coding/research assistant through the intellectual work. The included Python CLI scaffolds a run, searches and records papers, tracks reading digests, and checks required artifact structure and citation registration.

## When to use it

Use this skill when you have:

- A specific problem, including its input, desired output, and setting or constraints.
- One to three concrete ways current methods fail, with an observable symptom or example.
- A goal of proposing a new method, model, algorithm, architecture, training procedure, or technical framework.

It can also help answer “what has been tried and what is missing?” In that case, stop after the problem-definition and gap-finding stages and deliver `gaps.md`.

This skill is not intended for implementing or debugging a system, running or analyzing experiments, reproducing a paper, writing a survey or related-work section, summarizing a paper, reviewing a supplied draft, or choosing a research topic without a defined problem. Formulate the problem and challenge first for those broader topic-discovery requests.

## Workflow

The stages communicate through files in a run directory, so each stage can be inspected and resumed.

| Stage | Work | Main artifact |
| --- | --- | --- |
| 1. Intake | Define the problem and its challenge axes; restate each challenge without domain-specific nouns. | `problem.md` |
| 2. Gap finding | Search the same-problem literature and summarize what existing methods do and where their mechanisms fall short. | `gaps.md` |
| 3. Innovation | Search other fields for mechanisms that address the same underlying structure; compare and document candidate transfers. | `candidates.md` |
| 4. Review | Try to falsify each candidate's novelty and transfer claim; revise, reject, or let it survive. | `reviews.md` |
| 5. Report | Write a results-masked proposal with an evaluation plan, predictions, limitations, and grounded citations. | `proposal.md` |
| 6. Gate and deliver | Check artifacts and citation/read records; report the epistemic status and a cheap falsifying experiment. | Checked run directory |

The same-problem search regime looks for near-misses in the target problem area. The cross-setting regime removes the problem's own domain terms and searches for transferable mechanisms in structurally analogous settings. Cross-setting probes should cover at least three distinct sub-fields.

For each paper used as evidence, the workflow calls for a digest grounded in the full text. The final proposal describes plans and falsifiable predictions; it must not present unrun predictions as results. If the candidate ideas do not survive review, a negative result is a valid outcome.

## Inputs and outputs

### Inputs

Provide a problem definition with its input, desired output, and setting; one to three challenge axes with a failing desideratum, an observable, and a concrete example; and any methods already tried. The skill asks for a domain-neutral restatement of each challenge because that framing supports the cross-setting search.

### Run files

`ideasci.py init` creates these files from the templates:

| File | Purpose |
| --- | --- |
| `plan.md` | Stage status, decisions, selected candidate, and next action. |
| `problem.md` | Problem definition, challenge axes, prior attempts, and scope. |
| `gaps.md` | Same-problem mechanisms and method-level gaps. |
| `candidates.md` | Candidate mechanisms and their proposed transfer. |
| `reviews.md` | Evidence-based review verdicts and strongest objections. |
| `proposal.md` | The selected, falsifiable, results-masked research proposal. |
| `papers/_TEMPLATE.md` | Template for paper-reading digests. |
| `ledger.json` | Search trail, paper metadata, aliases, reading levels, and digest paths. |

The assistant fills the research artifacts. The CLI does not generate the gap analysis, candidate ideas, reviews, paper digests, or proposal for you. It records metadata returned by its search backends and checks defined structure and ledger-based reading/citation rules.

## Install

The skill is a folder; there is no package installer or third-party Python dependency. Install the folder in the skill directory for the assistant you use, or install it in a project when you want it scoped to that project:

| Assistant | User-level location | Project-level location |
| --- | --- | --- |
| Codex | `~/.agents/skills/grounded-research-ideation/` | `<repo>/.agents/skills/grounded-research-ideation/` |
| Claude Code | `~/.claude/skills/grounded-research-ideation/` | `<repo>/.claude/skills/grounded-research-ideation/` |

Copy the complete skill folder, preserving `SKILL.md`, `scripts/`, `assets/`, `references/`, and `agents/`. On older Codex builds, the user-level location may be `~/.codex/skills/grounded-research-ideation/`. Restart the assistant if the skills directory was created after its session started.

The helper CLI requires Python 3.8 or newer and uses only the Python standard library. Run commands from the skill folder with `python` on Windows or `python3` on macOS/Linux. The commands below use `demo-run` as an example run name; replace it with a short name of your choice.

## Start a run

Create a run directory. Standard mode is the default; `quick` reduces search and reading counts and should be labelled “lightly grounded” in the resulting work.

```sh
python scripts/ideasci.py init runs/demo-run
# or: python scripts/ideasci.py init runs/demo-run --mode quick
```

The command creates the templates and `ledger.json`. Provide the problem details in `problem.md` and have the assistant maintain `plan.md`, then validate intake:

```sh
python scripts/ideasci.py check --run runs/demo-run --stage problem
```

Search the same-problem regime for prior methods. Search results are stored in the run ledger:

```sh
python scripts/ideasci.py search "graph query latency" --run runs/demo-run --regime same --source arxiv,openalex
```

After filling `gaps.md`, search for structural analogues in other fields. Record a sub-field for every cross-setting probe:

```sh
python scripts/ideasci.py search "budgeted adaptive sampling" --run runs/demo-run --regime cross --probe "operations research" --source arxiv,openalex
```

These query phrases only illustrate the command shape; choose terms and probes that fit your own challenge.

For each paper the work relies on, read the paper and write a digest using `runs/demo-run/papers/_TEMPLATE.md`. Then register the completed digest with the CLI:

```sh
python scripts/ideasci.py read arxiv:2501.01234 --run runs/demo-run --level full
```

Replace the example paper ID with an ID returned by `search` or registered with `add`. The default digest location is `runs/demo-run/papers/<safe-id>.md`, with characters such as `:` replaced by `_` (for example, `arxiv_2501.01234.md`). Full-text reads need at least two text anchors such as section, equation, table, figure, or appendix references. Use `--level abstract` only for background citations; near-misses and mechanism sources need full-text reads. `--force` skips the anchor check and is recorded in the ledger and reported by `status` and `check`.

If a paper was found outside the CLI search, register it first, then write and register its digest:

```sh
python scripts/ideasci.py add --run runs/demo-run --id arxiv:2501.01234 --title "Example paper title" --year 2025 --field cs.IR
```

Replace the example ID, title, year, and field with the paper's actual metadata.

Continue through `candidates.md`, `reviews.md`, and `proposal.md`, following the stage instructions in `SKILL.md`. Check any stage independently with `--stage problem|gaps|candidates|reviews|proposal`, inspect progress with `status`, and run the final gate with:

```sh
python scripts/ideasci.py status --run runs/demo-run
python scripts/ideasci.py check --run runs/demo-run --stage all
```

`check` exits with code `0` when there are no errors and `1` when validity errors remain. `--strict` treats warnings as errors. CLI usage, I/O, or network errors exit with code `2`.

## Search backends

- **arXiv** is the default keyword search source. The helper retries a multi-term query with OR if the initial AND search returns no papers, unless `--no-relax` is set. It throttles arXiv requests to roughly one every three seconds.
- **OpenAlex** searches scholarly works across fields. The skill's retrieval notes state that an API key is expected; set `OPENALEX_API_KEY` if requests are refused or rate-limited. Select it with `--source openalex` or combine it with arXiv using `--source arxiv,openalex`.
- **Platform web search** can be used when a backend is unavailable. The CLI does not perform that web search; register papers you rely on with `add`. For retrospective runs, provide `--date` so the cutoff checker can validate them.

If network retrieval fails, the CLI exits with a fallback hint and does not log the failed search as completed coverage. Search queries are keyword-based, not semantic. Results from different sources with normalized matching titles are deduplicated in the ledger.

`init --cutoff YYYY-MM-DD` is for retrospective replay, not ordinary current research. It makes searches default to that date and `check` rejects cited papers dated later than the cutoff. The cutoff does not control model memory, and papers from manual/web search need dates recorded to be checked.

## Limits and epistemic status

- This workflow produces a proposal; it does not run experiments or establish that a proposal is feasible, novel, or effective. Novelty review is a proxy, not proof.
- The CLI checks document structure, required fields, query records, and whether citations are registered and marked read. It cannot confirm that a paper digest is accurate, that a citation supports a claim, or that the proposed mechanism is genuinely novel.
- The included helper does not fetch or parse full-text papers. A reader must access the text and create the digest; retrieval tools and access to papers depend on the assistant environment.
- This skill operationalizes parts of the IdeaScientist method. It does not include the paper's RL-trained roles or 4.7-million-paper corpus, and its keyword-search workflow is a weaker retrieval substitute.
- The cited method was evaluated on machine-learning methodology proposals. Its use in other scientific domains is untested by that evaluation.
- Research runs may contain notes, citations, and intermediate ideas. Add `runs/` to the consuming repository's `.gitignore` if those run artifacts should stay local.

## Acknowledgements

This skill was designed based on the research ideation workflow described in [*IdeaScientist: Orchestrating Agents for Grounded Scientific Ideation*](https://arxiv.org/abs/2610.04074) by Jiarui Liu et al. We thank the authors for the ideas that informed this skill's workflow, especially its combination of same-problem gap finding, cross-field mechanism transfer, and critical review. This repository is an independent skill implementation and is not an official artifact from the paper's authors.

## License

This project is released under the MIT License. See [LICENSE](LICENSE).

See [`SKILL.md`](SKILL.md) for the complete stage instructions, schemas, reading protocol, and delivery checklist. See [`evals/README.md`](evals/README.md) for development-only evaluation procedures; that folder is not part of the runtime skill package.
