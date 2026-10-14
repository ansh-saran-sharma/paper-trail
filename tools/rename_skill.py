#!/usr/bin/env python3
"""Rename the skill and fill in the repository placeholders, in one go.

Usage:
    python tools/rename_skill.py --name paper-trail --repo yourname/paper-trail \
        --author "Your Name" --security-email you@example.com [--dry-run]

What it changes:
    - folder skills/idea-dossier/  ->  skills/<name>/
    - every occurrence of "idea-dossier" -> <name>, and "Idea Dossier" -> title-cased <name>
    - OWNER/REPO -> <repo>, [AUTHOR] -> <author>, [SECURITY_EMAIL] -> <email>
in all text files of the repository (binary files and .git are left alone).

Every option is optional, so you can run it again later just to fill in, say, the email.
Run with --dry-run first to see what would change. Standard library only.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {".md", ".py", ".json", ".jsonl", ".html", ".yml", ".yaml", ".txt", ".toml", ""}
SKIP_DIRS = {".git", "dist", "__pycache__", "node_modules"}


def current_name():
    found = list((ROOT / "skills").glob("*/SKILL.md"))
    if len(found) != 1:
        sys.exit("Expected exactly one skills/<name>/SKILL.md")
    return found[0].parent.name


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", help="new skill name: lowercase, digits, hyphens")
    ap.add_argument("--repo", help="GitHub owner/repo")
    ap.add_argument("--author", help="copyright holder for LICENSE")
    ap.add_argument("--security-email", help="where vulnerability reports go")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    old = current_name()
    subs = []
    if a.name:
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", a.name) or len(a.name) > 64:
            sys.exit("--name must be lowercase letters, digits and single hyphens, max 64 characters")
        subs += [(old, a.name), (old.replace("-", " ").title(), a.name.replace("-", " ").title())]
    if a.repo:
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", a.repo):
            sys.exit("--repo must look like owner/repo")
        subs.append(("OWNER/REPO", a.repo))
    if a.author:
        subs.append(("[AUTHOR]", a.author))
    if a.security_email:
        subs.append(("[SECURITY_EMAIL]", a.security_email))
    if not subs:
        sys.exit("Nothing to do. Pass at least one of --name, --repo, --author, --security-email.")

    changed = 0
    for p in sorted(ROOT.rglob("*")):
        if p.is_dir() or any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        if p.suffix not in TEXT_SUFFIXES or p.resolve() == Path(__file__).resolve():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new = text
        for s_old, s_new in subs:
            new = new.replace(s_old, s_new)
        if new != text:
            changed += 1
            print(("would update " if a.dry_run else "updated ") + str(p.relative_to(ROOT)))
            if not a.dry_run:
                p.write_text(new, encoding="utf-8")

    if a.name and a.name != old:
        src, dst = ROOT / "skills" / old, ROOT / "skills" / a.name
        print(f"{'would rename' if a.dry_run else 'renamed'} skills/{old} -> skills/{a.name}")
        if not a.dry_run:
            src.rename(dst)
    print(f"{'Would change' if a.dry_run else 'Changed'} {changed} file(s).")
    if not a.dry_run:
        print("Next: python -m unittest discover -s tests  &&  python tools/package_skill.py")


if __name__ == "__main__":
    main()
