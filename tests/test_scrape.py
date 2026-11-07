"""Scraper logic, tested offline. All papers and people here are fake."""

import json
from pathlib import Path

import pandas as pd
import pymupdf
import pytest
from playwright.sync_api import Error as PlaywrightError

from questioniq.scrape import (
    CATALOGUE_COLUMNS,
    MANIFEST_COLUMNS,
    DownloadFailed,
    SessionExpired,
    already_downloaded,
    catalogue_row,
    choose_subjects,
    download_all,
    fetch_bytes,
    is_exam_paper,
    is_pdf,
    list_papers,
    paper_path,
    pdf_info,
    read_manifest,
    save_pdf,
    sha256_file,
    summary_markdown,
    unlisted_files,
    write_manifest,
)

PORTAL = {
    "backend": "https://backend.example.test",
    "max_retries": 3,
    "min_delay_seconds": 1.0,
    "page_size": 20,
    "retry_base_seconds": 15,
}
HEADERS = {"authorization": "fake"}


def make_pdf(text: str) -> bytes:
    """Return a one-page PDF holding the given text."""
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), text)
    return document.tobytes()


TEXT_PDF = make_pdf("\n".join(["toy line of text for the test"] * 5))
BLANK_PDF = make_pdf("toy")


class FakeResponse:
    def __init__(self, status: int, body: bytes = b"") -> None:
        self.status = status
        self._body = body

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def body(self) -> bytes:
        return self._body


class FakeSession:
    """Answers each GET from a list; a list entry that is an exception gets raised."""

    def __init__(self, answers: list) -> None:
        self.answers = list(answers)
        self.urls: list[str] = []

    def get(self, url: str, headers: dict, timeout: int) -> FakeResponse:
        self.urls.append(url)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def api_item(**overrides: object) -> dict:
    item = {
        "id": 7,
        "course_code": "XX1000",
        "course_name": "Toy Subject",
        "title": "XX1000 - Toy Subject - Endterm - 2024",
        "paper_type": "endterm",
        "year": 2024,
        "semester": "5",
        "status": "approved",
        "file_name": "toy.pdf",
        "uploaded_at": "2026-01-01T00:00:00",
        "uploader_name": "Fake Person",
        "uploader_email": "fake@example.test",
        "uploaded_by": 2,
        "public_url": "https://example.test/secret-link",
        "public_link_id": "fake-id",
    }
    return item | overrides


def row(paper_id: int = 7, course: str = "XX1000", **overrides: object) -> dict:
    return catalogue_row(api_item(id=paper_id, course_code=course, **overrides))


def test_catalogue_row_drops_uploader_details_and_public_links() -> None:
    result = catalogue_row(api_item())
    assert list(result) == CATALOGUE_COLUMNS
    assert "Fake Person" not in result.values()
    assert "fake@example.test" not in result.values()
    assert "https://example.test/secret-link" not in result.values()
    assert result["exam_type"] == "Endterm"


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({}, True),
        ({"paper_type": "other"}, True),
        ({"paper_type": "assignment"}, False),
        ({"status": "pending"}, False),
        ({"title": "Assignment 3 - Toy Subject"}, False),
        ({"title": "CODING-HOUR 2 Toy Subject"}, False),
    ],
)
def test_is_exam_paper(overrides: dict, expected: bool) -> None:
    assert is_exam_paper(row(**overrides), ["Assignment"], ["assignment", "coding hour"]) is expected


def test_choose_subjects_puts_multi_year_first_then_most_papers() -> None:
    catalogue = pd.DataFrame(
        [
            {"course": "ONEYEAR", "year": 2024, "paper_id": 1},
            {"course": "ONEYEAR", "year": 2024, "paper_id": 2},
            {"course": "ONEYEAR", "year": 2024, "paper_id": 3},
            {"course": "TWOYEAR", "year": 2023, "paper_id": 4},
            {"course": "TWOYEAR", "year": 2024, "paper_id": 5},
            {"course": "SINGLE", "year": 2024, "paper_id": 6},
        ]
    )
    assert choose_subjects(catalogue) == ["TWOYEAR", "ONEYEAR", "SINGLE"]
    assert choose_subjects(catalogue, limit=2) == ["TWOYEAR", "ONEYEAR"]


def test_paper_path_follows_the_layout() -> None:
    path = paper_path(Path("data/raw"), "AS1202", 2024, "Endterm", 149)
    assert path.as_posix() == "data/raw/AS1202/2024_Endterm_149.pdf"


def test_paper_path_cannot_escape_the_raw_folder() -> None:
    path = paper_path(Path("data/raw"), "../../evil", 2024, "End/term", 1)
    assert ".." not in path.parts
    assert path.parent.parent == Path("data/raw")


def test_is_pdf() -> None:
    assert is_pdf(TEXT_PDF)
    assert not is_pdf(b"<html>Please log in</html>")


def test_sha256_file_matches_a_known_digest(tmp_path: Path) -> None:
    path = tmp_path / "x.txt"
    path.write_bytes(b"abc")
    expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert sha256_file(path) == expected


def test_pdf_info_tells_text_from_nearly_empty_pages(tmp_path: Path) -> None:
    text, blank = tmp_path / "t.pdf", tmp_path / "b.pdf"
    text.write_bytes(TEXT_PDF)
    blank.write_bytes(BLANK_PDF)
    assert pdf_info(text, 50) == (1, True)
    assert pdf_info(blank, 50) == (1, False)


def test_save_pdf_rejects_non_pdf_and_leaves_nothing(tmp_path: Path) -> None:
    dest = tmp_path / "c" / "x.pdf"
    with pytest.raises(DownloadFailed):
        save_pdf(b"<html>Please log in</html>", dest, 50)
    assert not dest.exists()


def test_save_pdf_rejects_corrupt_pdf_and_leaves_nothing(tmp_path: Path) -> None:
    dest = tmp_path / "x.pdf"
    with pytest.raises(DownloadFailed):
        save_pdf(b"%PDF-1.7 this is not really a pdf", dest, 50)
    assert list(tmp_path.iterdir()) == []


def test_fetch_retries_with_backoff_then_succeeds() -> None:
    session = FakeSession([FakeResponse(503), FakeResponse(500), FakeResponse(200, b"ok")])
    waits: list[float] = []
    assert fetch_bytes(session, "u", HEADERS, 3, waits.append) == b"ok"
    assert waits == [2, 4]


def test_fetch_backoff_uses_the_configured_base() -> None:
    session = FakeSession([FakeResponse(500)] * 3 + [FakeResponse(200, b"ok")])
    waits: list[float] = []
    assert fetch_bytes(session, "u", HEADERS, 3, waits.append, 15) == b"ok"
    assert waits == [15, 30, 60]


def test_fetch_gives_up_after_three_retries() -> None:
    session = FakeSession([FakeResponse(503)] * 4)
    with pytest.raises(DownloadFailed, match="HTTP 503"):
        fetch_bytes(session, "u", HEADERS, 3, lambda _: None)
    assert len(session.urls) == 4


def test_fetch_does_not_retry_a_missing_paper() -> None:
    session = FakeSession([FakeResponse(404)])
    with pytest.raises(DownloadFailed, match="HTTP 404"):
        fetch_bytes(session, "u", HEADERS, 3, lambda _: None)
    assert len(session.urls) == 1


def test_fetch_raises_session_expired_on_401() -> None:
    with pytest.raises(SessionExpired):
        fetch_bytes(FakeSession([FakeResponse(401)]), "u", HEADERS, 3, lambda _: None)


def test_fetch_never_keeps_the_playwright_error_message() -> None:
    error = PlaywrightError("call log: authorization: fake-secret")
    with pytest.raises(DownloadFailed) as caught:
        fetch_bytes(FakeSession([error]), "u", HEADERS, 0, lambda _: None)
    assert "fake-secret" not in str(caught.value)


def json_response(data: dict) -> FakeResponse:
    return FakeResponse(200, json.dumps(data).encode())


def test_list_papers_walks_every_year_and_page_politely() -> None:
    session = FakeSession(
        [
            json_response({"years": [2024, 2023]}),
            json_response({"items": [api_item(id=1)], "total": 3, "pages": 3}),
            json_response({"items": [api_item(id=1)], "total": 2, "pages": 2}),
            json_response({"items": [api_item(id=2)], "total": 2, "pages": 2}),
            json_response({"items": [api_item(id=3)], "total": 1, "pages": 1}),
        ]
    )
    waits: list[float] = []
    items = list_papers(session, PORTAL["backend"], HEADERS, PORTAL, waits.append)
    assert [item["id"] for item in items] == [1, 2, 3]
    assert session.urls[3].endswith("page=2&limit=20&year=2024")
    assert session.urls[4].endswith("page=1&limit=20&year=2023")
    assert waits == [1.0] * 5


def test_list_papers_refuses_an_incomplete_list() -> None:
    session = FakeSession(
        [
            json_response({"years": [2024]}),
            json_response({"items": [api_item()], "total": 5, "pages": 5}),
            json_response({"items": [api_item()], "total": 1, "pages": 1}),
        ]
    )
    with pytest.raises(DownloadFailed, match="Listed 1 papers but the portal says 5"):
        list_papers(session, PORTAL["backend"], HEADERS, PORTAL, lambda _: None)


def run_download(session: FakeSession, rows: list[dict], tmp_path: Path) -> tuple[Path, list, list]:
    """Run download_all into tmp_path; return the manifest path, failures and waits."""
    manifest_path = tmp_path / "manifest.csv"
    failures: list[dict] = []
    waits: list[float] = []
    download_all(
        session, rows, HEADERS, PORTAL, tmp_path / "raw", manifest_path, 50, failures, waits.append
    )
    return manifest_path, failures, waits


def test_download_all_writes_files_and_manifest_with_the_plan_columns(tmp_path: Path) -> None:
    session = FakeSession([FakeResponse(200, TEXT_PDF), FakeResponse(200, BLANK_PDF)])
    manifest_path, failures, waits = run_download(session, [row(1), row(2)], tmp_path)
    manifest = read_manifest(manifest_path)
    assert failures == []
    assert waits == [1.0]
    assert list(manifest["1"]) == MANIFEST_COLUMNS
    assert manifest["1"]["has_text_layer"] == "True"
    assert manifest["2"]["has_text_layer"] == "False"
    assert already_downloaded(manifest["1"])
    assert unlisted_files(tmp_path / "raw", manifest) == []


def test_second_run_skips_files_whose_sha256_matches(tmp_path: Path) -> None:
    run_download(FakeSession([FakeResponse(200, TEXT_PDF)]), [row(1)], tmp_path)
    second = FakeSession([])
    run_download(second, [row(1)], tmp_path)
    assert second.urls == []


def test_changed_file_is_downloaded_again(tmp_path: Path) -> None:
    manifest_path, _, _ = run_download(FakeSession([FakeResponse(200, TEXT_PDF)]), [row(1)], tmp_path)
    Path(read_manifest(manifest_path)["1"]["path"]).write_bytes(b"damaged")
    second = FakeSession([FakeResponse(200, TEXT_PDF)])
    run_download(second, [row(1)], tmp_path)
    assert len(second.urls) == 1


def test_first_paper_failing_stops_the_run(tmp_path: Path) -> None:
    session = FakeSession([FakeResponse(404), FakeResponse(200, TEXT_PDF)])
    with pytest.raises(DownloadFailed):
        run_download(session, [row(1), row(2)], tmp_path)
    assert len(session.urls) == 1


def test_later_failure_is_recorded_and_the_run_continues(tmp_path: Path) -> None:
    session = FakeSession(
        [FakeResponse(200, TEXT_PDF), FakeResponse(404), FakeResponse(200, TEXT_PDF)]
    )
    manifest_path, failures, _ = run_download(session, [row(1), row(2), row(3)], tmp_path)
    assert sorted(read_manifest(manifest_path)) == ["1", "3"]
    assert [failure["paper_id"] for failure in failures] == ["2"]


def test_expired_session_stops_but_keeps_progress(tmp_path: Path) -> None:
    session = FakeSession([FakeResponse(200, TEXT_PDF), FakeResponse(401)])
    with pytest.raises(SessionExpired):
        run_download(session, [row(1), row(2)], tmp_path)
    assert sorted(read_manifest(tmp_path / "manifest.csv")) == ["1"]


def test_unlisted_files_finds_both_kinds_of_mismatch(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "stray.pdf").write_bytes(TEXT_PDF)
    manifest = {"1": {"path": (raw / "gone.pdf").as_posix()}}
    assert unlisted_files(raw, manifest) == sorted(
        [(raw / "gone.pdf").as_posix(), (raw / "stray.pdf").as_posix()]
    )


def test_summary_reports_subjects_and_everything_needing_a_look() -> None:
    base = {"course": "XX1", "course_name": "Toy", "year": "2024", "sha256": "same"}
    manifest = {
        "1": base | {"paper_id": "1", "title": "One", "exam_type": "Endterm", "has_text_layer": "False"},
        "2": base | {"paper_id": "2", "title": "Two", "exam_type": "Other", "has_text_layer": "True"},
    }
    catalogue = [
        {"paper_id": 1, "title": "One"},
        {"paper_id": 2, "title": "Two"},
        {"paper_id": 3, "title": "Skipped assignment"},
        {"paper_id": 4, "title": "Broken"},
    ]
    failures = [{"paper_id": "4", "title": "Broken", "reason": "HTTP 404"}]
    text = summary_markdown(manifest, catalogue, failures)
    assert "| Toy | XX1 | 2 | 2024 | Endterm, Other | 1 | 1 |" in text
    assert "4: Broken (HTTP 404)" in text
    assert "3: Skipped assignment" in text
    assert "- 2: Two" in text
    assert "- 1, 2" in text


def test_write_manifest_refuses_columns_outside_the_plan(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_manifest([{"uploader_email": "fake@example.test"}], tmp_path / "m.csv")
