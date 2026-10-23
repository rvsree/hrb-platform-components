"""Mechanism-level tests for the Postgres connection-plumbing adaptation
(ROADMAP.md Phase 1's spec) - confirms InterviewQaStore calls
hrb_common.db.connection.get_connection() with a PostgresConnectionConfig,
not a real database. No real Postgres connection is ever made here."""

from hrb_common.db.connection import PostgresConnectionConfig

from src.platform.interview_qa import store as store_module
from src.platform.interview_qa.store import InterviewQaStore


class _FakeCursor:
    """Stands in for a psycopg cursor - returns canned rows instead of
    querying a real database."""

    def __init__(self, rows):
        self.rows = rows
        self.last_sql = None
        self.last_params = None

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.last_params = params
        return self

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConnection:
    """Stands in for a psycopg connection - never touches a real database."""

    def __init__(self, cursor_rows=None, execute_result=None):
        self._cursor_rows = cursor_rows or []
        self._execute_result = execute_result or _FakeCursor([(0,)])
        self.committed = False
        self.ddl_executed = []

    def cursor(self, row_factory=None):
        return _FakeCursor(self._cursor_rows)

    def execute(self, sql, params=None):
        self.ddl_executed.append(sql)
        return self._execute_result

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _store_with_fake_connection(monkeypatch, fake_connection):
    config = PostgresConnectionConfig(host="fakehost", port="5432", dbname="fakedb", user="fakeuser", password="fakepass")
    captured = {}

    def fake_get_connection(passed_config):
        captured["config"] = passed_config
        return fake_connection

    monkeypatch.setattr(store_module, "get_connection", fake_get_connection)
    return InterviewQaStore(config=config), captured


async def test_ensure_table_calls_get_connection_with_store_config(monkeypatch):
    """The one place real logic changed - confirms the store's config flows
    through to hrb_common.db.connection.get_connection(), not a hardcoded
    psycopg.connect()."""
    fake_connection = _FakeConnection()
    store, captured = _store_with_fake_connection(monkeypatch, fake_connection)

    await store._ensure_table()

    assert captured["config"] is store.config
    assert any("CREATE TABLE" in sql for sql in fake_connection.ddl_executed)
    assert fake_connection.committed is True


async def test_list_cards_returns_rows_from_fake_connection(monkeypatch):
    row = {
        "id": 1, "topic": "Topic A", "topic_order": 0, "card_order": 0, "question": "Q?", "hint": None,
        "concept": None, "situation": None, "task": None, "action": None, "result": None, "project_link": None,
        "leadership_angle": None, "trade_offs": [], "keywords": [], "tech_stack": [], "feature_references": [],
        "created_at": __import__("datetime").datetime(2026, 10, 15), "updated_at": __import__("datetime").datetime(2026, 10, 15),
    }
    fake_connection = _FakeConnection(cursor_rows=[row])
    store, _ = _store_with_fake_connection(monkeypatch, fake_connection)
    store._table_ready = True

    rows = await store.list_cards()

    assert len(rows) == 1
    assert rows[0]["topic"] == "Topic A"
    assert rows[0]["created_at"] == "2026-10-15T00:00:00"


async def test_delete_card_returns_true_when_row_removed(monkeypatch):
    class _DeleteCursor(_FakeCursor):
        rowcount = 1

    fake_connection = _FakeConnection(execute_result=_DeleteCursor([]))
    store, _ = _store_with_fake_connection(monkeypatch, fake_connection)
    store._table_ready = True

    deleted = await store.delete_card(1)

    assert deleted is True


def test_health_check_reports_unhealthy_when_host_not_set(monkeypatch):
    config = PostgresConnectionConfig(host="", port="5432", dbname="", user="", password="")
    store = InterviewQaStore(config=config)

    report = store.health_check()

    assert report["status"] == "unhealthy"
    assert report["message"] == "POSTGRES_DB_HOST not set"
