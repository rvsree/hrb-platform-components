"""Ported from hrb_chatbot_v2's tests/hrb_chatbot/api/admin/test_manage_admin.py
interview-qa block (ROADMAP.md Phase 1's spec) - the one RBAC test
(test_employee_admin_cannot_list_interview_qa_cards) is not ported, since
this repo has no RBAC layer. Uses the same FakeInterviewQaStore shape as
hrb_chatbot_v2's tests/conftest.py - never touches a real database."""

from fastapi.testclient import TestClient

from src.platform.interview_qa.routes import get_interview_qa_store
from src.platform.main import app

client = TestClient(app)

_INTERVIEW_QA_FIELDS = {
    "topic": "Topic A",
    "topic_order": 1,
    "card_order": 1,
    "question": "Does CRUD work end to end?",
    "hint": "yes",
    "concept": None,
    "situation": None,
    "task": None,
    "action": None,
    "result": None,
    "project_link": None,
    "leadership_angle": None,
    "trade_offs": ["one"],
    "keywords": [{"term": "CRUD", "definition": "Create/Read/Update/Delete"}],
    "tech_stack": ["FastAPI"],
    "feature_references": [{"label": "store", "file_path": "src/platform/interview_qa/store.py"}],
}

_USER_PROFILE = {"employee_id": "E1", "full_name": "Admin One", "role": "ADMIN"}


class FakeInterviewQaStore:
    """Same in-memory shape as hrb_chatbot_v2's tests/conftest.py::FakeInterviewQaStore -
    never touches a real database."""

    def __init__(self):
        self._rows: dict[int, dict] = {}
        self._next_id = 1

    async def list_cards(self, topic=None):
        rows = list(self._rows.values())
        if topic:
            rows = [row for row in rows if row["topic"] == topic]
        return [dict(row) for row in sorted(rows, key=lambda r: (r["topic_order"], r["card_order"]))]

    async def get_card(self, card_id):
        row = self._rows.get(card_id)
        return dict(row) if row else None

    async def create_card(self, fields):
        row = {
            "id": self._next_id,
            "topic": fields.get("topic"),
            "topic_order": fields.get("topic_order", 0),
            "card_order": fields.get("card_order", 0),
            "question": fields.get("question"),
            "hint": fields.get("hint"),
            "concept": fields.get("concept"),
            "situation": fields.get("situation"),
            "task": fields.get("task"),
            "action": fields.get("action"),
            "result": fields.get("result"),
            "project_link": fields.get("project_link"),
            "leadership_angle": fields.get("leadership_angle"),
            "trade_offs": fields.get("trade_offs") or [],
            "keywords": fields.get("keywords") or [],
            "tech_stack": fields.get("tech_stack") or [],
            "feature_references": fields.get("feature_references") or [],
            "created_at": "2026-10-15T00:00:00Z",
            "updated_at": "2026-10-15T00:00:00Z",
        }
        self._rows[self._next_id] = row
        self._next_id += 1
        return dict(row)

    async def update_card(self, card_id, fields):
        row = self._rows.get(card_id)
        if row is None:
            return None
        for key in (
            "topic", "topic_order", "card_order", "question", "hint", "concept", "situation", "task", "action",
            "result", "project_link", "leadership_angle", "trade_offs", "keywords", "tech_stack", "feature_references",
        ):
            if key in fields:
                row[key] = fields[key]
        return dict(row)

    async def delete_card(self, card_id):
        return self._rows.pop(card_id, None) is not None

    def health_check(self):
        return {"provider": "postgres", "status": "healthy"}


def _use_fake_store(store):
    app.dependency_overrides[get_interview_qa_store] = lambda: store


def teardown_function():
    app.dependency_overrides.pop(get_interview_qa_store, None)


def test_list_interview_qa_cards_filtered_by_topic():
    store = FakeInterviewQaStore()
    _use_fake_store(store)

    import asyncio

    asyncio.run(store.create_card({**_INTERVIEW_QA_FIELDS, "topic": "Topic A"}))
    asyncio.run(store.create_card({**_INTERVIEW_QA_FIELDS, "topic": "Topic B"}))

    response = client.get("/v1/admin/interview-qa")
    assert response.status_code == 200
    assert response.json()["count"] == 2

    filtered = client.get("/v1/admin/interview-qa", params={"topic": "Topic A"})
    assert filtered.status_code == 200
    body = filtered.json()
    assert body["count"] == 1
    assert body["cards"][0]["topic"] == "Topic A"


def test_get_interview_qa_card_404_for_unknown_id():
    _use_fake_store(FakeInterviewQaStore())

    response = client.get("/v1/admin/interview-qa/999")

    assert response.status_code == 404
    assert response.json()["code"] == "ADMIN_INTERVIEW_QA_NOT_FOUND"


def test_create_update_and_delete_interview_qa_card():
    _use_fake_store(FakeInterviewQaStore())

    create_response = client.post(
        "/v1/admin/interview-qa", json={"user_profile": _USER_PROFILE, "fields": _INTERVIEW_QA_FIELDS}
    )
    assert create_response.status_code == 200
    card = create_response.json()
    assert card["question"] == "Does CRUD work end to end?"
    assert card["keywords"] == [{"term": "CRUD", "definition": "Create/Read/Update/Delete"}]

    updated_fields = {**_INTERVIEW_QA_FIELDS, "question": "Does CRUD work end to end - updated?"}
    update_response = client.put(
        f"/v1/admin/interview-qa/{card['id']}", json={"user_profile": _USER_PROFILE, "fields": updated_fields}
    )
    assert update_response.status_code == 200
    assert update_response.json()["question"] == "Does CRUD work end to end - updated?"

    delete_response = client.request("DELETE", f"/v1/admin/interview-qa/{card['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"id": card["id"], "deleted": True}

    get_after_delete = client.get(f"/v1/admin/interview-qa/{card['id']}")
    assert get_after_delete.status_code == 404


def test_update_interview_qa_card_404_for_unknown_id():
    _use_fake_store(FakeInterviewQaStore())

    response = client.put(
        "/v1/admin/interview-qa/999", json={"user_profile": _USER_PROFILE, "fields": _INTERVIEW_QA_FIELDS}
    )

    assert response.status_code == 404
    assert response.json()["code"] == "ADMIN_INTERVIEW_QA_NOT_FOUND"
