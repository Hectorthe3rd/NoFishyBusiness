#!/usr/bin/env python3
"""
eval/eval.py
═══════════════════════════════════════════════════════════════════════════════
High-Coverage Evaluation Runner for NoFishyBusiness
═══════════════════════════════════════════════════════════════════════════════

DESIGN PHILOSOPHY
─────────────────
This runner is built around three ideas:

1. DATA-DRIVEN: All test cases live in test_cases.json. Adding a new feature
    (e.g. a CO2 Calculator) only requires adding entries to the JSON — the
    runner code never needs to change.

2. ASSERTION ENGINE: Instead of one simple keyword check, each test case can
    declare multiple assertion types that are evaluated independently:
        • required_all    — every keyword in the list must appear in the response
        • forbidden_any   — none of these keywords may appear (safety checks)
        • numeric_range   — a numeric field in the JSON must be within [min, max]
        • schema_keys     — the response JSON must contain all listed keys
        • http_status     — the HTTP status code must match the expected value

3. MOCK MODE (default) vs LIVE MODE (--live flag):
    In mock mode the runner still calls the real backend but skips any test
    tagged "llm" — those tests require an actual OpenAI call and cost money.
    Pass --live to run everything including LLM-dependent tests.

USAGE
─────
    # Run all non-LLM tests (free, fast):
    python eval/eval.py

    # Run ALL tests including LLM calls (costs API credits):
    python eval/eval.py --live

    # Point at a different backend:
    python eval/eval.py --backend-url http://localhost:8001

    # Save results to a Markdown report:
    python eval/eval.py --report

EXIT CODES
──────────
    0 — all executed tests passed
    1 — one or more tests failed, or backend unreachable
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse                         # CLI argument parsing
import json                             # JSON serialisation / deserialisation
import os                               # File path helpers
import sys                              # sys.exit()
import time                             # Timestamps for the report
from collections import defaultdict     # Group results by feature area
from datetime import datetime           # User-readable timestamps

import requests                         # HTTP client for calling the backend

# ─────────────────────────────────────────────────────────────────────────────
# Paths & defaults
# ─────────────────────────────────────────────────────────────────────────────

# Directory that contains this script (eval/)
_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_BACKEND_URL = "http://localhost:8000"
TEST_CASES_PATH     = os.path.join(_EVAL_DIR, "test_cases.jsonc")
REPORT_PATH         = os.path.join(_EVAL_DIR, "test_results.md")


# ═════════════════════════════════════════════════════════════════════════════
# ASSERTION ENGINE
# ═════════════════════════════════════════════════════════════════════════════
# Each assertion class receives the full response body (as a dict or string)
# and returns (passed: bool, reason: str).
#
# Design decision: class-based rather than a big if/elif chain so that new
# assertion types can be added without touching the runner loop.
# ═════════════════════════════════════════════════════════════════════════════

class Assertion:
    """Base class — all assertions implement check(body_str, body_json)."""

    def check(self, body_str: str, body_json: dict | None) -> tuple[bool, str]:
        raise NotImplementedError


class RequiredAll(Assertion):
    """
    Every keyword in the list must appear somewhere in the response body.

    Use case: verify that a species response contains 'behavior', 'ph', etc.
    """
    def __init__(self, keywords: list[str]):
        self.keywords = keywords   # List of strings that must all be present

    def check(self, body_str, body_json):
        missing = [kw for kw in self.keywords if kw.lower() not in body_str.lower()]
        if missing:
            return False, f"Required keywords missing: {missing}"
        return True, f"All required keywords found: {self.keywords}"


class ForbiddenAny(Assertion):
    """
    None of the keywords in the list may appear in the response body.

    Use case: safety checks — verify the AI never suggests dangerous actions,
    never hallucinates a fictional species name, never mentions off-topic content.
    """
    def __init__(self, keywords: list[str]):
        self.keywords = keywords   # List of strings that must NOT appear

    def check(self, body_str, body_json):
        found = [kw for kw in self.keywords if kw.lower() in body_str.lower()]
        if found:
            return False, f"Forbidden keywords found in response: {found}"
        return True, f"No forbidden keywords found (good)"


class NumericRange(Assertion):
    """
    A numeric field in the JSON response must fall within [min_val, max_val].

    Use case: volume calculator — verify 14.96 gallons is within ±0.1 of expected.
    The field_path supports dot-notation: "temperature_f.min" navigates nested dicts.
    """
    def __init__(self, field_path: str, min_val: float, max_val: float):
        self.field_path = field_path   # e.g. "volume_gallons" or "temperature_f.min"
        self.min_val    = min_val
        self.max_val    = max_val

    def _get_nested(self, obj: dict, path: str):
        """Navigate a dot-separated path through nested dicts."""
        for key in path.split("."):
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
        return obj

    def check(self, body_str, body_json):
        if body_json is None:
            return False, f"Response is not JSON — cannot check numeric field '{self.field_path}'"
        value = self._get_nested(body_json, self.field_path)
        if value is None:
            return False, f"Field '{self.field_path}' not found in response"
        try:
            num = float(value)
        except (TypeError, ValueError):
            return False, f"Field '{self.field_path}' = {value!r} is not numeric"
        if self.min_val <= num <= self.max_val:
            return True, f"'{self.field_path}' = {num} is within [{self.min_val}, {self.max_val}]"
        return False, f"'{self.field_path}' = {num} is OUTSIDE [{self.min_val}, {self.max_val}]"


class SchemaKeys(Assertion):
    """
    The JSON response must contain all listed top-level keys.

    Use case: species tool — verify the response always has 'behavior',
    'compatible_tank_mates', 'temperature_f', etc.
    """
    def __init__(self, required_keys: list[str]):
        self.required_keys = required_keys

    def check(self, body_str, body_json):
        if body_json is None:
            return False, "Response is not JSON — cannot validate schema"
        missing = [k for k in self.required_keys if k not in body_json]
        if missing:
            return False, f"Schema keys missing from response: {missing}"
        return True, f"All schema keys present: {self.required_keys}"


class HttpStatus(Assertion):
    """
    The HTTP status code must match the expected value.

    Use case: verify that invalid inputs return 422, unknown species return 404, etc.
    """
    def __init__(self, expected_status: int, actual_status: int):
        self.expected = expected_status
        self.actual   = actual_status   # Set by the runner before calling check()

    def check(self, body_str, body_json):
        if self.actual == self.expected:
            return True, f"HTTP status {self.actual} matches expected {self.expected}"
        return False, f"HTTP status {self.actual} != expected {self.expected}"


def build_assertions(case: dict, actual_http_status: int) -> list[Assertion]:
    """
    Read the assertion declarations from a test case dict and instantiate
    the corresponding Assertion objects.

    This is the bridge between the JSON test case format and the class-based
    assertion engine. Adding a new assertion type only requires:
        1. A new Assertion subclass above
        2. A new elif branch here
    The runner loop never changes.
    """
    assertions = []

    # Legacy single-keyword support (backwards compatible with old test cases)
    if "assert_keyword" in case:
        assertions.append(RequiredAll([case["assert_keyword"]]))
    if "assert_absent_keyword" in case:
        assertions.append(ForbiddenAny([case["assert_absent_keyword"]]))

    # New advanced assertion types
    for a in case.get("assertions", []):
        atype = a.get("type")

        if atype == "required_all":
            # Every keyword in the list must appear
            assertions.append(RequiredAll(a["keywords"]))

        elif atype == "forbidden_any":
            # None of these keywords may appear
            assertions.append(ForbiddenAny(a["keywords"]))

        elif atype == "numeric_range":
            # A numeric field must be within [min, max]
            assertions.append(NumericRange(a["field"], a["min"], a["max"]))

        elif atype == "schema_keys":
            # The response JSON must contain all listed keys
            assertions.append(SchemaKeys(a["keys"]))

        elif atype == "http_status":
            # The HTTP status code must match
            assertions.append(HttpStatus(a["expected"], actual_http_status))

        else:
            print(f"    [WARN] Unknown assertion type: {atype!r} — skipped")

    return assertions


# ═════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK & REQUEST DISPATCHER
# ═════════════════════════════════════════════════════════════════════════════

def check_health(backend_url: str) -> bool:
    """
    Ping the backend's /health endpoint to confirm it is running.

    Kept as a module-level function so tests can patch it directly:
        patch("eval.eval.check_health", return_value=False)

    Returns True if the server responds with a 2xx status, False otherwise.
    """
    try:
        resp = requests.get(f"{backend_url}/health", timeout=5)
        return resp.ok
    except requests.RequestException:
        return False


def send_request(backend_url: str, case: dict) -> tuple:
    """
    Send the HTTP request described by a test case and return (response, error).

    Supports:
        • GET  — no body (used for /health)
        • POST with JSON payload (most endpoints)
        • POST with multipart/form-data (image-scan endpoint)

    The test case signals multipart by setting "content_type": "multipart".
    For multipart tests, "input" must be a dict with a "file_path" key pointing
    to a local image file relative to the eval/ directory.

    Returns (None, error_message) on network failure.
    """
    endpoint     = case["endpoint"]
    method       = case.get("method", "POST").upper()
    payload      = case.get("input")
    content_type = case.get("content_type", "json")   # "json" or "multipart"
    url          = f"{backend_url}{endpoint}"

    try:
        if method == "GET":
            return requests.get(url, timeout=30), ""

        elif content_type == "multipart":
            # ── Multipart file upload (image-scan) ────────────────────────
            file_path = payload.get("file_path", "") if payload else ""
            abs_path  = os.path.join(_EVAL_DIR, file_path)

            if not os.path.isfile(abs_path):
                synthetic_jpeg = _make_synthetic_jpeg()
                files = {"file": ("test.jpg", synthetic_jpeg, "image/jpeg")}
            else:
                with open(abs_path, "rb") as f:
                    files = {"file": (os.path.basename(abs_path), f.read(), "image/jpeg")}

            return requests.post(url, files=files, timeout=60), ""

        else:
            # ── Standard JSON POST ────────────────────────────────────────
            return requests.post(url, json=payload, timeout=60), ""

    except requests.RequestException as exc:
        return None, f"Network error: {exc}"


def _make_synthetic_jpeg() -> bytes:
    """
    Return the bytes of a minimal valid 1×1 pixel JPEG.

    Used when a multipart test case references an image file that doesn't
    exist locally. This keeps the test runnable without bundling real images
    in the repository, while still exercising the endpoint's validation logic.
    """
    # This is a real, valid JPEG — the smallest possible one.
    # It was generated with Pillow and hard-coded here to avoid a runtime dependency.
    import base64
    tiny_jpeg_b64 = (
        "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8U"
        "HRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgN"
        "DRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
        "MjL/wAARCAABAAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAA"
        "AAAAAAAAAAAAAP/EABQBAQAAAAAAAAAAAAAAAAAAAAD/xAAUEQEAAAAAAAAAAAAAAAAAAAAA"
        "/9oADAMBAAIRAxEAPwCwABmX/9k="
    )
    return base64.b64decode(tiny_jpeg_b64)


# ═════════════════════════════════════════════════════════════════════════════
# TEST RUNNER
# ═════════════════════════════════════════════════════════════════════════════

def run_test_case(backend_url: str, case: dict, live_mode: bool = True) -> dict:
    """
    Execute one test case and return a result dict.

    Kept as a module-level function so tests can call it directly.
    The live_mode parameter defaults to True so legacy test code that
    doesn't pass it still works correctly.

    Result dict keys:
        test_name     — from the test case
        feature_area  — from the test case (used for grouping in the report)
        difficulty    — "Basic", "Logic", or "Stress-Test"
        tags          — list of tag strings
        passed        — True / False
        skipped       — True if skipped (e.g. LLM test in mock mode)
        reasons       — list of reason strings from each assertion
        http_status   — actual HTTP status code received
    """
    test_name    = case.get("test_name", "unnamed")
    feature_area = case.get("feature_area", "General")
    difficulty   = case.get("difficulty", "Basic")
    tags         = case.get("tags", [])

    # ── Mock mode: skip LLM-dependent tests ──────────────────────────────
    if not live_mode and "llm" in tags:
        return {
            "test_name": test_name, "feature_area": feature_area,
            "difficulty": difficulty, "tags": tags,
            "passed": True, "skipped": True,
            "reasons": ["Skipped in mock mode (run with --live to execute)"],
            "http_status": None,
        }

    # ── Send the request ──────────────────────────────────────────────────
    resp, network_error = send_request(backend_url, case)

    if resp is None:
        return {
            "test_name": test_name, "feature_area": feature_area,
            "difficulty": difficulty, "tags": tags,
            "passed": False, "skipped": False,
            "reasons": [network_error],
            "http_status": None,
        }

    # ── Parse the response body ───────────────────────────────────────────
    try:
        body_json = resp.json()
        body_str  = json.dumps(body_json)
    except Exception:
        body_json = None
        body_str  = resp.text

    # ── Build and run assertions ──────────────────────────────────────────
    assertions = build_assertions(case, resp.status_code)

    all_passed = True
    reasons    = []

    for assertion in assertions:
        ok, reason = assertion.check(body_str, body_json)
        reasons.append(reason)
        if not ok:
            all_passed = False

    if not assertions:
        all_passed = resp.ok
        reasons    = [f"HTTP {resp.status_code} — no assertions declared"]

    return {
        "test_name": test_name, "feature_area": feature_area,
        "difficulty": difficulty, "tags": tags,
        "passed": all_passed, "skipped": False,
        "reasons": reasons,
        "http_status": resp.status_code,
    }


# ═════════════════════════════════════════════════════════════════════════════
# STATEFUL CONTEXT TESTING (AI Assistant multi-turn)
# ═════════════════════════════════════════════════════════════════════════════

def run_conversation_test(backend_url: str, case: dict, live_mode: bool) -> list[dict]:
    """
    Run a multi-turn conversation test for the AI Assistant.

    The test case must have a "turns" list instead of a single "input".
    Each turn has a "message" and its own assertions. The conversation
    history is accumulated across turns so the LLM has context.

    This tests Requirement 9.3: the assistant retains the last 5 message pairs.
    """
    tags = case.get("tags", [])
    if not live_mode and "llm" in tags:
        return [{
            "test_name": f"{case['test_name']}_turn_{i+1}",
            "feature_area": case.get("feature_area", "AI Assistant"),
            "difficulty": case.get("difficulty", "Logic"),
            "tags": tags, "passed": True, "skipped": True,
            "reasons": ["Skipped in mock mode"],
            "http_status": None,
        } for i in range(len(case.get("turns", [])))]

    history = []   # Accumulated conversation history
    results = []

    for i, turn in enumerate(case.get("turns", [])):
        message = turn["message"]
        turn_case = {
            "test_name":    f"{case['test_name']}_turn_{i+1}",
            "feature_area": case.get("feature_area", "AI Assistant"),
            "difficulty":   case.get("difficulty", "Logic"),
            "tags":         tags,
            "endpoint":     "/assistant",
            "method":       "POST",
            "input":        {"message": message, "history": history[-10:]},
            "assertions":   turn.get("assertions", []),
        }

        result = run_test_case(backend_url, turn_case, live_mode)
        results.append(result)

        # Append this turn to history for the next turn
        history.append({"role": "user",      "content": message})
        history.append({"role": "assistant", "content": "(response)"})

    return results


# ═════════════════════════════════════════════════════════════════════════════
# REPORTING
# ═════════════════════════════════════════════════════════════════════════════

def generate_report(results: list[dict], backend_url: str, live_mode: bool) -> str:
    """
    Generate a Markdown report grouped by Feature Area and Difficulty Level.

    The report is written to eval/test_results.md and also returned as a string.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Group results by feature area
    by_feature: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_feature[r["feature_area"]].append(r)

    # Count totals
    total   = len(results)
    passed  = sum(1 for r in results if r["passed"] and not r["skipped"])
    failed  = sum(1 for r in results if not r["passed"] and not r["skipped"])
    skipped = sum(1 for r in results if r["skipped"])

    lines = [
        "# NoFishyBusiness — Evaluation Results",
        "",
        f"**Generated:** {now}  ",
        f"**Backend:** {backend_url}  ",
        f"**Mode:** {'LIVE (LLM calls enabled)' if live_mode else 'MOCK (LLM tests skipped)'}  ",
        "",
        f"## Summary",
        "",
        f"| Status | Count |",
        f"|--------|-------|",
        f"| ✅ Passed  | {passed} |",
        f"| ❌ Failed  | {failed} |",
        f"| ⏭ Skipped | {skipped} |",
        f"| **Total**  | **{total}** |",
        "",
    ]

    # One section per feature area
    for feature, feature_results in sorted(by_feature.items()):
        lines.append(f"## {feature}")
        lines.append("")

        # Group by difficulty within the feature
        by_difficulty: dict[str, list[dict]] = defaultdict(list)
        for r in feature_results:
            by_difficulty[r["difficulty"]].append(r)

        for difficulty in ["Basic", "Logic", "Stress-Test"]:
            diff_results = by_difficulty.get(difficulty, [])
            if not diff_results:
                continue

            lines.append(f"### {difficulty}")
            lines.append("")
            lines.append("| Test | Status | HTTP | Reasons |")
            lines.append("|------|--------|------|---------|")

            for r in diff_results:
                if r["skipped"]:
                    icon = "⏭"
                elif r["passed"]:
                    icon = "✅"
                else:
                    icon = "❌"

                http   = str(r["http_status"]) if r["http_status"] else "—"
                reason = "; ".join(r["reasons"])[:120]   # Truncate long reasons
                lines.append(f"| `{r['test_name']}` | {icon} | {http} | {reason} |")

            lines.append("")

    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    # ── CLI arguments ─────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        description="NoFishyBusiness high-coverage evaluation runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python eval/eval.py                  # mock mode (no LLM calls)\n"
            "  python eval/eval.py --live           # live mode (calls OpenAI)\n"
            "  python eval/eval.py --live --report  # live + save Markdown report\n"
        )
    )
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL,
                        help=f"Backend URL (default: {DEFAULT_BACKEND_URL})")
    parser.add_argument("--live", action="store_true",
                        help="Enable live LLM calls (costs API credits)")
    parser.add_argument("--report", action="store_true",
                        help=f"Write Markdown report to {REPORT_PATH}")
    args = parser.parse_args()

    backend_url = args.backend_url.rstrip("/")
    live_mode   = args.live

    mode_label = "LIVE MODE — LLM calls enabled" if live_mode else "MOCK MODE — LLM tests skipped (use --live to enable)"
    print(f"\n{'='*60}")
    print(f"  NoFishyBusiness Evaluation Suite")
    print(f"  {mode_label}")
    print(f"{'='*60}\n")

    # ── Health check ──────────────────────────────────────────────────────
    print(f"Checking backend at {backend_url}/health ...")
    if not check_health(backend_url):
        print(f"\nERROR: Backend not reachable at {backend_url}.")
        print("Start the backend first:  python -m uvicorn backend.main:app --port 8000")
        sys.exit(1)
    print("Backend is reachable.\n")

    # ── Load test cases ───────────────────────────────────────────────────
    # Strip // comments before parsing — JSON doesn't support comments natively
    # but they make the test file much more readable for humans.
    try:
        with open(TEST_CASES_PATH, "r", encoding="utf-8") as fh:
            raw = fh.read()
        import re as _re
        clean = _re.sub(r"//[^\n]*", "", raw)   # Remove // comment lines
        test_cases = json.loads(clean)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"ERROR: Could not load {TEST_CASES_PATH}: {exc}")
        sys.exit(1)

    print(f"Loaded {len(test_cases)} test case(s) from {TEST_CASES_PATH}\n")

    # ── Run tests ─────────────────────────────────────────────────────────
    all_results = []

    for case in test_cases:
        # Multi-turn conversation tests have a "turns" key instead of "input"
        if "turns" in case:
            turn_results = run_conversation_test(backend_url, case, live_mode)
            all_results.extend(turn_results)
            for r in turn_results:
                _print_result(r)
        else:
            result = run_test_case(backend_url, case, live_mode)
            all_results.append(result)
            _print_result(result)

    # ── Summary ───────────────────────────────────────────────────────────
    total   = len(all_results)
    passed  = sum(1 for r in all_results if r["passed"] and not r["skipped"])
    failed  = sum(1 for r in all_results if not r["passed"] and not r["skipped"])
    skipped = sum(1 for r in all_results if r["skipped"])

    print(f"\n{'='*60}")
    print(f"  Passed: {passed} / Total: {total}  (Failed: {failed}, Skipped: {skipped})")
    print(f"{'='*60}\n")

    # ── Optional Markdown report ──────────────────────────────────────────
    if args.report:
        report_md = generate_report(all_results, backend_url, live_mode)
        with open(REPORT_PATH, "w", encoding="utf-8") as fh:
            fh.write(report_md)
        print(f"Report written to: {REPORT_PATH}\n")

    # Exit 1 if any test failed (not just skipped)
    if failed > 0:
        sys.exit(1)


def _print_result(r: dict) -> None:
    """Print a single test result line to stdout."""
    if r["skipped"]:
        icon = "⏭ SKIP"
        tag  = "[SKIP]"
    elif r["passed"]:
        icon = "✅ PASS"
        tag  = "[PASS]"
    else:
        icon = "❌ FAIL"
        tag  = "[FAIL]"

    # Show the first failing reason (or first reason if all passed)
    first_reason = r["reasons"][0] if r["reasons"] else ""
    if not r["passed"] and not r["skipped"]:
        first_reason = " | ".join(r["reasons"])

    # Print both the emoji icon AND the plain [TAG] so tests can assert on either
    print(f"{tag} [{icon}] {r['test_name']} ({r['feature_area']} / {r['difficulty']}): {first_reason}")


if __name__ == "__main__":
    main()
