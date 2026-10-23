"""Ported from hrb_chatbot_v2's tests/hrb_chatbot/api/admin/test_manage_admin.py
golden-dataset/eval-runs/ci-status/pipeline blocks (ROADMAP.md Phase 2's
spec) - a representative subset, not all ~20 original tests (see spec's
Behavior parity note). RBAC-specific tests (403 for non-admin) are not
ported - no RBAC layer exists in this repo. Uses the same
FakeGoldenDatasetStore/FakeEvalRunStore/FakePipelineRunStore/
_FakeGitHubActionsClient shapes as hrb_chatbot_v2's own tests - never
touches a real database or the real GitHub API."""

from fastapi.testclient import TestClient

from src.platform.build_deployment import routes as routes_module
from src.platform.main import app

client = TestClient(app)


class FakeGoldenDatasetStore:
    def __init__(self, cases=None):
        self._cases = cases or []

    async def list_cases(self):
        return list(self._cases)


class FakeEvalRunStore:
    def __init__(self, runs=None):
        self._runs = runs or []

    async def list_runs(self):
        return [{k: v for k, v in run.items() if k != "cases"} for run in self._runs]

    async def get_run(self, run_id):
        for run in self._runs:
            if run["id"] == run_id:
                return run
        return None


class FakePipelineRunStore:
    def __init__(self):
        self._by_sha: dict[str, dict] = {}
        self._next_id = 1
        self.upsert_calls = []

    async def upsert_snapshot(self, head_sha, head_commit_message, head_branch, event, actor_login, runs, eval_gate):
        self.upsert_calls.append(head_sha)
        existing = self._by_sha.get(head_sha)
        row = {
            "id": existing["id"] if existing else self._next_id,
            "head_sha": head_sha, "head_commit_message": head_commit_message, "head_branch": head_branch,
            "event": event, "actor_login": actor_login, "captured_at": "2026-10-16T00:00:00Z",
            "runs_json": runs, "eval_gate_json": eval_gate,
        }
        if not existing:
            self._next_id += 1
        self._by_sha[head_sha] = row
        return dict(row)

    async def list_snapshots(self):
        return [
            {"id": r["id"], "head_sha": r["head_sha"], "head_commit_message": r["head_commit_message"], "captured_at": r["captured_at"]}
            for r in self._by_sha.values()
        ]

    async def get_snapshot(self, snapshot_id):
        for row in self._by_sha.values():
            if row["id"] == snapshot_id:
                return dict(row)
        return None


class _FakeGitHubActionsClient:
    def __init__(self, latest_sha="abc1234", runs=None, jobs_by_run_id=None, error=None, runs_by_workflow_file=None, total_count_by_workflow_file=None):
        self.latest_sha = latest_sha
        self.runs = runs if runs is not None else []
        self.jobs_by_run_id = jobs_by_run_id or {}
        self.error = error
        self.runs_by_workflow_file = runs_by_workflow_file or {}
        self.total_count_by_workflow_file = total_count_by_workflow_file or {}

    def list_workflow_runs(self, workflow_file, per_page=5, page=1):
        if self.error:
            return {"runs": [], "total_count": 0, "error": self.error}
        runs = self.runs_by_workflow_file.get(workflow_file, [])
        total_count = self.total_count_by_workflow_file.get(workflow_file, len(runs))
        return {"runs": runs, "total_count": total_count, "error": None}

    def get_latest_run_sha(self):
        if self.error:
            return {"sha": None, "error": self.error}
        return {"sha": self.latest_sha, "error": None}

    def get_latest_run_sha_for_workflow(self, workflow_file):
        if self.error:
            return {"sha": None, "error": self.error}
        return {"sha": self.latest_sha, "error": None}

    def get_runs_for_sha(self, sha):
        if self.error:
            return {"runs": [], "error": self.error}
        return {"runs": self.runs, "error": None}

    def get_run_jobs(self, run_id):
        return {"jobs": self.jobs_by_run_id.get(run_id, []), "error": None}


def _fake_workflow_run(run_id, run_number):
    return {
        "id": run_id, "run_number": run_number, "status": "completed", "conclusion": "success",
        "head_sha": "d870681", "head_commit_message": "A real commit",
        "html_url": f"https://github.com/rvsree/hrb_chatbot_service/actions/runs/{run_id}",
        "created_at": "2026-10-19T03:58:22Z",
    }


def _use_github(monkeypatch, fake_github, requested_repos=None):
    def fake_get_github_actions_client(repo):
        if requested_repos is not None:
            requested_repos.append(repo)
        return fake_github

    monkeypatch.setattr(routes_module, "get_github_actions_client", fake_get_github_actions_client)


def test_list_golden_dataset(monkeypatch):
    cases = [{
        "id": 1, "case_key": "k1", "dataset": "d1", "category": "cat", "query": "q",
        "raw_case": {"x": 1}, "created_at": "2026-10-15T00:00:00Z", "updated_at": "2026-10-15T00:00:00Z",
    }]
    monkeypatch.setattr(routes_module, "get_golden_dataset_store", lambda: FakeGoldenDatasetStore(cases))

    response = client.get("/v1/admin/golden-dataset")

    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_list_and_get_eval_run(monkeypatch):
    runs = [{
        "id": 1, "run_at": "2026-10-15T22:10:00Z", "decision": "PASS", "flags": [], "aggregated_scores": {"recall": 0.9},
        "total_cases": 10, "scored_cases": 10, "failed_case_ids": [], "retrieval_k": 5, "cases": [],
    }]
    monkeypatch.setattr(routes_module, "get_eval_run_store", lambda: FakeEvalRunStore(runs))

    list_response = client.get("/v1/admin/eval-runs")
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1

    get_response = client.get("/v1/admin/eval-runs/1")
    assert get_response.status_code == 200
    assert get_response.json()["decision"] == "PASS"


def test_get_eval_run_404_for_unknown_id(monkeypatch):
    monkeypatch.setattr(routes_module, "get_eval_run_store", lambda: FakeEvalRunStore([]))

    response = client.get("/v1/admin/eval-runs/999")

    assert response.status_code == 404
    assert response.json()["code"] == "ADMIN_EVAL_RUN_NOT_FOUND"


def test_ci_status_defaults_to_backend_with_both_workflows(monkeypatch):
    fake_github = _FakeGitHubActionsClient(
        runs_by_workflow_file={"ci.yml": [_fake_workflow_run(1, 240)], "deploy.yml": [_fake_workflow_run(2, 58)]},
    )
    requested_repos = []
    _use_github(monkeypatch, fake_github, requested_repos)

    response = client.get("/v1/admin/ci-status")

    assert response.status_code == 200
    body = response.json()
    assert body["application"] == "backend"
    assert [w["workflow_file"] for w in body["workflows"]] == ["ci.yml", "deploy.yml"]
    assert body["workflows"][0]["display_name"] == "Continuous Integration Checks"
    assert requested_repos == ["rvsree/hrb_chatbot_service"]


def test_ci_status_ingestion_lambda_shows_only_its_own_workflow(monkeypatch):
    fake_github = _FakeGitHubActionsClient(runs_by_workflow_file={"deploy-lambda.yml": [_fake_workflow_run(3, 12)]})
    _use_github(monkeypatch, fake_github)

    response = client.get("/v1/admin/ci-status", params={"application": "ingestion_lambda"})

    assert response.status_code == 200
    body = response.json()
    assert [w["workflow_file"] for w in body["workflows"]] == ["deploy-lambda.yml"]
    assert body["workflows"][0]["display_name"] == "Async Ingestion Deploy"


def test_ci_status_lms_mcp_uses_its_own_repo(monkeypatch):
    fake_github = _FakeGitHubActionsClient(runs_by_workflow_file={"deploy.yml": []})
    requested_repos = []
    _use_github(monkeypatch, fake_github, requested_repos)

    response = client.get("/v1/admin/ci-status", params={"application": "lms_mcp"})

    assert response.status_code == 200
    assert requested_repos == ["rvsree/hrb_lms_mcp"]


def test_ci_status_frontend_returns_honest_message_and_skips_github_call(monkeypatch):
    fake_github = _FakeGitHubActionsClient(error="should never be called for frontend")
    _use_github(monkeypatch, fake_github)

    response = client.get("/v1/admin/ci-status", params={"application": "frontend"})

    assert response.status_code == 200
    body = response.json()
    assert body["workflows"] == []
    assert "no automated CI/CD" in body["error"]


def test_ci_status_has_more_true_when_additional_pages_exist(monkeypatch):
    fake_github = _FakeGitHubActionsClient(
        runs_by_workflow_file={"ci.yml": [_fake_workflow_run(1, 1)], "deploy.yml": []},
        total_count_by_workflow_file={"ci.yml": 25, "deploy.yml": 0},
    )
    _use_github(monkeypatch, fake_github)

    response = client.get("/v1/admin/ci-status", params={"page": 1})

    body = response.json()
    ci_workflow = next(w for w in body["workflows"] if w["workflow_file"] == "ci.yml")
    assert ci_workflow["has_more"] is True

    response_last_page = client.get("/v1/admin/ci-status", params={"page": 5})
    ci_workflow_last_page = next(w for w in response_last_page.json()["workflows"] if w["workflow_file"] == "ci.yml")
    assert ci_workflow_last_page["has_more"] is False


def test_ci_status_surfaces_a_github_error_per_workflow(monkeypatch):
    fake_github = _FakeGitHubActionsClient(error="GITHUB_TOKEN not configured")
    _use_github(monkeypatch, fake_github)

    response = client.get("/v1/admin/ci-status")

    body = response.json()
    for workflow in body["workflows"]:
        assert workflow["error"] == "GITHUB_TOKEN not configured"
        assert workflow["runs"] == []


def test_pipeline_status_defaults_to_the_latest_sha_and_stitches_workflows(monkeypatch):
    fake_github = _FakeGitHubActionsClient(
        latest_sha="d40e8b1",
        runs=[
            {
                "id": 1, "run_number": 240, "workflow_file": "ci.yml", "status": "completed", "conclusion": "success",
                "head_commit_message": "Suppress bandit finding", "head_branch": "develop", "event": "push",
                "actor_login": "rvsree", "html_url": "https://github.com/.../runs/1", "created_at": "2026-10-16T02:52:00Z",
            },
            {
                "id": 2, "run_number": 58, "workflow_file": "deploy.yml", "status": "completed", "conclusion": "success",
                "head_commit_message": "Suppress bandit finding", "head_branch": "master", "event": "push",
                "actor_login": "rvsree", "html_url": "https://github.com/.../runs/2", "created_at": "2026-10-16T02:53:20Z",
            },
        ],
        jobs_by_run_id={1: [], 2: []},
    )
    _use_github(monkeypatch, fake_github)
    eval_store = FakeEvalRunStore(runs=[{
        "id": 1, "run_at": "2026-10-15T22:10:00Z", "decision": "PASS", "flags": [], "aggregated_scores": {"recall": 0.91},
        "total_cases": 26, "scored_cases": 26, "failed_case_ids": [], "retrieval_k": 5, "cases": [],
    }])
    monkeypatch.setattr(routes_module, "get_eval_run_store", lambda: eval_store)
    pipeline_store = FakePipelineRunStore()
    monkeypatch.setattr(routes_module, "get_pipeline_run_store", lambda: pipeline_store)

    response = client.get("/v1/admin/ci-status/pipeline")

    assert response.status_code == 200
    body = response.json()
    assert body["head_sha"] == "d40e8b1"
    assert [run["workflow_file"] for run in body["runs"]] == ["ci.yml", "deploy.yml"]
    assert body["eval_gate"]["decision"] == "PASS"
    assert pipeline_store.upsert_calls == ["d40e8b1"]


def test_pipeline_status_shows_no_eval_gate_when_none_precedes_it(monkeypatch):
    fake_github = _FakeGitHubActionsClient(
        latest_sha="abc1234",
        runs=[{
            "id": 1, "run_number": 10, "workflow_file": "deploy.yml", "status": "in_progress", "conclusion": None,
            "head_commit_message": "", "head_branch": "master", "event": "push", "actor_login": "rvsree",
            "html_url": "https://github.com/.../runs/1", "created_at": "2026-10-16T02:53:20Z",
        }],
        jobs_by_run_id={1: []},
    )
    _use_github(monkeypatch, fake_github)
    monkeypatch.setattr(routes_module, "get_eval_run_store", lambda: FakeEvalRunStore([]))
    monkeypatch.setattr(routes_module, "get_pipeline_run_store", lambda: FakePipelineRunStore())

    response = client.get("/v1/admin/ci-status/pipeline")

    body = response.json()
    assert body["eval_gate"] is None
    assert body["runs"][0]["status"] == "in_progress"


def test_pipeline_status_frontend_application_returns_honest_message(monkeypatch):
    fake_github = _FakeGitHubActionsClient(error="should never be called")
    _use_github(monkeypatch, fake_github)

    response = client.get("/v1/admin/ci-status/pipeline", params={"application": "frontend"})

    body = response.json()
    assert "no automated CI/CD" in body["error"]
    assert body["runs"] == []


def test_pipeline_status_skips_snapshot_persistence_for_non_backend_application(monkeypatch):
    fake_github = _FakeGitHubActionsClient(
        latest_sha="abc1234",
        runs=[{
            "id": 1, "run_number": 12, "workflow_file": "deploy-lambda.yml", "status": "completed", "conclusion": "success",
            "head_commit_message": "msg", "head_branch": "master", "event": "push", "actor_login": "rvsree",
            "html_url": "https://github.com/.../runs/1", "created_at": "2026-10-16T02:53:20Z",
        }],
        jobs_by_run_id={1: []},
    )
    _use_github(monkeypatch, fake_github)
    pipeline_store = FakePipelineRunStore()
    monkeypatch.setattr(routes_module, "get_pipeline_run_store", lambda: pipeline_store)

    response = client.get("/v1/admin/ci-status/pipeline", params={"application": "ingestion_lambda"})

    assert response.status_code == 200
    assert pipeline_store.upsert_calls == []


def test_pipeline_snapshot_history_list_get_and_404(monkeypatch):
    pipeline_store = FakePipelineRunStore()
    monkeypatch.setattr(routes_module, "get_pipeline_run_store", lambda: pipeline_store)

    import asyncio

    asyncio.run(
        pipeline_store.upsert_snapshot(
            head_sha="abc1234", head_commit_message="msg", head_branch="master", event="push",
            actor_login="rvsree", runs=[], eval_gate=None,
        )
    )

    list_response = client.get("/v1/admin/ci-status/pipeline/history")
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1
    snapshot_id = list_response.json()["snapshots"][0]["id"]

    get_response = client.get(f"/v1/admin/ci-status/pipeline/history/{snapshot_id}")
    assert get_response.status_code == 200
    assert get_response.json()["head_sha"] == "abc1234"

    not_found = client.get("/v1/admin/ci-status/pipeline/history/999")
    assert not_found.status_code == 404
    assert not_found.json()["code"] == "ADMIN_PIPELINE_SNAPSHOT_NOT_FOUND"
