# First message for Claude Code

Copy everything between the lines into Claude Code as your first message,
in plan mode (Shift+Tab until it says "plan mode").

---

Hi. I'm building QuestionIQ, my AI mini project at JKLU. I'm working alone: the synopsis lists three people, but there's no team, so don't plan work for anyone else. It analyses
previous-year exam papers: it extracts questions from PDFs, finds topics with
LDA (benchmarked against NMF), predicts Easy/Medium/Hard with Random Forest vs
Logistic Regression, explains every prediction (SHAP, LR coefficients, topic
keywords), and shows year-wise trends on a Flask + Chart.js dashboard.

Before doing anything, read these three files fully:

1. `CLAUDE.md`: hard rules. Most important: no LLM or hosted AI APIs anywhere
   in the product, and you never create difficulty labels or topic names.
2. `docs/synopsis.md`: the approved synopsis, i.e. what we promised our guide.
3. `docs/plan.md`: scope, three deliberate deviations from the synopsis,
   phases 0 to 9, and evaluation targets.

Then do this:

A. Summarise the project back to me in 10 bullet points or fewer, so I can
   check you understood it. Call out anything in the synopsis and plan that
   contradicts itself or that you think is risky.

B. Propose a plan for **Phase 0 only** (scaffold): folder structure, the
   `requirements.txt` with pinned versions, `config.yaml` fields, `.gitignore`,
   the module files with function signatures and docstrings (no real logic yet),
   a first pytest test, and `docs/decisions.md`. Include the Playwright
   Chromium install and how I install Tesseract OCR. I'm on Windows, so make
   the commands work in PowerShell, and tell me exactly which commands to run
   to create a virtual environment and install everything.

C. Wait for my approval before writing any files.

**Important: I am not collecting the papers. You are.** Phase 0b in
`docs/plan.md` is yours: discover the portal's API, write `scrape.py`, and
download PYQs for **at least 20 subjects** from
https://exam-quiz-portal-lib-jklu.vercel.app into `data/raw/`. The portal needs
a login. Your script opens a browser window, I sign in by hand once, and the
script reuses that session. Never ask me for my password or put it in any
file. Most papers are watermarked scans, so plan for OCR from the start.
We'll do Phase 0b straight after Phase 0.

---

## Phase 0b (collecting the papers)

New session, plan mode:

> Read CLAUDE.md and docs/plan.md. We're on Phase 0b: collect the papers. Start
> with step 1 (discover the API). Plan it, then run it. When the browser opens
> I'll sign in. After it finishes, show me docs/portal_api.md, then plan step 2
> (scrape.py) and wait for my approval before downloading anything.

When it asks, sign in in the browser window it opens. After the download,
check `reports/collection_summary.md`: at least 20 subjects, with real years
and exam types.

## After Phase 0b

For each later phase, start a fresh session (`/clear`), go into plan mode and
send:

> Read CLAUDE.md and docs/plan.md. We're on Phase N. Phases before it are done
> (see docs/decisions.md). Propose a plan for Phase N only, including the tests
> you'll write and how we'll check the "done when" criterion. Wait for my
> approval.

When it's done:

> Run the tests and show me the output. Then explain this phase's code as if
> I'm defending it in a viva: what each function does, why we chose this
> method, and what an examiner might ask.

Then commit: `git checkout -b phase-N`, commit, and merge once you understand
it.
