"""Mechanism-level tests for the 3 stores' Postgres connection-plumbing
adaptation (ROADMAP.md Phase 2's spec, same pattern as Phase 1's
test_interview_qa/test_store.py) - never touches a real database."""

from hrb_common.db.connection import PostgresConnectionConfig

from src.platform.build_deployment import stores as stores_module
from src.platform.build_deployment.stores import EvalRunStore, GoldenDatasetStore, PipelineRunStore


class _FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
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


def _patch_get_connection(monkeypatch, fake_connection):
    captured = {}

    def fake_get_connection(passed_config):
        captured["config"] = passed_config
        return fake_connection

    monkeypatch.setattr(stores_module, "get_connection", fake_get_connection)
    return captured


async def test_golden_dataset_store_ensure_table_uses_store_config(monkeypatch):
    fake_connection = _FakeConnection()
    captured = _patch_get_connection(monkeypatch, fake_connection)
    config = PostgresConnectionConfig(host="fakehost", port="5432", dbname="fakedb", user="u", password="p")
    store = GoldenDatasetStore(config=config)

    await store._ensure_table()

    assert captured["config"] is store.config
    assert any("golden_dataset_cases" in sql for sql in fake_connection.ddl_executed)


async def test_golden_dataset_store_list_cases_returns_fake_rows(monkeypatch):
    import datetime

    row = {
        "id": 1, "case_key": "k1", "dataset": "d1", "category": "cat", "query": "q",
        "raw_case": {}, "created_at": datetime.datetime(2026, 10, 15), "updated_at": datetime.datetime(2026, 10, 15),
    }
    fake_connection = _FakeConnection(cursor_rows=[row])
    _patch_get_connection(monkeypatch, fake_connection)
    store = GoldenDatasetStore(config=PostgresConnectionConfig(host="h", port="5432", dbname="d", user="u", password="p"))
    store._table_ready = True

    cases = await store.list_cases()

    assert len(cases) == 1
    assert cases[0]["case_key"] == "k1"
    assert cases[0]["created_at"] == "2026-10-15T00:00:00"


async def test_eval_run_store_ensure_table_uses_store_config(monkeypatch):
    fake_connection = _FakeConnection()
    captured = _patch_get_connection(monkeypatch, fake_connection)
    config = PostgresConnectionConfig(host="fakehost", port="5432", dbname="fakedb", user="u", password="p")
    store = EvalRunStore(config=config)

    await store._ensure_table()

    assert captured["config"] is store.config
    assert any("eval_runs" in sql for sql in fake_connection.ddl_executed)


async def test_pipeline_run_store_ensure_table_uses_store_config(monkeypatch):
    fake_connection = _FakeConnection()
    captured = _patch_get_connection(monkeypatch, fake_connection)
    config = PostgresConnectionConfig(host="fakehost", port="5432", dbname="fakedb", user="u", password="p")
    store = PipelineRunStore(config=config)

    await store._ensure_table()

    assert captured["config"] is store.config
    assert any("pipeline_runs" in sql for sql in fake_connection.ddl_executed)


def test_health_check_reports_unhealthy_when_host_not_set():
    config = PostgresConnectionConfig(host="", port="5432", dbname="", user="", password="")
    assert GoldenDatasetStore(config=config).health_check()["status"] == "unhealthy"
    assert EvalRunStore(config=config).health_check()["status"] == "unhealthy"
    assert PipelineRunStore(config=config).health_check()["status"] == "unhealthy"
