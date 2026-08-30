"""Generate the title + closing card videos for the demo.

Output:
  scripts/build/cards/01_title.mp4    (5s, 1280x720, 30fps)
  scripts/build/cards/02_closing.mp4  (6s, 1280x720, 30fps)

We render HTML directly with Playwright (no Marp) so we have full control
over the dark amber aesthetic. Marp's `gaia` theme kept overriding the
background, so the cards came out cream-colored.
"""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent
CARDS = REPO / "scripts" / "build" / "cards"
CARDS.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 1. HTML pages
# ---------------------------------------------------------------------------

TITLE_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { width: 1280px; height: 720px; overflow: hidden; }
  body {
    background: #1c1814;     /* warm near-black, matching the dashboard */
    color: #f5efe6;
    font-family: 'Geist', 'Inter Tight', 'Helvetica Neue', system-ui, -apple-system, sans-serif;
    -webkit-font-smoothing: antialiased;
    padding: 80px 96px;
    display: flex; flex-direction: column; justify-content: center;
    position: relative;
  }
  /* Top-right "v0.3 · dev" tag */
  .tag {
    position: absolute; top: 32px; right: 40px;
    font-family: 'JetBrains Mono', 'SF Mono', monospace;
    font-size: 12px; letter-spacing: 0.1em; text-transform: uppercase;
    color: #6f6256;
  }
  /* Brand mark — inset square with the amber "ember" pixel */
  .brand {
    width: 56px; height: 56px; border-radius: 8px;
    background: #14110d;
    border: 1px solid #3a322a;
    position: relative; margin-bottom: 32px;
  }
  .brand::after {
    content: ''; position: absolute;
    top: 16px; left: 16px; right: 16px; bottom: 16px;
    border-radius: 2px;
    background: #d99a4a;       /* the "latent ember" amber */
  }
  h1 {
    font-size: 96px; font-weight: 600; letter-spacing: -0.04em;
    line-height: 1; color: #f5efe6;
  }
  .tagline {
    font-size: 24px; color: #b8a99a; font-weight: 400;
    margin-top: 24px; line-height: 1.5; max-width: 720px;
  }
  .url {
    font-family: 'JetBrains Mono', 'SF Mono', monospace;
    font-size: 22px; color: #d99a4a;
    margin-top: 32px; letter-spacing: -0.01em;
  }
  .meta {
    position: absolute; bottom: 40px; left: 96px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px; color: #6f6256;
    letter-spacing: 0.1em; text-transform: uppercase;
  }
</style>
</head>
<body>
  <div class="tag">v0.3 · dev</div>
  <div class="brand"></div>
  <h1>LatentCode</h1>
  <div class="tagline">AI-powered analyzer that finds hidden defects in software projects</div>
  <div class="url">github.com/Hemanthdamineni/latentcode</div>
  <div class="meta">BuildSprint 2026</div>
</body></html>
"""


CLOSING_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { width: 1280px; height: 720px; overflow: hidden; }
  body {
    background: #1c1814;
    color: #f5efe6;
    font-family: 'Geist', 'Inter Tight', 'Helvetica Neue', system-ui, -apple-system, sans-serif;
    -webkit-font-smoothing: antialiased;
    padding: 80px 96px;
    display: flex; flex-direction: column; justify-content: center;
    align-items: center; text-align: center;
    position: relative;
  }
  .tag {
    position: absolute; top: 32px; right: 40px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px; letter-spacing: 0.1em; text-transform: uppercase;
    color: #6f6256;
  }
  h2 {
    font-size: 64px; font-weight: 600; letter-spacing: -0.02em;
    line-height: 1.1; color: #f5efe6;
  }
  h2 .accent { color: #d99a4a; }
  .url {
    font-family: 'JetBrains Mono', 'SF Mono', monospace;
    font-size: 24px; color: #d99a4a;
    margin-top: 32px; letter-spacing: -0.01em;
  }
  .pills {
    display: flex; gap: 12px; justify-content: center;
    margin: 32px 0 24px 0;
  }
  .pills span {
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px; color: #b8a99a;
    border: 1px solid #3a322a;
    background: #14110d;
    padding: 8px 18px;
    border-radius: 999px;
    letter-spacing: 0.04em;
  }
  .stats {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px; color: #6f6256;
    letter-spacing: 0.1em; text-transform: uppercase;
  }
  .bottom {
    position: absolute; bottom: 32px; left: 0; right: 0;
    text-align: center;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px; color: #6f6256; letter-spacing: 0.12em;
  }
</style>
</head>
<body>
  <div class="tag">v0.3 · dev</div>
  <h2>Five <span class="accent">interfaces</span>.<br>One <span class="accent">pipeline</span>.</h2>
  <div class="url">github.com/Hemanthdamineni/latentcode</div>
  <div class="pills">
    <span>CLI</span><span>MCP</span><span>Skill</span><span>Hook</span><span>Web</span>
  </div>
  <div class="stats">17 tests · 3-class eval harness · sectioned before/after report</div>
  <div class="bottom">BuildSprint 2026</div>
</body></html>
"""


def render_html_to_png(html: str, png_path: Path) -> None:
    """Render HTML at 1280x720 to a PNG via headless Chromium."""
    html_path = png_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        ctx = browser.new_context(viewport={"width": 1280, "height": 720},
                                  device_scale_factor=1)
        page = ctx.new_page()
        page.goto(f"file://{html_path}", wait_until="networkidle")
        page.wait_for_timeout(500)
        page.screenshot(path=str(png_path), full_page=False)
        browser.close()
    print(f"  png: {png_path.name}  ({png_path.stat().st_size // 1024} KB)")


# ---------------------------------------------------------------------------
# 2. Convert PNG to silent MP4
# ---------------------------------------------------------------------------

def silent_wav(out_path: Path, seconds: float) -> None:
    sr = 44100
    n = int(seconds * sr)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(b"\x00\x00" * n * 2)


def image_to_mp4(image: Path, mp4: Path, duration_s: float) -> None:
    silent = mp4.with_suffix(".silent.wav")
    silent_wav(silent, duration_s)
    cmd = ["ffmpeg", "-y",
           "-loop", "1", "-framerate", "30",
           "-i", str(image),
           "-i", str(silent),
           "-c:v", "libx264", "-t", f"{duration_s:.3f}",
           "-profile:v", "high", "-level", "4.0",
           "-pix_fmt", "yuv420p", "-r", "30", "-s", "1280x720",
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
           "-shortest",
           "-movflags", "+faststart",
           str(mp4)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    silent.unlink()
    print(f"  mp4: {mp4.name}  ({mp4.stat().st_size // 1024} KB, {duration_s}s)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== 1. Rendering cards (HTML → PNG via Playwright) ===")
    title_png = CARDS / "01_title.png"
    closing_png = CARDS / "02_closing.png"
    render_html_to_png(TITLE_HTML, title_png)
    render_html_to_png(CLOSING_HTML, closing_png)

    print("\n=== 2. Building MP4 cards (PNG → silent MP4) ===")
    image_to_mp4(title_png, CARDS / "01_title.mp4", 5.0)
    image_to_mp4(closing_png, CARDS / "02_closing.mp4", 6.0)

    print(f"\n✓ Done. Cards at: {CARDS}/")
    for p in sorted(CARDS.glob("*.mp4")):
        size_kb = p.stat().st_size // 1024
        print(f"   {p.name}  {size_kb} KB")


if __name__ == "__main__":
    main()