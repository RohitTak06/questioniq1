# Decisions log

Append-only. One line per decision: `date | area | decision | reason`.

2026-11-07 | reproducibility | `random_state=42` for every random process | Results must be repeatable (project rule).
2026-11-07 | topics | Sweep k = 4..15 and choose by best C_v | Choose k by a measured score, as the synopsis promises.
2026-11-07 | topics | LDA on raw counts, NMF on TF-IDF | LDA models word counts, so this deviates from the synopsis on purpose.
2026-11-07 | topics | Train on the pooled question set, not per subject | Most subjects have 1 to 3 papers, too few questions for a stable per-subject model.
2026-11-07 | dependencies | Pin `pymupdf==1.28.2`, not 2.x | 2.x requires `pymupdf4llm`, `pymupdf-layout` and `onnxruntime`; we only render pages to images.
2026-11-07 | dependencies | Pin `opencv-python-headless==4.14.0.94`, not 5.0 | 5.0 is a new major version; we only need basic image operations.
2026-11-07 | dependencies | Pin `scipy==1.17.1` | Not on the original allowed list, but scikit-learn and gensim require it; the pin keeps installs repeatable. Approved by the owner.
2026-11-07 | collection | Download every eligible paper, not just 20 subjects | About 150 papers across 127 courses is thin, so we keep all of it. Approved by the owner.
2026-11-07 | collection | Keep papers typed Other, labelled `Other`; skip titles containing "assignment" or "coding hour" | Sampled Other titles look like real papers; the summary lists them so the owner can exclude any. Approved by the owner.
2026-11-07 | collection | `has_text_layer` is true if any page has at least 50 characters of text | Same threshold as `extraction.min_chars_per_page`, so a watermark alone does not count as text.
2026-11-07 | collection | 5 s between requests, retries after 15, 30 and 60 s | At about 1.5 s apart the backend returned 500 or reset the connection on list page 4; the same page worked at 6 s apart.
2026-11-07 | collection | Correction to the line above: spacing was not the main cause. List papers one year at a time | The plain list answers 500 past position 142 at any speed, while year filters reach all 150. The 5 s gap stays as a precaution against occasional connection resets.
2026-11-07 | extraction | `table_digit_ratio` = 0.35 | Real statistical table pages scored 0.39 to 0.81 and the next highest page 0.21, so 0.35 falls in the gap.
2026-11-07 | segmentation | One row per question; sub-parts are separate only when each has its own marks; each OR option is its own row; MCQ options stay in the text | A sub-part without its own marks has no separate marks to learn from. Approved by the owner.
2026-11-07 | segmentation | Paper 116 is excluded from analysis | Identical file to paper 50, so its questions would be counted twice. Approved by the owner.
2026-11-07 | segmentation | Misread question numbers are kept and flagged, not corrected | Numbers can really skip, so a guess could be wrong. The split boundary is still right.
