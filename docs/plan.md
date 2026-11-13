# QuestionIQ build plan

Source of truth for what to build and in what order. The synopsis
(`docs/synopsis.md`) says *what* the system is; this file says *how* we build it.
Project rules are in `CLAUDE.md`.

## Scope for v1

- At least 20 JKLU subjects, collected automatically by `scrape.py` (Phase 0b).
  Prefer subjects with papers in 2 or more years, then the most papers
- Scanned papers are the norm, so OCR (Tesseract) is in scope. pdfplumber is
  used first and OCR kicks in when a page has no usable text layer
- About 300 questions labelled by the owner for the difficulty model, with a
  150-question relabel round at least 48 hours later to measure agreement
- Dashboard pages: Upload, Question Bank, Topics, Trends, Model Report, plus a
  per-question Explain drawer
- Out of scope: semantic search, predicting future topics, user accounts

## Deliberate deviations from the synopsis

1. LDA runs on raw counts (`CountVectorizer`), not TF-IDF. LDA models word
   counts. NMF runs on TF-IDF. Both are compared with C_v coherence.
2. "Question Generation" in the synopsis flow means the topic-wise question
   bank. We do not generate new questions.
3. The Logistic Regression segmentation fallback is dropped (decided 2026-11-13).
   Its 10 reserved papers became the fresh test set for the rule-based segmenter,
   after the first check was used to fix the rules. See `docs/decisions.md`.
4. OCR moves from "future work" into v1, because most portal papers are scans.
5. Topic models are trained on the pooled question set (all subjects, or one
   model per department such as AS / CS / EE when a group has 150+ questions),
   not one model per subject. Most subjects have only 1 to 3 papers, too few
   questions for a stable per-subject LDA. Results are still shown per subject.

## Data source

PYQs come from the JKLU Paper Portal, https://exam-quiz-portal-lib-jklu.vercel.app
(login required). **Claude Code collects them with `scrape.py`; the owner only
signs in once.** Course, year and exam type (Midterm / Endterm / Other /
Assignment) come from the portal's metadata, so they are never parsed out of
the PDF.

What was seen on the portal (7 Nov 2026):

- React frontend; data from a separate REST backend, `https://learn-backend-jklu.vercel.app`
- Routes used by the frontend include `/courses`, `/papers`, `/papers/metadata`,
  `/papers/public`, `/papers/{id}/preview` and `/papers/{id}/download`.
  Exact parameters and auth header are unknown: discover them, don't guess
- About 150 papers in total across about 120 course codes; years 2019 to 2025
- Cards are titled like `AS1202 - Advanced Statistics - Endterm - Sem 5 - 2024`
- The UI lists 20 papers per page and has a year filter and a course dropdown
  (codes only, no names)
- Example paper: AS1202 Advanced Statistics, End Term Dec 2024. It's a 4-page
  scan with a diagonal "JK Lakshmipat University" watermark and a logo behind
  the text. Questions are in a bordered table with marks and CO columns on the
  right, and pages 3 to 4 are statistical tables (z-table), not questions

Output of collection:

- PDFs at `data/raw/<course>/<year>_<exam>_<paper_id>.pdf`
- `data/manifest.csv` with columns:
  `course, course_name, title, year, exam_type, semester, paper_id, path, sha256, n_pages, has_text_layer, downloaded_at`

## Schedule: 4 days, solo

| Day | Phases | Owner by hand |
| --- | --- | --- |
| Sat 7 Nov | 0, 0b, start OCR on everything | sign in for scraper, install Tesseract |
| Sun 8 Nov | 1, 2, 3, annotation page (4) | 3 OCR reference pages, hand-count 10 papers, name topics, rubric, labelling round 1 (~300) |
| Mon 9 Nov | 5, 6, 7 | review results |
| Tue 10 Nov | 8, 9 | labelling round 2 (150, at least 48 h after round 1), Kappa, report |

Work fast: once a phase plan is approved, implement the whole phase in one go,
run tests, and fix failures without asking. Ask only when a decision changes
results (k, features, thresholds). Run long jobs (downloads, OCR) in the
background and keep building the next phase meanwhile. If behind schedule, cut
in this order: department-level topic models, the Upload page, the LR
segmentation fallback. Never cut the evaluation numbers.

## Phases

Each phase ends with passing tests and the "done when" check.

### Phase 0: Scaffold
Repo structure from `CLAUDE.md`, `pyproject.toml` / `requirements.txt`,
`config.yaml`, `.gitignore` (.env, data/raw/, models/, *.db), pytest set up,
empty modules with docstrings and function signatures, `docs/decisions.md`,
the Playwright browser install (`playwright install chromium`), and a check
that Tesseract is installed (on Windows, the owner installs it once and its
path goes in `config.yaml` as `tesseract_cmd`). Add `.auth/` and `data/ocr/`
to `.gitignore`.
**Done when:** `pytest -q` passes and `python -c "import pytesseract; print(pytesseract.get_tesseract_version())"` prints a version.

### Phase 0b: Collect the papers (Claude Code does this)
1. **Discover the API.** Write `scripts/discover_api.py`. It uses Playwright
   with a persistent profile in `.auth/` and opens a headed browser at the
   portal. It waits until the owner has signed in, which you detect by the
   page showing "Dashboard" or a non-zero "Total available". Then it clicks
   through one year filter, one page change and one "View". It logs every
   request to the backend host (method, URL, query parameters, response
   status, the first 500 characters of JSON responses, and header *names*
   only) to `data/api_log.jsonl`. Redact token values. Read the log and write
   `docs/portal_api.md` describing the list, metadata and download calls.
2. **Write `scrape.py`.** It reuses the saved session (Playwright
   `context.request`, or requests with the cookie/token read from the profile
   at runtime, never written to disk in plain text). It then:
   - lists every paper with its metadata
   - writes `data/catalogue.csv` (all papers, including ones not downloaded)
   - picks subjects by the rule in Scope
   - downloads at least 20 subjects' papers, one at a time, ≥1 s apart,
     retrying 3 times with backoff and skipping files whose sha256 already
     matches
   - writes `data/manifest.csv`
   Skip assignments and coding-hour items unless they contain exam-style
   questions. If the API can't be used, fall back to driving the UI: year
   filter → pages → "View" → "Download".
3. **Report.** Print and save `reports/collection_summary.md` with one table:
   subject, course code, number of papers, years, exam types, scanned vs text.
**Done when:** ≥20 subjects are in `data/raw/`, every file is in the manifest,
and the summary table exists. If the portal has fewer than 20 subjects with
exam papers, stop and say so instead of padding.

### Phase 1: Extraction (with OCR) and segmentation
`extract_text(pdf_path)` tries pdfplumber first. If a page has fewer than
~50 usable characters, it renders the page at 300 dpi with PyMuPDF and runs
Tesseract (`--psm 6`, English). Before OCR it reduces the watermark with
grayscale, contrast stretch and adaptive threshold (OpenCV), and drops the
light diagonal text. It detects and skips pages that are statistical tables
(mostly digits in a grid). Output is text per page plus `has_text_layer` and
`ocr_used`, cached in `data/ocr/<paper_id>.json` so OCR runs only once.
Measure OCR quality: hand-type 3 reference pages into `data/ocr_gold/` (the
owner does this) and compute character error rate with a small Levenshtein
function. The marks/CO column on the right can be read by cropping the
table's last column, or with regex on the line ends.
`segment(text)` uses regex rules for `Q1`, `Q.1`, `Q9`, `1.`,
`1(a)`, `(i)`, `a)` and pulls marks from `[5]`, `(5 marks)`, `5M` or a trailing
marks column. It returns `Question(qno, sub_part, text, marks, co)`.
Instructions ("Attempt any five", "Use of calculators is allowed") and headers
are not questions. Question numbers can skip (one 2024 paper goes Q7 → Q9), so
never assume they are consecutive. Then add a Logistic Regression "does a new question start on
this line?" fallback trained on hand-labelled lines (features: numbering
pattern, line length, marks bracket at the end, previous line blank).
**Done when:** at least 90% of questions are split correctly on 10 hand-counted
papers. Print per-paper counts so the owner can check them.

### Phase 2: Preprocessing
Lowercase, tokenize, NLTK stopwords plus exam stopwords (explain, write,
briefly, marks, following, question, short note, ...), WordNet lemmatizer, drop
tokens under 3 characters and pure numbers. Keep the raw text for display.
**Done when:** 20 sampled cleaned questions still read as their topic.

### Phase 3: Topic modelling
Train on the pooled question set (see deviation 5). If a department group has
150+ questions, also train one model for that group and compare. Sweep k = 4..15 for LDA (counts, uni+bigrams, min_df=2)
and NMF (TF-IDF). C_v coherence with gensim on the top 10 words. Plot
coherence vs k for both, pick k by best C_v, save top-10 keywords per topic to
CSV, and store each question's dominant topic and full distribution. The owner
names the topics from their keywords (stored in `data/topic_names.csv`). Also
report how strongly topics line up with subjects (a topic × subject table),
since pooled topics may partly rediscover the subjects.
**Done when:** coherence plot, LDA-vs-NMF table, named topics, topic × subject table.

### Phase 4: Annotation tool (the owner labels, code never does)
This is a solo project, so agreement is measured between two labelling rounds
by the owner (intra-annotator, test-retest), optionally plus one helper.
Flask page `/annotate?annotator=<round1|round2|helper>`: one question at a
time with marks and course, Easy / Medium / Hard / Skip, saves to
`data/labels/difficulty_<annotator>.csv`. It never shows labels from another
round. `round2` serves a fixed random sample of 150 round-1 questions in
shuffled order, and refuses to open until 48 hours after the last round-1 label.
Plus `scripts/kappa.py` using `sklearn.metrics.cohen_kappa_score` (round1 vs
round2, and round1 vs helper if present) and a disagreement list for the owner
to settle. The owner writes the rubric in `docs/rubric.md`.
**Done when:** Kappa >= 0.6.

### Phase 5: Difficulty model
Features: highest Bloom level of the action verbs (`bloom_verbs.yaml`), word
count, marks, number of sub-parts, has numbers, has formula symbols
(=, ^, integral, sigma, root), count of technical TF-IDF terms, dominant topic. RF
(class_weight="balanced") vs LR (scaled), stratified 5-fold CV, small grid
search, majority-class baseline. Report per-class P/R/F1, macro-F1, confusion
matrices to `reports/metrics/`. Save the best model with joblib.
**Done when:** a results table with both models and the baseline.

### Phase 6: Explainability
RF: SHAP TreeExplainer, global summary plot and top-5 signed features per
question. LR: per-class coefficients mapped to feature names. Topics: the
question's topic distribution and the topic keywords that appear in it. All
returned as JSON for the dashboard.
**Done when:** any question can show "Hard because: Bloom level 6, 10 marks,
contains formula" backed by SHAP values.

### Phase 7: Database, trends, pipeline
SQLAlchemy models Paper, Question, Topic, Prediction (SQLite). `trends.py`
covers topic share by year and exam type, difficulty mix by year, and concepts
that recur across 3 or more years. `pipeline.py` runs extract -> segment ->
preprocess -> topics -> features -> predict -> explain -> store for the whole
manifest, idempotently.
**Done when:** one command rebuilds the database from `data/raw/`.

### Phase 8: Dashboard
Flask + Jinja + Chart.js (CDN), no React. Pages: Upload (PDF -> inference
with saved models), Question Bank (filter by course/topic/difficulty/year/exam,
keyword search), Topics, Trends (stacked bar of topic share per year, line of
difficulty mix), Model Report (metrics, confusion matrices, LDA vs NMF), and an
Explain drawer on every question.
**Done when:** a new paper can be uploaded and one prediction explained in
under 2 minutes.

### Phase 9: Figures and README
All report figures regenerate from `notebooks/` into `reports/figures/`. Add
`docs/report_outline.md` drafted from `docs/decisions.md` and saved metrics, and
a README with setup and a 5-step demo. The owner writes the report prose.

## Evaluation targets

| Stage | Metric | Target |
| --- | --- | --- |
| Collection | Subjects downloaded, manifest complete | >= 20 subjects |
| OCR | Character error rate on 3 hand-typed pages | <= 10% |
| Segmentation | % questions split correctly, 10 hand-counted papers | >= 90% |
| Topics | C_v, LDA vs NMF, k = 4..15 | Best k by C_v, both reported |
| Annotation | Cohen's Kappa, ~400 questions | >= 0.6 |
| Difficulty | Macro-F1, per-class P/R/F1, confusion matrix, 5-fold CV | Beats majority baseline |
| Explanations | Top SHAP features match rubric, 20 samples | >= 15 of 20 |
| System | Time per uploaded paper | < 10 s |
