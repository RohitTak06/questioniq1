# Decisions log

Append-only. One line per decision: `date | area | decision | reason`.

2026-11-07 | reproducibility | `random_state=42` for every random process | Results must be repeatable (project rule).
2026-11-07 | topics | Sweep k = 4..15 and choose by best C_v | Choose k by a measured score, as the synopsis promises.
2026-11-07 | topics | LDA on raw counts, NMF on TF-IDF | LDA models word counts, so this deviates from the synopsis on purpose.
2026-11-07 | topics | Train on the pooled question set, not per subject | Most subjects have 1 to 3 papers, too few questions for a stable per-subject model.
2026-11-07 | dependencies | Pin `pymupdf==1.28.2`, not 2.x | 2.x requires `pymupdf4llm`, `pymupdf-layout` and `onnxruntime`; we only render pages to images.
2026-11-07 | dependencies | Pin `opencv-python-headless==4.14.0.94`, not 5.0 | 5.0 is a new major version; we only need basic image operations.
2026-11-07 | dependencies | Pin `scipy==1.17.1` | Not on the original allowed list, but scikit-learn and gensim require it; the pin keeps installs repeatable. Approved by the owner.
