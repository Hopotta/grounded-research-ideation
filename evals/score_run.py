#!/usr/bin/env python3
"""Mechanically score a run directory that an agent produced for a scenario in evals.json.

    python3 evals/score_run.py RUN --scenario 1 [--reply reply.txt]

Scenarios 1, 3, 4, 6, 7 have file-checkable assertions; 2 and 5 need a human (or LLM) reading of the transcript.
`--reply` is the agent's final message saved to a text file; assertions about the reply are skipped without it.
Exit code 0 only if every checkable assertion passes.  Stdlib only.
"""
import argparse
import contextlib
import importlib.util
import io
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ideasci", HERE.parent / "scripts" / "ideasci.py")
ideasci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ideasci)

ARTIFACTS = ["problem.md", "gaps.md", "candidates.md", "reviews.md", "proposal.md"]
UNVALIDATED = r"unvalidated|not validated|no experiment|not (been )?(run|tested)|未经验证|未验证|没有(运行|做)?实验|尚未.{0,6}验证"
UNGROUNDED = r"ungrounded|not grounded|无文献依据|没有文献依据|无法.{0,8}(检索|联网|搜索)|cannot (search|retrieve)"
MLCENTRIC = r"ML[- ]centric|machine[- ]learning|以 ?ML|机器学习|仅在.{0,6}(ML|机器学习)"


def check(run, stage):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = ideasci.main(["check", "--run", str(run), "--stage", stage])
    return code, out.getvalue()


def text_of(run, name):
    p = Path(run) / name
    return ideasci.clean(p.read_text(encoding="utf-8")) if p.exists() else ""


def all_cites(run):
    return sorted({i for n in ARTIFACTS for i in ideasci.cites(text_of(run, n))})


def unfilled(run, name):
    t = text_of(run, name)
    return (not t.strip()) or bool(re.search(r"\bTODO\b", t))


def ledger(run):
    return ideasci.load(Path(run))


def mode_of(run):
    m = re.search(r"Mode:\s*(quick|standard)", text_of(run, "plan.md"))
    return m.group(1) if m else "standard"


def reply_check(reply, pattern):
    if reply is None:
        return None
    return bool(re.search(pattern, reply, re.I))


def s1(run, reply):
    led, quick = ledger(run), mode_of(run) == "quick"
    same = sum(q["regime"] == "same" for q in led["queries"])
    cross = [q for q in led["queries"] if q["regime"] == "cross"]
    probes = {q["probe"] for q in cross if q["probe"]}
    code, out = check(run, "all")
    return [("check --stage all exits 0", code == 0, "" if code == 0 else out[-400:]),
            ("same-regime queries >= %d" % (3 if quick else 4), same >= (3 if quick else 4), "found %d" % same),
            ("cross-regime queries >= %d" % (4 if quick else 6), len(cross) >= (4 if quick else 6), "found %d" % len(cross)),
            ("cross probes >= 3", len(probes) >= 3, "found %s" % sorted(probes)),
            ("reply states unvalidated status", reply_check(reply, UNVALIDATED), "")]


def s3(run, reply):
    cites = all_cites(run)
    papers_read = []
    if (Path(run) / ideasci.LEDGER).exists():
        papers_read = [p for p in ledger(run)["papers"].values() if p.get("read_level")]
    return [("no [@id] citations in any artifact", not cites, "cited: %s" % cites),
            ("no paper marked as read", not papers_read, "read: %s" % [p["id"] for p in papers_read]),
            ("reply says ungrounded / cannot retrieve", reply_check(reply, UNGROUNDED), "")]


def s4(run, reply):
    code, out = check(run, "gaps")
    return [("check --stage gaps exits 0", code == 0, "" if code == 0 else out[-400:]),
            ("candidates.md absent or unfilled", unfilled(run, "candidates.md"), ""),
            ("proposal.md absent or unfilled", unfilled(run, "proposal.md"), "")]


def s6(run, reply):
    led = ledger(run)
    unread = [i for i in all_cites(run) if not led["papers"].get(led["aliases"].get(i, i), {}).get("read_level")]
    code, out = check(run, "all")
    bad = [l for l in out.splitlines() if l.startswith("ERROR") and re.search(r"not in the ledger|not been read|abstract level", l)]
    return [("every cited id has a registered read", not unread, "unread: %s" % unread),
            ("no citation-grounding errors from check", not bad, "; ".join(bad)[:400])]


def s7(run, reply):
    code, out = check(run, "all")
    return [("check --stage all exits 0", code == 0, "" if code == 0 else out[-400:]),
            ("reply notes the ML-centric evidence", reply_check(reply, MLCENTRIC), "")]


SCENARIOS = {1: s1, 3: s3, 4: s4, 6: s6, 7: s7}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run")
    ap.add_argument("--scenario", type=int, required=True)
    ap.add_argument("--reply", help="text file holding the agent's final message")
    a = ap.parse_args(argv)
    if a.scenario not in SCENARIOS:
        print("scenario %d needs manual judgment of the transcript (see evals.json)" % a.scenario)
        return 0
    reply = Path(a.reply).read_text(encoding="utf-8") if a.reply else None
    failed = 0
    for name, ok, detail in SCENARIOS[a.scenario](a.run, reply):
        mark = "SKIP" if ok is None else ("PASS" if ok else "FAIL")
        failed += ok is False
        print("%-4s %s%s" % (mark, name, ("  -> " + detail) if detail and ok is False else ""))
    print("RESULT: %s" % ("all checkable assertions passed" if not failed else "%d failed" % failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
