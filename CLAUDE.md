# QuestionIQ

AI-based exam pattern analysis for JKLU previous-year question papers (PYQs).
Solo project: one student builds it alone ("the owner"). Guide: Dr. Devisha Tiwari.
The synopsis lists a three-person team, but there are no other members: never
plan work for teammates or assume someone else can review, label or test.

Pipeline: PDF -> text extraction -> question segmentation -> preprocessing ->
topic modelling (LDA vs NMF) -> difficulty prediction (Random Forest vs Logistic
Regression) -> explanations (SHAP, LR coefficients, topic keywords) -> year-wise
trends -> Flask + Chart.js dashboard.

Key docs, read them before planning any phase:
- `docs/synopsis.md`: the approved project synopsis (what we promised)
- `docs/plan.md`: scope, deviations from the synopsis, phases 0-9 with
  "done when" checks, evaluation targets
- `docs/decisions.md`: log of every modelling choice (append-only)

We work one phase at a time, in the order of `docs/plan.md`. Don't start
the next phase until the current one's "done when" check passes.

## Hard rules

- NO LLM or hosted AI APIs anywhere in `src/` or `app/` (no openai, anthropic,
  google-generativeai, transformers pipelines, langchain, etc.). The project's
  core claim is a self-trained classical NLP/ML system.
- Never generate, guess or auto-fill difficulty labels or topic names. Labels
  in `data/labels/` are written only by the owner (or a helper the owner names).
- Allowed libraries: pdfplumber, pymupdf, pytesseract, opencv-python-headless,
  pillow, nltk, scikit-learn, gensim, shap, numpy, pandas, matplotlib,
  sqlalchemy, flask, joblib, pyyaml, requests, pytest, playwright (only for
  `scrape.py`). Tesseract OCR is installed separately on the machine. Ask
  before adding anything else.
- Every random process uses `random_state=42`.
- Never commit `.env`, auth tokens, the browser profile in `.auth/`, or
  anything under `data/raw/`.

## Data collection rules (you collect the papers, not the owner)

- You write and run `scrape.py` to download PYQs from the JKLU Paper Portal
  (https://exam-quiz-portal-lib-jklu.vercel.app). Target: at least 20 subjects.
- The portal needs a login. Never type, store or ask for the password. The
  script opens a visible browser window and waits; the owner signs in by hand
  once; the script reuses that saved session from `.auth/`.
- Be polite to the portal: one request at a time, at least 1 s apart, skip
  anything already downloaded, no parallel downloads.
- Most papers are scanned images with a university watermark, so text comes
  from OCR (Tesseract), not only from pdfplumber.

## Conventions

- Python 3.11, code in `src/questioniq/`, Flask app in `app/`, tests in `tests/`.
- Small pure functions with type hints and docstrings, e.g.
  `segment(text: str) -> list[Question]`.
- Every new module gets pytest tests. Run `pytest -q` after each change and
  show the output.
- Config (courses, k range, paths) lives in `config.yaml`, not in code.
- Models are saved with joblib to `models/`; metrics as JSON to `reports/metrics/`;
  figures to `reports/figures/`.
- When we make a modelling choice (k, hyperparameters, thresholds, stopwords),
  append one dated line to `docs/decisions.md` with the reason.
- Frontend: Jinja templates + Chart.js from a CDN. No React, no JS build step.

## Layout

```
.auth/                       # saved portal login session (gitignored)
data/raw/<course>/<year>_<exam>_<id>.pdf   # filled by scrape.py
data/catalogue.csv           # every paper on the portal
data/manifest.csv            # every paper downloaded
data/ocr/                    # cached OCR text per paper
data/ocr_gold/               # hand-typed pages for OCR accuracy
data/labels/difficulty_<annotator>.csv
src/questioniq/  scrape extract segment preprocess topics features
                 difficulty explain trends db pipeline
app/             routes.py templates/ static/
notebooks/       EDA, k-sweep, model comparison
tests/
docs/decisions.md
```

## Evaluation targets

- Collection: >= 20 subjects downloaded, every paper listed in the manifest
- OCR: character error rate (CER) <= 10% on 3 hand-typed reference pages
- Segmentation: >= 90% questions split correctly on 10 hand-counted papers
- Topics: C_v coherence for LDA and NMF, k = 4..15, choose k by best C_v
- Annotation: Cohen's Kappa >= 0.6 between the owner's two labelling rounds
- Difficulty: macro-F1 + per-class P/R/F1 + confusion matrix, stratified
  5-fold CV, compared with a majority-class baseline

## How to work with me

- Propose a plan before writing code for any new phase.
- Explain code in plain language when asked; I must be able to defend every
  line in a viva.
- If a PDF breaks parsing, show the exact page text that failed rather than
  guessing.
- `data/raw/` is filled by `scrape.py`. Never invent, retype from memory or
  synthesise exam questions to pad the dataset.
