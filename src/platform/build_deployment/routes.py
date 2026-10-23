"""Ported from hrb_chatbot_v2's api/admin/manage_admin.py (lines ~244-654) -
the 7 CI/CD pipeline dashboard routes. Same no-RBAC adaptation as Phase 1's
interview_qa routes (ROADMAP.md Phase 2's spec) - require_role() calls and
GET routes' query-param identity are dropped.

GitHub Actions client swap: hrb_chatbot_v2 builds GitHubActionsClient through
its own ClientGateway.github_actions(repo=None), where None means "use this
project's own GITHUB_REPO env default." hrb-common-libs' GitHubActionsClient
takes repo as a required arg with no env default (a shared library has no
one default repo). _APPLICATION_REPOS below maps BACKEND/INGESTION_LAMBDA to
the literal "rvsree/hrb_chatbot_service" instead of None, and
_github_actions_client() is a small local per-repo cache replacing
ClientGateway.github_actions() - flagged in the delivery note as a judgment
call, not confirmed with the user."""

from fastapi import APIRouter
from hrb_common.ci.github_actions_client import GitHubActionsClient
from hrb_common.observability.logger import get_logger
from hrb_common.observability.secrets import read_secret

from src.platform.build_deployment.models import (
    Application,
    CiStatusResponse,
    EvalRunCaseDetail,
    EvalRunDetail,
    EvalRunListResponse,
    EvalRunSummary,
    GoldenDatasetCaseSummary,
    GoldenDatasetListResponse,
    PipelineJobDetail,
    PipelineSnapshotListResponse,
    PipelineSnapshotSummary,
    PipelineStatusResponse,
    PipelineWorkflowRun,
    WorkflowRunSummary,
    WorkflowStatus,
)
from src.platform.build_deployment.stores import EvalRunStore, GoldenDatasetStore, PipelineRunStore
from src.platform.common import error_codes
from src.platform.common.responses import json_error

router_build_deployment = APIRouter(tags=["build-deployment"])
logger = get_logger("build_deployment_routes")

_golden_dataset_store = GoldenDatasetStore()
_eval_run_store = EvalRunStore()
_pipeline_run_store = PipelineRunStore()
_github_actions_clients: dict[str, GitHubActionsClient] = {}

# Phase 233 (hrb_chatbot_v2) - which GitHub repo + workflow file(s) each real
# deployable maps to. BACKEND/INGESTION_LAMBDA share one repo but must never
# show each other's runs. LMS_MCP is a genuinely separate repo. FRONTEND
# isn't here at all - it has no GitHub Actions workflow, handled as its own
# early-return below.
_APPLICATION_REPOS: dict[Application, str] = {
    Application.BACKEND: "rvsree/hrb_chatbot_service",
    Application.INGESTION_LAMBDA: "rvsree/hrb_chatbot_service",
    Application.LMS_MCP: "rvsree/hrb_lms_mcp",
}
_APPLICATION_WORKFLOW_FILES: dict[Application, list[str]] = {
    Application.BACKEND: ["ci.yml", "deploy.yml"],
    Application.INGESTION_LAMBDA: ["deploy-lambda.yml"],
    Application.LMS_MCP: ["deploy.yml"],
}
# None means "use get_latest_run_sha() (any workflow in the repo)".
_APPLICATION_ANCHOR_WORKFLOW: dict[Application, str | None] = {
    Application.BACKEND: None,
    Application.INGESTION_LAMBDA: "deploy-lambda.yml",
    Application.LMS_MCP: None,
}
_WORKFLOW_DISPLAY_NAMES: dict[str, str] = {
    "ci.yml": "Continuous Integration Checks",
    "deploy.yml": "Production Deploy",
    "deploy-lambda.yml": "Async Ingestion Deploy",
}
_CI_STATUS_PER_PAGE = 5

_NO_CICD_MESSAGE = (
    "hrb_chatbot_ui has no automated CI/CD yet - deployed manually "
    "(npm run build + aws s3 sync + CloudFront invalidation). "
    "See hrb_chatbot_ui/README.md."
)


def get_golden_dataset_store() -> GoldenDatasetStore:
    return _golden_dataset_store


def get_eval_run_store() -> EvalRunStore:
    return _eval_run_store


def get_pipeline_run_store() -> PipelineRunStore:
    return _pipeline_run_store


def get_github_actions_client(repo: str) -> GitHubActionsClient:
    """One cached client per repo string - the plain local substitute for
    hrb_chatbot_v2's ClientGateway.github_actions(repo=...)."""
    if repo not in _github_actions_clients:
        _github_actions_clients[repo] = GitHubActionsClient(token=read_secret("GITHUB_TOKEN", ""), repo=repo)
    return _github_actions_clients[repo]


def _to_workflow_status(workflow_file: str, result: dict, page: int) -> WorkflowStatus:
    total_count = result["total_count"]
    return WorkflowStatus(
        workflow_file=workflow_file,
        display_name=_WORKFLOW_DISPLAY_NAMES.get(workflow_file, workflow_file),
        runs=[WorkflowRunSummary(**run) for run in result["runs"]],
        total_count=total_count,
        has_more=page * _CI_STATUS_PER_PAGE < total_count,
        error=result["error"],
    )


@router_build_deployment.get("/golden-dataset", response_model=GoldenDatasetListResponse)
async def list_golden_dataset():
    cases = await get_golden_dataset_store().list_cases()
    return GoldenDatasetListResponse(
        count=len(cases),
        cases=[
            GoldenDatasetCaseSummary(
                id=case["id"], case_key=case["case_key"], dataset=case["dataset"], category=case["category"],
                query=case["query"], raw_case=case["raw_case"], created_at=case["created_at"], updated_at=case["updated_at"],
            )
            for case in cases
        ],
    )


@router_build_deployment.get("/eval-runs", response_model=EvalRunListResponse)
async def list_eval_runs():
    runs = await get_eval_run_store().list_runs()
    return EvalRunListResponse(
        count=len(runs),
        runs=[
            EvalRunSummary(
                id=run["id"], run_at=run["run_at"], decision=run["decision"], flags=run["flags"],
                aggregated_scores=run["aggregated_scores"], total_cases=run["total_cases"], scored_cases=run["scored_cases"],
                failed_case_ids=run["failed_case_ids"], retrieval_k=run["retrieval_k"],
            )
            for run in runs
        ],
    )


@router_build_deployment.get("/eval-runs/{run_id}", response_model=EvalRunDetail)
async def get_eval_run(run_id: int):
    run = await get_eval_run_store().get_run(run_id)
    if run is None:
        return json_error(404, f"No eval run found with id {run_id}.", code=error_codes.EVAL_RUN_NOT_FOUND)

    return EvalRunDetail(
        id=run["id"], run_at=run["run_at"], decision=run["decision"], flags=run["flags"],
        aggregated_scores=run["aggregated_scores"], total_cases=run["total_cases"], scored_cases=run["scored_cases"],
        failed_case_ids=run["failed_case_ids"], retrieval_k=run["retrieval_k"],
        cases=[
            EvalRunCaseDetail(case_id=case["case_id"], category=case["category"], scores=case["scores"], status=case["status"])
            for case in run["cases"]
        ],
    )


@router_build_deployment.get("/ci-status", response_model=CiStatusResponse)
async def get_ci_status(application: Application = Application.BACKEND, page: int = 1):
    if application == Application.FRONTEND:
        return CiStatusResponse(application=application, page=page, workflows=[], error=_NO_CICD_MESSAGE)

    repo = _APPLICATION_REPOS[application]
    workflow_files = _APPLICATION_WORKFLOW_FILES[application]
    github = get_github_actions_client(repo)

    workflows = [
        _to_workflow_status(workflow_file, github.list_workflow_runs(workflow_file, per_page=_CI_STATUS_PER_PAGE, page=page), page)
        for workflow_file in workflow_files
    ]

    return CiStatusResponse(application=application, page=page, workflows=workflows, error=None)


@router_build_deployment.get("/ci-status/pipeline", response_model=PipelineStatusResponse)
async def get_ci_pipeline_status(sha: str | None = None, application: Application = Application.BACKEND):
    if application == Application.FRONTEND:
        return PipelineStatusResponse(
            head_sha="", head_commit_message="", head_branch="", event="", actor_login="",
            runs=[], eval_gate=None, error=_NO_CICD_MESSAGE,
        )

    repo = _APPLICATION_REPOS[application]
    workflow_files = _APPLICATION_WORKFLOW_FILES[application]
    anchor_workflow = _APPLICATION_ANCHOR_WORKFLOW[application]
    github = get_github_actions_client(repo)

    target_sha = sha
    if not target_sha:
        latest = github.get_latest_run_sha_for_workflow(anchor_workflow) if anchor_workflow else github.get_latest_run_sha()
        if latest["error"] or not latest["sha"]:
            return PipelineStatusResponse(
                head_sha="", head_commit_message="", head_branch="", event="", actor_login="",
                runs=[], eval_gate=None, error=latest["error"] or "No workflow runs found",
            )
        target_sha = latest["sha"]

    runs_result = github.get_runs_for_sha(target_sha)
    if runs_result["error"]:
        return PipelineStatusResponse(
            head_sha=target_sha, head_commit_message="", head_branch="", event="", actor_login="",
            runs=[], eval_gate=None, error=runs_result["error"],
        )

    # Phase 233 - only this application's own workflow file(s), since a
    # shared repo (BACKEND/INGESTION_LAMBDA) can have both kinds of run on
    # the same commit.
    relevant_runs = [run for run in runs_result["runs"] if run["workflow_file"] in workflow_files]

    pipeline_runs = []
    head_commit_message = ""
    head_branch = ""
    event = ""
    actor_login = ""
    latest_run_created_at = None
    for run in relevant_runs:
        head_commit_message = run["head_commit_message"] or head_commit_message
        head_branch = head_branch or run["head_branch"]
        event = event or run["event"]
        actor_login = actor_login or run["actor_login"]
        jobs_result = github.get_run_jobs(run["id"])
        pipeline_runs.append(
            PipelineWorkflowRun(
                workflow_file=run["workflow_file"], id=run["id"], run_number=run["run_number"], status=run["status"],
                conclusion=run["conclusion"], html_url=run["html_url"], created_at=run["created_at"],
                jobs=[PipelineJobDetail(**job) for job in jobs_result["jobs"]],
            )
        )
        if run["workflow_file"] == "deploy.yml":
            latest_run_created_at = run["created_at"]

    # Nearest eval-gate run at or before this pipeline's own timestamp -
    # BACKEND only: eval_run_store only ever holds hrb_chatbot_service's own
    # golden-dataset release-gate runs.
    eval_gate_summary = None
    reference_time = latest_run_created_at or (pipeline_runs[0].created_at if pipeline_runs else None)
    if reference_time and application == Application.BACKEND:
        all_eval_runs = await get_eval_run_store().list_runs()
        candidates = [run for run in all_eval_runs if run["run_at"] <= reference_time]
        if candidates:
            nearest = max(candidates, key=lambda run: run["run_at"])
            eval_gate_summary = EvalRunSummary(
                id=nearest["id"], run_at=nearest["run_at"], decision=nearest["decision"], flags=nearest["flags"],
                aggregated_scores=nearest["aggregated_scores"], total_cases=nearest["total_cases"],
                scored_cases=nearest["scored_cases"], failed_case_ids=nearest["failed_case_ids"], retrieval_k=nearest["retrieval_k"],
            )

    # Persist-on-read - BACKEND only, deliberately: pipeline_runs' own
    # schema keys snapshots by head_sha alone with no application/repo
    # column, so persisting another application's snapshot here would mix
    # into the same undifferentiated history list with no way to tell them
    # apart later.
    if application != Application.BACKEND:
        return PipelineStatusResponse(
            head_sha=target_sha, head_commit_message=head_commit_message, head_branch=head_branch, event=event,
            actor_login=actor_login, runs=pipeline_runs, eval_gate=eval_gate_summary, error=None,
        )

    try:
        await get_pipeline_run_store().upsert_snapshot(
            head_sha=target_sha, head_commit_message=head_commit_message, head_branch=head_branch, event=event,
            actor_login=actor_login, runs=[run.model_dump() for run in pipeline_runs],
            eval_gate=eval_gate_summary.model_dump() if eval_gate_summary else None,
        )
    except Exception as error:
        logger.warning("Could not persist pipeline snapshot for %s: %s", target_sha, error)

    return PipelineStatusResponse(
        head_sha=target_sha, head_commit_message=head_commit_message, head_branch=head_branch, event=event,
        actor_login=actor_login, runs=pipeline_runs, eval_gate=eval_gate_summary, error=None,
    )


@router_build_deployment.get("/ci-status/pipeline/history", response_model=PipelineSnapshotListResponse)
async def list_pipeline_snapshots():
    snapshots = await get_pipeline_run_store().list_snapshots()
    return PipelineSnapshotListResponse(
        count=len(snapshots),
        snapshots=[
            PipelineSnapshotSummary(
                id=snapshot["id"], head_sha=snapshot["head_sha"], head_commit_message=snapshot["head_commit_message"],
                captured_at=snapshot["captured_at"],
            )
            for snapshot in snapshots
        ],
    )


@router_build_deployment.get("/ci-status/pipeline/history/{snapshot_id}", response_model=PipelineStatusResponse)
async def get_pipeline_snapshot(snapshot_id: int):
    snapshot = await get_pipeline_run_store().get_snapshot(snapshot_id)
    if snapshot is None:
        return json_error(404, f"No pipeline snapshot found with id {snapshot_id}.", code=error_codes.PIPELINE_SNAPSHOT_NOT_FOUND)

    return PipelineStatusResponse(
        head_sha=snapshot["head_sha"], head_commit_message=snapshot["head_commit_message"],
        head_branch=snapshot["head_branch"], event=snapshot["event"], actor_login=snapshot["actor_login"],
        runs=[PipelineWorkflowRun(**run) for run in snapshot["runs_json"]],
        eval_gate=EvalRunSummary(**snapshot["eval_gate_json"]) if snapshot["eval_gate_json"] else None,
        error=None,
    )
