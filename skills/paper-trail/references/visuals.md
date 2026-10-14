# Visuals in the dossier

`assets/dossier-template.html` draws everything with inline SVG and plain JavaScript. It has no external dependencies apart from optional web fonts, so it works offline, attached to an email, or hosted. You never edit it per dossier; the JSON drives it.

## Visual grammar (consistent everywhere)

**Confidence is shown by fill, not only by colour or a label**, so it survives printing in greyscale:

| Fill | Meaning |
|---|---|
| Solid | Verified against a source |
| Hatched | Estimated, with reasoning |
| Hollow, dashed outline | Assumption |

Every confidence badge is clickable and shows the `source_ref` or `basis` behind the number.

**Decision states have fixed colours and line styles:** accepted (green, solid), proposed (grey, dotted), parked (amber, dashed), rejected (red, ends in a cross), superseded (violet, curve to its replacement).

## What each section draws

| Section | Visual | Interaction | Data it reads |
|---|---|---|---|
| `summary` | Large name and one-liner, a five-step stage track, highlight cards with ranges, a stacked bar of decision outcomes | Confidence popovers | `summary.*`, counts from `decisions` |
| `journey` | Numbered chapter timeline; each change is a state pill | Pill opens the decision drawer | `journey[].changes` |
| `decisions` | **Decision river**: one lane per decision across time, chapter bands behind, curves linking superseded → replacement and rejected → revival | Area filter chips, "hide rejected" toggle, click or Enter on a lane opens the drawer | `decisions[].history`, `superseded_by`, `revives`, `journey[].date` |
| `features` | Board: MVP / Later / Undecided / Cut, each card with its latest reason and a strip of its past states | Card opens the drawer | Decisions with area `feature` or `scope` |
| `validation` | Weighted for/against balance bar, then a diverging bar per piece of evidence | — | `validation.evidence` |
| `pros_cons` | Two weighted columns | — | `pros_cons` |
| `dos_donts` | Two columns with the reason under each | — | `dos_donts` |
| `plan` | Gantt with dependency connectors and an "MVP ready" line; bars use the confidence fill | Hover titles | `plan.milestones`, `plan.start_date` |
| `costs` | Range bars per item, tabbed by monthly / one-time / yearly; a cumulative cost curve with a low–high band | Tabs; a 1–36 month slider updates the total, range and category split | `costs.items` |
| `tech` | Layered stack; chosen tech as chips, dropped alternatives struck through beside them | Chip opens the drawer | Decisions with area `tech` |
| `skills` | Level meter (1–5) per skill with have / partly / gap tags | — | `skills.items` |
| `team` | Person figures per role, split by MVP and later; hollow figures are optional roles | — | `team.roles` |
| `risks` | 3×3 likelihood × impact matrix with numbered markers; open risks filled, mitigated hollow | Hover or focus highlights the matching row | `risks.items` |
| `open_questions` | List with "waiting on this" links to blocked decisions | Links open the drawer | `open_questions` |
| `sources` | Timeline strip of when each conversation happened, plus a table | — | `sources` |

**The decision drawer** is shared by the river, journey, board, tech and questions: the full state history with dates, chapter, source anchor and reason, plus links to whatever replaced or revived it.

## Behaviour you can rely on

- Missing section keys are simply not drawn; the nav only lists sections that exist.
- `meta.collapsed` sections render folded and open on click.
- Light and dark themes follow the viewer's system setting; the "Switch theme" button overrides it and redraws the charts.
- Layout adapts down to phone width; wide charts scroll inside their own panel.
- Printing expands folded sections and hides the controls.

## Getting the most out of the visuals

The visuals are only as good as the data. Things that noticeably improve them:

- Dates on every decision event, so the river spreads out over time instead of stacking.
- An `iteration` event at every real change in direction, so the river and journey have chapters.
- `low` and `high` on uncertain numbers, so ranges and the cost band appear.
- `superseded_by` and `revives` filled in, so the river's connecting curves tell the story.
- `depends_on` on milestones, so the Gantt shows sequencing.
