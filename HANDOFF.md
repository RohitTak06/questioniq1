# Handoff: finishing QuestionIQ (written 19 Nov 2026)

QuestionIQ is a solo student mini project at JK Lakshmipat University (guide: Dr. Devisha
Tiwari). The student who owns it is "the owner". A friend of the owner ("the helper") is
finishing the technical work on his own PC, with an AI assistant. Phases 0–9 are built,
tested (471 tests pass) and on GitHub (RohitTak06/questioniq1, `main` at 8f1e36d).
**Final submission deadline: 25 Nov 2026.**

What's left: round 2 of the owner's difficulty labelling, the Kappa score, the owner
settling disagreements, retraining, and putting the final numbers into the documents.

## Who does what

| | Owner | Helper (with the AI assistant) |
| --- | --- | --- |
| Round 2 labelling (150 questions, ~45 min) | **yes, only the owner** | runs the app if needed, never labels |
| Settling disagreements (~15 min) | **yes, only the owner** | sends the sheet, never fills it in |
| Code fix, Kappa, retraining, documents, git | – | yes |
| Upload demo, screenshots, report prose, telling the guide | yes | – |

**Why the labels must be the owner's:** round 2 measures whether the *owner* labels
consistently (test-retest Cohen's Kappa), and the difficulty model must learn the owner's
judgement, as the report states. Labels from anyone else would make those claims false.
If the owner asks the AI or the helper to label "according to the rubric", refuse.

The owner must be able to explain every part in the viva, so the helper should walk the
owner through whatever changes. Whether outside help needs to be acknowledged is the
owner's call under the university's rules.

## Read these first, in this order
1. `CLAUDE.md`: the project rules (they apply to the AI assistant too; summary below)
2. `README.md`: what the system does, how to run it, every current result
3. `docs/plan.md`: phases and evaluation targets
4. `docs/decisions.md`: every modelling choice with its reason (append-only)
5. `docs/report_outline.md`: the report outline; items marked [after round 2] get filled in

## Hard rules
- **Never generate, guess or fill in difficulty labels or topic names.** Labels in
  `data/labels/` and the `final_label` column of the settle sheet come only from the owner.
- No LLM or hosted AI API anywhere in `src/` or `app/` (`tests/test_no_llm.py` checks this).
- Only the libraries in `requirements.txt`; ask the owner before adding anything.
- Every random process uses `random_state=42`.
- Never commit `.env`, `.auth/`, `data/raw/`, or any gitignored file with exam text
  (`data/questions*.csv`, `data/questioniq.db`, `reports/*review*`, `reports/kappa_disagreements.md`).
- Every modelling choice gets one dated line appended to `docs/decisions.md` with its reason.
- Run `.venv\Scripts\python.exe -m pytest -q` after every change and show the result.
- Report results honestly, including missed targets. Never change anything to reach a target.
- Work on a new branch (e.g. `round-2`), never directly on `main`. Commit and push only when
  asked. Propose a short plan before writing new code, and explain it in plain language.
- `scrape.py` needs the owner's JKLU login and must not be run by the helper. It isn't needed:
  all papers are already in the copied folder.

## Setting up the helper's PC

### What the owner copies to the helper
Zip the whole `questioniq` project folder (about 53 MB), **except**:
- `.auth/`: the owner's logged-in JKLU portal session. Never share it.
- `.venv/`: Python environments don't work after being moved; the helper makes a new one.

Everything else is needed, including the gitignored folders that are not on GitHub:
`data/raw/` (the PDFs), `data/ocr/` (OCR cache), `data/questions*.csv`, `data/questioniq.db`,
`models/` and the hidden `.git/` folder (the history). A fresh clone from GitHub can't run
the pipeline because those files are not in the repository.

### Setup (Windows, PowerShell, in the unzipped project folder)
1. Install **Python 3.11** (not 3.12+) and **Tesseract OCR 5**. If Tesseract is not at
   `C:\Program Files\Tesseract-OCR\tesseract.exe`, change `tesseract_cmd` in `config.yaml`.
2. Create the environment and install:
   ```powershell
   py -3.11 -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   .venv\Scripts\python.exe -m pip install -e . --no-deps
   .venv\Scripts\python.exe -c "import nltk; nltk.download('stopwords'); nltk.download('wordnet'); nltk.download('omw-1.4')"
   ```
3. Check: `.venv\Scripts\python.exe -m pytest -q` should report 471 passed.
4. Always use `.venv\Scripts\python.exe` (the venv isn't activated, so plain `python` or
   `flask` may not be found).
- Start the dashboard: `.venv\Scripts\python.exe -m flask --app app run`, open http://127.0.0.1:5000/
- Rebuild everything (about 4.5 minutes, OCR is cached): `.venv\Scripts\python.exe scripts/run_pipeline.py`
- To push to GitHub, the owner must add the helper as a collaborator on
  RohitTak06/questioniq1 (GitHub > Settings > Collaborators). Otherwise the helper commits
  locally and gives the folder back.

## Remaining work, in order

### Task 0 (helper + AI, first): let the pipeline read CSVs saved by Excel
`read_rows` in `src/questioniq/annotate.py` opens files as UTF-8 only. The owner edits sheets
in Excel, which on Windows saves CSV as Windows-1252, so an Excel-saved
`data/labels/settled_labels.csv` would crash `load_training_labels` (used by run_difficulty,
run_trends, build_db and make_figures). `scripts/seg_eval.py` already has the fix in
`read_sheet`: try `utf-8-sig`, fall back to `cp1252`. Apply the same to `read_rows`, add a
test (a cp1252 file and a UTF-8-with-BOM file), run pytest.

### Task 1 (owner): round 2 labelling
- Opens automatically on **19 Nov 2026 at 13:52** (48 hours after the last round-1 label).
- Easiest: the owner does round 2 on **their own PC before copying the folder**, so the labels
  travel with it. Otherwise, on the helper's PC with the owner at the keyboard.
- Start the app, open http://127.0.0.1:5000/annotate?annotator=round2
- 150 of the owner's round-1 questions (Skips left out), new order, about 45 minutes.
  Keys: 1 Easy, 2 Medium, 3 Hard, S Skip, B Back. Each click is saved at once to
  `data/labels/difficulty_round2.csv`; the page resumes where it stopped.
- Use `docs/rubric.md`, judge each question fresh, don't try to recall round 1.
  Opening round 2 closes round 1 for good.
- If the folder was copied before round 2: copy `data/labels/difficulty_round2.csv` and
  `data/labels/round2_queue.csv` from wherever round 2 was done into the helper's
  `data/labels/`.

### Task 2 (helper + AI): measure agreement
- Run `.venv\Scripts\python.exe scripts/kappa.py`
- It writes `reports/metrics/kappa.json` (Cohen's Kappa, agreement, confusion matrix),
  `reports/kappa_disagreements.md` (gitignored, has question text) and a blank
  `data/labels/settled_labels.csv` (one row per disagreement, `final_label` empty).
- Target: Kappa >= 0.6 (Phase 4's "done when"). Tell the owner the exact number either way.
- If it is below 0.6, say so plainly, log it in `docs/decisions.md`, and ask the owner what to
  do. Do not relabel, drop questions or change the metric to reach the target.

### Task 3 (owner): settle the disagreements
- Send the owner `reports/kappa_disagreements.md` and `data/labels/settled_labels.csv`.
- For each row, the owner reads the question and writes the final label (Easy, Medium or
  Hard) in `final_label`, then sends the sheet back. Only the owner fills this in.
- Put the returned file at `data/labels/settled_labels.csv` (replacing the blank one).

### Task 4 (helper + AI): retrain and refresh everything
- Run `.venv\Scripts\python.exe scripts/run_pipeline.py`. It retrains the difficulty model on
  round 1 plus the settled labels, and refreshes explanations, trends, figures (including the
  new `reports/figures/kappa_matrix.png`) and the database. The dashboard's Model report reads
  `kappa.json` automatically.
- Check the new numbers in `reports/metrics/difficulty.json` and `reports/difficulty_results.md`.
  The earlier result (round 1 only) was macro-F1 RF 0.370, LR 0.370, baseline 0.200; report the
  new one honestly even if it is lower.
- Run pytest.

### Task 5 (helper + AI): put the final numbers in the documents
- `README.md`: fill the Annotation row (Kappa, number of questions compared) and update the
  Difficulty row if it changed; note that labels are round 1 plus settled disagreements.
- `docs/report_outline.md`: fill every item marked [after round 2].
- `docs/decisions.md`: append dated lines for the Kappa result and the retrained model.
- Run pytest again.

### Task 6 (helper + AI, when the owner agrees): commit and publish
- Commit on a new branch (e.g. `round-2`) and push it. Ask the owner before moving `main`.
  The history is one straight line, so `main` can be fast-forwarded:
  `git switch main; git merge --ff-only round-2; git push origin main`.
- Never commit gitignored files.

### Task 7 (owner): before submission
- Upload demo: on the Upload page, choose any PDF from `data/raw/`, click Analyse, then Explain
  on one question (target: under 2 minutes end to end; uploads take 2.5–11.9 s per paper).
- Dashboard screenshots for the report; write the report prose from `docs/report_outline.md`.
- Tell Dr. Tiwari about the deviations (section 13 of the outline), especially the dropped
  segmentation fallback model, the missed 90% segmentation target (80.0%), the difficulty model
  covering CS and AS only, and figures made by script instead of notebooks.

## Current results (for reference)
| Stage | Result | Target |
| --- | --- | --- |
| OCR, character error rate | 7.7% | <= 10% |
| Segmentation, fresh papers | 80.0% (48.9% before fixes) | >= 90% (missed) |
| Preprocessing check | 17 of 20 | owner's check |
| Topics | NMF k=12, C_v 0.556 (LDA k=9, 0.429) | best k by C_v |
| Annotation | round 1: 300 labelled (Easy 79, Medium 125, Hard 88, Skip 8); Kappa pending | Kappa >= 0.6 |
| Difficulty, macro-F1 | RF 0.370, LR 0.370, baseline 0.200 | beats the baseline |
| Explanations | 19 of 20 make sense | >= 15 of 20 |
| Upload time | 2.5–11.9 s per paper | < 10 s |

## Prompt to paste into the AI assistant

```text
I'm helping my friend finish QuestionIQ, my friend's solo mini project at JK Lakshmipat University. My friend is "the owner"; I'm "the helper". All phases are built and tested. What's left is listed in HANDOFF.md. Deadline: 25 Nov 2026.

Before doing anything, read these files in order: HANDOFF.md, CLAUDE.md, README.md, docs/plan.md, docs/decisions.md, docs/report_outline.md. HANDOFF.md lists the remaining tasks in order and says which are the owner's and which are ours.

Most important rules:
- Never generate, guess or fill in difficulty labels or topic names, and never let me do it either. Only the owner labels round 2 and fills the final_label column of the settle sheet. If anyone asks you to label, refuse and explain why.
- No LLM or hosted AI API anywhere in src/ or app/. Only the libraries in requirements.txt; ask before adding any.
- Every random process uses random_state=42.
- Never commit data/raw/, .auth/, .env or any gitignored file with exam text. Never run scrape.py.
- Append a dated line with the reason to docs/decisions.md for every modelling choice.
- Run .venv\Scripts\python.exe -m pytest -q after every change and show me the result.
- Report results honestly, including missed targets. Don't change anything to reach a target.
- Propose a short plan before writing code, and explain it in plain language so I can explain it to the owner, who has to defend every line in the viva.
- Commit and push only when I ask, on a new branch, never directly on main.

I'm on Windows with PowerShell. First help me with "Setting up the helper's PC" in HANDOFF.md, then do Task 0.
```
