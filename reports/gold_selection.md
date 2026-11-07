# Hand-work selection

Drawn once with `random_state=42`; papers are not swapped afterwards.

## 3 pages to type (one each from low, middle and high OCR confidence)

| Type into | PDF | Page | OCR confidence |
| --- | --- | --- | --- |
| `data/ocr_gold/101_p1.txt` | `data/raw/AS1109/2023_Endterm_101.pdf` | 1 | 81.3 |
| `data/ocr_gold/89_p4.txt` | `data/raw/ID1104/2023_Endterm_89.pdf` | 4 | 83.7 |
| `data/ocr_gold/145_p1.txt` | `data/raw/ME1223/2023_Endterm_145.pdf` | 1 | 88.7 |

## How to type a reference page

- Open the PDF at the page shown, and type into the blank `.txt` file named above.
- Type from the PDF. Do not start from OCR output, or the error rate will come out too low.
- Type line by line, left to right across the whole page, including headers, the marks
  and CO column, and "Page 1 of 4". Don't type the watermark.
- Type symbols as best you can (λ, ≤, x^2). Missing symbols will count as OCR errors,
  which is correct: they are.
- Case and punctuation count. Spacing and table lines don't.

## 10 papers to check

| Paper | Course | PDF |
| --- | --- | --- |
| 33 | MA1105 | `data/raw/MA1105/2020_Endterm_33.pdf` |
| 38 | AS1202 | `data/raw/AS1202/2024_Endterm_38.pdf` |
| 49 | CS1132 | `data/raw/CS1132/2024_Endterm_49.pdf` |
| 53 | CS1140 | `data/raw/CS1140/2024_Endterm_53.pdf` |
| 59 | CS1236 | `data/raw/CS1236/2024_Endterm_59.pdf` |
| 64 | EE1228 | `data/raw/EE1228/2024_Endterm_64.pdf` |
| 131 | CS1227 | `data/raw/CS1227/2023_Endterm_131.pdf` |
| 140 | CE1206 | `data/raw/CE1206/2023_Endterm_140.pdf` |
| 160 | CS1135 | `data/raw/CS1135/2023_Other_160.pdf` |
| 169 | AS1114 | `data/raw/AS1114/2025_Midterm_169.pdf` |

## How to check a paper

For each paper, open its PDF next to `reports/segmentation_review/<paper_id>.md`, and fill in
`data/seg_gold/segmentation_check.csv`:

- `owner_total`: how many questions the paper really has, counting by the rule below.
- `owner_correct`: how many of those appear in the review file as one correct row: the right
  start and end, not merged with another question and not cut in two.
- `notes`: anything odd. OCR typos inside a question don't make it wrong here; the OCR score
  measures those.

The counting rule: one row per question, except that sub-parts count separately only when
each has its own marks, and each OR option counts separately. MCQ options are not separate.

## Numbering styles across all papers

- number: 24 papers
- q: 116 papers
- table: 8 papers

## Reserved papers for the fallback model (only if we keep it)

23, 24, 31, 51, 55, 63, 92, 103, 127, 143
