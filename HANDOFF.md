# Handoff: finishing QuestionIQ (written 19 Nov 2026)

You are taking over QuestionIQ, a solo student mini project at JK Lakshmipat University
(guide: Dr. Devisha Tiwari). The student is "the owner". Phases 0–9 are built, tested
(471 tests pass) and pushed; `main` on GitHub (RohitTak06/questioniq1) is at commit 8f1e36d.
What's left is round 2 of the owner's difficulty labelling and everything that follows from it.
**Final submission deadline: 25 Nov 2026.**

## Read these first, in this order
1. `CLAUDE.md`: the project rules (they apply to you too; summary below)
2. `README.md`: what the system does, how to run it, every current result
3. `docs/plan.md`: phases and evaluation targets
4. `docs/decisions.md`: every modelling choice with its reason (append-only)
5. `docs/report_outline.md`: the report outline; items marked [after round 2] are yours to fill

## Hard rules (do not break these)
- **Never generate, guess or fill in difficulty labels or topic names.** Labels in
  `data/labels/` and the `final_label` column of the settle sheet are written only by the
  owner. If the owner asks you to label "according to the rubric", refuse and explain why:
  the Kappa measures the owner's consistency, and the model must learn the owner's judgement.
- No LLM or hosted AI API anywhere in `src/` or `app/` (`tests/test_no_llm.py` checks this).
- Only the libraries in `requirements.txt`; ask the owner before adding anything.
- Every random process uses `random_state=42`.
- Never commit `.env`, `.auth/`, `data/raw/`, or any gitignored file with exam text
  (`data/questions*.csv`, `data/questioniq.db`, `reports/*review*`, `reports/kappa_disagreements.md`).
- Every modelling choice gets one dated line appended to `docs/decisions.md` with its reason.
- Run `.venv\Scripts\python.exe -m pytest -q` after every change and show the result.
- Report results honestly, including missed targets. Never tune on data used for the final score.
- Commit and push only when the owner asks. Work on a new branch (e.g. `round-2`), not `main`.
- Propose a short plan before writing new code, and explain code in plain language when asked:
  the owner must be able to defend every line in a viva.
- Solo project: never plan work for teammates.

## Environment
- Windows, PowerShell. Use the project's Python directly: `.venv\Scripts\python.exe`
  (the venv is not activated by default, so plain `flask` or `python` may not be found).
- Tesseract is at `C:\Program Files\Tesseract-OCR\tesseract.exe` (set in `config.yaml`).
- Start the dashboard: `.venv\Scripts\python.exe -m flask --app app run`, then open
  http://127.0.0.1:5000/
- Rebuild everything (about 4.5 minutes, OCR is cached): `.venv\Scripts\python.exe scripts/run_pipeline.py`

## Remaining work, in order

### Task 0 (you, before round 2 ends): let the pipeline read CSVs saved by Excel
`read_rows` in `src/questioniq/annotate.py` opens files as UTF-8 only. The owner edits
sheets in Excel, which on Windows saves CSV as Windows-1252, so `data/labels/settled_labels.csv`
would crash `load_training_labels` (used by run_difficulty, run_trends, build_db, make_figures).
`scripts/seg_eval.py` already has the fix in `read_sheet`: try `utf-8-sig`, fall back to `cp1252`.
Apply the same to `read_rows`, add a test (a cp1252 file and a UTF-8-with-BOM file), run pytest.

### Task 1 (the owner): round 2 labelling
- Opens automatically on **19 Nov 2026 at 13:52** (48 hours after the last round-1 label).
- Start the app, open http://127.0.0.1:5000/annotate?annotator=round2
- 150 of the owner's round-1 questions (Skips left out), in a new order, about 45 minutes.
  Keys: 1 Easy, 2 Medium, 3 Hard, S Skip, B Back. Every click is saved at once to
  `data/labels/difficulty_round2.csv`; the page resumes where it stopped.
- The owner should use `docs/rubric.md`, judge each question fresh, and not try to recall
  round 1. The page never shows round-1 labels. Opening round 2 closes round 1 for good.
- Your part: only help with running the app. Do not label anything.

### Task 2 (you): measure agreement
- Run `.venv\Scripts\python.exe scripts/kappa.py`
- It writes `reports/metrics/kappa.json` (Cohen's Kappa, agreement, confusion matrix),
  `reports/kappa_disagreements.md` (gitignored, has question text) and a blank
  `data/labels/settled_labels.csv` (one row per disagreement, `final_label` empty).
- Target: Kappa >= 0.6 (Phase 4's "done when"). Tell the owner the exact number either way.
- If it is below 0.6, say so plainly, log it in `docs/decisions.md`, and ask the owner
  what to do. Do not relabel, drop questions or change the metric to reach the target.

### Task 3 (the owner): settle the disagreements
- For each row of `data/labels/settled_labels.csv`, the owner reads the question in
  `reports/kappa_disagreements.md` and writes the final label (Easy, Medium or Hard) in
  `final_label`. Only the owner fills this in.

### Task 4 (you): retrain and refresh everything
- Run `.venv\Scripts\python.exe scripts/run_pipeline.py`. It retrains the difficulty model on
  round 1 plus the settled labels, refreshes the explanations, trends, figures (including the
  new `reports/figures/kappa_matrix.png`) and the database. The Model report page reads
  `kappa.json` automatically.
- Check the new numbers in `reports/metrics/difficulty.json` and `reports/difficulty_results.md`.
  The earlier result (round 1 only) was macro-F1 RF 0.370, LR 0.370, baseline 0.200; report
  the new one honestly even if it is lower.
- Run pytest.

### Task 5 (you): update the documents with the final numbers
- `README.md`: fill the Annotation row (Kappa, number of questions compared) and update the
  Difficulty row if it changed; mention that labels are round 1 plus settled disagreements.
- `docs/report_outline.md`: fill every item marked [after round 2].
- `docs/decisions.md`: append dated lines for the Kappa result and the retrained model.
- Run pytest again.

### Task 6 (you, when the owner says so): commit and publish
- Commit on a new branch (e.g. `round-2`), push it, then ask the owner before moving `main`.
  The history is one straight line, so `main` can be fast-forwarded:
  `git switch main; git merge --ff-only round-2; git push origin main`.
- Never commit gitignored files.

### Task 7 (the owner): before submission
- Upload demo: on the Upload page, choose any PDF from `data/raw/`, click Analyse, then Explain
  on one question. The target is under 2 minutes end to end. Uploads took 2.5–11.9 s per paper.
- Take dashboard screenshots for the report.
- Write the report prose from `docs/report_outline.md`.
- Tell Dr. Tiwari about the deviations (listed in section 13 of the outline), especially:
  the dropped segmentation fallback model, the missed 90% segmentation target (80.0%), the
  difficulty model covering CS and AS only, and figures made by script instead of notebooks.

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
