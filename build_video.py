"""Build the LatentCode demo video v2 — real terminal recording.

Architecture (from SkillPatch's demo-video-pipeline skill, refined):
  - Python's `pty` module spawns commands in real PTYs. Each command's
    stdout is captured byte-by-byte with timing. The output is written
    directly in asciicast v2 format (`<timestamp>, "o", "..."` events)
    — same format asciinema produces.
  - agg converts each `.cast` to MP4 with proper font rendering at 60fps.
  - 2 Marp slides (title + closing) bookend the recording.
  - ffmpeg `concat` demuxer stitches the 7 segments into the final MP4.

Why not asciinema rec -c '<cmd>'? Because the command's stdout is then a
pipe, not a TTY, so tools like pytest buffer their output and dump it all
at the end. The recording looks static (2-3 events total).

This script uses Python's pty.fork() to give each command a real TTY,
reads byte-by-byte, and synthesizes asciicast v2 events. The result is
identical to what asciinema would have recorded if it had a real shell
to drive. The .cast files are valid asciicast v2 and can be replayed
with `asciinema play` or any asciinema-compatible viewer.
"""
from __future__ import annotations

import errno
import json
import os
import pty
import re
import select
import shutil
import subprocess
import sys
import termios
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent
BUILD = REPO / "scripts" / "build"
CAST = BUILD / "cast"
SLIDES = BUILD / "slides"
SEGMENTS = BUILD / "segments"
FINAL = BUILD / "final"

LATENTCODE_DIR = REPO  # run latentcode from its own repo
AGG_BIN = shutil.which("agg") or "/home/zorro-omarchy/.local/bin/agg"

# Terminal dimensions pinned for consistent rendering
COLS = 120
ROWS = 30

# Slides use these CSS
SLIDE_CSS = """
section {
    width: 1280px; height: 720px;
    display: flex; flex-direction: column;
    justify-content: center; align-items: center;
    text-align: center; padding: 60px;
    font-family: 'Helvetica Neue', Arial, sans-serif;
    background: #0b0d12; color: #e5e7eb;
}
h1 { font-size: 64px; color: #c4b5fd; margin-bottom: 16px; }
h2 { font-size: 40px; color: #c4b5fd; margin-bottom: 24px; }
p, li { font-size: 24px; color: #e5e7eb; line-height: 1.4; }
code { font-family: 'SF Mono', Consolas, monospace; color: #6ee7b7; }
pre { background: #000; padding: 16px; border-radius: 6px; font-size: 18px; }
section.subtitle { color: #9ca3af; }
"""

SLIDES_MD = {
    "01_title": """# LatentCode

Finding hidden defects in software projects

BuildSprint 2026
""",
    "07_closing": """# github.com/Hemanthdamineni/latentcode

Five interfaces, one pipeline:

`latentcode scan | repair | fix | regress | verify | eval`

17 tests · 3-class eval harness · sectioned before/after report
""",
}

# Each cast segment is a real shell command. The command runs in a real
# PTY; asciinema captures every byte in/out. The .cast file is the
# source of truth — re-running the same command produces equivalent
# output. No mocks, no pre-rendered HTML.
#
# Commands are prepended with a `clear` so each segment starts on a fresh
# screen. The "title" command (`echo === ... ===`) prints a header that
# stays visible while the rest of the output scrolls in.

QUEUE_INSPECTOR = (
    "import json,sys; "
    "q=json.load(sys.stdin); "
    "p=q['pending'][0]; "
    "print('id:           ', p['id']); "
    "print('patch_source: ', p['patch_source']); "
    "print('scope files:  ', p['candidate'].get('repair_scope',{}).get('files',[])); "
    "print(); "
    "print('--- patch (unified diff) ---'); "
    "print(p['patch'])"
)

CAST_SEGMENTS = [
    {
        "name": "02_pytest",
        "title": "Tests: 17 passed",
        "command": (
            f"cd {REPO} && "
            f"export TERM=xterm-256color && "
            f"clear && "
            f"echo '=== pytest tests/ -v (17 smoke tests for the v0.3 pipeline) ===' && "
            f"sleep 0.4 && "
            # PYTHONUNBUFFERED=1 forces line-buffered output. No pipe (no
            # tail) — let the full pytest output scroll in the terminal.
            # The 30-row viewport will scroll naturally; agg captures
            # the scrollback.
            f"PYTHONUNBUFFERED=1 python3 -m pytest tests/ -v --color=yes 2>&1"
        ),
        "expected_seconds": 6.0,
    },
    {
        "name": "03_scan",
        "title": "Scan: 16 issues across 3 categories",
        "command": (
            f"cd {REPO} && "
            f"export TERM=xterm-256color && "
            f"clear && "
            f"sleep 0.4 && "
            f"rm -rf examples/target_repos/broken-app/.latentcode && "
            f"echo '=== latentcode scan examples/target_repos/broken-app ===' && "
            f"sleep 0.4 && "
            # No tail — let the full scan output (small) render.
            f"PYTHONUNBUFFERED=1 latentcode scan examples/target_repos/broken-app --judge heuristic 2>&1"
        ),
        "expected_seconds": 8.0,
    },
    {
        "name": "04_queue",
        "title": "Approval queue: scope + diff per patch",
        "command": (
            f"cd {REPO} && "
            f"export TERM=xterm-256color && "
            f"clear && "
            f"sleep 0.4 && "
            f"echo '=== inspect one pending patch from the approval queue ===' && "
            f"sleep 0.4 && "
            f"latentcode scan examples/target_repos/broken-app --judge heuristic --no-queue --out /tmp/inspect-scan > /dev/null 2>&1 && "
            f"PYTHONUNBUFFERED=1 python3 -u {REPO}/scripts/build/inspect_queue.py 2>&1"
        ),
        "expected_seconds": 8.0,
    },
    {
        "name": "05_eval",
        "title": "Eval harness: static / integration / behavioral",
        "command": (
            f"cd {REPO} && "
            f"export TERM=xterm-256color && "
            f"clear && "
            f"sleep 0.4 && "
            f"echo '=== three-class eval against the e2e-broken target ===' && "
            f"sleep 0.4 && "
            f"PYTHONUNBUFFERED=1 latentcode eval examples/target_repos/e2e-broken 2>&1"
        ),
        "expected_seconds": 6.0,
    },
    {
        "name": "06_regress",
        "title": "Regress: sectioned before/after report",
        "command": (
            f"cd {REPO} && "
            f"export TERM=xterm-256color && "
            f"clear && "
            f"sleep 0.4 && "
            f"echo '=== sectioned regression report (no composite %) ===' && "
            f"sleep 0.4 && "
            f"PYTHONUNBUFFERED=1 latentcode regress examples/target_repos/broken-app --baseline /tmp/baseline-v2/findings.json 2>&1"
        ),
        "expected_seconds": 6.0,
    },
]


# ---------------------------------------------------------------------------
# 1. Marp slide rendering
# ---------------------------------------------------------------------------

def render_slides() -> dict[str, Path]:
    SLIDES.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, md in SLIDES_MD.items():
        front = f"---\nmarp: true\ntheme: gaia\nsize: 16:9\n---\n\n"
        full = front + md
        md_path = SLIDES / f"{name}.md"
        md_path.write_text(full, encoding="utf-8")
        png_path = SLIDES / f"{name}.png"
        cmd = ["npx", "--yes", "@marp-team/marp-cli", "--image", "png",
               "--allow-local-files", "-o", str(png_path), str(md_path)]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, cwd=str(SLIDES))
        paths[name] = png_path
        print(f"  slide: {name} -> {png_path.name}")
    return paths


def image_to_mp4(image: Path, out_mp4: Path, duration_s: float) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    silent = out_mp4.with_suffix(".silent.wav")
    sr = 44100
    n = int(duration_s * sr)
    import wave
    with wave.open(str(silent), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(b"\x00\x00" * n * 2)
    cmd = ["ffmpeg", "-y", "-loop", "1", "-framerate", "25",
           "-i", str(image), "-i", str(silent),
           "-c:v", "libx264", "-t", f"{duration_s:.3f}",
           "-pix_fmt", "yuv420p", "-r", "25", "-s", "1280x720",
           "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
           "-shortest", str(out_mp4)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  segment: {out_mp4.name} ({duration_s}s slide)")


# ---------------------------------------------------------------------------
# 2. Real PTY recording
# ---------------------------------------------------------------------------

def record_in_pty(command: str, out_cast: Path, max_seconds: float = 30.0) -> None:
    """Run `command` in a real PTY, capture every byte, write asciicast v2.

    This is what asciinema would do, but in pure Python. We use pty.fork()
    to spawn the command in a new session with a real PTY, then read
    output byte-by-byte (with a small delay per chunk to simulate
    realistic pacing). The output is written in asciicast v2 format
    so agg can render it.
    """
    CAST.mkdir(parents=True, exist_ok=True)
    if out_cast.exists():
        out_cast.unlink()

    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["COLUMNS"] = str(COLS)
    env["LINES"] = str(ROWS)
    env["LATENTCODE_DEMO"] = "1"  # marker for any demo-aware hooks

    pid, fd = pty.fork()
    if pid == 0:
        # Child: set up the TTY then exec the command via bash -c
        try:
            # Set the window size via ioctl TIOCSWINSZ
            import fcntl
            fcntl.ioctl(0, termios.TIOCSWINSZ,
                       struct.pack("HHHH", ROWS, COLS, 0, 0))
        except Exception:
            pass
        # Use bash -c to run the command, so we get shell parsing + builtins
        os.execvpe("/bin/bash", ["bash", "-c", command], env)

    # Parent: read the PTY, write events
    events: list[tuple[float, str, str]] = []
    start = time.time()

    # Mark start
    out_handle = out_cast.open("w", encoding="utf-8")
    header = {
        "version": 2,
        "width": COLS,
        "height": ROWS,
        "timestamp": int(start),
        "env": {"SHELL": "/bin/bash", "TERM": "xterm-256color"},
    }
    out_handle.write(json.dumps(header) + "\n")

    try:
        while True:
            elapsed = time.time() - start
            if elapsed > max_seconds:
                # Hard cap to avoid runaway processes
                try:
                    os.kill(pid, 9)
                except ProcessLookupError:
                    pass
                break

            # Wait for output or timeout (poll every 50ms for responsiveness)
            try:
                rlist, _, _ = select.select([fd], [], [], 0.05)
            except (OSError, ValueError):
                break
            if not rlist:
                # Check if child has exited
                wait_pid, status = os.waitpid(pid, os.WNOHANG)
                if wait_pid == pid:
                    # Drain any remaining output
                    try:
                        while True:
                            chunk = os.read(fd, 4096)
                            if not chunk:
                                break
                            events.append((time.time() - start, "o", chunk.decode("utf-8", errors="replace")))
                    except OSError:
                        pass
                    break
                continue

            try:
                chunk = os.read(fd, 4096)
            except OSError as e:
                if e.errno == errno.EIO:
                    break
                raise
            if not chunk:
                break
            text = chunk.decode("utf-8", errors="replace")
            events.append((time.time() - start, "o", text))

            # After all data is consumed, check if child exited
            wait_pid, status = os.waitpid(pid, os.WNOHANG)
            if wait_pid == pid:
                # Drain any remaining
                try:
                    while True:
                        extra = os.read(fd, 4096)
                        if not extra:
                            break
                        events.append((time.time() - start, "o", extra.decode("utf-8", errors="replace")))
                except OSError:
                    pass
                break
    finally:
        # Write all events to the cast file. Use json.dumps to handle
        # all control characters correctly (ESC, \r, \n, etc.) — asciicast v2
        # uses standard JSON escaping.
        for t, kind, data in events:
            escaped_data = json.dumps(data, ensure_ascii=False)
            out_handle.write(f'[{t:.6f}, "{kind}", {escaped_data}]\n')
        out_handle.close()
        # Wait for the child to finish (in case we didn't get a clean exit)
        try:
            os.waitpid(pid, 0)
        except (OSError, ChildProcessError):
            pass


def record_cast(name: str, command: str, out_cast: Path) -> None:
    """Record a real shell session in a real PTY and write asciicast v2."""
    # Strip leading `cd ... &&` from the command because we set cwd in the
    # asciicast header. We keep the bash -c wrapping for shell parsing.
    inner = command
    if inner.startswith("cd ") and " && " in inner:
        # Extract the part after the first ` && `
        inner = inner.split(" && ", 1)[1]
    if inner.startswith("export TERM=xterm-256color && "):
        inner = inner.replace("export TERM=xterm-256color && ", "", 1)

    record_in_pty(inner, out_cast, max_seconds=20.0)
    size = out_cast.stat().st_size
    print(f"  cast: {out_cast.name} ({size} bytes)")


# ---------------------------------------------------------------------------
# 3. agg render
# ---------------------------------------------------------------------------

def render_cast(cast_path: Path, mp4_path: Path, font_size: int = 16) -> None:
    """Render a .cast to MP4 using agg.

    agg is the official asciinema-to-MP4 converter (Rust). It uses
    alacritty's terminal renderer for proper font hinting and exact
    frame timing. The output resolution is computed from font size and
    terminal dimensions.

    Important: agg's `--idle-time-limit` is applied to IDLE GAPS in the
    recording (periods with no output). Setting it to 3 means any 3+
    second idle gap is collapsed to 3s in the output. For a 30s video
    where the command finishes in 5s of actual output, that gives us
    ~3.5s of output + 25s of waiting — not what we want.

    We pass --idle-time-limit 30 to be safe (longer than our longest
    segment's real duration) and let agg do the right thing.
    """
    mp4_path.parent.mkdir(parents=True, exist_ok=True)
    if mp4_path.exists():
        mp4_path.unlink()
    cmd = [
        AGG_BIN,
        str(cast_path),
        str(mp4_path),
        "--cols", str(COLS),
        "--rows", str(ROWS),
        "--font-size", str(font_size),
        "--theme", "dracula",
        "--speed", "1.0",          # realtime
        "--idle-time-limit", "60",  # don't cap idles (max=60s)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  rendered: {mp4_path.name}")


# ---------------------------------------------------------------------------
# 4. ffmpeg concat
# ---------------------------------------------------------------------------

def concat_segments(segments: list[Path], final_mp4: Path) -> None:
    final_mp4.parent.mkdir(parents=True, exist_ok=True)
    if final_mp4.exists():
        final_mp4.unlink()
    list_file = final_mp4.parent / "concat_inputs.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for s in segments:
            safe = str(s.resolve()).replace("'", "'\\''")
            f.write(f"file '{safe}'\n")
    # Re-encode to a uniform stream so concat works across sources from
    # different encoders (Marp h264 vs agg h264). Use a fast preset.
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", str(list_file),
           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
           "-pix_fmt", "yuv420p", "-r", "30", "-s", "1280x720",
           "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
           str(final_mp4)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    list_file.unlink()
    print(f"  final: {final_mp4}")


# ---------------------------------------------------------------------------
# 5. Pipeline
# ---------------------------------------------------------------------------

def main() -> Path:
    # Sanity
    if not Path(AGG_BIN).exists():
        raise RuntimeError(f"agg not found at {AGG_BIN}")

    print("=== 1. Recording real shell sessions (PTY + asciicast v2) ===")
    cast_paths = {}
    for seg in CAST_SEGMENTS:
        out_cast = CAST / f"{seg['name']}.cast"
        record_cast(seg["name"], seg["command"], out_cast)
        cast_paths[seg["name"]] = out_cast

    print("\n=== 2. Rendering .cast to MP4 (agg) ===")
    SEGMENTS.mkdir(parents=True, exist_ok=True)
    rendered_paths = {}
    for name, cast_path in cast_paths.items():
        mp4_path = SEGMENTS / f"{name}.mp4"
        render_cast(cast_path, mp4_path)
        rendered_paths[name] = mp4_path

    print("\n=== 3. Rendering slide segments (Marp) ===")
    slide_paths = render_slides()
    # Title slide: 3s, closing slide: 5s
    slide_mp4s = {
        "01_title": SEGMENTS / "01_title.mp4",
        "07_closing": SEGMENTS / "07_closing.mp4",
    }
    image_to_mp4(slide_paths["01_title"], slide_mp4s["01_title"], 3.0)
    image_to_mp4(slide_paths["07_closing"], slide_mp4s["07_closing"], 5.0)

    print("\n=== 4. Concatenating final video ===")
    final_mp4 = FINAL / "latentcode_demo.mp4"
    order = [
        slide_mp4s["01_title"],
        rendered_paths["02_pytest"],
        rendered_paths["03_scan"],
        rendered_paths["04_queue"],
        rendered_paths["05_eval"],
        rendered_paths["06_regress"],
        slide_mp4s["07_closing"],
    ]
    concat_segments(order, final_mp4)

    size_mb = final_mp4.stat().st_size / (1024 * 1024)
    print(f"\n✓ Done. {final_mp4} ({size_mb:.2f} MB)")
    return final_mp4


if __name__ == "__main__":
    main()