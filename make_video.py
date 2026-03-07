"""
WeldWarp Full Feature Demo Video
Captures every page with real data, overlays titles, builds MP4.
"""

import asyncio, subprocess, sys
from pathlib import Path

FRONTEND = "http://localhost:3000"
JOB_ID   = "WLD-0WZI-TY"
SHOTS_DIR = Path("/workspace/screenshots")
VIDEO_PATH = Path("/workspace/weldwarp_demo.mp4")
SHOTS_DIR.mkdir(exist_ok=True)

DEMO_COOKIE = {"name": "ww-demo", "value": "1", "domain": "localhost", "path": "/"}
VIEWPORT    = {"width": 1280, "height": 800}

# Each entry: (filename_stem, url, title, subtitle, scroll_to_bottom, extra_wait_ms)
SCENES = [
    ("01_login",
     f"{FRONTEND}/login",
     "Login Page",
     "NextAuth v5 · Google & GitHub OAuth · JWT session strategy",
     False, 0),

    ("02_upload",
     f"{FRONTEND}/",
     "Upload & Run Pipeline",
     "Drag-and-drop ILI file upload (.xlsx, .xls, .csv) · Job configuration",
     False, 0),

    ("03_jobs",
     f"{FRONTEND}/jobs",
     "Job History",
     "All pipeline runs · Status badges · Auto-refreshes every 5 s",
     False, 500),

    ("04_dashboard_top",
     f"{FRONTEND}/jobs/{JOB_ID}",
     "Results Dashboard — KPI Cards",
     "8 matched · 8 High-confidence · Mean growth 0.57 %WT/yr · 0 ft residual",
     False, 2000),

    ("05_dashboard_charts",
     f"{FRONTEND}/jobs/{JOB_ID}",
     "Results Dashboard — Charts",
     "Match overview bar chart · Confidence distribution · Top severity list",
     True, 2000),

    ("06_matches_table",
     f"{FRONTEND}/jobs/{JOB_ID}/matches",
     "Anomaly Matches Table",
     "Paginated · Sortable by any column · Filter by confidence & feature type",
     False, 2000),

    ("07_matches_detail",
     f"{FRONTEND}/jobs/{JOB_ID}/matches",
     "Match Detail Panel",
     "Click any row to expand: Δ-dist, Δ-clock, depth A→B, match probability",
     True, 1000),

    ("08_growth_chart",
     f"{FRONTEND}/jobs/{JOB_ID}/growth",
     "Growth Trends Chart",
     "Recharts area chart · Avg & max growth rate + severity along odometer",
     False, 2000),

    ("09_risk_segments",
     f"{FRONTEND}/jobs/{JOB_ID}/growth",
     "Risk Segments",
     "HIGH / MEDIUM / LOW color-coded severity list with remaining-life estimates",
     True, 1000),

    ("10_settings",
     f"{FRONTEND}/settings",
     "Settings & Admin Panel",
     "User profile · Role display · Admin role-preview · User management table",
     False, 500),
]


async def take_screenshots():
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport=VIEWPORT)
        await ctx.add_cookies([DEMO_COOKIE])

        page = await ctx.new_page()

        for scene in SCENES:
            stem, url, title, subtitle, scroll, extra_ms = scene
            print(f"  → {title}")
            await page.goto(url, wait_until="networkidle", timeout=25000)
            await page.wait_for_timeout(2000 + extra_ms)

            if scroll:
                await page.evaluate("window.scrollBy(0, 400)")
                await page.wait_for_timeout(600)

            path = SHOTS_DIR / f"{stem}.png"
            await page.screenshot(path=str(path), full_page=False)
            print(f"    saved {path.name}  ({path.stat().st_size:,} bytes)")

        await browser.close()


print("Capturing screenshots…")
asyncio.run(take_screenshots())
print("✓ All screenshots done\n")


# ─────────────────────────────────────────────────────────────────────────────
# Build video
# ─────────────────────────────────────────────────────────────────────────────
print("Building video…")

shots = sorted(SHOTS_DIR.glob("*.png"))
DURATION = 5   # seconds each slide holds

# Write ffmpeg concat input file
concat = SHOTS_DIR / "concat.txt"
with open(concat, "w") as f:
    for s in shots:
        f.write(f"file '{s}'\nduration {DURATION}\n")
    f.write(f"file '{shots[-1]}'\n")

# Build a drawtext filter chain — one title+subtitle per slide
def esc(s):
    return s.replace("'", "\u2019").replace(":", "\\:").replace(",", "\\,")

filter_parts = []
for i, shot in enumerate(shots):
    idx   = int(shot.stem.split("_")[0]) - 1
    title   = esc(SCENES[idx][2])
    sub     = esc(SCENES[idx][3])
    t0, t1  = i * DURATION, (i + 1) * DURATION
    H = VIEWPORT["height"]  # 800
    bt = f"between(t,{t0},{t1})"
    filter_parts += [
        # dark banner at bottom (fixed coords)
        f"drawbox=x=0:y={H-80}:w=1280:h=80:color=black@0.72:t=fill:enable='{bt}'",
        # title text
        f"drawtext=text='{title}':fontsize=26:fontcolor=white:x=24:y={H-64}:enable='{bt}'",
        # subtitle text
        f"drawtext=text='{sub}':fontsize=15:fontcolor=#aaaacc:x=24:y={H-32}:enable='{bt}'",
        # slide counter top-right
        f"drawtext=text='{i+1}\\/{len(shots)}':fontsize=14:fontcolor=#888888:x=1224:y=8:enable='{bt}'",
    ]

vf = f"fps=25,scale={VIEWPORT['width']}:{VIEWPORT['height']}," + ",".join(filter_parts)

cmd = [
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0", "-i", str(concat),
    "-vf", vf,
    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
    "-pix_fmt", "yuv420p",
    str(VIDEO_PATH),
]

result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode == 0:
    mb = VIDEO_PATH.stat().st_size / 1024 / 1024
    print(f"✓ Video: {VIDEO_PATH}  ({mb:.1f} MB, ~{len(shots)*DURATION}s)")
else:
    print("ffmpeg error:", result.stderr[-1000:])
    sys.exit(1)
