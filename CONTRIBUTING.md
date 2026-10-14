# Contributing

Thanks for helping. Bug reports, new export formats, visuals, translations and documentation are all welcome.

- [Ground rules](#ground-rules)
- [Development setup](#development-setup)
- [Project layout](#project-layout)
- [Running the tests](#running-the-tests)
- [Common contributions](#common-contributions)
- [Changing the skill's instructions](#changing-the-skills-instructions)
- [Style](#style)
- [Pull requests](#pull-requests)
- [Releasing](#releasing)

## Ground rules

These keep the skill portable and trustworthy. PRs that break them will be asked to change:

1. **No third-party dependencies** in `skills/`. Scripts use the Python standard library (3.9+); the template uses plain JavaScript and inline SVG with no libraries. The skill must run in any agent's sandbox, offline.
2. **No network access** from scripts, and none from the template beyond the optional font links.
3. **Honesty rules are features, not friction.** Don't loosen validation that stops unsupported "verified" numbers, invented sections, or contradictory decision states. Discuss in an issue first if you think a rule is wrong.
4. **Every step needs a no-code fallback** described in `SKILL.md`, for agents that can't run scripts.
5. **User text never goes into `innerHTML`** (or `outerHTML`, `insertAdjacentHTML`, `document.write`) in the template. See [SECURITY.md](SECURITY.md).
6. Be kind. See the [Code of Conduct](CODE_OF_CONDUCT.md).

## Development setup

```bash
git clone https://github.com/ansh-saran-sharma/paper-trail.git
cd paper-trail
python -m unittest discover -s tests -v
```

That's all you need. Optional extras:

```bash
pip install playwright && playwright install chromium   # browser test + screenshots
```

To try your working copy in an agent, link the skill folder instead of copying it, so edits apply immediately:

```bash
ln -s "$PWD/skills/paper-trail" ~/.claude/skills/paper-trail    # Claude Code; adjust the path for other tools
```

## Project layout

| Path | What | Ship in release? |
|---|---|---|
| `skills/paper-trail/` | The skill: `SKILL.md`, `references/`, `scripts/`, `assets/` | Yes, this is the release |
| `tests/` | `unittest` suite and fixture exports from five tools | No |
| `examples/` | Example ledgers, dossier JSON and built HTML | No |
| `evals/evals.json` | Prompts for testing with a real agent | No |
| `tools/` | Packaging, renaming, example builds | No |
| `docs/` | How-it-works guide and screenshots | No |

## Running the tests

```bash
python -m unittest discover -s tests -v       # or: make test
```

The suite covers export detection for every supported format, ledger validation and replay, scaffold fidelity (facts must match the hand-compiled example exactly), build refusals for dishonest or unfinished data, audience ordering, HTML escaping, and, if Playwright is installed, a real browser render with no JavaScript errors. CI runs it on Python 3.9 to 3.12 on Linux, macOS and Windows.

After changing the template or examples, rebuild and eyeball them:

```bash
python tools/build_examples.py                 # or: make examples
python tools/build_examples.py --screenshots   # refresh docs/images (needs Playwright)
```

Check light and dark themes, a phone-width window, and print preview.

## Common contributions

### Supporting a new export format

1. Add a small, **anonymized** sample to `tests/fixtures/`, ideally a few messages including one tool call or system message that should be skipped.
2. In `scripts/normalize_exports.py`, add a reader. Detection goes in `read_json`, `read_jsonl` or `read_any`, based on something distinctive in the format; message text extraction should reuse `text_of()`.
3. Skip non-conversation content (tool calls and results, system prompts, hidden messages, regenerated branches).
4. Add tests in `tests/test_pipeline.py`: it's detected with the right tool name, message count is right, skipped content is absent.
5. Add a row to the export table in `references/ingestion.md` and in the README.

### Adding or changing a dossier section

A section touches several files; keep them in step:

| File | Change |
|---|---|
| `references/dossier-schema.md` | Document the JSON shape |
| `references/dossier-sections.md` | Inclusion rule and position per audience |
| `scripts/scaffold_dossier.py` | Fill it from ledger events, if it can be derived |
| `scripts/build_dossier.py` | Add to `SECTIONS` and `ORDERS`; validate its data |
| `assets/dossier-template.html` | Add a `builders.<key>` function and a title in `TITLES` |
| `references/visuals.md` | Describe the visual and its data |
| `examples/` and `tests/` | Example data and at least one test |

Template conventions: build DOM with the `h()` and `s()` helpers, colors only from CSS variables (`css("--name")` inside SVG), a `_redraw` hook if the section has SVG that must follow theme changes, keyboard access for anything clickable, and no animation unless it answers a user action.

### Adding a validation check

Every check in `build_dossier.py` must say who can resolve it, because a refusal is only useful if it says what to do:

- If only the person can supply the missing fact (a source, a reason, a number, what happened), use `who="person"` with an `ask=` question in plain language. Name the item the way the person would recognize it (use `describe()` for numbers), and give `options=` that are all honest, including the downgrade or remove route.
- If the agent can repair it from the ledger or by writing prose, leave `who="agent"` and give a `fix=` hint.
- Use `r.err` only when building would mislead a reader; everything else is `r.warn` (optional, shown as "would make it stronger").

Add a test asserting the question text, as `test_refusal_tells_the_person_what_is_needed` does.

### Adding a ledger event type or field

Update `references/ledger-format.md`, `PREFIX` and `check()` in `scripts/ledger.py`, `replay()` if it needs grouping, and the scaffold. New fields should be optional so existing ledgers stay valid.

### Translations

The dossier's interface text lives in `TITLES`, `STATE_LABEL`, `CONF_TEXT` and the section ledes in the template. Open an issue before starting, so we agree on how to select a language (likely `meta.lang`).

## Changing the skill's instructions

`SKILL.md` and `references/` are read by AI agents, so changes there affect behavior in ways unit tests can't catch.

- Keep `SKILL.md` under about 500 lines; move detail into `references/` and point to it.
- Explain *why* a rule exists rather than adding capital-letter MUSTs; agents follow reasons better.
- The `description` frontmatter field controls implicit activation. Keep it under 1024 characters (`tools/package_skill.py --check` enforces this) and include phrases real people say.
- Test with a real agent using the prompts in `evals/evals.json` and the fixtures. In your PR, note which agent and model you tested with and what changed in the output.

## Style

- Python: standard library only, 3.9-compatible syntax, functions over classes, clear error messages that say how to fix the problem. Line length about 120.
- Documentation: plain language, sentence case headings, short paragraphs.
- Commit messages: imperative mood ("Add Perplexity export reader"), with a reference to the issue if there is one.

## Pull requests

1. Open an issue first for anything bigger than a small fix, so effort isn't wasted.
2. Branch from `main`; keep PRs focused on one change.
3. Make sure `make test` and `python tools/package_skill.py --check` pass.
4. Update docs and `CHANGELOG.md` (under "Unreleased").
5. Fill in the PR template, including screenshots for visual changes.

By contributing, you agree that your contributions are licensed under the project's [MIT License](LICENSE).

## Releasing

For maintainers:

1. Move "Unreleased" entries in `CHANGELOG.md` under a new version heading.
2. Bump `metadata.version` in `skills/paper-trail/SKILL.md`.
3. Commit, then tag: `git tag v0.2.0 && git push --tags`.
4. The release workflow runs the tests, builds `paper-trail.skill`, `paper-trail-v0.2.0.zip` and `SHA256SUMS.txt`, and attaches them to a GitHub release.

To build locally: `python tools/package_skill.py` (or `make package`); output goes to `dist/`.
