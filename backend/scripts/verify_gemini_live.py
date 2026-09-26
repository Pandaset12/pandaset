"""Opt-in live Gemini verification through real local HTTP servers.

Run from the repository root: python -m backend.scripts.verify_gemini_live
Requires a configured Gemini key; sends four generation requests and an
intentional invalid-model request. Uses only the seeded demo portfolio.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import httpx

from backend.config import Settings

ROOT = Path(__file__).resolve().parents[2]
SOURCE_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
EVIDENCE_FIELDS = (
    "status", "error_code", "answer", "warnings", "sources", "grounding_supports",
    "web_search_queries", "search_suggestions_html", "url_retrievals", "grounding_text",
)


@contextmanager
def running_api(settings, directory, model):
    """Start and stop only this script's server; never touch the user's server."""
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
    env = dict(os.environ, ANALYST_MODE="gemini", GEMINI_MODEL=model,
               GEMINI_API_KEY=settings.gemini_api_key.get_secret_value(),
               STORAGE_PATH=str(directory / "verification.sqlite3"),
               GEMINI_TIMEOUT_SECONDS=str(settings.gemini_timeout_seconds))
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False,
                          timeout=settings.gemini_timeout_seconds + 15) as api:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Verification API exited during startup.")
                try:
                    health = api.get("/health")
                    if health.status_code == 200:
                        assert health.json()["analyst_mode"] == "gemini"
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Verification API did not become ready.")
            yield api
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def analyze_demo(api):
    response = api.post("/api/v1/portfolios/demo/analysis")
    response.raise_for_status()
    data = response.json()
    assert data["data_mode"] == "demo", "This verifier must use fictional demo data."
    return data


def check_case(api, analysis, name, options, expectation):
    question = (
        "Search for the latest Federal Reserve policy news as of today and explain "
        "its possible relevance to the TLT holding in this fictional portfolio. "
        "Use current sources, distinguish news from causation, and keep the explanation "
        "qualitative without numbers or dates. If web tools are disabled, say current "
        "news cannot be verified and explain only the saved snapshot."
    )
    if options.get("source_urls"):
        question = (
            "Read the supplied Federal Reserve calendar page using URL Context and "
            "summarize its relevance to TLT. Keep the explanation qualitative with no "
            "numbers or dates. If Google Search is available, also search for current "
            "policy context. Label this portfolio as fictional."
        )
    record = {"case": name, "request_options": options, "passed": False}
    try:
        response = api.post("/api/v1/portfolios/demo/ask", json={
            "analysis_id": analysis["analysis_id"], "question": question, **options,
        })
        record["http_status"] = response.status_code
        record["request_id"] = response.headers.get("x-request-id")
        response.raise_for_status()
        data = response.json()
        record["response"] = {field: data.get(field) for field in EVIDENCE_FIELDS}
        assert data["analysis_id"] == analysis["analysis_id"], "Wrong saved analysis."
        assert data["metrics"]["portfolio_volatility"] == analysis["portfolio_volatility"], "Metrics changed."
        if expectation == "failure":
            assert data["status"] == "unavailable", "Invalid model must fail safely."
            assert data["error_code"] == "GEMINI_UNAVAILABLE", "Unexpected failure type."
            assert not data["sources"] and not data["web_search_queries"], "Failure invented evidence."
        else:
            assert data["status"] == "complete", "HTTP success did not produce a complete AI answer."
            for support in data["grounding_supports"]:
                assert all(0 <= i < len(data["sources"])
                           for i in support.get("grounding_chunk_indices", [])), "Invalid source index."
            if expectation == "search":
                assert data["web_search_queries"], "No actual search queries returned; search is unverified."
                assert any(source.get("web", {}).get("uri") for source in data["sources"]), "No web sources."
                assert data["grounding_supports"], "No grounding supports; review the raw response."
                assert data["search_suggestions_html"], "No search display metadata."
            if options.get("source_urls"):
                assert any(item.get("url_retrieval_status") == "URL_RETRIEVAL_STATUS_SUCCESS"
                           and item.get("retrieved_url") in options["source_urls"]
                           for item in data["url_retrievals"]), "Requested URL retrieval was not confirmed."
            if options.get("web_search") is False:
                assert not data["web_search_queries"] and not data["search_suggestions_html"], "Opt-out returned search metadata."
                if not options.get("source_urls"):
                    assert not data["sources"] and not data["grounding_supports"] and not data["url_retrievals"], "Opt-out returned web evidence."
        record["passed"] = True
    except AssertionError as error:
        record["failure"] = str(error)  # Only the fixed assertions above.
    except Exception as error:
        record["failure"] = type(error).__name__  # Never expose keys or raw upstream errors.
    print(json.dumps({"case": name, "passed": record["passed"],
                      "status": record.get("response", {}).get("status"),
                      "failure": record.get("failure")}), flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional local JSON evidence report.")
    args = parser.parse_args()
    settings = Settings()
    if not settings.has_gemini_key:
        print("Missing GEMINI_API_KEY. Configure backend/.env locally; do not paste keys into chat.", file=sys.stderr)
        return 2
    report = {"checked_at": datetime.now(timezone.utc).isoformat(),
              "model": settings.gemini_model, "cases": []}
    with tempfile.TemporaryDirectory(prefix="portfoliolens-live-search-") as temporary:
        directory = Path(temporary)
        with running_api(settings, directory, settings.gemini_model) as api:
            analysis = analyze_demo(api)
            for name, options, expectation in [
                ("omitted_web_search", {}, "search"),
                ("explicit_opt_out", {"web_search": False}, "no_search"),
                ("source_urls_with_default_search", {"source_urls": [SOURCE_URL]}, "url"),
                ("source_urls_without_search", {"web_search": False, "source_urls": [SOURCE_URL]}, "url"),
            ]:
                report["cases"].append(check_case(api, analysis, name, options, expectation))
        with running_api(settings, directory, "portfoliolens-intentional-invalid-model") as api:
            analysis = analyze_demo(api)
            report["cases"].append(check_case(api, analysis, "upstream_failure", {}, "failure"))
    report["passed"] = all(case["passed"] for case in report["cases"])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
