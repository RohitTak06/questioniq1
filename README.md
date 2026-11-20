# QuestionIQ

AI-based exam pattern analysis for JKLU previous-year question papers (PYQs).
A mini project at JK Lakshmipat University, guided by Dr. Devisha Tiwari.

QuestionIQ reads scanned question papers, splits them into questions, finds the topics
that run through them, rates each question Easy / Medium / Hard, explains every rating,
and shows year-wise trends in a web dashboard.

It is a **self-trained classical NLP/ML system**: no LLM or hosted AI API is used anywhere,
and every difficulty label the model learns from was given by hand by the project owner.

```
PDF papers (JKLU Paper Portal)
  -> text: pdfplumber, else OCR (Tesseract on the 1-bit scan layers, without the watermark)
  -> questions: rule-based segmentation (Q1, Q.1.1, 1(a), OR options, marks, CO)
  -> cleaned words: NLTK stopwords + exam words, WordNet lemmas
  -> topics: LDA (counts) vs NMF (TF-IDF), k = 4..15 chosen by C_v coherence
  -> difficulty: Random Forest vs Logistic Regression vs majority baseline (nested 5-fold CV)
  -> explanations: SHAP for the forest, coefficients for logistic regression, topic keywords
  -> trends by year, SQLite database, Flask + Chart.js dashboard
```

## Results

| Stage | Measure | Result | Target |
| --- | --- | --- | --- |
| Collection | Papers downloaded / subjects | 149 papers, 115 courses (148 analysed) | ≥ 20 subjects |
| OCR | Character error rate, 13 hand-typed pages | **7.7%** (layers method; otsu 14.5%, adaptive 17.4%) | ≤ 10% |
| Segmentation | Questions split correctly, 10 fresh papers | **80.0%** (64/80); 48.9% before the rule fixes | ≥ 90% (**missed**) |
| Preprocessing | Cleaned questions that keep their topic | 17 of 20 | owner's check |
| Topics | Best C_v coherence | **NMF k = 12: 0.556**; LDA k = 9: 0.429 | best k by C_v |
| Annotation | Cohen's Kappa, round 1 vs round 2 | **0.119** on 146 questions (64/146 agreed, 82 settled) | ≥ 0.6 (**missed**) |
| Difficulty | Macro-F1, nested stratified 5-fold CV | **RF 0.412**, LR 0.374, baseline 0.212 | beats the baseline |
| Explanations | Reasons that make sense by the rubric | 19 of 20 | ≥ 15 of 20 |
| System | Seconds per uploaded paper | 2.5–11.9 s (4 of 5 under target) | < 10 s |

Every number comes from `reports/metrics/*.json`, and every choice behind it is logged with
its reason in [`docs/decisions.md`](docs/decisions.md). Missed targets are reported as they are.

**Limits worth knowing**

- The difficulty model was trained on 292 labelled **CS and AS** questions only (round 1 plus 82 settled disagreements; Easy 73, Medium 136, Hard 83). Predictions for other departments are marked "outside training subjects".
- Difficulty accuracy (0.428) does not beat always answering "Medium" (0.466); macro-F1, the target measure, does.
- Most questions come from 2023 (643) and 2024 (409), so only those years support trend
  comparisons; every chart shows its question counts.

## Setup (Windows, PowerShell)

1. Install **Python 3.11** and **Tesseract OCR 5** (default path
   `C:\Program Files\Tesseract-OCR\tesseract.exe`, as in `config.yaml`).
2. From the project folder:
   ```powershell
   py -3.11 -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   .venv\Scripts\python.exe -m pip install -e . --no-deps
   .venv\Scripts\python.exe -c "import nltk; nltk.download('stopwords'); nltk.download('wordnet'); nltk.download('omw-1.4')"
   ```
3. Check everything works:
   ```powershell
   .venv\Scripts\python.exe -m pytest -q
   ```

**The papers are not in this repository.** `data/raw/` is filled by
`src/questioniq/scrape.py` from the JKLU Paper Portal, which needs a JKLU login: the script
opens a browser window, you sign in by hand once, and it reuses that session. It never
stores a password. The catalogue and manifest (`data/catalogue.csv`, `data/manifest.csv`)
list every paper.

## Run it

Rebuild everything from `data/raw/` with one command (about 4.5 minutes; OCR is cached):

```powershell
.venv\Scripts\python.exe scripts/run_pipeline.py
```

It runs, in order: `run_extraction`, `run_segmentation`, `run_preprocess`, `run_topics`,
`run_difficulty`, `run_explain`, `run_trends`, `make_figures`, `build_db`. It never touches
the owner's labels, rubric, topic names or check sheets.

Start the dashboard:

```powershell
.venv\Scripts\python.exe -m flask --app app run
```

and open http://127.0.0.1:5000/.

## 5-step demo

1. **Home**: totals for the 148 papers and 1,155 questions.
2. **Questions**: filter Department = CS, Difficulty = Hard, keyword "tree".
3. Click **Explain** on a question: the prediction, its probabilities, the owner's label (if
   labelled), the 5 strongest SHAP reasons and the topic keywords found.
4. **Trends** and **Model report**: topic share and difficulty by year; every evaluation
   number with the LDA-vs-NMF and RF-vs-LR comparisons.
5. **Upload**: choose any question-paper PDF, then click **Explain** on one of its questions.

## Project layout

```
src/questioniq/   scrape extract segment preprocess annotate topics features
                  difficulty explain trends db infer pipeline
app/              Flask app: dashboard.py (pages), routes.py (labelling), templates/, static/
scripts/          one script per pipeline stage, plus the owner's check scorers
tests/            pytest suite (run with pytest -q)
config.yaml       every setting: paths, k range, thresholds, stopwords, random_state = 42
bloom_verbs.yaml  revised Bloom's taxonomy verb list (Anderson & Krathwohl, 2001)
docs/             synopsis, plan, decisions log, rubric, report outline
reports/          metrics (JSON), figures (PNG), trend tables
data/             catalogue, manifest, labels, features, topics (exam text stays local)
```

## Rules this project follows

- No LLM or hosted AI API in `src/` or `app/` (a test checks this).
- Difficulty labels and topic names are written only by the owner.
- Every random process uses `random_state=42`.
- Exam text, the portal session and the database stay out of git.
