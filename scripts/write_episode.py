#!/usr/bin/env python3
"""
Write today's episode script with the Anthropic API (web search + web fetch).

Usage:
  python scripts/write_episode.py --kind dagelijks
  python scripts/write_episode.py --kind vrijdagspecial
  python scripts/write_episode.py --kind dagelijks --date 2026-10-11 --dry-run

Writes episodes/<date>.md (daily) or episodes/<date>-vrijdagspecial.md and
prints the source URLs to stdout (used in the commit message).
Exits 0 without doing anything if the file already exists, so a script that
was written by hand is never overwritten.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
EPISODES = ROOT / "episodes"
PROMPTS = ROOT / "prompts"
TZ = ZoneInfo("Europe/Amsterdam")

DEFAULT_MODEL = "claude-sonnet-5-5"
WEEKDAYS = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
MONTHS = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
          "augustus", "september", "oktober", "november", "december"]
# Dutch number words, enough for days of the month
UNITS = ["", "een", "twee", "drie", "vier", "vijf", "zes", "zeven", "acht", "negen"]
TEENS = {10: "tien", 11: "elf", 12: "twaalf", 13: "dertien", 14: "veertien", 15: "vijftien",
         16: "zestien", 17: "zeventien", 18: "achttien", 19: "negentien"}
TENS = {20: "twintig", 30: "dertig"}

LIMITS = {  # word count of running text (without headings)
    "dagelijks": (450, 950),
    "vrijdagspecial": (300, 900),
}


def annotate(msg: str) -> None:
    print(f"! {msg}", file=sys.stderr)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::error::{msg}")


def day_words(n: int) -> str:
    if n == 1:
        return "één"
    if n < 10:
        return UNITS[n]
    if n < 20:
        return TEENS[n]
    tens, unit = divmod(n, 10)
    if unit == 0:
        return TENS[tens * 10]
    joiner = "ën" if UNITS[unit].endswith("e") else "en"
    return f"{UNITS[unit]}{joiner}{TENS[tens * 10]}"


def date_spoken(d: dt.date) -> str:
    return f"{WEEKDAYS[d.weekday()]} {day_words(d.day)} {MONTHS[d.month - 1]}"


def previous_context(kind: str, today: dt.date) -> str:
    """Earlier episodes the model should not repeat."""
    files = sorted(EPISODES.glob("*.md"), reverse=True)
    if kind == "dagelijks":
        picked = [f for f in files if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", f.name)
                  and f.stem < today.isoformat()][:3]
    else:
        picked = [f for f in files if f.name.endswith("-vrijdagspecial.md")
                  and f.name[:10] < today.isoformat()][:1]
    if not picked:
        return "(Er zijn nog geen eerdere afleveringen.)"
    return "\n\n".join(f"=== {f.name} ===\n{f.read_text(encoding='utf-8')}" for f in picked)


def call_model(prompt: str, model: str) -> str:
    import anthropic

    client = anthropic.Anthropic(max_retries=4)
    tools = [
        {"type": "web_search_20260318", "name": "web_search", "max_uses": 15},
        {"type": "web_fetch_20260318", "name": "web_fetch", "max_uses": 20,
         "max_content_tokens": 8000},
    ]
    messages = [{"role": "user", "content": prompt}]
    searches = 0
    for turn in range(12):  # server tools may pause a long turn; continue it
        resp = client.messages.create(model=model, max_tokens=16000,
                                      messages=messages, tools=tools)
        usage = getattr(resp, "usage", None)
        stu = getattr(usage, "server_tool_use", None)
        searches += getattr(stu, "web_search_requests", 0) or 0
        print(f"  turn {turn + 1}: stop={resp.stop_reason} "
              f"in={getattr(usage, 'input_tokens', '?')} out={getattr(usage, 'output_tokens', '?')}",
              file=sys.stderr)
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        print(f"  web searches: {searches}", file=sys.stderr)
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    raise RuntimeError("model did not finish within 12 turns")


def extract(text: str, start: str, end: str) -> str:
    m = re.search(re.escape(start) + r"\s*\n(.*?)\n\s*" + re.escape(end), text, re.S)
    return m.group(1).strip() if m else ""


def validate(episode: str, kind: str, today: dt.date) -> list[str]:
    problems = []
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", episode, re.S)
    if not m:
        return ["front matter (---) ontbreekt"]
    meta, body = m.group(1), m.group(2)
    if f"date: {today.isoformat()}" not in meta:
        problems.append("date in front matter klopt niet")
    if not re.search(r"^title: .+", meta, re.M):
        problems.append("title ontbreekt")
    if kind == "vrijdagspecial" and ("kind: special" not in meta or "label: Vrijdagspecial" not in meta):
        problems.append("kind/label voor de special ontbreken")
    headings = re.findall(r"^(#{2,3}) (.+)$", body, re.M)
    if not headings or headings[0] != ("##", "Opening"):
        problems.append("eerste kop is niet '## Opening'")
    words = len(re.findall(r"\w+", re.sub(r"^#.*$", "", body, flags=re.M)))
    lo, hi = LIMITS[kind]
    if not lo <= words <= hi:
        problems.append(f"{words} woorden, verwacht {lo}-{hi}")
    if re.search(r"https?://|\*\*|\[[^\]]+\]\(", body):
        problems.append("links of markdown-opmaak in de lopende tekst")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["dagelijks", "vrijdagspecial"], required=True)
    ap.add_argument("--date", help="YYYY-MM-DD (default: today in Europe/Amsterdam)")
    ap.add_argument("--dry-run", action="store_true", help="print, do not write")
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(TZ).date()
    name = f"{today.isoformat()}.md" if args.kind == "dagelijks" else f"{today.isoformat()}-vrijdagspecial.md"
    target = EPISODES / name
    if target.exists() and not args.dry_run:
        print(f"= {name} bestaat al; niets te doen", file=sys.stderr)
        return 0
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        annotate("Secret ANTHROPIC_API_KEY ontbreekt (Settings > Secrets and variables > Actions)")
        return 1

    template = (PROMPTS / f"{args.kind}.md").read_text(encoding="utf-8")
    prompt = (template.replace("{{DATUM}}", today.isoformat())
                      .replace("{{DATUM_VOLUIT}}", date_spoken(today))
              + "\n\n## Eerdere afleveringen\n\n" + previous_context(args.kind, today))
    model = os.environ.get("CLAUDE_MODEL", "").strip() or DEFAULT_MODEL

    last_problems: list[str] = []
    for attempt in range(1, 3):
        print(f"+ {name}: schrijven met {model} (poging {attempt})", file=sys.stderr)
        t0 = time.time()
        answer = call_model(prompt if attempt == 1 else prompt + (
            "\n\nLET OP: een vorige poging werd afgekeurd om deze redenen: "
            + "; ".join(last_problems) + ". Los dat op."), model)
        episode = extract(answer, "<<<EPISODE", "EPISODE>>>")
        sources = extract(answer, "<<<BRONNEN", "BRONNEN>>>")
        last_problems = validate(episode, args.kind, today) if episode else ["geen <<<EPISODE-blok in het antwoord"]
        print(f"  klaar in {time.time() - t0:.0f}s; controle: {last_problems or 'in orde'}", file=sys.stderr)
        if not last_problems:
            break
    if last_problems:
        annotate(f"{name}: script afgekeurd: " + "; ".join(last_problems))
        return 1

    if args.dry_run:
        print(episode, file=sys.stderr)   # shows up in the Actions log
    else:
        target.write_text(episode.rstrip() + "\n", encoding="utf-8")
        print(f"+ geschreven: {target.relative_to(ROOT)}", file=sys.stderr)
    # sources to stdout for the commit message
    print("\n".join(u for u in sources.splitlines() if u.strip().startswith("http")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
