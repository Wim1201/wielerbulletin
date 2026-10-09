#!/usr/bin/env python3
"""
Build the Wielerbulletin feed.

For every script in episodes/*.md (last KEEP_DAYS days) this:
  1. splits the script into chapters (## headings),
  2. renders each chapter with ElevenLabs (model eleven_v4 by default),
  3. joins the chapters into one mp3 with a short pause in between,
  4. stores chapter start times and a waveform envelope for the app,
  5. writes feed.json and removes audio older than KEEP_DAYS.

Already rendered episodes are skipped (keyed on a hash of the script),
so re-running the workflow costs no extra ElevenLabs credits.

Usage:
  python scripts/build_episodes.py --episodes episodes --store store
  python scripts/build_episodes.py ... --fake-tts     # test without API calls
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

API_BASE = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL = "eleven_v4"
KEEP_DAYS = int(os.environ.get("KEEP_DAYS", "14"))
PAUSE_SECONDS = 0.8
PEAK_COUNT = 240
SAMPLE_RATE = 44100


def annotate(message: str) -> None:
    """Print an error; on GitHub Actions it also shows as a run annotation."""
    print(f"! {message}", file=sys.stderr)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::error::{message}")


# ---------------------------------------------------------------- parsing

def parse_episode(path: Path) -> dict:
    """Read front matter + chapters from an episode markdown file."""
    raw = path.read_text(encoding="utf-8")
    meta: dict = {}
    body = raw
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip().strip('"')
        body = m.group(2)

    chapters = []
    current = None
    for line in body.splitlines():
        # "## " = chapter, "### " = sub-chapter (e.g. the Visma | Lease a Bike angle)
        heading = re.match(r"^(#{2,3})\s+(.*)$", line)
        if heading:
            current = {"title": heading.group(2).strip(),
                       "level": len(heading.group(1)), "lines": []}
            chapters.append(current)
        elif current is not None:
            current["lines"].append(line)
    for ch in chapters:
        text = "\n".join(ch.pop("lines")).strip()
        # Plain text for TTS: no markdown emphasis, no pipes from team names.
        ch["text"] = re.sub(r"[*_`#>]", "", text).replace("|", " ")
    chapters = [c for c in chapters if c["text"]]
    if not chapters:
        raise ValueError(f"{path.name}: no '## ' chapters with text found")
    if chapters[0]["level"] != 2:
        raise ValueError(f"{path.name}: the first heading must be a '## ' chapter")

    date = meta.get("date") or path.stem
    dt.date.fromisoformat(date)  # validate
    return {
        "date": date,
        "title": meta.get("title", f"Wielerbulletin {date}"),
        "summary": meta.get("summary", ""),
        "chapters": chapters,
        "hash": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16],
    }


# ---------------------------------------------------------------- TTS

def tts_elevenlabs(text: str, out: Path) -> None:
    """Render one chapter to mp3 via ElevenLabs. Falls back to the
    text-to-dialogue endpoint if the TTS endpoint rejects the model."""
    import requests

    key = os.environ["ELEVENLABS_API_KEY"]
    voice = os.environ["ELEVENLABS_VOICE_ID"]
    model = os.environ.get("ELEVENLABS_MODEL", DEFAULT_MODEL)
    headers = {"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    params = {"output_format": "mp3_44100_128"}
    # Steady, businesslike delivery: high stability, no added style.
    settings = {"stability": 0.7, "similarity_boost": 0.8, "style": 0.0,
                "use_speaker_boost": True, "speed": 1.0}

    attempts = [
        (f"{API_BASE}/text-to-speech/{voice}",
         {"text": text, "model_id": model, "language_code": "nl", "voice_settings": settings}),
        (f"{API_BASE}/text-to-dialogue",
         {"inputs": [{"text": text, "voice_id": voice}], "model_id": model,
          "language_code": "nl", "settings": {"stability": settings["stability"]}}),
    ]
    last_error = ""
    for url, payload in attempts:
        for attempt in range(4):
            r = requests.post(url, params=params, headers=headers, json=payload, timeout=300)
            if r.status_code == 200 and r.content:
                out.write_bytes(r.content)
                return
            last_error = f"{url} -> HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(5 * (attempt + 1))
                continue
            break  # client error: try the next endpoint
        print(f"  ! {last_error}", file=sys.stderr)
    raise RuntimeError(f"ElevenLabs failed: {last_error}")


def tts_fake(text: str, out: Path) -> None:
    """Test mode: a speech-like tone whose length matches the text."""
    seconds = max(3.0, len(text) / 15.0)
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
         f"sine=frequency=180:duration={seconds:.2f}",
         "-f", "lavfi", "-i", f"anoisesrc=d={seconds:.2f}:a=0.15",
         "-filter_complex",
         "[0][1]amix=inputs=2,volume='if(lt(mod(t,4.3),0.5),0.03,0.35+0.65*abs(sin(t*2.3)*sin(t*0.37)))':eval=frame",
         "-ar", str(SAMPLE_RATE), "-b:a", "128k", str(out)],
        check=True)


# ---------------------------------------------------------------- audio

def duration_of(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def concat_with_pauses(parts: list[Path], out: Path, workdir: Path) -> list[float]:
    """Join parts with silence; returns chapter start times in seconds.
    Uses the real (encoded) length of the pause so chapter times stay exact."""
    silence = workdir / "pause.mp3"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
         f"anullsrc=r={SAMPLE_RATE}:cl=mono", "-t", str(PAUSE_SECONDS),
         "-b:a", "128k", str(silence)], check=True)
    pause = duration_of(silence)

    listing = workdir / "list.txt"
    starts, t, lines = [], 0.0, []
    for i, part in enumerate(parts):
        if i:
            lines.append(f"file '{silence}'")
            t += pause
        starts.append(round(t, 2))
        lines.append(f"file '{part}'")
        t += duration_of(part)
    listing.write_text("\n".join(lines))
    # Re-encode for a clean, gapless single file (mono 64 kbps keeps it small).
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-ac", "1", "-ar", str(SAMPLE_RATE),
         "-b:a", "96k", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", str(out)],
        check=True)
    return starts


def waveform_peaks(path: Path, count: int = PEAK_COUNT) -> list[float]:
    """RMS envelope of the file, normalised to 0..1, for the app's waveform."""
    pcm = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(path), "-ac", "1",
         "-ar", "8000", "-f", "s16le", "-"],
        check=True, capture_output=True).stdout
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    if samples.size == 0:
        return [0.0] * count
    chunks = np.array_split(samples, count)
    rms = np.array([np.sqrt(np.mean(c ** 2)) if c.size else 0.0 for c in chunks])
    rms = rms / (rms.max() or 1.0)
    return [round(float(v) ** 0.7, 3) for v in rms]  # soft curve looks livelier


# ---------------------------------------------------------------- build

def render_episode(ep: dict, audio_dir: Path, fake: bool) -> dict:
    mp3 = audio_dir / f"{ep['date']}.mp3"
    meta_path = audio_dir / f"{ep['date']}.json"
    if mp3.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta.get("hash") == ep["hash"]:
            print(f"= {ep['date']}: up to date")
            return meta

    print(f"+ {ep['date']}: rendering {len(ep['chapters'])} chapters"
          f" ({sum(len(c['text']) for c in ep['chapters'])} chars)")
    tts = tts_fake if fake else tts_elevenlabs
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        parts = []
        for i, ch in enumerate(ep["chapters"]):
            part = work / f"part{i:02d}.mp3"
            tts(ch["text"], part)
            parts.append(part)
            print(f"  - {ch['title']}: {duration_of(part):.1f}s")
        starts = concat_with_pauses(parts, mp3, work)

    meta = {
        "hash": ep["hash"],
        "duration": round(duration_of(mp3), 2),
        "chapters": [{"title": c["title"], "start": s, "level": c["level"]}
                     for c, s in zip(ep["chapters"], starts)],
        "peaks": waveform_peaks(mp3),
        "model": "fake" if fake else os.environ.get("ELEVENLABS_MODEL", DEFAULT_MODEL),
    }
    meta_path.write_text(json.dumps(meta))
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", default="episodes")
    ap.add_argument("--store", default="store", help="persistent audio store (audio branch)")
    ap.add_argument("--fake-tts", action="store_true")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD) for testing")
    args = ap.parse_args()

    if not args.fake_tts:
        missing = [k for k in ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID")
                   if not os.environ.get(k, "").strip()]
        if missing:
            annotate("Secret ontbreekt of is leeg: " + ", ".join(missing)
                     + " (Settings > Secrets and variables > Actions)")
            return 1

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    cutoff = today - dt.timedelta(days=KEEP_DAYS - 1)
    store = Path(args.store)
    audio_dir = store / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    feed, failures = [], 0
    for path in sorted(Path(args.episodes).glob("*.md"), reverse=True):
        try:
            ep = parse_episode(path)
        except ValueError as exc:
            annotate(str(exc))
            failures += 1
            continue
        if dt.date.fromisoformat(ep["date"]) < cutoff:
            continue
        try:
            meta = render_episode(ep, audio_dir, args.fake_tts)
        except Exception as exc:  # keep older episodes publishable
            annotate(f"{ep['date']}: {exc}")
            failures += 1
            continue
        feed.append({
            "date": ep["date"],
            "title": ep["title"],
            "summary": ep["summary"],
            "audio": f"audio/{ep['date']}.mp3?v={meta['hash']}",
            "duration": meta["duration"],
            "chapters": meta["chapters"],
            "peaks": meta["peaks"],
        })

    # Prune audio that fell out of the window.
    keep = {e["date"] for e in feed}
    for f in audio_dir.iterdir():
        if f.stem not in keep:
            f.unlink()
            print(f"- pruned {f.name}")

    (store / "feed.json").write_text(json.dumps({
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "episodes": feed,
    }, ensure_ascii=False, indent=1))
    print(f"feed.json: {len(feed)} episodes")
    # Fail the run only if today's episode could not be built.
    return 1 if failures and not any(e["date"] == today.isoformat() for e in feed) else 0


if __name__ == "__main__":
    sys.exit(main())
