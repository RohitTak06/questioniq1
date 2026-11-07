"""The discovery log must never hold secrets. All values here are fake."""

import pytest

from scripts.discover_api import (
    MASK,
    is_auth_url,
    is_backend_request,
    log_entry,
    looks_signed_in,
    redact_json_snippet,
    redact_url,
)

BACKEND = "https://backend.example.test"
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.c2lnbmF0dXJlLWZha2U"


def test_is_backend_request_matches_host_only() -> None:
    assert is_backend_request(f"{BACKEND}/papers?page=2", BACKEND)
    assert not is_backend_request("https://accounts.example.test/signin", BACKEND)


@pytest.mark.parametrize(
    "path",
    ["/auth/login", "/api/token", "/users/me", "/me", "/user", "/profile", "/session"],
)
def test_is_auth_url_catches_login_and_account_routes(path: str) -> None:
    assert is_auth_url(f"{BACKEND}{path}")


@pytest.mark.parametrize(
    "path",
    ["/courses", "/papers", "/papers/metadata", "/papers/public", "/papers/12/preview"],
)
def test_is_auth_url_leaves_paper_routes_alone(path: str) -> None:
    assert not is_auth_url(f"{BACKEND}{path}")


def test_redact_url_masks_sensitive_parameters() -> None:
    url = f"{BACKEND}/papers?access_token=fake123&code=fake456&email=a%40b.test&sig=fake789"
    redacted = redact_url(url)
    for secret in ("fake123", "fake456", "a%40b.test", "fake789"):
        assert secret not in redacted
    assert redacted.count(MASK) == 4


def test_redact_url_keeps_useful_parameters() -> None:
    redacted = redact_url(f"{BACKEND}/papers?page=2&limit=20&year=2024&courseCode=AS1202")
    assert redacted == f"{BACKEND}/papers?page=2&limit=20&year=2024&courseCode=AS1202"


def test_redact_url_removes_fragment_and_masks_token_in_path() -> None:
    redacted = redact_url(f"{BACKEND}/files/{FAKE_JWT}#access_token=fake123")
    assert "fake123" not in redacted
    assert FAKE_JWT not in redacted


def test_redact_json_masks_sensitive_fields() -> None:
    text = '{"token": "fake123", "user_email": "a@b.test", "refreshToken": "fake456", "pwd": 99}'
    redacted = redact_json_snippet(text)
    for secret in ("fake123", "a@b.test", "fake456", "99"):
        assert secret not in redacted


def test_redact_json_masks_secrets_under_innocent_names() -> None:
    text = f'{{"note": "{FAKE_JWT}", "contact": "a@b.test", "h": "Bearer fake.value-1"}}'
    redacted = redact_json_snippet(text)
    for secret in (FAKE_JWT, "a@b.test", "fake.value-1"):
        assert secret not in redacted


def test_redact_json_keeps_paper_metadata() -> None:
    text = '{"courseCode": "AS1202", "title": "Advanced Statistics - Endterm", "year": 2024}'
    assert redact_json_snippet(text) == text


def test_redact_json_masks_before_cutting() -> None:
    text = '{"title": "' + "x" * 490 + f'", "token": "{FAKE_JWT}"}}'
    redacted = redact_json_snippet(text)
    assert len(redacted) <= 500
    assert "eyJ" not in redacted


def test_log_entry_drops_body_of_auth_urls() -> None:
    entry = log_entry("POST", f"{BACKEND}/auth/login", 200, [], [], "application/json", '{"a": 1}')
    assert entry["body_snippet"] is None


def test_log_entry_keeps_names_and_never_has_a_request_body_field() -> None:
    entry = log_entry(
        "GET",
        f"{BACKEND}/papers?page=2",
        200,
        ["authorization", "accept"],
        ["content-type"],
        "application/json",
        '{"total": 150}',
    )
    assert entry["request_header_names"] == ["accept", "authorization"]
    assert entry["query"] == {"page": "2"}
    assert entry["body_snippet"] == '{"total": 150}'
    assert "request_body" not in entry


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Total available: 150", True),
        ("Total available\n150", True),
        ("Total available: 0", False),
        ("Sign in to continue", False),
        ("Browse papers instantly. Access your dashboard after registration.", False),
        ("All Papers\n0\nMidterm\nEndterm\nOther\nLogin\nSign Up", False),
    ],
)
def test_looks_signed_in(text: str, expected: bool) -> None:
    assert looks_signed_in(text) is expected
