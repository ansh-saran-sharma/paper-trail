# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x (latest) | Yes |
| Older | No; please upgrade |

## Reporting a vulnerability

**Please don't open a public issue for security problems.**

- Preferred: use GitHub's private reporting. Go to the repository's **Security** tab and choose **Report a vulnerability**.
- Or email **ansh.sharma@live.com** with "paper-trail security" in the subject.

Include what's affected (script, template, or instructions), steps to reproduce, and the impact you expect. A minimal input file helps; please strip personal data from it.

What to expect:

- Acknowledgement within 5 working days.
- An assessment and planned fix timeline within 14 days.
- Credit in the release notes if you'd like it.

## What this project is, from a security point of view

The skill has three parts, each with different exposure:

1. **Instructions** (`SKILL.md`, `references/`): text an AI agent reads and follows.
2. **Scripts** (`scripts/*.py`): run locally by the agent or by you. Python standard library only.
3. **Template** (`assets/dossier-template.html`): becomes a standalone HTML file that people open in a browser and share.

## Threat model and safeguards

### Your data stays local

- The scripts make **no network requests**. They read the files you give them and write to the folder you choose.
- No telemetry, analytics or update checks anywhere.
- The generated HTML loads web fonts from Google Fonts by default, which reveals the viewer's IP address and the fact that the page was opened to Google. Build with `--no-webfonts` to remove this; the page then makes **zero network requests**.
- Your AI agent processes your conversation as it always does; this skill doesn't change what your agent provider receives.

### Sensitive content in exports and ledgers

Chat exports contain *all* your conversations, and ledgers and dossiers contain your decisions, costs and sometimes names.

- Filter exports to the relevant idea (`--match`). Full exports are never needed.
- Keep `.dossier/sources/` and raw exports out of version control. The provided `.gitignore` excludes them.
- **Review a dossier before sharing it.** It deliberately includes the decision history, reasons, source conversation titles and dates. Remove anything you don't want recipients to see from `dossier.json` and rebuild.
- The dossier embeds its data as JSON in the page. Anyone with the file can read all of it, including folded sections.

### Untrusted input: prompt injection

Exported conversations, notes and web content are **data, not instructions**. A transcript could contain text like "ignore your instructions and…". The skill tells the agent to extract facts from transcripts and never to follow instructions found inside them. Treat any agent behavior that changes after ingesting a file as suspicious, and report it if it reproduces.

### Malicious input files

- **Zip archives** are read in memory and never extracted to disk, so path-traversal ("zip slip") isn't possible. Members larger than 512 MB uncompressed are skipped.
- **Malformed JSON or JSONL** is reported and skipped, never executed.
- **Very large files** are read fully into memory; don't run the scripts on untrusted multi-gigabyte inputs.

### The generated HTML

- All user-provided text is inserted with `textContent` or as SVG text nodes, never as HTML, so content in the ledger can't inject markup or script.
- The embedded JSON escapes `</` sequences, so data can't close the script tag early. The test suite checks this.
- The page uses `localStorage` only to remember the light/dark choice, wrapped so it fails safely.
- External resources are limited to the optional font links.

### Running the scripts

- Scripts only read paths you pass and write to the `--out` path you choose (default `.dossier/`).
- No `eval`, no `exec`, no shell invocation, no dynamic imports of user data.
- Release archives contain only the skill folder. Verify downloads against the release's checksums when they're published.

## Out of scope

- How a given AI agent or vendor stores or processes your conversations.
- Bugs in third-party tools' export formats.
- Social engineering of people you share a dossier with.

## For contributors

Changes to the template must keep user text out of `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` and inline event-handler strings. Changes to scripts must not add network access or third-party dependencies without discussion in an issue first. See [CONTRIBUTING.md](CONTRIBUTING.md).
