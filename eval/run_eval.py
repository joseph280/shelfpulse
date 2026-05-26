"""eval/run_eval.py - End-to-end evaluation harness for ShelfPulse.

Hits the running /ask endpoint with 10 canned questions and grades
the response against expected facts. Uses simple substring and
structural checks rather than LLM-as-judge: faster, deterministic,
and adequate for a target of 6/10 pass.

Run with the API server running:
    uv run python eval/run_eval.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx


API_URL = "http://localhost:8000/ask"
QUESTIONS_PATH = Path(__file__).parent / "questions.jsonl"
REQUEST_TIMEOUT = 90.0


def load_questions() -> list[dict[str, Any]]:
    with QUESTIONS_PATH.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def grade_response(
    response: dict[str, Any], expected: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Return (passed, list_of_failures)."""
    failures: list[str] = []

    # Refusal expected
    if expected.get("is_refusal"):
        if "insight" in response:
            failures.append("expected refusal, got full response")
            return (False, failures)
        actual_reason = response.get("reason")
        expected_reason = expected.get("expected_reason")
        if expected_reason and actual_reason != expected_reason:
            failures.append(
                f"reason mismatch: expected {expected_reason}, got {actual_reason}"
            )
        return (not failures, failures)

    # Full response expected
    if "insight" not in response:
        failures.append("expected full response, got refusal or error")
        return (False, failures)

    insight = response["insight"]
    action_plan = response.get("action_plan", {})
    actions = action_plan.get("actions", [])

    # Category keyword in summary
    cat = expected.get("category_keyword")
    if cat and cat.lower() not in insight["summary"].lower():
        failures.append(f"category '{cat}' not in summary")

    # Action presence
    if expected.get("expects_actions") and not actions:
        failures.append("expected actions, got none")

    # Evidence count
    min_ev = expected.get("min_evidence")
    if min_ev is not None and len(insight.get("evidence", [])) < min_ev:
        failures.append(
            f"evidence count {len(insight.get('evidence', []))} < {min_ev}"
        )

    # Substring keyword check
    needles = expected.get("must_contain_one_of") or []
    if needles:
        blob = insight["summary"] + " " + " ".join(
            a.get("description", "") for a in actions
        )
        if not any(n.lower() in blob.lower() for n in needles):
            failures.append(
                f"none of {needles} found in summary or action descriptions"
            )

    # Lever check
    levers = expected.get("expected_lever_one_of")
    if levers:
        seen_levers = {a.get("lever") for a in actions}
        if not seen_levers.intersection(levers):
            failures.append(
                f"none of expected levers {levers} found in actions; got {sorted(seen_levers)}"
            )

    return (not failures, failures)


def run_one(client: httpx.Client, q: dict[str, Any]) -> dict[str, Any]:
    start = time.time()
    try:
        r = client.post(
            API_URL,
            json={"question": q["question"]},
            timeout=REQUEST_TIMEOUT,
        )
        elapsed = time.time() - start
        if r.status_code != 200:
            return {
                "id": q["id"],
                "passed": False,
                "elapsed_s": elapsed,
                "failures": [f"HTTP {r.status_code}: {r.text[:100]}"],
            }
        response = r.json()
        passed, failures = grade_response(response, q["expected"])
        return {
            "id": q["id"],
            "passed": passed,
            "elapsed_s": elapsed,
            "failures": failures,
            "trace_id": response.get("trace_id"),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "id": q["id"],
            "passed": False,
            "elapsed_s": time.time() - start,
            "failures": [f"request error: {type(exc).__name__}: {exc}"],
        }


def main() -> int:
    questions = load_questions()
    print(f"Running {len(questions)} evals against {API_URL}\n")

    results: list[dict[str, Any]] = []
    with httpx.Client() as client:
        for q in questions:
            print(f"  [{q['id']}] {q['question'][:60]}{'...' if len(q['question']) > 60 else ''}")
            res = run_one(client, q)
            results.append(res)
            status = "PASS" if res["passed"] else "FAIL"
            print(f"        {status}  ({res['elapsed_s']:.1f}s)")
            for f in res["failures"]:
                print(f"          - {f}")
            print()

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print("=" * 60)
    print(f"RESULTS: {passed}/{total} passed")
    print("=" * 60)
    print(f"{'id':<5}{'pass':<8}{'time':<10}{'trace_id'}")
    print("-" * 60)
    for r in results:
        pf = "PASS" if r["passed"] else "FAIL"
        tid = r.get("trace_id", "-") or "-"
        print(f"{r['id']:<5}{pf:<8}{r['elapsed_s']:>6.1f}s   {tid}")

    return 0 if passed >= 6 else 1


if __name__ == "__main__":
    sys.exit(main())