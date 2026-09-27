"""Owner-scoped MongoDB records for authenticated portfolios and event runs.

Records use opaque string IDs. Every user-data query includes ``owner_id``;
the owner is supplied only by the verified API identity, never request JSON.
Analysis and run inputs are copied at creation so refreshed prices and edited
portfolios cannot alter a saved result.
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Callable
from uuid import uuid4

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from .event_schemas import EventPortfolio, EventPortfolioInput
from .schemas import AnalyticsSnapshot
from .storage import SnapshotNotFound


class IdempotencyConflict(Exception):
    """An idempotency key was already used for different input."""


class RecordNotFound(Exception):
    """No visible record belongs to this owner and ID."""


class InvalidTransition(Exception):
    """A job no longer has the expected status."""


class QuotaExceeded(Exception):
    """The configured active-job or message limit has been reached."""


class ReservationInProgress(Exception):
    """An identical idempotency key is already being processed."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _owner(owner_id: str) -> str:
    if not isinstance(owner_id, str) or not owner_id.strip():
        raise ValueError("A verified owner ID is required.")
    return owner_id


def _visible(owner_id: str, record_id: str | None = None) -> dict[str, Any]:
    query: dict[str, Any] = {"owner_id": _owner(owner_id), "deleted_at": {"$exists": False}}
    if record_id is not None:
        query["_id"] = record_id
    return query


def _public(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    result = deepcopy(document)
    result["id"] = result.pop("_id")
    result.pop("request_hash", None)
    return result


def _payload_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return sha256(serialized.encode("utf-8")).hexdigest()


def _idempotency_key(key: str | None) -> str | None:
    if key is None:
        return None
    if not isinstance(key, str) or not 1 <= len(key) <= 128 or not key.isascii():
        raise ValueError("Idempotency key must be 1–128 ASCII characters.")
    return key


class MongoPortfolioStore:
    """Synchronous store; call from FastAPI's threadpool in async routes.

    Construction creates indexes and therefore checks database availability.
    Instantiate only when the authenticated feature flag is enabled. A
    ``database`` can be passed for an already configured Mongo client.
    """

    def __init__(
        self,
        uri: str | None = None,
        database_name: str = "portfoliolens",
        *,
        database: Database | None = None,
        supported_symbol: Callable[[str], bool] | None = None,
        max_active_jobs_per_owner: int = 5,
        max_messages_per_run: int = 100,
    ) -> None:
        if database is None:
            if not uri:
                raise ValueError("MONGODB_URI is required when Mongo storage is enabled.")
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
            database = self.client[database_name]
        else:
            self.client = database.client
        self.db = database
        self.supported_symbol = supported_symbol
        self.max_active_jobs_per_owner = max_active_jobs_per_owner
        self.max_messages_per_run = max_messages_per_run
        self.portfolios = database["portfolios"]
        self.analyses = database["analyses"]
        self.analysis_counters = database["analysis_counters"]
        self.drafts = database["scenario_drafts"]
        self.runs = database["scenario_runs"]
        self.messages = database["run_messages"]
        self.message_claims = database["message_claims"]
        self.quotas = database["scenario_quotas"]
        if max_active_jobs_per_owner < 1 or max_messages_per_run < 1:
            raise ValueError("Quota limits must be positive.")
        self._ensure_indexes()
        self._last_reconciliation = _now()
        self.reconcile_quotas()

    def _ensure_indexes(self) -> None:
        self.portfolios.create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
        self.analyses.create_index([("owner_id", ASCENDING), ("portfolio_id", ASCENDING), ("sequence", DESCENDING)])
        self.drafts.create_index([("owner_id", ASCENDING), ("portfolio_id", ASCENDING), ("created_at", DESCENDING)])
        self.runs.create_index([("owner_id", ASCENDING), ("portfolio_id", ASCENDING), ("created_at", DESCENDING)])
        self.messages.create_index([("owner_id", ASCENDING), ("run_id", ASCENDING), ("created_at", ASCENDING)])
        for collection in (self.drafts, self.runs, self.messages):
            collection.create_index(
                [("owner_id", ASCENDING), ("idempotency_key", ASCENDING)],
                unique=True,
                partialFilterExpression={"idempotency_key": {"$type": "string"}},
            )
        # Workers can claim due work by status without scanning unrelated data.
        for collection in (self.drafts, self.runs):
            collection.create_index([("status", ASCENDING), ("updated_at", ASCENDING)])

    def _job_quota_id(self, owner_id: str) -> str:
        return f"jobs:{_owner(owner_id)}"

    def _message_quota_id(self, owner_id: str, run_id: str) -> str:
        return f"messages:{_owner(owner_id)}:{run_id}"

    def _reserve_quota(self, quota_id: str, record_id: str, limit: int, **scope: str) -> None:
        # A single Mongo document is the admission point. Each slot belongs to
        # one record, so cleanup and competing delete paths can release it once.
        slot_path = f"reservations.{record_id}"
        try:
            self.quotas.insert_one({"_id": quota_id, "used": 0, "reservations": {}, **scope})
        except DuplicateKeyError:
            pass
        query = {"_id": quota_id, "used": {"$lt": limit}, slot_path: {"$exists": False}}
        update = {"$inc": {"used": 1}, "$set": {slot_path: {"state": "pending", "created_at": _now()}}}
        reserved = self.quotas.find_one_and_update(query, update, return_document=ReturnDocument.AFTER)
        if reserved is None:
            # A process may have stopped after reserving a slot or after
            # finishing a job. Reconcile, then retry admission exactly once.
            self.reconcile_quotas()
            reserved = self.quotas.find_one_and_update(query, update, return_document=ReturnDocument.AFTER)
        if reserved is None:
            raise QuotaExceeded("Scenario quota reached.")

    def _activate_quota(self, quota_id: str, record_id: str) -> bool:
        slot_path = f"reservations.{record_id}"
        changed = self.quotas.update_one(
            {"_id": quota_id, f"{slot_path}.state": "pending"},
            {"$set": {f"{slot_path}.state": "active"}},
        )
        return bool(changed.modified_count or self.quotas.find_one(
            {"_id": quota_id, f"{slot_path}.state": "active"}, {"_id": 1}
        ))

    def _release_quota(self, quota_id: str, record_id: str, *, pending_only: bool = False) -> bool:
        slot_path = f"reservations.{record_id}"
        query: dict[str, Any] = {"_id": quota_id, slot_path: {"$exists": True}}
        if pending_only:
            query[f"{slot_path}.state"] = "pending"
        result = self.quotas.update_one(
            query, {"$unset": {slot_path: ""}, "$inc": {"used": -1}}
        )
        return result.modified_count == 1

    def _reserve_job(self, owner_id: str, record_id: str) -> None:
        self._reserve_quota(
            self._job_quota_id(owner_id), record_id, self.max_active_jobs_per_owner,
            owner_id=owner_id, kind="jobs",
        )

    def _release_job(self, owner_id: str, record_id: str) -> bool:
        return self._release_quota(self._job_quota_id(owner_id), record_id)

    def reconcile_quotas(self, stale_after_seconds: int = 30, *, record_id: str | None = None) -> int:
        """Repair interrupted admissions and terminal releases without freeing live slots.

        A pending reservation is fenced by its per-record state: reconciliation
        may remove it only while it remains pending, and a producer must change
        it to active before publishing the record. A producer that loses this
        race deletes its initializing record. Active slots are retained for
        queued/running jobs and saved messages.
        """
        if stale_after_seconds < 0:
            raise ValueError("Reconciliation delay must be nonnegative.")
        checked_at = _now()
        if record_id is None:
            self._last_reconciliation = checked_at
        repaired = 0
        for quota in self.quotas.find({}):
            quota_id = quota["_id"]
            owner_id = quota.get("owner_id")
            kind = quota.get("kind")
            if not owner_id or kind not in {"jobs", "messages"}:
                continue
            for slot_id, slot in list(quota.get("reservations", {}).items()):
                if record_id is not None and slot_id != record_id:
                    continue
                if kind == "messages":
                    collection = self.messages
                    parent = self.runs.find_one(_visible(owner_id, quota.get("run_id", "")))
                    parent_ok = parent is not None and self.get_portfolio(
                        owner_id, parent.get("portfolio_id", "")) is not None
                else:
                    collection = self.drafts if slot_id.startswith("draft_") else self.runs
                    parent_ok = True
                record = collection.find_one({"_id": slot_id, "owner_id": owner_id})
                if kind == "jobs" and record is not None:
                    parent_ok = self.get_portfolio(owner_id, record.get("portfolio_id", "")) is not None
                state = slot.get("state")
                created_at = slot.get("created_at")
                if isinstance(created_at, datetime) and created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                stale = not isinstance(created_at, datetime) or (
                    checked_at - created_at >= timedelta(seconds=stale_after_seconds)
                )
                # An answer request can legitimately spend up to the provider
                # timeout generating before its message is inserted. Give that
                # reservation a longer recovery window than a local DB write.
                if kind == "messages" and record is None and isinstance(created_at, datetime):
                    stale = checked_at - created_at >= timedelta(minutes=5)
                if record is None or record.get("deleted_at") is not None or not parent_ok:
                    if state == "active" or stale:
                        if record is not None and not parent_ok:
                            collection.delete_one({"_id": slot_id, "owner_id": owner_id})
                        if self._release_quota(quota_id, slot_id, pending_only=state == "pending"):
                            repaired += 1
                    continue
                status = record.get("status")
                if kind == "jobs" and status not in {"initializing", "pending", "running"}:
                    if self._release_quota(quota_id, slot_id):
                        repaired += 1
                    continue
                if kind == "messages" and status not in {"initializing", "saved"}:
                    if self._release_quota(quota_id, slot_id):
                        repaired += 1
                    continue
                if status == "initializing" and (state == "active" or stale):
                    if self._activate_quota(quota_id, slot_id):
                        collection.update_one(
                            {"_id": slot_id, "owner_id": owner_id, "status": "initializing",
                             "deleted_at": {"$exists": False}},
                            {"$set": {"status": "saved" if kind == "messages" else "pending",
                                      "updated_at": _now()}},
                        )
                        repaired += 1
                elif state == "pending" and stale:
                    if self._activate_quota(quota_id, slot_id):
                        repaired += 1
        for claim in self.message_claims.find({}):
            token = claim["token"]
            if record_id is not None and token != record_id:
                continue
            message = self.messages.find_one({"_id": token, "owner_id": claim["owner_id"]})
            quota_id = self._message_quota_id(claim["owner_id"], claim["run_id"])
            slot_exists = self.quotas.find_one({"_id": quota_id, f"reservations.{token}": {"$exists": True}})
            created_at = claim.get("created_at")
            if isinstance(created_at, datetime) and created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            stale_claim = not isinstance(created_at, datetime) or (
                checked_at - created_at >= timedelta(minutes=5)
            )
            if (message is not None and message.get("status") == "saved") or (slot_exists is None and stale_claim):
                self.message_claims.delete_one({"_id": claim["_id"], "token": token})
        return repaired

    def _maybe_reconcile_quotas(self) -> None:
        if _now() - self._last_reconciliation >= timedelta(seconds=60):
            self.reconcile_quotas()

    def _validate_portfolio_input(self, request: EventPortfolioInput) -> None:
        if len(request.holdings) > 25:
            raise ValueError("A portfolio can have at most 25 holdings.")
        if self.supported_symbol is not None:
            unsupported = [item.symbol for item in request.holdings if not self.supported_symbol(item.symbol)]
            if unsupported:
                raise ValueError(f"Unsupported symbols: {', '.join(unsupported)}")

    def create_portfolio(self, owner_id: str, request: EventPortfolioInput) -> EventPortfolio:
        _owner(owner_id)
        self._validate_portfolio_input(request)
        portfolio = EventPortfolio(
            **request.model_dump(), portfolio_id="portfolio_" + uuid4().hex, created_at=_now()
        )
        self.portfolios.insert_one({
            "_id": portfolio.portfolio_id,
            "owner_id": owner_id,
            "payload": portfolio.model_dump(mode="json"),
            "created_at": portfolio.created_at,
            "updated_at": portfolio.created_at,
        })
        return portfolio

    def list_portfolios(self, owner_id: str) -> list[EventPortfolio]:
        cursor = self.portfolios.find(_visible(owner_id)).sort("created_at", DESCENDING)
        return [EventPortfolio.model_validate(doc["payload"]) for doc in cursor]

    def get_portfolio(self, owner_id: str, portfolio_id: str) -> EventPortfolio | None:
        doc = self.portfolios.find_one(_visible(owner_id, portfolio_id))
        return EventPortfolio.model_validate(doc["payload"]) if doc else None

    def update_portfolio(self, owner_id: str, portfolio_id: str, request: EventPortfolioInput) -> EventPortfolio:
        self._validate_portfolio_input(request)
        current = self.get_portfolio(owner_id, portfolio_id)
        if current is None:
            raise RecordNotFound(portfolio_id)
        updated = EventPortfolio(**request.model_dump(), portfolio_id=portfolio_id, created_at=current.created_at)
        result = self.portfolios.find_one_and_update(
            _visible(owner_id, portfolio_id),
            {"$set": {"payload": updated.model_dump(mode="json"), "updated_at": _now()}},
            return_document=ReturnDocument.AFTER,
        )
        if result is None:
            raise RecordNotFound(portfolio_id)
        return EventPortfolio.model_validate(result["payload"])

    def delete_portfolio(self, owner_id: str, portfolio_id: str) -> bool:
        # Tombstone first. Concurrent new child writes fail their parent lookup;
        # all subsequent reads exclude deleted records even during cleanup.
        result = self.portfolios.find_one_and_update(
            _visible(owner_id, portfolio_id), {"$set": {"deleted_at": _now()}}
        )
        if result is None:
            return False
        scope = {"owner_id": _owner(owner_id), "portfolio_id": portfolio_id}
        for run in self.runs.find(scope, {"_id": 1}):
            self.delete_run(owner_id, run["_id"])
        for draft in self.drafts.find(scope, {"_id": 1}):
            self.delete_draft(owner_id, draft["_id"])
        self.messages.delete_many(scope)
        self.runs.delete_many(scope)
        self.drafts.delete_many(scope)
        self.analyses.delete_many(scope)
        self.portfolios.delete_one({"_id": portfolio_id, "owner_id": owner_id, "deleted_at": {"$exists": True}})
        return True

    def save_analysis(
        self,
        owner_id: str,
        metrics: AnalyticsSnapshot,
        allocation_snapshot: dict[str, Any] | None = None,
        price_snapshot: dict[str, Any] | None = None,
        model_version: str = "unknown",
    ) -> tuple[str, datetime]:
        portfolio = self.get_portfolio(owner_id, metrics.portfolio_id)
        if portfolio is None:
            raise RecordNotFound(metrics.portfolio_id)
        if metrics.weights != portfolio.weights:
            raise ValueError("Analysis allocation must match the selected portfolio.")
        allocation = portfolio.model_dump(mode="json")
        if allocation_snapshot is not None and allocation_snapshot != allocation:
            raise ValueError("Allocation snapshot must match the saved portfolio.")
        if not isinstance(allocation, dict) or not isinstance(price_snapshot, dict) or not price_snapshot:
            raise ValueError("Allocation and adjusted-price snapshots are required.")
        if not isinstance(model_version, str) or not model_version.strip():
            raise ValueError("A model version is required.")
        analysis_id, created_at = "analysis_" + uuid4().hex, _now()
        counter = self.analysis_counters.find_one_and_update(
            {"_id": f"{owner_id}:{metrics.portfolio_id}"},
            {"$inc": {"sequence": 1}}, upsert=True, return_document=ReturnDocument.AFTER,
        )
        self.analyses.insert_one({
            "_id": analysis_id,
            "owner_id": _owner(owner_id),
            "portfolio_id": metrics.portfolio_id,
            "created_at": created_at,
            "sequence": counter["sequence"],
            "metrics": metrics.model_dump(mode="json"),
            "allocation_snapshot": deepcopy(allocation),
            "price_snapshot": deepcopy(price_snapshot),
            "model_version": model_version,
        })
        return analysis_id, created_at

    def get_analysis(self, owner_id: str, portfolio_id: str, analysis_id: str) -> tuple[AnalyticsSnapshot, datetime]:
        record = self.get_analysis_record(owner_id, portfolio_id, analysis_id)
        if record is None:
            raise SnapshotNotFound(analysis_id)
        return AnalyticsSnapshot.model_validate(record["metrics"]), record["created_at"]

    def list_analyses(self, owner_id: str, portfolio_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Newest saved analyses, including their immutable metrics, for one owner."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            raise ValueError("Analysis list limit must be between 1 and 50.")
        if self.get_portfolio(owner_id, portfolio_id) is None:
            raise RecordNotFound(portfolio_id)
        query = {**_visible(owner_id), "portfolio_id": portfolio_id}
        cursor = self.analyses.find(
            query, {"_id": 1, "portfolio_id": 1, "created_at": 1, "metrics": 1,
                    "price_snapshot.provenance": 1}
        ).sort("sequence", DESCENDING).limit(limit)
        return [_public(doc) for doc in cursor]

    def get_analysis_record(self, owner_id: str, portfolio_id: str, analysis_id: str) -> dict[str, Any] | None:
        if self.get_portfolio(owner_id, portfolio_id) is None:
            return None
        query = _visible(owner_id, analysis_id)
        query["portfolio_id"] = portfolio_id
        return _public(self.analyses.find_one(query))

    def _insert_idempotent(
        self,
        collection: Any,
        record_id: str,
        owner_id: str,
        payload: dict[str, Any],
        idempotency_key: str | None,
        *,
        initializing: bool = False,
    ) -> tuple[dict[str, Any], bool]:
        key = _idempotency_key(idempotency_key)
        content_hash = _payload_hash(payload)
        now = _now()
        doc = {
            "_id": record_id,
            "owner_id": _owner(owner_id),
            "idempotency_key": key,
            "request_hash": content_hash,
            "created_at": now,
            "updated_at": now,
            **deepcopy(payload),
        }
        if initializing:
            doc["status"] = "initializing"
        if key is None:
            doc.pop("idempotency_key")
        try:
            collection.insert_one(doc)
        except DuplicateKeyError as exc:
            if key is None:
                raise
            existing = self._existing_idempotent(collection, owner_id, key, payload)
            if existing is None:
                raise IdempotencyConflict(key) from exc
            return existing, False
        return _public(doc), True

    def _finish_admission(
        self, collection: Any, quota_id: str, owner_id: str, record_id: str,
        *, ready_status: str, parent_exists: Callable[[], bool], parent_id: str,
    ) -> dict[str, Any]:
        if not parent_exists() or not self._activate_quota(quota_id, record_id):
            collection.delete_one({"_id": record_id, "owner_id": owner_id, "status": "initializing"})
            self._release_quota(quota_id, record_id)
            raise RecordNotFound(parent_id)
        collection.update_one(
            {"_id": record_id, "owner_id": owner_id, "status": "initializing", "deleted_at": {"$exists": False}},
            {"$set": {"status": ready_status, "updated_at": _now()}},
        )
        doc = collection.find_one({"_id": record_id, "owner_id": owner_id, "deleted_at": {"$exists": False}})
        if doc is None:
            self._release_quota(quota_id, record_id)
            raise RecordNotFound(parent_id)
        return _public(doc)

    def _existing_idempotent(
        self, collection: Any, owner_id: str, key: str | None, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        key = _idempotency_key(key)
        if key is None:
            return None
        existing = collection.find_one({"owner_id": _owner(owner_id), "idempotency_key": key})
        if existing is None:
            return None
        if existing.get("request_hash") != _payload_hash(payload):
            raise IdempotencyConflict(key)
        if existing.get("status") == "initializing":
            # A retry may arrive after the insert but before admission was
            # published. Finish that admission through the slot fence; never
            # return the internal status to a client or strand it from workers.
            self.reconcile_quotas(stale_after_seconds=0, record_id=existing["_id"])
            existing = collection.find_one({"owner_id": owner_id, "idempotency_key": key})
            if existing is None:
                return None
            if existing.get("status") == "initializing":
                quota_id = (self._message_quota_id(owner_id, existing["run_id"])
                            if collection == self.messages else self._job_quota_id(owner_id))
                if self.quotas.find_one({"_id": quota_id, f"reservations.{existing['_id']}": {"$exists": True}}) is None:
                    collection.delete_one({"_id": existing["_id"], "owner_id": owner_id, "status": "initializing"})
                    return None
                raise ReservationInProgress(key)
        return _public(existing)

    def create_draft(
        self,
        owner_id: str,
        portfolio_id: str,
        request: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if self.get_portfolio(owner_id, portfolio_id) is None:
            raise RecordNotFound(portfolio_id)
        if not isinstance(request, dict) or not request:
            raise ValueError("Draft request must be a nonempty object.")
        analysis_id = request.get("analysis_id")
        if not isinstance(analysis_id, str) or self.get_analysis_record(owner_id, portfolio_id, analysis_id) is None:
            raise SnapshotNotFound(str(analysis_id))
        payload = {
            "portfolio_id": portfolio_id,
            "status": "pending",
            "attempt_count": 0,
            "request": deepcopy(request),
        }
        existing = self._existing_idempotent(self.drafts, owner_id, idempotency_key, payload)
        if existing is not None:
            return existing
        draft_id = "draft_" + uuid4().hex
        self._reserve_job(owner_id, draft_id)
        try:
            record, inserted = self._insert_idempotent(
                self.drafts, draft_id, owner_id, payload, idempotency_key, initializing=True
            )
        except Exception:
            self._release_job(owner_id, draft_id)
            raise
        if not inserted:
            self._release_job(owner_id, draft_id)
            return record
        return self._finish_admission(
            self.drafts, self._job_quota_id(owner_id), owner_id, draft_id,
            ready_status="pending", parent_exists=lambda: self.get_portfolio(owner_id, portfolio_id) is not None,
            parent_id=portfolio_id,
        )

    def get_draft(self, owner_id: str, draft_id: str) -> dict[str, Any] | None:
        doc = self.drafts.find_one(_visible(owner_id, draft_id))
        if doc and doc.get("status") == "initializing":
            self.reconcile_quotas(stale_after_seconds=0, record_id=draft_id)
            doc = self.drafts.find_one(_visible(owner_id, draft_id))
        if doc and doc.get("status") == "initializing":
            return None
        if doc and self.get_portfolio(owner_id, doc["portfolio_id"]) is not None:
            return _public(doc)
        return None

    def list_drafts(self, owner_id: str, portfolio_id: str) -> list[dict[str, Any]]:
        if self.get_portfolio(owner_id, portfolio_id) is None:
            raise RecordNotFound(portfolio_id)
        query = {**_visible(owner_id), "portfolio_id": portfolio_id}
        for doc in self.drafts.find({**query, "status": "initializing"}, {"_id": 1}):
            self.reconcile_quotas(stale_after_seconds=0, record_id=doc["_id"])
        return [_public(doc) for doc in self.drafts.find(
            {**query, "status": {"$ne": "initializing"}}
        ).sort("created_at", DESCENDING)]

    def _claim(
        self,
        collection: Any,
        worker_id: str,
        owner_id: str | None = None,
        record_id: str | None = None,
        lease_seconds: int = 120,
        max_attempts: int = 3,
    ) -> dict[str, Any] | None:
        if not worker_id or not 1 <= lease_seconds <= 3600 or not 1 <= max_attempts <= 20:
            raise ValueError("Invalid worker lease or retry limit.")
        now = _now()
        query: dict[str, Any] = {
            "deleted_at": {"$exists": False},
            "attempt_count": {"$lt": max_attempts},
            "$or": [
                {"status": "pending"},
                {"status": "running", "lease_expires_at": {"$lte": now}},
            ],
        }
        if owner_id is not None:
            query["owner_id"] = _owner(owner_id)
        if record_id is not None:
            query["_id"] = record_id
        doc = collection.find_one_and_update(
            query,
            {"$set": {
                "status": "running", "lease_owner": worker_id,
                "lease_expires_at": now + timedelta(seconds=lease_seconds), "updated_at": now,
            }, "$inc": {"attempt_count": 1}},
            sort=[("created_at", ASCENDING)],
            return_document=ReturnDocument.AFTER,
        )
        return _public(doc)

    def claim_draft(
        self, owner_id: str, draft_id: str, max_attempts: int = 3,
        *, worker_id: str = "worker", lease_seconds: int = 120,
    ) -> dict[str, Any]:
        doc = self._claim(self.drafts, worker_id, owner_id, draft_id, lease_seconds, max_attempts)
        if doc is None:
            raise InvalidTransition(draft_id)
        return doc

    def claim_next_draft(self, worker_id: str, *, lease_seconds: int = 120, max_attempts: int = 3) -> dict[str, Any] | None:
        self._maybe_reconcile_quotas()
        return self._claim(self.drafts, worker_id, lease_seconds=lease_seconds, max_attempts=max_attempts)

    def renew_draft_lease(self, owner_id: str, draft_id: str, worker_id: str, lease_seconds: int = 120) -> bool:
        return self._renew_lease(self.drafts, owner_id, draft_id, worker_id, lease_seconds)

    def complete_draft(
        self, owner_id: str, draft_id: str, proposal: dict[str, Any], *, worker_id: str
    ) -> dict[str, Any]:
        if not isinstance(proposal, dict) or not proposal:
            raise ValueError("A proposal is required.")
        query = {**_visible(owner_id, draft_id), "status": "running", "lease_owner": worker_id,
                 "lease_expires_at": {"$gt": _now()}}
        doc = self.drafts.find_one_and_update(
            query,
            {"$set": {"status": "ready", "proposal": deepcopy(proposal), "revision": 1, "updated_at": _now()},
             "$unset": {"lease_owner": "", "lease_expires_at": ""}},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            raise InvalidTransition(draft_id)
        self._release_job(owner_id, draft_id)
        return _public(doc)

    def fail_draft(
        self, owner_id: str, draft_id: str, error: str, *, worker_id: str,
        retryable: bool = False, max_attempts: int = 3,
    ) -> dict[str, Any]:
        return self._fail_job(self.drafts, owner_id, draft_id, error, worker_id, retryable, max_attempts)

    def confirm_draft(
        self, owner_id: str, draft_id: str, confirmed_shocks: dict[str, Any], *, revision: int | None = None
    ) -> dict[str, Any]:
        if not isinstance(confirmed_shocks, dict) or not confirmed_shocks:
            raise ValueError("Confirmed shocks are required.")
        query = {**_visible(owner_id, draft_id), "status": "ready"}
        if revision is not None:
            query["revision"] = revision
        doc = self.drafts.find_one_and_update(
            query,
            {"$set": {"status": "confirmed", "confirmed_shocks": deepcopy(confirmed_shocks), "updated_at": _now()}},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            raise InvalidTransition(draft_id)
        return _public(doc)

    def cancel_draft(self, owner_id: str, draft_id: str) -> bool:
        doc = self.drafts.find_one_and_update(
            {**_visible(owner_id, draft_id), "status": {"$in": ["pending", "running", "ready"]}},
            {"$set": {"status": "cancelled", "updated_at": _now()}},
        )
        if doc is None:
            return False
        if doc["status"] in {"initializing", "pending", "running"}:
            self._release_job(owner_id, draft_id)
        return True

    def delete_draft(self, owner_id: str, draft_id: str) -> bool:
        doc = self.drafts.find_one_and_update(_visible(owner_id, draft_id), {"$set": {"deleted_at": _now()}})
        if doc is None:
            return False
        if doc["status"] in {"initializing", "pending", "running"}:
            self._release_job(owner_id, draft_id)
        self.drafts.delete_one({"_id": draft_id, "owner_id": owner_id, "deleted_at": {"$exists": True}})
        return True

    def create_run(
        self,
        owner_id: str,
        draft_id: str,
        analysis_id: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        draft = self.get_draft(owner_id, draft_id)
        if draft is None or draft["status"] != "confirmed":
            raise InvalidTransition(draft_id)
        portfolio_id = draft["portfolio_id"]
        analysis = self.get_analysis_record(owner_id, portfolio_id, analysis_id)
        if analysis is None:
            raise SnapshotNotFound(analysis_id)
        if draft["request"].get("analysis_id") != analysis_id:
            raise ValueError("Run analysis must match the confirmed draft.")
        payload = {
            "portfolio_id": portfolio_id,
            "draft_id": draft_id,
            "analysis_id": analysis_id,
            "status": "pending",
            "attempt_count": 0,
            "confirmed_shocks": deepcopy(draft["confirmed_shocks"]),
            "allocation_snapshot": deepcopy(analysis["allocation_snapshot"]),
            "price_snapshot": deepcopy(analysis["price_snapshot"]),
            "analysis_snapshot": deepcopy(analysis["metrics"]),
            "model_version": analysis["model_version"],
            "proposed_weights": deepcopy(draft["request"].get("proposed_weights") or analysis["metrics"]["weights"]),
            "proposal_snapshot": deepcopy(draft["proposal"]),
        }
        existing = self._existing_idempotent(self.runs, owner_id, idempotency_key, payload)
        if existing is not None:
            return existing
        run_id = "run_" + uuid4().hex
        self._reserve_job(owner_id, run_id)
        try:
            record, inserted = self._insert_idempotent(
                self.runs, run_id, owner_id, payload, idempotency_key, initializing=True
            )
        except Exception:
            self._release_job(owner_id, run_id)
            raise
        if not inserted:
            self._release_job(owner_id, run_id)
            return record
        return self._finish_admission(
            self.runs, self._job_quota_id(owner_id), owner_id, run_id,
            ready_status="pending", parent_exists=lambda: self.get_portfolio(owner_id, portfolio_id) is not None,
            parent_id=portfolio_id,
        )

    def get_run(self, owner_id: str, run_id: str) -> dict[str, Any] | None:
        doc = self.runs.find_one(_visible(owner_id, run_id))
        if doc and doc.get("status") == "initializing":
            self.reconcile_quotas(stale_after_seconds=0, record_id=run_id)
            doc = self.runs.find_one(_visible(owner_id, run_id))
        if doc and doc.get("status") == "initializing":
            return None
        if doc and self.get_portfolio(owner_id, doc["portfolio_id"]) is not None:
            return _public(doc)
        return None

    def list_runs(self, owner_id: str, portfolio_id: str) -> list[dict[str, Any]]:
        if self.get_portfolio(owner_id, portfolio_id) is None:
            raise RecordNotFound(portfolio_id)
        query = {**_visible(owner_id), "portfolio_id": portfolio_id}
        for doc in self.runs.find({**query, "status": "initializing"}, {"_id": 1}):
            self.reconcile_quotas(stale_after_seconds=0, record_id=doc["_id"])
        return [_public(doc) for doc in self.runs.find(
            {**query, "status": {"$ne": "initializing"}}
        ).sort("created_at", DESCENDING)]

    def claim_run(
        self, owner_id: str, run_id: str, max_attempts: int = 3,
        *, worker_id: str = "worker", lease_seconds: int = 120,
    ) -> dict[str, Any]:
        doc = self._claim(self.runs, worker_id, owner_id, run_id, lease_seconds, max_attempts)
        if doc is None:
            raise InvalidTransition(run_id)
        return doc

    def claim_next_run(self, worker_id: str, *, lease_seconds: int = 120, max_attempts: int = 3) -> dict[str, Any] | None:
        self._maybe_reconcile_quotas()
        return self._claim(self.runs, worker_id, lease_seconds=lease_seconds, max_attempts=max_attempts)

    def renew_run_lease(self, owner_id: str, run_id: str, worker_id: str, lease_seconds: int = 120) -> bool:
        return self._renew_lease(self.runs, owner_id, run_id, worker_id, lease_seconds)

    def _renew_lease(self, collection: Any, owner_id: str, record_id: str, worker_id: str, lease_seconds: int) -> bool:
        if not worker_id or not 1 <= lease_seconds <= 3600:
            raise ValueError("Invalid worker lease.")
        now = _now()
        return collection.update_one(
            {**_visible(owner_id, record_id), "status": "running", "lease_owner": worker_id,
             "lease_expires_at": {"$gt": now}},
            {"$set": {"lease_expires_at": now + timedelta(seconds=lease_seconds), "updated_at": now}},
        ).modified_count == 1

    def complete_run(
        self, owner_id: str, run_id: str, result: dict[str, Any], *, worker_id: str
    ) -> dict[str, Any]:
        if not isinstance(result, dict) or not result:
            raise ValueError("Calculated run result is required.")
        query = {**_visible(owner_id, run_id), "status": "running", "lease_owner": worker_id,
                 "lease_expires_at": {"$gt": _now()}}
        doc = self.runs.find_one_and_update(
            query,
            {"$set": {"status": "completed", "result": deepcopy(result), "updated_at": _now()},
             "$unset": {"lease_owner": "", "lease_expires_at": ""}},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            raise InvalidTransition(run_id)
        self._release_job(owner_id, run_id)
        return _public(doc)

    def fail_run(
        self, owner_id: str, run_id: str, error: str, *, worker_id: str,
        retryable: bool = False, max_attempts: int = 3,
    ) -> dict[str, Any]:
        return self._fail_job(self.runs, owner_id, run_id, error, worker_id, retryable, max_attempts)

    def _fail_job(
        self, collection: Any, owner_id: str, record_id: str, error: str,
        worker_id: str, retryable: bool, max_attempts: int,
    ) -> dict[str, Any]:
        current = collection.find_one({**_visible(owner_id, record_id), "status": "running", "lease_owner": worker_id})
        if current is None:
            raise InvalidTransition(record_id)
        status = "pending" if retryable and current["attempt_count"] < max_attempts else "failed"
        doc = collection.find_one_and_update(
            {**_visible(owner_id, record_id), "status": "running", "lease_owner": worker_id},
            {"$set": {"status": status, "last_error": str(error)[:500], "updated_at": _now()},
             "$unset": {"lease_owner": "", "lease_expires_at": ""}},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            raise InvalidTransition(record_id)
        if status == "failed":
            self._release_job(owner_id, record_id)
        return _public(doc)

    def active_job_count(self, owner_id: str) -> int:
        query = {**_visible(owner_id), "status": {"$in": ["pending", "running"]}}
        return self.drafts.count_documents(query) + self.runs.count_documents(query)

    def expire_exhausted_jobs(self, max_attempts: int = 3) -> int:
        """Mark expired leases that have used their last attempt as failed."""
        if not 1 <= max_attempts <= 20:
            raise ValueError("Invalid retry limit.")
        now = _now()
        total = 0
        for collection in (self.drafts, self.runs):
            query = {"status": "running", "lease_expires_at": {"$lte": now},
                     "attempt_count": {"$gte": max_attempts}, "deleted_at": {"$exists": False}}
            for candidate in collection.find(query, {"_id": 1, "owner_id": 1}):
                doc = collection.find_one_and_update(
                    {**query, "_id": candidate["_id"], "owner_id": candidate["owner_id"]},
                    {"$set": {"status": "failed", "last_error": "Worker lease expired after retry limit.",
                              "updated_at": now},
                     "$unset": {"lease_owner": "", "lease_expires_at": ""}},
                )
                if doc is not None:
                    self._release_job(candidate["owner_id"], candidate["_id"])
                    total += 1
        return total

    def cancel_run(self, owner_id: str, run_id: str) -> bool:
        doc = self.runs.find_one_and_update(
            {**_visible(owner_id, run_id), "status": {"$in": ["pending", "running"]}},
            {"$set": {"status": "cancelled", "updated_at": _now()}},
        )
        if doc is None:
            return False
        self._release_job(owner_id, run_id)
        return True

    def delete_run(self, owner_id: str, run_id: str) -> bool:
        doc = self.runs.find_one_and_update(_visible(owner_id, run_id), {"$set": {"deleted_at": _now()}})
        if doc is None:
            return False
        if doc["status"] in {"initializing", "pending", "running"}:
            self._release_job(owner_id, run_id)
        self.messages.delete_many({"owner_id": owner_id, "run_id": run_id})
        self.message_claims.delete_many({"owner_id": owner_id, "run_id": run_id})
        self.quotas.delete_one({"_id": self._message_quota_id(owner_id, run_id)})
        self.runs.delete_one({"_id": run_id, "owner_id": owner_id, "deleted_at": {"$exists": True}})
        return True

    def reserve_message_slot(self, owner_id: str, run_id: str, idempotency_key: str | None = None) -> str:
        """Atomically admit one chat request before any answer generation.

        A keyed request also holds a unique owner-wide claim, so a concurrent
        retry cannot receive a second slot or run the answer generator twice.
        The returned token is private to the server-side caller.
        """
        run = self.get_run(owner_id, run_id)
        if run is None or run["status"] != "completed":
            raise RecordNotFound(run_id)
        key = _idempotency_key(idempotency_key)
        token = "message_" + uuid4().hex
        claim_id = None
        if key is not None:
            claim_id = sha256(json.dumps([owner_id, key]).encode("utf-8")).hexdigest()
            existing = self.messages.find_one({"owner_id": owner_id, "idempotency_key": key})
            if existing is not None:
                if existing.get("status") == "initializing":
                    self.reconcile_quotas(stale_after_seconds=0, record_id=existing["_id"])
                    existing = self.messages.find_one({"owner_id": owner_id, "idempotency_key": key})
                if existing is not None:
                    raise IdempotencyConflict(key)
            claim = {"_id": claim_id, "owner_id": owner_id, "run_id": run_id,
                     "token": token, "created_at": _now()}
            try:
                self.message_claims.insert_one(claim)
            except DuplicateKeyError as exc:
                old = self.message_claims.find_one({"_id": claim_id})
                if old is not None:
                    created_at = old.get("created_at")
                    if isinstance(created_at, datetime) and created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    if isinstance(created_at, datetime) and _now() - created_at >= timedelta(minutes=5):
                        self.reconcile_quotas()
                        self.release_message_slot(old["owner_id"], old["run_id"], old["token"])
                existing = self.messages.find_one({"owner_id": owner_id, "idempotency_key": key})
                if existing is not None:
                    raise IdempotencyConflict(key) from exc
                raise ReservationInProgress(key) from exc
        quota_id = self._message_quota_id(owner_id, run_id)
        try:
            self._reserve_quota(
                quota_id, token, self.max_messages_per_run,
                owner_id=owner_id, run_id=run_id, kind="messages",
            )
        except Exception:
            if claim_id is not None:
                self.message_claims.delete_one({"_id": claim_id, "token": token})
            raise
        # Parent deletion or a status change can race the two durable writes.
        # Return no token for an orphan; the caller will not start generation.
        if self.get_run(owner_id, run_id) is None:
            self.release_message_slot(owner_id, run_id, token)
            raise RecordNotFound(run_id)
        return token

    def release_message_slot(self, owner_id: str, run_id: str, reservation_id: str) -> bool:
        """Drop an unused slot; a saved message's active slot stays counted."""
        released = self._release_quota(
            self._message_quota_id(owner_id, run_id), reservation_id, pending_only=True,
        )
        self.message_claims.delete_one({"owner_id": _owner(owner_id), "run_id": run_id,
                                        "token": reservation_id})
        return released

    def save_message(
        self,
        owner_id: str,
        run_id: str,
        message: dict[str, Any],
        idempotency_key: str | None = None,
        *,
        reservation_id: str | None = None,
    ) -> dict[str, Any]:
        run = self.get_run(owner_id, run_id)
        if run is None or run["status"] != "completed":
            raise RecordNotFound(run_id)
        if not isinstance(message, dict) or not message:
            raise ValueError("Message must be a nonempty object.")
        payload = {
            "portfolio_id": run["portfolio_id"], "run_id": run_id, "message": deepcopy(message)
        }
        existing = self._existing_idempotent(self.messages, owner_id, idempotency_key, payload)
        if existing is not None:
            return existing
        quota_id = self._message_quota_id(owner_id, run_id)
        message_id = reservation_id or "message_" + uuid4().hex
        if reservation_id is None:
            self._reserve_quota(
                quota_id, message_id, self.max_messages_per_run,
                owner_id=owner_id, run_id=run_id, kind="messages",
            )
        elif self.quotas.find_one({"_id": quota_id,
                                   f"reservations.{message_id}.state": "pending"}) is None:
            raise InvalidTransition(message_id)
        try:
            record, inserted = self._insert_idempotent(
                self.messages, message_id, owner_id, payload, idempotency_key, initializing=True
            )
        except Exception:
            self.release_message_slot(owner_id, run_id, message_id)
            raise
        if not inserted:
            self.release_message_slot(owner_id, run_id, message_id)
            return record
        saved = self._finish_admission(
            self.messages, quota_id, owner_id, message_id,
            ready_status="saved", parent_exists=lambda: self.get_run(owner_id, run_id) is not None,
            parent_id=run_id,
        )
        self.message_claims.delete_one({"owner_id": owner_id, "run_id": run_id, "token": message_id})
        return saved

    def list_messages(self, owner_id: str, run_id: str) -> list[dict[str, Any]]:
        if self.get_run(owner_id, run_id) is None:
            raise RecordNotFound(run_id)
        query = {**_visible(owner_id), "run_id": run_id}
        for doc in self.messages.find({**query, "status": "initializing"}, {"_id": 1}):
            self.reconcile_quotas(stale_after_seconds=0, record_id=doc["_id"])
        return [_public(doc) for doc in self.messages.find(
            {**query, "status": "saved"}
        ).sort("created_at", ASCENDING)]
