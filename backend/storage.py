from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

from .schemas import AnalyticsSnapshot, Portfolio, PortfolioInput


class SnapshotNotFound(Exception):
    pass


class StalePortfolio(Exception):
    pass


class PortfolioStore:
    """Small persistent demo store; each operation owns its SQLite connection."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS portfolios (
                    portfolio_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    owner_id TEXT
                );
                CREATE TABLE IF NOT EXISTS analyses (
                    analysis_id TEXT PRIMARY KEY,
                    portfolio_id TEXT NOT NULL REFERENCES portfolios(portfolio_id),
                    created_at TEXT NOT NULL,
                    metrics TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS analysis_portfolio
                    ON analyses(portfolio_id, analysis_id);
            """)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(portfolios)")}
            if "owner_id" not in columns:
                connection.execute("ALTER TABLE portfolios ADD COLUMN owner_id TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS portfolios_owner ON portfolios(owner_id, portfolio_id)")

    @contextmanager
    def connection(self):
        with closing(sqlite3.connect(self.path, timeout=5)) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            with connection:
                yield connection

    def seed_demo(self, metrics: AnalyticsSnapshot) -> None:
        portfolio = Portfolio(
            portfolio_id="demo",
            name="Demo Portfolio",
            holdings=[{"symbol": symbol, "weight": weight} for symbol, weight in metrics.weights.items()],
            created_at=datetime.now(timezone.utc),
        )
        with self.connection() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO portfolios (portfolio_id, payload) VALUES (?, ?)",
                (portfolio.portfolio_id, portfolio.model_dump_json()),
            )

    def create(self, request: PortfolioInput, owner_id: str) -> Portfolio:
        portfolio = Portfolio(
            **request.model_dump(),
            portfolio_id="portfolio_" + uuid4().hex,
            created_at=datetime.now(timezone.utc),
        )
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO portfolios (portfolio_id, payload, owner_id) VALUES (?, ?, ?)",
                (portfolio.portfolio_id, portfolio.model_dump_json(), owner_id),
            )
        return portfolio

    def get(self, portfolio_id: str, owner_id: str) -> Portfolio | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM portfolios WHERE portfolio_id = ? AND owner_id = ?", (portfolio_id, owner_id)
            ).fetchone()
        return Portfolio.model_validate_json(row[0]) if row else None

    def update(self, portfolio_id: str, owner_id: str, request: PortfolioInput) -> Portfolio | None:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM portfolios WHERE portfolio_id = ? AND owner_id = ?",
                (portfolio_id, owner_id),
            ).fetchone()
            if row is None:
                return None
            previous = Portfolio.model_validate_json(row[0])
            updated = Portfolio(
                **request.model_dump(), portfolio_id=portfolio_id,
                created_at=previous.created_at,
            )
            connection.execute(
                "UPDATE portfolios SET payload = ? WHERE portfolio_id = ? AND owner_id = ?",
                (updated.model_dump_json(), portfolio_id, owner_id),
            )
            if updated.weights != previous.weights:
                connection.execute("DELETE FROM analyses WHERE portfolio_id = ?", (portfolio_id,))
        return updated

    def list_for_owner(self, owner_id: str) -> list[Portfolio]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM portfolios WHERE owner_id = ? ORDER BY rowid DESC", (owner_id,)
            ).fetchall()
        return [Portfolio.model_validate_json(row[0]) for row in rows]

    def delete(self, portfolio_id: str, owner_id: str) -> bool:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            owned = connection.execute(
                "SELECT 1 FROM portfolios WHERE portfolio_id = ? AND owner_id = ?",
                (portfolio_id, owner_id),
            ).fetchone()
            if owned is None:
                return False
            connection.execute("DELETE FROM analyses WHERE portfolio_id = ?", (portfolio_id,))
            connection.execute(
                "DELETE FROM portfolios WHERE portfolio_id = ? AND owner_id = ?",
                (portfolio_id, owner_id),
            )
        return True

    def save_analysis(self, metrics: AnalyticsSnapshot, owner_id: str) -> tuple[str, datetime]:
        analysis_id = "analysis_" + uuid4().hex
        created_at = datetime.now(timezone.utc)
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM portfolios WHERE portfolio_id = ? AND owner_id = ?",
                (metrics.portfolio_id, owner_id),
            ).fetchone()
            if row is None or Portfolio.model_validate_json(row[0]).weights != metrics.weights:
                raise StalePortfolio(metrics.portfolio_id)
            connection.execute(
                "INSERT INTO analyses VALUES (?, ?, ?, ?)",
                (analysis_id, metrics.portfolio_id, created_at.isoformat(), metrics.model_dump_json()),
            )
        return analysis_id, created_at

    def get_analysis(self, portfolio_id: str, analysis_id: str) -> tuple[AnalyticsSnapshot, datetime]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT metrics, created_at FROM analyses WHERE portfolio_id = ? AND analysis_id = ?",
                (portfolio_id, analysis_id),
            ).fetchone()
        if not row:
            raise SnapshotNotFound(analysis_id)
        return AnalyticsSnapshot.model_validate_json(row[0]), datetime.fromisoformat(row[1])
