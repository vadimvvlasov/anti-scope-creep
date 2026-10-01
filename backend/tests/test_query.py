import pytest

from tests.conftest import assert_error


def test_valid_question_returns_501_feature_not_available(client, auth_headers):
    response = client.post(
        "/query", json={"question": "Which contracts had uncapped liability this month?"}, headers=auth_headers
    )
    error = assert_error(response, 501, "FEATURE_NOT_AVAILABLE")
    assert error["message"] == "History search is coming soon."


def test_500_character_question_is_accepted(client, auth_headers):
    response = client.post("/query", json={"question": f"  {'q' * 500}  "}, headers=auth_headers)
    assert_error(response, 501, "FEATURE_NOT_AVAILABLE")


@pytest.mark.parametrize("payload", [{"question": "   "}, {"question": "q" * 501}, {}, {"question": 5}])
def test_invalid_question_is_validation_error(client, auth_headers, payload):
    assert_error(client.post("/query", json=payload, headers=auth_headers), 422, "VALIDATION_ERROR")


def test_query_requires_auth(client):
    assert_error(client.post("/query", json={"question": "anything"}), 401, "UNAUTHORIZED")
