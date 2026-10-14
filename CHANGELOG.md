# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-14

### Added
- Named **Paper Trail** (`paper-trail`).
- **Capture mode:** append-only decision ledger (`.dossier/ledger.jsonl`, or ```` ```ledger ```` checkpoint blocks in chat-only apps) with decision states (proposed, accepted, rejected, parked, superseded), partial revivals, confidence tags on every number, chapters, risks, evidence, skills, guidelines and questions.
- **Ingest mode:** `normalize_exports.py` reads ChatGPT (zip or JSON, active branch only), Claude.ai, Claude Code, Codex and Gemini CLI logs, and markdown or text transcripts, producing anchored transcripts (`[S2#m14]`) and a manifest.
- **Compile mode:** `scaffold_dossier.py` copies facts from the ledger into a draft `dossier.json`; `build_dossier.py` validates honesty rules and renders a single-file interactive HTML dossier.
- `ledger.py` with `check`, `replay`, `merge` and `next-id`.
- Dossier visuals: decision river, journey, feature board, plan timeline, cost ranges with a cumulative projection, tech stack, skills, team, risk matrix, evidence balance, open questions, sources. Light and dark themes, mobile layout, print styles, keyboard access.
- Audience profiles: investor, team, engineer, personal.
- `--no-webfonts` build option for fully offline output.
- When the build refuses, it says what's missing and from whom: questions for the person (with honest options such as giving a source, explaining an estimate, or marking a guess), fixes the agent makes itself, and optional improvements. `--report FILE` writes them as JSON. The ledger checker and scaffold use the same person-facing questions.
- Test suite, fixtures from five tools, examples, CI on Python 3.9 to 3.12, packaging and rename tools.
