#!/usr/bin/env python3
"""Package the skill for distribution.

Usage:
    python tools/package_skill.py            # builds into dist/
    python tools/package_skill.py --check    # validate only, build nothing

Produces:
    dist/<name>.skill              upload-ready for claude.ai / Claude desktop (a zip with the skill folder at its root)
    dist/<name>-v<version>.zip     the same content, for people who unzip into their agent's skills folder

Validation performed first (the build stops on failure):
    - exactly one skills/<name>/SKILL.md, frontmatter has name + description, name matches the folder
    - name is lowercase letters, digits and hyphens, at most 64 characters
    - description is at most 1024 characters
    - every file SKILL.md mentions under scripts/, references/ or assets/ exists

Standard library only.
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {"__pycache__", "node_modules", ".pytest_cache"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    fm, key = {}, None
    for line in m.group(1).splitlines():
        if re.match(r"^[A-Za-z_-]+:", line):
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"')
        elif key == "metadata":
            k, _, v = line.strip().partition(":")
            fm.setdefault("_meta", {})[k.strip()] = v.strip().strip('"')
    return fm


def find_skill():
    found = [p for p in (ROOT / "skills").glob("*/SKILL.md")]
    if len(found) != 1:
        sys.exit(f"Expected exactly one skills/<name>/SKILL.md, found {len(found)}")
    return found[0].parent


def validate(skill):
    errors = []
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    fm = frontmatter(text)
    if not fm:
        return ["SKILL.md has no YAML frontmatter"], {}
    name, desc = fm.get("name", ""), fm.get("description", "")
    if not name:
        errors.append("frontmatter: missing 'name'")
    elif name != skill.name:
        errors.append(f"frontmatter name '{name}' must match folder name '{skill.name}'")
    if name and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
        errors.append("name must be lowercase letters, digits and single hyphens")
    if len(name) > 64:
        errors.append("name longer than 64 characters")
    if not desc:
        errors.append("frontmatter: missing 'description'")
    if len(desc) > 1024:
        errors.append(f"description is {len(desc)} characters; the limit is 1024")
    for ref in sorted(set(re.findall(r"`((?:scripts|references|assets)/[\w./-]+\.\w+)", text))):
        if not (skill / ref).exists():
            errors.append(f"SKILL.md mentions {ref}, which does not exist")
    return errors, fm


def files(skill):
    for p in sorted(skill.rglob("*")):
        rel = p.relative_to(skill.parent)
        if p.is_dir() or any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if p.name in EXCLUDE_FILES or p.suffix in EXCLUDE_SUFFIXES:
            continue
        yield p, rel


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "dist"))
    a = ap.parse_args()

    skill = find_skill()
    errors, fm = validate(skill)
    if errors:
        print("Validation failed:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    version = (fm.get("_meta") or {}).get("version", "0.0.0")
    print(f"OK: {skill.name} v{version}, description {len(fm['description'])}/1024 chars")
    if a.check:
        return

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    targets = [out / f"{skill.name}.skill", out / f"{skill.name}-v{version}.zip"]
    for t in targets:
        with zipfile.ZipFile(t, "w", zipfile.ZIP_DEFLATED) as z:
            for p, rel in files(skill):
                z.write(p, rel.as_posix())
    count = sum(1 for _ in files(skill))
    for t in targets:
        print(f"Built {t.relative_to(ROOT) if t.is_relative_to(ROOT) else t} ({count} files, {t.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
