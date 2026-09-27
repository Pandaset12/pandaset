"""Focused authentication and owner-isolation checks for the event store."""

from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import base64

import httpx
import jwt
import mongomock
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from backend.auth import AuthUnavailable, InvalidAccessToken, SupabaseTokenVerifier
from backend.event_schemas import EventPortfolioInput
from backend.mongo_store import (
    IdempotencyConflict,
    InvalidTransition,
    MongoPortfolioStore,
    QuotaExceeded,
    RecordNotFound,
    ReservationInProgress,
)


ISSUER = "https://example.supabase.co/auth/v1"
OWNER = "00000000-0000-4000-8000-000000000001"
OTHER = "00000000-0000-4000-8000-000000000002"


class StaticJWKS:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, token):
        return self.key


def asymmetric_token(private_key, **overrides):
    claims = {
        "iss": ISSUER,
        "aud": "authenticated",
        "sub": OWNER,
        "role": "authenticated",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="EdDSA", headers={"kid": "test-key"})


def test_asymmetric_verification_checks_signature_and_access_claims():
    private_key = ed25519.Ed25519PrivateKey.generate()
    raw_public = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    jwk = jwt.PyJWK.from_dict({
        "kty": "OKP", "crv": "Ed25519", "x": base64.urlsafe_b64encode(raw_public).rstrip(b"=").decode(),
        "alg": "EdDSA", "kid": "test-key",
    })
    verifier = SupabaseTokenVerifier(
        "https://example.supabase.co", "sb_publishable_test",
        jwks_client=StaticJWKS(jwk),
    )
    assert verifier.verify(asymmetric_token(private_key)).user_id == OWNER
    for overrides in (
        {"iss": "https://other.supabase.co/auth/v1"},
        {"aud": "service_role"},
        {"role": "service_role"},
        {"is_anonymous": True},
        {"exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
    ):
        with pytest.raises(InvalidAccessToken):
            verifier.verify(asymmetric_token(private_key, **overrides))
    with pytest.raises(InvalidAccessToken):
        verifier.verify(asymmetric_token(ed25519.Ed25519PrivateKey.generate()))


def test_legacy_verification_uses_auth_server_and_its_canonical_user_id():
    def respond(request: httpx.Request):
        assert request.url == f"{ISSUER}/user"
        assert request.headers["apikey"] == "sb_publishable_test"
        assert request.headers["authorization"].startswith("Bearer ")
        return httpx.Response(200, json={"id": OWNER})

    verifier = SupabaseTokenVerifier(
        "https://example.supabase.co", "sb_publishable_test", "legacy",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    token = jwt.encode({"sub": OTHER}, "unused-secret-with-at-least-32-bytes", algorithm="HS256")
    assert verifier.verify(token).user_id == OWNER
    invalid = SupabaseTokenVerifier(
        "https://example.supabase.co", "sb_publishable_test", "legacy",
        http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(401))),
    )
    with pytest.raises(InvalidAccessToken):
        invalid.verify(token)
    unavailable = SupabaseTokenVerifier(
        "https://example.supabase.co", "sb_publishable_test", "legacy",
        http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503))),
    )
    with pytest.raises(AuthUnavailable):
        unavailable.verify(token)


@pytest.fixture
def store():
    database = mongomock.MongoClient()["event_lab_test"]
    return MongoPortfolioStore(database=database, supported_symbol=lambda symbol: symbol == "SPY")


def saved_analysis(store):
    portfolio = store.create_portfolio(OWNER, EventPortfolioInput(name="My portfolio", holdings=[{"symbol": "SPY", "weight": 1.0}]))
    prices = {"source": "adjusted test prices", "dates": ["2026-01-01"], "adjusted_close": {"SPY": [100.0]}}
    return portfolio, "legacy-placeholder", prices


def create_pinned_draft(store, owner_id, portfolio_id, request, key=None):
    portfolio = store.get_portfolio(owner_id, portfolio_id)
    if portfolio is None:
        raise RecordNotFound(portfolio_id)
    context = {
        "portfolio_revision": portfolio.revision,
        "allocation_snapshot": portfolio.model_dump(mode="json"),
        "price_snapshot": {"source": "adjusted test prices", "dates": ["2026-01-01"],
                           "adjusted_close": {"SPY": [100.0]}},
        "analysis_snapshot": {"weights": portfolio.weights},
        "model_version": "event-v1",
        "proposed_weights": request.get("proposed_weights") or portfolio.weights,
    }
    clean_request = {name: value for name, value in request.items() if name != "analysis_id"}
    return store.create_draft(owner_id, portfolio_id,
                              {**clean_request, "portfolio_revision": context["portfolio_revision"]},
                              key, context=context)


def test_owner_scope_and_immutable_snapshots(store):
    portfolio, analysis_id, prices = saved_analysis(store)
    assert store.get_portfolio(OTHER, portfolio.portfolio_id) is None
    draft = create_pinned_draft(store, OWNER, portfolio.portfolio_id, {"analysis_id": analysis_id})
    assert store.get_draft(OTHER, draft["id"]) is None
    prices["adjusted_close"]["SPY"][0] = 999
    record = store.get_draft(OWNER, draft["id"])
    assert record["context"]["price_snapshot"]["adjusted_close"]["SPY"] == [100.0]
    store.update_portfolio(OWNER, portfolio.portfolio_id, EventPortfolioInput(name="Renamed", holdings=[{"symbol": "SPY", "weight": 1.0}]))
    assert record["context"]["allocation_snapshot"]["name"] == "My portfolio"
    assert store.get_draft(OWNER, draft["id"])["context"]["allocation_snapshot"]["name"] == "My portfolio"
    assert not store.delete_portfolio(OTHER, portfolio.portfolio_id)
    assert store.delete_portfolio(OWNER, portfolio.portfolio_id)
    assert store.get_draft(OWNER, draft["id"]) is None


def test_idempotent_draft_run_and_messages_with_leases(store):
    portfolio, analysis_id, _ = saved_analysis(store)
    request = {"analysis_id": analysis_id, "template_id": "rates"}
    draft = create_pinned_draft(store, OWNER, portfolio.portfolio_id, request, "draft-key")
    assert create_pinned_draft(store, OWNER, portfolio.portfolio_id, request, "draft-key")["id"] == draft["id"]
    with pytest.raises(IdempotencyConflict):
        create_pinned_draft(store, OWNER, portfolio.portfolio_id, {**request, "template_id": "oil"}, "draft-key")
    claimed = store.claim_draft(OWNER, draft["id"], worker_id="worker-a")
    assert claimed["attempt_count"] == 1 and claimed["lease_owner"] == "worker-a"
    with pytest.raises(InvalidTransition):
        store.complete_draft(OWNER, draft["id"], {"factors": []}, worker_id="worker-b")
    ready = store.complete_draft(OWNER, draft["id"], {"factors": []}, worker_id="worker-a")
    assert ready["revision"] == 1
    with pytest.raises(InvalidTransition):
        store.confirm_draft(OWNER, draft["id"], {"central": {}}, revision=2)
    store.confirm_draft(OWNER, draft["id"], {"central": {}}, revision=1)
    run = store.create_run(OWNER, draft["id"], "run-key")
    assert store.create_run(OWNER, draft["id"], "run-key")["id"] == run["id"]
    with pytest.raises(RecordNotFound):
        store.save_message(OTHER, run["id"], {"role": "user", "content": "hello"})
    store.claim_run(OWNER, run["id"], worker_id="worker-a")
    store.complete_run(OWNER, run["id"], {"return": 0.01}, worker_id="worker-a")
    message = store.save_message(OWNER, run["id"], {"role": "user", "content": "hello"}, "message-key")
    assert store.save_message(OWNER, run["id"], {"role": "user", "content": "hello"}, "message-key")["id"] == message["id"]
    assert len(store.list_messages(OWNER, run["id"])) == 1
    assert store.delete_run(OWNER, run["id"])
    assert store.messages.count_documents({"run_id": run["id"]}) == 0


def test_portfolio_limit_and_supported_symbols(store):
    with pytest.raises(ValueError, match="Unsupported symbols"):
        store.create_portfolio(OWNER, EventPortfolioInput(name="Bad", holdings=[{"symbol": "BAD", "weight": 1.0}]))
    with pytest.raises(ValueError, match="at most 25"):
        store.create_portfolio(OWNER, EventPortfolioInput(
            name="Too many", holdings=[{"symbol": f"S{i}", "weight": 1 / 26} for i in range(26)]
        ))


def test_expired_worker_lease_can_be_reclaimed_and_exhausted(store):
    portfolio, analysis_id, _ = saved_analysis(store)
    draft = create_pinned_draft(store, OWNER, portfolio.portfolio_id, {"analysis_id": analysis_id})
    store.claim_draft(OWNER, draft["id"], max_attempts=2, worker_id="worker-a")
    assert not store.renew_draft_lease(OWNER, draft["id"], "worker-b")
    store.drafts.update_one({"_id": draft["id"]}, {"$set": {"lease_expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}})
    reclaimed = store.claim_draft(OWNER, draft["id"], max_attempts=2, worker_id="worker-b")
    assert reclaimed["attempt_count"] == 2
    with pytest.raises(InvalidTransition):
        store.complete_draft(OWNER, draft["id"], {"factors": []}, worker_id="worker-a")
    store.drafts.update_one({"_id": draft["id"]}, {"$set": {"lease_expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}})
    assert store.expire_exhausted_jobs(max_attempts=2) == 1
    assert store.get_draft(OWNER, draft["id"])["status"] == "failed"


def test_atomic_owner_job_quota_under_concurrent_draft_requests():
    database = mongomock.MongoClient()["job_quota_test"]
    store = MongoPortfolioStore(database=database, max_active_jobs_per_owner=3)
    portfolio, analysis_id, _ = saved_analysis(store)

    def create(index):
        try:
            return create_pinned_draft(store, OWNER, portfolio.portfolio_id, {
                "analysis_id": analysis_id, "question": str(index),
            })
        except QuotaExceeded:
            return None

    with ThreadPoolExecutor(max_workers=12) as pool:
        outcomes = list(pool.map(create, range(24)))
    created = [item for item in outcomes if item is not None]
    assert len(created) == 3
    assert store.quotas.find_one({"_id": store._job_quota_id(OWNER)})["used"] == 3
    assert store.active_job_count(OWNER) == 3
    assert store.cancel_draft(OWNER, created[0]["id"])
    assert create(25) is not None
    assert store.active_job_count(OWNER) == 3


def test_atomic_run_message_quota_and_pinned_proposal():
    database = mongomock.MongoClient()["message_quota_test"]
    store = MongoPortfolioStore(database=database, max_messages_per_run=2)
    portfolio, analysis_id, _ = saved_analysis(store)
    draft = create_pinned_draft(store, OWNER, portfolio.portfolio_id, {
        "analysis_id": analysis_id, "proposed_weights": {"SPY": 1.0},
    })
    store.claim_draft(OWNER, draft["id"], worker_id="worker-a")
    store.complete_draft(OWNER, draft["id"], {"evidence": [{"source": "test"}]}, worker_id="worker-a")
    store.confirm_draft(OWNER, draft["id"], {"central": {"rates": 0.01}})
    run = store.create_run(OWNER, draft["id"])
    assert run["proposed_weights"] == {"SPY": 1.0}
    assert run["proposal_snapshot"] == {"evidence": [{"source": "test"}]}
    store.claim_run(OWNER, run["id"], worker_id="worker-a")
    store.complete_run(OWNER, run["id"], {"return": 0.01}, worker_id="worker-a")
    store.delete_draft(OWNER, draft["id"])
    assert store.get_run(OWNER, run["id"])["proposal_snapshot"] == run["proposal_snapshot"]

    def post(index):
        try:
            return store.save_message(OWNER, run["id"], {"content": str(index)})
        except QuotaExceeded:
            return None

    with ThreadPoolExecutor(max_workers=12) as pool:
        outcomes = list(pool.map(post, range(24)))
    assert sum(item is not None for item in outcomes) == 2
    assert len(store.list_messages(OWNER, run["id"])) == 2
    assert store.quotas.find_one({"_id": store._message_quota_id(OWNER, run["id"])})["used"] == 2


def test_reconcile_interrupted_reservation_and_terminal_release():
    database = mongomock.MongoClient()["reconcile_test"]
    store = MongoPortfolioStore(database=database, max_active_jobs_per_owner=1)
    portfolio, analysis_id, _ = saved_analysis(store)
    abandoned_id = "draft_abandoned"
    store._reserve_job(OWNER, abandoned_id)
    quota_id = store._job_quota_id(OWNER)
    store.quotas.update_one({"_id": quota_id}, {"$set": {
        f"reservations.{abandoned_id}.created_at": datetime.now(timezone.utc) - timedelta(minutes=1)
    }})
    assert store.reconcile_quotas() == 1
    assert store.quotas.find_one({"_id": quota_id})["used"] == 0

    draft = create_pinned_draft(store, OWNER, portfolio.portfolio_id, {"analysis_id": analysis_id})
    assert store.quotas.find_one({"_id": quota_id})["used"] == 1
    # Simulate a process dying after a durable status change but before slot release.
    store.drafts.update_one({"_id": draft["id"]}, {"$set": {"status": "ready"}})
    assert store.reconcile_quotas() == 1
    assert store.quotas.find_one({"_id": quota_id})["used"] == 0
    assert create_pinned_draft(store, OWNER, portfolio.portfolio_id, {"analysis_id": analysis_id, "question": "second"})


def test_reconcile_initializing_job_and_message_after_crash():
    database = mongomock.MongoClient()["initializing_test"]
    store = MongoPortfolioStore(database=database)
    portfolio, analysis_id, _ = saved_analysis(store)
    draft_id = "draft_interrupted"
    store._reserve_job(OWNER, draft_id)
    store.drafts.insert_one({
        "_id": draft_id, "owner_id": OWNER, "portfolio_id": portfolio.portfolio_id,
        "status": "initializing", "attempt_count": 0,
    })
    store.quotas.update_one({"_id": store._job_quota_id(OWNER)}, {"$set": {
        f"reservations.{draft_id}.created_at": datetime.now(timezone.utc) - timedelta(minutes=1)
    }})
    assert store.reconcile_quotas() == 1
    assert store.drafts.find_one({"_id": draft_id})["status"] == "pending"
    assert store.quotas.find_one({"_id": store._job_quota_id(OWNER)})["reservations"][draft_id]["state"] == "active"

    ready = create_pinned_draft(store, OWNER, portfolio.portfolio_id, {"analysis_id": analysis_id})
    store.claim_draft(OWNER, ready["id"], worker_id="worker-a")
    store.complete_draft(OWNER, ready["id"], {"evidence": []}, worker_id="worker-a")
    store.confirm_draft(OWNER, ready["id"], {"central": {}})
    run = store.create_run(OWNER, ready["id"])
    store.claim_run(OWNER, run["id"], worker_id="worker-a")
    store.complete_run(OWNER, run["id"], {"return": 0.01}, worker_id="worker-a")
    message_id = "message_interrupted"
    quota_id = store._message_quota_id(OWNER, run["id"])
    store._reserve_quota(quota_id, message_id, 100, owner_id=OWNER, run_id=run["id"], kind="messages")
    store.messages.insert_one({
        "_id": message_id, "owner_id": OWNER, "portfolio_id": portfolio.portfolio_id,
        "run_id": run["id"], "status": "initializing", "message": {"content": "saved"},
    })
    store.quotas.update_one({"_id": quota_id}, {"$set": {
        f"reservations.{message_id}.created_at": datetime.now(timezone.utc) - timedelta(minutes=1)
    }})
    assert store.reconcile_quotas() == 1
    assert store.messages.find_one({"_id": message_id})["status"] == "saved"


def test_delete_during_admission_releases_only_its_own_slot():
    database = mongomock.MongoClient()["admission_delete_test"]
    store = MongoPortfolioStore(database=database, max_active_jobs_per_owner=2)
    survivor, survivor_analysis, _ = saved_analysis(store)
    other = store.create_portfolio(OWNER, EventPortfolioInput(name="Other", holdings=[{"symbol": "SPY", "weight": 1.0}]))
    other_analysis = "legacy-placeholder"
    survivor_draft = create_pinned_draft(store, OWNER, survivor.portfolio_id, {"analysis_id": survivor_analysis})
    original_finish = store._finish_admission

    def delete_before_recheck(*args, **kwargs):
        store.delete_portfolio(OWNER, other.portfolio_id)
        return original_finish(*args, **kwargs)

    store._finish_admission = delete_before_recheck
    with pytest.raises(RecordNotFound):
        create_pinned_draft(store, OWNER, other.portfolio_id, {"analysis_id": other_analysis})
    store._finish_admission = original_finish
    quota = store.quotas.find_one({"_id": store._job_quota_id(OWNER)})
    assert quota["used"] == 1
    assert set(quota["reservations"]) == {survivor_draft["id"]}


def test_event_store_exposes_no_standalone_analysis_storage(store):
    assert not hasattr(store, "save_analysis")
    assert not hasattr(store, "get_analysis")
    assert not hasattr(store, "list_analyses")
    assert not hasattr(store, "get_analysis_record")


def test_idempotent_retry_recovers_interrupted_draft_and_run_admission(store):
    portfolio, analysis_id, _ = saved_analysis(store)
    request = {"analysis_id": analysis_id}
    draft = create_pinned_draft(store, OWNER, portfolio.portfolio_id, request, "draft-retry")
    quota_id = store._job_quota_id(OWNER)
    store.drafts.update_one({"_id": draft["id"]}, {"$set": {"status": "initializing"}})
    store.quotas.update_one({"_id": quota_id}, {"$set": {
        f"reservations.{draft['id']}.state": "pending"
    }})
    recovered = create_pinned_draft(store, OWNER, portfolio.portfolio_id, request, "draft-retry")
    assert recovered["id"] == draft["id"] and recovered["status"] == "pending"
    assert store.list_drafts(OWNER, portfolio.portfolio_id)[0]["status"] == "pending"
    store.claim_draft(OWNER, draft["id"], worker_id="worker-a")
    store.complete_draft(OWNER, draft["id"], {"evidence": []}, worker_id="worker-a")
    store.confirm_draft(OWNER, draft["id"], {"central": {}})

    run = store.create_run(OWNER, draft["id"], "run-retry")
    store.runs.update_one({"_id": run["id"]}, {"$set": {"status": "initializing"}})
    store.quotas.update_one({"_id": quota_id}, {"$set": {
        f"reservations.{run['id']}.state": "pending"
    }})
    recovered_run = store.create_run(OWNER, draft["id"], "run-retry")
    assert recovered_run["id"] == run["id"] and recovered_run["status"] == "pending"
    assert store.list_runs(OWNER, portfolio.portfolio_id)[0]["status"] == "pending"


def test_message_slot_blocks_duplicate_generation_and_survives_live_timeout():
    database = mongomock.MongoClient()["message_reservation_test"]
    store = MongoPortfolioStore(database=database, max_messages_per_run=1)
    portfolio, analysis_id, _ = saved_analysis(store)
    draft = create_pinned_draft(store, OWNER, portfolio.portfolio_id, {"analysis_id": analysis_id})
    store.claim_draft(OWNER, draft["id"], worker_id="worker-a")
    store.complete_draft(OWNER, draft["id"], {"evidence": []}, worker_id="worker-a")
    store.confirm_draft(OWNER, draft["id"], {"central": {}})
    run = store.create_run(OWNER, draft["id"])
    store.claim_run(OWNER, run["id"], worker_id="worker-a")
    store.complete_run(OWNER, run["id"], {"return": 0.01}, worker_id="worker-a")

    def reserve_same_key(_):
        try:
            return store.reserve_message_slot(OWNER, run["id"], "answer-key")
        except ReservationInProgress:
            return None

    with ThreadPoolExecutor(max_workers=12) as pool:
        reservations = list(pool.map(reserve_same_key, range(24)))
    tokens = [item for item in reservations if item is not None]
    assert len(tokens) == 1
    token = tokens[0]
    quota_id = store._message_quota_id(OWNER, run["id"])
    old_time = datetime.now(timezone.utc) - timedelta(seconds=31)
    store.message_claims.update_one({"token": token}, {"$set": {"created_at": old_time}})
    store.quotas.update_one({"_id": quota_id}, {"$set": {
        f"reservations.{token}.created_at": old_time
    }})
    with pytest.raises(ReservationInProgress):
        store.reserve_message_slot(OWNER, run["id"], "answer-key")
    with pytest.raises(QuotaExceeded):
        store.reserve_message_slot(OWNER, run["id"], "different-key")
    assert store.quotas.find_one({"_id": quota_id})["used"] == 1
    saved = store.save_message(OWNER, run["id"], {"content": "answer"}, "answer-key", reservation_id=token)
    assert saved["status"] == "saved"
    assert store.release_message_slot(OWNER, run["id"], token) is False
    assert store.quotas.find_one({"_id": quota_id})["used"] == 1
    with pytest.raises(IdempotencyConflict):
        store.reserve_message_slot(OWNER, run["id"], "answer-key")


def test_abandoned_message_claim_is_recovered_after_grace_period(store):
    portfolio, analysis_id, _ = saved_analysis(store)
    draft = create_pinned_draft(store, OWNER, portfolio.portfolio_id, {"analysis_id": analysis_id})
    store.claim_draft(OWNER, draft["id"], worker_id="worker-a")
    store.complete_draft(OWNER, draft["id"], {"evidence": []}, worker_id="worker-a")
    store.confirm_draft(OWNER, draft["id"], {"central": {}})
    run = store.create_run(OWNER, draft["id"])
    store.claim_run(OWNER, run["id"], worker_id="worker-a")
    store.complete_run(OWNER, run["id"], {"return": 0.01}, worker_id="worker-a")
    token = store.reserve_message_slot(OWNER, run["id"], "lost-key")
    old_time = datetime.now(timezone.utc) - timedelta(minutes=6)
    store.message_claims.update_one({"token": token}, {"$set": {"created_at": old_time}})
    quota_id = store._message_quota_id(OWNER, run["id"])
    store.quotas.update_one({"_id": quota_id}, {"$set": {
        f"reservations.{token}.created_at": old_time
    }})
    assert store.reconcile_quotas() == 1
    assert store.quotas.find_one({"_id": quota_id})["used"] == 0
    assert store.reserve_message_slot(OWNER, run["id"], "lost-key") != token
