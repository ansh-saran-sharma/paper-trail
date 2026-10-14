#!/usr/bin/env python3
"""Validate a dossier.json and render it into a self-contained HTML file.

Usage:
    python build_dossier.py dossier.json --out dossier.html [--report findings.json] [--strict] [--no-webfonts]

Every finding says who can resolve it and how:
  NEEDED FROM THE PERSON   facts only they know (a source, how a number was worked out,
                           what actually happened), phrased as questions with honest options
  AGENT CAN FIX            structure and prose the agent can repair from the ledger
Required findings refuse the build: placeholders, "verified" numbers without a source,
"estimated" numbers without a basis, decisions that contradict their own history.
Optional findings ("would make it stronger") don't. --strict makes them required.
--report FILE writes the same findings as JSON.

Standard library only.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = HERE.parent / "assets" / "dossier-template.html"
PLACEHOLDER = "const DOSSIER = null; /*__DOSSIER_DATA__*/"

STATES = {"proposed", "accepted", "rejected", "parked", "superseded"}
CONF = {"verified", "estimated", "assumption"}
AUDIENCES = {"investor", "team", "engineer", "personal"}
SECTIONS = ["summary", "journey", "decisions", "features", "validation", "pros_cons",
            "dos_donts", "plan", "costs", "tech", "skills", "team", "risks",
            "open_questions", "sources"]
ORDERS = {
    "investor": ["summary", "validation", "pros_cons", "plan", "costs", "risks", "team",
                 "features", "journey", "decisions", "tech", "open_questions", "sources"],
    "team": ["summary", "journey", "decisions", "features", "plan", "costs", "tech", "skills",
             "team", "dos_donts", "risks", "validation", "pros_cons", "open_questions", "sources"],
    "engineer": ["summary", "features", "tech", "decisions", "plan", "skills", "dos_donts", "risks",
                 "open_questions", "costs", "journey", "validation", "pros_cons", "team", "sources"],
    "personal": ["summary", "journey", "decisions", "features", "open_questions", "plan", "costs",
                 "tech", "skills", "team", "dos_donts", "risks", "validation", "pros_cons", "sources"],
}
COLLAPSED = {"investor": ["decisions", "tech"], "engineer": ["validation", "pros_cons"]}
OMIT = {"investor": ["skills"]}  # left out unless meta.section_order lists them explicitly
TRANSITIONS = {
    None: {"proposed", "accepted", "rejected", "parked"},
    "proposed": {"accepted", "rejected", "parked"},
    "accepted": {"superseded", "rejected", "parked", "accepted"},
    "parked": {"accepted", "rejected", "proposed"},
    "rejected": {"proposed", "accepted"},
    "superseded": set(),
}


class Issue:
    """One problem found in dossier.json.

    who:      "person" if only the person can supply it (a source, a reason, a number),
              "agent" if the agent can fix it from the ledger or by writing prose.
    blocking: True if the build is refused until it's resolved.
    ask:      for "person" issues, the question to put to them, in plain language.
    options:  honest ways to resolve it, e.g. give a source, or downgrade the confidence.
    """
    def __init__(self, where, msg, who="agent", blocking=True, ask=None, options=None, fix=None):
        self.where, self.msg, self.who, self.blocking = where, msg, who, blocking
        self.ask, self.options, self.fix = ask, options or [], fix

    def as_dict(self):
        return {k: v for k, v in vars(self).items() if v not in (None, [])}


class Report:
    def __init__(self):
        self.issues = []

    def err(self, where, msg, **kw):
        self.issues.append(Issue(where, msg, blocking=True, **kw))

    def warn(self, where, msg, **kw):
        self.issues.append(Issue(where, msg, blocking=False, **kw))

    @property
    def errors(self):
        return [i for i in self.issues if i.blocking]

    @property
    def warnings(self):
        return [i for i in self.issues if not i.blocking]


def describe(obj, unit_hint=""):
    """Human label for a number-carrying object: 'Supabase Pro hosting ($25/month)'."""
    label = obj.get("label") or obj.get("name") or obj.get("metric") or "this number"
    v = obj.get("value")
    if isinstance(v, (int, float)):
        unit = obj.get("unit") or unit_hint
        return f"\u201c{label}\u201d ({v:g}{(' ' + unit) if unit else ''})"
    if obj.get("duration_weeks") is not None:
        return f"\u201c{label}\u201d ({obj['duration_weeks']:g} weeks)"
    return f"\u201c{label}\u201d"


def check_conf(obj, where, r, needs_number=True, unit_hint=""):
    what = describe(obj, unit_hint)
    if needs_number and not isinstance(obj.get("value"), (int, float)):
        r.err(where, "'value' must be a number", who="person",
              ask=f"What is the figure for {what}? A single best number is fine; add a low and high if unsure.",
              options=["Give the number", "Remove this item"])
    c = obj.get("confidence")
    if c not in CONF:
        r.err(where, f"'confidence' must be one of {sorted(CONF)} (got {c!r})", who="person",
              ask=f"How sure are we about {what}? Was it checked against a source, worked out from something concrete, or a guess?",
              options=["Checked: give the source (Verified)", "Worked out: explain how (Estimated)", "A guess (Assumption)"])
        return
    if c == "verified" and not obj.get("source_ref"):
        r.err(where, "marked verified but has no 'source_ref'", who="person",
              ask=f"Where does {what} come from? A link, document, invoice, quote or pricing page is enough.",
              options=["Give the source: it stays Verified",
                       "Explain how it was worked out: it becomes Estimated",
                       "It's a rough guess: it becomes Assumption",
                       "Remove this number"])
    if c == "estimated" and not obj.get("basis"):
        r.err(where, "marked estimated but has no 'basis' explaining how it was worked out", who="person",
              ask=f"How was {what} worked out? One sentence is enough, e.g. "
                  + ("\u201cthree screens at about two weeks each, solo\u201d." if obj.get("duration_weeks") is not None or "week" in str(obj.get("unit", ""))
                     else "\u201cthe starter plan price plus a small database\u201d."),
              options=["Explain the calculation: it stays Estimated",
                       "It's a guess: it becomes Assumption",
                       "Remove this number"])
    lo, hi, v = obj.get("low"), obj.get("high"), obj.get("value")
    if (lo is None) != (hi is None):
        r.warn(where, "has only one of low/high", who="person",
               ask=f"What's the realistic range for {what}? Give both a low and a high, or neither.")
    if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and isinstance(v, (int, float)):
        if not (lo <= v <= hi):
            r.err(where, f"value {v} is outside its range {lo}\u2013{hi}", who="person",
                  ask=f"{what} falls outside its own range ({lo:g} to {hi:g}). Which is right: the number or the range?",
                  options=["Correct the number", "Correct the range"])


def validate(d):
    r = Report()
    if not isinstance(d, dict):
        r.err("root", "must be a JSON object", fix="Rebuild dossier.json with scaffold_dossier.py")
        return r

    # Placeholders: the agent writes prose, but some fields are facts only the person knows.
    PERSON_TODOS = {
        "dossier.summary.name": "What is the idea called? A working name is fine.",
        "dossier.summary.stage": "Where does the idea stand: just an idea, researching, validating with real people, building, launched, or paused?",
    }

    def find_todos(o, path):
        if isinstance(o, str) and o.startswith("TODO:"):
            if path in PERSON_TODOS:
                r.err(path, "still a placeholder", who="person", ask=PERSON_TODOS[path])
            else:
                r.err(path, f"still a placeholder ({o[5:65].strip()})",
                      fix="Write this from the ledger and conversation; ask the person only if the ledger has nothing on it")
        elif isinstance(o, dict):
            for k, v in o.items():
                find_todos(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                find_todos(v, f"{path}[{i}]")
    find_todos(d, "dossier")
    for k in sorted(set(d) - set(SECTIONS) - {"meta"}):
        r.warn(k, "unknown top-level key; the template will ignore it", fix="Remove it or rename it to a known section key")

    meta = d.get("meta")
    if not isinstance(meta, dict):
        r.err("meta", "required object", fix="Add meta with title, audience and generated date")
        meta = {}
    if meta.get("audience") not in AUDIENCES:
        r.warn("meta.audience", f"should be one of {sorted(AUDIENCES)}; defaulting to 'team'", who="person",
               ask="Who is this dossier for: investors, your team or cofounder, engineers who will build it, or just you?")

    S = d.get("summary")
    if not isinstance(S, dict) or not S.get("name"):
        r.err("summary.name", "required", who="person", ask=PERSON_TODOS["dossier.summary.name"])
        S = S if isinstance(S, dict) else {}
    if S.get("one_liner") and len(S["one_liner"].split()) > 25:
        r.warn("summary.one_liner", "longer than ~20 words", fix="Tighten it to one short sentence")
    for i, hl in enumerate(S.get("highlights") or []):
        where = f"summary.highlights[{i}]"
        check_conf(hl, where, r)
        prose = " ".join(str(S.get(k) or "") for k in ("status", "problem", "solution", "objective")).lower()
        disclosed = any(w in prose for w in ("guess", "assum", "unverified", "not yet checked", "rough"))
        if hl.get("confidence") == "assumption" and not disclosed:
            r.warn(where, "headline number is an assumption but the summary text doesn't say so",
                   fix="Say it's a guess in summary.status, or choose a better-supported headline number")
    if len(S.get("highlights") or []) > 4:
        r.warn("summary.highlights", "more than 4 highlights dilutes the first screen", fix="Keep the 4 this audience cares about most")

    # decisions
    decs = d.get("decisions") or []
    ids = {}
    REBUILD = "Re-run scaffold_dossier.py from the ledger rather than editing decisions by hand"
    for i, dec in enumerate(decs):
        where = f"decisions[{i}] ({dec.get('id', '?')})"
        if not dec.get("id") or not dec.get("title"):
            r.err(where, "needs 'id' and 'title'", fix=REBUILD)
            continue
        if dec["id"] in ids:
            r.err(where, "duplicate id", fix=REBUILD)
        ids[dec["id"]] = dec
        hist = dec.get("history") or []
        if not hist:
            r.err(where, "empty 'history'", fix=REBUILD)
            continue
        prev = None
        for j, ev in enumerate(hist):
            st = ev.get("state")
            if st not in STATES:
                r.err(f"{where}.history[{j}]", f"unknown state {st!r}", fix=REBUILD)
                break
            if st not in TRANSITIONS[prev]:
                r.err(f"{where}.history[{j}]", f"invalid transition {prev or '(new)'} -> {st}", who="person",
                      ask=f"The record for \u201c{dec['title']}\u201d goes from {prev or 'nothing'} straight to {st}, which can't happen. "
                          f"What actually happened to it, and in what order?",
                      fix="If the ledger has the steps in the wrong order, fix the order; if a step is missing, ask the person")
            if j > 0 and not ev.get("reason"):
                verb = {"accepted": "accepted", "rejected": "dropped", "parked": "put off for later",
                        "superseded": "replaced", "proposed": "brought back"}.get(st, st)
                r.warn(f"{where}.history[{j}]", f"'{st}' has no reason", who="person",
                       ask=f"Why was \u201c{dec['title']}\u201d {verb}? One sentence is enough.")
            prev = st
        cur = dec.get("current_state")
        if cur and cur != hist[-1].get("state"):
            r.err(where, f"current_state {cur!r} disagrees with its own history (last: {hist[-1].get('state')!r})",
                  fix=REBUILD + "; if the ledger itself is unclear, ask the person which state is current")
        if hist[-1].get("state") == "superseded" and not dec.get("superseded_by"):
            r.err(where, "superseded but no 'superseded_by'", who="person",
                  ask=f"\u201c{dec['title']}\u201d was replaced. What replaced it?",
                  fix="Look for the replacing decision in the ledger first")
        if dec.get("area") in ("feature", "scope") and hist[-1].get("state") == "accepted" and dec.get("phase") not in ("mvp", "later"):
            r.warn(where, "accepted feature without phase 'mvp' or 'later'; it will show under MVP", who="person",
                   ask=f"Is \u201c{dec['title']}\u201d part of the first version (MVP), or for later?")
        if dec.get("area") == "tech" and hist[-1].get("state") == "accepted" and not dec.get("layer"):
            r.warn(where, "accepted tech decision without 'layer'; it will show under 'other'",
                   fix="Set layer (frontend, mobile, backend, ai, data, infra, tooling) from what the technology is")
    for dec in decs:
        for key in ("superseded_by", "revives"):
            ref = dec.get(key)
            if ref and ref not in ids:
                r.err(f"decisions ({dec.get('id')})", f"{key} points to unknown id {ref!r}", fix=REBUILD)

    for i, ch in enumerate(d.get("journey") or []):
        for j, c in enumerate(ch.get("changes") or []):
            if c.get("decision_id") and c["decision_id"] not in ids:
                r.warn(f"journey[{i}].changes[{j}]", f"decision_id {c['decision_id']!r} not in decisions", fix=REBUILD)
            if c.get("to") not in STATES:
                r.err(f"journey[{i}].changes[{j}]", f"'to' must be a decision state (got {c.get('to')!r})",
                      fix="Copy the state from the matching decision's history")

    if "features" in d and not any(x.get("area") in ("feature", "scope") for x in decs):
        r.warn("features", "section present but no feature/scope decisions", fix="Remove the features section")
    if "tech" in d and not any(x.get("area") == "tech" and (x.get("history") or [{}])[-1].get("state") == "accepted" for x in decs):
        r.warn("tech", "section present but no accepted tech decisions", fix="Remove the tech section")

    # costs
    C = d.get("costs")
    if C is not None:
        items = C.get("items") or []
        if not items:
            r.warn("costs", "no items", fix="Remove the section and add an open question about costs")
        cur_code = C.get("currency") or meta.get("currency") or "USD"
        for i, it in enumerate(items):
            where = f"costs.items[{i}]"
            unit = {"monthly": f"{cur_code}/month", "yearly": f"{cur_code}/year"}.get(it.get("kind"), cur_code)
            check_conf(it, where, r, unit_hint=unit)
            if it.get("kind") not in ("one_time", "monthly", "yearly"):
                r.err(where, "'kind' must be one_time, monthly or yearly", who="person",
                      ask=f"Is {describe(it)} a one-time cost, a monthly cost, or a yearly cost?")
        if items and all(it.get("confidence") == "assumption" for it in items):
            biggest = sorted(items, key=lambda x: -(x.get("high") or x.get("value") or 0))[:2]
            r.warn("costs", "every cost is an assumption", who="person",
                   ask="All the costs are guesses so far. Can you check the biggest ones ("
                       + ", ".join(describe(b) for b in biggest) + ") against a price list or quote?")

    # plan
    P = d.get("plan")
    if P is not None:
        ms = P.get("milestones") or []
        if not ms:
            r.warn("plan", "no milestones", fix="Remove the section")
        mids = {m.get("id") for m in ms}
        for i, m in enumerate(ms):
            where = f"plan.milestones[{i}]"
            missing = [k for k in ("start_week", "duration_weeks") if not isinstance(m.get(k), (int, float))]
            if missing:
                r.err(where, f"{' and '.join(missing)} must be numbers", who="person",
                      ask=f"For the \u201c{m.get('name', 'unnamed')}\u201d phase: when does it start (weeks from the beginning) and roughly how many weeks will it take?")
            check_conf(m, where, r, needs_number=False)
            for dep in m.get("depends_on") or []:
                if dep not in mids:
                    r.warn(where, f"depends_on unknown milestone {dep!r}", fix="Remove the dependency or add the milestone")

    for key, field in (("validation", "evidence"), ("skills", "items"), ("risks", "items"), ("team", "roles")):
        sec = d.get(key)
        if sec is not None and not (sec.get(field) or []):
            r.warn(key, f"no {field}", fix="Remove the section")
    for i, rk in enumerate((d.get("risks") or {}).get("items") or []):
        bad = [k for k in ("likelihood", "impact") if rk.get(k) not in (1, 2, 3)]
        if bad:
            r.err(f"risks.items[{i}]", f"{' and '.join(bad)} must be 1, 2 or 3", who="person",
                  ask=f"For the risk \u201c{rk.get('text', '?')}\u201d: how likely is it (low, medium, high), and how bad would it be (low, medium, high)?")
    for i, ev in enumerate((d.get("validation") or {}).get("evidence") or []):
        if ev.get("supports") not in ("for", "against"):
            r.err(f"validation.evidence[{i}]", "'supports' must be 'for' or 'against'", who="person",
                  ask=f"Does \u201c{ev.get('claim', '?')}\u201d count in favour of the idea, or against it?")
    for i, k in enumerate((d.get("skills") or {}).get("items") or []):
        if k.get("level") not in (1, 2, 3, 4, 5):
            r.err(f"skills.items[{i}]", "'level' must be 1-5", who="person",
                  ask=f"How much {k.get('name', 'of this skill')} is needed, from 1 (basic) to 5 (expert)?")
    pc = d.get("pros_cons")
    if pc is not None and not (pc.get("pros") or pc.get("cons")):
        r.warn("pros_cons", "empty", fix="Remove the section")
    dd = d.get("dos_donts")
    if dd is not None and not (dd.get("do") or dd.get("dont")):
        r.warn("dos_donts", "empty", fix="Remove the section")

    oq = d.get("open_questions") or []
    pending = [x for x in decs if (x.get("history") or [{}])[-1].get("state") == "proposed"]
    if pending and not oq:
        r.warn("open_questions", f"{len(pending)} decisions are still only proposed but no open questions are listed",
               fix="Add an open question for each: " + ", ".join(x.get("title", "?") for x in pending))
    if meta.get("audience") == "investor":
        expect = {"costs": "what it will cost", "plan": "a timeline", "validation": "evidence that people want it",
                  "risks": "the main risks"}
        for k, words in expect.items():
            if k not in d and not any(k.rstrip("s") in (q.get("text", "") + q.get("why_it_matters", "")).lower() for q in oq):
                r.warn(k, "investors usually expect this section", who="person",
                       ask=f"Investors usually look for {words}. Do you have anything on that? If not, I'll list it as an open question rather than make it up.")
    if not d.get("sources"):
        r.warn("sources", "no sources listed", fix="Add the conversations this came from (sources.json and 'live')")
    return r


def print_report(r, built):
    person_block = [i for i in r.errors if i.who == "person"]
    agent_block = [i for i in r.errors if i.who == "agent"]
    person_opt = [i for i in r.warnings if i.who == "person"]
    agent_opt = [i for i in r.warnings if i.who == "agent"]
    if not built:
        print("NOT BUILT. These must be resolved before the dossier can be trusted.\n")
    if person_block:
        print(f"NEEDED FROM THE PERSON ({len(person_block)}), required to build:")
        for n, i in enumerate(person_block, 1):
            print(f"  {n}. {i.ask}")
            for o in i.options:
                print(f"       - {o}")
            print(f"       [{i.where}: {i.msg}]")
        print()
    if agent_block:
        print(f"AGENT CAN FIX ({len(agent_block)}), required to build:")
        for i in agent_block:
            print(f"  - {i.where}: {i.msg}" + (f"\n      fix: {i.fix}" if i.fix else ""))
        print()
    if person_opt:
        print(f"WOULD MAKE IT STRONGER, ASK THE PERSON ({len(person_opt)}), optional:")
        for i in person_opt:
            print(f"  - {i.ask}  [{i.where}]")
        print()
    if agent_opt:
        print(f"WOULD MAKE IT STRONGER, AGENT ({len(agent_opt)}), optional:")
        for i in agent_opt:
            print(f"  - {i.where}: {i.msg}" + (f" ({i.fix})" if i.fix else ""))
        print()


def main():
    if hasattr(sys.stdout, "reconfigure"):  # never crash on non-ASCII output (e.g. Windows consoles)
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dossier", help="path to dossier.json")
    ap.add_argument("--out", default="dossier.html")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--report", metavar="FILE",
                    help="also write the findings as JSON (what's needed from the person, what the agent can fix)")
    ap.add_argument("--no-webfonts", action="store_true",
                    help="drop the Google Fonts links so the file makes no network requests (system fonts are used)")
    a = ap.parse_args()

    try:
        data = json.loads(Path(a.dossier).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"Invalid JSON in {a.dossier}: {e}")

    r = validate(data)
    refused = bool(r.errors) or (a.strict and bool(r.warnings))
    if a.strict:
        for i in r.warnings:
            i.blocking = True
    if a.report:
        Path(a.report).write_text(json.dumps({
            "built": not refused,
            "needed_from_person": [i.as_dict() for i in r.errors if i.who == "person"],
            "agent_can_fix": [i.as_dict() for i in r.errors if i.who == "agent"],
            "optional_ask_person": [i.as_dict() for i in r.warnings if i.who == "person"],
            "optional_agent": [i.as_dict() for i in r.warnings if i.who == "agent"],
        }, indent=2, ensure_ascii=False), encoding="utf-8")
    print_report(r, built=not refused)
    if refused:
        n_person = sum(1 for i in r.errors if i.who == "person")
        sys.exit(f"Not built: {len(r.errors)} required item(s) ({n_person} need the person), "
                 f"{len(r.warnings)} optional.")

    meta = data.setdefault("meta", {})
    aud = meta.get("audience") if meta.get("audience") in AUDIENCES else "team"
    meta["audience"] = aud
    explicit = bool(meta.get("section_order"))
    if not explicit:
        meta["section_order"] = list(ORDERS[aud])
    if "collapsed" not in meta:
        meta["collapsed"] = COLLAPSED.get(aud, [])
    # make sure every present section is reachable, except ones this audience leaves out by default
    for k in SECTIONS:
        if k in data and k not in meta["section_order"]:
            if not explicit and k in OMIT.get(aud, []):
                print(f"NOTE     '{k}' left out for the {aud} audience; list it in meta.section_order to include it")
                continue
            order = meta["section_order"]
            tail = [i for i, x in enumerate(order) if x in ("open_questions", "sources")]
            order.insert(tail[0] if tail else len(order), k)

    tpl = Path(a.template).read_text(encoding="utf-8")
    if PLACEHOLDER not in tpl:
        sys.exit(f"Template {a.template} has no data placeholder line: {PLACEHOLDER}")
    if a.no_webfonts:
        tpl = "\n".join(l for l in tpl.splitlines() if "fonts.googleapis.com" not in l and "fonts.gstatic.com" not in l)
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    Path(a.out).write_text(tpl.replace(PLACEHOLDER, f"const DOSSIER = {payload};"), encoding="utf-8")
    present = [k for k in meta["section_order"] if k in data]
    print(f"\nBuilt {a.out} for audience '{aud}' with {len(present)} sections: {', '.join(present)}"
          f" ({len(r.warnings)} warning(s)).")


if __name__ == "__main__":
    main()
