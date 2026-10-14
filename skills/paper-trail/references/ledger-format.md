# Ledger format

The ledger is an append-only list of events, one JSON object per line (JSONL). Nothing is ever edited or deleted. To change something, append a new event with the same ID; for each ID, the latest event is the current state and the earlier ones are its history.

In chat-only mode the same lines go inside a fenced block:

````
```ledger
{"type":"decision","id":"D-004","state":"rejected","title":"Offline sync","area":"feature","reason":"Doubles build time; only 2 of 12 interviewees asked for it","ts":"2026-10-03","source":"live"}
```
````

## Fields every event has

| Field | Required | Meaning |
|---|---|---|
| `type` | yes | One of the types below |
| `id` | yes | Stable ID, prefix by type (see below). Reuse it to update the same thing |
| `ts` | yes | ISO date or datetime when this happened. For ingested events, the source message time if known |
| `source` | yes | `live` for the current conversation, or a source anchor like `S2#m14` from ingestion |
| `backfilled` | no | `true` if written after the fact from a transcript rather than as it happened |

IDs are sequential per prefix: `D-001`, `D-002`… Check the ledger for the highest existing number before assigning a new one.

## Event types

### `frame` — what the idea is
The core description. Fields: `field` (one of `name`, `one_liner`, `problem`, `solution`, `audience`, `why_now`, `status`, `objective`), `text`. ID: `F-<field>`, for example `F-problem`. Later events with the same field replace the earlier text, and the change shows in the journey.

### `iteration` — a chapter in the journey
Marks the start of a phase of thinking: "Initial concept", "Pivot to B2B", "Cost cutting pass". Fields: `title`, `summary`. ID prefix `I-`. Events after it belong to it until the next iteration. Record one whenever the direction meaningfully shifts; it's what makes the timeline readable.

### `decision` — anything chosen, dropped or deferred
Fields:
- `title`: short noun phrase ("Offline sync", "Postgres over Firestore", "Freemium pricing")
- `area`: `feature`, `scope`, `tech`, `business`, `pricing`, `audience`, `design`, `team`, `ops`, `legal`, `other`
- `state`: see the state machine below
- `reason`: why this state, in one or two sentences. Required for every state except the first `proposed`
- `phase`: for accepted features and tech, `mvp` or `later`
- `layer`: for `tech` decisions, which part of the stack (`frontend`, `backend`, `data`, `infra`, `ai`, `mobile`, `tooling`…)
- `role`, `count`: for `team` decisions, the role name and headcount
- `superseded_by`: required when state is `superseded`, the decision ID that replaced it
- `revives`: on a new decision that brings back part of a rejected or superseded one, the old ID
- `details`: optional extra description

ID prefix `D-`.

### `estimate` — any number
Fields:
- `metric`: what is measured ("Monthly hosting", "MVP build time", "Price per seat")
- `value`, and optionally `low` and `high` for a range
- `unit`: `USD`, `USD/month`, `weeks`, `users`, `%`…
- `kind`: `one_time`, `monthly`, `yearly`, `duration`, `count`, `percent`, `price`, `other`
- `category` for costs: `infra`, `tools`, `people`, `marketing`, `legal`, `hardware`, `other`
- `confidence`: `verified`, `estimated` or `assumption` (see below)
- `basis`: how it was worked out. Required for `estimated`
- `source_ref`: URL, document, or a short quote. Required for `verified`

ID prefix `E-`. Re-estimates reuse the ID; the dossier shows how the number moved.

### `question` — something unresolved
Fields: `text`, `status` (`open`, `answered`, `dropped`), `answer` when answered, `blocks` (list of decision IDs waiting on it), `owner` if someone took it. ID prefix `Q-`.

### `risk`
Fields: `text`, `likelihood` (1 low – 3 high), `impact` (1–3), `mitigation`, `status` (`open`, `mitigated`, `accepted`, `closed`). ID prefix `R-`.

### `evidence` — validation for or against the idea
Fields: `claim`, `supports` (`for` or `against`), `strength` (`strong`, `moderate`, `weak`), `source_ref`. ID prefix `V-`. Interviews, surveys, competitor facts, market data, prototype results.

### `milestone` — a phase of the plan
Fields: `name`, `goal`, `start_week` (weeks from plan start, 0-based), `duration_weeks`, `deliverables` (list), `confidence`, `basis`, `depends_on` (milestone IDs). ID prefix `M-`.

### `skill` — capability the build needs
Fields: `name`, `level` (1 basic – 5 expert), `needed_for`, `have` (`yes`, `partial`, `no`: does the person or team already have it). ID prefix `K-`.

### `guideline` — a do or a don't
Fields: `polarity` (`do` or `dont`), `text`, `why`. ID prefix `G-`. Lessons that came out of the discussion: "Don't build your own auth", "Do launch to one niche first".

### `note`
Free context that doesn't fit elsewhere. Fields: `text`, `tags`. ID prefix `N-`. Use sparingly.

## Decision state machine

```
            ┌──────────► accepted ───────► superseded (terminal; needs superseded_by)
            │              │  ▲
 proposed ──┼──► parked ◄──┘  │
            │      │  ▲       │
            └──────┼──┼───► rejected
                   │  │       │
                   ▼  │       ▼
                (any of)   proposed  (revived; reason required)
```

Allowed transitions:

| From | To |
|---|---|
| (new) | `proposed`, `accepted`, `rejected`, `parked` |
| `proposed` | `accepted`, `rejected`, `parked` |
| `accepted` | `superseded`, `rejected`, `parked`, `accepted` (a refinement; say what changed in `reason`) |
| `parked` | `accepted`, `rejected`, `proposed` |
| `rejected` | `proposed`, `accepted` (a revival; the reason must say what changed) |
| `superseded` | nothing. To bring part of it back, create a new decision with `revives` |

Meanings:
- `proposed`: on the table, not decided
- `accepted`: part of the plan now
- `rejected`: decided against, with a reason
- `parked`: good idea, deliberately deferred to later without commitment
- `superseded`: was accepted, then replaced by a different decision (for example "Firebase" superseded by "Supabase")

The difference between `rejected` and `superseded` matters in the dossier: rejected means "we chose not to", superseded means "we chose this, then found something better". Both stay visible with their reasons.

**Partial revival.** When something dropped earlier comes back in a reduced form ("offline sync was rejected, but read-only offline cache is in"), create a new decision for the reduced form with `revives` pointing to the old one. Don't reopen the old one: its rejection reason is still true for the full version.

## Confidence tags

Every `estimate` and every `milestone` carries one:

| Tag | Means | Requires |
|---|---|---|
| `verified` | Checked against a real source: pricing page, quote, invoice, published data | `source_ref` |
| `estimated` | Worked out with reasoning from something concrete | `basis` |
| `assumption` | A guess, gut feel, or placeholder to be checked | nothing, but consider an open question |

Be strict. A number the assistant produced from general knowledge is `estimated` at best, and only if the reasoning is stated. A number the person "thinks is about right" is an `assumption`. Only upgrade to `verified` when an actual source is named.

## Example sequence

A feature's life, as the ledger records it:

```
{"type":"iteration","id":"I-001","title":"First concept","summary":"Personal habit tracker for students","ts":"2026-09-02","source":"S1#m1"}
{"type":"decision","id":"D-004","state":"proposed","title":"Offline sync","area":"feature","ts":"2026-09-02","source":"S1#m9"}
{"type":"decision","id":"D-004","state":"accepted","title":"Offline sync","area":"feature","phase":"mvp","reason":"Students on patchy campus wifi","ts":"2026-09-03","source":"S1#m22"}
{"type":"estimate","id":"E-002","metric":"MVP build time","value":10,"low":8,"high":14,"unit":"weeks","kind":"duration","confidence":"estimated","basis":"Solo dev, 3 screens + sync layer","ts":"2026-09-03","source":"S1#m25"}
{"type":"iteration","id":"I-002","title":"Scope cut","summary":"Trim MVP to ship before semester starts","ts":"2026-09-10","source":"S2#m1"}
{"type":"decision","id":"D-004","state":"rejected","title":"Offline sync","area":"feature","reason":"Doubles build time; only 2 of 12 interviewees asked for it","ts":"2026-09-10","source":"S2#m6"}
{"type":"estimate","id":"E-002","metric":"MVP build time","value":6,"low":5,"high":8,"unit":"weeks","kind":"duration","confidence":"estimated","basis":"Same scope minus sync layer","ts":"2026-09-10","source":"S2#m7"}
{"type":"decision","id":"D-011","state":"accepted","title":"Read-only offline cache","area":"feature","phase":"mvp","revives":"D-004","reason":"Covers the wifi problem for viewing at ~1 week of effort","ts":"2026-09-18","source":"live"}
```
