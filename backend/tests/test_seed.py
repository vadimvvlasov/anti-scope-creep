import asyncio
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from app.analyzer import AnalysisResult, EmailDraftContent, FindingDraft, StubAnalyzer
from app.config import Settings
from app.context import AppContext
from app.main import create_app
from app.seed import (
    DEMO_CONTRACTS,
    DEMO_EMAIL,
    DEMO_PASSWORD,
    OTHER_EMAIL,
    finish_pending_analyses,
    seed_demo_data,
)
from app.store import InMemoryStore
from tests.conftest import assert_error
from tests.fakes import FakeClock
from tests.samples import TEST_JWT_SECRET


@pytest.fixture(scope="module")
def seeded():
    app = create_app(Settings(jwt_secret=TEST_JWT_SECRET, seed_demo_data=True))
    client = TestClient(app)  # not entered: the delayed pending run does not start

    def login(email):
        response = client.post("/auth/login", json={"email": email, "password": DEMO_PASSWORD})
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    demo = login(DEMO_EMAIL)
    items = client.get("/contracts?page_size=50", headers=demo).json()["items"]
    details = [client.get(f"/contracts/{item['id']}", headers=demo).json() for item in items]
    return client, login, demo, details


def by_title(details, title):
    return next(d for d in details if d["title"] == title)


def test_demo_user_has_23_contracts_over_two_pages(seeded):
    client, _, demo, _ = seeded
    page = client.get("/contracts", headers=demo).json()
    assert (page["total_count"], page["page_size"], page["total_pages"]) == (23, 20, 2)


def test_seed_statuses(seeded):
    *_, details = seeded
    assert Counter(d["status"] for d in details) == {"done": 20, "failed": 2, "analyzing": 1}
    assert details[0]["title"] == "Illustration License Agreement.pdf"
    assert details[0]["status"] == "analyzing"


def test_seeded_results_follow_the_email_rule(seeded):
    *_, details = seeded
    for detail in details:
        if detail["analyzed_at"] is None:
            continue
        findings = [FindingDraft(**{k: v for k, v in f.items() if k != "id"}) for f in detail["findings"]]
        email = detail["email_draft"]
        content = EmailDraftContent(subject=email["subject"], body=email["body"]) if email else None
        AnalysisResult(findings=findings, email_draft=content)  # raises if the rule is broken
        actionable = sum(f["risk_level"] != "low" for f in detail["findings"])
        assert (email["body"].count("\n- ") if email else 0) == actionable


def test_special_seed_rows(seeded):
    *_, details = seeded
    stub = by_title(details, "Website Redesign Agreement.pdf")
    assert stub["risk_summary"] == {
        "overall_risk_level": "high",
        "high_count": 1,
        "medium_count": 1,
        "low_count": 1,
    }

    empty = by_title(details, "Copywriting Retainer")
    assert (empty["filename"], empty["file_size"], empty["findings"], empty["email_draft"]) == ("", None, [], None)
    assert empty["overall_risk_level"] == "low"

    never = by_title(details, "Consulting Agreement Q3.pdf")
    assert (never["status"], never["analyzed_at"], never["risk_summary"]) == ("failed", None, None)

    kept = by_title(details, "Video Production Contract.pdf")
    assert kept["status"] == "failed"
    assert [(f["category"], f["risk_level"]) for f in kept["findings"]] == [
        ("ip_transfer_before_payment", "high")
    ]
    assert kept["email_draft"] is not None


def test_recent_uncapped_liability_findings(seeded):
    *_, details = seeded
    recent = [
        f for d in details[:10] for f in d["findings"] if f["category"] == "uncapped_liability"
    ]
    assert len(recent) >= 2
    assert len(DEMO_CONTRACTS) == 23


def test_other_users_contract_is_hidden_from_demo(seeded):
    client, login, demo, _ = seeded
    other = login(OTHER_EMAIL)
    other_items = client.get("/contracts", headers=other).json()["items"]
    assert len(other_items) == 1
    assert_error(client.get(f"/contracts/{other_items[0]['id']}", headers=demo), 404, "CONTRACT_NOT_FOUND")


def test_pending_seed_analysis_finishes_with_stub_fixture():
    context = AppContext(Settings(jwt_secret=TEST_JWT_SECRET), InMemoryStore(), StubAnalyzer(), FakeClock())
    pending = seed_demo_data(context)
    assert len(pending) == 1

    asyncio.run(finish_pending_analyses(context, pending, delay=0))

    demo = context.store.get_user_by_email(DEMO_EMAIL)
    contract = context.store.get_contract(demo.id, pending[0][0])
    assert contract.status == "done"
    assert len(context.store.get_findings(contract.id)) == 3


def test_seeding_is_disabled_by_setting():
    app = create_app(Settings(jwt_secret=TEST_JWT_SECRET, seed_demo_data=False))
    assert app.state.context.store.get_user_by_email(DEMO_EMAIL) is None
