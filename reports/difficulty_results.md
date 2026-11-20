# Difficulty model results

- Labelled questions: 292 (Easy 73, Medium 136, Hard 83), CS and AS only
- Labels: round 1, with 82 settled after round 2
- Scores: nested stratified 5-fold CV (grid search inside each training part), random_state=42
- Chosen model: **Random Forest**

| Model | Macro-F1 (mean ± sd) | Accuracy | Easy F1 | Medium F1 | Hard F1 |
| --- | --- | --- | --- | --- | --- |
| Random Forest | 0.412 ± 0.082 | 0.428 | 0.323 | 0.492 | 0.436 |
| Logistic Regression | 0.374 ± 0.058 | 0.384 | 0.331 | 0.396 | 0.417 |
| Majority baseline | 0.212 ± 0.003 | 0.466 | 0.000 | 0.636 | 0.000 |

## Per-class precision and recall

**Random Forest**

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| Easy | 0.295 | 0.356 | 0.323 | 73 |
| Medium | 0.556 | 0.441 | 0.492 | 136 |
| Hard | 0.406 | 0.470 | 0.436 | 83 |

**Logistic Regression**

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| Easy | 0.284 | 0.397 | 0.331 | 73 |
| Medium | 0.512 | 0.324 | 0.396 | 136 |
| Hard | 0.375 | 0.470 | 0.417 | 83 |

**Majority baseline**

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| Easy | 0.000 | 0.000 | 0.000 | 73 |
| Medium | 0.466 | 1.000 | 0.636 | 136 |
| Hard | 0.000 | 0.000 | 0.000 | 83 |
