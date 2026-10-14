# Usage guide

Step-by-step walkthroughs for every way of using Paper Trail. For installation see the [README](README.md#installation); for the internals see [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md).

- [Scenario 1: Capture a new idea in a coding agent](#scenario-1-capture-a-new-idea-in-a-coding-agent)
- [Scenario 2: Capture in a chat app (no filesystem)](#scenario-2-capture-in-a-chat-app-no-filesystem)
- [Scenario 3: Import research from other tools](#scenario-3-import-research-from-other-tools)
- [Scenario 4: Rescue an existing long conversation](#scenario-4-rescue-an-existing-long-conversation)
- [Scenario 5: Compile for different audiences](#scenario-5-compile-for-different-audiences)
- [Scenario 6: Keep going after the first dossier](#scenario-6-keep-going-after-the-first-dossier)
- [Scenario 7: A team sharing one ledger](#scenario-7-a-team-sharing-one-ledger)
- [Scenario 8: Use the scripts without any agent](#scenario-8-use-the-scripts-without-any-agent)
- [Phrase cheat sheet](#phrase-cheat-sheet)
- [Script reference](#script-reference)
- [Writing good ledger entries](#writing-good-ledger-entries)

---

## Scenario 1: Capture a new idea in a coding agent

Applies to Claude Code, Codex, Gemini CLI, Cursor, Copilot agent mode: anything with a working folder.

1. Open your agent in a folder for the idea (a new empty folder is fine).
2. Start explicitly so nothing is missed:
   ```text
   /paper-trail start. I'm exploring a marketplace for renting camera gear between photographers.
   ```
   (Codex: `$paper-trail start ...`; elsewhere: "Use paper-trail to start tracking this idea: ...")
3. The agent creates `.dossier/ledger.jsonl` and tells you once. From then on, talk normally. Each reply that recorded something ends with one line like:
   ```text
   Logged: D-003 accepted (insurance included in every rental), E-001 estimated.
   ```
4. Give reasons when you decide things; they're the most valuable part. Compare:
   - "Drop insurance." → logged, but the reason is thin.
   - "Drop built-in insurance, the quotes were 18% of rental value and three renters said they have their own." → this is what the dossier will explain six weeks later.
5. Say numbers with their basis when you can: "Hosting will be about $40 a month, that's Render's starter plan plus a small Postgres". A number with a stated source or calculation gets a better confidence tag than a gut feel.
6. Ask for status any time: "What have we decided so far?" or "What's still open?"
7. When ready: "Compile it". See [Scenario 5](#scenario-5-compile-for-different-audiences).

The ledger stays in the folder. Next session, invoke the skill again and it continues the same file.

## Scenario 2: Capture in a chat app (no filesystem)

Applies to chat apps without file access, or with code execution off.

1. Start explicitly: "Use paper-trail to start a ledger for this idea: ...".
2. The agent keeps the ledger as checkpoint blocks in its replies. You'll see something like:
   ````text
   ```ledger
   {"type":"decision","id":"D-004","state":"rejected","title":"Built-in insurance","area":"feature","reason":"Quotes were 18% of rental value; renters have their own","ts":"2026-10-03","source":"live"}
   ```
   ````
   It posts one when you say "checkpoint", about every five new events, after a big change of direction, or when the conversation gets long.
3. **Save each block.** Copy them into one text file (e.g. `checkpoints.md`, in order), or into your project's notes. In chat-only mode, these blocks *are* your ledger.
4. In claude.ai with code execution on, the agent can also offer `ledger.jsonl` as a download at each checkpoint. Keep the latest one.
5. Next session: upload `checkpoints.md` (or `ledger.jsonl`) and say "continue the dossier from this ledger".
6. To compile: upload your saved checkpoints and say "compile". With code execution, the agent runs `ledger.py merge` to combine the blocks; without it, it replays them by hand.

## Scenario 3: Import research from other tools

1. Export your chats (see the [README table](README.md#exporting-your-chats-from-other-tools)). You don't need to unzip a ChatGPT export.
2. Upload or point the agent at them, and say which idea:
   ```text
   Here are my ChatGPT and Claude exports and a Gemini chat I copied into a file.
   Add everything about the camera rental idea.
   ```
3. With a big account export, the agent first lists what matched (`--list`) and may ask you to confirm which conversations to include.
4. It then normalizes them into `.dossier/sources/S1.md …` and extracts events from each, oldest first. Each event cites its message, e.g. `S2#m14`.
5. Expect a report like:
   ```text
   Ingested 3 sources (ChatGPT Sept 2–4, Claude Sept 10–12, Gemini undated):
   S1: 9 decisions, 2 estimates · S2: 7 decisions, 1 estimate, 3 evidence · S3: 1 decision, 1 question
   Needs your call: the Gemini chat has no dates. Roughly when was it?
   Conflict resolved: S1 accepted native apps; S2 (later) rejected them, so current state is rejected.
   ```
6. Answer its questions. Things it flags:
   - **Undated sources.** It needs a rough date to place them in the timeline.
   - **Conflicts with unknown order.** It won't guess which is current.
   - **Options discussed at length that never reappear.** These are logged as parked with "no decision recorded" rather than with an invented reason. Tell it what actually happened if you remember.

You can ingest more later; new sources get the next free IDs, so earlier citations stay valid.

## Scenario 4: Rescue an existing long conversation

You've been brainstorming for an hour without the skill:

```text
Use paper-trail on this conversation so far, then keep tracking.
```

The agent backfills events from the visible conversation (marked `backfilled`) and tells you if early parts were already compacted away. If they were, export the conversation from the app and give it the export, which is usually complete.

## Scenario 5: Compile for different audiences

```text
Compile it for investors.
```

What happens, in order:

1. The ledger is checked; real errors are fixed or raised with you.
2. If you didn't name an audience, the agent asks once (investor, team, engineer, personal). Default: team.
3. A draft is scaffolded with every fact copied from the ledger. The agent writes the prose (chapter summaries, intros, the evidence verdict), picks up to four headline numbers, and trims to what the audience needs.
4. The build validates and renders `dossier.html`. If something required is missing, it stops, and you get one message listing only what the agent couldn't resolve itself, for example:
   ```text
   The dossier is ready except for two things I can't fill in without you, because otherwise
   it would present guesses as facts:

   1. Where does the $25/month hosting cost come from? A link or pricing page is enough.
      Or tell me how you worked it out, or that it's a guess.
   2. How was the 6-week MVP estimate worked out? One sentence is enough, or tell me it's a guess.

   If you don't have some of these, say so and I'll mark them as guesses rather than leave them out.
   ```
   Answer what you can. Answers go into the ledger, so you won't be asked again. Anything you can't answer is downgraded or becomes an open question, never invented. If the agent has a browser, it then checks the result visually.
5. You get the file plus a two-to-three sentence summary.

The same facts, reorganized:

| Audience | Leads with | Folded | Left out |
|---|---|---|---|
| `investor` | Overview, evidence, plan, costs, risks, team | Decisions, tech | Skills |
| `team` (default) | Overview, journey, decisions, features | — | — |
| `engineer` | Features, tech, decisions, plan, skills | Evidence, pros and cons | — |
| `personal` | Journey, decisions, open questions | — | — |

Useful variations:

- "Make it with no web fonts" makes the file fully offline.
- "Put validation first" overrides the order.
- "Leave out costs, they're confidential" removes a section for this audience.
- "Use EUR" changes the currency (amounts aren't converted; the ledger's numbers must already be in that currency).

When an investor dossier lacks something investors expect (costs, plan, evidence, risks), the dossier shows an open question saying so rather than a made-up section.

## Scenario 6: Keep going after the first dossier

The ledger doesn't end at compile. Keep discussing; later say "update the dossier". It re-scaffolds from the full ledger and rebuilds, so the new version shows the new chapters, and numbers that moved show their history.

Tip: keep each compiled version (`dossier-2026-10-12.html`) if you want to compare how the idea evolved.

## Scenario 7: A team sharing one ledger

1. Install the skill at project level (`.agents/skills/paper-trail/`, `.claude/skills/…`, etc.) and commit it.
2. Commit `.dossier/ledger.jsonl`. It's append-only JSON Lines, so merges are usually trivial (both sides appended lines).
3. Don't commit raw exports or `.dossier/sources/` if they contain private chats. The repo's `.gitignore` shows how.
4. After a merge, run `python skills/paper-trail/scripts/ledger.py check .dossier/ledger.jsonl`. Two people may have assigned the same new ID; renumber one of them before continuing. If two people changed the same decision on the same day, check that the order of their lines is the order things actually happened.

## Scenario 8: Use the scripts without any agent

```bash
S=skills/paper-trail/scripts

# 1. See what's in your exports, then normalize the relevant ones
python $S/normalize_exports.py ~/Downloads/chatgpt-export.zip ~/Downloads/claude/conversations.json --match "camera" --list
python $S/normalize_exports.py ~/Downloads/chatgpt-export.zip ~/Downloads/claude/conversations.json --match "camera" --out .dossier/sources

# 2. Write ledger events by hand (format: skills/paper-trail/references/ledger-format.md)
python $S/ledger.py next-id .dossier/ledger.jsonl D          # → D-001
echo '{"type":"decision","id":"D-001","state":"accepted","title":"Peer-to-peer rentals only","area":"scope","phase":"mvp","reason":"No inventory costs","ts":"2026-10-14","source":"S1#m12"}' >> .dossier/ledger.jsonl
python $S/ledger.py check .dossier/ledger.jsonl

# 3. Draft, edit, build
python $S/scaffold_dossier.py .dossier/ledger.jsonl --audience team --sources .dossier/sources/sources.json --out dossier.json
$EDITOR dossier.json                                         # replace every "TODO:" string
python $S/build_dossier.py dossier.json --out dossier.html   # if it stops, answer the NEEDED FROM THE PERSON questions
```

## Phrase cheat sheet

| Goal | Say |
|---|---|
| Start tracking | `/paper-trail start` · `$paper-trail start` · "Start a dossier for this idea" · "Track this" |
| Start late | "Use paper-trail on this conversation so far" |
| Save progress | "Checkpoint" · "Save the ledger" |
| Status | "What have we decided?" · "What's still open?" · "Summarize the ledger" |
| Explain a decision | "Why did we drop X?" · "When did we switch to Y and why?" |
| Correct the record | "That's wrong: we rejected X because of cost, not time" (appends a correction) |
| Import | "Here are my exports" · "Add only the chats about X" · "Only from September" |
| Compile | "Compile" · "Make the doc" · "Make it shareable" |
| Audience | "…for investors" · "…for my cofounder" · "…for the engineers" · "…just for me" |
| Variants | "…with no web fonts" · "…leave out costs" · "…put evidence first" |
| Refresh | "Update the dossier" |
| Answer build questions | "It's from their pricing page: <link>" · "That's a guess" · "I don't know, leave it as an open question" |
| Pause | "Don't log this part" · "Stop tracking" |

## Script reference

All scripts: Python 3.9+, standard library only, `--help` for details.

### `normalize_exports.py`

| Flag | Meaning |
|---|---|
| `inputs…` | Files or folders (zip, json, jsonl, md, txt) |
| `--out DIR` | Output folder (default `.dossier/sources`) |
| `--match TEXT` | Keep conversations whose title or text contains TEXT; repeatable, case-insensitive |
| `--since / --until YYYY-MM-DD` | Date filter |
| `--min-messages N` | Drop tiny conversations |
| `--start-id N` | First source number, to append to an existing set |
| `--list` | Preview only; writes nothing |

### `ledger.py`

| Command | Meaning |
|---|---|
| `check LEDGER…` | Validate JSON, IDs, transitions, references, confidence rules. Exit code 1 on errors |
| `replay LEDGER… [--json]` | Current state of everything with full history |
| `merge LEDGER… --out FILE` | Combine `.jsonl` files and markdown with ` ```ledger ` blocks; sorted by time, de-duplicated |
| `next-id LEDGER PREFIX` | Next free ID, e.g. `D` → `D-014` |

### `scaffold_dossier.py`

| Flag | Meaning |
|---|---|
| `LEDGER…` | One or more ledgers |
| `--audience` | `investor`, `team`, `engineer`, `personal` |
| `--sources FILE` | `sources.json` from normalization |
| `--live-tool / --live-title` | How the current conversation is labelled in Sources |
| `--out FILE` | Default `dossier.json` |

### `build_dossier.py`

| Flag | Meaning |
|---|---|
| `DOSSIER` | `dossier.json` |
| `--out FILE` | Default `dossier.html` |
| `--strict` | Treat optional findings as required |
| `--report FILE` | Write findings as JSON: `needed_from_person`, `agent_can_fix`, `optional_ask_person`, `optional_agent`, each with the question and options |
| `--no-webfonts` | Remove Google Fonts links (no network requests) |
| `--template FILE` | Use a custom template |

## Writing good ledger entries

- **Reasons are the point.** A state change without a reason is a fact; with a reason it's knowledge.
- **One idea per decision.** "Supabase + Expo + Stripe" is three decisions.
- **Use the right ending.** `rejected` = we chose not to. `superseded` = we chose it, then replaced it (needs `superseded_by`). `parked` = good, but later.
- **Don't reopen superseded decisions.** Create a new one with `revives`.
- **Be strict with confidence.** Assistant-generated numbers are `estimated` at best, and only with the reasoning stated. Gut feel is `assumption`. Only a named source makes something `verified`.
- **Mark chapters.** An `iteration` event at each real change of direction makes the journey and decision river readable.
