"""Build the LatentCode demo video using the demo-video-pipeline skill.

Architecture: Marp slides + Playwright recordings → FFmpeg stitch → final MP4.

The skill wanted TTS voiceover (Sarvam) and a Gemini planner. Both are
dropped because:
  - Speech isn't mandatory for the submission.
  - The 8-segment plan is small + deterministic; no LLM needed.

We pre-render the actual command output (pytest, scan, eval, regress) to
styled HTML, and Playwright records scrolling through them. No real
terminal, no real network calls during recording.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent
BUILD = REPO / "scripts" / "build"
SLIDES = BUILD / "slides"
HTML = BUILD / "html"
RECORDINGS = BUILD / "recordings"
SEGMENTS = BUILD / "segments"
FINAL = BUILD / "final"

VIEWPORT = {"width": 1280, "height": 720}
FPS = 25


# ---------------------------------------------------------------------------
# 1. Marp slide generation
# ---------------------------------------------------------------------------

CSS = """
section {
    width: 1280px; height: 720px;
    display: flex; flex-direction: column;
    justify-content: center; align-items: center;
    text-align: center; padding: 60px;
    font-family: 'Helvetica Neue', Arial, sans-serif;
    background: #0b0d12; color: #e5e7eb;
}
h1 { font-size: 56px; color: #c4b5fd; margin-bottom: 20px; }
h2 { font-size: 36px; color: #c4b5fd; margin-bottom: 30px; }
h3 { font-size: 28px; color: #fcd34d; margin: 20px 0 10px 0; }
p, li { font-size: 24px; color: #e5e7eb; line-height: 1.4; }
code { font-family: 'SF Mono', Consolas, monospace; color: #6ee7b7; }
pre { background: #000; padding: 16px; border-radius: 6px; font-size: 18px; }
ul { text-align: left; max-width: 900px; }
section.title h1 { font-size: 80px; }
section.subtitle { color: #9ca3af; }
section.subtitle p { color: #9ca3af; }
"""

SLIDES_MD = {
    "01_title": """# LatentCode

Finding hidden defects in software projects

BuildSprint 2026
""",
    "02_problem": """# The Problem

LLM-generated code looks done — but isn't

- **Disconnected code** — components that compile but are never called
- **Broken end-to-end features** — UI exists, API exists, wiring doesn't
- **Agent shortcuts** — `TODO` in shipping paths, `not implemented` in handlers

Standard linters miss it. Tests pass because they were never written for those paths.
""",
    "04_architecture": """# Architecture

```
  static + runtime evidence
            │
            ▼
  ┌─────────────────┐
  │     JUDGE       │  classify + score, NO patch
  └────────┬────────┘
            ▼
  ┌─────────────────┐
  │    PROPOSER     │  write diff, scope-validated
  └────────┬────────┘
            ▼
  Approval Queue → Human → Apply → Regress
```

Tooling-led, LLM-assisted. Five interface layers.
""",
    "08_closing": """# Five Interfaces, One Pipeline

```
  CLI      latentcode scan | repair | fix | regress | verify | eval
  MCP      8 tools (latentcode_scan, ...)
  Skill    /latentcode
  Hook     pre-commit
  Web      Next.js dashboard
```

github.com/Hemanthdamineni/latentcode

17 tests · 3-class eval harness · sectioned before/after report
""",
}


def render_slides() -> dict[str, Path]:
    """Render all Marp slides to PNG. Returns {name: path}."""
    SLIDES.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, md in SLIDES_MD.items():
        front = f"---\nmarp: true\ntheme: gaia\nsize: 16:9\n---\n\n"
        full = front + md
        md_path = SLIDES / f"{name}.md"
        md_path.write_text(full, encoding="utf-8")
        png_path = SLIDES / f"{name}.png"
        # Build the slide using a sub-page of the marp HTML output
        # simpler: use --image png via npx marp-cli
        cmd = ["npx", "--yes", "@marp-team/marp-cli", "--image", "png",
               "--allow-local-files", "-o", str(png_path), str(md_path)]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, cwd=str(SLIDES))
        paths[name] = png_path
        print(f"  slide: {name} -> {png_path.name}")
    return paths


# ---------------------------------------------------------------------------
# 2. Terminal-as-HTML recording
# ---------------------------------------------------------------------------

TERMINAL_CSS = """
body {
    margin: 0; background: #0b0d12; color: #e5e7eb;
    font-family: 'SF Mono', 'Consolas', 'Liberation Mono', monospace;
    font-size: 28px; line-height: 1.6;
    padding: 50px 70px;
    min-height: 100vh;
    box-sizing: border-box;
}
.prompt { color: #6ee7b7; }
.path { color: #c4b5fd; }
.success { color: #10b981; font-weight: bold; }
.warn { color: #fcd34d; }
.danger { color: #fca5a5; }
.muted { color: #6b7280; }
.heading { color: #c4b5fd; font-weight: bold; margin-top: 16px; }
pre { font-family: inherit; margin: 0; white-space: pre-wrap; font-size: 28px; }
"""


def make_terminal_html(title: str, body_html: str) -> Path:
    """Wrap text content in a styled terminal-style HTML page."""
    HTML.mkdir(parents=True, exist_ok=True)
    safe_title = title.replace(" ", "_").lower()
    out = HTML / f"{safe_title}.html"
    full = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>{TERMINAL_CSS}</style></head>
<body><pre>{body_html}</pre></body></html>"""
    out.write_text(full, encoding="utf-8")
    return out


def text_to_html(text: str) -> str:
    """Convert plain text command output to terminal-style HTML.

    Heuristics: colorize '→' lines, .py lines, PASS/FAIL markers, etc.
    """
    import html
    out = []
    for line in text.splitlines():
        line_esc = html.escape(line)
        if line.startswith(("→", "$", "latentcode", "python", "pytest")):
            line_esc = f'<span class="prompt">{line_esc}</span>'
        elif "passed" in line.lower() or "✓" in line:
            line_esc = f'<span class="success">{line_esc}</span>'
        elif "warning" in line.lower() or "WARN" in line:
            line_esc = f'<span class="warn">{line_esc}</span>'
        elif "failed" in line.lower() or "error" in line.lower() or "✗" in line:
            line_esc = f'<span class="danger">{line_esc}</span>'
        elif line.startswith("#"):
            line_esc = f'<span class="heading">{line_esc}</span>'
        out.append(line_esc)
    return "\n".join(out)


# 4 HTML pages for the 4 recording segments
RECORDINGS_SRC = {
    "03_pytest": {
        "title": "Pytest output",
        "body": (BUILD / "pytest_output.txt").read_text(),
    },
    "05_scan": {
        "title": "LatentCode scan",
        "body": (BUILD / "scan_output.txt").read_text(),
    },
    "06_eval": {
        "title": "LatentCode eval",
        "body": (BUILD / "eval_output.txt").read_text(),
    },
    "07_regress": {
        "title": "LatentCode regress",
        "body": (BUILD / "regress_output.txt").read_text(),
    },
}


def render_htmls() -> dict[str, Path]:
    """Render all 4 terminal HTML pages."""
    paths = {}
    for name, src in RECORDINGS_SRC.items():
        html_body = text_to_html(src["body"])
        paths[name] = make_terminal_html(src["title"], html_body)
        print(f"  html: {name} -> {paths[name].name}")
    return paths


def record_segment(page_url: str, output_webm: Path, hold_seconds: float = 4.0) -> None:
    """Record a Playwright page navigation as a .webm video.

    The recording uses Playwright's native video capture. The page is
    scrolled to the top, held for `hold_seconds` (long enough for the
    recording to capture the full content as a stable shot), then closed.

    A single static shot is more readable than a slow scroll for
    short terminal output. The HTML is styled so the whole content fits
    in the viewport.
    """
    RECORDINGS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        context = browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(RECORDINGS),
            record_video_size=VIEWPORT,
        )
        page = context.new_page()
        page.set_default_timeout(10000)
        page.goto(page_url, wait_until="load")
        # If content is taller than viewport, scroll through it
        height = page.evaluate("() => document.body.scrollHeight")
        viewport_h = VIEWPORT["height"]
        if height > viewport_h * 1.2:
            pos = 0
            while pos < height - viewport_h:
                pos += viewport_h // 2
                page.evaluate(f"window.scrollTo(0, {pos})")
                page.wait_for_timeout(700)
        # Hold the final view for the bulk of the recording
        page.wait_for_timeout(int(hold_seconds * 1000))
        context.close()
        browser.close()
    # Move the latest webm to the requested path
    webms = sorted(RECORDINGS.glob("*.webm"), key=lambda p: p.stat().st_mtime)
    if not webms:
        raise RuntimeError(f"No webm produced for {page_url}")
    shutil.move(str(webms[-1]), str(output_webm))
    print(f"  recorded: {output_webm.name} (held {hold_seconds}s)")


# ---------------------------------------------------------------------------
# 3. FFmpeg media stitching
# ---------------------------------------------------------------------------

def get_audio_duration(wav_path: Path) -> float:
    with wave.open(str(wav_path), "rb") as w:
        frames = w.getnframes()
        rate = w.getframerate()
        if rate == 0:
            raise ValueError("audio sample rate is 0")
        return frames / float(rate)


def make_silent_wav(out_path: Path, seconds: float) -> Path:
    """Generate a silent WAV file of the given length."""
    import struct
    sample_rate = 44100
    n_samples = int(seconds * sample_rate)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x00" * n_samples * 2)
    return out_path


def image_to_mp4(image: Path, audio: Path | None, out_mp4: Path, duration_s: float) -> None:
    """Loop a static image for `duration_s`, optionally with audio."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    if audio and audio.exists():
        cmd = ["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS),
               "-i", str(image), "-i", str(audio),
               "-c:v", "libx264", "-t", f"{duration_s:.3f}",
               "-pix_fmt", "yuv420p", "-r", str(FPS), "-s", "1280x720",
               "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
               "-shortest", str(out_mp4)]
    else:
        # synthetic silent audio
        silent = out_mp4.with_suffix(".silent.wav")
        make_silent_wav(silent, duration_s)
        cmd = ["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS),
               "-i", str(image), "-i", str(silent),
               "-c:v", "libx264", "-t", f"{duration_s:.3f}",
               "-pix_fmt", "yuv420p", "-r", str(FPS), "-s", "1280x720",
               "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
               "-shortest", str(out_mp4)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  segment: {out_mp4.name}")


def webm_to_mp4(webm: Path, out_mp4: Path, target_duration: float) -> None:
    """Transcode a Playwright webm to a uniform mp4 clip with silent audio.

    The webm may be shorter than `target_duration` because Playwright
    optimizes static content. We force the output to the requested duration
    by using `-t` and matching video length to the audio.
    """
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    silent = out_mp4.with_suffix(".silent.wav")
    make_silent_wav(silent, target_duration)
    cmd = ["ffmpeg", "-y",
           "-i", str(webm),
           "-i", str(silent),
           "-filter_complex", "[0:v]scale=1280:720:force_original_aspect_ratio=decrease,"
                              "pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1[v]",
           "-map", "[v]", "-map", "1:a",
           "-t", f"{target_duration:.3f}",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
           str(out_mp4)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  segment: {out_mp4.name} ({target_duration}s)")


def concat_segments(segments: list[Path], final_mp4: Path) -> None:
    """Concatenate uniform mp4 clips via FFmpeg concat demuxer."""
    final_mp4.parent.mkdir(parents=True, exist_ok=True)
    list_file = final_mp4.parent / "concat_inputs.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for s in segments:
            safe = str(s.resolve()).replace("'", "'\\''")
            f.write(f"file '{safe}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", str(list_file), "-c", "copy", str(final_mp4)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    list_file.unlink()
    print(f"  final: {final_mp4}")


# ---------------------------------------------------------------------------
# 4. Pipeline orchestration
# ---------------------------------------------------------------------------

# Segment plan: (name, type, duration_s)
PLAN = [
    ("01_title",     "slide",  6.0),
    ("02_problem",   "slide",  12.0),
    ("03_pytest",    "record", 6.0),
    ("04_architecture", "slide", 10.0),
    ("05_scan",      "record", 8.0),
    ("06_eval",      "record", 6.0),
    ("07_regress",   "record", 6.0),
    ("08_closing",   "slide",  8.0),
]


def main() -> Path:
    print("=== 1. Rendering slides (Marp) ===")
    slide_paths = render_slides()

    print("\n=== 2. Rendering terminal HTML pages ===")
    html_paths = render_htmls()

    print("\n=== 3. Recording segments (Playwright) ===")
    RECORDINGS.mkdir(parents=True, exist_ok=True)
    record_paths = {}
    # Map recording names to PLAN duration + 0.5s scroll buffer
    record_hold = {name: dur + 0.5 for name, kind, dur in PLAN if kind == "record"}
    for name, html_path in html_paths.items():
        webm = RECORDINGS / f"{name}.webm"
        record_segment(html_path.as_uri(), webm, hold_seconds=record_hold.get(name, 4.0))
        record_paths[name] = webm

    print("\n=== 4. Building per-segment MP4s ===")
    SEGMENTS.mkdir(parents=True, exist_ok=True)
    segment_paths = []
    for name, kind, dur in PLAN:
        seg_mp4 = SEGMENTS / f"{name}.mp4"
        if kind == "slide":
            image_to_mp4(slide_paths[name], None, seg_mp4, dur)
        else:
            webm_to_mp4(record_paths[name], seg_mp4, target_duration=dur)
        segment_paths.append(seg_mp4)

    print("\n=== 5. Concatenating final video ===")
    final_mp4 = FINAL / "latentcode_demo.mp4"
    concat_segments(segment_paths, final_mp4)

    size_mb = final_mp4.stat().st_size / (1024 * 1024)
    print(f"\n✓ Done. {final_mp4} ({size_mb:.1f} MB)")
    return final_mp4


if __name__ == "__main__":
    main()