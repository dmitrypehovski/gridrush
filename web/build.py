#!/usr/bin/env python3
"""Build the single-file GRIDRUSH dashboard.

Reads a results JSON (CONTRACT.md §5 schema), injects it into web/template.html
as ``window.RUN_DATA = {...}`` and writes ``web/dashboard.html``.

Everything stays local: no network, no CDN, no external fonts or libraries —
the output is a self-contained HTML file that opens from file://.

Usage (from the gridrush repo root):
    python3 web/build.py                         # ../results/loop.json
    python3 web/build.py results/loop.json
    python3 web/build.py ../results/sim_baseline.json -o web/dashboard.html
    python3 web/build.py web/sample_run.json     # offline fallback sample

Exit codes: 0 ok, 2 bad arguments / missing files, 3 invalid JSON or template.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../gridrush/web
ROOT = HERE.parent                              # .../gridrush

TOKEN = "/*__RUN_DATA__*/ null"
DEFAULT_JSON = ROOT / "results" / "loop.json"
DEFAULT_TEMPLATE = HERE / "template.html"
DEFAULT_OUT = HERE / "dashboard.html"

# Ключи, которые дашборд умеет показать. Отсутствие — предупреждение, не ошибка:
# каждый блок рендерится с плейсхолдером.
EXPECTED = ["meta", "sites", "grid", "baselines", "iterations", "best", "comparison"]


def die(msg: str, code: int = 2) -> "NoReturn":
    print(f"build.py: error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def resolve(path_str: str, kind: str = "JSON") -> Path:
    """Resolve a CLI path relative to CWD; fall back to the repo root / web dir."""
    p = Path(path_str).expanduser()
    if p.is_file():
        return p
    if not p.is_absolute():
        for base in (ROOT, HERE):
            cand = base / path_str
            if cand.is_file():
                return cand
    die(f"{kind} file not found: {path_str}")


def load_json(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        die(f"{path} is not valid JSON: {e}", 3)
    if not isinstance(data, dict):
        die(f"{path}: expected a JSON object at the top level", 3)
    return data


def validate(data: dict, verbose: bool = True) -> list[str]:
    """Cheap schema sanity check; returns human-readable warnings."""
    warnings: list[str] = []
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    sites = data.get("sites") if isinstance(data.get("sites"), list) else []
    iterations = data.get("iterations") if isinstance(data.get("iterations"), list) else []
    best = data.get("best") if isinstance(data.get("best"), dict) else {}
    comparison = data.get("comparison") if isinstance(data.get("comparison"), dict) else {}
    baselines = data.get("baselines") if isinstance(data.get("baselines"), dict) else {}
    stress = ((data.get("grid") or {}).get("stress_day")) if isinstance(data.get("grid"), dict) else None

    if not meta.get("region"):
        warnings.append("meta.region missing — header will fall back to placeholders")
    if not sites:
        warnings.append("sites[] is empty — the map will show a placeholder")
    if len(iterations) < 2:
        warnings.append("iterations[] has fewer than 2 scored entries — learning curve unavailable")
    if not best.get("sites"):
        warnings.append("best.sites[] missing — map tooltips / per-site SLA view will be empty")
    if not (best.get("monthly_mw") or best.get("monthly_mw_by_mode")):
        warnings.append("best.monthly_mw / monthly_mw_by_mode missing — MW-by-month chart unavailable")
    if not baselines:
        warnings.append("baselines{} is empty — baseline toggle unavailable")
    if not isinstance(stress, dict) or not stress:
        warnings.append("grid.stress_day missing — worst-day chart unavailable")
    if not comparison:
        warnings.append("comparison{} is empty — KPI cards fall back to best{}")
    return warnings


def inject(template: str, data: dict) -> str:
    if TOKEN not in template:
        die("template is missing the /*__RUN_DATA__*/ null injection token", 3)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # безопасная вставка в <script>: не даём данным закрыть тег и не ломаем JS-парсер
    payload = payload.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return template.replace(TOKEN, payload, 1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Inject a GRIDRUSH results JSON into the offline dashboard template.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("json", nargs="?", default=str(DEFAULT_JSON),
                    help="path to results JSON (default: ../results/loop.json)")
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT), help="output HTML (default: web/dashboard.html)")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="dashboard template")
    ap.add_argument("-q", "--quiet", action="store_true", help="only print the output path")
    args = ap.parse_args(argv)

    json_path = resolve(args.json)
    template_path = resolve(args.template, "template")
    out_path = Path(args.out).expanduser()
    if not out_path.is_absolute():
        out_path = (ROOT / out_path) if not out_path.parent.exists() else out_path
        if not out_path.is_absolute():
            out_path = Path.cwd() / out_path

    data = load_json(json_path)
    warnings = validate(data)
    template = template_path.read_text(encoding="utf-8")
    html = inject(template, data)

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
    except OSError as e:
        die(f"cannot write {out_path}: {e}")

    if args.quiet:
        print(out_path)
        return 0

    size_kb = out_path.stat().st_size / 1024
    meta = data.get("meta") or {}
    sites = data.get("sites") or []
    iters = data.get("iterations") or []
    stress = ((data.get("grid") or {}).get("stress_day") or {})
    print(f"GRIDRUSH dashboard built: {out_path}")
    print(f"  source     : {json_path}")
    print(f"  region     : {meta.get('region', '?')} {meta.get('region_name', '')}".rstrip())
    print(f"  payload    : {len(sites)} sites, {len(iters)} iterations, "
          f"{len((data.get('best') or {}).get('sites') or [])} energized sites")
    if stress:
        print(f"  stress day : {stress.get('date', '?')} ({len(stress.get('demand_mw') or stress.get('demand_index') or [])} h)")
    print(f"  output     : {size_kb:.0f} KB single file (offline, no CDN)")
    for w in warnings:
        print(f"  warning    : {w}")
    if warnings:
        print("  (dashboard will show placeholders for the missing pieces instead of failing)")
    print("  open with  : open web/dashboard.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
