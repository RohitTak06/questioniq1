# Difficulty model results

- Labelled questions: 292 (Easy 79, Medium 125, Hard 88), CS and AS only
- Labels: round 1 (round 2 not settled yet)
- Scores: nested stratified 5-fold CV (grid search inside each training part), random_state=42
- Chosen model: **Random Forest**

| Model | Macro-F1 (mean ± sd) | Accuracy | Easy F1 | Medium F1 | Hard F1 |
| --- | --- | --- | --- | --- | --- |
| Random Forest | 0.370 ± 0.057 | 0.377 | 0.362 | 0.391 | 0.374 |
| Logistic Regression | 0.370 ± 0.081 | 0.373 | 0.360 | 0.387 | 0.370 |
| Majority baseline | 0.200 ± 0.001 | 0.428 | 0.000 | 0.600 | 0.000 |

## Per-class precision and recall

**Random Forest**

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| Easy | 0.327 | 0.405 | 0.362 | 79 |
| Medium | 0.453 | 0.344 | 0.391 | 125 |
| Hard | 0.354 | 0.398 | 0.374 | 88 |

**Logistic Regression**

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| Easy | 0.333 | 0.392 | 0.360 | 79 |
| Medium | 0.471 | 0.328 | 0.387 | 125 |
| Hard | 0.330 | 0.420 | 0.370 | 88 |

**Majority baseline**

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| Easy | 0.000 | 0.000 | 0.000 | 79 |
| Medium | 0.428 | 1.000 | 0.600 | 125 |
| Hard | 0.000 | 0.000 | 0.000 | 88 |
