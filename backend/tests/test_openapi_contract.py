"""openapi.yaml is the API contract; the FastAPI app must not drift from it.

The hand-written file is the source of truth and is never generated from the app.
This test compares it with `app.openapi()`:
- both have the same operations (method + path);
- every operation has the same success (2xx) status;
- the app documents no error status that the contract lacks.

Error responses that exist only in openapi.yaml (401, 404, 409, 500, 501) are expected:
FastAPI only documents what a route signature declares, and these errors are raised in
dependencies and exception handlers.
"""

from pathlib import Path

import pytest
import yaml

from tests.conftest import Harness

CONTRACT = Path(__file__).resolve().parents[2] / "openapi.yaml"
METHODS = {"get", "post", "put", "patch", "delete"}

# FastAPI adds 422 to every route with parameters. On these routes the only parameter is
# the contract id, a plain str parsed inside the route: a malformed id returns
# 404 CONTRACT_NOT_FOUND, so this 422 can never happen.
NEVER_RETURNED = {
    ("GET", "/contracts/{id}"): {"422"},
    ("DELETE", "/contracts/{id}"): {"422"},
    ("POST", "/contracts/{id}/retry"): {"422"},
}

Operations = dict[tuple[str, str], set[str]]


def _operations(spec: dict) -> Operations:
    return {
        (method.upper(), path): {str(status) for status in operation.get("responses", {})}
        for path, item in spec["paths"].items()
        for method, operation in item.items()
        if method in METHODS
    }


def _success(statuses: set[str]) -> set[str]:
    return {status for status in statuses if status.startswith("2")}


@pytest.fixture(scope="module")
def contract() -> Operations:
    return _operations(yaml.safe_load(CONTRACT.read_text()))


@pytest.fixture(scope="module")
def generated() -> Operations:
    return _operations(Harness().app.openapi())


def test_operations_match(contract: Operations, generated: Operations):
    assert sorted(generated.keys() - contract.keys()) == [], "in the app, missing from openapi.yaml"
    assert sorted(contract.keys() - generated.keys()) == [], "in openapi.yaml, missing from the app"


def test_success_statuses_match(contract: Operations, generated: Operations):
    mismatched = {
        op: (sorted(_success(contract[op])), sorted(_success(generated[op])))
        for op in contract.keys() & generated.keys()
        if _success(contract[op]) != _success(generated[op])
    }
    assert mismatched == {}, "(openapi.yaml, app) success statuses differ"


def test_app_documents_no_error_missing_from_the_contract(contract: Operations, generated: Operations):
    undocumented = {
        op: sorted(extra)
        for op in contract.keys() & generated.keys()
        if (extra := generated[op] - contract[op] - NEVER_RETURNED.get(op, set()))
    }
    assert undocumented == {}, "error statuses the app documents but openapi.yaml does not"


def test_never_returned_exceptions_are_still_needed(generated: Operations):
    stale = {op: sorted(codes - generated.get(op, set())) for op, codes in NEVER_RETURNED.items()}
    assert {op: codes for op, codes in stale.items() if codes} == {}, "drop exceptions FastAPI no longer adds"
