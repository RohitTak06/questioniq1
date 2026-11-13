# Second segmentation check (fresh papers)

The segmentation rules were fixed after the first check and are now frozen.
These papers were reserved when the first selection was drawn and were not
looked at while fixing, so this score is the honest one.

| Paper | Course | PDF | Review file |
| --- | --- | --- | --- |
| 23 | ED1109 | `data/raw/ED1109/2024_Endterm_23.pdf` | `reports/segmentation_review/23.md` |
| 24 | FA1101 | `data/raw/FA1101/2024_Endterm_24.pdf` | `reports/segmentation_review/24.md` |
| 31 | MA1102 | `data/raw/MA1102/2024_Endterm_31.pdf` | `reports/segmentation_review/31.md` |
| 51 | CS1134 | `data/raw/CS1134/2024_Endterm_51.pdf` | `reports/segmentation_review/51.md` |
| 55 | CS1142 | `data/raw/CS1142/2024_Endterm_55.pdf` | `reports/segmentation_review/55.md` |
| 63 | EE1227 | `data/raw/EE1227/2024_Endterm_63.pdf` | `reports/segmentation_review/63.md` |
| 92 | LS1103 | `data/raw/LS1103/2023_Endterm_92.pdf` | `reports/segmentation_review/92.md` |
| 103 | AS2202 | `data/raw/AS2202/2023_Endterm_103.pdf` | `reports/segmentation_review/103.md` |
| 127 | AS1406 | `data/raw/AS1406/2023_Endterm_127.pdf` | `reports/segmentation_review/127.md` |
| 143 | CS1228 | `data/raw/CS1228/2023_Endterm_143.pdf` | `reports/segmentation_review/143.md` |

## How to check a paper

For each paper, open its PDF next to `reports/segmentation_review/<paper_id>.md`, and fill in
`data/seg_gold/segmentation_check_fresh.csv`:

- `owner_total`: how many questions the paper really has, counting by the rule below.
- `owner_correct`: how many of those appear in the review file as one correct row: the right
  start and end, not merged with another question and not cut in two.
- `notes`: anything odd. OCR typos inside a question don't make it wrong here; the OCR score
  measures those.

The counting rule: one row per question, except that sub-parts count separately only when
each has its own marks, and each OR option counts separately. MCQ options are not separate.
