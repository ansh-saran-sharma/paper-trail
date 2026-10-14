#!/usr/bin/env python3
"""Work with an paper-trail ledger (JSONL, or markdown containing ```ledger blocks).

Subcommands:
  check   LEDGER...              validate events, transitions, references, confidence rules
  replay  LEDGER... [--json]     current state of everything, with full history
  merge   LEDGER... --out FILE   combine ledgers / chat checkpoint blocks, sorted by time, de-duplicated
  next-id LEDGER PREFIX          next free ID for a prefix, e.g. D -> D-014

Inputs can be .jsonl files or .md/.txt files with fenced ```ledger blocks
(how the ledger is kept in chat-only mode). Standard library only.
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

PREFIX = {"frame": "F", "iteration": "I", "decision": "D", "estimate": "E", "question": "Q",
          "risk": "R", "evidence": "V", "milestone": "M", "skill": "K", "guideline": "G", "note": "N"}
STATES = {"proposed", "accepted", "rejected", "parked", "superseded"}
TRANSITIONS = {
    None: {"proposed", "accepted", "rejected", "parked"},
    "proposed": {"accepted", "rejected", "parked"},
    "accepted": {"superseded", "rejected", "parked", "accepted"},
    "parked": {"accepted", "rejected", "proposed"},
    "rejected": {"proposed", "accepted"},
    "superseded": set(),
}
CONF = {"verified", "estimated", "assumption"}
FENCE = re.compile(r"```ledger\s*\n(.*?)```", re.S)


def load(paths):
    """Return list of (event, origin) in file order."""
    events = []
    for p in paths:
        path = Path(p)
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".jsonl":
            chunks = [(text, 0)]
        else:
            chunks = [(m.group(1), text[:m.start()].count("\n") + 1) for m in FENCE.finditer(text)]
            if not chunks and path.suffix.lower() == ".json":
                chunks = [(text, 0)]
        for chunk, base in chunks:
            for i, line in enumerate(chunk.splitlines(), 1):
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                origin = f"{path.name}:{base + i}"
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError as e:
                    events.append(({"__bad__": str(e), "__line__": line[:120]}, origin))
                    continue
                events.append((ev, origin))
    return events


def ts_key(ev):
    t = ev.get("ts") or ""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(t[:len(datetime.now().strftime(fmt))].rstrip("Z"), fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def check(events):
    errs, warns = [], []
    last_state, seen_ids, refs = {}, {}, []
    for ev, origin in events:
        if "__bad__" in ev:
            errs.append(f"{origin}: not valid JSON ({ev['__bad__']}): {ev['__line__']}")
            continue
        t, i = ev.get("type"), ev.get("id")
        if t not in PREFIX:
            errs.append(f"{origin}: unknown type {t!r}")
            continue
        if not i or not str(i).startswith(PREFIX[t] + "-"):
            errs.append(f"{origin}: id {i!r} should start with '{PREFIX[t]}-' for type {t}")
        if i in seen_ids and seen_ids[i] != t:
            errs.append(f"{origin}: id {i} reused with a different type ({seen_ids[i]} vs {t})")
        seen_ids.setdefault(i, t)
        if not ev.get("ts"):
            errs.append(f"{origin} ({i}): missing 'ts'")
        elif ts_key(ev) is None:
            warns.append(f"{origin} ({i}): 'ts' {ev['ts']!r} is not an ISO date")
        if not ev.get("source"):
            errs.append(f"{origin} ({i}): missing 'source' (use 'live' or an anchor like S2#m14)")

        if t == "decision":
            st = ev.get("state")
            if st not in STATES:
                errs.append(f"{origin} ({i}): unknown state {st!r}")
                continue
            prev = last_state.get(i)
            if st not in TRANSITIONS[prev]:
                errs.append(f"{origin} ({i}): invalid transition {prev or '(new)'} -> {st}"
                            + (" (superseded is final; create a new decision with 'revives')" if prev == "superseded" else ""))
            if prev is not None and not ev.get("reason"):
                warns.append(f"{origin} ({i}): '{st}' without a reason. Ask the person why "
                             f"\u201c{ev.get('title')}\u201d became {st}")
            if st == "superseded":
                if not ev.get("superseded_by"):
                    errs.append(f"{origin} ({i}): superseded needs 'superseded_by'")
                else:
                    refs.append((origin, i, "superseded_by", ev["superseded_by"]))
            if ev.get("revives"):
                refs.append((origin, i, "revives", ev["revives"]))
            if not ev.get("title"):
                errs.append(f"{origin} ({i}): decision needs 'title'")
            last_state[i] = st
        elif t in ("estimate", "milestone"):
            c = ev.get("confidence")
            if c not in CONF:
                errs.append(f"{origin} ({i}): confidence must be one of {sorted(CONF)}")
            elif c == "verified" and not ev.get("source_ref"):
                errs.append(f"{origin} ({i}): verified without 'source_ref'. Ask the person: where does "
                            f"\u201c{ev.get('metric') or ev.get('name')}\u201d come from? (or record it as estimated / assumption)")
            elif c == "estimated" and not ev.get("basis"):
                errs.append(f"{origin} ({i}): estimated without 'basis'. Ask the person: how was "
                            f"\u201c{ev.get('metric') or ev.get('name')}\u201d worked out? (or record it as an assumption)")
            if t == "estimate" and not isinstance(ev.get("value"), (int, float)):
                errs.append(f"{origin} ({i}): estimate 'value' must be a number")
            for dep in ev.get("depends_on") or []:
                refs.append((origin, i, "depends_on", dep))
        elif t == "question":
            for b in ev.get("blocks") or []:
                refs.append((origin, i, "blocks", b))
            if ev.get("status") == "answered" and not ev.get("answer"):
                warns.append(f"{origin} ({i}): answered without 'answer'")
        elif t == "risk":
            for k in ("likelihood", "impact"):
                if ev.get(k) not in (1, 2, 3):
                    errs.append(f"{origin} ({i}): {k} must be 1, 2 or 3")
        elif t == "frame" and ev.get("field") not in ("name", "one_liner", "problem", "solution", "audience", "why_now", "status", "objective"):
            warns.append(f"{origin} ({i}): unusual frame field {ev.get('field')!r}")

    for origin, i, key, ref in refs:
        if ref not in seen_ids:
            errs.append(f"{origin} ({i}): {key} points to unknown id {ref!r}")
    proposed = [k for k, v in last_state.items() if v == "proposed"]
    if proposed:
        warns.append(f"{len(proposed)} decision(s) still only proposed: {', '.join(sorted(proposed))}")
    return errs, warns


def replay(events):
    evs = [(e, o) for e, o in events if "__bad__" not in e and e.get("type") in PREFIX]
    # iterations, by time, so each event can be placed in a chapter
    iters = sorted([e for e, _ in evs if e["type"] == "iteration"], key=lambda e: (ts_key(e) or datetime.min))
    seen_iter, iters_u = set(), []
    for it in iters:
        if it["id"] not in seen_iter:
            seen_iter.add(it["id"])
            iters_u.append(it)

    def chapter(ev):
        t = ts_key(ev)
        cur = None
        for it in iters_u:
            it_t = ts_key(it)
            if t is not None and it_t is not None and it_t <= t:
                cur = it["id"]
        return cur

    out = {"frame": {}, "iterations": [], "decisions": {}, "estimates": {}, "questions": {}, "risks": {},
           "evidence": {}, "milestones": {}, "skills": {}, "guidelines": {}, "notes": {}}
    bucket = {"estimate": "estimates", "question": "questions", "risk": "risks", "evidence": "evidence",
              "milestone": "milestones", "skill": "skills", "guideline": "guidelines", "note": "notes"}
    for ev, _ in evs:
        t = ev["type"]
        if t == "frame":
            out["frame"][ev.get("field")] = ev.get("text")
        elif t == "iteration":
            if not any(x["id"] == ev["id"] for x in out["iterations"]):
                out["iterations"].append({"id": ev["id"], "title": ev.get("title"), "date": ev.get("ts"),
                                          "summary": ev.get("summary"), "source": ev.get("source")})
            else:
                x = next(x for x in out["iterations"] if x["id"] == ev["id"])
                x.update({k: ev[k] for k in ("title", "summary") if ev.get(k)})
        elif t == "decision":
            d = out["decisions"].setdefault(ev["id"], {"id": ev["id"], "history": []})
            for k in ("title", "area", "phase", "layer", "superseded_by", "revives", "details", "role", "count"):
                if ev.get(k) is not None:
                    d[k] = ev[k]
            d["current_state"] = ev.get("state")
            d["history"].append({"state": ev.get("state"), "date": ev.get("ts"), "reason": ev.get("reason"),
                                 "source": ev.get("source"), "iteration": chapter(ev),
                                 "backfilled": ev.get("backfilled", False)})
        else:
            b = out[bucket[t]]
            cur = b.setdefault(ev["id"], {"id": ev["id"], "history": []})
            snap = {k: v for k, v in ev.items() if k not in ("type",)}
            cur.update(snap)
            if t == "estimate":
                cur["history"].append({"date": ev.get("ts"), "value": ev.get("value"), "confidence": ev.get("confidence")})
            else:
                cur["history"].append({"date": ev.get("ts"), "source": ev.get("source")})
    out["iterations"].sort(key=lambda x: x["date"] or "")
    for k in ("decisions", "estimates", "questions", "risks", "evidence", "milestones", "skills", "guidelines", "notes"):
        out[k] = list(out[k].values())
    return out


def print_replay(st):
    f = st["frame"]
    print(f"# {f.get('name') or '(unnamed idea)'}")
    if f.get("one_liner"):
        print(f.get("one_liner"))
    print(f"\n## Iterations ({len(st['iterations'])})")
    for it in st["iterations"]:
        print(f"- {it['id']} {it['date']}: {it['title']}")
    print(f"\n## Decisions ({len(st['decisions'])})")
    for d in sorted(st["decisions"], key=lambda d: (d.get("area") or "", d["id"])):
        path = " -> ".join(h["state"] for h in d["history"])
        extra = f" (by {d['superseded_by']})" if d.get("superseded_by") else ""
        extra += f" (revives {d['revives']})" if d.get("revives") else ""
        print(f"- {d['id']} [{d.get('area', '?')}] {d.get('title')}: {d['current_state'].upper()}{extra}   path: {path}")
        last_reason = next((h["reason"] for h in reversed(d["history"]) if h.get("reason")), None)
        if last_reason:
            print(f"    why: {last_reason}")
    for key, label in (("estimates", "Estimates"), ("milestones", "Milestones"), ("questions", "Questions"),
                       ("risks", "Risks"), ("evidence", "Evidence"), ("skills", "Skills"), ("guidelines", "Guidelines")):
        if not st[key]:
            continue
        print(f"\n## {label} ({len(st[key])})")
        for x in st[key]:
            if key == "estimates":
                rng = f" [{x.get('low')}–{x.get('high')}]" if x.get("low") is not None else ""
                moved = " (moved: " + " -> ".join(str(h["value"]) for h in x["history"]) + ")" if len(x["history"]) > 1 else ""
                print(f"- {x['id']} {x.get('metric')}: {x.get('value')}{rng} {x.get('unit', '')} <{x.get('confidence')}>{moved}")
            elif key == "questions":
                print(f"- {x['id']} [{x.get('status', 'open')}] {x.get('text')}")
            elif key == "milestones":
                print(f"- {x['id']} {x.get('name')}: week {x.get('start_week')} +{x.get('duration_weeks')}w <{x.get('confidence')}>")
            elif key == "risks":
                print(f"- {x['id']} L{x.get('likelihood')}×I{x.get('impact')} [{x.get('status', 'open')}] {x.get('text')}")
            elif key == "evidence":
                print(f"- {x['id']} {x.get('supports')}/{x.get('strength')}: {x.get('claim')}")
            elif key == "skills":
                print(f"- {x['id']} {x.get('name')} L{x.get('level')} have={x.get('have')}")
            else:
                print(f"- {x['id']} {x.get('polarity')}: {x.get('text')}")


def main():
    if hasattr(sys.stdout, "reconfigure"):  # never crash on non-ASCII output (e.g. Windows consoles)
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("ledger", nargs="+")
    r = sub.add_parser("replay"); r.add_argument("ledger", nargs="+"); r.add_argument("--json", action="store_true")
    m = sub.add_parser("merge"); m.add_argument("ledger", nargs="+"); m.add_argument("--out", required=True)
    n = sub.add_parser("next-id"); n.add_argument("ledger"); n.add_argument("prefix")
    a = ap.parse_args()

    if a.cmd == "next-id":
        p = Path(a.ledger)
        evs = load([p]) if p.exists() else []
        nums = [int(m.group(1)) for e, _ in evs for m in [re.match(rf"{re.escape(a.prefix)}-(\d+)$", str(e.get("id", "")))] if m]
        print(f"{a.prefix}-{(max(nums) + 1 if nums else 1):03d}")
        return

    events = load(a.ledger)
    if a.cmd == "check":
        errs, warns = check(events)
        for w in warns:
            print("WARNING ", w)
        for e in errs:
            print("ERROR   ", e)
        print(f"\n{len(events)} events, {len(errs)} error(s), {len(warns)} warning(s).")
        sys.exit(1 if errs else 0)
    if a.cmd == "replay":
        st = replay(events)
        if a.json:
            print(json.dumps(st, indent=2, ensure_ascii=False))
        else:
            print_replay(st)
        return
    if a.cmd == "merge":
        seen, merged = set(), []
        good = [(e, o) for e, o in events if "__bad__" not in e]
        bad = len(events) - len(good)
        indexed = list(enumerate(good))
        indexed.sort(key=lambda x: ((ts_key(x[1][0]) or datetime.max), x[0]))
        for _, (e, _) in indexed:
            key = json.dumps(e, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            merged.append(e)
        Path(a.out).write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in merged), encoding="utf-8")
        print(f"Wrote {len(merged)} events to {a.out} ({len(good) - len(merged)} duplicates dropped, {bad} unreadable lines skipped).")
        errs, _ = check([(e, a.out) for e in merged])
        if errs:
            print(f"Merged ledger has {len(errs)} error(s); run 'check' on it.")


if __name__ == "__main__":
    main()
