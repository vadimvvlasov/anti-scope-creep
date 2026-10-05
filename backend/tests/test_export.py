from uuid import uuid4

import pytest

from tests.conftest import assert_error


@pytest.mark.parametrize("fmt", ["pdf", "docx"])
def test_export_of_own_contract_returns_501_feature_not_available(harness, auth_headers, fmt):
    contract_id = harness.create_contract(auth_headers)["id"]
    response = harness.client.post(
        f"/contracts/{contract_id}/export", json={"format": fmt}, headers=auth_headers
    )
    error = assert_error(response, 501, "FEATURE_NOT_AVAILABLE")
    assert error["message"] == "Report export is coming soon."


@pytest.mark.parametrize("contract_id", [str(uuid4()), "not-a-uuid"])
def test_export_of_unknown_contract_is_404(client, auth_headers, contract_id):
    response = client.post(f"/contracts/{contract_id}/export", json={"format": "pdf"}, headers=auth_headers)
    assert_error(response, 404, "CONTRACT_NOT_FOUND")


@pytest.mark.parametrize(
    "payload", [{}, {"format": "txt"}, {"format": "PDF"}, {"format": "pdf", "logo": "x"}]
)
def test_export_validates_the_body(harness, auth_headers, payload):
    contract_id = harness.create_contract(auth_headers)["id"]
    response = harness.client.post(f"/contracts/{contract_id}/export", json=payload, headers=auth_headers)
    assert_error(response, 422, "VALIDATION_ERROR")


def test_export_requires_auth(harness, auth_headers):
    contract_id = harness.create_contract(auth_headers)["id"]
    response = harness.client.post(f"/contracts/{contract_id}/export", json={"format": "pdf"})
    assert_error(response, 401, "UNAUTHORIZED")
