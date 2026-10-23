"""Ported from hrb_chatbot_v2's common/clients/db_client/{pipeline_run_store,
eval_run_store,golden_dataset_store}.py - 3 small Postgres stores, colocated
in one file since none of them depend on each other (ROADMAP.md Phase 2's
spec). SQL/CRUD logic is unchanged; only the connection-acquisition plumbing
changes, same adaptation as Phase 1's InterviewQaStore - hrb_common.db.
connection.get_connection()/PostgresConnectionConfig instead of a direct
psycopg.connect() built from this store's own settings."""

import asyncio
import json

from hrb_common.db.connection import PostgresConnectionConfig, get_connection
from hrb_common.observability.call_logger import log_backend_call
from hrb_common.observability.logger import get_logger

logger = get_logger("build_deployment_stores")

CREATE_GOLDEN_DATASET_TABLE = """
CREATE TABLE IF NOT EXISTS golden_dataset_cases (
    id SERIAL PRIMARY KEY,
    case_key TEXT NOT NULL,
    dataset TEXT NOT NULL,
    category TEXT,
    query TEXT,
    raw_case JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

CREATE_CASE_KEY_DATASET_INDEX = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_golden_dataset_case_key_dataset ON golden_dataset_cases(case_key, dataset)"
)

CREATE_EVAL_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS eval_runs (
    id SERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    decision TEXT NOT NULL,
    flags JSONB NOT NULL DEFAULT '[]',
    aggregated_scores JSONB NOT NULL DEFAULT '{}',
    total_cases INTEGER NOT NULL,
    scored_cases INTEGER NOT NULL,
    failed_case_ids JSONB NOT NULL DEFAULT '[]',
    retrieval_k INTEGER NOT NULL
)
"""

CREATE_EVAL_RUN_CASES_TABLE = """
CREATE TABLE IF NOT EXISTS eval_run_cases (
    id SERIAL PRIMARY KEY,
    eval_run_id INTEGER NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    case_id TEXT NOT NULL,
    category TEXT,
    scores JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL
)
"""

CREATE_EVAL_RUN_CASES_INDEX = "CREATE INDEX IF NOT EXISTS idx_eval_run_cases_eval_run_id ON eval_run_cases(eval_run_id)"

CREATE_PIPELINE_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    head_sha TEXT NOT NULL UNIQUE,
    head_commit_message TEXT NOT NULL DEFAULT '',
    head_branch TEXT NOT NULL DEFAULT '',
    event TEXT NOT NULL DEFAULT '',
    actor_login TEXT NOT NULL DEFAULT '',
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    runs_json JSONB NOT NULL DEFAULT '[]',
    eval_gate_json JSONB
)
"""

ADD_PIPELINE_RUNS_COLUMNS = """
ALTER TABLE pipeline_runs
    ADD COLUMN IF NOT EXISTS head_branch TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS event TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS actor_login TEXT NOT NULL DEFAULT ''
"""


def _dict_row_factory(cursor):
    columns = [desc.name for desc in cursor.description]
    return lambda values: dict(zip(columns, values, strict=True))


class GoldenDatasetStore:
    """Phase 181 (hrb_chatbot_v2) - mirrors resources/golden_dataset/*.json
    into Postgres for the Deployment Dashboard's golden-dataset viewer. A
    read mirror kept in sync by scripts/sync_golden_dataset.py, never
    written to directly by the API."""

    PROVIDER_NAME = "postgres"

    def __init__(self, config: PostgresConnectionConfig | None = None):
        self.config = config or PostgresConnectionConfig.from_env()

        if not self.config.host:
            logger.warning("[POSTGRES] POSTGRES_DB_HOST not set")

        self._table_ready = False

    def _connect(self):
        return get_connection(self.config)

    def _ensure_table_sync(self) -> None:
        with self._connect() as conn:
            conn.execute(CREATE_GOLDEN_DATASET_TABLE)
            conn.execute(CREATE_CASE_KEY_DATASET_INDEX)
            conn.commit()

    async def _ensure_table(self) -> None:
        if self._table_ready:
            return
        await asyncio.to_thread(self._ensure_table_sync)
        self._table_ready = True

    def _list_cases_sync(self) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor(row_factory=_dict_row_factory) as cur:
                cur.execute("SELECT * FROM golden_dataset_cases ORDER BY dataset, case_key")
                rows = cur.fetchall()
        for row in rows:
            row["created_at"] = row["created_at"].isoformat()
            row["updated_at"] = row["updated_at"].isoformat()
        return rows

    async def list_cases(self) -> list[dict]:
        await self._ensure_table()
        with log_backend_call(logger, "postgres", "golden_dataset_cases.list"):
            return await asyncio.to_thread(self._list_cases_sync)

    def health_check(self) -> dict:
        result = {"provider": self.PROVIDER_NAME, "host": self.config.host, "port": self.config.port, "db_name": self.config.dbname}

        if not self.config.host:
            result["status"] = "unhealthy"
            result["message"] = "POSTGRES_DB_HOST not set"
            return result

        try:
            with self._connect() as conn:
                conn.execute(CREATE_GOLDEN_DATASET_TABLE)
                conn.commit()
                row = conn.execute("SELECT count(*) FROM golden_dataset_cases").fetchone()
            result["status"] = "healthy"
            result["cases_stored"] = row[0]
        except Exception as error:
            result["status"] = "unhealthy"
            result["message"] = str(error)

        return result


class EvalRunStore:
    """Phase 182 (hrb_chatbot_v2) - persists scripts/run_release_gate.py's
    own per-run results so the Deployment Dashboard can show history
    instead of each run's output only ever living in CI stdout."""

    PROVIDER_NAME = "postgres"

    def __init__(self, config: PostgresConnectionConfig | None = None):
        self.config = config or PostgresConnectionConfig.from_env()

        if not self.config.host:
            logger.warning("[POSTGRES] POSTGRES_DB_HOST not set")

        self._table_ready = False

    def _connect(self):
        return get_connection(self.config)

    def _ensure_table_sync(self) -> None:
        with self._connect() as conn:
            conn.execute(CREATE_EVAL_RUNS_TABLE)
            conn.execute(CREATE_EVAL_RUN_CASES_TABLE)
            conn.execute(CREATE_EVAL_RUN_CASES_INDEX)
            conn.commit()

    async def _ensure_table(self) -> None:
        if self._table_ready:
            return
        await asyncio.to_thread(self._ensure_table_sync)
        self._table_ready = True

    def _record_run_sync(
        self, decision, flags, aggregated_scores, total_cases, scored_cases, failed_case_ids, retrieval_k, case_results
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO eval_runs (decision, flags, aggregated_scores, total_cases, scored_cases, "
                "failed_case_ids, retrieval_k) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (
                    decision,
                    json.dumps(flags),
                    json.dumps(aggregated_scores),
                    total_cases,
                    scored_cases,
                    json.dumps(failed_case_ids),
                    retrieval_k,
                ),
            )
            run_id = cur.fetchone()[0]
            for case_result in case_results:
                conn.execute(
                    "INSERT INTO eval_run_cases (eval_run_id, case_id, category, scores, status) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        run_id,
                        case_result["case_id"],
                        case_result.get("category"),
                        json.dumps(case_result.get("scores", {})),
                        case_result["status"],
                    ),
                )
            conn.commit()
            return run_id

    async def record_run(
        self, decision, flags, aggregated_scores, total_cases, scored_cases, failed_case_ids, retrieval_k, case_results
    ) -> int:
        """Never allowed to fail the gate itself - callers must catch and
        log, not propagate."""
        await self._ensure_table()
        with log_backend_call(logger, "postgres", "eval_runs.record", decision=decision):
            return await asyncio.to_thread(
                self._record_run_sync, decision, flags, aggregated_scores, total_cases, scored_cases, failed_case_ids,
                retrieval_k, case_results,
            )

    def _list_runs_sync(self) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor(row_factory=_dict_row_factory) as cur:
                cur.execute("SELECT * FROM eval_runs ORDER BY run_at DESC")
                rows = cur.fetchall()
        for row in rows:
            row["run_at"] = row["run_at"].isoformat()
        return rows

    async def list_runs(self) -> list[dict]:
        await self._ensure_table()
        with log_backend_call(logger, "postgres", "eval_runs.list"):
            return await asyncio.to_thread(self._list_runs_sync)

    def _get_run_sync(self, run_id: int) -> dict | None:
        with self._connect() as conn:
            with conn.cursor(row_factory=_dict_row_factory) as cur:
                cur.execute("SELECT * FROM eval_runs WHERE id = %s", (run_id,))
                run = cur.fetchone()
                if run is None:
                    return None
                cur.execute("SELECT * FROM eval_run_cases WHERE eval_run_id = %s ORDER BY case_id", (run_id,))
                run["cases"] = cur.fetchall()
        run["run_at"] = run["run_at"].isoformat()
        return run

    async def get_run(self, run_id: int) -> dict | None:
        await self._ensure_table()
        with log_backend_call(logger, "postgres", "eval_runs.get", run_id=run_id):
            return await asyncio.to_thread(self._get_run_sync, run_id)

    def health_check(self) -> dict:
        result = {"provider": self.PROVIDER_NAME, "host": self.config.host, "port": self.config.port, "db_name": self.config.dbname}

        if not self.config.host:
            result["status"] = "unhealthy"
            result["message"] = "POSTGRES_DB_HOST not set"
            return result

        try:
            with self._connect() as conn:
                conn.execute(CREATE_EVAL_RUNS_TABLE)
                conn.commit()
                row = conn.execute("SELECT count(*) FROM eval_runs").fetchone()
            result["status"] = "healthy"
            result["runs_stored"] = row[0]
        except Exception as error:
            result["status"] = "unhealthy"
            result["message"] = str(error)

        return result


class PipelineRunStore:
    """Phase 189 (hrb_chatbot_v2) - persists a snapshot of the live pipeline
    route's own response, upserted by head_sha, on every successful real
    fetch (persist-on-read)."""

    PROVIDER_NAME = "postgres"

    def __init__(self, config: PostgresConnectionConfig | None = None):
        self.config = config or PostgresConnectionConfig.from_env()

        if not self.config.host:
            logger.warning("[POSTGRES] POSTGRES_DB_HOST not set")

        self._table_ready = False

    def _connect(self):
        return get_connection(self.config)

    def _ensure_table_sync(self) -> None:
        with self._connect() as conn:
            conn.execute(CREATE_PIPELINE_RUNS_TABLE)
            conn.execute(ADD_PIPELINE_RUNS_COLUMNS)
            conn.commit()

    async def _ensure_table(self) -> None:
        if self._table_ready:
            return
        await asyncio.to_thread(self._ensure_table_sync)
        self._table_ready = True

    def _upsert_snapshot_sync(self, head_sha, head_commit_message, head_branch, event, actor_login, runs, eval_gate) -> dict:
        with self._connect() as conn:
            with conn.cursor(row_factory=_dict_row_factory) as cur:
                cur.execute(
                    "INSERT INTO pipeline_runs (head_sha, head_commit_message, head_branch, event, actor_login, runs_json, eval_gate_json) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (head_sha) DO UPDATE SET "
                    "head_commit_message = EXCLUDED.head_commit_message, head_branch = EXCLUDED.head_branch, "
                    "event = EXCLUDED.event, actor_login = EXCLUDED.actor_login, runs_json = EXCLUDED.runs_json, "
                    "eval_gate_json = EXCLUDED.eval_gate_json, captured_at = now() "
                    "RETURNING *",
                    (
                        head_sha, head_commit_message, head_branch, event, actor_login,
                        json.dumps(runs), json.dumps(eval_gate) if eval_gate else None,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        row["captured_at"] = row["captured_at"].isoformat()
        return row

    async def upsert_snapshot(self, head_sha, head_commit_message, head_branch, event, actor_login, runs, eval_gate) -> dict:
        """Called on every successful real fetch of the live pipeline
        route - never allowed to break that route if persistence fails,
        callers must catch and log, not propagate."""
        await self._ensure_table()
        with log_backend_call(logger, "postgres", "pipeline_runs.upsert", head_sha=head_sha):
            return await asyncio.to_thread(
                self._upsert_snapshot_sync, head_sha, head_commit_message, head_branch, event, actor_login, runs, eval_gate
            )

    def _list_snapshots_sync(self) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor(row_factory=_dict_row_factory) as cur:
                cur.execute("SELECT id, head_sha, head_commit_message, captured_at FROM pipeline_runs ORDER BY captured_at DESC")
                rows = cur.fetchall()
        for row in rows:
            row["captured_at"] = row["captured_at"].isoformat()
        return rows

    async def list_snapshots(self) -> list[dict]:
        await self._ensure_table()
        with log_backend_call(logger, "postgres", "pipeline_runs.list"):
            return await asyncio.to_thread(self._list_snapshots_sync)

    def _get_snapshot_sync(self, snapshot_id: int) -> dict | None:
        with self._connect() as conn:
            with conn.cursor(row_factory=_dict_row_factory) as cur:
                cur.execute("SELECT * FROM pipeline_runs WHERE id = %s", (snapshot_id,))
                row = cur.fetchone()
        if row is None:
            return None
        row["captured_at"] = row["captured_at"].isoformat()
        return row

    async def get_snapshot(self, snapshot_id: int) -> dict | None:
        await self._ensure_table()
        with log_backend_call(logger, "postgres", "pipeline_runs.get", snapshot_id=snapshot_id):
            return await asyncio.to_thread(self._get_snapshot_sync, snapshot_id)

    def health_check(self) -> dict:
        result = {"provider": self.PROVIDER_NAME, "host": self.config.host, "port": self.config.port, "db_name": self.config.dbname}

        if not self.config.host:
            result["status"] = "unhealthy"
            result["message"] = "POSTGRES_DB_HOST not set"
            return result

        try:
            with self._connect() as conn:
                conn.execute(CREATE_PIPELINE_RUNS_TABLE)
                conn.commit()
                row = conn.execute("SELECT count(*) FROM pipeline_runs").fetchone()
            result["status"] = "healthy"
            result["snapshots_stored"] = row[0]
        except Exception as error:
            result["status"] = "unhealthy"
            result["message"] = str(error)

        return result
