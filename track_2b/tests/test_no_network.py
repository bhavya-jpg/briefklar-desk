"""Nothing at runtime may open a network connection other than to LLM_BASE_URL (spec 17.1)."""

import re
import socket
from pathlib import Path

import pytest

from tests.conftest import wait_ready

ROOT = Path(__file__).resolve().parent.parent
# local checkout: frontend/build; Docker image: /app/static
BUILD = next((p for p in (ROOT / "frontend" / "build", ROOT / "static") if p.is_dir()), ROOT / "frontend" / "build")
# Strings that look like URLs but are never fetched: XML namespaces and links inside error messages.
NOT_FETCHED = ("http://www.w3.org/", "https://svelte.dev/")


def test_demo_case_opens_no_outbound_connection(client, monkeypatch):
    attempts = []

    def blocked_connect(self, address, *args, **kwargs):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            attempts.append(address)
            raise OSError(f"blocked outbound connection to {address}")
        return original(self, address, *args, **kwargs)

    def blocked_create(address, *args, **kwargs):
        attempts.append(address)
        raise OSError(f"blocked outbound connection to {address}")

    original = socket.socket.connect
    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    monkeypatch.setattr(socket, "create_connection", blocked_create)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: attempts.append(a) or [])

    case_id = client.post("/api/demo", json={"client_language": "ar"}).json()["case_id"]
    client.post(f"/api/cases/{case_id}/process")
    case = wait_ready(client, case_id)
    assert all(letter["status"] == "done" for letter in case["letters"])
    letter_id = next(l["id"] for l in case["letters"] if l["label"] == "demo-03")
    client.post(f"/api/letters/{letter_id}/delivery-date", json={"date": "2026-10-08"})
    reply = client.post(f"/api/letters/{letter_id}/replies", json={"template_id": "objection_payment_order"}).json()["reply"]
    client.put(f"/api/replies/{reply['id']}", json={"slots": {"place": "Bern"}})
    for url in (f"/api/replies/{reply['id']}.pdf", f"/api/cases/{case_id}/handout.pdf", f"/api/cases/{case_id}/case-note.pdf"):
        assert client.get(url).status_code == 200
    client.delete(f"/api/cases/{case_id}")
    assert attempts == []


def test_app_sends_a_same_origin_content_security_policy(client):
    policy = client.get("/api/health").headers["content-security-policy"]
    assert "default-src 'self'" in policy and "connect-src 'self'" in policy and "font-src 'self'" in policy
    assert "http" not in policy


def test_frontend_bundle_references_no_external_origin():
    if not BUILD.is_dir():
        pytest.skip("frontend/build is missing: run `npm run build` in frontend/ (the Docker image always builds it)")
    found = {}
    for path in BUILD.rglob("*"):
        if path.suffix not in {".js", ".css", ".html", ".svg", ".json"}:
            continue
        for url in re.findall(r"""https?://[^\s"'`)<>\\]+""", path.read_text(encoding="utf-8", errors="ignore")):
            if not url.startswith(NOT_FETCHED):
                found.setdefault(url, path.name)
    assert found == {}, f"external origins in the bundle: {found}"


def test_fonts_are_self_hosted_with_licences():
    fonts = next(p for p in (ROOT / "frontend" / "static" / "fonts", BUILD / "fonts") if p.is_dir())
    assert len(list(fonts.glob("*.woff2"))) >= 20
    for family in ("inter-tight", "jetbrains-mono", "noto-sans", "noto-sans-arabic", "noto-sans-ethiopic", "noto-sans-tamil"):
        licence = fonts / "licenses" / f"{family}-LICENSE.txt"
        assert "SIL Open Font License" in licence.read_text(encoding="utf-8")
