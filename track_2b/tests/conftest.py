"""Tests run in replay mode: no model, no network. Set before anything imports briefklar.config."""

import os
import tempfile
from pathlib import Path

os.environ["BRIEFKLAR_MODE"] = "replay"
os.environ["BRIEFKLAR_RECORD"] = "0"
os.environ.setdefault("BRIEFKLAR_TMP", tempfile.mkdtemp(prefix="briefklar-test-"))
os.environ.pop("BRIEFKLAR_TODAY", None)

import pytest  # noqa: E402

PROJECT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from briefklar.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def wait_ready(client, case_id: str) -> dict:
    import time

    for _ in range(300):
        case = client.get(f"/api/cases/{case_id}").json()
        if case["status"] == "ready":
            return case
        time.sleep(0.05)
    raise AssertionError("the case was not ready in time")


@pytest.fixture
def demo_case(client):
    """The demo case, processed from cached responses, with the payment order's delivery date entered."""
    case_id = client.post("/api/demo", json={"client_language": "sq"}).json()["case_id"]
    assert client.post(f"/api/cases/{case_id}/process").json()["started"]
    wait_ready(client, case_id)
    case = client.post(f"/api/letters/demo-03.{case_id}/delivery-date", json={"date": "2026-10-08"}).json()
    yield case
    client.delete(f"/api/cases/{case_id}")
