"""OpenAI call that returns ranked coach findings as JSON."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

PROMPT_VERSION = "coach-v3"
DAY_PROMPT_VERSION = "coach-day-v3"
DEFAULT_MODEL = "gpt-4o-mini"
MANUAL_PATH = Path(__file__).with_name("manual_t1_mgdl.md")

SYSTEM_PROMPT_CORE = """You are a diabetes coach for a person managing Type 1 diabetes with CGM data (and optional food, sleep, activity imports).

Your job: propose ranked FINDING CARDS from the structured context pack for THIS analysis window only, grounded in the Type 1 management manual (mg/dL) below.

Hard rules:
1. Never invent metrics, dates, times, meals, workouts, or episodes. Only use what is in the context pack, especially context.examples.
2. Every insight MUST name at least one concrete example from context.examples (date + time and/or values), e.g. "On 12 Oct at 03:15 glucose fell to 58 mg/dL" or "After dinner on 9 Oct (pizza, 19:30) peak 230 mg/dL at ~21:30". Put those dates in evidence.days.
3. Respect coverage: if food/sleep/activity/glucose is sparse or missing, say so and lower confidence. Do not treat missing days as zeros.
4. The coach_brief (if present) is a hard constraint — never contradict it.
5. Do not recommend specific insulin unit dose changes unless carb_ratio / correction_factor are present AND evidence is clear. Prefer timing, carbs, snacks, checks, sleep, or training adjustments. Never tell them to omit basal insulin.
6. Safety first (time below 70 / 54, severe highs ≥250). Then high-impact patterns (TIR 70–180, CV ≤36), then lifestyle links.
7. Prefer recurring patterns supported by multiple dated examples over one-offs.
8. try_text must be a SPECIFIC next action for THIS week — not vague advice like "monitor more" or "be careful with carbs". Good tries name what to change/check, when, and how to judge success (e.g. "For the next 3 dinners that look like your 9 Oct meal, bolus 15 minutes earlier and write the 2-hour reading; compare to the 230 mg/dL spike"). Bad tries: "Improve bolus timing", "Watch overnight lows".
9. Prefer 5–8 findings. Rank: safety first, then highest score.
10. Write in plain English using mg/dL. Be direct. Do not paste the manual into findings.

Return JSON ONLY with this shape:
{
  "findings": [
    {
      "section": "safety|glucose|food|sleep|activity|insulin",
      "title": "short headline",
      "insight": "pattern + at least one dated example with values/times from context.examples",
      "why_it_matters": "why that matters for TIR, hypos, variability, or delayed effects",
      "try_text": "one specific, time-bound next step the user can do this week",
      "confidence": "high|medium|low",
      "score": 0-100,
      "evidence": { "metrics": ["..."], "days": ["YYYY-MM-DD"], "notes": "short pointer to the cited episodes" },
      "data_used": ["glucose","food","sleep","activity","insulin"]
    }
  ]
}
"""


@lru_cache(maxsize=1)
def load_manual() -> str:
    return MANUAL_PATH.read_text(encoding="utf-8")


def system_prompt() -> str:
    return (
        SYSTEM_PROMPT_CORE
        + "\n\n--- TYPE 1 DIABETES MANAGEMENT MANUAL (mg/dL) ---\n\n"
        + load_manual()
    )


def api_key_configured() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def model_name() -> str:
    return os.environ.get("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty model response")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        return json.loads(fence.group(1).strip())
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("Model response was not valid JSON")


DAY_SYSTEM_PROMPT_CORE = """You are a diabetes coach reviewing ONE calendar day of Type 1 diabetes data (mg/dL).

This is a WHOLE-DAY review — not a meal-by-meal report card. Meals matter when they drive disruption, but hypos, near-lows, corrections, rebound highs, overnight, exercise, and inter-meal insulin often matter more.

Priorities (in order):
1. Safety: lows (<70), very highs (≥250), rapid bolus while glucose is already low/near-low (see insulin_with_glucose.bolus_while_low and event_arcs).
2. Causal chains in event_arcs (e.g. near-low → likely treatment/correction → rebound high). Prefer these over blaming the next meal.
3. True post-meal problems ONLY when meal_glucose_windows.assessment is "post_meal_high" (in-range pre-meal, then a clear meal-driven spike).
4. What went well: if assessment is "well_managed", do NOT invent an improvement experiment for that meal. At most one short positive card covering well-managed meals together.
5. Overnight, sleep, and workouts when those examples exist.
6. Diversify sections (safety / glucose / insulin / food / activity / sleep). Never return three near-identical Food cards for breakfast/lunch/dinner.

Meal assessment meanings (do not ignore):
- well_managed: in-range response — success, not a finding that needs fixing.
- started_low: pre-meal was already <70 — this is hypo recovery context, not a "successful meal dose". Prefer safety guidance over meal praise.
- started_high: pre-meal glucose was already above target — the high is NOT caused by that meal/insulin. Explain the prior arc (soft_lows, low_episodes, bolus_while_low, event_arcs).
- post_meal_high: genuine meal-driven spike from an in-range start — fair to critique food/bolus timing.
- mild_overshoot / moderate_rise: minor; only mention if part of a larger pattern.

Hard rules:
1. Never invent times, meals, workouts, carbs, or glucose values. Only use the day context pack.
2. Every insight must cite at least one concrete time + mg/dL from examples (event_arcs, lows, soft_lows, highs, insulin_with_glucose, meal windows, overnight, workouts).
3. If meals.source is "estimated", times come from schedule + that day's rapid boluses; carbs unknown; lower confidence for carb-dose claims.
4. If meals.source is "scheduled", times are Settings only; lower confidence.
5. If meals.source is "logged", use logged times/carbs when present.
6. Snacks only if logged — do not invent snacks. You MAY say a rebound high is consistent with hypo treatment carbs even if snacks were not logged, when event_arcs show low_then_high / bolus_while_low — phrase it as a likely explanation, not a fact.
7. coach_brief is a hard constraint. Do not recommend omitting basal. Avoid specific unit dose changes unless carb_ratio/correction_factor are present and evidence is clear — prefer timing, when to treat lows gently, when NOT to bolus, checks, and what to record.
8. try_text must be a SPECIFIC next action for a similar situation (name the time-of-day pattern and how to judge success). Bad tries: "check glucose 1 hour after breakfast", "monitor more", "be careful". Good tries fix the real problem (e.g. "Next time glucose is ~75–85 mid-afternoon, skip or sharply reduce correction bolus and treat only if <70; aim to avoid the climb past 200 before dinner").
9. Prefer 2–5 findings. Skip filler. Safety and causal chains first.
10. Write in plain English using mg/dL.

Return JSON ONLY:
{
  "findings": [
    {
      "section": "safety|glucose|food|sleep|activity|insulin",
      "title": "short headline",
      "insight": "what happened this day with times and values",
      "why_it_matters": "why it matters",
      "try_text": "one specific next-step action",
      "confidence": "high|medium|low",
      "score": 0-100,
      "evidence": { "metrics": ["..."], "days": ["YYYY-MM-DD"], "notes": "..." },
      "data_used": ["glucose","food","sleep","activity","insulin"]
    }
  ]
}
"""


def day_system_prompt() -> str:
    return (
        DAY_SYSTEM_PROMPT_CORE
        + "\n\n--- TYPE 1 DIABETES MANAGEMENT MANUAL (mg/dL) ---\n\n"
        + load_manual()
    )


def _call_findings(system: str, user_content: str) -> list[dict[str, Any]]:
    if not api_key_configured():
        raise RuntimeError("OPENAI_API_KEY is not set")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is not installed") from exc

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip())
    response = client.chat.completions.create(
        model=model_name(),
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    )
    content = response.choices[0].message.content or ""
    payload = _extract_json(content)
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise ValueError("Model JSON missing a findings array")
    return findings


def generate_findings(context_pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Call OpenAI and return raw finding dicts for a multi-day window."""
    user_content = (
        "Context pack (JSON). Produce ranked finding cards grounded in the manual.\n\n"
        + json.dumps(context_pack, ensure_ascii=False, separators=(",", ":"))
    )
    return _call_findings(system_prompt(), user_content)


def generate_day_findings(context_pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Call OpenAI for a balanced single-day review (safety + arcs + selective meals)."""
    user_content = (
        "Single-day context pack (JSON). Produce a balanced day review — prioritise "
        "event_arcs / safety / rebound highs; only critique meals with assessment "
        "post_meal_high; do not invent tries for well_managed meals; diversify sections.\n\n"
        + json.dumps(context_pack, ensure_ascii=False, separators=(",", ":"))
    )
    return _call_findings(day_system_prompt(), user_content)
