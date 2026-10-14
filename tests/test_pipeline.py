"""End-to-end tests for the skill's scripts. Standard library only.

Run:  python -m unittest discover -s tests -v
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = next((ROOT / "skills").glob("*/SKILL.md")).parent
SCRIPTS = SKILL / "scripts"
FIX = ROOT / "tests" / "fixtures"
HABITAT = ROOT / "examples" / "habitat"
TIDY = ROOT / "examples" / "tidyfiles"


def run(script, *args, ok=True):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    if ok and r.returncode != 0:
        raise AssertionError(f"{script} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
    return r


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestNormalize(Tmp):
    def test_detects_every_format_and_filters(self):
        out = self.tmp / "src"
        r = run("normalize_exports.py", FIX, "--match", "habit", "--out", out)
        self.assertIn("6 conversation(s); 5 kept", r.stdout)  # the pasta chat is filtered out
        manifest = json.loads((out / "sources.json").read_text(encoding="utf-8"))
        tools = [m["tool"] for m in manifest]
        self.assertEqual(tools[:3], ["ChatGPT", "Claude", "Claude Code"])
        self.assertIn("Gemini", tools)
        self.assertIn("Notes", tools)

    def test_chatgpt_follows_active_branch_only(self):
        out = self.tmp / "src"
        run("normalize_exports.py", FIX / "chatgpt-export.zip", "--match", "habit", "--out", out)
        text = (out / "S1.md").read_text(encoding="utf-8")
        self.assertNotIn("regenerated answer", text)
        self.assertIn("[S1#m8]", text)
        self.assertNotIn("[S1#m9]", text)

    def test_claude_code_skips_tool_results(self):
        out = self.tmp / "src"
        run("normalize_exports.py", FIX / "session-7f3a.jsonl", "--out", out)
        text = (out / "S1.md").read_text(encoding="utf-8")
        self.assertNotIn("package.json", text)
        self.assertIn("Messages: 4", text)

    def test_markdown_speakers_and_plain_notes(self):
        out = self.tmp / "src"
        run("normalize_exports.py", FIX / "gemini-pricing.md", FIX / "notes.txt", "--out", out)
        m = json.loads((out / "sources.json").read_text(encoding="utf-8"))
        by_tool = {x["tool"]: x for x in m}
        self.assertEqual(by_tool["Gemini"]["messages"], 5)
        self.assertEqual(by_tool["Notes"]["messages"], 1)

    def test_start_id_appends(self):
        out = self.tmp / "src"
        run("normalize_exports.py", FIX / "claude-conversations.json", "--out", out)
        run("normalize_exports.py", FIX / "gemini-pricing.md", "--out", out, "--start-id", 2)
        ids = [x["id"] for x in json.loads((out / "sources.json").read_text(encoding="utf-8"))]
        self.assertEqual(ids, ["S1", "S2"])

    def test_list_writes_nothing(self):
        out = self.tmp / "src"
        run("normalize_exports.py", FIX, "--list", "--out", out)
        self.assertFalse(out.exists())


class TestLedger(Tmp):
    def test_example_ledgers_are_valid(self):
        for led in (HABITAT / "ledger.jsonl", TIDY / "ledger.jsonl"):
            r = run("ledger.py", "check", led)
            self.assertIn(" 0 error(s)", r.stdout, led)

    def bad(self, *lines):
        p = self.tmp / "bad.jsonl"
        p.write_text((HABITAT / "ledger.jsonl").read_text(encoding="utf-8") + "\n".join(lines) + "\n", encoding="utf-8")
        return run("ledger.py", "check", p, ok=False)

    def test_superseded_is_final(self):
        r = self.bad('{"type":"decision","id":"D-004","state":"accepted","title":"Firebase","reason":"x","ts":"2026-10-06","source":"live"}')
        self.assertEqual(r.returncode, 1)
        self.assertIn("superseded -> accepted", r.stdout)

    def test_confidence_rules(self):
        r = self.bad('{"type":"estimate","id":"E-090","metric":"x","value":1,"kind":"one_time","confidence":"verified","ts":"2026-10-06","source":"live"}',
                     '{"type":"estimate","id":"E-091","metric":"y","value":1,"kind":"one_time","confidence":"estimated","ts":"2026-10-06","source":"live"}')
        self.assertIn("verified without 'source_ref'", r.stdout)
        self.assertIn("estimated without 'basis'", r.stdout)

    def test_dangling_reference_and_bad_json(self):
        r = self.bad('{"type":"decision","id":"D-090","state":"accepted","title":"x","revives":"D-999","ts":"2026-10-06","source":"live"}', "not json")
        self.assertIn("unknown id 'D-999'", r.stdout)
        self.assertIn("not valid JSON", r.stdout)

    def test_next_id(self):
        self.assertEqual(run("ledger.py", "next-id", HABITAT / "ledger.jsonl", "D").stdout.strip(), "D-018")
        self.assertEqual(run("ledger.py", "next-id", self.tmp / "missing.jsonl", "Q").stdout.strip(), "Q-001")

    def test_merge_chat_checkpoints(self):
        md = self.tmp / "checkpoints.md"
        md.write_text("Chat text\n```ledger\n" + "\n".join((TIDY / "ledger.jsonl").read_text(encoding="utf-8").splitlines()[:5])
                      + "\n```\nmore\n```ledger\n" + "\n".join((TIDY / "ledger.jsonl").read_text(encoding="utf-8").splitlines()[3:]) + "\n```\n", encoding="utf-8")
        out = self.tmp / "merged.jsonl"
        run("ledger.py", "merge", md, "--out", out)
        self.assertEqual(len(out.read_text(encoding="utf-8").splitlines()), len((TIDY / "ledger.jsonl").read_text(encoding="utf-8").splitlines()))
        self.assertIn(" 0 error(s)", run("ledger.py", "check", out).stdout)

    def test_replay_current_state_wins(self):
        st = json.loads(run("ledger.py", "replay", HABITAT / "ledger.jsonl", "--json").stdout)
        dec = {d["id"]: d for d in st["decisions"]}
        self.assertEqual([h["state"] for h in dec["D-003"]["history"]], ["proposed", "accepted", "rejected"])
        self.assertEqual(dec["D-004"]["superseded_by"], "D-010")
        self.assertEqual(dec["D-011"]["revives"], "D-003")
        est = {e["id"]: e for e in st["estimates"]}
        self.assertEqual(est["E-001"]["value"], 6)
        self.assertEqual([h["value"] for h in est["E-001"]["history"]], [10, 6])


class TestScaffold(Tmp):
    def test_facts_match_hand_compiled_example(self):
        out = self.tmp / "draft.json"
        run("scaffold_dossier.py", HABITAT / "ledger.jsonl", "--sources", HABITAT / "sources.json", "--out", out)
        draft, ref = json.loads(out.read_text(encoding="utf-8")), json.loads((HABITAT / "dossier.json").read_text(encoding="utf-8"))
        key = lambda ds: {d["id"]: (d["current_state"], [(h["state"], h["date"], h["reason"]) for h in d["history"]]) for d in ds}
        self.assertEqual(key(draft["decisions"]), key(ref["decisions"]))
        self.assertEqual(sorted((i["id"], i["value"], i["confidence"]) for i in draft["costs"]["items"]),
                         sorted((i["id"], i["value"], i["confidence"]) for i in ref["costs"]["items"]))
        self.assertIn("TODO:", out.read_text(encoding="utf-8"))

    def test_omits_sections_without_evidence(self):
        out = self.tmp / "draft.json"
        run("scaffold_dossier.py", TIDY / "ledger.jsonl", "--audience", "personal", "--out", out)
        d = json.loads(out.read_text(encoding="utf-8"))
        for absent in ("costs", "plan", "team", "risks", "validation", "skills"):
            self.assertNotIn(absent, d)
        self.assertEqual([q["blocks"] for q in d["open_questions"]], [["D-005"]])  # undecided -> question

    def test_refuses_broken_ledger(self):
        p = self.tmp / "bad.jsonl"
        p.write_text('{"type":"decision","id":"D-001","state":"superseded","title":"x","ts":"2026-01-01","source":"live"}\n', encoding="utf-8")
        self.assertEqual(run("scaffold_dossier.py", p, "--out", self.tmp / "x.json", ok=False).returncode, 1)


class TestBuild(Tmp):
    def build(self, data, *flags, ok=True):
        js = self.tmp / "d.json"
        js.write_text(json.dumps(data), encoding="utf-8")
        return run("build_dossier.py", js, "--out", self.tmp / "d.html", *flags, ok=ok)

    def test_examples_build_cleanly(self):
        for js in sorted((ROOT / "examples").glob("*/dossier*.json")):
            r = run("build_dossier.py", js, "--out", self.tmp / "x.html")
            self.assertIn("0 warning(s)", r.stdout, js)
        html = (self.tmp / "x.html").read_text(encoding="utf-8")
        self.assertNotIn("const DOSSIER = null;", html)

    def test_refuses_dishonest_or_unfinished_data(self):
        d = json.loads((HABITAT / "dossier.json").read_text(encoding="utf-8"))
        d["costs"]["items"][0].pop("source_ref")                  # verified without a source
        d["plan"]["milestones"][0].pop("basis")                   # estimated without a basis
        d["decisions"][0]["current_state"] = "accepted"           # disagrees with history
        d["validation"]["verdict"] = "TODO: write this"           # unfinished prose
        r = self.build(d, ok=False)
        self.assertEqual(r.returncode, 1)
        for msg in ("no 'source_ref'", "no 'basis'", "disagrees with its own history", "still a placeholder"):
            self.assertIn(msg, r.stdout)

    def test_refusal_tells_the_person_what_is_needed(self):
        d = json.loads((HABITAT / "dossier.json").read_text(encoding="utf-8"))
        d["costs"]["items"][0].pop("source_ref")          # only the person knows the source
        d["summary"]["name"] = "TODO: name"                # only the person knows the name
        d["journey"][0]["summary"] = "TODO: summary"       # the agent can write this
        d["decisions"][2]["history"][1]["reason"] = None   # optional: a missing reason
        report = self.tmp / "findings.json"
        r = self.build(d, "--report", report, ok=False)
        self.assertIn("NEEDED FROM THE PERSON (2)", r.stdout)
        self.assertIn("Where does \u201cSupabase Pro hosting\u201d (25 USD/month) come from?", r.stdout)
        self.assertIn("It's a rough guess: it becomes Assumption", r.stdout)
        self.assertIn("AGENT CAN FIX (1)", r.stdout)
        f = json.loads(report.read_text(encoding="utf-8"))
        self.assertFalse(f["built"])
        self.assertEqual(sorted(i["where"] for i in f["needed_from_person"]), ["costs.items[0]", "dossier.summary.name"])
        self.assertEqual([i["where"] for i in f["agent_can_fix"]], ["dossier.journey[0].summary"])
        self.assertTrue(any("Why was \u201cOffline sync\u201d accepted?" in i["ask"] for i in f["optional_ask_person"]))

    def test_strict_makes_optional_items_required(self):
        d = json.loads((HABITAT / "dossier.json").read_text(encoding="utf-8"))
        d["decisions"][2]["history"][1]["reason"] = None
        self.build(d)                                      # optional: builds
        self.assertEqual(self.build(d, "--strict", ok=False).returncode, 1)

    def test_audience_ordering(self):
        d = json.loads((HABITAT / "dossier-investor.json").read_text(encoding="utf-8"))
        self.build(d)
        html = (self.tmp / "d.html").read_text(encoding="utf-8")
        meta = json.loads(html.split("const DOSSIER = ", 1)[1].split(";\n", 1)[0])["meta"]
        self.assertEqual(meta["section_order"][:2], ["summary", "validation"])
        self.assertNotIn("skills", meta["section_order"])
        self.assertEqual(meta["collapsed"], ["decisions", "tech"])
        self.assertEqual(meta["section_order"][-2:], ["open_questions", "sources"])

    def test_no_webfonts_and_script_escaping(self):
        d = json.loads((TIDY / "dossier.json").read_text(encoding="utf-8"))
        d["summary"]["status"] = "Contains </script><script>alert(1)</script> text"
        self.build(d, "--no-webfonts")
        html = (self.tmp / "d.html").read_text(encoding="utf-8")
        self.assertNotIn("fonts.googleapis.com", html)
        self.assertNotIn("</script><script>alert(1)", html)


class TestTemplate(unittest.TestCase):
    def test_renders_in_browser_if_available(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("playwright not installed")
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "x.html"
            run("build_dossier.py", HABITAT / "dossier.json", "--out", out, "--no-webfonts")
            with sync_playwright() as p:
                try:
                    b = p.chromium.launch()
                except Exception as e:  # browser binaries not installed
                    self.skipTest(f"chromium unavailable: {e}")
                pg = b.new_page()
                errors = []
                pg.on("pageerror", lambda e: errors.append(str(e)))
                pg.goto(out.as_uri())
                pg.wait_for_timeout(500)
                self.assertEqual(errors, [])
                self.assertEqual(pg.locator("section.sec").count(), 14)
                self.assertNotIn("null", pg.locator("main").inner_text().split())
                pg.locator("#s-decisions g.lane").filter(has_text="Offline sync").first.click()
                self.assertTrue(pg.locator("dialog.drawer[open]").is_visible())
                self.assertNotIn("in the MVP", pg.locator("dialog.drawer .meta").inner_text())  # rejected != in MVP
                b.close()


if __name__ == "__main__":
    unittest.main()
