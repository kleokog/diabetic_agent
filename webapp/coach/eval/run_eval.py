#!/usr/bin/env python3
"""Score day-coach findings against golden_days.json.

Usage (from repo root):
  PYTHONPATH=. python -m webapp.coach.eval.run_eval              # context checks only
  PYTHONPATH=. python -m webapp.coach.eval.run_eval --live       # call OpenAI + score
  PYTHONPATH=. python -m webapp.coach.eval.run_eval --date 2026-10-20 --live
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from webapp.coach import context, llm, service
from webapp.db import DEFAULT_DB_PATH, connect

GOLDEN_PATH = Path(__file__).with_name("golden_days.json")


def _load_golden() -> dict[str, Any]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def _blob(findings: list[dict[str, Any]]) -> str:
    parts = []
    for f in findings:
        parts.extend(
            [
                f.get("title") or "",
                f.get("insight") or "",
                f.get("why_it_matters") or "",
                f.get("try_text") or "",
            ]
        )
    return " ".join(parts).lower()


def _mentions(blob: str, needles: list[str]) -> bool:
    return any(n.lower() in blob for n in needles)


def _mentions_any_regex(blob: str, patterns: list[str]) -> list[str]:
    hit = []
    for p in patterns:
        if re.search(p, blob, re.I):
            hit.append(p)
    return hit


def score_case(
    case: dict[str, Any],
    findings: list[dict[str, Any]],
    pack: dict[str, Any],
) -> dict[str, Any]:
    expect = case.get("expect") or {}
    blob = _blob(findings)
    checks: list[dict[str, Any]] = []
    failed = 0

    def add(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failed
        checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            failed += 1

    max_f = expect.get("max_findings")
    if max_f is not None:
        add("max_findings", len(findings) <= int(max_f), f"{len(findings)} findings")

    if expect.get("expected_diverse_sections") and findings:
        sections = {f.get("section") for f in findings}
        add(
            "diverse_sections",
            sections != {"food"},
            f"sections={sorted(sections)}",
        )

    preferred = expect.get("preferred_sections_any") or []
    if preferred and findings:
        sections = {f.get("section") for f in findings}
        add(
            "preferred_section",
            bool(sections & set(preferred)),
            f"have={sorted(sections)} want_any={preferred}",
        )

    must_any = expect.get("must_mention_any") or []
    if must_any:
        add("must_mention_any", _mentions(blob, must_any), f"need any of {must_any}")

    for phrase in expect.get("must_not_mention") or []:
        add(f"must_not:{phrase[:40]}", phrase.lower() not in blob, phrase)

    # Assessment respect: don't "fix" well_managed meals in try_text
    windows = {
        (w.get("label") or "").lower(): w
        for w in (pack.get("examples") or {}).get("meal_glucose_windows") or []
    }
    for label in expect.get("should_not_fix_meals") or []:
        w = windows.get(label.lower())
        if not w or w.get("assessment") != "well_managed":
            continue
        # Heuristic: try_text naming that meal + change/adjust/bolus/carb
        bad = False
        for f in findings:
            try_text = (f.get("try_text") or "").lower()
            if label.lower() in try_text and re.search(
                r"\b(adjust|increase|decrease|change|bolus|carb|earlier|later)\b",
                try_text,
            ):
                bad = True
                break
        add(f"no_fix:{label}", not bad, "try_text looks like a meal experiment")

    for label in expect.get("must_not_blame_meals") or []:
        w = windows.get(label.lower())
        assess = (w or {}).get("assessment")
        if assess not in {"started_high", "started_low", "well_managed"}:
            continue
        blamed = False
        for f in findings:
            text = f"{f.get('title')} {f.get('insight')} {f.get('try_text')}".lower()
            if label.lower() in text and re.search(
                r"\b(insufficient|too little|increase.*(dose|units)|dinner insulin|meal (was|is) (the )?problem)\b",
                text,
            ):
                blamed = True
                break
        add(f"no_blame:{label}", not blamed, f"assessment={assess}")

    return {
        "id": case["id"],
        "date": case["date"],
        "pass": failed == 0,
        "failed": failed,
        "findings_n": len(findings),
        "checks": checks,
    }


def context_sanity(case: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    """Cheap checks that the day pack still matches the archetype (no LLM)."""
    windows = (pack.get("examples") or {}).get("meal_glucose_windows") or []
    arcs = (pack.get("examples") or {}).get("event_arcs") or []
    by_label = {(w.get("label") or ""): w.get("assessment") for w in windows}
    issues = []
    cid = case["id"]
    if cid == "rebound_not_dinner":
        if by_label.get("Dinner") != "started_high":
            issues.append(f"Dinner assessment={by_label.get('Dinner')} expected started_high")
        if by_label.get("Breakfast") != "well_managed":
            issues.append(f"Breakfast assessment={by_label.get('Breakfast')}")
        if not any(a.get("kind") == "bolus_while_low" for a in arcs):
            issues.append("missing bolus_while_low arc")
    if cid == "weekend_breakfast_spike_and_hypo_dinner":
        if by_label.get("Breakfast") != "post_meal_high":
            issues.append(f"Breakfast assessment={by_label.get('Breakfast')}")
        if by_label.get("Dinner") != "started_low":
            issues.append(f"Dinner assessment={by_label.get('Dinner')} expected started_low")
    if cid == "true_lunch_spike":
        if by_label.get("Lunch") != "post_meal_high":
            issues.append(f"Lunch assessment={by_label.get('Lunch')}")
    return {"id": case["id"], "ok": not issues, "issues": issues, "assessments": by_label}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate day coach against golden days")
    parser.add_argument("--live", action="store_true", help="Call OpenAI for each case")
    parser.add_argument("--date", help="Only run this YYYY-MM-DD case")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args(argv)

    golden = _load_golden()
    cases = golden["days"]
    if args.date:
        cases = [c for c in cases if c["date"] == args.date]
        if not cases:
            print(f"No golden case for {args.date}", file=sys.stderr)
            return 2

    print("Principles:")
    for p in golden.get("principles") or []:
        print(f"  • {p}")
    print()

    conn = connect(args.db)
    context_fails = 0
    live_fails = 0

    for case in cases:
        day = date.fromisoformat(case["date"])
        pack = context.build_day_context_pack(conn, day)
        sanity = context_sanity(case, pack)
        status = "OK" if sanity["ok"] else "FAIL"
        if not sanity["ok"]:
            context_fails += 1
        print(f"[context] {status} {case['id']} ({case['date']}) {sanity['assessments']}")
        for issue in sanity["issues"]:
            print(f"          - {issue}")

        if not args.live:
            continue

        if not llm.api_key_configured():
            print("OPENAI_API_KEY not set; cannot --live", file=sys.stderr)
            return 2
        try:
            raw = llm.generate_day_findings(pack)
            findings = service.validate_findings(raw, coverage=pack.get("coverage") or {})
            findings = findings[:6]
        except Exception as exc:  # noqa: BLE001
            print(f"[live] ERROR {case['id']}: {exc}")
            live_fails += 1
            continue

        result = score_case(case, findings, pack)
        status = "PASS" if result["pass"] else "FAIL"
        if not result["pass"]:
            live_fails += 1
        print(f"[live] {status} {case['id']} findings={result['findings_n']}")
        for check in result["checks"]:
            mark = "✓" if check["ok"] else "✗"
            print(f"       {mark} {check['name']}" + (f" — {check['detail']}" if check["detail"] else ""))
        print("       titles:", [f.get("title") for f in findings])
        print()

    print(
        f"Done. context_fails={context_fails}"
        + (f" live_fails={live_fails}" if args.live else " (context-only; pass --live to call the model)")
    )
    return 1 if context_fails or live_fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
