"""Download previous-year papers from the JKLU Paper Portal (Phase 0b, step 2).

Reuses the owner's saved session from .auth/. If it has expired, a visible
browser opens and the owner signs in by hand. The auth header is copied from the
site's own request and kept in memory only. One request at a time, at least
min_delay_seconds apart.

Run from the project root: python -m questioniq.scrape
"""

import csv
import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd
import pdfplumber
from playwright.sync_api import APIRequestContext, BrowserContext, Page, Playwright, Request
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from questioniq.config import load_config

CATALOGUE_COLUMNS = [
    "paper_id",
    "course",
    "course_name",
    "title",
    "year",
    "exam_type",
    "semester",
    "status",
    "file_name",
    "uploaded_at",
]
MANIFEST_COLUMNS = [
    "course",
    "course_name",
    "title",
    "year",
    "exam_type",
    "semester",
    "paper_id",
    "path",
    "sha256",
    "n_pages",
    "has_text_layer",
    "downloaded_at",
]
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
REQUEST_TIMEOUT_MS = 60000
SESSION_WAIT_MS = 8000
SIGN_IN_POLL_MS = 2000
TOTAL_AVAILABLE = re.compile(r"total available\D*[1-9]", re.I)


class SessionExpired(Exception):
    """The backend rejected the saved session, so the owner must sign in again."""


class DownloadFailed(Exception):
    """One request or paper failed; the message is safe to show and save."""


def looks_signed_in(page_text: str) -> bool:
    """Return True if the page shows a non-zero "Total available".

    The word "Dashboard" is not enough: the public landing page says it too.
    """
    return bool(TOTAL_AVAILABLE.search(page_text))


def wait_for_sign_in(page: Page, timeout_seconds: int) -> None:
    """Wait until the owner has signed in by hand; raise TimeoutError if they haven't."""
    for _ in range(timeout_seconds * 1000 // SIGN_IN_POLL_MS):
        try:
            if looks_signed_in(page.locator("body").inner_text(timeout=SIGN_IN_POLL_MS)):
                return
        except PlaywrightError:
            if page.is_closed():
                raise
        page.wait_for_timeout(SIGN_IN_POLL_MS)
    raise TimeoutError(f"No sign-in seen within {timeout_seconds} s")


def fetch_bytes(
    session: APIRequestContext,
    url: str,
    headers: dict[str, str],
    max_retries: int,
    sleep: Callable[[float], None] = time.sleep,
    retry_base_seconds: float = 2.0,
) -> bytes:
    """GET a URL, retrying with backoff. Raise SessionExpired on 401, DownloadFailed otherwise."""
    reason = "not attempted"
    for attempt in range(max_retries + 1):
        if attempt:
            sleep(retry_base_seconds * 2 ** (attempt - 1))
        try:
            response = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT_MS)
            if response.status == 401:
                raise SessionExpired("The backend answered 401")
            if response.ok:
                return response.body()
            reason = f"HTTP {response.status}"
            if response.status not in RETRYABLE_STATUS:
                break
        except PlaywrightError:
            # Playwright's message can echo request headers, so it is never kept.
            reason = "network error"
    raise DownloadFailed(reason)


def list_papers(
    session: APIRequestContext,
    backend: str,
    headers: dict[str, str],
    portal: dict,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict]:
    """Return every paper on the portal, listed one year at a time.

    The plain list answers HTTP 500 past about position 142, so it can't reach the
    last papers. Year filters can. The result must match the portal's total.
    """

    def get_json(url: str) -> dict:
        body = fetch_bytes(
            session, url, headers, portal["max_retries"], sleep, portal["retry_base_seconds"]
        )
        sleep(portal["min_delay_seconds"])
        return json.loads(body)

    years = get_json(f"{backend}/papers/metadata")["years"]
    total = get_json(f"{backend}/papers/public/all?page=1&limit=1")["total"]
    items: dict[int, dict] = {}
    for year in years:
        page = 1
        while True:
            query = f"page={page}&limit={portal['page_size']}&year={year}"
            data = get_json(f"{backend}/papers/public/all?{query}")
            items.update({item["id"]: item for item in data["items"]})
            if page >= data["pages"]:
                break
            page += 1
    if len(items) != total:
        raise DownloadFailed(f"Listed {len(items)} papers but the portal says {total}")
    return list(items.values())


def catalogue_row(item: dict) -> dict:
    """Keep only the fields we need. Uploader details and public links are dropped."""
    return {
        "paper_id": item["id"],
        "course": item["course_code"],
        "course_name": item["course_name"],
        "title": item["title"],
        "year": item["year"],
        "exam_type": item["paper_type"].capitalize(),
        "semester": item["semester"],
        "status": item["status"],
        "file_name": item["file_name"],
        "uploaded_at": item["uploaded_at"],
    }


def is_exam_paper(row: dict, skip_types: list[str], skip_title_words: list[str]) -> bool:
    """Return True for approved papers that are not assignments or coding-hour items."""
    title = str(row["title"]).lower().replace("-", " ")
    return (
        row["status"] == "approved"
        and row["exam_type"] not in skip_types
        and not any(word in title for word in skip_title_words)
    )


def choose_subjects(catalogue: pd.DataFrame, limit: int | None = None) -> list[str]:
    """Rank courses: papers in 2 or more years first, then the most papers, then by code."""
    grouped = catalogue.groupby("course").agg(
        n_years=("year", "nunique"), n_papers=("paper_id", "count")
    )
    grouped["multi_year"] = grouped["n_years"] >= 2
    ranked = grouped.reset_index().sort_values(
        ["multi_year", "n_papers", "course"], ascending=[False, False, True]
    )
    return ranked["course"].tolist()[:limit]


def paper_path(raw_dir: Path, course: str, year: int, exam_type: str, paper_id: int) -> Path:
    """Return data/raw/<course>/<year>_<exam>_<id>.pdf, with unsafe characters replaced."""

    def safe(text: object) -> str:
        return re.sub(r"[^A-Za-z0-9_-]+", "_", str(text)).strip("_") or "unknown"

    return raw_dir / safe(course) / f"{safe(year)}_{safe(exam_type)}_{safe(paper_id)}.pdf"


def is_pdf(data: bytes) -> bool:
    """Return True if the bytes start like a PDF file."""
    return data.startswith(b"%PDF")


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_info(path: Path, min_chars: int) -> tuple[int, bool]:
    """Return the page count and whether any page has at least min_chars of real text."""
    with pdfplumber.open(path) as pdf:
        has_text = any(len((page.extract_text() or "").strip()) >= min_chars for page in pdf.pages)
        return len(pdf.pages), has_text


def save_pdf(data: bytes, dest: Path, min_chars: int) -> tuple[int, bool]:
    """Check the bytes are a readable PDF, then save them. A bad file never reaches dest."""
    if not is_pdf(data):
        raise DownloadFailed("Response is not a PDF")
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_name(dest.name + ".part")
    temp.write_bytes(data)
    try:
        info = pdf_info(temp, min_chars)
    except Exception as error:
        temp.unlink()
        raise DownloadFailed(f"Unreadable PDF ({type(error).__name__})") from None
    temp.replace(dest)
    return info


def write_csv(rows: list[dict], path: Path, columns: list[str]) -> None:
    """Write rows to a CSV file, replacing it in one step so a crash can't truncate it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with open(temp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def write_manifest(rows: list[dict], path: Path) -> None:
    """Write one row per downloaded paper to the manifest CSV."""
    write_csv(rows, path, MANIFEST_COLUMNS)


def read_manifest(path: Path) -> dict[str, dict]:
    """Return the existing manifest keyed by paper_id, or an empty dict if there is none."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8", newline="") as f:
        return {row["paper_id"]: row for row in csv.DictReader(f)}


def already_downloaded(row: dict | None) -> bool:
    """Return True if a manifest row's file exists and its sha256 still matches."""
    if row is None or not Path(row["path"]).is_file():
        return False
    return sha256_file(Path(row["path"])) == row["sha256"]


def download_paper(
    session: APIRequestContext,
    row: dict,
    headers: dict[str, str],
    portal: dict,
    raw_dir: Path,
    min_chars: int,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Download one paper and return its manifest row."""
    url = f"{portal['backend']}/papers/{row['paper_id']}/download"
    data = fetch_bytes(
        session, url, headers, portal["max_retries"], sleep, portal["retry_base_seconds"]
    )
    dest = paper_path(raw_dir, row["course"], row["year"], row["exam_type"], row["paper_id"])
    n_pages, has_text = save_pdf(data, dest, min_chars)
    return {
        "course": row["course"],
        "course_name": row["course_name"],
        "title": row["title"],
        "year": row["year"],
        "exam_type": row["exam_type"],
        "semester": row["semester"],
        "paper_id": row["paper_id"],
        "path": dest.as_posix(),
        "sha256": sha256_file(dest),
        "n_pages": n_pages,
        "has_text_layer": has_text,
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def download_all(
    session: APIRequestContext,
    rows: list[dict],
    headers: dict[str, str],
    portal: dict,
    raw_dir: Path,
    manifest_path: Path,
    min_chars: int,
    failures: list[dict],
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Download papers one at a time, saving the manifest after each.

    Papers already on disk are skipped. If the very first attempt fails, stop,
    because something is wrong with every download rather than with one paper.
    """
    manifest = read_manifest(manifest_path)
    any_success = False
    for number, row in enumerate(rows, start=1):
        paper_id = str(row["paper_id"])
        label = f"[{number}/{len(rows)}] paper {paper_id}"
        if already_downloaded(manifest.get(paper_id)):
            any_success = True
            print(f"{label}: already downloaded", flush=True)
            continue
        try:
            manifest[paper_id] = download_paper(
                session, row, headers, portal, raw_dir, min_chars, sleep
            )
            write_manifest(list(manifest.values()), manifest_path)
            any_success = True
            kind = "text" if manifest[paper_id]["has_text_layer"] else "scan"
            print(f"{label}: ok, {manifest[paper_id]['n_pages']} pages, {kind}", flush=True)
        except DownloadFailed as error:
            failures.append({"paper_id": paper_id, "title": row["title"], "reason": str(error)})
            print(f"{label}: FAILED, {error}", flush=True)
            if not any_success:
                raise
        if number < len(rows):
            sleep(portal["min_delay_seconds"])


def unlisted_files(raw_dir: Path, manifest: dict[str, dict]) -> list[str]:
    """Return PDFs on disk missing from the manifest, and manifest paths missing from disk."""
    on_disk = {path.as_posix() for path in raw_dir.rglob("*.pdf")}
    listed = {row["path"] for row in manifest.values()}
    return sorted(on_disk ^ listed)


def summary_markdown(
    manifest: dict[str, dict], catalogue: list[dict], failures: list[dict]
) -> str:
    """Build the collection report: one row per subject, then anything needing a look."""

    def cell(text: object) -> str:
        return str(text).replace("|", "\\|")

    by_course: dict[str, list[dict]] = defaultdict(list)
    for row in manifest.values():
        by_course[row["course"]].append(row)

    n_text = sum(str(row["has_text_layer"]) == "True" for row in manifest.values())
    lines = [
        "# Collection summary",
        "",
        f"- Papers on the portal: {len(catalogue)}",
        f"- Subjects downloaded: {len(by_course)}",
        f"- Papers downloaded: {len(manifest)} ({len(manifest) - n_text} scanned, {n_text} text)",
        f"- Failed: {len(failures)}",
        "",
        "| Subject | Course code | Papers | Years | Exam types | Scanned | Text |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for course in sorted(by_course):
        rows = by_course[course]
        years = ", ".join(sorted({str(row["year"]) for row in rows}))
        types = ", ".join(sorted({row["exam_type"] for row in rows}))
        text = sum(str(row["has_text_layer"]) == "True" for row in rows)
        lines.append(
            f"| {cell(rows[0]['course_name'])} | {cell(course)} | {len(rows)} | {years} "
            f"| {types} | {len(rows) - text} | {text} |"
        )

    failed_ids = {failure["paper_id"] for failure in failures}
    skipped = [
        row
        for row in catalogue
        if str(row["paper_id"]) not in manifest and str(row["paper_id"]) not in failed_ids
    ]
    other = [row for row in manifest.values() if row["exam_type"] == "Other"]
    by_hash: dict[str, list[str]] = defaultdict(list)
    for row in manifest.values():
        by_hash[row["sha256"]].append(str(row["paper_id"]))
    duplicates = [ids for ids in by_hash.values() if len(ids) > 1]

    sections = [
        ("Failed downloads", [f"{f['paper_id']}: {f['title']} ({f['reason']})" for f in failures]),
        ("Not downloaded by the filter", [f"{r['paper_id']}: {r['title']}" for r in skipped]),
        ("Papers typed Other", [f"{r['paper_id']}: {r['title']}" for r in other]),
        ("Identical files under different ids", [", ".join(ids) for ids in duplicates]),
    ]
    for heading, items in sections:
        lines += ["", f"## {heading}", ""]
        lines += [f"- {item}" for item in items] or ["None."]
    return "\n".join(lines) + "\n"


def capture_auth_header(
    context: BrowserContext, portal: dict, headless: bool
) -> dict[str, str] | None:
    """Load the site and return the auth header it sends, if the backend still accepts it."""
    backend_host = urlsplit(portal["backend"]).hostname
    captured: dict[str, str] = {}

    def remember(request: Request) -> None:
        if urlsplit(request.url).hostname == backend_host:
            value = request.all_headers().get("authorization")
            if value:
                captured["authorization"] = value

    context.on("request", remember)
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(f"{portal['url']}/home")
    if not headless:
        print('Your session has expired. Please click "Login" and sign in.', flush=True)
        wait_for_sign_in(page, portal["login_timeout_seconds"])
    page.wait_for_timeout(SESSION_WAIT_MS)
    context.remove_listener("request", remember)
    if not captured:
        return None
    check = context.request.get(f"{portal['backend']}/me", headers=captured)
    return captured if check.ok else None


def open_session(
    playwright: Playwright, portal: dict
) -> tuple[BrowserContext, dict[str, str]]:
    """Reuse the saved session without a window, or open a window for the owner to sign in."""
    profile = str(Path(portal["profile_dir"]).resolve())
    for headless in (True, False):
        context = playwright.chromium.launch_persistent_context(profile, headless=headless)
        headers = capture_auth_header(context, portal, headless)
        if headers:
            return context, headers
        context.close()
    raise SessionExpired("No valid session after signing in")


def main() -> None:
    """Write the catalogue, download the papers, write the manifest and summary."""
    cfg = load_config()
    portal = cfg["portal"]
    collection = cfg["collection"]
    paths = cfg["paths"]
    raw_dir = Path(paths["raw"])
    manifest_path = Path(paths["manifest"])
    failures: list[dict] = []
    status = 0

    with sync_playwright() as playwright:
        context, headers = open_session(playwright, portal)
        print("Session ready.", flush=True)
        items = list_papers(context.request, portal["backend"], headers, portal)
        catalogue = [catalogue_row(item) for item in items]
        write_csv(catalogue, Path(paths["catalogue"]), CATALOGUE_COLUMNS)
        print(f"Catalogue written: {len(catalogue)} papers.", flush=True)

        eligible = [
            row
            for row in catalogue
            if is_exam_paper(row, collection["skip_exam_types"], collection["skip_title_words"])
        ]
        limit = None if collection["scope"] == "all" else collection["min_subjects"]
        courses = choose_subjects(pd.DataFrame(eligible), limit)
        if len(courses) < collection["min_subjects"]:
            context.close()
            sys.exit(f"STOPPED: only {len(courses)} subjects have exam papers.")
        order = {course: position for position, course in enumerate(courses)}
        wanted = sorted(
            (row for row in eligible if row["course"] in order),
            key=lambda row: (order[row["course"]], row["year"], row["paper_id"]),
        )
        print(f"Eligible: {len(wanted)} papers in {len(courses)} subjects.", flush=True)

        try:
            download_all(
                context.request,
                wanted,
                headers,
                portal,
                raw_dir,
                manifest_path,
                cfg["extraction"]["min_chars_per_page"],
                failures,
            )
        except SessionExpired:
            status = 2
            print("STOPPED: the session expired. Run again to sign in and resume.", flush=True)
        except DownloadFailed:
            status = 3
            print("STOPPED: the first download failed, so nothing else was tried.", flush=True)
        context.close()

    manifest = read_manifest(manifest_path)
    summary_path = Path(paths["summary"])
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary_markdown(manifest, catalogue, failures), encoding="utf-8")
    mismatched = unlisted_files(raw_dir, manifest)
    subjects = len({row["course"] for row in manifest.values()})
    print(
        f"COLLECTION DONE: {len(manifest)} papers, {subjects} subjects, {len(failures)} failed, "
        f"{len(mismatched)} files not matching the manifest. Summary: {summary_path}",
        flush=True,
    )
    sys.exit(status)


if __name__ == "__main__":
    main()
