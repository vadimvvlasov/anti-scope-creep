"""Test doubles shared by unit and API tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class RecordingRunner:
    """Records scheduled runs instead of executing them, so tests control timing."""

    def __init__(self) -> None:
        self.scheduled: list[tuple[UUID, UUID]] = []

    def schedule(self, contract_id: UUID, run_id: UUID) -> None:
        self.scheduled.append((contract_id, run_id))


class FailingAnalyzer:
    def analyze(self, source_text: str):
        raise RuntimeError("analyzer exploded")
