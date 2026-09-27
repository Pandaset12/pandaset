"""Focused event coordinator and contract checks without vendor calls."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import threading

import mongomock
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.auth import AuthenticatedUser
from backend.config import Settings
from backend.event_agents import grounded_source_records
from backend.event_api import _aligned_histories, _validate_event_allocation
from backend.event_jobs import process_draft, process_run
from backend.event_schemas import DraftRequest, EventPortfolioInput, validate_shocks
from backend.event_templates import get_event_template
from backend.event_sources import record_source_retrieval
from backend.main import create_app
from backend.mongo_store import MongoPortfolioStore
from backend.schemas import AnalyticsSnapshot
from backend.schemas import PortfolioInput
from backend.storage import PortfolioStore


def _settings(**changes):
    values = dict(event_lab_enabled=True, supabase_url="https://example.supabase.co",
                  supabase_publishable_key="publishable", mongo_uri=SecretStr("mongodb://unused"),
                  alpaca_api_key=SecretStr("vendor-key"), alpaca_api_secret=SecretStr("vendor-secret"),
                  alpaca_history_feed="iex", alpaca_cache_rights_confirmed=True,
                  gemini_api_key=SecretStr("gemini"),
                  tavily_api_key=SecretStr("tavily"), deepseek_api_key=SecretStr("deepseek"),
                  event_lab_allowed_user_ids="owner-a,owner-b")
    values.update(changes)
    return Settings(**values)


def _shocks():
    return {case: {horizon: {"factors": {"equity": 0.01, "rates": -0.01, "gold": 0.0},
                            "issuers": {"AAPL": 0.2}}
                   for horizon in ("1m", "3m")}
            for case in ("mild", "central", "severe")}


def test_confirmed_shocks_reject_unsupported_factor_and_issuer():
    valid = _shocks()
    assert validate_shocks(valid, {"AAPL"}) == valid
    valid["mild"]["1m"]["factors"]["unknown"] = 0.1
    with pytest.raises(ValueError, match="exactly"):
        validate_shocks(valid, {"AAPL"})
    valid = _shocks()
    valid["central"]["3m"]["issuers"]["NVDA"] = 0.1
    with pytest.raises(ValueError, match="outside"):
        validate_shocks(valid, {"AAPL"})


def test_event_research_validates_issuer_target_and_symbol_union():
    from fastapi import HTTPException

    template = get_event_template("issuer_earnings")
    body = DraftRequest(portfolio_id="portfolio-a", portfolio_revision=1,
                        template_id="issuer_earnings", target_symbol="TLT",
                        proposed_weights={"AAPL": 0.5, "TLT": 0.5})
    with pytest.raises(HTTPException) as invalid:
        _validate_event_allocation(template, body, ["AAPL", "TLT"])
    assert invalid.value.detail["code"] == "INVALID_TARGET"
    body = body.model_copy(update={"target_symbol": "AAPL"})
    _validate_event_allocation(template, body, ["AAPL", "TLT"])
    with pytest.raises(HTTPException) as too_many:
        _validate_event_allocation(template, body, ["AAPL"] * 9)
    assert too_many.value.detail["code"] == "SYMBOL_LIMIT_EXCEEDED"


def test_grounding_promotes_only_supported_approved_https_sources():
    grounding = {"sources": [
        {"web": {"uri": "https://www.federalreserve.gov/newsevents/pressreleases/example.htm", "title": "Fed"}},
        {"web": {"uri": "https://unapproved.example/news", "title": "Unapproved"}},
    ], "grounding_supports": [
        {"segment": {"text": "The cited release describes a policy decision."},
         "grounding_chunk_indices": [0, 1]},
    ], "url_retrievals": []}
    records = grounded_source_records(grounding, set())
    assert len(records) == 1
    assert records[0]["status"] == "available"
    assert records[0]["publication_status"] == "unknown"
    assert records[0]["source_url"].startswith("https://www.federalreserve.gov/")


def test_undated_official_retrievals_have_distinct_url_citations():
    now = datetime.now(timezone.utc)
    first = record_source_retrieval(
        "fomc_releases", source_url="https://www.federalreserve.gov/newsevents/pressreleases/a.htm",
        title="Release A", excerpt="A", published_at=None, retrieved_at=now)
    second = record_source_retrieval(
        "fomc_releases", source_url="https://www.federalreserve.gov/newsevents/pressreleases/b.htm",
        title="Release B", excerpt="B", published_at=None, retrieved_at=now)
    assert first.evidence_id != second.evidence_id
    assert first.evidence_id.startswith("official:fomc_releases:undated:")
    assert first.source_url.endswith("a.htm") and second.source_url.endswith("b.htm")


def test_draft_worker_persists_enriched_evidence(monkeypatch):
    from backend import event_jobs

    class Store:
        def get_analysis_record(self, owner, portfolio, analysis):
            assert (owner, portfolio, analysis) == ("owner-a", "portfolio-a", "analysis-a")
            return {"allocation_snapshot": {"holdings": [{"symbol": "AAPL", "weight": 1.0}]},
                    "price_snapshot": {"dates": ["2025-12-31T00:00:00+00:00"],
                                       "provenance": {"data_source": "twelve_data_adjusted_daily"}}}

        def complete_draft(self, owner, draft_id, proposal, *, worker_id):
            assert (owner, draft_id, worker_id) == ("owner-a", "draft-a", "worker-a")
            return proposal

    async def research(**kwargs):
        return {"facts": [{"claim": "Observed rate", "evidence_ids": ["fred:FEDFUNDS"]}],
                "evidence": [*kwargs["evidence"], {"evidence_id": "fred:FEDFUNDS", "status": "available"}],
                "missing_evidence": ["Future rate path"], "grounding": {"sources": [], "url_retrievals": []},
                "grounding_text": "{}"}

    async def design(**kwargs):
        assert any(item["evidence_id"] == "fred:FEDFUNDS" for item in kwargs["evidence"])
        return {"proposed_shocks": {}, "grounding": {}, "grounding_text": "{}"}

    class Fred:
        def __init__(self, key):
            pass

        def observation(self, series_id, as_of):
            from backend.event_sources import EventEvidence
            return EventEvidence(evidence_id="fred:FEDFUNDS", kind="fred_observation",
                                 title="Rate", source_name="FRED", source_url="https://fred.stlouisfed.org/series/FEDFUNDS",
                                 status="available", retrieval_status="retrieved", publication_status="unknown",
                                 retrieved_at=datetime.now(timezone.utc).isoformat(), value=4.0)

    monkeypatch.setattr(event_jobs, "FredClient", Fred)
    monkeypatch.setattr(event_jobs, "research_event", research)
    monkeypatch.setattr(event_jobs, "design_scenarios", design)
    job = {"id": "draft-a", "owner_id": "owner-a", "portfolio_id": "portfolio-a",
           "request": {"portfolio_revision": 1, "template_id": "fed_policy", "question": "What if?"},
           "context": {"allocation_snapshot": {"holdings": [{"symbol": "AAPL", "weight": 1.0}]},
                       "price_snapshot": {"dates": ["2025-12-31T00:00:00+00:00"],
                                          "provenance": {"data_source": "twelve_data_adjusted_daily"}},
                       "analysis_snapshot": {"weights": {"AAPL": 1.0}}}}
    proposal = asyncio.run(process_draft(Store(), _settings(), job, "worker-a"))
    assert proposal["evidence"][0]["status"] == "available"
    assert proposal["missing_evidence"] == ["Future rate path"]
    assert proposal["price_provenance"]["data_source"] == "twelve_data_adjusted_daily"


def test_v2_requires_bearer_and_has_error_envelope(tmp_path):
    app = create_app(Settings(storage_path=tmp_path / "portfolios.sqlite3"))
    with TestClient(app) as client:
        response = client.get("/api/v2/portfolios")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"
    assert response.json()["error"]["request_id"]


def test_event_lab_requires_rights_to_retain_price_snapshots():
    assert _settings(alpaca_cache_rights_confirmed=False).event_lab_ready is False
    assert _settings().event_lab_ready is True
    assert _settings(event_lab_public_enabled=True).event_lab_public_ready is False


def test_pinned_event_run_survives_portfolio_and_price_changes(tmp_path):
    main_store = PortfolioStore(tmp_path / "portfolios.sqlite3")
    portfolio = main_store.create(PortfolioInput(name="Core", holdings=[
        {"symbol": "AAPL", "weight": 0.6}, {"symbol": "TLT", "weight": 0.4},
    ]), "owner-a")
    store = MongoPortfolioStore(database=mongomock.MongoClient()["pinned_event"],
                                portfolio_repository=main_store)
    app = create_app(_settings(storage_path=tmp_path / "portfolios.sqlite3"))

    class Verifier:
        def verify(self, token):
            return AuthenticatedUser(user_id=token, claims={"sub": token})

    class Prices:
        calls = 0

        def prices(self, symbols, lookback_days):
            self.calls += 1
            dates = pd.date_range("2025-01-02", periods=253, freq="B", tz="UTC")
            frame = pd.DataFrame({symbol: 100 + np.arange(253) * (index + 1)
                                  + np.sin(np.arange(253) / (index + 2))
                                  for index, symbol in enumerate(symbols)}, index=dates)
            frame.attrs["provenance"] = {"data_mode": "live", "data_source": "alpaca_adjusted_daily",
                                         "freshness": "fresh", "warnings": []}
            return frame

    provider = Prices()
    with TestClient(app) as client:
        app.state.event_store = store
        app.state.event_price_provider = provider
        app.state.auth_verifier = Verifier()
        body = {"portfolio_id": portfolio.portfolio_id, "portfolio_revision": 1,
                "template_id": "fed_policy", "question": "What if rates change?",
                "proposed_weights": {"AAPL": 0.4, "TLT": 0.3, "SPY": 0.3}}
        own = {"Authorization": "Bearer owner-a"}
        other = {"Authorization": "Bearer owner-b"}
        assert client.post("/api/v2/scenarios/drafts", json=body, headers=other).status_code == 404
        created = client.post("/api/v2/scenarios/drafts", json=body,
                              headers={**own, "Idempotency-Key": "pinned-retry"})
        assert created.status_code == 202, created.text
        draft_id = created.json()["draft_id"]
        draft = store.get_draft("owner-a", draft_id)
        assert draft["context"]["portfolio_revision"] == 1
        assert set(draft["context"]["proposed_weights"]) == {"AAPL", "TLT", "SPY"}
        assert draft["context"]["allocation_snapshot"]["name"] == "Core"
        assert len(draft["context"]["price_snapshot"]["dates"]) == 253
        assert not list(store.db["analyses"].find({}))
        assert client.get(f"/api/v2/scenarios/drafts/{draft_id}", headers=other).status_code == 404
        store.claim_draft("owner-a", draft_id, worker_id="test-worker")
        store.complete_draft("owner-a", draft_id, {"template": {"template_id": "fed_policy"},
                       "facts": [], "evidence": [], "proposed_shocks": {}}, worker_id="test-worker")
        main_store.update(portfolio.portfolio_id, "owner-a", PortfolioInput(name="Changed", holdings=[
            {"symbol": "AAPL", "weight": 1.0},
        ]))
        retried_draft = client.post("/api/v2/scenarios/drafts", json=body,
                                    headers={**own, "Idempotency-Key": "pinned-retry"})
        assert retried_draft.status_code == 202
        assert retried_draft.json()["draft_id"] == draft_id
        assert client.post("/api/v2/scenarios/drafts", json={**body, "question": "Different"},
                           headers={**own, "Idempotency-Key": "pinned-retry"}).status_code == 409
        result = client.post(f"/api/v2/scenarios/drafts/{draft_id}/confirm",
                             json={"revision": 1, "confirmed_shocks": _shocks()}, headers=own)
        assert result.status_code == 202, result.text
        retried = client.post(f"/api/v2/scenarios/drafts/{draft_id}/confirm",
                              json={"revision": 1, "confirmed_shocks": _shocks()}, headers=own)
        assert retried.status_code == 202 and retried.json()["run_id"] == result.json()["run_id"]
        run = store.get_run("owner-a", result.json()["run_id"])
        assert "analysis_id" not in run
        assert run["allocation_snapshot"]["name"] == "Core"
        assert run["portfolio_revision"] == 1
        assert provider.calls == 1
        store.claim_run("owner-a", run["id"], worker_id="test-worker")
        completed = asyncio.run(process_run(store, _settings(),
                                            store.get_run("owner-a", run["id"]), "test-worker"))
        assert completed["result"]["current_weights"]["AAPL"] == 0.6
        assert completed["result"]["proposed_weights"]["SPY"] == 0.3
        assert provider.calls == 1
        assert not list(store.db["analyses"].find({}))
        revised = client.post(f"/api/v2/scenarios/runs/{run['id']}/messages",
                              json={"content": "Change the shock assumptions"},
                              headers={**own, "Idempotency-Key": "saved-run-revision"})
        assert revised.status_code == 201, revised.text
        revision_draft = store.get_draft("owner-a", revised.json()["revision_draft_id"])
        assert revision_draft["request"]["source_run_id"] == run["id"]
        assert revision_draft["context"]["portfolio_revision"] == 1
        assert revision_draft["context"]["price_snapshot"] == run["price_snapshot"]
        assert provider.calls == 1


def test_event_draft_rejects_missing_history_before_saving(tmp_path):
    main_store = PortfolioStore(tmp_path / "portfolios.sqlite3")
    portfolio = main_store.create(PortfolioInput(name="Core", holdings=[
        {"symbol": "AAPL", "weight": 1.0},
    ]), "owner-a")
    store = MongoPortfolioStore(database=mongomock.MongoClient()["missing_prices"],
                                portfolio_repository=main_store)
    app = create_app(_settings(storage_path=tmp_path / "portfolios.sqlite3"))

    class Verifier:
        def verify(self, token):
            return AuthenticatedUser(user_id=token, claims={"sub": token})

    class Prices:
        def prices(self, symbols, lookback_days):
            dates = pd.date_range("2025-01-02", periods=120, freq="B", tz="UTC")
            frame = pd.DataFrame({symbol: 100 + np.arange(120) for symbol in symbols}, index=dates)
            frame.attrs["provenance"] = {"data_mode": "live", "data_source": "test"}
            return frame

    with TestClient(app) as client:
        app.state.event_store = store
        app.state.event_price_provider = Prices()
        app.state.auth_verifier = Verifier()
        response = client.post("/api/v2/scenarios/drafts", json={
            "portfolio_id": portfolio.portfolio_id, "portfolio_revision": 1,
            "template_id": "fed_policy", "situation_id": "faster_cuts",
            "proposed_weights": {"AAPL": 1.0},
        }, headers={"Authorization": "Bearer owner-a"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PRICE_COVERAGE"
    assert store.drafts.count_documents({}) == 0


def test_internal_gate_denies_uninvited_even_with_valid_token():
    app = create_app(_settings(event_lab_allowed_user_ids=""))

    class Verifier:
        def verify(self, token):
            return AuthenticatedUser(user_id="owner-a", claims={"sub": "owner-a"})

    app.state.auth_verifier = Verifier()
    response = TestClient(app).get("/api/v2/portfolios", headers={"Authorization": "Bearer valid"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "EVENT_LAB_NOT_INVITED"


def test_run_worker_uses_pinned_prices_and_omits_uncalibrated_probabilities():
    rng = np.random.default_rng(42)
    days = pd.date_range("2025-01-01", periods=301, freq="B", tz="UTC")
    changes = rng.normal(0, 0.004, size=(300, 3))
    factor_prices = np.vstack([np.ones(3), np.cumprod(1 + changes, axis=0)]) * 100
    holding_returns = changes @ np.array([0.9, 0.3, -0.1]) + rng.normal(0, 0.002, 300)
    holding_prices = np.r_[100.0, 100.0 * np.cumprod(1 + holding_returns)]

    class Store:
        def complete_run(self, owner, run_id, result, *, worker_id):
            assert (owner, run_id, worker_id) == ("owner-a", "run-a", "worker-a")
            return result

    job = {"id": "run-a", "owner_id": "owner-a", "analysis_id": "analysis-a",
           "allocation_snapshot": {"holdings": [{"symbol": "AAPL", "weight": 1.0}]},
           "proposed_weights": {"AAPL": 1.0},
           "proposal_snapshot": {"facts": [], "evidence": []},
           "price_snapshot": {"dates": [day.isoformat() for day in days],
                              "holding_prices": {"AAPL": holding_prices.tolist()},
                              "factor_prices": {symbol: factor_prices[:, index].tolist()
                                                for index, symbol in enumerate(("SPY", "TLT", "GLD"))},
                              "provenance": {"data_source": "alpaca_adjusted_daily", "feed": "iex"}},
           "confirmed_shocks": _shocks()}
    result = asyncio.run(process_run(Store(), _settings(), job, "worker-a"))
    assert len(result["cases"]) == 6
    assert result["probabilities"]["status"] == "omitted"
    assert result["probabilities"]["reason"] == "calibration_gate_disabled"
    assert result["price_provenance"]["data_source"] == "alpaca_adjusted_daily"


def test_chat_retry_returns_saved_answer_before_gemini_and_checks_quota(monkeypatch):
    from backend import event_api

    calls = {"answer": 0, "save": 0}

    class Store:
        max_messages_per_run = 1

        def __init__(self):
            self.saved = []
            self.reserved = False

        def get_run(self, owner, run_id):
            return {"status": "completed", "result": {"cases": [], "facts": [], "evidence": []}}

        def list_messages(self, owner, run_id):
            return self.saved[:]

        def reserve_message_slot(self, owner, run_id, key):
            from backend.mongo_store import QuotaExceeded
            if self.saved or self.reserved:
                raise QuotaExceeded()
            self.reserved = True
            return "slot-a"

        def release_message_slot(self, owner, run_id, reservation_id):
            self.reserved = False
            return True

        def save_message(self, owner, run_id, message, key, *, reservation_id):
            calls["save"] += 1
            assert self.reserved and reservation_id == "slot-a"
            record = {"id": "message-a", "idempotency_key": key, "message": message,
                      "created_at": datetime.now(timezone.utc)}
            self.saved.append(record)
            return record

    async def answer(**kwargs):
        calls["answer"] += 1
        return {"content": "Saved answer", "citations": []}

    monkeypatch.setattr(event_api, "answer_run_question", answer)
    app = create_app(_settings())
    app.state.event_store = Store()

    class Verifier:
        def verify(self, token):
            return AuthenticatedUser(user_id="owner-a", claims={"sub": "owner-a"})

    app.state.auth_verifier = Verifier()
    client = TestClient(app)
    headers = {"Authorization": "Bearer valid", "Idempotency-Key": "same-key"}
    url = "/api/v2/scenarios/runs/run-a/messages"
    first = client.post(url, json={"content": "Explain the result"}, headers=headers)
    retry = client.post(url, json={"content": "Explain the result"}, headers=headers)
    conflict = client.post(url, json={"content": "Different question"}, headers=headers)
    over_limit = client.post(url, json={"content": "Another question"},
                             headers={**headers, "Idempotency-Key": "new-key"})
    assert first.status_code == retry.status_code == 201
    assert first.json()["message"]["id"] == retry.json()["message"]["id"]
    assert conflict.status_code == 409 and over_limit.status_code == 429
    assert calls == {"answer": 1, "save": 1}


def test_cached_history_rollover_refreshes_both_sides_once(monkeypatch):
    from backend import event_api

    class Provider:
        def __init__(self, fresh=False):
            self.fresh = fresh
            self.calls = 0

        def prices(self, symbols, lookback_days):
            self.calls += 1
            start = "2025-01-02" if self.fresh or "SPY" not in symbols else "2025-01-01"
            dates = pd.date_range(start, periods=253, freq="B", tz="UTC")
            frame = pd.DataFrame({symbol: np.arange(253, dtype=float) + 100 for symbol in symbols}, index=dates)
            frame.attrs["provenance"] = {"fresh": self.fresh}
            return frame

    cached = Provider()
    fresh = Provider(fresh=True)
    monkeypatch.setattr(event_api, "AlpacaHistoryProvider", lambda *args, **kwargs: fresh)
    symbols = [f"STOCK{i}" for i in range(23)]
    prices, factors = asyncio.run(_aligned_histories(cached, _settings(), symbols))
    assert cached.calls == 2 and fresh.calls == 2
    assert prices.index.equals(factors.index)
    assert prices.attrs["provenance"]["fresh"] is True


def test_concurrent_chat_reservation_blocks_second_gemini_call(monkeypatch):
    from backend import event_api

    store = MongoPortfolioStore(database=mongomock.MongoClient()["chat_slots"],
                                supported_symbol=lambda symbol: symbol == "AAPL",
                                max_messages_per_run=1)
    portfolio = store.create_portfolio("owner-a", EventPortfolioInput(
        name="Owned", holdings=[{"symbol": "AAPL", "weight": 1.0}]))
    metrics = AnalyticsSnapshot(portfolio_id=portfolio.portfolio_id, data_mode="demo",
                                lookback_trading_days=10, portfolio_volatility=0,
                                weights={"AAPL": 1.0}, risk_contribution={})
    context = {"portfolio_revision": 1,
               "allocation_snapshot": portfolio.model_dump(mode="json"),
               "price_snapshot": {"source": "pinned"},
               "analysis_snapshot": metrics.model_dump(mode="json"),
               "model_version": "event-v1", "proposed_weights": {"AAPL": 1.0}}
    draft = store.create_draft("owner-a", portfolio.portfolio_id,
                               {"portfolio_revision": 1, "template_id": "fed_policy"},
                               context=context)
    store.claim_draft("owner-a", draft["id"], worker_id="test-worker")
    store.complete_draft("owner-a", draft["id"], {"template": {"template_id": "fed_policy"}},
                         worker_id="test-worker")
    store.confirm_draft("owner-a", draft["id"], _shocks(), revision=1)
    run = store.create_run("owner-a", draft["id"])
    store.claim_run("owner-a", run["id"], worker_id="test-worker")
    store.complete_run("owner-a", run["id"], {"cases": [], "facts": [], "evidence": []},
                       worker_id="test-worker")
    app = create_app(_settings())
    app.state.event_store = store

    class Verifier:
        def verify(self, token):
            return AuthenticatedUser(user_id="owner-a", claims={"sub": "owner-a"})

    app.state.auth_verifier = Verifier()
    started, release = threading.Event(), threading.Event()
    calls = 0
    counter_lock = threading.Lock()

    async def slow_answer(**kwargs):
        nonlocal calls
        with counter_lock:
            calls += 1
        started.set()
        await asyncio.to_thread(release.wait, 5)
        return {"content": "Saved answer", "citations": []}

    monkeypatch.setattr(event_api, "answer_run_question", slow_answer)
    url = f"/api/v2/scenarios/runs/{run['id']}/messages"
    headers = {"Authorization": "Bearer valid"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(lambda: TestClient(app).post(
            url, json={"content": "First question"},
            headers={**headers, "Idempotency-Key": "first"}))
        assert started.wait(5)
        second = pool.submit(lambda: TestClient(app).post(
            url, json={"content": "Second question"},
            headers={**headers, "Idempotency-Key": "second"}))
        assert second.result(timeout=5).status_code == 429
        release.set()
        first_response = first.result(timeout=5)
    assert first_response.status_code == 201
    assert calls == 1
    retry = TestClient(app).post(url, json={"content": "First question"},
                                 headers={**headers, "Idempotency-Key": "first"})
    assert retry.status_code == 201
    assert calls == 1


def test_chat_generation_failure_releases_reserved_slot(monkeypatch):
    from backend import event_api

    class Store:
        max_messages_per_run = 1

        def __init__(self):
            self.reserved = False
            self.saved = []

        def get_run(self, owner, run_id):
            return {"status": "completed", "result": {"cases": [], "facts": [], "evidence": []}}

        def list_messages(self, owner, run_id):
            return self.saved[:]

        def reserve_message_slot(self, owner, run_id, key):
            from backend.mongo_store import QuotaExceeded
            if self.reserved:
                raise QuotaExceeded()
            self.reserved = True
            return "reserved"

        def release_message_slot(self, owner, run_id, token):
            self.reserved = False
            return True

        def save_message(self, owner, run_id, message, key, *, reservation_id):
            self.saved.append({"id": "saved", "message": message, "idempotency_key": key})
            return self.saved[-1]

    attempts = 0

    async def answer(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary provider failure")
        return {"content": "Answer", "citations": []}

    monkeypatch.setattr(event_api, "answer_run_question", answer)
    app = create_app(_settings())
    store = Store()
    app.state.event_store = store

    class Verifier:
        def verify(self, token):
            return AuthenticatedUser(user_id="owner-a", claims={"sub": "owner-a"})

    app.state.auth_verifier = Verifier()
    client = TestClient(app)
    url = "/api/v2/scenarios/runs/run-a/messages"
    headers = {"Authorization": "Bearer valid", "Idempotency-Key": "retry"}
    first = client.post(url, json={"content": "Explain"}, headers=headers)
    assert first.status_code == 502 and store.reserved is False
    second = client.post(url, json={"content": "Explain"}, headers=headers)
    assert second.status_code == 201 and attempts == 2
