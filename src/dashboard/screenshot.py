"""Capture dashboard screenshots headlessly (for the Notion writeup).

Boots `streamlit run` in a subprocess, loads it in headless Chromium via Playwright, waits for the
charts to render, and writes PNGs to docs/screenshots/.

Run:  python -m src.dashboard.screenshot --db data/dq.db
"""
from __future__ import annotations
import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("docs/screenshots")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def capture(db: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "src/dashboard/app.py",
         "--server.headless", "true", "--server.port", str(port),
         "--browser.gatherUsageStats", "false", "--", "--db", db],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        url = f"http://localhost:{port}/"
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            # tall viewport: Streamlit scrolls an inner container, so full_page misses content
            # below the fold — size the viewport to fit all four panels instead.
            page = browser.new_page(viewport={"width": 1440, "height": 1600},
                                    device_scale_factor=2)
            # retry until the server is up
            for _ in range(30):
                try:
                    page.goto(url, wait_until="networkidle", timeout=4000)
                    break
                except Exception:
                    time.sleep(1)
            # let Streamlit run the script + render Vega charts
            page.wait_for_timeout(6000)
            page.wait_for_selector("text=News-Events Data Quality", timeout=15000)

            page.screenshot(path=str(OUT / "dashboard_full.png"))
            # crop the two halves for crisp section shots in the writeup
            full = OUT / "dashboard_full.png"
            from PIL import Image
            im = Image.open(full)
            w, h = im.size
            im.crop((0, 0, w, int(h * 0.52))).save(OUT / "dashboard_top.png")
            im.crop((0, int(h * 0.48), w, h)).save(OUT / "dashboard_bottom.png")
            browser.close()
        print(f"wrote {OUT}/dashboard_full.png, dashboard_top.png, dashboard_bottom.png")
    finally:
        proc.terminate()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/dq.db")
    args = ap.parse_args()
    capture(args.db)
