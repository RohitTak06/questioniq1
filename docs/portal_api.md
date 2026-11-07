# JKLU Paper Portal API

Observed on 7 Nov 2026 with `scripts/discover_api.py` (log: `data/api_log.jsonl`,
gitignored) plus a few read-only follow-up calls. Only what was actually seen is
stated as fact; everything else is under "Not confirmed".

- Frontend: `https://exam-quiz-portal-lib-jklu.vercel.app`
- Backend: `https://learn-backend-jklu.vercel.app`

## Calls

| Purpose | Call | Auth header seen | Response |
| --- | --- | --- | --- |
| List papers | `GET /papers/public/all?page=N&limit=20` | Not needed (200 without it) | JSON envelope, below; fails past position 142, see "Speed and limits" |
| Filter by type | add `&paper_type=endterm\|midterm\|other\|assignment` | Not needed | Same envelope |
| Filter by year | add `&year=2025` | Sent by the site | Same envelope |
| Filter values | `GET /papers/metadata` | Not needed | `years`, `types`, `courses` (`id`, `code`, `name`) |
| Course list | `GET /courses` | Not needed | `id`, `code`, `name`, `description`, timestamps |
| Get a PDF | `GET /papers/{id}/download` | Sent by the site | `application/pdf`, with `content-disposition` |
| Sign in | `POST /login` | No | Handled by the owner; response not logged |
| Current user | `GET /me` | Yes | Response not logged |
| Keep-alive | `GET /wake` | No | Status message |

Clicking "View" on a paper calls `/papers/{id}/download` (seen twice per view).

## List response

```json
{"items": ["..."], "total": 150, "page": 1, "size": 20, "pages": 8}
```

Fields of each item:

| Field | Type | Use |
| --- | --- | --- |
| `id` | int | `paper_id` |
| `course_code`, `course_name`, `course_id` | str, str, int | Course |
| `title`, `description` | str | Title; `description` can hold programme, year and semester |
| `paper_type` | str | Exam type |
| `year` | int | Year |
| `semester` | str | Free text: both `"1"` and `"2nd Sem"` were seen |
| `status` | str | `approved` on the items seen |
| `file_name`, `file_path` | str | Original file names |
| `uploaded_at` | str | Upload time |
| `quiz_set`, `department` | null on the items seen | Unused |
| `uploaded_by`, `uploader_name`, `uploader_email` | int, str, str or null | Personal data: never stored |
| `public_link_id`, `public_url` | str | Not used: we download with the signed-in session |

## Sign-in and session

- The token is in the browser's `localStorage` under the key `token`. There are no cookies.
- The site sends it in an `authorization` header. Header values were not logged, so
  the scheme is not recorded here.
- `.auth/` keeps the session between runs: a new browser opened with that profile
  shows "Total available" without signing in again.
- Playwright's `context.request` does not add this header by itself, because the
  token is not a cookie.

## Portal contents on 7 Nov 2026

- 150 papers: 135 endterm, 4 midterm, 10 other, 1 assignment
- 127 courses in `/papers/metadata`
- Years listed: 2025, 2024, 2023, 2022, 2020, 2019 (no 2021)

## Speed and limits

- A list page of 20 takes about 9 s, and a page of 5 about 3.5 s.
- The plain list answers HTTP 500 for any position past 142, including positions
  beyond the end of the list, at any speed. So `page=8&limit=20` always fails and the
  last 8 papers can't be reached that way.
- Year filters reach everything: listing each year in `/papers/metadata` gave all 150
  papers. Ids 21 to 27 appear only this way.
- Occasional connection resets after about 5 s also happen, and pass on retry.
- The cause of both is not known.

## Not confirmed

- Whether `/papers/{id}/download` works without the auth header. It was only seen with it.
- `/papers/{id}/preview` and `/papers` were not called during this session.
- The parameter for filtering by course. It is not needed, since we list every page.
- The largest `limit` the backend allows. We use the site's own value, 20.
- How long a session lasts before it expires.
