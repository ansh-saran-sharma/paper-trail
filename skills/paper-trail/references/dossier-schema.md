# `dossier.json` schema

The template renders whatever sections are present. Omit a section key to omit the section. `assets/example-dossier.json` is a complete, valid example to copy from.

Shared conventions:
- Dates are ISO strings (`2026-09-14`).
- Any object carrying a number that came from an estimate has `confidence` (`verified` | `estimated` | `assumption`), plus `source_ref` when verified and `basis` when estimated. The build fails without them.
- `id` fields reuse ledger IDs so the visuals can cross-link (a feature card can open its decision history).

## `meta` (required)

```json
{
  "title": "Habitat: dossier",
  "audience": "team",
  "generated": "2026-10-12",
  "currency": "USD",
  "section_order": ["summary", "journey", "..."],
  "collapsed": ["skills"]
}
```
`audience`: `investor` | `team` | `engineer` | `personal`. `section_order` and `collapsed` are optional; the build fills defaults from the audience.

## `summary` (required)

```json
{
  "name": "Habitat",
  "one_liner": "A habit tracker that study groups share, so nobody quits alone.",
  "stage": "validating",
  "status": "MVP scoped, 9 of 15 interviews done, no code yet",
  "problem": "...", "solution": "...", "audience": "...", "why_now": "...", "objective": "...",
  "highlights": [
    {"label": "MVP build", "value": 6, "low": 5, "high": 8, "unit": "weeks", "confidence": "estimated", "basis": "..."},
    {"label": "Run cost at launch", "value": 45, "unit": "USD/month", "confidence": "verified", "source_ref": "https://..."}
  ]
}
```
`stage`: `idea` | `research` | `validating` | `building` | `launched` | `paused`. `problem`, `solution`, `audience`, `why_now`, `objective` are each optional; include what the ledger has. Up to 4 `highlights`; pick the numbers the audience will look for first.

## `journey`

```json
[
  {"id": "I-001", "title": "First concept", "date": "2026-09-02",
   "summary": "Started as a personal habit tracker for students...",
   "changes": [{"decision_id": "D-004", "to": "accepted", "text": "Offline sync added for patchy campus wifi"}]}
]
```
Chronological. `changes` lists the decision state changes that happened in this chapter, in plain language.

## `decisions`

```json
[
  {"id": "D-004", "title": "Offline sync", "area": "feature",
   "current_state": "rejected", "phase": null, "layer": null,
   "superseded_by": null, "revives": null,
   "details": "Full two-way sync of habits and check-ins",
   "history": [
     {"state": "proposed", "date": "2026-09-02", "reason": null, "source": "S1#m9", "iteration": "I-001"},
     {"state": "accepted", "date": "2026-09-03", "reason": "Students on patchy campus wifi", "source": "S1#m22", "iteration": "I-001"},
     {"state": "rejected", "date": "2026-09-10", "reason": "Doubles build time; 2 of 12 interviewees asked", "source": "S2#m6", "iteration": "I-002"}
   ]}
]
```
Include every decision, including rejected and superseded ones. `current_state` must equal the last `history` state. `features` and `tech` are derived from this list, so set `area`, `phase` and `layer` carefully.

## `features`

```json
{"intro": "Everything outside the MVP column is deliberately out of the first release."}
```
The board is derived from decisions with `area` `feature` or `scope`: accepted with `phase: "mvp"` → MVP; accepted with `phase: "later"` or `parked` → Later; `rejected` or `superseded` → Cut; `proposed` → Undecided. Include the key (even as `{}`) to render the section.

## `validation`

```json
{"verdict": "Early signal is positive but thin: 9 interviews, no paid commitment yet.",
 "evidence": [{"id": "V-001", "claim": "7 of 9 students said they quit habit apps within 2 weeks",
               "supports": "for", "strength": "moderate", "source_ref": "Interview notes, Sept 2026", "date": "2026-09-20"}]}
```

## `pros_cons`

```json
{"pros": [{"text": "...", "weight": 3}], "cons": [{"text": "...", "weight": 2}]}
```
`weight` 1–3 sets visual size; use it to show which ones actually matter.

## `dos_donts`

```json
{"do": [{"text": "Launch on one campus first", "why": "..."}], "dont": [{"text": "...", "why": "..."}]}
```

## `plan`

```json
{"start_date": "2026-11-02",
 "milestones": [
   {"id": "M-001", "name": "MVP", "goal": "...", "start_week": 0, "duration_weeks": 6,
    "deliverables": ["..."], "confidence": "estimated", "basis": "...", "depends_on": [], "is_mvp": true}
 ]}
```
`start_date` is optional; without it the axis shows week numbers.

## `costs`

```json
{"currency": "USD", "note": "Excludes the founder's own time.",
 "items": [
   {"id": "E-005", "label": "Hosting (Supabase Pro)", "category": "infra", "kind": "monthly",
    "value": 25, "confidence": "verified", "source_ref": "supabase.com/pricing, checked 2026-09-28",
    "history": [{"date": "2026-09-05", "value": 0}, {"date": "2026-09-28", "value": 25}]}
 ]}
```
`kind`: `one_time` | `monthly` | `yearly`. `low`/`high` optional. `history` optional, shows how the estimate moved.

## `tech`

```json
{"intro": "Chosen for one-person maintainability over scale."}
```
The stack is derived from accepted decisions with `area: "tech"`, grouped by `layer`; superseded tech choices show as struck-through alternatives under their replacement.

## `skills`

```json
{"items": [{"name": "React Native", "level": 3, "needed_for": "Mobile app", "have": "partial"}]}
```

## `team`

```json
{"note": "A solo build is realistic for the MVP.",
 "roles": [{"role": "Full-stack developer", "count": 1, "phase": "mvp", "essential": true, "why": "..."}]}
```
`phase`: `mvp` | `later` | `both`.

## `risks`

```json
{"items": [{"id": "R-001", "text": "...", "likelihood": 2, "impact": 3, "mitigation": "...", "status": "open"}]}
```

## `open_questions`

```json
[{"id": "Q-003", "text": "Will students pay, or does this need a campus licence?",
  "why_it_matters": "Decides the whole pricing model", "blocks": ["D-009"], "owner": null}]
```

## `sources`

```json
[{"id": "S1", "tool": "ChatGPT", "title": "habit app idea", "started": "2026-09-02", "ended": "2026-09-04", "messages": 48},
 {"id": "live", "tool": "Claude", "title": "This conversation", "started": "2026-09-15", "ended": "2026-10-12", "messages": null}]
```
