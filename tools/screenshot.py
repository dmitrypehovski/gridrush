"""Lead tool: headless screenshot for visual QA + demo backup (file://, offline)."""
import subprocess, sys, os, tempfile
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def shot(html, out, w=1600, h=1000, wait_ms=3000):
    url = "file://" + os.path.abspath(html)
    profile = os.path.join(ROOT, ".chrome-profile")
    os.makedirs(profile, exist_ok=True)
    cmd = [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
           f"--user-data-dir={profile}", f"--window-size={w},{h}",
           f"--screenshot={os.path.abspath(out)}", f"--virtual-time-budget={wait_ms}", url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    ok = os.path.exists(out)
    print(("OK " if ok else "FAIL ") + out)
    if not ok:
        print((r.stderr or "")[-1200:])
    return ok
if __name__ == "__main__":
    html = sys.argv[1] if len(sys.argv) > 1 else "web/dashboard.html"
    out = sys.argv[2] if len(sys.argv) > 2 else "web/qa_shot.png"
    shot(html, out)
