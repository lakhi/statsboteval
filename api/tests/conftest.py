from pathlib import Path

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "aggregates_synthetic.json"


class FakeSource:
    """Stands in for the blob: returns a fixed payload, counts fetches."""

    def __init__(self, payload: bytes | None) -> None:
        self.payload = payload
        self.calls = 0

    def fetch(self) -> bytes | None:
        self.calls += 1
        return self.payload
