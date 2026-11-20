# QuestionIQ report outline

An outline for the owner's report: headings, the points to make, the numbers to quote and
the figures to include. The prose is the owner's to write. Numbers come from
`reports/metrics/*.json`; reasons come from `docs/decisions.md` (cite the dated entries).
Items previously marked **[after round 2]** have been filled in with the final numbers from round 2 and retraining.

## 1. Abstract
- Problem: students revise from previous-year papers without knowing which topics recur
  or how hard questions tend to be.
- What was built: a classical NLP/ML pipeline (no LLMs) from scanned PDFs to a dashboard.
- Headline numbers: 148 papers, 1,155 questions; OCR CER 7.7%; NMF topics C_v 0.556
  (k = 12); difficulty macro-F1 0.412 vs baseline 0.212; 19/20 explanations sensible;
  Kappa 0.119 on 146 questions (target 0.6 missed).

## 2. Problem statement and objectives
- Restate the synopsis objectives: topic discovery, difficulty estimation, explainability,
  year-wise trends, dashboard.
- State the evaluation targets up front (the plan's table) so results can be judged against them.

## 3. Data collection
- Source: JKLU Paper Portal. Automated with Playwright: the owner signs in once by hand,
  the script reuses the session, waits 5 s between requests, skips what's downloaded.
- Listing the portal by year, because its paged listing fails past position 142 (decisions, 2026-11-06).
- 150 catalogued, 149 downloaded, 148 analysed (paper 116 duplicates paper 50); 115 courses,
  16 departments; years 2019–2025, mostly 2023 and 2024.
- Figures: `dataset_by_year.png`, `dataset_by_department.png`.

## 4. Text extraction and OCR
- Most papers are watermarked scans. pdfplumber first; Tesseract (psm 6, 300 dpi) otherwise.
- Three preprocessing methods compared on 13 hand-typed pages: layers (draw only the 1-bit
  scan layers, which leaves out the watermark) 7.7%, otsu 14.5%, adaptive 17.4%.
- Safety fallback: otsu is used when layers keeps under half of otsu's words.
- Caveats to state: the method was chosen and scored on the same pages; pages using the
  fallback are not measured; paper 101 alone is above 10%.
- Figure: `ocr_by_method.png`.

## 5. Question segmentation
- Rule-based: Q1 / Q.1.1 / 1(a) styles, OR options, marks parsing, CO labels, misread
  numbers kept and flagged.
- Unit rule: sub-parts are separate only when each has its own marks.
- Honest measurement: 48.9% on 10 studied papers, rules fixed, then **80.0%** on 10 fresh
  papers checked after the rules were frozen (commit bcf4dd1). Target 90%: **missed**.
- Remaining errors: numbered lists inside "1."-numbered papers, table rows with empty number
  cells, question numbers lost by OCR.
- Figure: `segmentation_before_after.png`.

## 6. Preprocessing
- Lowercase, OCR debris removed, hyphenated terms joined, NLTK + exam stopwords (checked by
  verb form too), WordNet noun lemmas, course codes and CO labels dropped.
- Owner's check: 17 of 20 cleaned questions keep their topic; fixes made from the notes.

## 7. Topic modelling
- Pooled model over all questions; words plus word pairs; min_df = 2.
- LDA on counts vs NMF on TF-IDF (deviation 1 from the synopsis), k = 4..15, C_v coherence.
- Result: NMF k = 12, C_v 0.556; LDA best k = 9, C_v 0.429.
- Noise words (MCQ "none of the options", course codes) first pushed the best k to the edge
  (k = 4); removing them gave a clear peak inside the range.
- Topic names given by the owner; topic–department NMI 0.23 (topics cut across subjects).
- Figure: `coherence_vs_k.png`; table: `reports/topic_keywords.csv`, `reports/topic_by_department.csv`.

## 8. Annotation
- Rubric written by the owner (`docs/rubric.md`), based on cognitive demand.
- Labelling page: marks hidden (marks is a model feature), shuffled order, link to the PDF.
- Round 1: 300 CS and AS questions (Easy 79, Medium 125, Hard 88, Skip 8). Limited to the
  subjects the owner could judge.
- Round 2: 150 questions (146 graded, 4 skips), at least 48 h later, new order. Kappa 0.119
  (observed agreement 43.8%, 64/146 agreed, 82 disagreements); target 0.6 missed.
- Figures: `label_distribution.png`, `kappa_matrix.png`.

## 9. Difficulty estimation
- Features: Bloom level of command verbs (standard revised Bloom list), word count, marks
  (with a missing flag), parts, numbers, formulas, technical words, main topic.
- Random Forest vs Logistic Regression vs majority baseline; nested stratified 5-fold CV
  with the grid search inside each training part.
- Result: retrained on 292 CS and AS questions (round 1 + 82 settled disagreements;
  Easy 73, Medium 136, Hard 83): macro-F1 RF 0.412 ± 0.082, LR 0.374 ± 0.058, baseline 0.212 ± 0.003.
  Accuracy RF 0.428 vs baseline 0.466.
- Discuss why the signal is weak: difficulty depends on content more than on surface features.
- The Bloom feature was corrected once (story verbs were counted); the score change was
  within the fold spread. Say so.
- Figures: `confusion_random_forest.png`, `confusion_logistic_regression.png`.

## 10. Explainability
- SHAP (TreeExplainer) per question: top 5 signed reasons and a "because" line.
- Logistic Regression coefficients per class.
- Strongest features overall: Bloom level, word count, marks, technical words.
- Owner's check on 20 unlabelled questions: 19 make sense by the rubric (target 15).
- Figure: `shap_importance.png`.

## 11. Trends across years
- Topic share by year, predicted difficulty by year (CS + AS), 18 concepts recurring in
  3+ years (word pairs such as fourier transform, truth table).
- Only 2023 vs 2024 has enough questions to compare; every chart shows n.
- Figures: `topic_share_by_year.png`, `difficulty_mix_by_year.png`.

## 12. System and dashboard
- SQLite database rebuilt by one command (`scripts/run_pipeline.py`, ~4.5 min, reproduces
  every result).
- Flask + Chart.js dashboard: question bank, Explain drawer, topics, trends, model report, upload.
- Upload: 2.5–11.9 s per paper (4 of 5 under the 10 s target).
- Screenshots: take them from the running app.

## 13. Deviations from the synopsis (with reasons)
1. LDA runs on counts, NMF on TF-IDF.
2. "Question generation" means the topic-wise question bank; no questions are generated.
3. The Logistic Regression segmentation fallback was dropped; its papers became the fresh test set.
4. OCR moved from future work into the core.
5. Topic models are pooled across subjects; department-level models were cut for time.
6. The difficulty model covers CS and AS only.
7. Report figures are made by a script, not notebooks (Jupyter isn't an allowed library).
8. Segmentation target (90%) missed: 80.0%.

## 14. Limitations and future work
- Segmentation of unusual layouts; OCR losing question numbers.
- More labels and more labellers (inter-annotator agreement), more subjects.
- Uneven years limit trend claims.
- Richer features for difficulty (e.g. solution length, prerequisite topics).

## 15. Conclusion
- What works well, what the numbers show, what was learned from the honest re-measurements.

## References
- Synopsis references, plus: Anderson & Krathwohl (2001) revised Bloom's taxonomy;
  Blei, Ng & Jordan (2003) LDA; Lee & Seung (1999) NMF; Röder, Both & Hinneburg (2015) C_v
  coherence; Lundberg & Lee (2017) SHAP; Cohen (1960) Kappa; Smith (2007) Tesseract.
