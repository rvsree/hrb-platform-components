"""Ported as-is from hrb_chatbot_v2's common/enums.py::Application and
models/admin.py - only the models the 7 build_deployment routes need
(ROADMAP.md Phase 2's spec)."""

from enum import StrEnum

from pydantic import BaseModel


class Application(StrEnum):
    """Phase 233 (hrb_chatbot_v2) - which real deployable the CI/CD Pipeline
    Visibility dashboard is showing. BACKEND/INGESTION_LAMBDA share one
    GitHub repo (hrb_chatbot_service) but are different workflow
    files/deploy targets; LMS_MCP is a genuinely separate repo
    (rvsree/hrb_lms_mcp); FRONTEND (hrb_chatbot_ui) has no GitHub Actions
    workflow at all - deployed manually, see its own README."""

    BACKEND = "backend"
    INGESTION_LAMBDA = "ingestion_lambda"
    LMS_MCP = "lms_mcp"
    FRONTEND = "frontend"


class GoldenDatasetCaseSummary(BaseModel):
    id: int
    case_key: str
    dataset: str
    category: str | None
    query: str | None
    raw_case: dict
    created_at: str
    updated_at: str


class GoldenDatasetListResponse(BaseModel):
    count: int
    cases: list[GoldenDatasetCaseSummary]


class EvalRunSummary(BaseModel):
    id: int
    run_at: str
    decision: str
    flags: list[str]
    aggregated_scores: dict[str, float]
    total_cases: int
    scored_cases: int
    failed_case_ids: list[str]
    retrieval_k: int


class EvalRunListResponse(BaseModel):
    count: int
    runs: list[EvalRunSummary]


class EvalRunCaseDetail(BaseModel):
    case_id: str
    category: str | None
    scores: dict[str, float]
    status: str


class EvalRunDetail(EvalRunSummary):
    cases: list[EvalRunCaseDetail]


class WorkflowRunSummary(BaseModel):
    id: int
    run_number: int
    status: str
    conclusion: str | None
    head_sha: str
    head_commit_message: str
    html_url: str
    created_at: str


class WorkflowStatus(BaseModel):
    workflow_file: str
    display_name: str
    runs: list[WorkflowRunSummary]
    total_count: int
    has_more: bool
    error: str | None


class CiStatusResponse(BaseModel):
    application: Application
    page: int
    workflows: list[WorkflowStatus]
    error: str | None


class PipelineStepDetail(BaseModel):
    name: str
    status: str
    conclusion: str | None
    started_at: str | None
    completed_at: str | None


class PipelineJobDetail(BaseModel):
    name: str
    status: str
    conclusion: str | None
    html_url: str
    steps: list[PipelineStepDetail]


class PipelineWorkflowRun(BaseModel):
    """One workflow file's run (ci.yml / deploy.yml) for a single commit."""

    workflow_file: str
    id: int
    run_number: int
    status: str
    conclusion: str | None
    html_url: str
    created_at: str
    jobs: list[PipelineJobDetail]


class PipelineStatusResponse(BaseModel):
    head_sha: str
    head_commit_message: str
    head_branch: str
    event: str
    actor_login: str
    runs: list[PipelineWorkflowRun]
    eval_gate: EvalRunSummary | None
    error: str | None


class PipelineSnapshotSummary(BaseModel):
    id: int
    head_sha: str
    head_commit_message: str
    captured_at: str


class PipelineSnapshotListResponse(BaseModel):
    count: int
    snapshots: list[PipelineSnapshotSummary]
