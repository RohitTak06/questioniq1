"""Record how the JKLU Paper Portal talks to its backend (Phase 0b, step 1).

Opens a visible browser with its own profile in .auth/. The owner signs in by
hand, then the script clicks one page change, one year filter and one "View"
while logging each backend call to data/api_log.jsonl. It never clicks
"Download", never touches the login form and never logs request bodies or
header values.

Run from the project root: python scripts/discover_api.py [--channel chrome]
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Response, sync_playwright

from questioniq.config import load_config
from questioniq.scrape import looks_signed_in, wait_for_sign_in

MASK = "[REDACTED]"
ASK_WAIT_SECONDS = 60
SETTLE_SECONDS = 3.0
CLICK_TIMEOUT_MS = 5000

AUTH_PATH = re.compile(
    r"login|logout|signin|signup|auth|token|session|callback|password"
    r"|/me(/|$)|/users?(/|$)|/profile|/account",
    re.I,
)
SENSITIVE_PART = re.compile(
    r"token|secret|passw|pwd|email|phone|mobile|session|auth|cookie|jwt"
    r"|signature|credential|api_?key",
    re.I,
)
SENSITIVE_EXACT = {"code", "key", "sig", "state"}
JSON_FIELD = re.compile(r'"((?:[^"\\]|\\.)+)"(\s*:\s*)("(?:[^"\\]|\\.)*"|-?[\w.]+)')
JWT = re.compile(r"eyJ[\w-]{10,}(?:\.[\w-]+)*")
BEARER = re.compile(r"bearer\s+[\w.~+/=-]+", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
LONG_OPAQUE = re.compile(r"[A-Za-z0-9_-]{40,}")
YEAR = re.compile(r"^20\d\d$")
NEXT_PAGE = re.compile(r"^(next( page)?|[›»>]|2)$", re.I)
VIEW = re.compile(r"^view( paper)?$", re.I)


def is_backend_request(url: str, backend: str) -> bool:
    """Return True if a URL is on the same host as the backend."""
    return urlsplit(url).hostname == urlsplit(backend).hostname


def is_auth_url(url: str) -> bool:
    """Return True for login or account URLs, whose responses are never logged."""
    return bool(AUTH_PATH.search(urlsplit(url).path))


def is_sensitive_name(name: str) -> bool:
    """Return True if a field or parameter name could hold a secret or personal data."""
    return bool(SENSITIVE_PART.search(name)) or name.lower() in SENSITIVE_EXACT


def mask_opaque(text: str) -> str:
    """Mask token-like strings, Bearer values and email addresses in free text."""
    for pattern in (JWT, BEARER, EMAIL, LONG_OPAQUE):
        text = pattern.sub(MASK, text)
    return text


def redact_url(url: str) -> str:
    """Return the URL with sensitive parameters masked and the fragment removed."""
    parts = urlsplit(url)
    query = [
        (name, MASK if is_sensitive_name(name) else mask_opaque(value))
        for name, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, mask_opaque(parts.path), urlencode(query, safe="[]"), "")
    )


def redact_json_snippet(text: str, limit: int = 500) -> str:
    """Mask sensitive values in JSON text, then cut it to limit characters."""

    def mask_field(match: re.Match) -> str:
        name, separator, value = match.groups()
        return f'"{name}"{separator}"{MASK}"' if is_sensitive_name(name) else match.group(0)

    return mask_opaque(JSON_FIELD.sub(mask_field, text))[:limit]


def log_entry(
    method: str,
    url: str,
    status: int,
    request_headers: list[str],
    response_headers: list[str],
    content_type: str,
    body: str | None,
) -> dict:
    """Build one safe log record. Headers are names only; login responses have no body."""
    safe_url = redact_url(url)
    keep_body = body is not None and not is_auth_url(url)
    return {
        "method": method,
        "url": safe_url,
        "query": dict(parse_qsl(urlsplit(safe_url).query, keep_blank_values=True)),
        "status": status,
        "request_header_names": sorted(request_headers),
        "response_header_names": sorted(response_headers),
        "content_type": content_type,
        "body_snippet": redact_json_snippet(body) if keep_body else None,
    }


def record(response: Response, backend: str, log_path: Path) -> None:
    """Append one backend response to the log. Request bodies are never read."""
    if not is_backend_request(response.url, backend):
        return
    try:
        request_headers = list(response.request.all_headers())
        response_headers = response.all_headers()
        content_type = response_headers.get("content-type", "")
        wants_body = "json" in content_type and not is_auth_url(response.url)
        body = response.text() if wants_body else None
    except PlaywrightError:
        request_headers, response_headers, content_type, body = [], {}, "", None
    entry = log_entry(
        response.request.method,
        response.url,
        response.status,
        request_headers,
        list(response_headers),
        content_type,
        body,
    )
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _next_page(page: Page) -> None:
    """Click the control that moves to the next page of results."""
    button = page.get_by_role("button", name=NEXT_PAGE)
    button.or_(page.get_by_role("link", name=NEXT_PAGE)).first.click(timeout=CLICK_TIMEOUT_MS)


def _choose_year(page: Page) -> None:
    """Choose one year in the filter, whether a plain select or a custom dropdown."""
    for select in page.locator("select").all():
        options = [text.strip() for text in select.locator("option").all_inner_texts()]
        years = [option for option in options if YEAR.match(option)]
        if years:
            select.select_option(label=years[0])
            return
    page.get_by_role("combobox", name=re.compile("year", re.I)).first.click(
        timeout=CLICK_TIMEOUT_MS
    )
    page.get_by_role("option", name=YEAR).first.click(timeout=CLICK_TIMEOUT_MS)


def _view_paper(page: Page) -> None:
    """Click "View" on the first paper listed."""
    button = page.get_by_role("button", name=VIEW)
    button.or_(page.get_by_role("link", name=VIEW)).first.click(timeout=CLICK_TIMEOUT_MS)


def click_through(page: Page, min_delay_seconds: float) -> None:
    """Do one page change, one year filter and one View, asking the owner if a control is hidden."""
    steps = [
        ("the next page of results", _next_page),
        ("a year in the year filter", _choose_year),
        ('"View" on one paper', _view_paper),
    ]
    for description, action in steps:
        try:
            action(page)
            print(f"Clicked {description}.", flush=True)
        except PlaywrightError:
            print(
                f"Could not find {description}. Please click it yourself in the browser "
                f"within {ASK_WAIT_SECONDS} s. Do not click Download.",
                flush=True,
            )
            page.wait_for_timeout(ASK_WAIT_SECONDS * 1000)
        page.wait_for_timeout(max(min_delay_seconds, SETTLE_SECONDS) * 1000)


def main() -> None:
    """Open the portal, wait for the owner's sign-in, click through and write the log."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", help='Browser to use instead of Chromium, e.g. "chrome"')
    args = parser.parse_args()

    cfg = load_config()
    portal = cfg["portal"]
    log_path = Path(cfg["paths"]["api_log"])
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(Path(portal["profile_dir"]).resolve()),
            headless=False,
            channel=args.channel,
            no_viewport=True,
        )
        context.on("response", lambda response: record(response, portal["backend"], log_path))
        hosts: Counter = Counter()
        context.on("request", lambda request: hosts.update([urlsplit(request.url).hostname]))
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(portal["url"])

        print(
            'Please click "Get Started", then "Login", and sign in. I continue once a page '
            'shows "Total available". If you reach a page without it, open the papers list.',
            flush=True,
        )
        wait_for_sign_in(page, portal["login_timeout_seconds"])
        print("Sign-in seen. Clicking through the portal.", flush=True)
        page.wait_for_timeout(SETTLE_SECONDS * 1000)
        click_through(page, portal["min_delay_seconds"])
        context.close()

    print(f"Hosts contacted (names only): {dict(hosts)}", flush=True)
    with open(log_path, encoding="utf-8") as f:
        print(f"DISCOVERY DONE: {sum(1 for _ in f)} calls in {log_path}", flush=True)


if __name__ == "__main__":
    main()
