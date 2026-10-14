# Dossier sections and audiences

Every section has an inclusion rule. If the ledger doesn't meet it, leave the section's key out of `dossier.json` entirely; the template doesn't render missing sections and the build script warns about empty ones.

The rule behind all of these: an absent section is honest, a section padded with plausible filler is not. When an audience would normally expect a section that the ledger can't support, add an open question for it instead ("No cost discussion yet: hosting and tooling costs need estimating before this goes to investors").

## Section catalog

| Key | Shows | Include when | Built from |
|---|---|---|---|
| `summary` | Name, one-liner, status, problem, solution, audience, why now | Always | `frame` events |
| `journey` | Chapters of how the idea evolved, with what changed in each | 2+ iterations, or 5+ decisions with state changes | `iteration` events and the decisions that changed inside each |
| `decisions` | Every decision with its full state history, as the decision river | 3+ decisions | `decision` events |
| `features` | Board of MVP / Later / Cut, each card explaining why | 1+ `feature` or `scope` decision | Replayed feature decisions |
| `validation` | Evidence for and against, weighted by strength | 1+ `evidence` | `evidence` events |
| `pros_cons` | Explicit trade-off summary | Pros/cons were actually discussed, or 3+ evidence items to summarize | Discussion + evidence |
| `dos_donts` | Guidelines with the reason for each | 1+ `guideline` | `guideline` events |
| `plan` | Milestones on a timeline, MVP to finished product | 1+ `milestone` | `milestone` events |
| `costs` | Cost items with ranges and confidence, monthly run-rate projection | 1+ cost-type `estimate` (`one_time`, `monthly`, `yearly`) | `estimate` events |
| `tech` | Stack by layer, each choice linked to its decision | 1+ accepted `tech` decision | Replayed tech decisions |
| `skills` | Skills needed, level, and whether the person/team has them | 1+ `skill` | `skill` events |
| `team` | Roles, headcount, which phase each is needed in | 1+ `team` decision, or team size was discussed | Team decisions |
| `risks` | Likelihood × impact matrix with mitigations | 1+ `risk` | `risk` events |
| `open_questions` | What's unresolved and what it blocks | Any open question, unverified critical number, or missing expected section | `question` events + compile-time gaps |
| `sources` | Where everything came from | Always | Ingestion manifest + "this conversation" |

"Team required or not" is itself an answer worth showing. If the discussion concluded a solo build is fine, include `team` with a single role and a note saying so.

## Audience profiles

Set `meta.audience`. The build script fills in a default `meta.section_order` for it if you don't provide one. Override the order when the content calls for it, for example moving `validation` up when evidence is the strongest part of the case.

**`investor`** (or funder, accelerator, manager approving budget)
- Order: summary, validation, pros_cons, plan, costs, risks, team, features, journey, open_questions, sources
- Leave out `skills`. Put `decisions` and `tech` in `meta.collapsed` (rendered folded, available on click).
- Tone: lead with the problem and evidence. Name risks plainly; investors distrust documents without them.
- Costs and timelines get extra scrutiny: if a headline number is an `assumption`, say so in the summary text, not only in the badge.

**`team`** (cofounder, collaborators; also the default)
- Order: summary, journey, decisions, features, plan, costs, tech, skills, team, dos_donts, risks, validation, pros_cons, open_questions, sources
- Everything included that the ledger supports. The journey and decisions matter most: the point is that someone joining can see why things are the way they are.

**`engineer`** (people who will build it)
- Order: summary, features, tech, decisions, plan, skills, dos_donts, risks, open_questions, costs, journey, sources
- `validation` and `pros_cons` go in `meta.collapsed`.
- Be specific in feature cards about scope boundaries: what's in MVP and, just as important, what's explicitly cut.

**`personal`** (a record for the person themselves)
- Order: summary, journey, decisions, features, open_questions, plan, costs, tech, skills, team, dos_donts, risks, validation, pros_cons, sources
- Keep more of the reasoning texture: why options lost, what almost happened.

## Writing the prose fields

- Write for the audience, in plain sentences. A non-technical investor shouldn't meet "RLS policies"; an engineer shouldn't get "a robust, scalable backend".
- Summaries state what is true now. History belongs in the journey.
- Keep the one-liner under 20 words.
- Each journey chapter: 2–3 sentences on what changed and why, not a list of everything discussed.
- Feature card reasons: one sentence, the actual reason from the ledger.
