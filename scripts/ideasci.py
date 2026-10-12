#!/usr/bin/env python3
"""ideasci - evidence ledger, literature search and stage gates for grounded research ideation.

Implements the mechanical parts of the IdeaScientist workflow (arXiv:2610.04074):
  * a search trail with two query regimes (same-problem vs cross-setting),
  * "read before cite": a paper can only be cited after a digest of it is registered,
  * deterministic validity gates for each stage artifact (schema, caps, citation grounding).

Stdlib only (Python >= 3.8).  Exit codes: 0 ok, 1 gate errors, 2 usage / IO / network error.

  ideasci.py init RUN [--mode quick|standard] [--cutoff YYYY-MM-DD]
  ideasci.py search QUERY --run RUN [--regime same|cross] [--probe SUBFIELD] [--source arxiv,openalex]
  ideasci.py add --run RUN --id ID --title T [--date YYYY-MM-DD] [--year Y] [--field F] [--url U]
  ideasci.py read ID --run RUN [--level full|abstract] [--digest PATH]
  ideasci.py status --run RUN
  ideasci.py check --run RUN [--stage problem|gaps|candidates|reviews|proposal|all] [--strict]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATES = SKILL_DIR / "assets" / "templates"
LEDGER = "ledger.json"
UA = "ideasci/1.0 (grounded-research-ideation skill)"


class UsageError(Exception):
    pass


# --------------------------------------------------------------------------- ids

ARXIV_NEW = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
ARXIV_OLD = re.compile(r"^[a-z\-]+(\.[A-Za-z]{2})?/\d{7}(v\d+)?$")


def _strip_v(x: str) -> str:
    return re.sub(r"v\d+$", "", x)


def normalize_id(raw: str) -> str:
    """Canonical ids: arxiv:<id> | oa:W<digits> | doi:<doi> | ss:<id> | url:<x>."""
    s = raw.strip().strip("[]").lstrip("@")
    if not s:
        raise UsageError("empty id")
    m = re.match(r"^https?://(?:www\.)?arxiv\.org/(?:abs|pdf|html)/(.+?)(?:\.pdf)?/?$", s, re.I)
    if m:
        return "arxiv:" + _strip_v(m.group(1))
    m = re.match(r"^https?://openalex\.org/(W\d+)$", s, re.I)
    if m:
        return "oa:" + m.group(1).upper()
    m = re.match(r"^https?://(?:dx\.)?doi\.org/(10\..+)$", s, re.I)
    if m:
        return "doi:" + m.group(1).lower()
    m = re.match(r"^(arxiv|oa|doi|ss|url):(.+)$", s, re.I)
    if m:
        p, rest = m.group(1).lower(), m.group(2).strip()
        if p == "arxiv":
            return "arxiv:" + _strip_v(rest)
        if p == "oa":
            return "oa:" + rest.upper()
        if p == "doi":
            return "doi:" + rest.lower()
        return p + ":" + rest
    if ARXIV_NEW.match(s) or ARXIV_OLD.match(s):
        return "arxiv:" + _strip_v(s)
    if re.match(r"^W\d+$", s, re.I):
        return "oa:" + s.upper()
    if re.match(r"^10\.\d{4,}/\S+$", s):
        return "doi:" + s.lower()
    raise UsageError("cannot normalise id %r (use arxiv:<id>, oa:W<digits>, doi:<doi>)" % raw)


def safe_id(pid: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", pid)


# ------------------------------------------------------------------------ ledger

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(run: Path) -> dict:
    f = run / LEDGER
    if not f.exists():
        raise UsageError("%s is not an ideation run directory (no %s); run `init` first" % (run, LEDGER))
    return json.loads(f.read_text(encoding="utf-8"))


def save(run: Path, led: dict) -> None:
    tmp = run / (LEDGER + ".tmp")
    tmp.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, run / LEDGER)


def tkey(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())


def register(led: dict, rec: dict, qn: int | None = None) -> str:
    """Add or merge a paper record; dedupe across sources by normalised title. Returns canonical id."""
    pid = led["aliases"].get(rec["id"], rec["id"])
    tk = tkey(rec.get("title", ""))
    if pid not in led["papers"] and tk and tk in led["titles"]:
        led["aliases"][rec["id"]] = led["titles"][tk]
        pid = led["titles"][tk]
    if pid in led["papers"]:
        cur = led["papers"][pid]
        for k in ("abstract", "field", "year", "date", "authors", "url"):
            if not cur.get(k) and rec.get(k):
                cur[k] = rec[k]
    else:
        led["papers"][pid] = {
            "id": pid,
            "title": rec.get("title", ""),
            "year": rec.get("year"),
            "date": rec.get("date"),
            "authors": rec.get("authors", ""),
            "field": rec.get("field", ""),
            "url": rec.get("url", ""),
            "abstract": (rec.get("abstract") or "")[:1500],
            "source": rec.get("source", "manual"),
            "found_by": [],
            "read_level": None,
            "digest": None,
        }
        if tk:
            led["titles"][tk] = pid
    if qn is not None and qn not in led["papers"][pid]["found_by"]:
        led["papers"][pid]["found_by"].append(qn)
    return pid


# ------------------------------------------------------------------------ search

def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _throttle_arxiv() -> None:
    """arXiv asks for at most one request per ~3 seconds."""
    f = Path(tempfile.gettempdir()) / "ideasci_arxiv_last"
    try:
        last = float(f.read_text())
    except Exception:
        last = 0.0
    wait = 3.1 - (time.time() - last)
    if wait > 0:
        time.sleep(wait)
    try:
        f.write_text(str(time.time()))
    except Exception:
        pass


def _date_ok(s: str | None) -> str | None:
    if s and not re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        raise UsageError("date must be YYYY-MM-DD: %s" % s)
    return s


def _authors(names) -> str:
    names = [n for n in names if n]
    return ", ".join(names[:3]) + (" et al." if len(names) > 3 else "")


def arxiv_expr(q: str, op: str = "AND") -> str:
    try:
        toks = shlex.split(q)
    except ValueError:
        toks = q.split()
    terms = []
    for t in toks:
        if re.search(r"[^A-Za-z0-9]", t):
            terms.append('all:"%s"' % t.replace('"', ""))
        else:
            terms.append("all:%s" % t)
    if not terms:
        raise UsageError("empty query")
    return (" %s " % op).join(terms)


def arxiv_url(expr: str, n: int, after: str | None, before: str | None) -> str:
    if after or before:
        a = (after or "1986-01-01").replace("-", "") + "0000"
        b = (before or "2099-12-31").replace("-", "") + "2359"
        expr = "(%s) AND submittedDate:[%s TO %s]" % (expr, a, b)
    qs = urllib.parse.urlencode({"search_query": expr, "start": 0, "max_results": n,
                                 "sortBy": "relevance", "sortOrder": "descending"})
    return "https://export.arxiv.org/api/query?" + qs


_NS = {"a": "http://www.w3.org/2005/Atom", "ax": "http://arxiv.org/schemas/atom"}


def parse_arxiv(data: bytes) -> list:
    root = ET.fromstring(data)
    out = []
    for e in root.findall("a:entry", _NS):
        idurl = e.findtext("a:id", "", _NS)
        if "/api/errors" in idurl:
            raise RuntimeError("arXiv API error: " + " ".join(e.findtext("a:summary", "", _NS).split()))
        aid = _strip_v(idurl.rsplit("/abs/", 1)[-1])
        pub = (e.findtext("a:published", "", _NS) or "")[:10]
        pc = e.find("ax:primary_category", _NS)
        out.append({
            "id": "arxiv:" + aid,
            "title": " ".join((e.findtext("a:title", "", _NS) or "").split()),
            "abstract": " ".join((e.findtext("a:summary", "", _NS) or "").split()),
            "date": pub,
            "year": int(pub[:4]) if pub[:4].isdigit() else None,
            "authors": _authors([a.findtext("a:name", "", _NS) for a in e.findall("a:author", _NS)]),
            "field": pc.get("term") if pc is not None else "",
            "url": "https://arxiv.org/abs/" + aid,
            "source": "arxiv",
        })
    return out


def do_arxiv(q: str, n: int, after, before, relax: bool):
    ops = ["AND", "OR"] if (relax and len(q.split()) > 1) else ["AND"]
    res: list = []
    for op in ops:
        _throttle_arxiv()
        res = parse_arxiv(http_get(arxiv_url(arxiv_expr(q, op), n, after, before)))
        if res:
            return res, op == "OR"
    return res, False


def rebuild_abstract(inv) -> str:
    if not inv:
        return ""
    pos = {}
    for w, idxs in inv.items():
        for i in idxs:
            pos[i] = w
    return " ".join(pos[i] for i in sorted(pos))


def openalex_url(q: str, n: int, after, before, key: str | None) -> str:
    params = {
        "search": q, "per_page": n,
        "select": "id,display_name,publication_year,publication_date,doi,abstract_inverted_index,"
                  "authorships,primary_topic,cited_by_count",
    }
    flt = []
    if after:
        flt.append("from_publication_date:" + after)
    if before:
        flt.append("to_publication_date:" + before)
    if flt:
        params["filter"] = ",".join(flt)
    if key:
        params["api_key"] = key
    return "https://api.openalex.org/works?" + urllib.parse.urlencode(params, safe=",:")


def parse_openalex(data: bytes) -> list:
    out = []
    for w in json.loads(data).get("results", []):
        wid = (w.get("id") or "").rsplit("/", 1)[-1]
        topic = w.get("primary_topic") or {}
        field = ((topic.get("subfield") or {}).get("display_name")
                 or (topic.get("field") or {}).get("display_name") or "")
        names = [((a.get("author") or {}).get("display_name")) for a in w.get("authorships", [])]
        out.append({
            "id": "oa:" + wid,
            "title": " ".join((w.get("display_name") or "").split()),
            "abstract": rebuild_abstract(w.get("abstract_inverted_index")),
            "date": w.get("publication_date") or "",
            "year": w.get("publication_year"),
            "authors": _authors(names),
            "field": field,
            "url": w.get("doi") or w.get("id") or "",
            "source": "openalex",
        })
    return out


def do_openalex(q: str, n: int, after, before, relax: bool):
    return parse_openalex(http_get(openalex_url(q, n, after, before, os.environ.get("OPENALEX_API_KEY")))), False


def describe_error(e: Exception, src: str) -> str:
    if isinstance(e, urllib.error.HTTPError):
        if e.code == 429:
            return "rate limited (HTTP 429); wait and retry with fewer queries"
        if e.code in (401, 403) and src == "openalex":
            return "HTTP %d; OpenAlex needs a (free) API key: set OPENALEX_API_KEY" % e.code
        return "HTTP %d" % e.code
    if isinstance(e, urllib.error.URLError):
        return "network unreachable or blocked (%s)" % getattr(e, "reason", e)
    return "%s: %s" % (type(e).__name__, e)


def cmd_search(a) -> int:
    run = Path(a.run)
    led = load(run)
    after, before = _date_ok(a.after), _date_ok(a.before)
    cutoff = plan_cutoff(run)
    if cutoff:
        if before and before > cutoff:
            raise UsageError("--before %s is later than this run's cutoff %s (plan.md)" % (before, cutoff))
        before = before or cutoff
    srcs = [s.strip() for s in a.source.split(",") if s.strip()]
    for s in srcs:
        if s not in ("arxiv", "openalex"):
            raise UsageError("unknown source %r (arxiv, openalex)" % s)
    if a.regime == "cross" and not a.probe:
        print("note: cross-regime searches should declare --probe <sub-field> "
              "(the gate wants >= 3 distinct probes)", file=sys.stderr)
    qn = len(led["queries"]) + 1
    ids: list = []
    shown: list = []
    failures: list = []
    relaxed_any = False
    for s in srcs:
        fn = do_arxiv if s == "arxiv" else do_openalex
        try:
            res, relaxed = fn(a.query, a.max, after, before, not a.no_relax)
        except (OSError, RuntimeError, ET.ParseError, ValueError) as e:
            failures.append("%s: %s" % (s, describe_error(e, s)))
            continue
        relaxed_any = relaxed_any or relaxed
        for rec in res:
            pid = register(led, rec, qn)
            if pid not in ids:
                ids.append(pid)
                shown.append(pid)
    if failures and not ids and len(failures) == len(srcs):
        print("search failed: " + "; ".join(failures), file=sys.stderr)
        print("fallback: use your platform's web search, then register each paper you will rely on with\n"
              "  ideasci.py add --run %s --id arxiv:<id> --title \"...\" --year <Y> --field <cat>\n"
              "Never cite a paper you could not retrieve." % a.run, file=sys.stderr)
        return 2
    led["queries"].append({"n": qn, "ts": now(), "q": a.query, "source": ",".join(srcs),
                           "regime": a.regime, "probe": a.probe or "", "after": after, "before": before,
                           "relaxed": relaxed_any, "ids": ids})
    save(run, led)
    if a.json:
        print(json.dumps([led["papers"][i] for i in shown], ensure_ascii=False, indent=1))
    else:
        tag = a.regime + ("|probe=" + a.probe if a.probe else "")
        if cutoff:
            tag += "|cutoff=" + cutoff
        print("search #%d [%s] %r -> %d results%s" % (qn, tag, a.query, len(shown),
                                                       " (AND returned nothing; relaxed to OR)" if relaxed_any else ""))
        for k, pid in enumerate(shown, 1):
            p = led["papers"][pid]
            mark = {"full": " [read:full]", "abstract": " [read:abs]"}.get(p["read_level"], "")
            print("%2d. %s | %s | %s | %s%s" % (k, pid, p.get("year") or "?", p.get("field") or "-",
                                                p["title"][:110], mark))
            if p.get("abstract"):
                print("      " + p["abstract"][:190].replace("\n", " ") + ("..." if len(p["abstract"]) > 190 else ""))
    for f in failures:
        print("warning: %s" % f, file=sys.stderr)
    return 0


# ----------------------------------------------------------------- init/add/read

def cmd_init(a) -> int:
    run = Path(a.run)
    (run / "papers").mkdir(parents=True, exist_ok=True)
    made, skipped = [], []
    for t in sorted(TEMPLATES.glob("*.md")):
        dest = run / "papers" / "_TEMPLATE.md" if t.name == "digest.md" else run / t.name
        if dest.exists():
            skipped.append(dest.name)
            continue
        text = t.read_text(encoding="utf-8")
        if t.name == "plan.md":
            text = text.replace("- Mode: standard", "- Mode: " + a.mode)
            if a.cutoff:
                text = text.replace("- Cutoff: none", "- Cutoff: " + _date_ok(a.cutoff))
        dest.write_text(text, encoding="utf-8")
        made.append(dest.name)
    if not (run / LEDGER).exists():
        save(run, {"version": 1, "created": now(), "papers": {}, "titles": {}, "aliases": {}, "queries": []})
        made.append(LEDGER)
    print("run dir: %s\ncreated: %s%s" % (run, ", ".join(made) or "-",
                                          ("\nkept existing: " + ", ".join(skipped)) if skipped else ""))
    return 0


def cmd_add(a) -> int:
    run = Path(a.run)
    led = load(run)
    if not a.title.strip():
        raise UsageError("--title is required")
    date = _date_ok(a.date)
    year = a.year or (int(date[:4]) if date else None)
    rec = {"id": normalize_id(a.id), "title": a.title.strip(), "year": year, "date": date or "", "field": a.field or "",
           "url": a.url or "", "abstract": a.abstract or "", "authors": a.authors or "", "source": "manual"}
    pid = register(led, rec)
    save(run, led)
    print("registered %s%s" % (pid, "" if pid == rec["id"] else " (duplicate of existing; alias recorded)"))
    return 0


ANCHOR_RE = re.compile(r"(§\s*\d|\bSec(?:tion)?s?\.?\s*\d|\bEq(?:uation)?s?\.?\s*\(?\d|\bTables?\s*\d|"
                       r"\bFig(?:ure)?s?\.?\s*\d|\bAppendix\s*[A-Z0-9]|\bAlgorithm\s*\d|\bTheorem\s*\d)", re.I)


def cmd_read(a) -> int:
    run = Path(a.run)
    led = load(run)
    pid = normalize_id(a.id)
    pid = led["aliases"].get(pid, pid)
    if pid not in led["papers"]:
        raise UsageError("%s is not in the ledger; find it with `search` or register it with `add` first" % pid)
    dpath = Path(a.digest) if a.digest else run / "papers" / (safe_id(pid) + ".md")
    if not dpath.exists():
        raise UsageError("digest file not found: %s (write it from papers/_TEMPLATE.md first)" % dpath)
    text = re.sub(r"<!--.*?-->", "", dpath.read_text(encoding="utf-8"), flags=re.S)
    if re.search(r"\bTODO\b", text):
        raise UsageError("digest still contains TODO placeholders: %s" % dpath)
    need = 300 if a.level == "full" else 150
    if len(text.strip()) < need:
        raise UsageError("digest too short for level=%s (%d chars < %d)" % (a.level, len(text.strip()), need))
    notes = []
    if "what this paper does" not in text.lower():
        notes.append("digest lacks a 'What this paper does' section")
    forced = False
    if a.level == "full" and len(ANCHOR_RE.findall(text)) < 2:
        if not a.force:
            raise UsageError("level=full needs >= 2 anchors into the full text (Sec./Eq./Table/Figure/Appendix). "
                             "Either read the full text and anchor the digest, or register with --level abstract.")
        forced = True
        notes.append("anchor check skipped (--force); this is recorded and reported by `check` and `status`")
    cur = led["papers"][pid]
    if not (cur["read_level"] == "full" and a.level == "abstract"):
        cur["read_level"] = a.level
        cur["forced"] = forced
    cur["digest"] = os.path.relpath(dpath, run)
    save(run, led)
    print("marked %s as read (%s)%s" % (pid, cur["read_level"], ("; note: " + "; ".join(notes)) if notes else ""))
    return 0


# --------------------------------------------------------------- markdown parsing

class Node:
    __slots__ = ("level", "title", "lines", "children")

    def __init__(self, level: int, title: str):
        self.level, self.title, self.lines, self.children = level, title, [], []


def clean(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def parse_md(text: str) -> Node:
    root = Node(0, "")
    stack = [root]
    fence = False
    for line in clean(text).splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            node = Node(len(m.group(1)), m.group(2).strip())
            while stack[-1].level >= node.level:
                stack.pop()
            stack[-1].children.append(node)
            stack.append(node)
        else:
            stack[-1].lines.append(line)
    return root


def body(n: Node) -> str:
    return "\n".join(n.lines).strip()


def full(n: Node) -> str:
    parts = [body(n)]
    for c in n.children:
        parts.append(c.title)
        parts.append(full(c))
    return "\n".join(p for p in parts if p)


def walk(n: Node):
    for c in n.children:
        yield c
        yield from walk(c)


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", t.lower())).strip()


def child_map(n: Node) -> dict:
    return {norm(c.title): c for c in n.children}


CITE_RE = re.compile(r"@((?:arxiv|oa|doi|ss|url):[A-Za-z0-9._:/\-]+)")


def cites(text: str) -> list:
    out = []
    for m in CITE_RE.finditer(text):
        try:
            out.append(normalize_id(m.group(1).rstrip(".-:/")))
        except UsageError:
            pass
    return out


def bullets(text: str) -> list:
    return re.findall(r"^\s*(?:[-*+]|\d+[.)])\s+(.+)$", text, re.M)


def sentences(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?\u3002\uff01\uff1f])\s+", text.strip()) if s.strip()])


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, where, msg):
        self.errors.append("%s: %s" % (where, msg))

    def warn(self, where, msg):
        self.warnings.append("%s: %s" % (where, msg))


def check_cites(rep: Report, led: dict, where: str, ids, need_full: bool = False) -> None:
    for pid in sorted(set(ids)):
        pid = led["aliases"].get(pid, pid)
        rec = led["papers"].get(pid)
        if rec is None:
            rep.err(where, "cited id %s is not in the ledger (never retrieved or added): possible fabricated citation" % pid)
        elif not rec.get("read_level"):
            rep.err(where, "cited id %s has not been read (no digest registered with `read`)" % pid)
        elif need_full and rec["read_level"] != "full":
            rep.err(where, "%s is cited as near-miss/source but was read only at abstract level; read the full text" % pid)


def todo_check(rep: Report, fname: str, text: str) -> None:
    n = len(re.findall(r"\bTODO\b", text))
    if n:
        rep.err(fname, "%d unfilled TODO placeholder(s)" % n)


def read_clean(run: Path, fname: str, rep: Report, required: bool = True):
    f = run / fname
    if not f.exists():
        (rep.err if required else rep.warn)(fname, "file is missing")
        return None
    text = f.read_text(encoding="utf-8")
    todo_check(rep, fname, clean(text))
    return text


def axis_name(title: str) -> str:
    return title.split(":", 1)[1].strip() if ":" in title else re.sub(r"^axis\s*\d*\s*", "", title, flags=re.I).strip()


def problem_axes(run: Path):
    f = run / "problem.md"
    if not f.exists():
        return None
    names = [axis_name(n.title) for n in walk(parse_md(f.read_text(encoding="utf-8")))
             if n.level == 3 and norm(n.title).startswith("axis")]
    return [n for n in names if n and n.upper() != "TODO"] or None


# ------------------------------------------------------------------- stage checks

GAP_FIELDS = ["gap", "near miss methods and coverage", "methodological deficiency", "why it matters", "evidence route"]
DEFICIENCY_TAGS = ["missing mechanism", "algorithmic limitation", "wrong inductive bias", "credit assignment flaw",
                   "training objective mismatch", "representation limitation", "scalability limit"]
NOVELTY_TYPES = ["new topic", "recombination of distant concepts", "reinforcing a weak connection"]


def check_problem(run, led, rep):
    text = read_clean(run, "problem.md", rep)
    if text is None:
        return
    root = parse_md(text)
    names = problem_axes(run)
    if names is None:
        rep.err("problem.md", "no '### Axis N: <name>' section with a real name")
    elif len(names) > 3:
        rep.warn("problem.md", "%d axes; the method handles one axis per gap-finding pass, use 1-3" % len(names))
    sections = child_map(next((c for c in root.children if c.level == 1), root))
    if "problem definition" not in sections:
        rep.err("problem.md", "missing '## Problem definition'")


def check_gaps(run, led, rep):
    text = read_clean(run, "gaps.md", rep)
    if text is None:
        return
    root = parse_md(text)
    axes = [n for n in walk(root) if n.level == 2 and norm(n.title).startswith("axis")]
    if not axes:
        rep.err("gaps.md", "no '## Axis: <name>' section")
    declared = problem_axes(run)
    declared_norm = [norm(x) for x in declared] if declared else None
    for ax in axes:
        where = "gaps.md > " + ax.title
        name = axis_name(ax.title)
        if declared_norm is not None and norm(name) not in declared_norm:
            rep.err(where, "axis %r does not match an axis in problem.md (%s)" % (name, ", ".join(declared)))
        kids = ax.children
        if not any(norm(c.title).startswith("prior work summary") and body(c) for c in kids):
            rep.err(where, "missing or empty '### Prior work summary'")
        gaps = [c for c in kids if re.match(r"^gap \d+$", norm(c.title))]
        if not gaps:
            rep.err(where, "no '### Gap N' section")
        if len(gaps) > 2:
            rep.err(where, "%d gaps under one axis; the method caps this at two" % len(gaps))
        for g in gaps:
            gw = "%s > %s" % (where, g.title)
            fields = child_map(g)
            for f in GAP_FIELDS:
                if f not in fields:
                    rep.err(gw, "missing '#### %s'" % f)
                elif not body(fields[f]):
                    rep.err(gw, "empty '#### %s'" % f)
            if "gap" in fields and not re.search(r"\bbut\b|\byet\b|\bhowever\b", body(fields["gap"]), re.I):
                rep.warn(gw, "Gap is not in contrast form ('Prior methods do X through Y, but Y leaves Z unresolved')")
            if "methodological deficiency" in fields:
                d = norm(body(fields["methodological deficiency"]))
                if not any(t in d for t in DEFICIENCY_TAGS):
                    rep.warn(gw, "Methodological deficiency carries no recognised tag (%s)" % "; ".join(DEFICIENCY_TAGS))
            if "near miss methods and coverage" in fields:
                nm = body(fields["near miss methods and coverage"])
                ids = sorted(set(cites(nm)))
                if len(ids) < 2 and not re.search(r"only one real near[- ]miss", nm, re.I):
                    rep.err(gw, "near-miss coverage cites %d distinct id(s); need >= 2 (or state 'only one real near miss')" % len(ids))
                check_cites(rep, led, gw + " > near-miss", ids, need_full=True)
    check_cites(rep, led, "gaps.md", cites(clean(text)))


def check_candidates(run, led, rep):
    text = read_clean(run, "candidates.md", rep)
    if text is None:
        return
    root = parse_md(text)
    cands = [n for n in walk(root) if n.level == 2 and norm(n.title).startswith("candidate")]
    if not cands:
        rep.err("candidates.md", "no '## Candidate Cn' section")
    req = ["intuition", "gap it attacks", "source inspiration", "how it maps to this problem",
           "why it could work", "novelty vs closest in domain work", "main risk"]
    for c in cands:
        w = "candidates.md > " + c.title
        f = child_map(c)
        for k in req:
            if k not in f:
                rep.err(w, "missing '### %s'" % k)
            elif not body(f[k]):
                rep.err(w, "empty '### %s'" % k)
        if "intuition" in f and sentences(body(f["intuition"])) > 2:
            rep.warn(w, "Intuition is longer than two sentences")
        src_ids: list = []
        if "source inspiration" in f:
            sb = body(f["source inspiration"])
            src_ids = sorted(set(cites(sb)))
            if not src_ids:
                rep.err(w, "Source inspiration cites no paper id")
            check_cites(rep, led, w + " > source", src_ids, need_full=True)
            if not any(re.search(r"novelty type:\s*\W*" + re.escape(t), sb, re.I) for t in NOVELTY_TYPES):
                rep.err(w, "Source inspiration lacks 'Novelty type:' (one of: %s)" % " | ".join(NOVELTY_TYPES))
            if not re.search(r"source setting:", sb, re.I):
                rep.warn(w, "Source inspiration lacks 'Source setting:' (transfer test condition 1)")
        if "how it maps to this problem" in f:
            mb = body(f["how it maps to this problem"])
            for lab, cond in (("Shared structure:", 3), ("Adaptation:", 4)):
                if not re.search(re.escape(lab), mb, re.I):
                    rep.warn(w, "'How it maps' lacks '%s' (transfer test condition %d)" % (lab, cond))
            if "```" in mb or "$$" in mb or "\\begin{" in mb:
                rep.warn(w, "'How it maps' contains pseudocode/equations; keep it in plain language until the report stage")
        if "why it could work" in f and not re.search(r"key assumption:", body(f["why it could work"]), re.I):
            rep.warn(w, "'Why it could work' lacks 'Key assumption:'")
        if "novelty vs closest in domain work" in f:
            nb = body(f["novelty vs closest in domain work"])
            near = sorted(set(cites(nb)))
            if not near:
                rep.err(w, "'Novelty vs. closest in-domain work' cites no paper id")
            check_cites(rep, led, w + " > closest in-domain", near)
            if set(near) & set(src_ids):
                rep.warn(w, "the source paper is also the closest in-domain work: is this a rediscovery rather than a transfer?")
            elif near and src_ids:
                fs = {led["papers"].get(led["aliases"].get(i, i), {}).get("field") for i in src_ids}
                fn = {led["papers"].get(led["aliases"].get(i, i), {}).get("field") for i in near}
                fs.discard(""); fn.discard("")
                if fs and fn and fs == fn and len(fs) == 1:
                    rep.warn(w, "source and closest in-domain paper share field %s: state why the transfer is non-trivial" % next(iter(fs)))
    check_cites(rep, led, "candidates.md", cites(clean(text)))


def check_reviews(run, led, rep, required=True):
    text = read_clean(run, "reviews.md", rep, required=required)
    if text is None:
        return
    root = parse_md(text)
    blocks = [n for n in walk(root) if n.level == 2 and norm(n.title).startswith("review")]
    if not blocks:
        rep.err("reviews.md", "no '## Review of Cn' section")
    for b in blocks:
        w = "reviews.md > " + b.title
        f = child_map(b)
        for k in ("verdict", "evidence", "strongest objection"):
            if k not in f:
                rep.err(w, "missing '### %s'" % k)
            elif not body(f[k]):
                rep.err(w, "empty '### %s'" % k)
        if "verdict" in f:
            v = body(f["verdict"]).strip().lstrip("*_ ").lower()
            if not re.match(r"^(survive|revise|reject)\b", v):
                rep.err(w, "Verdict must start with survive | revise | reject")
            elif v.startswith(("revise", "reject")) and not re.match(r"^(revise|reject)\s*[:\-]\s*\S", v):
                rep.err(w, "'revise' needs the single weakest dimension; 'reject' needs a short reason (e.g. 'revise: transfer assumption')")
        if "evidence" in f:
            ev = body(f["evidence"])
            if not cites(ev):
                rep.err(w, "Evidence cites no paper id")
            for bl in bullets(ev):
                if not cites(bl) and not re.search(r"challeng", bl, re.I):
                    rep.warn(w, "evidence bullet without a paper id: %s" % bl[:60])
        if "strongest objection" in f and sentences(body(f["strongest objection"])) > 2:
            rep.warn(w, "Strongest objection should be one sentence")
    check_cites(rep, led, "reviews.md", cites(clean(text)))


PROPOSAL_REQ = ["topic relevance", "one sentence thesis", "core problem", "key novelty", "problem definition",
                "key terms", "related work", "method", ("model details", "technical details"),
                "comparison to state of the art", "proposed evaluation", "falsifiable predictions", "limitations"]


def selected_candidate(run: Path):
    f = run / "plan.md"
    if not f.exists():
        return None
    m = re.search(r"Selected candidate:\s*(C\d+)", clean(f.read_text(encoding="utf-8")), re.I)
    return m.group(1).upper() if m else None


def plan_cutoff(run: Path):
    f = run / "plan.md"
    if not f.exists():
        return None
    m = re.search(r"^\s*-?\s*Cutoff:\s*(\d{4}-\d{2}-\d{2})\b", clean(f.read_text(encoding="utf-8")), re.M)
    return m.group(1) if m else None


STAGE_FILES = {"gaps": ["gaps.md"], "candidates": ["candidates.md"], "reviews": ["reviews.md"],
               "proposal": ["proposal.md"]}


def cited_in(run: Path, led: dict, stages) -> list:
    ids = []
    for s in stages:
        for f in STAGE_FILES.get(s, []):
            p = run / f
            if p.exists():
                ids += cites(clean(p.read_text(encoding="utf-8")))
    return sorted({led["aliases"].get(i, i) for i in ids})


def check_global(run, led, rep, stages):
    """Cross-cutting gates: --force traces and the retrospective cutoff."""
    ids = cited_in(run, led, stages)
    forced = [i for i in ids if led["papers"].get(i, {}).get("forced")]
    if forced:
        rep.warn("ledger", "%d cited paper(s) were registered with --force (full-text anchor check skipped): %s; "
                           "say so in the delivery" % (len(forced), ", ".join(forced)))
    cutoff = plan_cutoff(run)
    if not cutoff:
        return
    for i in ids:
        rec = led["papers"].get(i)
        if not rec:
            continue
        d = rec.get("date") or ""
        if re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            if d > cutoff:
                rep.err("cutoff", "%s is dated %s, after this run's cutoff %s" % (i, d, cutoff))
        elif rec.get("year"):
            if int(rec["year"]) > int(cutoff[:4]):
                rep.err("cutoff", "%s is from %s, after this run's cutoff %s" % (i, rec["year"], cutoff))
            elif int(rec["year"]) == int(cutoff[:4]):
                rep.warn("cutoff", "%s has only a year; cannot verify it precedes %s (re-add with --date)" % (i, cutoff))
        else:
            rep.warn("cutoff", "%s has no date; cannot verify it precedes %s (re-add with --date)" % (i, cutoff))
    loose = [str(q["n"]) for q in led["queries"] if not q.get("before") or q["before"] > cutoff]
    if loose:
        rep.warn("search trail", "queries #%s were not restricted to the cutoff %s" % (", ".join(loose), cutoff))
    if any(p.get("source") == "manual" and not p.get("date") for p in led["papers"].values()):
        rep.warn("search trail", "some papers were added by hand without --date; web-search fallbacks are not "
                                 "date-restricted, so check their dates yourself")


def check_proposal(run, led, rep):
    text = read_clean(run, "proposal.md", rep)
    if text is None:
        return
    root = parse_md(text)
    h1 = next((c for c in root.children if c.level == 1), None)
    if h1 is None or not h1.title.strip():
        rep.err("proposal.md", "missing '# <title>' heading")
        return
    sec = child_map(h1)
    for req in PROPOSAL_REQ:
        keys = (req,) if isinstance(req, str) else req
        hit = next((k for k in keys if k in sec), None)
        if hit is None:
            rep.err("proposal.md", "missing '## %s'" % " / ".join(k.title() for k in keys))
        elif not full(sec[hit]).strip():
            rep.err("proposal.md", "empty '## %s'" % hit.title())
    if "one sentence thesis" in sec:
        para = next((p.strip() for p in re.split(r"\n\s*\n", body(sec["one sentence thesis"])) if p.strip()), "")
        words = len(re.findall(r"\S+", para))
        if words >= 30:
            rep.err("proposal.md > thesis", "thesis has %d words; must be under 30" % words)
        if sentences(para) > 1:
            rep.warn("proposal.md > thesis", "thesis should be a single sentence")
        if re.search(r"\d+(\.\d+)?\s*%|\b\d+\.\d+\b", para):
            rep.warn("proposal.md > thesis", "thesis should not contain metric numbers")
    if "limitations" in sec:
        n = len(bullets(full(sec["limitations"])))
        if n < 3:
            rep.err("proposal.md > limitations", "%d limitation(s); need three to five" % n)
        elif n > 5:
            rep.warn("proposal.md > limitations", "%d limitations; three to five concise ones are expected" % n)
    if "falsifiable predictions" in sec:
        bl = bullets(full(sec["falsifiable predictions"]))
        if not bl:
            rep.err("proposal.md > predictions", "no prediction bullets")
        for b in bl:
            if not re.search(r"falsified if", b, re.I):
                rep.err("proposal.md > predictions", "prediction lacks 'Falsified if:' -> %s" % b[:70])
    all_ids = cites(clean(text))
    check_cites(rep, led, "proposal.md", all_ids)
    if "related work" in sec and not cites(full(sec["related work"])):
        rep.err("proposal.md > related work", "cites no paper id")
    sel = selected_candidate(run)
    cand_file = run / "candidates.md"
    if sel is None:
        rep.warn("plan.md", "no 'Selected candidate: Cn' recorded; cannot verify the proposal carries the candidate through")
    elif cand_file.exists():
        cnode = next((n for n in walk(parse_md(cand_file.read_text(encoding="utf-8")))
                      if n.level == 2 and re.search(r"\b%s\b" % sel, n.title, re.I)), None)
        if cnode is None:
            rep.err("plan.md", "selected candidate %s not found in candidates.md" % sel)
        else:
            f = child_map(cnode)
            src = set(cites(body(f.get("source inspiration", Node(0, ""))))) if "source inspiration" in f else set()
            near = set(cites(body(f["novelty vs closest in domain work"]))) if "novelty vs closest in domain work" in f else set()
            have = set(all_ids)
            miss = sorted(src - have)
            if miss:
                rep.err("proposal.md", "does not cite the mechanism source(s) of selected candidate %s: %s" % (sel, ", ".join(miss)))
            miss2 = sorted(near - have)
            if miss2:
                rep.warn("proposal.md", "does not cite the closest in-domain work of %s: %s" % (sel, ", ".join(miss2)))
    if sel and (run / "reviews.md").exists():
        rv = [n for n in walk(parse_md((run / "reviews.md").read_text(encoding="utf-8")))
              if n.level == 2 and re.search(r"\b%s\b" % sel, n.title, re.I)]
        last = None
        if rv:
            fv = child_map(rv[-1]).get("verdict")
            last = body(fv).strip().lstrip("*_ ").lower() if fv else None
        if not last or not last.startswith("survive"):
            rep.warn("reviews.md", "latest review of %s is not 'survive' (review gate)" % sel)
    elif sel:
        rep.warn("reviews.md", "no reviews.md; the selected candidate was never reviewed")
    if re.search(r"\b(achiev(?:es|ed)|outperform(?:s|ed)|improv(?:es|ed))\b[^.\n]{0,60}\d+(?:\.\d+)?\s*%", text, re.I):
        rep.warn("proposal.md", "reads like a measured result; the proposal is results-masked (plans and falsifiable predictions only)")


def cmd_check(a) -> int:
    run = Path(a.run)
    led = load(run)
    rep = Report()
    stages = ["problem", "gaps", "candidates", "reviews", "proposal"] if a.stage == "all" else [a.stage]
    for s in stages:
        n_err, n_warn = len(rep.errors), len(rep.warnings)
        if s == "problem":
            check_problem(run, led, rep)
        elif s == "gaps":
            check_gaps(run, led, rep)
        elif s == "candidates":
            check_candidates(run, led, rep)
        elif s == "reviews":
            check_reviews(run, led, rep, required=(a.stage == "reviews"))
        elif s == "proposal":
            check_proposal(run, led, rep)
        print("[%s] %d error(s), %d warning(s)" % (s, len(rep.errors) - n_err, len(rep.warnings) - n_warn))
    check_global(run, led, rep, stages)
    if a.stage == "all":
        cross = len({q["probe"] for q in led["queries"] if q["regime"] == "cross" and q["probe"]})
        if cross < 3:
            rep.warn("search trail", "%d distinct cross-regime probe(s); the innovator is expected to span >= 3 sub-fields" % cross)
        if not any(q["regime"] == "same" for q in led["queries"]):
            rep.warn("search trail", "no same-problem queries logged for the gap-finding stage")
    errs = list(rep.errors)
    warns = list(rep.warnings)
    if a.strict:
        errs += ["(strict) " + w for w in warns]
        warns = []
    for e in errs:
        print("ERROR  " + e)
    for w in warns:
        print("WARN   " + w)
    print("PASS" if not errs else "FAIL: %d error(s)" % len(errs))
    return 0 if not errs else 1


def cmd_status(a) -> int:
    run = Path(a.run)
    led = load(run)
    ps = led["papers"].values()
    full_n = sum(1 for p in ps if p["read_level"] == "full")
    abs_n = sum(1 for p in ps if p["read_level"] == "abstract")
    print("run: %s\npapers: %d (read full %d, abstract %d, unread %d)" % (run, len(led["papers"]), full_n, abs_n,
                                                                         len(led["papers"]) - full_n - abs_n))
    same = [q for q in led["queries"] if q["regime"] == "same"]
    cross = [q for q in led["queries"] if q["regime"] == "cross"]
    probes = sorted({q["probe"] for q in cross if q["probe"]})
    print("queries: %d same-problem, %d cross-setting; cross probes (%d): %s" % (len(same), len(cross), len(probes),
                                                                              ", ".join(probes) or "-"))
    for f in ("problem.md", "gaps.md", "candidates.md", "reviews.md", "proposal.md"):
        p = run / f
        if not p.exists():
            print("  %-14s missing" % f)
        else:
            n = len(re.findall(r"\bTODO\b", clean(p.read_text(encoding="utf-8"))))
            print("  %-14s %s" % (f, "%d TODO left" % n if n else "filled"))
    sel = selected_candidate(run)
    print("selected candidate: %s" % (sel or "none"))
    cut = plan_cutoff(run)
    print("cutoff: %s" % (cut or "none (real research)"))
    forced = sorted(p["id"] for p in led["papers"].values() if p.get("forced"))
    if forced:
        print("forced reads (anchor check skipped): %d -> %s" % (len(forced), ", ".join(forced)))
    return 0


# -------------------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ideasci", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="scaffold a run directory from the templates")
    s.add_argument("run")
    s.add_argument("--mode", choices=["quick", "standard"], default="standard")
    s.add_argument("--cutoff", help="YYYY-MM-DD; retrospective replay only: searches default to --before this date "
                                    "and `check` rejects cited papers dated later")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("search", help="search arXiv / OpenAlex and log the query in the ledger")
    s.add_argument("query", help="short keyword query; quote phrases")
    s.add_argument("--run", required=True)
    s.add_argument("--regime", choices=["same", "cross"], default="same",
                   help="same = exact terminology of the problem; cross = structural terms from other fields")
    s.add_argument("--probe", default="", help="sub-field being probed (cross regime)")
    s.add_argument("--source", default="arxiv", help="comma list: arxiv,openalex")
    s.add_argument("--max", type=int, default=10)
    s.add_argument("--after", help="YYYY-MM-DD")
    s.add_argument("--before", help="YYYY-MM-DD (temporal cutoff)")
    s.add_argument("--no-relax", action="store_true", help="do not retry arXiv with OR when AND finds nothing")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser("add", help="register a paper found by other means (web search)")
    s.add_argument("--run", required=True)
    s.add_argument("--id", required=True)
    s.add_argument("--title", required=True)
    s.add_argument("--year", type=int)
    s.add_argument("--date", help="YYYY-MM-DD publication date (needed to verify a retrospective cutoff)")
    s.add_argument("--field", default="")
    s.add_argument("--url", default="")
    s.add_argument("--authors", default="")
    s.add_argument("--abstract", default="")
    s.set_defaults(fn=cmd_add)

    s = sub.add_parser("read", help="mark a paper as read after writing its digest")
    s.add_argument("id")
    s.add_argument("--run", required=True)
    s.add_argument("--level", choices=["full", "abstract"], default="full")
    s.add_argument("--digest", help="path to the digest (default: <run>/papers/<id>.md)")
    s.add_argument("--force", action="store_true", help="skip the full-text anchor check")
    s.set_defaults(fn=cmd_read)

    s = sub.add_parser("status", help="show reads, queries and unfilled artifacts")
    s.add_argument("--run", required=True)
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("check", help="run the validity gates")
    s.add_argument("--run", required=True)
    s.add_argument("--stage", choices=["problem", "gaps", "candidates", "reviews", "proposal", "all"], default="all")
    s.add_argument("--strict", action="store_true", help="treat warnings as errors")
    s.set_defaults(fn=cmd_check)
    return p


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except UsageError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
