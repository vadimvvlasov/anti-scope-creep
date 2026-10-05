"""openapi.yaml is the API contract; the FastAPI app must not drift from it.

The hand-written file is the source of truth and is never generated from the app.
This test compares it with `app.openapi()`:
- both have the same operations (method + path);
- every operation has the same success (2xx) status;
- the app documents no error status that the contract lacks;
- every schema both define has the same properties, required fields, and enum values.

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
Shape = dict[str, list]


def _operations(spec: dict) -> Operations:
    return {
        (method.upper(), path): {str(status) for status in operation.get("responses", {})}
        for path, item in spec["paths"].items()
        for method, operation in item.items()
        if method in METHODS
    }


def _success(statuses: set[str]) -> set[str]:
    return {status for status in statuses if status.startswith("2")}


def _shapes(spec: dict) -> dict[str, Shape]:
    """Each component schema as its properties, required fields, and enum values."""
    schemas = spec["components"]["schemas"]
    return {name: _shape(schema, schemas) for name, schema in schemas.items()}


def _shape(schema: dict, schemas: dict) -> Shape:
    """Flattens `allOf` and `$ref`, so ContractDetail compares with the app's flat model."""
    if "$ref" in schema:
        return _shape(schemas[schema["$ref"].rsplit("/", 1)[-1]], schemas)
    shape: Shape = {
        "properties": sorted(schema.get("properties", {})),
        "required": sorted(schema.get("required", [])),
        "enum": sorted(schema.get("enum", [])),
    }
    for part in schema.get("allOf", []):
        for key, values in _shape(part, schemas).items():
            shape[key] = sorted({*shape[key], *values})
    return shape


@pytest.fixture(scope="module")
def contract_spec() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


@pytest.fixture(scope="module")
def generated_spec() -> dict:
    return Harness().app.openapi()


@pytest.fixture(scope="module")
def contract(contract_spec: dict) -> Operations:
    return _operations(contract_spec)


@pytest.fixture(scope="module")
def generated(generated_spec: dict) -> Operations:
    return _operations(generated_spec)


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


def test_shared_schemas_match(contract_spec: dict, generated_spec: dict):
    ours, theirs = _shapes(contract_spec), _shapes(generated_spec)
    mismatched = {
        name: {key: (ours[name][key], theirs[name][key]) for key in ours[name] if ours[name][key] != theirs[name][key]}
        for name in ours.keys() & theirs.keys()
        if ours[name] != theirs[name]
    }
    assert mismatched == {}, "(openapi.yaml, app) schemas differ"
