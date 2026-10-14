#!/usr/bin/env python3
"""Normalize exported AI conversations into anchored markdown transcripts.

Reads (auto-detected):
  - ChatGPT export: conversations.json (or the export .zip directly)
  - Claude.ai export: conversations.json (or the export .zip)
  - Claude Code sessions: ~/.claude/projects/<project>/*.jsonl
  - Other agent logs (Codex CLI, Gemini CLI, ...): .jsonl/.json with role/content-like fields
  - Markdown / text transcripts with speaker markers ("User:", "## Assistant", "**You:**"), or plain notes

Writes to --out (default .dossier/sources):
  S1.md, S2.md, ...   one per conversation, oldest first, every message tagged [S<n>#m<k>]
  sources.json        manifest {id, tool, title, started, ended, messages, file, origin}

Examples:
  python normalize_exports.py chatgpt.zip claude/conversations.json notes/ --match "habit" --list
  python normalize_exports.py chatgpt.zip claude/conversations.json notes/ --match "habit" --since 2026-08-01

Standard library only.
"""
import argparse
import io
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

MAX_ZIP_MEMBER = 512 * 1024 * 1024  # skip any single archive member larger than this when uncompressed
USER_ROLES = {"user", "human", "you", "me", "prompter"}
ASSIST_ROLES = {"assistant", "ai", "model", "bot", "chatgpt", "claude", "gemini", "copilot", "cursor", "codex", "perplexity"}
TEXT_TYPES = {"text", "input_text", "output_text"}
NAMES = r"(User|You|Me|Human|Prompter|Assistant|AI|ChatGPT|GPT-?[\w.]*|Claude|Gemini|Copilot|Cursor|Codex|Perplexity|Model|Bot)"
SPEAKER_INLINE = re.compile(r"^\s{0,3}(?:>\s*)?(?:\*\*|__)?" + NAMES + r"(?:\*\*|__)?\s*[:：]\s*(?:\*\*|__)?\s*(.*)$", re.I)
SPEAKER_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*(?:\*\*)?" + NAMES + r"(?:\*\*)?\s*[:：]?\s*$", re.I)
SKIP_PREFIXES = ("<environment_context", "<user_instructions", "<system-reminder", "<command-", "<local-command")


# ---------- small utils ----------
def iso(t):
    if t is None or t == "":
        return None
    if isinstance(t, (int, float)):
        if t > 1e12:
            t /= 1000.0
        return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M")
    s = str(t)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        m = re.match(r"\d{4}-\d{2}-\d{2}", s)
        return m.group(0) if m else None


def role_of(r):
    r = (r or "").lower()
    if r in USER_ROLES:
        return "user"
    if r in ASSIST_ROLES:
        return "assistant"
    return None


def text_of(c):
    """Pull readable text out of the many content shapes tools use."""
    if c is None:
        return ""
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(t for t in (text_of(x) for x in c) if t)
    if isinstance(c, dict):
        typ = c.get("type") or c.get("content_type")
        if typ in ("tool_use", "tool_result", "function_call", "function_call_output", "image", "image_url", "thinking", "redacted_thinking"):
            return ""
        if typ in TEXT_TYPES and isinstance(c.get("text"), str):
            return c["text"]
        if "parts" in c:
            return text_of(c["parts"])
        if isinstance(c.get("text"), str):
            return c["text"]
        if "content" in c:
            return text_of(c["content"])
    return ""


def conv(tool, title, msgs, origin):
    msgs = [m for m in msgs if m["text"].strip()]
    times = [m["time"] for m in msgs if m.get("time")]
    return {"tool": tool, "title": (title or "Untitled").strip(), "messages": msgs, "origin": origin,
            "started": min(times) if times else None, "ended": max(times) if times else None}


# ---------- format readers ----------
def read_chatgpt(items, origin):
    out = []
    for c in items:
        mapping = c.get("mapping") or {}
        node = c.get("current_node")
        chain = []
        while node and node in mapping:
            chain.append(mapping[node])
            node = mapping[node].get("parent")
        if not chain:  # fall back to all nodes by time
            chain = sorted(mapping.values(), key=lambda n: ((n.get("message") or {}).get("create_time") or 0), reverse=True)
        msgs = []
        for n in reversed(chain):
            m = n.get("message") or {}
            meta = m.get("metadata") or {}
            if meta.get("is_visually_hidden_from_conversation"):
                continue
            r = role_of((m.get("author") or {}).get("role"))
            if not r:
                continue
            content = m.get("content") or {}
            if content.get("content_type") not in (None, "text", "multimodal_text"):
                continue
            msgs.append({"role": r, "text": text_of(content.get("parts")), "time": iso(m.get("create_time"))})
        cv = conv("ChatGPT", c.get("title"), msgs, origin)
        cv["started"] = cv["started"] or iso(c.get("create_time"))
        out.append(cv)
    return out


def read_claude(items, origin):
    out = []
    for c in items:
        msgs = []
        for m in c.get("chat_messages") or []:
            r = role_of(m.get("sender"))
            if not r:
                continue
            t = text_of(m.get("content")) or m.get("text") or ""
            msgs.append({"role": r, "text": t, "time": iso(m.get("created_at"))})
        cv = conv("Claude", c.get("name"), msgs, origin)
        cv["started"] = cv["started"] or iso(c.get("created_at"))
        out.append(cv)
    return out


def find_messages(obj, acc, time_hint=None):
    """Generic walker: collect dicts that look like {role, content/text/parts}."""
    if isinstance(obj, dict):
        t = obj.get("timestamp") or obj.get("created_at") or obj.get("time") or time_hint
        author = obj.get("author")
        author = author if isinstance(author, str) else (author.get("role") if isinstance(author, dict) else None)
        r = role_of(obj.get("role") or author or obj.get("sender"))
        if r and any(k in obj for k in ("content", "text", "parts")):
            body = text_of(obj.get("content")) or text_of(obj.get("parts")) or (obj.get("text") if isinstance(obj.get("text"), str) else "")
            if body.strip() and not body.lstrip().startswith(SKIP_PREFIXES):
                acc.append({"role": r, "text": body, "time": iso(t)})
            return
        for v in obj.values():
            find_messages(v, acc, t)
    elif isinstance(obj, list):
        for v in obj:
            find_messages(v, acc, time_hint)


def read_jsonl(text, origin, name):
    lines = [l for l in text.splitlines() if l.strip()]
    objs = []
    for l in lines:
        try:
            objs.append(json.loads(l))
        except json.JSONDecodeError:
            continue
    if not objs:
        return []
    # Claude Code session
    if any(isinstance(o, dict) and o.get("type") in ("user", "assistant") and "message" in o for o in objs):
        msgs, title = [], None
        for o in objs:
            if not isinstance(o, dict):
                continue
            if o.get("type") == "summary" and o.get("summary"):
                title = title or o["summary"]
            if o.get("type") not in ("user", "assistant") or o.get("isMeta") or o.get("isSidechain"):
                continue
            m = o.get("message") or {}
            body = text_of(m.get("content"))
            if not body.strip() or body.lstrip().startswith(SKIP_PREFIXES):
                continue
            msgs.append({"role": "user" if o["type"] == "user" else "assistant", "text": body, "time": iso(o.get("timestamp"))})
        return [conv("Claude Code", title or name, msgs, origin)]
    tool = "Codex CLI" if any(isinstance(o, dict) and "payload" in o for o in objs) else "Agent log"
    msgs = []
    for o in objs:
        find_messages(o, msgs)
    return [conv(tool, name, msgs, origin)] if msgs else []


def read_json(data, origin, name):
    if isinstance(data, dict) and "conversations" in data and isinstance(data["conversations"], list):
        data = data["conversations"]
    if isinstance(data, list) and data and isinstance(data[0], dict):
        if "mapping" in data[0]:
            return read_chatgpt(data, origin)
        if "chat_messages" in data[0]:
            return read_claude(data, origin)
    if isinstance(data, dict) and "mapping" in data:
        return read_chatgpt([data], origin)
    if isinstance(data, dict) and "chat_messages" in data:
        return read_claude([data], origin)
    msgs = []
    find_messages(data, msgs)
    tool = "Gemini CLI" if '"model"' in json.dumps(data)[:20000] and "parts" in json.dumps(data)[:20000] else "Agent log"
    return [conv(tool, name, msgs, origin)] if msgs else []


def read_markdown(text, origin, name):
    msgs, cur = [], None
    title = None
    for line in text.splitlines():
        if title is None and line.startswith("# "):
            title = line[2:].strip()
        m = SPEAKER_HEADING.match(line) or SPEAKER_INLINE.match(line)
        if m:
            who = m.group(1).lower()
            r = "user" if who in USER_ROLES else "assistant"
            cur = {"role": r, "text": (m.group(2) if m.re is SPEAKER_INLINE else "").strip(), "time": None}
            msgs.append(cur)
        elif cur is not None:
            cur["text"] += "\n" + line
    if len(msgs) < 2:  # not a dialogue: treat as notes from the person
        return [conv("Notes", title or name, [{"role": "user", "text": text, "time": None}], origin)]
    tool = "Chat transcript"
    low = text.lower()
    for t in ("ChatGPT", "Gemini", "Copilot", "Cursor", "Perplexity", "Claude"):
        if t.lower() in low[:3000]:
            tool = t
            break
    return [conv(tool, title or name, msgs, origin)]


def read_any(name, raw, origin):
    suffix = Path(name).suffix.lower()
    if suffix == ".zip":
        out = []
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for info in z.infolist():
                inner = info.filename
                if inner.endswith("/") or "__MACOSX" in inner:
                    continue
                if info.file_size > MAX_ZIP_MEMBER:
                    print(f"  skipped: {origin}!{inner}: larger than {MAX_ZIP_MEMBER // 2**20} MB uncompressed")
                    continue
                if Path(inner).name in ("conversations.json",) or Path(inner).suffix.lower() in (".jsonl", ".md", ".txt"):
                    out += read_any(inner, z.read(inner), f"{origin}!{inner}")
        return out
    text = raw.decode("utf-8", errors="replace")
    if suffix == ".jsonl":
        return read_jsonl(text, origin, Path(name).stem)
    if suffix == ".json":
        try:
            return read_json(json.loads(text), origin, Path(name).stem)
        except json.JSONDecodeError:
            return read_jsonl(text, origin, Path(name).stem)
    if suffix in (".md", ".markdown", ".txt", ""):
        return read_markdown(text, origin, Path(name).stem)
    return None


# ---------- main ----------
def collect(paths):
    convs, skipped = [], []
    for p in paths:
        p = Path(p).expanduser()
        files = [f for f in p.rglob("*") if f.is_file()] if p.is_dir() else [p]
        for f in sorted(files):
            try:
                got = read_any(f.name, f.read_bytes(), str(f))
            except Exception as e:  # keep going; report at the end
                skipped.append(f"{f}: {e}")
                continue
            if got is None:
                skipped.append(f"{f}: unsupported file type")
                continue
            if not got:
                skipped.append(f"{f}: no messages found")
            convs += got
    return convs, skipped


def main():
    if hasattr(sys.stdout, "reconfigure"):  # never crash on non-ASCII output (e.g. Windows consoles)
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="files or folders")
    ap.add_argument("--out", default=".dossier/sources")
    ap.add_argument("--match", action="append", default=[], help="keep conversations whose title or text contains this (repeatable)")
    ap.add_argument("--since", help="YYYY-MM-DD")
    ap.add_argument("--until", help="YYYY-MM-DD")
    ap.add_argument("--min-messages", type=int, default=1)
    ap.add_argument("--start-id", type=int, default=1, help="first source number, to append to an existing set")
    ap.add_argument("--list", action="store_true", help="only list what was found")
    a = ap.parse_args()

    convs, skipped = collect(a.inputs)
    total = len(convs)
    if a.match:
        terms = [t.lower() for t in a.match]
        convs = [c for c in convs if any(t in c["title"].lower() or any(t in m["text"].lower() for m in c["messages"]) for t in terms)]
    if a.since:
        convs = [c for c in convs if not c["started"] or c["started"][:10] >= a.since]
    if a.until:
        convs = [c for c in convs if not c["started"] or c["started"][:10] <= a.until]
    convs = [c for c in convs if len(c["messages"]) >= a.min_messages]
    convs.sort(key=lambda c: c["started"] or "9999")

    print(f"Found {total} conversation(s); {len(convs)} kept after filters.")
    for s in skipped:
        print("  skipped:", s)
    if a.list:
        for i, c in enumerate(convs, a.start_id):
            print(f"  S{i:<3} {c['tool']:<15} {(c['started'] or 'undated')[:10]}  {len(c['messages']):>4} msgs  {c['title'][:70]}")
        return

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "sources.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() and a.start_id > 1 else []
    for i, c in enumerate(convs, a.start_id):
        sid = f"S{i}"
        lines = [f"# {sid}: {c['title']}", "",
                 f"- Tool: {c['tool']}", f"- Started: {c['started'] or 'unknown'}", f"- Ended: {c['ended'] or 'unknown'}",
                 f"- Messages: {len(c['messages'])}", f"- Origin: {c['origin']}", ""]
        for k, m in enumerate(c["messages"], 1):
            when = f" ({m['time'].replace('T', ' ')})" if m.get("time") else ""
            lines += [f"[{sid}#m{k}] **{m['role']}**{when}", "", m["text"].strip(), ""]
        (out / f"{sid}.md").write_text("\n".join(lines), encoding="utf-8")
        manifest.append({"id": sid, "tool": c["tool"], "title": c["title"], "started": (c["started"] or "")[:10] or None,
                         "ended": (c["ended"] or "")[:10] or None, "messages": len(c["messages"]),
                         "file": f"{sid}.md", "origin": c["origin"]})
        print(f"  {sid}: {c['tool']}, {len(c['messages'])} msgs, {c['title'][:60]}")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(convs)} transcript(s) and {manifest_path}.")


if __name__ == "__main__":
    main()
