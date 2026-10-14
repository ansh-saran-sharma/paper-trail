#!/usr/bin/env python3
"""Build a draft dossier.json from a ledger, so facts are copied mechanically, not retyped.

Usage:
    python scaffold_dossier.py LEDGER [LEDGER...] --audience team \
        [--sources .dossier/sources/sources.json] [--out dossier.json]

What it fills from the ledger (exactly, with full history and confidence):
    decisions, journey chapters and their state changes, costs, plan milestones,
    risks, evidence, skills, team roles, do's and don'ts, open questions, sources,
    and summary fields that exist as `frame` events.

What it leaves for you, marked with "TODO:" strings:
    prose the ledger can't write well: chapter summaries, journey change wording,
    the validation verdict, section intros, highlights, why_it_matters on questions.
    build_dossier.py refuses to build while any "TODO:" remains.

Sections with no supporting events are omitted, never stubbed.
Standard library only.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledger import load, replay, check  # noqa: E402

COST_KINDS = {"one_time", "monthly", "yearly"}


def day(ts):
    return (ts or "")[:10] or None


def main():
    if hasattr(sys.stdout, "reconfigure"):  # never crash on non-ASCII output (e.g. Windows consoles)
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ledger", nargs="+")
    ap.add_argument("--audience", default="team", choices=["investor", "team", "engineer", "personal"])
    ap.add_argument("--sources", help="sources.json from normalize_exports.py")
    ap.add_argument("--live-title", default="This conversation")
    ap.add_argument("--live-tool", default="AI assistant")
    ap.add_argument("--out", default="dossier.json")
    a = ap.parse_args()

    events = load(a.ledger)
    errs, _ = check(events)
    if errs:
        print("The ledger has errors, so no draft was written. Fix them first.")
        print("Lines saying 'Ask the person' need their input; put those questions to them together, with the options shown.")
        print("The rest you can correct in the ledger (by appending a corrected event, never by editing old lines).\n")
        for e in errs[:30]:
            print("  -", e)
        if len(errs) > 30:
            print(f"  ... and {len(errs) - 30} more (python ledger.py check LEDGER)")
        sys.exit(1)
    st = replay(events)
    f = st["frame"]
    d = {"meta": {"title": f"{f.get('name') or 'TODO: name'}: idea dossier", "audience": a.audience,
                  "generated": max((day(e.get("ts")) or "") for e, _ in events) or None, "currency": "USD"}}

    # ---- summary
    S = {"name": f.get("name") or "TODO: name", "one_liner": f.get("one_liner") or "TODO: one sentence, under 20 words",
         "stage": "TODO: idea | research | validating | building | launched | paused",
         "status": f.get("status") or "TODO: where things stand, in one sentence"}
    for k in ("problem", "solution", "audience", "why_now", "objective"):
        if f.get(k):
            S[k] = f[k]
    S["highlights"] = []  # chosen by you: up to 4 numbers this audience looks for first
    d["summary"] = S

    # ---- decisions (exact copy of replayed history)
    decs = []
    for x in st["decisions"]:
        decs.append({
            "id": x["id"], "title": x.get("title"), "area": x.get("area", "other"),
            "current_state": x["current_state"],
            "phase": x.get("phase"),
            "layer": x.get("layer"), "superseded_by": x.get("superseded_by"), "revives": x.get("revives"),
            "details": x.get("details"),
            "history": [{"state": h["state"], "date": day(h["date"]), "reason": h.get("reason"),
                         "source": h.get("source"), "iteration": h.get("iteration")} for h in x["history"]],
        })
    if decs:
        d["decisions"] = decs

    # ---- journey: chapters with the decision changes that happened inside each
    if st["iterations"]:
        chapters = []
        for it in st["iterations"]:
            changes = []
            for x in decs:
                for h in x["history"]:
                    if h["iteration"] == it["id"]:
                        changes.append({"decision_id": x["id"], "to": h["state"],
                                        "text": f"{x['title']}: {h['reason']}" if h.get("reason") else x["title"]})
            chapters.append({"id": it["id"], "title": it.get("title"), "date": day(it.get("date")),
                             "summary": it.get("summary") or "TODO: 2–3 sentences on what changed and why",
                             "changes": changes})
        d["journey"] = chapters

    if any(x["area"] in ("feature", "scope") for x in decs):
        d["features"] = {"intro": "TODO: one sentence framing what's in the MVP and what's deliberately out"}
    if any(x["area"] == "tech" and x["current_state"] == "accepted" for x in decs):
        d["tech"] = {"intro": "TODO: one sentence on what the stack was chosen for"}

    # ---- team from team decisions that are accepted or parked
    roles = []
    for x in st["decisions"]:
        if x.get("area") == "team" and x["current_state"] in ("accepted", "parked"):
            roles.append({"role": x.get("role") or x.get("title"), "count": x.get("count") or 1,
                          "phase": (x.get("phase") or "mvp") if x["current_state"] == "accepted" else "later",
                          "essential": x["current_state"] == "accepted",
                          "why": next((h["reason"] for h in reversed(x["history"]) if h.get("reason")), None)})
    if roles:
        d["team"] = {"note": "TODO: one sentence on whether a team is needed at all", "roles": roles}

    # ---- costs
    items = []
    for e in st["estimates"]:
        if e.get("kind") not in COST_KINDS:
            continue
        it = {"id": e["id"], "label": e.get("metric"), "category": e.get("category", "other"), "kind": e["kind"],
              "value": e["value"], "confidence": e.get("confidence")}
        for k in ("low", "high", "basis", "source_ref"):
            if e.get(k) is not None:
                it[k] = e[k]
        if len(e["history"]) > 1:
            it["history"] = [{"date": day(h["date"]), "value": h["value"]} for h in e["history"]]
        items.append(it)
    if items:
        units = {(e.get("unit") or "")[:3] for e in st["estimates"] if e.get("kind") in COST_KINDS}
        cur = units.pop() if len(units) == 1 and next(iter(units or {""}), "").isalpha() else "USD"
        d["meta"]["currency"] = cur if cur.isupper() and len(cur) == 3 else "USD"
        d["costs"] = {"currency": d["meta"]["currency"], "note": "TODO: what the costs include and exclude", "items": items}

    # ---- plan
    if st["milestones"]:
        ms = []
        for m in sorted(st["milestones"], key=lambda m: m.get("start_week") or 0):
            o = {k: m.get(k) for k in ("id", "name", "goal", "start_week", "duration_weeks", "confidence")}
            o["deliverables"] = m.get("deliverables") or []
            o["depends_on"] = m.get("depends_on") or []
            for k in ("basis", "source_ref"):
                if m.get(k):
                    o[k] = m[k]
            o["is_mvp"] = "mvp" in (m.get("name") or "").lower()
            ms.append(o)
        d["plan"] = {"milestones": ms}

    if st["evidence"]:
        d["validation"] = {"verdict": "TODO: an honest one-to-two sentence read of the evidence",
                           "evidence": [{"id": e["id"], "claim": e.get("claim"), "supports": e.get("supports"),
                                         "strength": e.get("strength"), "source_ref": e.get("source_ref"),
                                         "date": day(e.get("ts"))} for e in st["evidence"]]}
    if st["guidelines"]:
        g = st["guidelines"]
        d["dos_donts"] = {"do": [{"text": x["text"], "why": x.get("why")} for x in g if x.get("polarity") == "do"],
                          "dont": [{"text": x["text"], "why": x.get("why")} for x in g if x.get("polarity") == "dont"]}
    if st["skills"]:
        d["skills"] = {"items": [{k: s.get(k) for k in ("name", "level", "needed_for", "have")} for s in st["skills"]]}
    if st["risks"]:
        d["risks"] = {"items": [{k: r.get(k) for k in ("id", "text", "likelihood", "impact", "mitigation", "status")}
                                for r in st["risks"]]}

    # ---- open questions: open ones, plus every still-proposed decision without a question
    oq = [{"id": q["id"], "text": q.get("text"), "why_it_matters": "TODO: what this decides or blocks",
           "blocks": q.get("blocks") or [], "owner": q.get("owner")}
          for q in st["questions"] if q.get("status", "open") == "open"]
    covered = {b for q in oq for b in q["blocks"]}
    for x in decs:
        if x["current_state"] == "proposed" and x["id"] not in covered:
            oq.append({"id": f"Q-{x['id']}", "text": f"Undecided: {x['title']}",
                       "why_it_matters": "TODO: what depends on this decision", "blocks": [x["id"]]})
    for q in oq:
        if q.get("owner") is None:
            q.pop("owner", None)
    if oq:
        d["open_questions"] = oq

    # ---- sources
    srcs = []
    if a.sources and Path(a.sources).exists():
        srcs = [{k: s.get(k) for k in ("id", "tool", "title", "started", "ended", "messages")}
                for s in json.loads(Path(a.sources).read_text(encoding="utf-8"))]
    cited = {(h.get("source") or "").split("#")[0] for x in decs for h in x["history"]}
    cited |= {(e.get("source") or "").split("#")[0] for e, _ in events}
    srcs = [s for s in srcs if s["id"] in cited]
    live = sorted(day(e.get("ts")) for e, _ in events if e.get("source") == "live" and e.get("ts"))
    if live:
        srcs.append({"id": "live", "tool": a.live_tool, "title": a.live_title, "started": live[0], "ended": live[-1], "messages": None})
    undated = [s["id"] for s in srcs if not s.get("started")]
    if srcs:
        d["sources"] = srcs

    Path(a.out).write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    todos = json.dumps(d).count("TODO:")
    present = [k for k in d if k != "meta"]
    print(f"Wrote {a.out}: {len(present)} sections ({', '.join(present)}), {todos} TODO(s) to write.")
    if undated:
        print(f"Sources with no dates: {', '.join(undated)}. Ask the person roughly when, or the timeline will omit them.")
    if not S["highlights"] and (st["estimates"] or st["milestones"]):
        print("Pick up to 4 summary.highlights for this audience (each needs confidence + basis/source_ref).")


if __name__ == "__main__":
    main()
