"""Contract endpoints: upload, list, get, rename, delete, ownership."""

from uuid import UUID, uuid4

import pytest

from tests.conftest import assert_error
from tests.pdf_factory import text_pdf
from tests.samples import ENGLISH_CONTRACT

DETAIL_FIELDS = {
    "id",
    "title",
    "filename",
    "file_type",
    "file_size",
    "status",
    "created_at",
    "updated_at",
    "analyzed_at",
    "overall_risk_level",
    "source_text",
    "risk_summary",
    "findings",
    "email_draft",
}
SUMMARY_FIELDS = DETAIL_FIELDS - {"source_text", "risk_summary", "findings", "email_draft"}


# -- create ---------------------------------------------------------------------------


def test_create_returns_202_analyzing_contract_without_results(harness, auth_headers):
    harness.use_recording_runner()
    response = harness.paste(auth_headers, title="  Pasted SOW ")

    assert response.status_code == 202
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["status"] == "analyzing"
    assert body["title"] == "Pasted SOW"
    assert (body["filename"], body["file_type"], body["file_size"]) == ("", "txt", None)
    assert body["analyzed_at"] is None
    assert body["overall_risk_level"] is None
    assert body["risk_summary"] is None
    assert body["findings"] == []
    assert body["email_draft"] is None
    assert body["source_text"] == ENGLISH_CONTRACT


def test_create_schedules_one_run_matching_the_stored_run_id(harness, auth_headers):
    runner = harness.use_recording_runner()
    contract_id = harness.create_contract(auth_headers)["id"]

    assert len(runner.scheduled) == 1
    scheduled_id, run_id = runner.scheduled[0]
    record = harness.store.get_contract_for_analysis(scheduled_id, run_id)
    assert str(record.id) == contract_id
    assert record.analysis_started_at == harness.clock()


def test_background_analysis_completes_with_stub_fixture(harness, auth_headers):
    contract_id = harness.create_contract(auth_headers)["id"]

    body = harness.client.get(f"/contracts/{contract_id}", headers=auth_headers).json()

    assert body["status"] == "done"
    assert body["analyzed_at"] is not None
    assert body["overall_risk_level"] == "high"
    assert body["risk_summary"] == {
        "overall_risk_level": "high",
        "high_count": 1,
        "medium_count": 1,
        "low_count": 1,
    }
    assert [f["risk_level"] for f in body["findings"]] == ["high", "medium", "low"]
    assert set(body["findings"][0]) == {
        "id", "category", "risk_level", "quoted_text", "explanation", "suggested_change", "start_char", "end_char"
    }
    assert body["email_draft"]["subject"] == "Proposed changes to the agreement"
    assert set(body["email_draft"]) == {"id", "subject", "body", "created_at"}


def test_findings_carry_suggested_change_and_offsets_into_the_source_text(harness, auth_headers):
    contract_id = harness.create_contract(auth_headers)["id"]  # contains all three stub quotes

    body = harness.client.get(f"/contracts/{contract_id}", headers=auth_headers).json()

    for finding in body["findings"]:
        assert finding["suggested_change"]
        assert body["source_text"][finding["start_char"] : finding["end_char"]] == finding["quoted_text"]


def test_findings_whose_quote_is_not_in_the_text_have_null_offsets(harness, auth_headers):
    text = (
        "This Services Agreement is entered into between the Client and the Contractor. The Contractor "
        "will design a marketing website. Invoices are payable within 30 days of the invoice date."
    )
    contract_id = harness.create_contract(auth_headers, text=text)["id"]

    body = harness.client.get(f"/contracts/{contract_id}", headers=auth_headers).json()

    assert body["status"] == "done"
    assert [(f["start_char"], f["end_char"]) for f in body["findings"]] == [(None, None)] * 3


def test_list_items_never_include_source_text(harness, auth_headers):
    harness.create_contract(auth_headers)
    items = harness.client.get("/contracts", headers=auth_headers).json()["items"]
    assert "source_text" not in items[0]


def test_create_from_txt_file_defaults_title_to_filename(harness, auth_headers):
    harness.use_recording_runner()
    files = {"file": ("Brand Identity SOW.txt", ENGLISH_CONTRACT.encode(), "text/plain")}
    response = harness.client.post("/contracts", files=files, headers=auth_headers)

    assert response.status_code == 202
    body = response.json()
    assert body["title"] == "Brand Identity SOW.txt"
    assert body["filename"] == "Brand Identity SOW.txt"
    assert body["file_type"] == "txt"
    assert body["file_size"] == len(ENGLISH_CONTRACT.encode())


def test_create_from_pdf_file(harness, auth_headers):
    harness.use_recording_runner()
    files = {"file": ("agreement.pdf", text_pdf(ENGLISH_CONTRACT), "application/pdf")}
    response = harness.client.post(
        "/contracts", files=files, data={"title": "Agreement"}, headers=auth_headers
    )

    assert response.status_code == 202
    assert response.json()["file_type"] == "pdf"
    assert response.json()["title"] == "Agreement"


def test_create_with_both_inputs_is_rejected(harness, auth_headers):
    files = {"file": ("c.txt", ENGLISH_CONTRACT.encode(), "text/plain")}
    response = harness.client.post(
        "/contracts", files=files, data={"text": ENGLISH_CONTRACT, "title": "t"}, headers=auth_headers
    )
    assert_error(response, 422, "INVALID_CONTRACT_INPUT")


def test_create_without_input_is_rejected(harness, auth_headers):
    response = harness.client.post("/contracts", data={"title": "t"}, headers=auth_headers)
    assert_error(response, 422, "INVALID_CONTRACT_INPUT")


def test_create_with_pasted_text_requires_title(harness, auth_headers):
    response = harness.client.post("/contracts", data={"text": ENGLISH_CONTRACT}, headers=auth_headers)
    error = assert_error(response, 422, "VALIDATION_ERROR")
    assert error["message"] == "Title is required for pasted text."


def test_create_rejects_oversized_file(harness, auth_headers):
    data = ENGLISH_CONTRACT.encode() + b" " * 5_242_880
    files = {"file": ("big.txt", data, "text/plain")}
    assert_error(harness.client.post("/contracts", files=files, headers=auth_headers), 422, "FILE_TOO_LARGE")


def test_create_requires_auth(client):
    response = client.post("/contracts", data={"text": ENGLISH_CONTRACT, "title": "t"})
    assert_error(response, 401, "UNAUTHORIZED")


# -- list -----------------------------------------------------------------------------


def test_list_is_paginated_newest_first(harness, auth_headers):
    harness.use_recording_runner()
    ids = []
    for index in range(5):
        ids.append(harness.create_contract(auth_headers, title=f"Contract {index}")["id"])
        harness.clock.advance(1)

    response = harness.client.get("/contracts?page=2&page_size=2", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [ids[2], ids[1]]
    assert (body["total_count"], body["page"], body["page_size"], body["total_pages"]) == (5, 2, 2, 3)
    assert set(body["items"][0]) == SUMMARY_FIELDS


def test_list_defaults_and_empty_state(client, auth_headers):
    body = client.get("/contracts", headers=auth_headers).json()
    assert body == {"items": [], "total_count": 0, "page": 1, "page_size": 20, "total_pages": 0}


def test_list_page_beyond_total_is_empty(harness, auth_headers):
    harness.create_contract(auth_headers)
    body = harness.client.get("/contracts?page=5", headers=auth_headers).json()
    assert body["items"] == []
    assert body["total_count"] == 1


def test_list_shows_overall_risk_once_done(harness, auth_headers):
    harness.create_contract(auth_headers)
    item = harness.client.get("/contracts", headers=auth_headers).json()["items"][0]
    assert item["status"] == "done"
    assert item["overall_risk_level"] == "high"


@pytest.mark.parametrize("query", ["page=0", "page_size=0", "page_size=51", "page=abc"])
def test_list_rejects_out_of_range_params(client, auth_headers, query):
    assert_error(client.get(f"/contracts?{query}", headers=auth_headers), 422, "VALIDATION_ERROR")


# -- get / rename / delete --------------------------------------------------------------


@pytest.mark.parametrize("contract_id", [str(uuid4()), "not-a-uuid"])
def test_unknown_contract_is_404(client, auth_headers, contract_id):
    assert_error(client.get(f"/contracts/{contract_id}", headers=auth_headers), 404, "CONTRACT_NOT_FOUND")


def test_rename_trims_title(harness, auth_headers):
    contract_id = harness.create_contract(auth_headers)["id"]
    before = harness.client.get(f"/contracts/{contract_id}", headers=auth_headers).json()
    harness.clock.advance(5)

    response = harness.client.patch(
        f"/contracts/{contract_id}", json={"title": "  New title  "}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["title"] == "New title"
    assert response.json()["updated_at"] != before["updated_at"]
    assert response.json()["findings"] == before["findings"]


@pytest.mark.parametrize("payload", [{"title": "   "}, {"title": "t" * 251}, {}, {"title": "ok", "x": 1}])
def test_rename_validation(harness, auth_headers, payload):
    contract_id = harness.create_contract(auth_headers)["id"]
    response = harness.client.patch(f"/contracts/{contract_id}", json=payload, headers=auth_headers)
    assert_error(response, 422, "VALIDATION_ERROR")


def test_rename_accepts_250_characters(harness, auth_headers):
    contract_id = harness.create_contract(auth_headers)["id"]
    response = harness.client.patch(
        f"/contracts/{contract_id}", json={"title": "t" * 250}, headers=auth_headers
    )
    assert response.status_code == 200


def test_delete_removes_contract_and_results(harness, auth_headers):
    contract_id = harness.create_contract(auth_headers)["id"]

    response = harness.client.delete(f"/contracts/{contract_id}", headers=auth_headers)

    assert response.status_code == 204
    assert response.content == b""
    assert_error(harness.client.get(f"/contracts/{contract_id}", headers=auth_headers), 404, "CONTRACT_NOT_FOUND")
    assert harness.store.get_findings(UUID(contract_id)) == []
    assert harness.store.get_email_draft(UUID(contract_id)) is None


def test_delete_while_analyzing_is_409(harness, auth_headers):
    harness.use_recording_runner()
    contract_id = harness.create_contract(auth_headers)["id"]

    response = harness.client.delete(f"/contracts/{contract_id}", headers=auth_headers)

    assert_error(response, 409, "CONTRACT_ANALYSIS_IN_PROGRESS")


# -- ownership ------------------------------------------------------------------------


def test_other_users_contract_is_indistinguishable_from_missing(harness, auth_headers):
    contract_id = harness.create_contract(auth_headers)["id"]
    intruder = harness.register("intruder@example.com")
    missing = f"/contracts/{uuid4()}"
    owned = f"/contracts/{contract_id}"

    for method, suffix, kwargs in [
        ("get", "", {}),
        ("patch", "", {"json": {"title": "mine now"}}),
        ("delete", "", {}),
        ("post", "/retry", {}),
        ("post", "/export", {"json": {"format": "pdf"}}),
    ]:
        foreign = harness.client.request(method, owned + suffix, headers=intruder, **kwargs)
        absent = harness.client.request(method, missing + suffix, headers=intruder, **kwargs)
        assert_error(foreign, 404, "CONTRACT_NOT_FOUND")
        assert foreign.json() == absent.json()

    assert harness.client.get("/contracts", headers=intruder).json()["total_count"] == 0
    assert harness.client.get(owned, headers=auth_headers).json()["title"] == "Pasted contract"
