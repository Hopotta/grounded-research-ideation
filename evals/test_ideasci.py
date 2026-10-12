#!/usr/bin/env python3
"""Offline tests for scripts/ideasci.py and the skill package.  Run:  python3 evals/test_ideasci.py -v

All paper ids below are SYNTHETIC (arxiv:0000.xxxxx) and exist only inside temporary run directories.
Network calls are never made: http_get is patched.
"""
import contextlib
import importlib.util
import io
import json
import re
import shutil
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
FIX = HERE / "fixtures"

spec = importlib.util.spec_from_file_location("ideasci", SKILL / "scripts" / "ideasci.py")
ideasci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ideasci)


def cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = ideasci.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()


DIGEST = """# {title}

## What this paper does
A synthetic digest used only for testing the ledger gate. It describes a mechanism and its limits.

## Goal-by-goal answers
### Goal: mechanism and assumptions
The mechanism is described in Sec. 3 and formalised in Eq. 2; the main assumption is stated in Appendix A and
evaluated in Table 1. The answer is long enough to pass the minimum-length check for a full-text digest.
"""

PROBLEM = """# Problem
## Problem definition
- Input: user queries
- Desired output: ranked items
- Setting and constraints: large catalogue, strict latency budget
## Challenge axes
### Axis 1: latency
- Desideratum current solutions fail to meet: p99 latency
- Observable (metric or symptom): milliseconds at p99
- Concrete failing example: 3000 ms on long-tail queries
- Domain-neutral restatement: choose among very many items under a hard time budget
## What the requester already knows or tried
- distillation
## Out of scope
- hardware changes
## Mode
- standard
"""

GAPS = """# Gaps
## Axis: latency
### Prior work summary
Single-stage scorers dominate [@arxiv:0000.00001]; distillation shrinks the scorer [@arxiv:0000.00002].
### Gap 1
#### Gap
Prior methods shrink the scorer through distillation, but a smaller scorer still touches every item, so cost stays linear in catalogue size.
#### Near-miss methods and coverage
[@arxiv:0000.00001] and [@arxiv:0000.00002] come closest; both score all items. Search trail: queries 1-4.
#### Methodological deficiency
[algorithmic limitation] Per-item scoring cost is linear in catalogue size (see digest of 0000.00001, Sec. 3).
#### Why it matters
Serving teams cannot meet p99 budgets without more hardware.
#### Evidence route
A method whose latency grows sublinearly in catalogue size at equal accuracy would show the gap is closed.
"""

CANDS = """# Candidates
## Candidate C1
### Intuition
Cheaply narrow the candidate set before applying the expensive scorer.
### Gap it attacks
Axis latency, Gap 1: per-item scoring cost is linear in catalogue size.
### If improving prior candidate
n/a
### Source inspiration
- Source setting: database query planning
- Mechanism borrowed: filter-then-refine evaluation [@arxiv:0000.00003]
- Why it works there: a cheap predicate prunes most rows before the costly operator runs
- Novelty type: new topic
### How it maps to this problem
- Shared structure: both pick a few winners out of many items and have a cheap, recall-oriented proxy
- Adaptation: use a learned cheap proxy as the predicate; tune its threshold to a recall target
### Why it could work
- Plausibility given the source literature: pruning dominates cost in the source setting
- Key assumption: the cheap proxy keeps the true winners with high recall
### Novelty vs. closest in-domain work
Closest is [@arxiv:0000.00004], which prunes with a fixed heuristic; here the predicate is learned against a recall target.
### Main risk
Proxy recall collapses on long-tail queries.
"""

REVIEWS = """# Reviews
## Review of C1
### Verdict
survive
### Evidence
- [@arxiv:0000.00004] prunes with a fixed rule, so the learned recall-targeted predicate is a real difference.
### Strongest objection
Learned pruning may be no better than the fixed rule on long-tail queries.
"""

PLAN = "# Plan\n- Mode: standard\n- Selected candidate: C1\n## Status\n## Decisions log\n## Next action\n"

PROPOSAL = """# Recall-targeted filter-then-refine for sublinear-cost ranking
## Topic relevance
Efficient ranking; sub-area: serving latency.
## One-sentence thesis
Pruning candidates with a learned proxy tuned to a recall target makes ranking cost sublinear in catalogue size.
## Core problem
Per-item scoring is linear in catalogue size, which breaks p99 budgets [@arxiv:0000.00001].
## Key novelty
Recall-targeted learned predicate, borrowed from filter-then-refine evaluation in database query planning [@arxiv:0000.00003].
## Problem definition
Given a query and a catalogue, return the top-k items under a latency budget.
## Key terms
Predicate: a cheap test that discards items.
## Related work
Distillation shrinks the scorer but not the number of scored items [@arxiv:0000.00002]; fixed-heuristic pruning exists [@arxiv:0000.00004]; background on ranking [@oa:W100].
## Method
Stage one scores items with a small proxy and keeps those above a threshold chosen for a recall target; stage two applies the full scorer.
## Model details
Proxy: a small encoder trained with a recall-weighted loss; threshold calibrated on held-out queries.
## Comparison to state of the art
Versus [@arxiv:0000.00004]: the predicate is learned and the threshold is tied to a recall target rather than fixed.
## Proposed evaluation
Datasets, baselines, latency at fixed recall, and an ablation of the threshold rule (a plan; no results).
## Falsifiable predictions
- **P1:** latency grows sublinearly in catalogue size at equal top-k accuracy. *Falsified if:* latency scales linearly beyond 10x catalogue growth.
- **P2:** long-tail recall stays above the target. *Falsified if:* long-tail recall falls more than five points below the target.
## Limitations
- Depends on proxy recall.
- Adds a threshold to calibrate.
- Gains shrink for small catalogues.
"""

PAPERS = [  # id, title, field, level
    ("arxiv:0000.00001", "Single stage scorers at scale", "cs.IR", "full"),
    ("arxiv:0000.00002", "Distilling rankers", "cs.IR", "full"),
    ("arxiv:0000.00003", "Filter then refine query evaluation", "cs.DB", "full"),
    ("arxiv:0000.00004", "Heuristic candidate pruning for ranking", "cs.IR", "full"),
    ("oa:W100", "Background on ranking", "Information Systems", "abstract"),
]


def make_run(tmp: Path, **override) -> Path:
    run = tmp / "run"
    assert cli("init", run)[0] == 0
    files = {"problem.md": PROBLEM, "gaps.md": GAPS, "candidates.md": CANDS, "reviews.md": REVIEWS,
             "plan.md": PLAN, "proposal.md": PROPOSAL}
    files.update(override)
    for name, text in files.items():
        (run / name).write_text(text, encoding="utf-8")
    for pid, title, field, level in PAPERS:
        assert cli("add", "--run", run, "--id", pid, "--title", title, "--field", field, "--year", 2024)[0] == 0
        d = run / "papers" / (ideasci.safe_id(pid) + ".md")
        d.write_text(DIGEST.format(title=title), encoding="utf-8")
        code, out, err = cli("read", pid, "--run", run, "--level", level)
        assert code == 0, err
    # search trail: 4 same-problem queries + 6 cross-setting queries over 3 probes
    led = ideasci.load(run)
    trail = [("same", "")] * 4 + [("cross", "databases")] * 2 + [("cross", "operations research")] * 2 + [("cross", "networking")] * 2
    for i, (reg, probe) in enumerate(trail, 1):
        led["queries"].append({"n": i, "q": "q%d" % i, "regime": reg, "probe": probe, "ids": []})
    ideasci.save(run, led)
    return run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def check(self, run, stage="all", strict=False):
        args = ["check", "--run", run, "--stage", stage] + (["--strict"] if strict else [])
        return cli(*args)


class TestIds(unittest.TestCase):
    def test_normalize(self):
        n = ideasci.normalize_id
        self.assertEqual(n("2610.04074v1"), "arxiv:2610.04074")
        self.assertEqual(n("https://arxiv.org/abs/2610.04074v3"), "arxiv:2610.04074")
        self.assertEqual(n("https://arxiv.org/pdf/2610.04074.pdf"), "arxiv:2610.04074")
        self.assertEqual(n("arXiv:hep-th/9901001v2".replace("arXiv", "arxiv")), "arxiv:hep-th/9901001")
        self.assertEqual(n("https://openalex.org/w123".replace("w", "W")), "oa:W123")
        self.assertEqual(n("10.1145/356571.356573"), "doi:10.1145/356571.356573")
        self.assertEqual(n("[@arxiv:2401.00001]"), "arxiv:2401.00001")
        with self.assertRaises(ideasci.UsageError):
            n("not an id")

    def test_cite_extraction(self):
        t = "see [@arxiv:2401.00001v2], and [@doi:10.1145/1.2]. Also [@oa:W9]; email a@b.c"
        self.assertEqual(ideasci.cites(t), ["arxiv:2401.00001", "doi:10.1145/1.2", "oa:W9"])


class TestParsers(unittest.TestCase):
    def test_arxiv(self):
        recs = ideasci.parse_arxiv((FIX / "arxiv_sample.xml").read_bytes())
        self.assertEqual(len(recs), 2)
        r = recs[0]
        self.assertEqual(r["id"], "arxiv:0000.00011")
        self.assertEqual(r["title"], "Two-Stage Candidate Retrieval for Fast Ranking")
        self.assertEqual(r["field"], "cs.IR")
        self.assertEqual((r["year"], r["date"]), (2024, "2024-03-01"))
        self.assertEqual(r["authors"], "Ada Example, Bo Sample, Cy Test et al.")
        self.assertEqual(recs[1]["id"], "arxiv:hep-th/9901001")

    def test_arxiv_official_docs_example(self):
        """Response copied verbatim from arXiv's own API docs (info.arxiv.org/help/api/basics.html):
        redundant xmlns on every element, old-style id without version, wrapped title."""
        recs = ideasci.parse_arxiv((FIX / "arxiv_official_example.xml").read_bytes())
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["id"], "arxiv:hep-ex/0307015")
        self.assertEqual(r["title"], "Multi-Electron Production at High Transverse Momenta in ep Collisions at HERA")
        self.assertEqual((r["field"], r["year"], r["authors"]), ("hep-ex", 2003, "H1 Collaboration"))
        self.assertTrue(r["abstract"].startswith("Multi-electron production is studied"))
        self.assertEqual(r["url"], "https://arxiv.org/abs/hep-ex/0307015")

    def test_arxiv_error_feed(self):
        with self.assertRaises(RuntimeError):
            ideasci.parse_arxiv((FIX / "arxiv_error.xml").read_bytes())

    def test_openalex(self):
        recs = ideasci.parse_openalex((FIX / "openalex_sample.json").read_bytes())
        self.assertEqual(recs[0]["id"], "oa:W100")
        # positions: We0 study1 a2 first-stage3 filter4 then5 fine-grained6 a7 fine-grained8
        self.assertEqual(recs[0]["abstract"], "We study a first-stage filter then fine-grained a fine-grained")
        self.assertEqual(recs[0]["field"], "Information Systems")
        self.assertEqual(recs[1]["abstract"], "")
        self.assertEqual(recs[1]["field"], "Management Science and Operations Research")

    def test_query_builders(self):
        self.assertEqual(ideasci.arxiv_expr('two-stage ranking latency'), 'all:"two-stage" AND all:ranking AND all:latency')
        self.assertEqual(ideasci.arxiv_expr('"filter then refine" db', "OR"), 'all:"filter then refine" OR all:db')
        u = ideasci.arxiv_url("all:x", 5, "2020-01-02", "2025-12-31")
        self.assertIn("submittedDate", u)
        self.assertIn("202001020000", u)
        self.assertIn("202512312359", u)
        self.assertIn("api_key=K", ideasci.openalex_url("q", 5, None, "2025-12-31", "K"))
        self.assertIn("to_publication_date:2025-12-31", ideasci.openalex_url("q", 5, None, "2025-12-31", None))


class TestSearchFlow(Base):
    def setUp(self):
        super().setUp()
        self.run_dir = self.tmp / "run"
        cli("init", self.run_dir)
        self.p1 = mock.patch.object(ideasci, "_throttle_arxiv", lambda: None)
        self.p1.start()

    def tearDown(self):
        self.p1.stop()
        super().tearDown()

    def test_search_logs_and_dedupes_across_sources(self):
        def fake(url, timeout=30):
            return (FIX / ("arxiv_sample.xml" if "arxiv.org" in url else "openalex_sample.json")).read_bytes()
        with mock.patch.object(ideasci, "http_get", fake):
            code, out, err = cli("search", "two-stage ranking", "--run", self.run_dir, "--regime", "cross",
                                 "--probe", "databases", "--source", "arxiv,openalex")
        self.assertEqual(code, 0, err)
        led = ideasci.load(self.run_dir)
        # the OpenAlex copy of "Two-Stage Candidate Retrieval..." must dedupe onto the arXiv record
        self.assertEqual(len(led["papers"]), 3)
        self.assertEqual(led["aliases"].get("oa:W100"), "arxiv:0000.00011")
        q = led["queries"][0]
        self.assertEqual((q["regime"], q["probe"]), ("cross", "databases"))
        self.assertIn("search #1", out)

    def test_and_then_or_relaxation(self):
        calls = []

        def fake(url, timeout=30):
            calls.append(url)
            empty = b"<feed xmlns='http://www.w3.org/2005/Atom'></feed>"
            return empty if "+AND+" in url else (FIX / "arxiv_sample.xml").read_bytes()
        with mock.patch.object(ideasci, "http_get", fake):
            code, out, _ = cli("search", "alpha beta", "--run", self.run_dir)
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 2)
        self.assertIn("relaxed to OR", out)
        self.assertTrue(ideasci.load(self.run_dir)["queries"][0]["relaxed"])

    def test_network_failure_exit_2_with_fallback_hint(self):
        def boom(url, timeout=30):
            raise urllib.error.URLError("blocked by sandbox")
        with mock.patch.object(ideasci, "http_get", boom):
            code, out, err = cli("search", "anything", "--run", self.run_dir)
        self.assertEqual(code, 2)
        self.assertIn("network unreachable or blocked", err)
        self.assertIn("ideasci.py add", err)
        self.assertEqual(ideasci.load(self.run_dir)["queries"], [])  # failed searches are not logged as coverage

    def test_partial_failure_is_not_fatal(self):
        def fake(url, timeout=30):
            if "openalex" in url:
                raise urllib.error.HTTPError(url, 403, "forbidden", {}, None)
            return (FIX / "arxiv_sample.xml").read_bytes()
        with mock.patch.object(ideasci, "http_get", fake):
            code, out, err = cli("search", "x", "--run", self.run_dir, "--source", "arxiv,openalex")
        self.assertEqual(code, 0)
        self.assertIn("OPENALEX_API_KEY", err)

    def test_bad_date(self):
        code, _, err = cli("search", "x", "--run", self.run_dir, "--before", "2025/01/01")
        self.assertEqual(code, 2)


class TestReadGate(Base):
    def setUp(self):
        super().setUp()
        self.run_dir = self.tmp / "run"
        cli("init", self.run_dir)
        cli("add", "--run", self.run_dir, "--id", "arxiv:0000.00001", "--title", "T one")

    def digest(self, text):
        (self.run_dir / "papers" / "arxiv_0000.00001.md").write_text(text, encoding="utf-8")

    def test_unknown_id(self):
        code, _, err = cli("read", "arxiv:9999.99999", "--run", self.run_dir)
        self.assertEqual(code, 2)
        self.assertIn("not in the ledger", err)

    def test_missing_digest(self):
        self.assertEqual(cli("read", "arxiv:0000.00001", "--run", self.run_dir)[0], 2)

    def test_todo_digest_rejected(self):
        self.digest("# T\n## What this paper does\nTODO\n" + "x" * 400)
        self.assertEqual(cli("read", "arxiv:0000.00001", "--run", self.run_dir)[0], 2)

    def test_full_requires_anchors_but_abstract_does_not(self):
        self.digest("# T\n## What this paper does\n" + "A plain summary without any locator. " * 12)
        code, _, err = cli("read", "arxiv:0000.00001", "--run", self.run_dir, "--level", "full")
        self.assertEqual(code, 2)
        self.assertIn("anchors", err)
        self.assertEqual(cli("read", "arxiv:0000.00001", "--run", self.run_dir, "--level", "abstract")[0], 0)
        self.assertEqual(ideasci.load(self.run_dir)["papers"]["arxiv:0000.00001"]["read_level"], "abstract")

    def test_full_not_downgraded(self):
        self.digest(DIGEST.format(title="T"))
        self.assertEqual(cli("read", "arxiv:0000.00001", "--run", self.run_dir, "--level", "full")[0], 0)
        self.assertEqual(cli("read", "arxiv:0000.00001", "--run", self.run_dir, "--level", "abstract")[0], 0)
        self.assertEqual(ideasci.load(self.run_dir)["papers"]["arxiv:0000.00001"]["read_level"], "full")


class TestGoodRun(Base):
    def test_good_run_passes_all_stages_strict(self):
        run = make_run(self.tmp)
        code, out, _ = self.check(run, "all", strict=True)
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)

    def test_status_reports_filled(self):
        run = make_run(self.tmp)
        _, out, _ = cli("status", "--run", run)
        self.assertIn("read full 4, abstract 1", out)
        self.assertIn("selected candidate: C1", out)


class TestNegatives(Base):
    """Each case breaks exactly one rule; the gate must fail (or warn, for heuristics) with a pointed message."""

    def expect_error(self, files, needle, stage="all"):
        run = make_run(self.tmp, **files)
        code, out, _ = self.check(run, stage)
        self.assertEqual(code, 1, out)
        self.assertIn(needle, out)

    def expect_warn_only(self, files, needle, stage="all"):
        run = make_run(self.tmp, **files)
        code, out, _ = self.check(run, stage)
        self.assertEqual(code, 0, out)
        self.assertIn("WARN", out)
        self.assertIn(needle, out)
        self.assertEqual(self.check(run, stage, strict=True)[0], 1)  # --strict promotes warnings

    # ---- citation grounding (the paper's read-before-cite gate)
    def test_fabricated_citation(self):
        self.expect_error({"proposal.md": PROPOSAL.replace("[@oa:W100]", "[@arxiv:9999.99999]")},
                          "not in the ledger")

    def test_unread_citation(self):
        run = make_run(self.tmp)
        cli("add", "--run", run, "--id", "arxiv:0000.00005", "--title", "Seen but never read")
        (run / "proposal.md").write_text(PROPOSAL.replace("[@oa:W100]", "[@arxiv:0000.00005]"), encoding="utf-8")
        code, out, _ = self.check(run, "proposal")
        self.assertEqual(code, 1)
        self.assertIn("has not been read", out)

    def test_near_miss_only_abstract_level(self):
        run = make_run(self.tmp)
        led = ideasci.load(run)
        led["papers"]["arxiv:0000.00002"]["read_level"] = "abstract"
        ideasci.save(run, led)
        code, out, _ = self.check(run, "gaps")
        self.assertEqual(code, 1)
        self.assertIn("only at abstract level", out)

    def test_source_only_abstract_level(self):
        run = make_run(self.tmp)
        led = ideasci.load(run)
        led["papers"]["arxiv:0000.00003"]["read_level"] = "abstract"
        ideasci.save(run, led)
        code, out, _ = self.check(run, "candidates")
        self.assertEqual(code, 1)
        self.assertIn("only at abstract level", out)

    # ---- gap finder gates
    def test_three_gaps(self):
        extra = GAPS + "\n### Gap 2\n#### Gap\nx but y\n#### Near-miss methods and coverage\n[@arxiv:0000.00001][@arxiv:0000.00002]\n" \
                       "#### Methodological deficiency\n[missing mechanism] z\n#### Why it matters\nw\n#### Evidence route\nr\n" \
                       "\n### Gap 3\n#### Gap\nx but y\n#### Near-miss methods and coverage\n[@arxiv:0000.00001][@arxiv:0000.00002]\n" \
                       "#### Methodological deficiency\n[missing mechanism] z\n#### Why it matters\nw\n#### Evidence route\nr\n"
        self.expect_error({"gaps.md": extra}, "caps this at two", "gaps")

    def test_single_near_miss(self):
        self.expect_error({"gaps.md": GAPS.replace("[@arxiv:0000.00001] and [@arxiv:0000.00002] come closest",
                                                   "[@arxiv:0000.00001] comes closest")},
                          "need >= 2", "gaps")

    def test_single_near_miss_declared(self):
        run = make_run(self.tmp, **{"gaps.md": GAPS.replace(
            "[@arxiv:0000.00001] and [@arxiv:0000.00002] come closest", "Only one real near miss: [@arxiv:0000.00001]")})
        self.assertEqual(self.check(run, "gaps")[0], 0)

    def test_axis_mismatch(self):
        self.expect_error({"gaps.md": GAPS.replace("## Axis: latency", "## Axis: privacy")},
                          "does not match an axis in problem.md", "gaps")

    def test_missing_gap_field(self):
        self.expect_error({"gaps.md": GAPS.replace("#### Evidence route", "#### Misc")}, "missing '#### evidence route'", "gaps")

    def test_not_contrast_form_is_warning(self):
        self.expect_warn_only({"gaps.md": GAPS.replace(", but a smaller scorer", ". A smaller scorer")}, "contrast form", "gaps")

    def test_untagged_deficiency_is_warning(self):
        self.expect_warn_only({"gaps.md": GAPS.replace("[algorithmic limitation] ", "")}, "recognised tag", "gaps")

    # ---- innovator gates
    def test_missing_novelty_type(self):
        self.expect_error({"candidates.md": CANDS.replace("- Novelty type: new topic\n", "")}, "Novelty type", "candidates")

    def test_source_without_citation(self):
        self.expect_error({"candidates.md": CANDS.replace(" [@arxiv:0000.00003]", "")}, "cites no paper id", "candidates")

    def test_missing_transfer_structure_is_warning(self):
        self.expect_warn_only({"candidates.md": CANDS.replace("- Shared structure:", "- Similarity:")}, "Shared structure", "candidates")

    def test_pseudocode_at_idea_stage_is_warning(self):
        self.expect_warn_only({"candidates.md": CANDS.replace("- Adaptation:", "```\nfor x in items: pass\n```\n- Adaptation:")},
                              "pseudocode", "candidates")

    def test_rediscovery_flag(self):
        self.expect_warn_only({"candidates.md": CANDS.replace("[@arxiv:0000.00004]", "[@arxiv:0000.00003]")},
                              "rediscovery", "candidates")

    def test_same_field_source_flag(self):
        run = make_run(self.tmp)
        led = ideasci.load(run)
        led["papers"]["arxiv:0000.00003"]["field"] = "cs.IR"
        ideasci.save(run, led)
        code, out, _ = self.check(run, "candidates")
        self.assertEqual(code, 0)
        self.assertIn("share field cs.IR", out)

    # ---- reviewer gates
    def test_bad_verdict(self):
        self.expect_error({"reviews.md": REVIEWS.replace("survive", "looks fine")}, "survive | revise | reject", "reviews")

    def test_revise_without_dimension(self):
        self.expect_error({"reviews.md": REVIEWS.replace("survive", "revise")}, "weakest dimension", "reviews")

    def test_unsurvived_candidate_warns_at_proposal(self):
        self.expect_warn_only({"reviews.md": REVIEWS.replace("survive", "revise: transfer assumption")}, "review gate", "proposal")

    # ---- report writer gates
    def test_thesis_too_long(self):
        long = " ".join(["word"] * 31) + "."
        self.expect_error({"proposal.md": PROPOSAL.replace(
            "Pruning candidates with a learned proxy tuned to a recall target makes ranking cost sublinear in catalogue size.", long)},
            "must be under 30", "proposal")

    def test_thesis_with_metric_is_warning(self):
        self.expect_warn_only({"proposal.md": PROPOSAL.replace("makes ranking cost sublinear in catalogue size",
                                                               "cuts cost by 40%")}, "metric numbers", "proposal")

    def test_too_few_limitations(self):
        self.expect_error({"proposal.md": PROPOSAL.replace("- Adds a threshold to calibrate.\n- Gains shrink for small catalogues.\n", "")},
                          "need three to five", "proposal")

    def test_prediction_without_refutation(self):
        self.expect_error({"proposal.md": PROPOSAL.replace(" *Falsified if:* latency scales linearly beyond 10x catalogue growth.", "")},
                          "Falsified if", "proposal")

    def test_missing_section(self):
        self.expect_error({"proposal.md": PROPOSAL.replace("## Key terms\nPredicate: a cheap test that discards items.\n", "")},
                          "missing '## Key Terms'", "proposal")

    def test_technical_details_alias_accepted(self):
        run = make_run(self.tmp, **{"proposal.md": PROPOSAL.replace("## Model details", "## Technical details")})
        self.assertEqual(self.check(run, "proposal")[0], 0)

    def test_selected_source_not_carried_through(self):
        self.expect_error({"proposal.md": PROPOSAL.replace(" [@arxiv:0000.00003]", "")}, "does not cite the mechanism source", "proposal")

    def test_measured_result_language_is_warning(self):
        self.expect_warn_only({"proposal.md": PROPOSAL.replace("Datasets, baselines, latency at fixed recall",
                                                               "Our method achieves 31% lower latency; datasets, baselines")},
                              "measured result", "proposal")

    def test_unfilled_todo(self):
        self.expect_error({"proposal.md": PROPOSAL.replace("Predicate: a cheap test that discards items.", "TODO")},
                          "unfilled TODO", "proposal")

    def test_no_selected_candidate_is_warning(self):
        self.expect_warn_only({"plan.md": PLAN.replace("Selected candidate: C1", "Selected candidate: TODO")},
                              "no 'Selected candidate", "proposal")

    def test_thin_search_trail_is_warning_in_all(self):
        run = make_run(self.tmp)
        led = ideasci.load(run)
        led["queries"] = [q for q in led["queries"] if q["probe"] != "networking" and q["probe"] != "operations research"]
        ideasci.save(run, led)
        code, out, _ = self.check(run, "all")
        self.assertEqual(code, 0)
        self.assertIn("distinct cross-regime probe", out)


class TestCutoff(Base):
    def test_init_writes_cutoff_and_search_defaults_before(self):
        run = self.tmp / "run"
        self.assertEqual(cli("init", run, "--cutoff", "2024-06-30")[0], 0)
        self.assertEqual(ideasci.plan_cutoff(run), "2024-06-30")
        seen = []
        with mock.patch.object(ideasci, "_throttle_arxiv", lambda: None), \
             mock.patch.object(ideasci, "http_get", lambda url, timeout=30: seen.append(url) or (FIX / "arxiv_sample.xml").read_bytes()):
            code, out, _ = cli("search", "ranking", "--run", run)
        self.assertEqual(code, 0)
        self.assertIn("202406302359", seen[0])
        self.assertIn("cutoff=2024-06-30", out)
        self.assertEqual(ideasci.load(run)["queries"][0]["before"], "2024-06-30")

    def test_later_before_is_refused(self):
        run = self.tmp / "run"
        cli("init", run, "--cutoff", "2024-06-30")
        code, _, err = cli("search", "x", "--run", run, "--before", "2025-01-01")
        self.assertEqual(code, 2)
        self.assertIn("later than this run's cutoff", err)

    def test_no_cutoff_means_no_restriction(self):
        run = self.tmp / "run"
        cli("init", run)
        self.assertIsNone(ideasci.plan_cutoff(run))
        self.assertIn("Cutoff: none", (run / "plan.md").read_text())

    def test_cited_paper_after_cutoff_is_error(self):
        run = make_run(self.tmp)
        (run / "plan.md").write_text(PLAN.replace("- Mode: standard", "- Mode: standard\n- Cutoff: 2024-06-30"), encoding="utf-8")
        led = ideasci.load(run)
        led["papers"]["arxiv:0000.00003"]["date"] = "2024-09-01"
        for pid in ("arxiv:0000.00001", "arxiv:0000.00002", "arxiv:0000.00004", "oa:W100"):
            led["papers"][pid]["date"] = "2023-01-01"
        for q in led["queries"]:
            q["before"] = "2024-06-30"
        ideasci.save(run, led)
        code, out, _ = self.check(run, "all")
        self.assertEqual(code, 1)
        self.assertIn("arxiv:0000.00003 is dated 2024-09-01, after this run's cutoff 2024-06-30", out)

    def test_cutoff_clean_run_passes_but_loose_queries_and_missing_dates_warn(self):
        run = make_run(self.tmp)
        (run / "plan.md").write_text(PLAN.replace("- Mode: standard", "- Mode: standard\n- Cutoff: 2024-06-30"), encoding="utf-8")
        led = ideasci.load(run)
        for pid in ("arxiv:0000.00001", "arxiv:0000.00002", "arxiv:0000.00003", "arxiv:0000.00004"):
            led["papers"][pid]["date"] = "2023-01-01"
        led["papers"]["oa:W100"]["year"] = None   # no date, no year
        ideasci.save(run, led)
        code, out, _ = self.check(run, "all")
        self.assertEqual(code, 0, out)
        self.assertIn("not restricted to the cutoff", out)
        self.assertIn("oa:W100 has no date", out)

    def test_year_only_after_cutoff_year_is_error(self):
        run = make_run(self.tmp)
        (run / "plan.md").write_text(PLAN.replace("- Mode: standard", "- Mode: standard\n- Cutoff: 2023-06-30"), encoding="utf-8")
        code, out, _ = self.check(run, "proposal")   # fixtures carry year 2024 only
        self.assertEqual(code, 1)
        self.assertIn("is from 2024, after this run's cutoff", out)

    def test_add_with_date(self):
        run = self.tmp / "run"
        cli("init", run)
        cli("add", "--run", run, "--id", "arxiv:0000.00009", "--title", "Dated", "--date", "2022-02-03")
        rec = ideasci.load(run)["papers"]["arxiv:0000.00009"]
        self.assertEqual((rec["date"], rec["year"]), ("2022-02-03", 2022))
        self.assertEqual(cli("add", "--run", run, "--id", "arxiv:0000.00010", "--title", "Bad", "--date", "2022/02/03")[0], 2)


class TestForcedTrace(Base):
    def setUp(self):
        super().setUp()
        self.run_dir = self.tmp / "run"
        cli("init", self.run_dir)
        cli("add", "--run", self.run_dir, "--id", "arxiv:0000.00001", "--title", "T one")
        (self.run_dir / "papers" / "arxiv_0000.00001.md").write_text(
            "# T\n## What this paper does\n" + "A plain summary without any locator. " * 12, encoding="utf-8")

    def test_force_is_recorded_and_surfaced(self):
        code, out, _ = cli("read", "arxiv:0000.00001", "--run", self.run_dir, "--level", "full", "--force")
        self.assertEqual(code, 0)
        self.assertIn("--force", out)
        self.assertTrue(ideasci.load(self.run_dir)["papers"]["arxiv:0000.00001"]["forced"])
        self.assertIn("forced reads (anchor check skipped): 1", cli("status", "--run", self.run_dir)[1])

    def test_check_warns_when_a_forced_paper_is_cited(self):
        run = make_run(self.tmp)
        led = ideasci.load(run)
        led["papers"]["arxiv:0000.00003"]["forced"] = True
        ideasci.save(run, led)
        code, out, _ = self.check(run, "all")
        self.assertEqual(code, 0)
        self.assertIn("registered with --force", out)
        self.assertIn("arxiv:0000.00003", out)
        self.assertEqual(self.check(run, "all", strict=True)[0], 1)

    def test_unforced_full_read_clears_flag_and_abstract_never_forced(self):
        cli("read", "arxiv:0000.00001", "--run", self.run_dir, "--level", "full", "--force")
        (self.run_dir / "papers" / "arxiv_0000.00001.md").write_text(DIGEST.format(title="T"), encoding="utf-8")
        cli("read", "arxiv:0000.00001", "--run", self.run_dir, "--level", "full")
        self.assertFalse(ideasci.load(self.run_dir)["papers"]["arxiv:0000.00001"]["forced"])

    def test_good_run_has_no_forced_warning(self):
        run = make_run(self.tmp)
        self.assertNotIn("--force", self.check(run, "all", strict=True)[1])


class TestScorer(Base):
    def setUp(self):
        super().setUp()
        spec2 = importlib.util.spec_from_file_location("score_run", HERE / "score_run.py")
        self.sr = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(self.sr)

    def score(self, run, n, reply=None):
        out = io.StringIO()
        args = [str(run), "--scenario", str(n)]
        if reply is not None:
            rp = self.tmp / "reply.txt"
            rp.write_text(reply, encoding="utf-8")
            args += ["--reply", str(rp)]
        with contextlib.redirect_stdout(out):
            code = self.sr.main(args)
        return code, out.getvalue()

    def test_scenario1_good_run(self):
        run = make_run(self.tmp)
        code, out = self.score(run, 1, "This proposal is unvalidated: no experiment was run.")
        self.assertEqual(code, 0, out)

    def test_scenario1_fails_on_thin_trail_and_missing_status(self):
        run = make_run(self.tmp)
        led = ideasci.load(run)
        led["queries"] = [q for q in led["queries"] if q["probe"] == "databases" or q["regime"] == "same"]
        ideasci.save(run, led)
        code, out = self.score(run, 1, "Here is your proposal.")
        self.assertEqual(code, 1)
        self.assertIn("FAIL cross probes >= 3", out)
        self.assertIn("FAIL reply states unvalidated", out)

    def test_scenario1_without_reply_skips_reply_assertion(self):
        run = make_run(self.tmp)
        code, out = self.score(run, 1)
        self.assertEqual(code, 0)
        self.assertIn("SKIP reply states unvalidated", out)

    def test_scenario3_detects_fabrication(self):
        run = make_run(self.tmp)   # has citations and read papers: exactly what scenario 3 forbids
        code, out = self.score(run, 3, "ungrounded brainstorm")
        self.assertEqual(code, 1)
        self.assertIn("FAIL no [@id] citations", out)

    def test_scenario3_clean_run_passes(self):
        run = self.tmp / "run"
        cli("init", run)
        self.assertEqual(self.score(run, 3, "I could not search, so this is an ungrounded brainstorm.")[0], 0)

    def test_scenario4_gap_only(self):
        run = make_run(self.tmp)
        (run / "candidates.md").write_text("# Candidates\nTODO\n", encoding="utf-8")
        (run / "proposal.md").write_text("# P\nTODO\n", encoding="utf-8")
        self.assertEqual(self.score(run, 4)[0], 0)
        run2 = make_run(self.tmp / "b") if (self.tmp / "b").mkdir() is None else None
        code, out = self.score(run2, 4)           # complete run: candidates and proposal exist -> must fail
        self.assertEqual(code, 1)
        self.assertIn("FAIL candidates.md absent or unfilled", out)

    def test_scenario6_unread_citation(self):
        run = make_run(self.tmp)
        cli("add", "--run", run, "--id", "arxiv:0000.00005", "--title", "Never read")
        (run / "proposal.md").write_text(PROPOSAL.replace("[@oa:W100]", "[@arxiv:0000.00005]"), encoding="utf-8")
        code, out = self.score(run, 6)
        self.assertEqual(code, 1)
        self.assertIn("arxiv:0000.00005", out)

    def test_scenario7_and_manual_scenarios(self):
        run = make_run(self.tmp)
        self.assertEqual(self.score(run, 7, "Note the paper's evidence is ML-centric.")[0], 0)
        code, out = self.score(run, 2)
        self.assertEqual(code, 0)
        self.assertIn("manual", out)


class TestPackage(unittest.TestCase):
    def test_frontmatter_and_layout(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        self.assertTrue(m, "no frontmatter")
        fm = dict(re.findall(r"^([a-z\-]+):\s*(.*)$", m.group(1), re.M))
        self.assertEqual(set(fm), {"name", "description"})
        self.assertEqual(fm["name"], SKILL.name)
        self.assertRegex(fm["name"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(fm["name"]), 64)
        self.assertLessEqual(len(fm["description"]), 500, "Codex truncates/rejects descriptions over 500 chars")
        self.assertNotIn("<", fm["description"])
        self.assertNotIn(">", fm["description"])
        self.assertEqual(len(m.group(1).splitlines()), 2, "frontmatter fields must be single-line")
        self.assertLess(len(text.splitlines()), 500)

    def test_every_referenced_file_exists(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for rel in set(re.findall(r"`((?:references|assets|scripts|agents)/[A-Za-z0-9_./-]+)`", text)):
            self.assertTrue((SKILL / rel.rstrip("/")).exists(), "SKILL.md references missing path " + rel)

    def test_docs_use_only_real_cli_flags(self):
        parser = ideasci.build_parser()
        subs = parser._subparsers._group_actions[0].choices
        valid = {name: {s for a in sp._actions for s in a.option_strings} for name, sp in subs.items()}
        files = [SKILL / "SKILL.md"] + sorted((SKILL / "references").glob("*.md"))
        seen = 0
        for f in files:
            for line in f.read_text(encoding="utf-8").splitlines():
                m = re.search(r"(?:ideasci\.py|\$IDEASCI)\s+(init|search|add|read|status|check)\b([^`\n]*)", line)  # stop at the closing backtick
                if not m:
                    continue
                seen += 1
                for flag in re.findall(r"(?<![\w-])(--[a-z][a-z\-]*)", m.group(2)):
                    self.assertIn(flag, valid[m.group(1)], "%s: `%s` has no flag %s" % (f.name, m.group(1), flag))
        self.assertGreater(seen, 15, "docs should show real command lines (SKILL.md uses $IDEASCI)")

    def test_templates_have_the_headings_the_checker_requires(self):
        t = SKILL / "assets" / "templates"
        self.assertIn("Falsified if", (t / "proposal.md").read_text())
        for h in ideasci.GAP_FIELDS:
            self.assertIn(h.replace("near miss", "near-miss"), (t / "gaps.md").read_text().lower())

    def test_fresh_template_run_fails_closed(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            cli("init", tmp / "r")
            code, out, _ = cli("check", "--run", tmp / "r")
            self.assertEqual(code, 1)
            self.assertIn("unfilled TODO", out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
