import pytest
from fastapi.testclient import TestClient

from app.analyzer import Analyzer, StubAnalyzer
from app.config import Settings
from app.context import AppContext
from app.main import create_app
from app.store import InMemoryStore
from tests.fakes import FakeClock, RecordingRunner
from tests.samples import ENGLISH_CONTRACT, TEST_JWT_SECRET


class Harness:
    """A test app plus handles on its collaborators."""

    def __init__(self, analyzer: Analyzer | None = None, stale_after: int = 600):
        self.settings = Settings(
            jwt_secret=TEST_JWT_SECRET, analysis_stale_after_seconds=stale_after, seed_demo_data=False
        )
        self.store = InMemoryStore()
        self.clock = FakeClock()
        self.analyzer = analyzer or StubAnalyzer()
        self.app = create_app(self.settings, self.store, self.analyzer, self.clock)
        self.client = TestClient(self.app)

    @property
    def context(self) -> AppContext:
        return self.app.state.context

    def use_recording_runner(self) -> RecordingRunner:
        from app.routers.contracts import get_runner

        runner = RecordingRunner()
        self.app.dependency_overrides[get_runner] = lambda: runner
        return runner

    def register(self, email: str = "user@example.com", password: str = "password123") -> dict:
        response = self.client.post("/auth/register", json={"email": email, "password": password})
        assert response.status_code == 201, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def paste(self, headers: dict, text: str = ENGLISH_CONTRACT, title: str = "Pasted contract"):
        return self.client.post("/contracts", data={"text": text, "title": title}, headers=headers)

    def create_contract(self, headers: dict, **kwargs) -> dict:
        response = self.paste(headers, **kwargs)
        assert response.status_code == 202, response.text
        return response.json()


@pytest.fixture
def harness() -> Harness:
    return Harness()


@pytest.fixture
def client(harness: Harness) -> TestClient:
    return harness.client


@pytest.fixture
def auth_headers(harness: Harness) -> dict:
    return harness.register()


def assert_error(response, status_code: int, code: str) -> dict:
    assert response.status_code == status_code, response.text
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert body["error"]["message"]
    return body["error"]
