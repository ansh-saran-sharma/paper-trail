#!/usr/bin/env python3
"""Rebuild the example dossiers (and, optionally, the README screenshots).

Usage:
    python tools/build_examples.py                 # examples/*/dossier*.html
    python tools/build_examples.py --screenshots   # also docs/images/*.png (needs: pip install playwright && playwright install chromium)
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def skill_dir():
    found = list((ROOT / "skills").glob("*/SKILL.md"))
    if len(found) != 1:
        sys.exit("Expected exactly one skills/<name>/SKILL.md")
    return found[0].parent


def build():
    builder = skill_dir() / "scripts" / "build_dossier.py"
    built = []
    for js in sorted((ROOT / "examples").glob("*/dossier*.json")):
        out = js.with_suffix(".html")
        r = subprocess.run([sys.executable, str(builder), str(js), "--out", str(out)], capture_output=True, text=True)
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr)
        if r.returncode:
            sys.exit(f"Failed to build {js}")
        built.append(out)
    return built


def screenshots():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Screenshots need Playwright: pip install playwright && playwright install chromium")
    img = ROOT / "docs" / "images"
    img.mkdir(parents=True, exist_ok=True)
    page_url = (ROOT / "examples" / "habitat" / "dossier.html").as_uri()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1360, "height": 860})
        pg.goto(page_url)
        pg.wait_for_timeout(800)
        pg.screenshot(path=str(img / "overview.png"))
        for sec in ("decisions", "features", "plan", "costs", "risks"):
            pg.locator(f"#s-{sec}").screenshot(path=str(img / f"{sec}.png"))
        pg.locator("#s-decisions g.lane").filter(has_text="Offline sync").first.click()
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(img / "drawer.png"))
        pg.keyboard.press("Escape")
        pg.locator("#theme-btn").click()
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(img / "dark.png"))
        m = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        m.goto(page_url)
        m.wait_for_timeout(500)
        m.screenshot(path=str(img / "mobile.png"))
        b.close()
    print(f"Screenshots written to {img.relative_to(ROOT)}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--screenshots", action="store_true")
    a = ap.parse_args()
    build()
    if a.screenshots:
        screenshots()
